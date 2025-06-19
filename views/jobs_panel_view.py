from core.defaults import *
from core.event_bus import Events, get_event_bus
from utils import script_dir
from models.project_model import Project, Job
from typing import List

from views.jobs_view import JobsTableView
from views.project_view import ProjectGroup



class JobsPanelView(QWidget):
    """The main view for the Jobs Panel, combining projects and jobs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QHBoxLayout(self)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter)

        self.project_group = ProjectGroup()
        self.splitter.addWidget(self.project_group)

        self.jobs_table_view = JobsTableView()
        self.splitter.addWidget(self.jobs_table_view)
        self.splitter.setSizes([200, 600])

        get_event_bus().subscribe(
            Events.PROJECT_SELECTED,
            lambda event: self.jobs_table_view.switch_to_project(event.data["project"]),
        )

    def shutdown_ui(self, is_connected=False):
        """Show a 'No connection' panel or restore the normal UI."""
        if not hasattr(self, "_no_connection_panel"):
            # Create the panel once
            self._no_connection_panel = QWidget()
            layout = QVBoxLayout(self._no_connection_panel)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel("No connection")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(f"font-size: 22px; color: {COLOR_RED}; padding: 60px;")
            layout.addWidget(label)

        # Clear the main layout
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        if not is_connected:
            self.main_layout.addWidget(self._no_connection_panel)
        else:
            self.main_layout.addWidget(self.splitter)

