import uuid
from functools import partial
from typing import List

from core.defaults import *
from core.event_bus import Events, get_event_bus
from core.style import AppStyles
from models.project_model import Job, Project
from widgets.toast_widget import show_warning_toast
# from models.project_model import Project
from utils import script_dir
from widgets.new_job_widget import JobCreationDialog



class ActionButtonsWidget(QWidget):
    """Widget containing the seven action buttons for a job."""

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self.setObjectName("actionContainer")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.startButton = QPushButton()
        self.startButton.setObjectName("actionSubmitBtn")
        self.startButton.setToolTip("Start Job")
        layout.addWidget(self.startButton)

        self.stopButton = QPushButton()
        self.stopButton.setObjectName("actionStopBtn")
        self.stopButton.setToolTip("Stop Job")
        layout.addWidget(self.stopButton)

        self.cancelButton = QPushButton()
        self.cancelButton.setObjectName("actionCancelBtn")
        self.cancelButton.setToolTip("Cancel/Delete Job")
        layout.addWidget(self.cancelButton)

        self.logsButton = QPushButton()
        self.logsButton.setObjectName("actionLogsBtn")
        self.logsButton.setToolTip("View Logs")
        layout.addWidget(self.logsButton)

        self.duplicateButton = QPushButton()
        self.duplicateButton.setObjectName("actionDuplicateBtn")
        self.duplicateButton.setToolTip("Duplicate Job")
        layout.addWidget(self.duplicateButton)

        self.modifyButton = QPushButton()
        self.modifyButton.setObjectName("actionModifyBtn")
        self.modifyButton.setToolTip("Modify Job")
        layout.addWidget(self.modifyButton)

        self.terminalButton = QPushButton()
        self.terminalButton.setObjectName("actionTerminalBtn")
        self.terminalButton.setToolTip("Open Terminal on Node")
        layout.addWidget(self.terminalButton)
        
        self.startButton.clicked.connect(self._on_submit_clicked)
        self.stopButton.clicked.connect(self._on_stop_clicked)
        self.duplicateButton.clicked.connect(self._on_duplicate_clicked)
        self.modifyButton.clicked.connect(self._on_modify_clicked)
        self.cancelButton.clicked.connect(self._on_cancel_clicked)
        self.terminalButton.clicked.connect(self._on_terminal_clicked)
        self.logsButton.clicked.connect(self._on_logs_clicked)

        self._update_button_states()

    def update_status(self, new_status: str):
        """Public method to update the job status and refresh button states."""
        self.job.status = new_status
        self._update_button_states()

    def _update_button_states(self):
        """Enable or disable buttons based on job status."""
        status = self.job.status

        is_not_submitted = (status == NOT_SUBMITTED)
        is_active = status in [STATUS_RUNNING, STATUS_PENDING, STATUS_SUSPENDED, STATUS_COMPLETING, STATUS_PREEMPTED]
        is_running = (status == STATUS_RUNNING)
        can_be_deleted = status in [NOT_SUBMITTED, STATUS_COMPLETED, STATUS_FAILED, STATUS_STOPPED, CANCELLED]
        has_logs = not is_not_submitted

        self.startButton.setEnabled(is_not_submitted)
        self.stopButton.setEnabled(is_active)
        self.cancelButton.setEnabled(can_be_deleted)
        self.logsButton.setEnabled(True)
        self.duplicateButton.setEnabled(True)  # Always enabled
        self.modifyButton.setEnabled(is_not_submitted)
        self.terminalButton.setEnabled(is_running)
    
    def _on_stop_clicked(self):
        """Emit an event to stop (scancel) the job."""
        is_active = self.job.status in [STATUS_RUNNING, STATUS_PENDING, STATUS_SUSPENDED, STATUS_COMPLETING, STATUS_PREEMPTED]
        if is_active:
            get_event_bus().emit(
                Events.STOP_JOB,
                data={"project_name": self.job.project_name, "job_id": self.job.id},
                source="ActionButtonsWidget",
            )
        else:
            show_warning_toast(self, "Warning", f"Cannot stop a job in '{self.job.status}' state.")

    def _on_modify_clicked(self):
        """Emit an event to modify the job."""
        if self.job.status == NOT_SUBMITTED:
            get_event_bus().emit(
                Events.MODIFY_JOB,
                data={"project_name": self.job.project_name, "job_id": self.job.id},
                source="ActionButtonsWidget",
            )
        else:
            show_warning_toast(self, "Warning", "Only unsubmitted jobs can be edited!")

    def _on_cancel_clicked(self):
        """Emit an event to delete the job."""
        if self.job.status in [NOT_SUBMITTED, STATUS_COMPLETED, STATUS_FAILED, STATUS_STOPPED, "CANCELLED"]:
            get_event_bus().emit(
                Events.DEL_JOB,
                data={"project_name": self.job.project_name, "job_id": self.job.id},
                source="ActionButtonsWidget",
            )
        else:
            show_warning_toast(self, "Warning", f"Cannot delete a job in '{self.job.status}' state. Please stop or cancel it first.")
    
    def _on_duplicate_clicked(self):
        """Emit an event to duplicate the job."""
        get_event_bus().emit(
            Events.DUPLICATE_JOB,
            data={"project_name": self.job.project_name, "job_id": self.job.id},
            source="ActionButtonsWidget",
        )
   
    def _on_submit_clicked(self):
        """Emit an event to submit the job."""
        if self.job.status == NOT_SUBMITTED:
            get_event_bus().emit(
                Events.JOB_SUBMITTED,
                data={"project_name": self.job.project_name, "job_id": self.job.id},
                source="ActionButtonsWidget",
            )
        else:
            show_warning_toast(self, "Warning", "Job has already been submitted.")
   
    def _on_terminal_clicked(self):
        """Emit an event to open a terminal for the job."""
        if self.job.status == STATUS_RUNNING:
            get_event_bus().emit(
                Events.OPEN_JOB_TERMINAL,
                data={"project_name": self.job.project_name, "job_id": self.job.id},
                source="ActionButtonsWidget",
            )
        else:
            show_warning_toast(self, "Warning", "Terminal can only be opened for running jobs.")
    
    def _on_logs_clicked(self):
        """Emit an event to view the job's logs."""
        get_event_bus().emit(
                Events.VIEW_LOGS,
                data={"project_name": self.job.project_name, "job_id": self.job.id},
                source="ActionButtonsWidget",
            )

