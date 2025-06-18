from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox
from models.project_model import JobsModel
from views.jobs_panel_view import JobsPanelView
from core.event_bus import get_event_bus, Events, Event

class JobsPanelController:
    def __init__(self, model: JobsModel, view: JobsPanelView):
        self.model = model
        self.view = view
        self.event_bus = get_event_bus()
        self._connect_ui_signals()
        self._subscribe_to_events()

    def _connect_ui_signals(self):
        """Connect signals from the view to controller methods."""
        self.view.project_group.add_project_requested.connect(self._handle_add_project)
        self.view.project_group.delete_project_requested.connect(self._handle_delete_project)
        self.view.project_group.project_selected.connect(self._handle_project_selection)

    def _subscribe_to_events(self):
        """Subscribe to model changes from the event bus."""
        self.event_bus.subscribe(Events.PROJECT_LIST_CHANGED, self._on_project_list_changed)

    def _on_project_list_changed(self, event: Event):
        """Update the view when the project list in the model changes."""
        projects = event.data.get('projects', [])
        self.view.project_group.update_view(projects)

    def _handle_add_project(self, name: str):
        self.model.add_project(name)

    def _handle_delete_project(self, name: str):
        """Confirm and delete a project."""
        reply = QMessageBox.question(
            self.view,
            'Delete Project',
            f"Are you sure you want to delete the project '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.model.remove_project(name)
            
    def _handle_project_selection(self, name: str):
        """Update the active project in the model."""
        self.model.set_active_project(name)