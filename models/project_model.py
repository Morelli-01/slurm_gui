import copy
from dataclasses import dataclass, field
import uuid
from core.event_bus import get_event_bus, Events
from widgets.toast_widget import show_error_toast, show_success_toast
from typing import Dict, List, Any, Optional, Set

# In a new file: models/job.py
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    """
    A comprehensive data structure for a single SLURM job, designed to
    closely mirror sbatch command-line options.
    """

    # --- sbatch Options ---
    name: str = "my_slurm_job"
    account: Optional[str] = None
    array: Optional[str] = None
    working_directory: Optional[str] = None
    constraint: Optional[List[str]] = None
    cpus_per_task: Optional[int] = 1
    dependency: Optional[str] = None
    error_file: Optional[str] = None
    gpus: Optional[str] = None
    gpus_per_task: Optional[str] = None
    mem: Optional[str] = "1G"  # Default to 1GB
    nice: Optional[int] = None
    nodes: Optional[str] = 1
    ntasks: Optional[int] = 1
    output_file: Optional[str] = None
    oversubscribe: bool = False
    partition: Optional[str] = None
    qos: Optional[str] = None
    nodelist: Optional[List[str]] = None

    # --- Custom Fields ---
    venv: Optional[str] = None
    project_name: Optional[str] = None  # To link the job to a project in the GUI
    optional_sbatch: Optional[str] = None
    script_commands: str = "echo 'Hello from SLURM!'"

    # --- Internal State ---
    id: Optional[str] = None
    status: str = "NOT_SUBMITTED"
    elapsed: str = "00:00:00"
    
    def __post_init__(self):
        if self.error_file is None or self.output_file is None:
            # Import here to avoid circular import at module level
            from core.slurm_api import SlurmAPI
            remote_home = SlurmAPI().remote_home or "~/"
            if self.error_file is None:
                self.error_file = f"{remote_home}/.slurm_logs/err_%A.log"
            if self.output_file is None:
                self.output_file = f"{remote_home}/.slurm_logs/out_%A.log"
    
    def create_sbatch_script(self) -> str:
        """
        Generates the content for an sbatch submission script based on the
        job's attributes. Uses os.linesep for cross-platform compatibility.
        """
        lines = ["#!/bin/bash"]

        # --- Standard SBATCH Options ---
        if self.name:
            lines.append(f"#SBATCH --job-name={self.name}")
        if self.account:
            lines.append(f"#SBATCH --account={self.account}")
        if self.array:
            lines.append(f"#SBATCH --array={self.array}")
        if self.working_directory:
            lines.append(f"#SBATCH --chdir={self.working_directory}")
        if self.constraint:
            value = self.constraint[0]
            if len(self.constraint) >= 1:
                for c in self.constraint[1:]:
                    value += f"|{c}"
            lines.append(f"#SBATCH --constraint='{value }'")
        if self.cpus_per_task:
            lines.append(f"#SBATCH --cpus-per-task={self.cpus_per_task}")
        if self.dependency:
            lines.append(f"#SBATCH --dependency={self.dependency}")
        if self.error_file:
            lines.append(f"#SBATCH --error={self.error_file}")
        if self.gpus:
            lines.append(f"#SBATCH --gpus={self.gpus}")
        if self.gpus_per_task:
            lines.append(f"#SBATCH --gpus-per-task={self.gpus_per_task}")
        if self.mem:
            lines.append(f"#SBATCH --mem={self.mem}")
        if self.nice is not None:
            lines.append(f"#SBATCH --nice={self.nice}")
        if self.nodes:
            lines.append(f"#SBATCH --nodes={self.nodes}")
        if self.ntasks:
            lines.append(f"#SBATCH --ntasks={self.ntasks}")
        if self.output_file:
            lines.append(f"#SBATCH --output={self.output_file}")
        if self.oversubscribe:
            lines.append("#SBATCH --oversubscribe")
        if self.partition:
            lines.append(f"#SBATCH --partition={self.partition}")
        if self.qos:
            lines.append(f"#SBATCH --qos={self.qos}")
        if self.nodelist:
            lines.append(f"#SBATCH --nodelist={self.nodelist}")
        # --- Custom Options ---
        if self.optional_sbatch:
            lines.append(self.optional_sbatch)

        lines.append("")  # Blank line before commands
        lines.append("# --- Your commands start here ---")

        # Add setup for virtual environment if specified
        if self.venv:
            lines.append(f"source {self.venv}/bin/activate")
            lines.append("")

        lines.append(self.script_commands)

        # Join lines with the appropriate separator for the OS
        return "\n".join(lines)

    def to_table_row(self):
        return [ self.id, self.name, self.status, self.elapsed, self.cpus_per_task,self.mem, self.gpus if self.gpus != None else "0"]
@dataclass
class Project:
    """Data structure for a project, containing a name and a list of jobs."""

    name: str
    jobs: List[Job] = field(default_factory=list)

    def get_job_stats(self) -> dict:
        """Counts the number of jobs in each status category."""
        stats = {
            "COMPLETED": 0,
            "FAILED": 0,
            "PENDING": 0,
            "RUNNING": 0,
            "CANCELLED": 0,
            "NOT_SUBMITTED": 0,
        }
        for job in self.jobs:
            if job.status in stats:
                stats[job.status] += 1
        return stats


