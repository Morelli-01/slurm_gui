from PyQt6.QtWidgets import QWidget, QVBoxLayout
from models.project_model import JobsModel
from views.jobs_panel_view import JobsPanelView
from controllers.job_panel_controller import JobsPanelController

class JobsPanelWidget(QWidget):
    """Facade widget for the Jobs Panel."""
    def __init__(self, parent=None):
        super().__init__(parent)
        # Instantiate MVC components
        self.model = JobsModel()
        self.view = JobsPanelView(self)
        self.controller = JobsPanelController(self.model, self.view)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.view)