class JobsTableView(QWidget):
    """
    View to display jobs for projects. It manages a dictionary of QTableWidgets,
    one for each project, and displays them in a QStackedWidget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)

        self.tables = {}  # {project_name: QTableWidget}

        # A placeholder widget for when no project is selected
        self.placeholder_widget = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_widget)
        placeholder_label = QLabel("Select or create a project to view its jobs.")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(placeholder_label)
        self.stacked_widget.addWidget(self.placeholder_widget)
        self.stacked_widget.setCurrentWidget(self.placeholder_widget)
        self._apply_stylesheet()

    def _create_new_table(self, table_name=""):
        """Creates and configures a new QTableWidget."""
        headers = [
            "Job ID",
            "Job Name",
            "Status",
            "Runtime",
            "CPU",
            "RAM",
            "GPU",
            "Actions",
        ]
        table = QTableWidget()
        table.setObjectName(table_name)
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        h = table.horizontalHeader()
        h.setStretchLastSection(False)
        for i, head in enumerate(headers):
            if head == "Actions":
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(i, 240)  # Reduced width for smaller buttons
            elif head in ["CPU", "GPU", "RAM"]:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
                table.setColumnWidth(i, 70)
            elif head == "Job Name":
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        self.new_jobs_button = QPushButton("New Job", table)  # Set self as parent
        self.new_jobs_button.setObjectName(BTN_GREEN)

        self.new_jobs_button.clicked.connect(partial(self._create_new_job, table_name))
        self.new_jobs_button.setFixedSize(120, 40)  # Set a fixed size
        self.new_jobs_button.move(
            self.width() - self.new_jobs_button.width() - 20,
            self.height() - self.new_jobs_button.height() - 20,
        )
        return table

    def _apply_stylesheet(self):
        """Apply centralized styles to the jobs group"""
        # Use centralized styling system
        style = AppStyles.get_table_styles()
        style += AppStyles.get_button_styles()
        style += AppStyles.get_scrollbar_styles()
        style += AppStyles.get_job_action_styles()

        self.setStyleSheet(style)

    def update_projects(self, projects: List[Project]):
        """Synchronizes the tables with the list of projects from the model."""
        current_projects = set(p.name for p in projects)
        existing_tables = set(self.tables.keys())

        for project_name in existing_tables - current_projects:
            self.remove_project_table(project_name)

        for project in projects:
            if project.name not in self.tables:
                self.add_project_table(project.name)
            self.update_jobs_for_project(project.name, project.jobs)

        if len(projects) == 1:
            self.switch_to_project(projects[0].name)

    def add_project_table(self, project_name: str):
        """Adds a new table for a project."""
        if project_name not in self.tables:
            table = self._create_new_table(project_name)
            self.tables[project_name] = table
            self.stacked_widget.addWidget(table)

    def remove_project_table(self, project_name: str):
        """Removes the table for a project."""
        if project_name in self.tables:
            table = self.tables.pop(project_name)
            self.stacked_widget.removeWidget(table)
            table.deleteLater()

    def switch_to_project(self, project_name: str):
        """Switches the view to the table for the selected project."""
        if project_name in self.tables:
            self.stacked_widget.setCurrentWidget(self.tables[project_name])
        else:
            self.stacked_widget.setCurrentWidget(self.placeholder_widget)

    def update_jobs_for_project(self, project_name: str, jobs: List[Job]):
        """Populates a project's table with its jobs."""
        if project_name in self.tables:
            table = self.tables[project_name]
            table.setRowCount(0)
            for job_data in jobs:
                self._add_job_to_table(table, job_data)

    def _apply_state_color(self, item: QTableWidgetItem):
        """Apply color based on job status"""
        txt = item.text().lower()
        if txt in STATE_COLORS:
            color = QColor(STATE_COLORS[txt])
            item.setData(Qt.ItemDataRole.ForegroundRole, QBrush(color))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _add_job_to_table(self, table: QTableWidget, job_data: Job):
        """Adds a single job row to the given table, matching style and logic of _add_job_row."""
        actions_col = table.columnCount() - 1
        row_position = table.rowCount()
        table.insertRow(row_position)
        table.verticalHeader().setDefaultSectionSize(getattr(self, "_ROW_HEIGHT", 50))

        # Use to_table_row if available, else fallback to attributes
        if hasattr(job_data, "to_table_row"):
            row_values = job_data.to_table_row()

        for col in range(actions_col):
            val = row_values[col] if col < len(row_values) else ""
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if col == 2:  # Status column
                if hasattr(self, "_apply_state_color"):
                    self._apply_state_color(item)
            table.setItem(row_position, col, item)

        # Add action buttons
        action_widget = ActionButtonsWidget(job=job_data)
        action_widget._job_status = getattr(job_data, "status", None)
        table.setCellWidget(row_position, actions_col, action_widget)
    
    def resizeEvent(self, event):
        """Override resize event to reposition the button."""
        super().resizeEvent(event)
        # Position the button in the bottom-right corner of the visible area (viewport)
        if hasattr(self, "new_jobs_button"):
            self.new_jobs_button.move(
                self.width() - self.new_jobs_button.width() - 20,
                self.height() - self.new_jobs_button.height() - 20
            )

    def _create_new_job(self, project_name):
        get_event_bus().emit(
            Events.CREATE_JOB_DIALOG_REQUESTED,
            data={"project_name": project_name},
            source="JobsTableView",
        )