class JobsModel:
    """Model to manage projects and jobs."""

    def __init__(self):
        self.projects: List[Project] = []
        self.active_project: Optional[Project] = None
        self.event_bus = get_event_bus()
        self._event_bus_subscription()

    def _event_bus_subscription(self):
        self.event_bus.subscribe(Events.ADD_JOB, self.add_job_to_active_project)

    def add_project(self, event: Dict):
        """Adds a new project and emits an event."""
        name = event.data["project_name"]
        if name and not any(p.name == name for p in self.projects):
            new_project = Project(name=name)
            self.projects.append(new_project)
            self.event_bus.emit(
                Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
            )
        else:
            show_error_toast(self, "Error", "Project already exist")

    def remove_project(self, name: str):
        """Removes a project and emits an event."""
        project_to_remove = next((p for p in self.projects if p.name == name), None)
        if project_to_remove:
            self.projects.remove(project_to_remove)
            self.event_bus.emit(
                Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
            )

    def set_active_project(self, name: str):
        """Sets the currently active project and emits an event."""
        self.active_project = next((p for p in self.projects if p.name == name), None)

    def add_job_to_active_project(self, event: Dict):  # New method to add a job
        """Adds a new job to the active project and emits an event."""
        project_name = event.data["project_name"]
        job_to_add = event.data["job_data"]

        project = next((p for p in self.projects if p.name == project_name), None)
        if project:
            job_to_add.project_name = project.name
            project.jobs.append(job_to_add)
            self.event_bus.emit(
                Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
            )
        else:
            show_error_toast(self, "Error", f"Project '{project_name}' not found.")
    
    def get_job_by_id(self, project_name: str, job_id: str) -> Optional[Job]:
        """Retrieves a job by its ID from a specific project."""
        project = next((p for p in self.projects if p.name == project_name), None)
        if project:
            for job in project.jobs:
                if job.id == job_id:
                    return job
        return None

    def update_job_in_project(self, project_name: str, job_id: str, modified_job_data: Job):
        """Updates a job in the specified project."""
        project = next((p for p in self.projects if p.name == project_name), None)
        if project:
            for i, job in enumerate(project.jobs):
                if job.id == job_id:
                    project.jobs[i] = modified_job_data
                    self.event_bus.emit(
                        Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
                    )
                    break
    
    def duplicate_job(self, project_name: str, job_id: str):
        """Finds a job, creates a duplicate, and adds it to the project."""
        original_job = self.get_job_by_id(project_name, job_id)
        project = next((p for p in self.projects if p.name == project_name), None)

        if original_job and project:
            # Create a deep copy to avoid shared references
            new_job = copy.deepcopy(original_job)

            # Modify the new job
            new_job.id = uuid.uuid4().hex[:8].upper()
            new_job.name = f"{original_job.name}_copy"
            new_job.status = "NOT_SUBMITTED"
            new_job.dependency = None  # Clear dependencies

            # Add the duplicated job to the project
            project.jobs.append(new_job)

            # Emit event to update the UI
            self.event_bus.emit(
                Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
            )
            show_success_toast(None, "Job Duplicated", f"Created a copy of '{original_job.name}'.", duration=1000)
        else:
            show_error_toast(None, "Error", "Could not find the job or project to duplicate.")
    
    def update_job_after_submission(self, project_name: str, temp_job_id: str, new_slurm_id: str):
        """Updates a job's ID and status after successful submission."""
        project = next((p for p in self.projects if p.name == project_name), None)
        if project:
            job_to_update = self.get_job_by_id(project_name, temp_job_id)
            if job_to_update:
                job_to_update.id = new_slurm_id
                job_to_update.status = "PENDING"
                self.event_bus.emit(
                    Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
                )
              
    def remove_job_from_project(self, project_name: str, job_id: str):
        """Removes a job from a specific project."""
        project = next((p for p in self.projects if p.name == project_name), None)
        if project:
            job_to_remove = next((j for j in project.jobs if j.id == job_id), None)
            if job_to_remove:
                project.jobs.remove(job_to_remove)
                self.event_bus.emit(
                    Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
                )

    def get_active_job_ids(self) -> List[str]:
        """Scans all projects and returns a list of job IDs that are in an active state."""
        active_ids = []
        inactive_states = {"NOT_SUBMITTED", "COMPLETED", "FAILED", "CANCELLED", "STOPPED", "TIMEOUT"}
        for project in self.projects:
            for job in project.jobs:
                if job.id and job.id.isdigit() and job.status.upper() not in inactive_states:
                    active_ids.append(job.id)
        return list(set(active_ids))

    def update_jobs_from_sacct(self, job_updates: List[Dict[str, Any]]):
        """Updates job statuses and details from a list of sacct query results."""
        updated = False
        for update in job_updates:
            job_id = update.get("JobID")
            if not job_id:
                continue
            
            found_job = None
            for project in self.projects:
                job = self.get_job_by_id(project.name, job_id)
                if job:
                    found_job = job
                    break
            
            if found_job:
                new_status = update.get("State", found_job.status).upper()
                new_elapsed = update.get("Elapsed", found_job.elapsed)

                if found_job.status != new_status or found_job.elapsed != new_elapsed:
                    found_job.status = new_status
                    found_job.elapsed = new_elapsed
                    updated = True

        if updated:
            self.event_bus.emit(
                Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
            )