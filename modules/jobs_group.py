import functools
from typing import Iterable, Sequence, Any, List, Dict, Optional
from modules.data_classes import Job, Project
from utils import script_dir
from modules.defaults import *
from core.style import AppStyles


class JobsGroup(QWidget):
    """Container for project-specific job tables with efficient updates."""

    current_projectChanged = pyqtSignal(Project)
    startRequested = pyqtSignal(Project, Job)
    stopRequested = pyqtSignal(Project, Job)
    cancelRequested = pyqtSignal(Project, Job)
    logsRequested = pyqtSignal(Project, Job)
    submitRequested = pyqtSignal(Project, Job)
    duplicateRequested = pyqtSignal(Project, Job)
    modifyRequested = pyqtSignal(Project, Job)
    terminalRequested = pyqtSignal(Project, Job)

    _ROW_HEIGHT = 50

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._stack = QStackedLayout(self)
        self._indices: Dict[str, int] = {}

        # Track job data for each project to enable efficient updates
        # {project: {job_id: job_data}}
        self._project_jobs: Dict[str, Dict[str, List[Any]]] = {}
        self._job_row_indices: Dict[str, Dict[str, int]] = {}  # New: {project_name: {job_id: row_index}}

        self._default_headers = [
            "Job ID",
            "Name",
            "Status",
            "Runtime",
            "CPU",
            "GPU",
            "RAM",
            "Actions",
        ]

        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self._apply_stylesheet()

    def _apply_stylesheet(self):
        """Apply centralized styles to the jobs group"""
        # Use centralized styling system
        style = AppStyles.get_table_styles()
        style += AppStyles.get_button_styles()
        style += AppStyles.get_scrollbar_styles()
        style += AppStyles.get_job_action_styles()  # New method for action button styles

        self.setStyleSheet(style)
    
    def _create_actions_widget(self, project: Project, job: Job) -> QWidget:
        """Creates a widget containing action buttons for a job row using CSS-styled buttons with icons."""
        container = QWidget()
        container.setObjectName("actionContainer")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)  # Consistent spacing between buttons
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create buttons using CSS classes for icons and styling
        submit_btn = QPushButton()
        submit_btn.setObjectName("actionSubmitBtn")
        submit_btn.setToolTip("Submit job")
        submit_btn.clicked.connect(lambda: self.submitRequested.emit(project, job))

        stop_btn = QPushButton()
        stop_btn.setObjectName("actionStopBtn")
        stop_btn.setToolTip("Stop job")
        stop_btn.clicked.connect(lambda: self.stopRequested.emit(project, job))

        cancel_btn = QPushButton()
        cancel_btn.setObjectName("actionCancelBtn")
        cancel_btn.setToolTip("Delete job")
        cancel_btn.clicked.connect(lambda: self.cancelRequested.emit(project, job))

        logs_btn = QPushButton()
        logs_btn.setObjectName("actionLogsBtn")
        logs_btn.setToolTip("View logs")
        logs_btn.clicked.connect(lambda: self.logsRequested.emit(project, job))

        duplicate_btn = QPushButton()
        duplicate_btn.setObjectName("actionDuplicateBtn")
        duplicate_btn.setToolTip("Duplicate job")
        duplicate_btn.clicked.connect(lambda: self.duplicateRequested.emit(project, job))

        modify_btn = QPushButton()
        modify_btn.setObjectName("actionModifyBtn")
        modify_btn.setToolTip("Modify job")
        modify_btn.clicked.connect(lambda: self.modifyRequested.emit(project, job))

        terminal_btn = QPushButton()
        terminal_btn.setObjectName("actionTerminalBtn")
        terminal_btn.setToolTip("Open terminal on job node")
        terminal_btn.clicked.connect(lambda: self.terminalRequested.emit(project, job))
        
        # Enable/disable buttons based on job status
        job_status = job.status.upper() if hasattr(job, 'status') else None
        if job_status:
            submit_btn.setEnabled(job_status == "NOT_SUBMITTED")
            stop_btn.setEnabled(job_status in ["RUNNING", "PENDING"])
            cancel_btn.setEnabled(job_status in ["NOT_SUBMITTED", "COMPLETED", "FAILED", "CANCELLED"])
            logs_btn.setEnabled(True)
            modify_btn.setEnabled(job_status == "NOT_SUBMITTED")
            duplicate_btn.setEnabled(True)
            terminal_btn.setEnabled(job_status == "RUNNING")

        # Add buttons to layout
        layout.addWidget(submit_btn)
        layout.addWidget(stop_btn)
        layout.addWidget(cancel_btn)
        layout.addWidget(logs_btn)
        layout.addWidget(duplicate_btn)
        layout.addWidget(modify_btn)
        layout.addWidget(terminal_btn)
        
        return container

    def add_project(self, project_name: str, headers: List[str] | None = None) -> QTableWidget:
        """Add a project table if it doesn't exist"""
        if project_name in self._indices:
            return self._stack.widget(self._indices[project_name])

        headers = headers or self._default_headers
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
        table.setEditTriggers(table.EditTrigger.NoEditTriggers)
        table.setMouseTracking(True)

        # Configure column stretching
        h = table.horizontalHeader()
        h.setStretchLastSection(False)
        for i, head in enumerate(headers):
            if head == "Actions":
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(i, 240)  # Reduced width for smaller buttons
            elif head in ["CPU", "GPU", "RAM"]:
                h.setSectionResizeMode(
                    i, QHeaderView.ResizeMode.ResizeToContents)
                table.setColumnWidth(i, 70)
            elif head == "Name":
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                h.setSectionResizeMode(
                    i, QHeaderView.ResizeMode.ResizeToContents)

        index = self._stack.addWidget(table)
        self._indices[project_name] = index

        # Initialize job tracking for this project
        self._project_jobs[project_name] = {}

        return table

    def _apply_state_color(self, item: QTableWidgetItem):
        """Apply color based on job status"""
        txt = item.text().lower()
        if txt in STATE_COLORS:
            color = QColor(STATE_COLORS[txt])
            item.setData(Qt.ItemDataRole.ForegroundRole, QBrush(color))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _find_job_row(self, table: QTableWidget, job_id: str) -> int:
        """Find the row index for a given job ID, return -1 if not found"""
        for row in range(table.rowCount()):
            item = table.item(row, 0)  # Job ID is in first column
            if item and item.text() == str(job_id):
                return row
        return -1

    def _update_job_row(self, table: QTableWidget, row: int, job: Job, project: Project):
        """Update a specific row with new job data, using Job and Project objects directly."""
        actions_col = table.columnCount() - 1
        job_data = job.to_table_row() if hasattr(job, "to_table_row") else []
        # Update data columns (exclude actions column)
        for col in range(actions_col):
            if col < len(job_data):
                item = table.item(row, col)
                if not item:
                    item = QTableWidgetItem()
                    table.setItem(row, col, item)

                old_text = item.text()
                new_text = str(job_data[col])

                # Only update if text has changed
                if old_text != new_text:
                    item.setText(new_text)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                    # Apply status coloring for status column
                    if col == 2:
                        self._apply_state_color(item)

                    # Resource columns styling
                    if 4 <= col <= 6:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Update action buttons only if status changed
        current_action_widget = table.cellWidget(row, actions_col)
        needs_new_actions = True
        job_status = job.status if hasattr(job, 'status') else None
        if current_action_widget and hasattr(current_action_widget, '_job_status'):
            if current_action_widget._job_status == job_status:
                needs_new_actions = False

        if needs_new_actions:
            action_widget = self._create_actions_widget(project, job)
            action_widget._job_status = job_status  # Store status for comparison
            table.setCellWidget(row, actions_col, action_widget)

    def _add_job_row(self, table: QTableWidget, job: Job, project: Project):
        """Add a new job row to the table, using Job and Project objects directly."""
        actions_col = table.columnCount() - 1
        row_position = table.rowCount()
        table.insertRow(row_position)
        table.verticalHeader().setDefaultSectionSize(self._ROW_HEIGHT)

        job_data = job.to_table_row() if hasattr(job, "to_table_row") else []
        # Add data to columns
        for col in range(actions_col):
            val = job_data[col] if col < len(job_data) else ""
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if col == 2:  # Status column
                self._apply_state_color(item)

            # Resource columns styling
            if 4 <= col <= 6:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            # Apply alternating row colors
            if row_position % 2 == 0:
                item.setBackground(QColor(COLOR_DARK_BG))
            else:
                item.setBackground(QColor(COLOR_DARK_BG_ALT))

            table.setItem(row_position, col, item)

        # Add action buttons
        action_widget = self._create_actions_widget(project, job)
        action_widget._job_status = job.status if hasattr(job, 'status') else None
        table.setCellWidget(row_position, actions_col, action_widget)
        # Update job_id to row_index mapping
        if project.name not in self._job_row_indices:
            self._job_row_indices[project.name] = {}
        job_id = str(job.id) if hasattr(job, "id") else None
        if job_id:
            self._job_row_indices[project.name][job_id] = row_position

    def update_jobs(self, project: Project, jobs: Iterable[Job]) -> None:
        """
        Efficiently update jobs for a project using Project and Job objects directly.
        Only updates changed rows and adds/removes rows as needed.
        """
        table = self.add_project(project.name)
        jobs_list = list(jobs)

        # Convert new job data to a dictionary keyed by job_id
        new_jobs = {str(job.id): job for job in jobs_list if hasattr(job, 'id')}
        current_jobs = self._project_jobs.get(project.name, {})

        # Find jobs to update, add, or remove
        jobs_to_update = []
        jobs_to_add = []
        jobs_to_remove = []

        for job_id, job in new_jobs.items():
            if job_id in current_jobs:
                # Check if job data has changed (compare to_table_row)
                if current_jobs[job_id].to_table_row() != job.to_table_row():
                    jobs_to_update.append((job_id, job))
            else:
                jobs_to_add.append((job_id, job))

        for job_id in current_jobs:
            if job_id not in new_jobs:
                jobs_to_remove.append(job_id)

        # Remove jobs that no longer exist
        for job_id in jobs_to_remove:
            row = self._job_row_indices.get(project.name, {}).get(job_id, -1)
            if row >= 0:
                table.removeRow(row)
                # Remove from mapping
                del self._job_row_indices[project.name][job_id]

        # Update existing jobs
        for job_id, job in jobs_to_update:
            row = self._find_job_row(table, job_id)
            if row >= 0:
                self._update_job_row(table, row, job, project)

        # Add new jobs
        for job_id, job in jobs_to_add:
            self._add_job_row(table, job, project)

        # Update our tracking dictionary
        self._project_jobs[project.name] = new_jobs.copy()
        # After all adds/removes, rebuild mapping to ensure consistency
        self._job_row_indices[project.name] = {}
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item:
                self._job_row_indices[project.name][item.text()] = row

    def add_single_job(self, project: Project, job: Job) -> None:
        """Add a single new job to the specified project's table using a Job instance and Project object."""
        if project.name in self._indices:
            table = self._stack.widget(self._indices[project.name])
        else:
            raise Exception(f"Project {project.name} not found")
        job_id = str(job.id) if hasattr(job, "id") else None

        if job_id:
            self._add_job_row(table, job, project)
            # Update tracking
            if project.name not in self._project_jobs:
                self._project_jobs[project.name] = {}
            self._project_jobs[project.name][job_id] = job
            # Update mapping
            self._job_row_indices[project.name][job_id] = table.rowCount() - 1

    def update_single_job_row(self, project: Project, job: Job) -> None:
        """Update a single job row in the specified project's table using Project and Job objects."""
        if project.name not in self._indices:
            return

        table = self._stack.widget(self._indices[project.name])
        if not table:
            return
        row = self._job_row_indices.get(project.name, {}).get(str(job.id), -1)
        if row >= 0:
            self._update_job_row(table, row, job, project)
            # Update tracking
            if project.name not in self._project_jobs:
                self._project_jobs[project.name] = {}
            self._project_jobs[project.name][str(job.id)] = job

    def update_job_id(self, project: Project, old_job_id: str, new_job: Job) -> None:
        """
        Update a job's ID (used when temporary job gets submitted and receives real SLURM ID), using Project and Job objects.
        """
        if project.name not in self._indices:
            return

        table = self._stack.widget(self._indices[project.name])
        if not table:
            return

        # Find and remove the old job row
        old_row = self._job_row_indices.get(project.name, {}).get(old_job_id, -1)
        if old_row >= 0:
            table.removeRow(old_row)
            del self._job_row_indices[project.name][old_job_id]

        # Add the new job with updated ID and data
        self._add_job_row(table, new_job, project)

        # Update tracking - remove old ID and add new one
        if project.name in self._project_jobs:
            if old_job_id in self._project_jobs[project.name]:
                del self._project_jobs[project.name][old_job_id]
            self._project_jobs[project.name][str(new_job.id)] = new_job
        # Update mapping
        self._job_row_indices[project.name][str(new_job.id)] = table.rowCount() - 1

    def remove_job(self, project: Project, job: Job) -> None:
        """Remove a job from the project table using Project and Job objects."""
        if project.name not in self._indices:
            return
        table = self._stack.widget(self._indices[project.name])
        if not table:
            return
        row = self._job_row_indices.get(project.name, {}).get(str(job.id), -1)
        if row >= 0:
            table.removeRow(row)
            # Update mapping
            del self._job_row_indices[project.name][str(job.id)]
            # Update tracking
            if project.name in self._project_jobs and str(job.id) in self._project_jobs[project.name]:
                del self._project_jobs[project.name][str(job.id)]
        # After removal, reindex all rows for this project
        self._job_row_indices[project.name] = {}
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item:
                self._job_row_indices[project.name][item.text()] = row

    def show_project(self, project_or_name) -> None:
        """Show the specified project's table
        
        Args:
            project_or_name: Can be either a Project object or a project name string
        """
        if isinstance(project_or_name, Project):
            project = project_or_name
            project_name = project.name
        else:
            project_name = project_or_name
            project = None

        if project_name not in self._indices:
            self.add_project(project_name)

        idx = self._indices[project_name]
        if self._stack.currentIndex() != idx:
            self._stack.setCurrentIndex(idx)

        # Always try to emit a valid Project object if possible
        if project is None:
            # Try to find the Project object from current jobs
            # _project_jobs[project_name] is a dict of job_id: Job, but we want the Project
            # If jobs exist, get the Project from any job
            jobs = self._project_jobs.get(project_name, {})
            if jobs:
                # Try to get the Project from the first job
                first_job = next(iter(jobs.values()))
                if hasattr(first_job, 'project') and first_job.project is not None:
                    project = first_job.project
        # Only emit if we have a Project object
        if project is not None:
            self.current_projectChanged.emit(project)
        # If still None, do not emit (prevents TypeError)

    def remove_project(self, project_name: str):
        """Remove a project and its table"""
        if project_name not in self._indices:
            return

        index = self._indices[project_name]
        item = self._stack.widget(index)
        self._stack.removeWidget(item)
        del self._indices[project_name]

        # Clean up tracking
        if project_name in self._project_jobs:
            del self._project_jobs[project_name]
        # Clean up mapping
        if project_name in self._job_row_indices:
            del self._job_row_indices[project_name]

        # Show first available project
        if self._indices:
            first_project = list(self._indices.keys())[0]
            self.show_project(first_project)

    def show_connection_error(self, project_name: str):
        """Show connection error message in the project's job table"""
        table = self.add_project(project_name)
        table.setRowCount(1)
        table.setColumnCount(1)
        table.setHorizontalHeaderLabels(["Status"])
        
        error_item = QTableWidgetItem("⚠️ Unavailable Connection - Cannot load jobs")
        error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        error_item.setData(Qt.ItemDataRole.ForegroundRole, QBrush(QColor(COLOR_RED)))
        error_item.setFlags(error_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        
        table.setItem(0, 0, error_item)
        table.horizontalHeader().setStretchLastSection(True)