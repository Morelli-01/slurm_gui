from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import json


# Forward import for type checking – real instance is passed at runtime
from slurm_connection import SlurmConnection, determine_job_status, parse_duration
from datetime import datetime
from modules.defaults import *
__all__ = [
    "Job",
    "Project",
    "ProjectStore",
]

# ---------------------------------------------------------------------------
# Model layer
# ---------------------------------------------------------------------------


def _clean_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Drop None values so the JSON stays compact."""
    return {k: v for k, v in d.items() if v is not None}


@dataclass
class Job:
    id: Union[int, str]  # SLURM job ID
    name: str  # Job name
    # SLURM job status: PENDING, RUNNING, COMPLETED, FAILED, etc.
    status: str = "PENDING"

    # Core job attributes
    command: str = ""  # The job command/script
    partition: str = ""  # SLURM partition
    account: str = ""  # SLURM account
    time_limit: str = ""  # Time limit in HH:MM:SS format
    time_used: Optional[timedelta] = None  # Time used so far

    # Resource requirements
    nodes: int = 1  # Number of nodes
    cpus: int = 1  # Number of CPUs
    gpus: int = 0  # Number of GPUs
    memory: str = ""  # Memory requirement (e.g., "8G")

    # Additional configuration
    constraints: Optional[str] = None  # Node constraints
    qos: Optional[str] = None  # Quality of Service
    # Generic Resources string (e.g., "gpu:rtx5000:1")
    gres: Optional[str] = None

    # Output paths
    output_file: str = ""  # Path for job output
    error_file: str = ""  # Path for job errors
    working_dir: str = ""  # Working directory

    # Job array settings
    # Job array specification (e.g., "1-10:2")
    array_spec: Optional[str] = None
    array_max_jobs: Optional[int] = None  # Maximum concurrent array jobs

    # Job dependencies
    dependency: Optional[str] = None  # Job dependency specification

    # Additional information
    submission_time: Optional[datetime] = None  # When the job was submitted
    start_time: Optional[datetime] = None  # When the job started running
    end_time: Optional[datetime] = None  # When the job completed/failed
    priority: int = 0  # Job priority
    nodelist: str = ""  # List of nodes job is running on
    reason: str = ""  # Status reason (useful for pending jobs)

    # Extensible information dictionary for anything else
    info: Dict[str, Any] = field(default_factory=dict)

    # .................................................................

    def to_json(self) -> Dict[str, Any]:
        """Convert Job to JSON-serializable dictionary with proper datetime/timedelta handling"""
        d = {}

        # Handle each field explicitly to ensure JSON compatibility
        for field_name, field_value in asdict(self).items():
            if field_value is None:
                continue  # Skip None values to keep JSON compact

            # Handle datetime objects
            if isinstance(field_value, datetime):
                d[field_name] = field_value.isoformat()
            # Handle timedelta objects
            elif isinstance(field_value, timedelta):
                # Convert to string format like "1:23:45"
                d[field_name] = str(field_value)
            # Handle dictionary (info field)
            elif isinstance(field_value, dict):
                # Recursively clean the dictionary
                cleaned_dict = self._clean_dict_for_json(field_value)
                if cleaned_dict:  # Only add if not empty
                    d[field_name] = cleaned_dict
            # Handle all other types
            else:
                try:
                    # Test if the value is JSON serializable
                    json.dumps(field_value)
                    d[field_name] = field_value
                except (TypeError, ValueError):
                    # If not serializable, convert to string
                    d[field_name] = str(field_value)

        return d

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Job":
        # Make a copy to avoid modifying the input
        data_copy = data.copy()

        # Handle special types
        if "time_used" in data_copy and data_copy["time_used"]:
            try:
                parts = data_copy["time_used"].split(":")
                if len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                    data_copy["time_used"] = timedelta(
                        hours=hours, minutes=minutes, seconds=seconds)
                else:
                    data_copy["time_used"] = None
            except (ValueError, TypeError):
                data_copy["time_used"] = None

        # Handle date fields
        for date_field in ["submission_time", "start_time", "end_time"]:
            if date_field in data_copy and data_copy[date_field]:
                try:
                    data_copy[date_field] = datetime.fromisoformat(
                        data_copy[date_field])
                except (ValueError, TypeError):
                    data_copy[date_field] = None

        # Handle info dictionary
        info = data_copy.pop("info", {}) or {}

        # Create job with known fields
        known_fields = {k: v for k, v in data_copy.items()
                        if k in cls.__annotations__}
        job = cls(**known_fields)

        # Set info separately
        job.info = info

        return job

    @classmethod
    def from_slurm_dict(cls, slurm_dict: Dict[str, Any]) -> "Job":
        """Create a Job instance from a dictionary returned by SlurmConnection with proper status handling"""

        # Get the raw status and any exit code information
        raw_status = slurm_dict.get("Status", "PENDING")
        exit_code = slurm_dict.get("ExitCode")
        raw_state = slurm_dict.get("RawState", raw_status)

        # Determine refined status if we have exit code information
        if exit_code and raw_status == "COMPLETED":
            refined_status = determine_job_status(raw_state, exit_code)
        else:
            refined_status = raw_status

        job = cls(
            id=slurm_dict.get("Job ID", ""),
            name=slurm_dict.get("Job Name", ""),
            status=refined_status,  # Use refined status
            partition=slurm_dict.get("Partition", ""),
            account=slurm_dict.get("Account", ""),
            priority=slurm_dict.get("Priority", 0),
            nodelist=slurm_dict.get("Nodelist", ""),
            reason=slurm_dict.get("Reason", ""),
        )

        # Handle time fields
        if "Time Limit" in slurm_dict:
            job.time_limit = slurm_dict["Time Limit"]

        if "Time Used" in slurm_dict and isinstance(slurm_dict["Time Used"], list) and len(slurm_dict["Time Used"]) > 1:
            # Use the timedelta value
            job.time_used = slurm_dict["Time Used"][1]

        # Handle resource fields
        if "CPUs" in slurm_dict:
            job.cpus = slurm_dict["CPUs"]

        if "GPUs" in slurm_dict:
            job.gpus = slurm_dict["GPUs"]

        if "RAM" in slurm_dict:
            job.memory = slurm_dict["RAM"]

        # Store exit code and raw state for debugging
        job.info["exit_code"] = exit_code
        job.info["raw_state"] = raw_state
        job.info["raw_status"] = raw_status

        # Store the rest in info dictionary
        for k, v in slurm_dict.items():
            if k not in asdict(job):
                job.info[k] = v

        return job

    def get_runtime_str(self) -> str:
        """Return a formatted string of the job's runtime"""
        if not self.time_used:
            return "—"

        total_seconds = int(self.time_used.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def to_table_row(self) -> List[Any]:
        """
        Return a list of values for display in a table row.
        Format: [id, name, status, runtime, cpus, gpus, memory]
        """
        # Format runtime string (or use placeholder for NOT_SUBMITTED jobs)
        runtime_str = "—" if self.status == "NOT_SUBMITTED" else self.get_runtime_str()

        # Return formatted row data
        return [
            self.id,
            self.name,
            self.status,
            runtime_str,
            self.cpus,
            self.gpus,
            self.memory,
        ]

    def _clean_dict_for_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively clean a dictionary to make it JSON serializable"""
        cleaned = {}

        for key, value in data.items():
            if value is None:
                continue

            if isinstance(value, datetime):
                cleaned[key] = value.isoformat()
            elif isinstance(value, timedelta):
                cleaned[key] = str(value)
            elif isinstance(value, dict):
                nested_clean = self._clean_dict_for_json(value)
                if nested_clean:
                    cleaned[key] = nested_clean
            elif isinstance(value, (list, tuple)):
                # Handle lists/tuples that might contain non-serializable objects
                cleaned_list = []
                for item in value:
                    if isinstance(item, datetime):
                        cleaned_list.append(item.isoformat())
                    elif isinstance(item, timedelta):
                        cleaned_list.append(str(item))
                    else:
                        try:
                            json.dumps(item)
                            cleaned_list.append(item)
                        except (TypeError, ValueError):
                            cleaned_list.append(str(item))
                if cleaned_list:
                    cleaned[key] = cleaned_list
            else:
                try:
                    # Test if the value is JSON serializable
                    json.dumps(value)
                    cleaned[key] = value
                except (TypeError, ValueError):
                    # If not serializable, convert to string
                    cleaned[key] = str(value)

        return cleaned


@dataclass
class Project:
    name: str
    jobs: List[Job] = field(default_factory=list)

    # .................................................................
    def add_job(self, job: Job) -> None:
        """Add a job to the project"""
        # Check if job already exists (by ID)
        for i, existing_job in enumerate(self.jobs):
            if existing_job.id == job.id:
                # Update existing job
                self.jobs[i] = job
                return

        # Add new job
        self.jobs.append(job)

    def get_job(self, job_id: Union[int, str]) -> Optional[Job]:
        """Get a job by ID"""
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def remove_job(self, job_id: Union[int, str]) -> None:
        """Remove a job by ID"""
        self.jobs = [j for j in self.jobs if j.id != job_id]

    def get_job_stats(self) -> Dict[str, int]:
        """Get counts of jobs by status with proper failed job detection"""
        stats = {
            "RUNNING": 0,
            "PENDING": 0,
            "COMPLETED": 0,
            "FAILED": 0,
            "CANCELLED": 0,
            "SUSPENDED": 0,
            "NOT_SUBMITTED": 0,
            "TOTAL": len(self.jobs)
        }

        for job in self.jobs:
            status = job.status.upper()
            if status in stats:
                stats[status] += 1
            else:
                # Handle other statuses by categorizing them
                if status in ["COMPLETING"]:
                    stats["RUNNING"] += 1
                elif status in ["PREEMPTED", "STOPPED"]:
                    stats["SUSPENDED"] += 1
                elif status in ["TIMEOUT", "NODE_FAIL", "OUT_OF_MEMORY", "BOOT_FAIL"]:
                    stats["FAILED"] += 1
                elif status in ["REVOKED", "DEADLINE"]:
                    stats["CANCELLED"] += 1
                else:
                    # Unknown status, log it for debugging
                    print(f"Unknown job status encountered: {status}")

        return stats
    # .................................................................

    def to_json(self) -> Dict[str, Any]:
        """Serialize project to JSON-compatible dictionary"""
        return {
            "name": self.name,
            "jobs": [j.to_json() for j in self.jobs],
        }

    @classmethod
    def from_json(cls, name: str, data: Dict[str, Any]) -> "Project":
        """Create Project from JSON data"""
        jobs = [Job.from_json(j) for j in data.get("jobs", [])]
        return cls(name=name, jobs=jobs)


class ProjectStoreSignals(QObject):
    """Separate QObject to handle signals for ProjectStore"""
    job_status_changed = pyqtSignal(
        str, str, str, str)  # project, job_id, old_status, new_status
    job_updated = pyqtSignal(str, str)  # project, job_id
    project_stats_changed = pyqtSignal(str, dict)  # project, stats_dict

# ---------------------------------------------------------------------------
# Persistence facade (singleton)
# ---------------------------------------------------------------------------


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
    def _init(self, slurm: SlurmConnection, remote_path: Optional[str]):
        # if not slurm.check_connection():
        #     raise RuntimeError("SlurmConnection must be *connected* before using ProjectStore")
        self.signals = ProjectStoreSignals()
        self.slurm = slurm
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

    def remove_job(self, project: str, job_id: Union[int, str]) -> None:
        """Remove a job from a project"""
        pj = self._projects.get(project)
        if not pj:
            return
        pj.remove_job(job_id)
        self._write_to_settings()

    def add_new_job(self, project: str, job_details: Dict[str, Any]) -> Optional[str]:
        """Create a new job and add it to the project (without submitting to SLURM)"""
        if not self.slurm or not self.slurm.check_connection():
            raise ConnectionError("Not connected to SLURM")

        try:
            # Extract required fields
            job_name = job_details.get("job_name", "")
            partition = job_details.get("partition", "")
            time_limit = job_details.get("time_limit", "01:00:00")
            command = job_details.get("command", "")
            account = job_details.get("account", "")

            # Optional fields
            constraint = job_details.get("constraint")
            qos = job_details.get("qos")
            gres = job_details.get("gres")
            nodes = job_details.get("nodes", 1)
            cpus_per_task = job_details.get("cpus_per_task", 1)
            output_file = job_details.get("output_file", ".logs/out_%A.log")
            error_file = job_details.get("error_file", ".logs/err_%A.log")
            working_dir = job_details.get("working_dir", "")

            # Job array parameters
            array_spec = job_details.get("array")
            array_max_jobs = job_details.get("array_max_jobs")

            # Dependency parameters
            dependency = job_details.get("dependency")

            # Memory calculation - convert to proper format if needed
            memory = None
            if "memory" in job_details:
                memory = job_details["memory"]
            elif "memory_spin" in job_details and "memory_unit" in job_details:
                memory_value = job_details.get("memory_spin", 1)
                memory_unit = job_details.get("memory_unit", "GB")
                memory = f"{memory_value}{memory_unit.lower()}"

            # Generate a temporary ID (negative number to indicate not submitted yet)
            import random
            temp_id = f"NEW-{random.randint(1000, 9999)}"

            # Create job object without submitting to SLURM
            job = Job(
                id=temp_id,
                name=job_name,
                status="NOT_SUBMITTED",  # Special status to indicate job is not submitted yet
                command=command,
                partition=partition,
                account=account,
                time_limit=time_limit,
                nodes=nodes,
                cpus=cpus_per_task,
                constraints=constraint,
                qos=qos,
                gres=gres,
                output_file=output_file,
                error_file=error_file,
                working_dir=working_dir,
                submission_time=None,  # No submission time yet
                memory=memory or "",
            )
            if "discord_notifications" in job_details:
                job.info["discord_notifications"] = job_details["discord_notifications"]
            # Parse GPU count from gres if available
            if gres and "gpu:" in gres:
                try:
                    gpu_parts = gres.split(":")
                    if len(gpu_parts) == 2:  # Format: gpu:N
                        job.gpus = int(gpu_parts[1])
                    elif len(gpu_parts) == 3:  # Format: gpu:type:N
                        job.gpus = int(gpu_parts[2])
                except (ValueError, IndexError):
                    pass  # Keep default value if parsing fails

            # Add array information if present
            if array_spec:
                job.array_spec = array_spec
                if array_max_jobs:
                    job.array_max_jobs = array_max_jobs

            # Add dependency information if present
            if dependency:
                job.dependency = dependency

            # Store job details in info for later submission
            job.info["submission_details"] = job_details

            # Add the job to the project in the store
            self.add_job(project, job)
            return temp_id

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Job creation failed: {e}")

    def submit_job(self, project: str, job_id: str) -> Optional[str]:
        """Submit an existing job to SLURM with Discord notifications in script"""
        if not self.slurm or not self.slurm.check_connection():
            raise ConnectionError("Not connected to SLURM")

        # Get the job from the project
        project_obj = self.get(project)
        if not project_obj:
            raise ValueError(f"Project {project} not found")

        job = project_obj.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found in project {project}")

        # Skip if job is already submitted
        if not job.status == "NOT_SUBMITTED":
            return job.id

        try:
            # Get submission details from job info
            submission_details = job.info.get("submission_details", {})
            if not submission_details:
                raise ValueError(f"Job {job_id} has no submission details")

            # Extract Discord settings from job info
            discord_settings = job.info.get("discord_notifications", {})

            # Get job parameters
            job_name = job.name
            partition = job.partition
            time_limit = job.time_limit
            command = job.command
            account = job.account
            constraint = job.constraints
            qos = job.qos
            gres = job.gres
            nodes = job.nodes
            cpus_per_task = job.cpus
            output_file = job.output_file
            error_file = job.error_file
            memory = job.memory
            cpus = job.cpus

            # Submit job using SlurmConnection with Discord settings
            new_job_id = self.slurm.submit_job(
                job_name=job_name,
                partition=partition,
                time_limit=time_limit,
                command=command,
                account=account,
                constraint=constraint,
                qos=qos,
                gres=gres,
                nodes=nodes,
                output_file=output_file,
                error_file=error_file,
                memory=memory,
                cpus=cpus,
                discord_settings=discord_settings  # Pass Discord settings
            )

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

    # ------------------------------------------------------------------
    # Convenience / debugging helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover – convenience only
        return f"<ProjectStore {self._projects}>"
    # ------------------------------------------------------------------
    # Job Monitoring
    # ------------------------------------------------------------------

    def _start_job_monitoring(self):
        """Start the background job status monitoring"""
        from slurm_connection import JobStatusMonitor

        # Stop existing monitor if any
        if self.job_monitor is not None:
            self.job_monitor.stop()
            self.job_monitor.wait()

        # Only start monitoring if we have a valid connection
        if not self.slurm or not self.slurm.check_connection():
            print("Cannot start job monitoring - no SLURM connection")
            return

        self.job_monitor = JobStatusMonitor(
            self.slurm, self, update_interval=5)

        # Connect signals
        self.job_monitor.job_status_updated.connect(
            self._on_job_status_updated)
        self.job_monitor.job_details_updated.connect(
            self._on_job_details_updated)
        self.job_monitor.jobs_batch_updated.connect(
            self._on_jobs_batch_updated)

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
            project_name, job_id, old_status, new_status)
        self.signals.job_updated.emit(project_name, job_id)

        # Update project statistics
        stats = project.get_job_stats()
        self.signals.project_stats_changed.emit(project_name, stats)

    def _on_job_details_updated(self, project_name: str, job_id: str, job_details: dict):
        """Handle detailed job updates from monitor"""
        self.signals.job_updated.emit(project_name, job_id)

    def _on_jobs_batch_updated(self, updated_projects: dict):
        """Handle batch job updates from monitor"""
        for project_name, job_updates in updated_projects.items():
            project = self.get(project_name)
            if not project:
                continue

            # Update project statistics after batch changes
            stats = project.get_job_stats()
            self.signals.project_stats_changed.emit(project_name, stats)

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
