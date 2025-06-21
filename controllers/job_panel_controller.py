from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox
from models.project_model import JobsModel
from views.jobs_panel_view import JobsPanelView
from core.event_bus import get_event_bus, Events, Event
from core.slurm_api import *


class JobsPanelController:
    def __init__(self, model: JobsModel, view: JobsPanelView):
        self.model = model
        self.view = view
        self.event_bus = get_event_bus()
        self._event_bus_subscription()

    def _event_bus_subscription(self):
        """Subscribe to model changes from the event bus."""
        self.event_bus.subscribe(
            Events.PROJECT_LIST_CHANGED, self._on_project_list_changed
        )
        self.event_bus.subscribe(Events.CONNECTION_STATE_CHANGED, self._shutdown)
        self.event_bus.subscribe(Events.ADD_PROJECT, self.model.add_project)
        self.event_bus.subscribe(Events.DEL_PROJECT, self._handle_delete_project)
        self.event_bus.subscribe(Events.PROJECT_SELECTED, self._handle_project_selection)
        self.event_bus.subscribe(Events.MODIFY_JOB, self._handle_modify_job)

    def _on_project_list_changed(self, event: Event):
        """Update the view when the project list in the model changes."""
        projects = event.data.get("projects", [])
        # Update the list of projects in the left-hand panel
        self.view.project_group.update_view(projects)
        # Update the job tables in the right-hand panel
        self.view.jobs_table_view.update_projects(projects)

    def _handle_delete_project(self, event):
        """Confirm and delete a project."""
        name = event.data["project_name"]
        reply = QMessageBox.question(
            self.view,
            "Delete Project",
            f"Are you sure you want to delete the project '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.model.remove_project(name)
    
    def _handle_modify_job(self, event: Event):
        """Brings up the job modification dialog."""
        project_name = event.data["project_name"]
        job_id = event.data["job_id"]
        
        job_to_modify = self.model.get_job_by_id(project_name, job_id)
        
        if job_to_modify and job_to_modify.status == "NOT_SUBMITTED":
            from widgets.new_job_widget import JobCreationDialog
            dialog = JobCreationDialog(parent=self.view, project_name=project_name, job_to_modify=job_to_modify)
            if dialog.exec():
                modified_job = dialog.get_job()
                if modified_job:
                    self.model.update_job_in_project(project_name, job_id, modified_job)

    def _handle_project_selection(self, event):
        """Update the active project in the model."""
        name = event.data["project"]
        self.model.set_active_project(name)

    def _shutdown(self, event):
        """Handle connection status changes."""
        new_state = event.data["new_state"]
        if new_state == ConnectionState.DISCONNECTED:
            self.view.shutdown_ui(is_connected=False)
        elif new_state == ConnectionState.CONNECTED:
            self.view.shutdown_ui(is_connected=True)