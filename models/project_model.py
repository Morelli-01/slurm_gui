from ast import Dict
from dataclasses import dataclass, field
from typing import List, Optional
from core.event_bus import get_event_bus, Events
from widgets.toast_widget import show_error_toast

@dataclass
class Job:
    """Data structure for a single job within a project."""
    id: str
    name: str
    status: str
    runtime: str
    cpu: str
    ram: str
    gpu: str
    node: Optional[str] = None

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