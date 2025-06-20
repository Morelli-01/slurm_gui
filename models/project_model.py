from ast import Dict
from dataclasses import dataclass, field
from typing import List, Optional
import uuid
from core.event_bus import get_event_bus, Events
from widgets.toast_widget import show_error_toast

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
    constraint: Optional[str] = None
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

    # --- Custom Fields ---
    venv: Optional[str] = None
    project_name: Optional[str] = None  # To link the job to a project in the GUI
    optional_sbatch: Optional[str] = None
    script_commands: str = "echo 'Hello from SLURM!'"

    # --- Internal State ---
    id: Optional[str] = None
    status: str = "NOT_SUBMITTED"


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
            lines.append(f"#SBATCH --constraint={self.constraint}")
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

        # --- Custom Options ---
        if self.optional_sbatch:
            lines.append(self.optional_sbatch)

        lines.append("") # Blank line before commands
        lines.append("# --- Your commands start here ---")
        
        # Add setup for virtual environment if specified
        if self.venv:
            lines.append(f"source {self.venv}/bin/activate")
            lines.append("")

        lines.append(self.script_commands)
        
        # Join lines with the appropriate separator for the OS
        return os.linesep.join(lines)
    
@dataclass
class Project:
    """Data structure for a project, containing a name and a list of jobs."""
    name: str
    jobs: List[Job] = field(default_factory=list)

    def get_job_stats(self) -> dict:
        """Counts the number of jobs in each status category."""
        stats = {"COMPLETED": 0, "FAILED": 0, "PENDING": 0, "RUNNING": 0, "CANCELLED": 0, "NOT_SUBMITTED": 0}
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
            self.event_bus.emit(Events.PROJECT_LIST_CHANGED, data={'projects': self.projects})
        else:
            show_error_toast(self,"Error" ,"Project already exist")

    def remove_project(self, name: str):
        """Removes a project and emits an event."""
        project_to_remove = next((p for p in self.projects if p.name == name), None)
        if project_to_remove:
            self.projects.remove(project_to_remove)
            self.event_bus.emit(Events.PROJECT_LIST_CHANGED, data={'projects': self.projects})
    
    def set_active_project(self, name: str):
        """Sets the currently active project and emits an event."""
        self.active_project = next((p for p in self.projects if p.name == name), None)

    def add_job_to_active_project(self, event: Dict): # New method to add a job
        """Adds a new job to the active project and emits an event."""
        project_name = event.data["project_name"]
        job_data = event.data["job_data"]

        project = next((p for p in self.projects if p.name == project_name), None)
        if project:
            new_job = Job(
                id=job_data.get("id", str(uuid.uuid4())),
                name=job_data.get("name", "Untitled Job"),
                status=job_data.get("status", "NOT_SUBMITTED"),
                runtime=job_data.get("runtime", "0:00"),
                cpu=job_data.get("cpu", "1"),
                ram=job_data.get("ram", "1M"),
                gpu=job_data.get("gpu", "0"),
                node=job_data.get("node", "N/A"),
            )
            project.jobs.append(new_job)
            self.event_bus.emit(Events.PROJECT_LIST_CHANGED, data={'projects': self.projects})
        else:
            show_error_toast(self, "Error", f"Project '{project_name}' not found.")
