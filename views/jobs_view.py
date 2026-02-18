from typing import List, Optional, Sequence

from core.defaults import *
from core.event_bus import Events, get_event_bus
from core.style import AppStyles
from models.project_model import Job, Project
from widgets.toast_widget import show_warning_toast
# from models.project_model import Project
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
        can_be_deleted = status in [NOT_SUBMITTED, STATUS_COMPLETED, STATUS_FAILED, STATUS_STOPPED, CANCELLED, TIMEOUT]
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
        if self.job.status in [NOT_SUBMITTED, STATUS_COMPLETED, STATUS_FAILED, STATUS_STOPPED, CANCELLED, TIMEOUT]:
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
        self.setObjectName("jobsTableView")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)

        self._project_filter_text = ""
        self._status_filter_value = ""

        toolbar = QWidget()
        toolbar.setObjectName("jobsToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)

        self.panel_title_label = QLabel("Jobs")
        self.panel_title_label.setObjectName("jobsPanelTitle")
        toolbar_layout.addWidget(self.panel_title_label)

        self.jobs_meta_label = QLabel("No project selected")
        self.jobs_meta_label.setObjectName("jobsMetaLabel")
        toolbar_layout.addWidget(self.jobs_meta_label)

        toolbar_layout.addStretch(1)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("jobsFilterInput")
        self.search_input.setPlaceholderText("Search by ID, name, status, runtime...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_filter_inputs_changed)
        toolbar_layout.addWidget(self.search_input)

        self.status_filter = QComboBox()
        self.status_filter.setObjectName("jobsStatusFilter")
        self.status_filter.addItems(
            [
                "All statuses",
                NOT_SUBMITTED,
                STATUS_PENDING,
                STATUS_RUNNING,
                STATUS_COMPLETING,
                STATUS_COMPLETED,
                STATUS_FAILED,
                CANCELLED,
                STATUS_STOPPED,
                TIMEOUT,
            ]
        )
        self.status_filter.currentTextChanged.connect(self._on_filter_inputs_changed)
        toolbar_layout.addWidget(self.status_filter)

        self.clear_filters_button = QPushButton("Clear")
        self.clear_filters_button.setObjectName(BTN_BLUE)
        self.clear_filters_button.clicked.connect(self._clear_filters)
        toolbar_layout.addWidget(self.clear_filters_button)

        self.layout.addWidget(toolbar)

        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget, 1)

        self.tables = {}  # {project_name: QTableWidget}
        self._project_signatures = {}  # {project_name: tuple}
        self._current_project_name = None

        # A placeholder widget for when no project is selected
        self.placeholder_widget = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_widget)
        placeholder_label = QLabel("Select or create a project to view its jobs.")
        placeholder_label.setObjectName("jobsPlaceholderLabel")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(placeholder_label)
        self.stacked_widget.addWidget(self.placeholder_widget)
        self.stacked_widget.setCurrentWidget(self.placeholder_widget)

        # Footer action row keeps the button always accessible and avoids table overlap.
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.addStretch(1)

        self.new_jobs_button = QPushButton("New Job")
        self.new_jobs_button.setObjectName(BTN_GREEN)
        self.new_jobs_button.clicked.connect(self._create_new_job_for_current_project)
        self.new_jobs_button.setFixedSize(120, 40)
        self.new_jobs_button.hide()  # Initially hidden until a project is selected
        footer_layout.addWidget(self.new_jobs_button)
        self.layout.addLayout(footer_layout)

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
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(getattr(self, "_ROW_HEIGHT", 50))
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
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

        return table

    def _apply_stylesheet(self):
        """Apply centralized styles to the jobs group"""
        # Use centralized styling system
        style = AppStyles.get_table_styles()
        style += AppStyles.get_button_styles()
        style += AppStyles.get_scrollbar_styles()
        style += AppStyles.get_job_action_styles()
        style += f"""
        QWidget#jobsToolbar {{
            background-color: transparent;
        }}
        QLabel#jobsPanelTitle {{
            font-size: 18px;
            font-weight: 700;
            color: {COLOR_DARK_FG};
            padding-right: 6px;
        }}
        QLabel#jobsMetaLabel {{
            font-size: 12px;
            color: {COLOR_GRAY};
        }}
        QLineEdit#jobsFilterInput {{
            min-width: 270px;
            max-width: 380px;
        }}
        QComboBox#jobsStatusFilter {{
            min-width: 150px;
        }}
        QLabel#jobsPlaceholderLabel {{
            color: {COLOR_GRAY};
            font-size: 14px;
        }}
        QWidget#jobsTableView QTableWidget::item:selected {{
            background-color: {COLOR_DARK_BG_HOVER};
            color: {COLOR_BLUE};
            border: 1px solid {COLOR_DARK_BORDER};
        }}
        """

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

            project_signature = self._build_project_signature(project.jobs)
            if self._project_signatures.get(project.name) != project_signature:
                self.update_jobs_for_project(project.name, project.jobs)
                self._project_signatures[project.name] = project_signature

        if not projects:
            self._current_project_name = None
            self.stacked_widget.setCurrentWidget(self.placeholder_widget)
            self.new_jobs_button.hide()
            self._update_panel_header(None)
            return

        self._update_panel_header(self._current_project_name)

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
            self._project_signatures.pop(project_name, None)
            self.stacked_widget.removeWidget(table)
            table.deleteLater()

    def switch_to_project(self, project_name: str):
        """Switches the view to the table for the selected project."""
        if project_name in self.tables:
            self._current_project_name = project_name
            self.stacked_widget.setCurrentWidget(self.tables[project_name])
            self.new_jobs_button.show()
            self.new_jobs_button.setToolTip(f"Create a new job in '{project_name}'")
            self._apply_filters_to_table(self.tables[project_name])
            self._update_panel_header(project_name)
        else:
            self._current_project_name = None
            self.stacked_widget.setCurrentWidget(self.placeholder_widget)
            self.new_jobs_button.hide()
            self._update_panel_header(None)


    def update_jobs_for_project(self, project_name: str, jobs: List[Job]):
        """Populates a project's table with its jobs."""
        if project_name not in self.tables:
            return

        table = self.tables[project_name]
        scrollbar = table.verticalScrollBar()
        was_at_bottom = scrollbar.value() == scrollbar.maximum()
        old_scroll_position = scrollbar.value()

        table.setUpdatesEnabled(False)
        try:
            previous_keys = table.property("job_keys") or []
            new_keys = [self._job_key(job_data) for job_data in jobs]

            if previous_keys == new_keys and table.rowCount() == len(jobs):
                self._refresh_existing_rows(table, jobs)
            else:
                self._rebuild_table_rows(table, jobs)
                table.setProperty("job_keys", new_keys)
        finally:
            table.setUpdatesEnabled(True)

        self._apply_filters_to_table(table)

        if was_at_bottom:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(old_scroll_position)

    def _build_project_signature(self, jobs: List[Job]) -> tuple:
        """Build a lightweight signature to skip unchanged table refreshes."""
        signature_rows = []
        for job_data in jobs:
            values = self._get_row_values(job_data)
            signature_rows.append(tuple(str(value) for value in values))
        return tuple(signature_rows)

    def _job_key(self, job_data: Job) -> str:
        """Stable row identity used for in-place table refresh."""
        job_id = getattr(job_data, "id", None)
        if job_id not in (None, ""):
            return str(job_id)
        return f"tmp::{id(job_data)}"

    def _get_row_values(self, job_data: Job) -> Sequence[str]:
        if hasattr(job_data, "to_table_row"):
            raw_values = job_data.to_table_row()
        else:
            raw_values = [
                getattr(job_data, "id", ""),
                getattr(job_data, "name", ""),
                getattr(job_data, "status", ""),
                getattr(job_data, "elapsed", ""),
                getattr(job_data, "cpus_per_task", ""),
                getattr(job_data, "mem", ""),
                getattr(job_data, "gpus", "0"),
            ]

        values = [str(value) for value in raw_values[:7]]
        while len(values) < 7:
            values.append("")
        return values

    def _refresh_existing_rows(self, table: QTableWidget, jobs: List[Job]):
        actions_col = table.columnCount() - 1
        for row_index, job_data in enumerate(jobs):
            row_values = self._get_row_values(job_data)
            for col in range(actions_col):
                self._set_table_item(table, row_index, col, row_values[col])

            action_widget = table.cellWidget(row_index, actions_col)
            if isinstance(action_widget, ActionButtonsWidget):
                action_widget.job = job_data
                action_widget.update_status(getattr(job_data, "status", ""))
            else:
                table.setCellWidget(row_index, actions_col, ActionButtonsWidget(job=job_data))

    def _rebuild_table_rows(self, table: QTableWidget, jobs: List[Job]):
        table.clearContents()
        table.setRowCount(len(jobs))
        for row_index, job_data in enumerate(jobs):
            self._populate_job_row(table, row_index, job_data)

    def _set_table_item(self, table: QTableWidget, row: int, col: int, value: str):
        item = table.item(row, col)
        if item is None:
            item = QTableWidgetItem(value)
            table.setItem(row, col, item)
        elif item.text() != value:
            item.setText(value)

        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if col == 2:  # Status column
            self._apply_state_color(item)


    def _apply_state_color(self, item: QTableWidgetItem):
        """Apply color based on job status"""
        txt = item.text().lower()
        if txt in STATE_COLORS:
            color = QColor(STATE_COLORS[txt])
            item.setData(Qt.ItemDataRole.ForegroundRole, QBrush(color))
        else:
            item.setData(Qt.ItemDataRole.ForegroundRole, QBrush(QColor(COLOR_DARK_FG)))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _populate_job_row(self, table: QTableWidget, row_position: int, job_data: Job):
        """Populates a single job row in the provided table."""
        actions_col = table.columnCount() - 1
        row_values = self._get_row_values(job_data)

        for col in range(actions_col):
            self._set_table_item(table, row_position, col, row_values[col])

        # Add action buttons
        action_widget = ActionButtonsWidget(job=job_data)
        action_widget._job_status = getattr(job_data, "status", None)
        table.setCellWidget(row_position, actions_col, action_widget)

    def _create_new_job_for_current_project(self):
        """Creates a new job for the currently selected project."""
        if self._current_project_name and self._current_project_name in self.tables:
            self._create_new_job(self._current_project_name)
            return

        show_warning_toast(
            self,
            "No Project Selected",
            "Please select or create a project first.",
        )

    def _create_new_job(self, project_name):
        get_event_bus().emit(
            Events.CREATE_JOB_DIALOG_REQUESTED,
            data={"project_name": project_name},
            source="JobsTableView",
        )

    def _clear_filters(self):
        self.search_input.clear()
        self.status_filter.setCurrentIndex(0)

    def _on_filter_inputs_changed(self):
        self._project_filter_text = self.search_input.text().strip().lower()
        selected_status = self.status_filter.currentText().strip()
        self._status_filter_value = "" if selected_status == "All statuses" else selected_status.upper()
        self._apply_filters_to_current_table()

    def _apply_filters_to_current_table(self):
        if self._current_project_name and self._current_project_name in self.tables:
            self._apply_filters_to_table(self.tables[self._current_project_name])
        else:
            self._update_panel_header(None)

    def _apply_filters_to_table(self, table: QTableWidget):
        table.setUpdatesEnabled(False)
        try:
            for row in range(table.rowCount()):
                row_texts = []
                for col in range(4):  # ID, name, status, runtime
                    item = table.item(row, col)
                    row_texts.append(item.text().lower() if item else "")

                status_item = table.item(row, 2)
                row_status = status_item.text().upper() if status_item else ""

                matches_query = (
                    not self._project_filter_text
                    or any(self._project_filter_text in text for text in row_texts)
                )
                matches_status = (
                    not self._status_filter_value
                    or row_status == self._status_filter_value
                )
                table.setRowHidden(row, not (matches_query and matches_status))
        finally:
            table.setUpdatesEnabled(True)

        self._update_panel_header(self._current_project_name)

    def _update_panel_header(self, project_name: Optional[str]):
        if not project_name or project_name not in self.tables:
            self.panel_title_label.setText("Jobs")
            self.jobs_meta_label.setText("No project selected")
            return

        table = self.tables[project_name]
        total_rows = table.rowCount()
        visible_rows = sum(1 for row in range(total_rows) if not table.isRowHidden(row))

        self.panel_title_label.setText(f"Jobs · {project_name}")
        if total_rows == 0:
            self.jobs_meta_label.setText("No jobs yet")
        elif visible_rows != total_rows:
            self.jobs_meta_label.setText(f"Showing {visible_rows} of {total_rows} jobs")
        else:
            label = "job" if total_rows == 1 else "jobs"
            self.jobs_meta_label.setText(f"{total_rows} {label}")
