from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import json


# Forward import for type checking – real instance is passed at runtime
from modules.defaults import *
from modules.data_classes import *
from utils import parse_duration
from widgets.slurm_connection_widget import SlurmConnection
__all__ = [
    "Job",
    "Project",
    "ProjectStore",
]


class ProjectStoreSignals(QObject):
    """Separate QObject to handle signals for ProjectStore"""
    job_status_changed = pyqtSignal(
        Project, Job, str, str)  # project, job_id, old_status, new_status
    job_updated = pyqtSignal(Project, Job)  # project, job_id
    project_stats_changed = pyqtSignal(Project, dict)  # project, stats_dict



class ProjectStore:
    """Thread‑safe singleton that mirrors a remote *settings.ini* file."""
    _instance: "ProjectStore | None" = None
    _lock = RLock()

    def __new__(cls, slurm: SlurmConnection, remote_path: Optional[str] = None):

        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init(slurm, remote_path)
            return cls._instance

    # ------------------------------------------------------------------
    # initialisation & helpers
    # ------------------------------------------------------------------
    def _init(self, slurm_connection_widget, remote_path: Optional[str] = None):
        # if not slurm.check_connection():
        #     raise RuntimeError("SlurmConnection must be *connected* before using ProjectStore")
        self.signals = ProjectStoreSignals()
        self.slurm = slurm_connection_widget
        self._projects: Dict[str, Project] = {}
        # Where to put the INI on the cluster
        if remote_path is None:
            home = (
                self.slurm.remote_home
                or self.slurm.run_command("echo $HOME")[0].strip()
            )
            remote_path = f"{home}/.slurm_gui/project_settings.ini"
        self.remote_path = remote_path

        # Local temporary copy (lives for the whole session)
        self._tmp_local = Path(tempfile.mkdtemp()) / "project_settings.ini"

        self._download_remote()
        self.settings = QSettings(
            str(self._tmp_local), QSettings.Format.IniFormat)
        self.settings.setFallbacksEnabled(False)

        self._projects: Dict[str, Project] = self._read_from_settings()
        self.job_monitor = None
        self._start_job_monitoring()

    # .................................................................
    def _download_remote(self) -> None:
        """Fetch the INI from the cluster (create it if missing)."""
        try:
            sftp = self.slurm.client.open_sftp()
            remote_dir = Path(self.remote_path).parent.as_posix()
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                sftp.mkdir(remote_dir)

            try:
                sftp.get(self.remote_path, str(self._tmp_local))
            except FileNotFoundError:
                # First run → create an empty file and upload it
                self._tmp_local.touch()
                sftp.put(str(self._tmp_local), self.remote_path)
        finally:
            sftp.close()

    def _upload_remote(self) -> None:
        """Push the local INI back to the cluster."""
        self.settings.sync()
        try:
            sftp = self.slurm.client.open_sftp()
            sftp.put(str(self._tmp_local), self.remote_path)
        finally:
            sftp.close()

    def _read_from_settings(self) -> Dict[str, Project]:
        raw = self.settings.value("projects/data", "")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return {
                name: Project.from_json(name, pj_data) for name, pj_data in data.items()
            }
        except Exception as e:
            print(f"Error reading project data: {e}")
            # corrupted → reset
            return {}

    def _write_to_settings(self) -> None:
        """Write projects to settings with enhanced error handling"""
        try:
            # Convert projects to JSON-serializable format
            data = {}
            for name, project in self._projects.items():
                try:
                    project_data = project.to_json()
                    # Double-check that the data is actually JSON serializable
                    json.dumps(project_data)
                    data[name] = project_data
                except (TypeError, ValueError) as e:
                    print(f"Error serializing project '{name}': {e}")
                    # Skip this project or create a fallback representation
                    data[name] = {
                        "name": name,
                        "jobs": [],
                        "error": f"Serialization failed: {str(e)}"
                    }

            # Convert to JSON string and save
            json_str = json.dumps(data)
            self.settings.setValue("projects/data", json_str)
            self._upload_remote()

        except Exception as e:
            print(f"Critical error in _write_to_settings: {e}")
            # Try to save a minimal backup
            try:
                backup_data = {name: {"name": name, "jobs": []}
                               for name in self._projects.keys()}
                self.settings.setValue(
                    "projects/data", json.dumps(backup_data))
                self._upload_remote()
                print("Saved minimal backup data")
            except Exception as backup_error:
                print(f"Failed to save backup: {backup_error}")
                raise e  # Re-raise original error
    # ------------------------------------------------------------------
    # Public API (project level)
    # ------------------------------------------------------------------

    def all_projects(self) -> List[str]:
        """Get names of all projects"""
        return list(self._projects.keys())

    def add_project(self, name: str, *, jobs: Optional[List[Job]] = None) -> None:
        """Add a new project or update an existing one with jobs"""
        if name in self._projects:
            # Project exists, update jobs if provided
            if jobs:
                for job in jobs:
                    self._projects[name].add_job(job)
        else:
            # Create new project
            self._projects[name] = Project(name, jobs or [])

        self._write_to_settings()

    def remove_project(self, name: str) -> None:
        """Remove a project by name"""
        if name not in self._projects:
            return
        self._projects.pop(name)
        self._write_to_settings()

    # ------------------------------------------------------------------
    # Public API (job level)
    # ------------------------------------------------------------------
    def get(self, name: str) -> Optional[Project]:
        """Get a project by name"""
        return self._projects.get(name)

    def add_job(self, project: str, job: Job) -> None:
        """Add a job to a project (creates project if it doesn't exist)"""
        self._projects.setdefault(project, Project(project)).add_job(job)
        self._write_to_settings()

    def get_job(self, project: str, job_id: Union[int, str]) -> Optional[Job]:
        """Get a job by project name and job ID"""
        pj = self._projects.get(project)
        if not pj:
            return None
        return pj.get_job(job_id)

    def remove_job(self, project: str, job: Job) -> None:
        """Remove a job from a project"""
        pj = self._projects.get(project.name)
        if not pj:
            return
        pj.remove_job(job.id)
        self._write_to_settings()

    def add_new_job(self, project: str, job_details: Dict[str, Any]) -> Optional[str]:
        try:
            # Create Job object using SlurmConnection helper
            job = Job.create_job_from_details(job_details)

            # Handle job arrays by creating multiple Job objects
            if job.array_spec:
                created_jobs = self._create_array_jobs(
                    project, job, job_details)
                return created_jobs
            else:
                # Single job
                self.add_job(project, job)
                return job

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Job creation failed: {e}")

    def _create_array_jobs(self, project: str, base_job: 'Job', job_details: Dict[str, Any]) -> List[str]:
        """
        Create multiple Job objects for job arrays.

        Args:
            project: Project name
            base_job: Base Job object with array specification
            job_details: Original job details

        Returns:
            List[str]: List of created job IDs
        """
        def parse_array_spec(spec):
            """Parse array specification into task IDs"""
            result = []
            if not spec:
                return result

            if "," in spec:
                for part in spec.split(","):
                    part = part.strip()
                    if "-" in part:
                        if ":" in part:
                            rng, step = part.split(":")
                            start, end = map(int, rng.split("-"))
                            step = int(step)
                            result.extend(list(range(start, end+1, step)))
                        else:
                            start, end = map(int, part.split("-"))
                            result.extend(list(range(start, end+1)))
                    else:
                        try:
                            result.append(int(part))
                        except Exception:
                            pass
            elif "-" in spec:
                if ":" in spec:
                    rng, step = spec.split(":")
                    start, end = map(int, rng.split("-"))
                    step = int(step)
                    result.extend(list(range(start, end+1, step)))
                else:
                    start, end = map(int, spec.split("-"))
                    result.extend(list(range(start, end+1)))
            else:
                try:
                    result.append(int(spec))
                except Exception:
                    pass

            return sorted(set(result))

        # Parse array specification
        task_ids = parse_array_spec(base_job.array_spec)
        if not task_ids:
            task_ids = [0]  # Fallback

        # Modify output/error files for arrays ONLY if user did not specify %a or %A_%a
        def needs_array_placeholder(path):
            # Accepts %a or %A_%a or %A.%a or %A-%a as valid
            return not any(p in path for p in ["%a", "%A_%a", "%A.%a", "%A-%a"])

        output_file = base_job.output_file
        error_file = base_job.error_file

        # Only modify if user did not specify a valid array placeholder
        if needs_array_placeholder(output_file):
            if "%A" in output_file:
                output_file = output_file.replace("%A", "%A_%a")
            else:
                output_file = output_file.replace(".log", "_%a.log")

        if needs_array_placeholder(error_file):
            if "%A" in error_file:
                error_file = error_file.replace("%A", "%A_%a")
            else:
                error_file = error_file.replace(".log", "_%a.log")

        created_ids = []
        created_jobs = []
        # Create individual Job objects for each array task
        for task_id in task_ids:
            # Create a copy of the base job for this array task
            array_job = Job(
                id=f"{base_job.id}_{task_id}",
                name=f"{base_job.name}[{task_id}]",
                status="NOT_SUBMITTED",
                command=base_job.command,
                partition=base_job.partition,
                account=base_job.account,
                time_limit=base_job.time_limit,
                nodes=base_job.nodes,
                cpus=base_job.cpus,
                ntasks=base_job.ntasks,
                ntasks_per_node=base_job.ntasks_per_node,
                memory=base_job.memory,
                memory_per_cpu=base_job.memory_per_cpu,
                memory_per_node=base_job.memory_per_node,
                memory_per_gpu=base_job.memory_per_gpu,
                gpus=base_job.gpus,
                gres=base_job.gres,
                constraints=base_job.constraints,
                qos=base_job.qos,
                reservation=base_job.reservation,
                nodelist=base_job.nodelist,
                exclude=base_job.exclude,
                begin_time=base_job.begin_time,
                deadline=base_job.deadline,
                dependency=base_job.dependency,
                array_spec=str(task_id),  # Individual task ID
                array_max_jobs=base_job.array_max_jobs,
                ntasks_per_core=base_job.ntasks_per_core,
                ntasks_per_socket=base_job.ntasks_per_socket,
                sockets_per_node=base_job.sockets_per_node,
                cores_per_socket=base_job.cores_per_socket,
                wait=base_job.wait,
                wrap=base_job.wrap,
                output_file=output_file.replace("%a", str(task_id)),
                error_file=error_file.replace("%a", str(task_id)),
                input_file=base_job.input_file,
                working_dir=base_job.working_dir,
                priority=base_job.priority,
                nice=base_job.nice,
                requeue=base_job.requeue,
                no_requeue=base_job.no_requeue,
                reboot=base_job.reboot,
                mail_type=base_job.mail_type,
                mail_user=base_job.mail_user,
                export_env=base_job.export_env,
                get_user_env=base_job.get_user_env,
                exclusive=base_job.exclusive,
                overcommit=base_job.overcommit,
                oversubscribe=base_job.oversubscribe,
                threads_per_core=base_job.threads_per_core,
            )

            # Copy additional info
            array_job.info = base_job.info.copy()
            array_job.info['array_task_id'] = task_id
            array_job.info['submission_details'] = job_details

            # Add to project
            self.add_job(project, array_job)
            created_jobs.append(array_job)
            created_ids.append(array_job.id)

        return array_job

    def submit_job(self, project: Project, job: Job) -> Optional[str]:
        """
        Enhanced submit method using the new Job-based submission system.

        Args:
            project: Project name
            job_id: Job ID to submit

        Returns:
            str: New job ID if successful, None otherwise
        """
        if not self.slurm or not self.slurm.check_connection():
            raise ConnectionError("Not connected to SLURM")

        # Skip if job is already submitted
        if job.status != "NOT_SUBMITTED":
            return job.id

        try:
            # Get Discord settings from job info
            discord_settings = job.info.get("discord_notifications", {})

            # Submit job using the enhanced method
            new_job_id = self.slurm.submit_job(
                job, discord_settings)

            if new_job_id:
                # Update the job with the new ID and status
                old_id = job.id
                job.id = new_job_id
                job.status = "PENDING"
                job.submission_time = datetime.now()

                # Remove temporary submission details to save space
                if "submission_details" in job.info:
                    del job.info["submission_details"]

                # Save changes
                self._write_to_settings()

                return new_job_id

            return None

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Job submission failed: {e}")

    def get_job_script_preview(self, project: str, job_id: str) -> str:
        """
        Get a preview of the sbatch script for a job without submitting it.

        Args:
            project: Project name
            job_id: Job ID

        Returns:
            str: Generated sbatch script content
        """
        project_obj = self.get(project)
        if not project_obj:
            raise ValueError(f"Project {project} not found")

        job = project_obj.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in project {project}")

        # Get Discord settings if available
        discord_settings = job.info.get("discord_notifications", {})
        include_discord = discord_settings.get("enabled", False)

        return job.generate_sbatch_script(
            include_discord=include_discord,
            discord_settings=discord_settings if include_discord else None
        )

    def validate_job(self, project: str, job_id: str) -> List[str]:
        """
        Validate a job's parameters.

        Args:
            project: Project name
            job_id: Job ID

        Returns:
            List[str]: List of validation issues
        """
        project_obj = self.get(project)
        if not project_obj:
            return [f"Project {project} not found"]

        job = project_obj.get_job(job_id)
        if not job:
            return [f"Job {job_id} not found in project {project}"]

        return job.validate_parameters()

    def get_job_resource_summary(self, project: str, job_id: str) -> Dict[str, Any]:
        """
        Get a summary of resources requested by a job.

        Args:
            project: Project name
            job_id: Job ID

        Returns:
            Dict[str, Any]: Resource summary
        """
        project_obj = self.get(project)
        if not project_obj:
            return {}

        job = project_obj.get_job(job_id)
        if not job:
            return {}

        return job.get_resource_summary()
    # ------------------------------------------------------------------
    # Convenience / debugging helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover – convenience only
        return f"<ProjectStore {self._projects}>"
    # ------------------------------------------------------------------
    # Job Monitoring
    # ------------------------------------------------------------------

    def _start_job_monitoring(self):
        """Start job monitoring with MVC integration"""

        if self.job_monitor is not None:
            self.job_monitor.stop()
            self.job_monitor.wait()

        if not self.slurm or not self.slurm.check_connection():
            print("Cannot start job monitoring - no SLURM connection")
            return

        # Pass the MVC widget instead of raw connection
        # self.job_monitor = JobStatusMonitor(
        #     self.slurm, self, update_interval=5)

        # Connect signals - same as before
        self.job_monitor.job_status_updated.connect(self._on_job_status_updated)
        self.job_monitor.job_details_updated.connect(self._on_job_details_updated)
        self.job_monitor.jobs_batch_updated.connect(self._on_jobs_batch_updated)

        self.job_monitor.start()
        print("Started job status monitoring")
        

    def stop_job_monitoring(self):
        """Stop the background job status monitoring"""
        if self.job_monitor is not None:
            self.job_monitor.stop()
            self.job_monitor.wait()
            self.job_monitor = None
            print("Stopped job status monitoring")

    def _on_job_status_updated(self, project_name: str, job_id: str, new_status: str):
        """Simplified job status update handler without Discord notifications"""
        print(
            f"[JOB_UPDATE] Processing status update: {project_name}/{job_id} -> {new_status}")

        project = self.get(project_name)
        if not project:
            print(f"[JOB_UPDATE] Project not found: {project_name}")
            return

        job = project.get_job(job_id)
        if not job:
            print(f"[JOB_UPDATE] Job not found: {job_id}")
            return

        old_status = job.status
        print(f"[JOB_UPDATE] Status change: {old_status} -> {new_status}")

        # Update the job status
        job.status = new_status

        # Update timing based on new status
        now = datetime.now()
        if new_status == "RUNNING" and not job.start_time:
            job.start_time = now
        elif new_status in ["COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"] and not job.end_time:
            job.end_time = now

        # Save changes to storage
        self._write_to_settings()

        # Emit UI update signals
        self.signals.job_status_changed.emit(
            project, job, old_status, new_status)
        self.signals.job_updated.emit(project, job)

        # Update project statistics
        stats = project.get_job_stats()
        self.signals.project_stats_changed.emit(project, stats)

    def _on_job_details_updated(self, project_name, job_id):
        # Look up Project and Job objects before emitting the signal
        project = self.get(project_name) if hasattr(self, 'get') else None
        job = project.get_job(job_id) if project and hasattr(project, 'get_job') else None
        if project and job:
            self.signals.job_updated.emit(project, job)

    def _on_jobs_batch_updated(self, updated_projects: dict):
        """Handle batch job updates from monitor"""
        for project_name, job_updates in updated_projects.items():
            project = self.get(project_name)
            if not project:
                continue

            # Update project statistics after batch changes
            stats = project.get_job_stats()
            self.signals.project_stats_changed.emit(project, stats)

    def update_job_status(self, project: str, job_id: Union[int, str], status: str) -> None:
        """Update the status of a job (enhanced version)"""
        pj = self._projects.get(project)
        if not pj:
            return

        job = pj.get_job(job_id)
        if job:
            old_status = job.status
            job.status = status

            # Update timing information based on status changes
            now = datetime.now()
            if status == "RUNNING" and old_status in ["PENDING", "NOT_SUBMITTED"] and not job.start_time:
                job.start_time = now
            elif status in ["COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"] and not job.end_time:
                job.end_time = now

            self._write_to_settings()

            # Emit signal for UI updates using signals object
            # self.signals.job_status_changed.emit(
            #     project, str(job_id), old_status, status)

    def get_active_jobs(self) -> List[Tuple[str, Job]]:
        """Get all jobs that are currently active (need monitoring)"""
        active_jobs = []
        active_statuses = {'PENDING', 'RUNNING',
                           'COMPLETING', 'SUSPENDED', 'PREEMPTED'}

        for project_name, project in self._projects.items():
            for job in project.jobs:
                if job.status in active_statuses and job.status != 'NOT_SUBMITTED':
                    active_jobs.append((project_name, job))

        return active_jobs

    def _update_job_from_sacct(self, job: Job, slurm_data: Dict[str, Any]):
        """Update job object with data from sacct"""
        # Update timing information
        if slurm_data.get('Start') and slurm_data['Start'] not in ['Unknown', 'None']:
            try:
                job.start_time = datetime.strptime(
                    slurm_data['Start'], '%Y-%m-%dT%H:%M:%S')
            except (ValueError, TypeError):
                pass

        if slurm_data.get('End') and slurm_data['End'] not in ['Unknown', 'None']:
            try:
                job.end_time = datetime.strptime(
                    slurm_data['End'], '%Y-%m-%dT%H:%M:%S')
            except (ValueError, TypeError):
                pass

        # Update elapsed time
        if slurm_data.get('Elapsed'):
            try:
                job.time_used = parse_duration(slurm_data['Elapsed'])
            except (ValueError, TypeError):
                pass

        # Update resource information
        if slurm_data.get('AllocCPUS'):
            try:
                job.cpus = int(slurm_data['AllocCPUS'])
            except (ValueError, TypeError):
                pass

        # Update node and reason information
        if slurm_data.get('NodeList'):
            job.nodelist = slurm_data['NodeList']

        if slurm_data.get('Reason'):
            job.reason = slurm_data['Reason']

        # Store additional information
        job.info.update({
            'exit_code': slurm_data.get('ExitCode'),
            'max_rss': slurm_data.get('MaxRSS'),
            'last_sacct_update': datetime.now().isoformat()
        })

    def __del__(self):
        """Cleanup when store is destroyed"""
        self.stop_job_monitoring()

    def get_project_by_obj(self, project: Project) -> Project:
        """Return the canonical Project object from the store (by name)."""
        return self._projects.get(project.name, project)

    def get_job_by_obj(self, project: Project, job: Job) -> Job:
        """Return the canonical Job object from the store (by project and job id)."""
        proj = self.get_project_by_obj(project)
        return proj.get_job(job.id) if proj else job

    def submit_job_obj(self, project: Project, job: Job) -> Optional[str]:
        """Submit a job using Project and Job objects."""
        return self.submit_job(project.name, job.id)

    def get_job_script_preview_obj(self, project: Project, job: Job) -> str:
        return self.get_job_script_preview(project.name, job.id)

    def validate_job_obj(self, project: Project, job: Job) -> List[str]:
        return self.validate_job(project.name, job.id)

    def get_job_resource_summary_obj(self, project: Project, job: Job) -> Dict[str, Any]:
        return self.get_job_resource_summary(project.name, job.id)
