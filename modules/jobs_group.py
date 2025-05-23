import functools
from typing import Iterable, Sequence, Any, List, Dict, Optional
import os
from PyQt6.QtWidgets import (
    QWidget,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSizePolicy,
    QPushButton,
    QHBoxLayout,
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QTimer
from PyQt6 import QtGui
from utils import script_dir
from modules.defaults import (
    COLOR_DARK_BG as BASE_BG,
    COLOR_DARK_BG_ALT as ALT_BG,
    COLOR_DARK_BG_HOVER as HOVER_BG,
    COLOR_DARK_FG as FG,
    COLOR_DARK_BORDER as GRID,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_BLUE,
    COLOR_ORANGE,
    COLOR_PURPLE,
    COLOR_GRAY,
    STATUS_RUNNING,
    STATUS_PENDING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    NOT_SUBMITTED,
    scroll_bar_stylesheet,
    STATE_COLORS
)




class JobsGroup(QWidget):
    """Container for project-specific job tables with efficient updates."""

    current_projectChanged = pyqtSignal(str)
    startRequested = pyqtSignal(str, object)
    stopRequested = pyqtSignal(str, object)
    cancelRequested = pyqtSignal(str, object)
    logsRequested = pyqtSignal(str, object)
    submitRequested = pyqtSignal(str, object)
    duplicateRequested = pyqtSignal(str, object)
    modifyRequested = pyqtSignal(str, object)
    
    _ROW_HEIGHT = 50

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._stack = QStackedLayout(self)
        self._indices: Dict[str, int] = {}
        
        # Track job data for each project to enable efficient updates
        self._project_jobs: Dict[str, Dict[str, List[Any]]] = {}  # {project: {job_id: job_data}}

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

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_stylesheet()

    def _apply_stylesheet(self):
        style = f"""
            QTableWidget {{
                background-color: {BASE_BG};
                color: {FG};
                selection-background-color: {BASE_BG};
                selection-color: {FG};
                gridline-color: {BASE_BG};
                border: 1px solid {GRID};
                border-radius: 14px;
                font-size: 14px;
                show-decoration-selected: 1;
                padding-top: 5px;
            }}
            QTableWidget::item {{
                background-color: {ALT_BG};
                border: 0px solid {GRID};
                border-radius: 14px;
                margin-top: 2px;
                margin-bottom: 2px;
                padding: 5px;
            }}
            QTableWidget::item:hover {{
                background-color: {HOVER_BG};
            }}
            QHeaderView::section {{
                background-color: {ALT_BG};
                color: {FG};
                padding: 6px;
                border: 0px solid {GRID};
                border-bottom: 2px solid {COLOR_BLUE};
                font-weight: bold;
                border-radius: 14px;
            }}
            
            QPushButton {{
                border: none;
                border-radius: 14px;
                min-width: 30px;
                min-height: 30px;
                max-width: 30px;
                max-height: 30px;
                padding: 0px;
            }}
            
            QPushButton#submitBtn {{ background-color: {COLOR_GREEN}; }}
            QPushButton#stopBtn {{ background-color: {COLOR_PURPLE}; }}
            QPushButton#cancelBtn {{ background-color: {COLOR_RED}; }}
            QPushButton#logsBtn {{ background-color: #6DB8E8; }}
            QPushButton#duplicateBtn {{ background-color: {COLOR_ORANGE}; }}
            QPushButton#modifyBtn {{ background-color: #6272a4; }}
            
            QWidget#actionContainer {{ background: transparent; }}
        """ + scroll_bar_stylesheet
        self.setStyleSheet(style)

    def _create_action_button(self, icon_path, tooltip, button_id):
        """Create an action button with a simple ID-based style"""
        button = QPushButton()
        button.setObjectName(button_id)
        button.setToolTip(tooltip)
        button.setFixedSize(30, 30)

        icon = QtGui.QIcon(icon_path)
        if icon.isNull():
            print(f"Warning: Could not load icon from {icon_path}")
        button.setIcon(icon)
        button.setIconSize(QSize(16, 16))
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        return button

    def _create_actions_widget(self, project: str, job_id: Any, job_status: str = None) -> QWidget:
        """Creates a widget containing action buttons for a job row."""
        container = QWidget()
        container.setObjectName("actionContainer")

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Create buttons
        submit_path = os.path.join(script_dir, "src_static", "submit.svg")
        submit_btn = self._create_action_button(submit_path, "Submit job", "submitBtn")
        submit_btn.clicked.connect(functools.partial(self.submitRequested.emit, project, job_id))

        stop_path = os.path.join(script_dir, "src_static", "stop.svg")
        stop_btn = self._create_action_button(stop_path, "Stop job", "stopBtn")
        stop_btn.clicked.connect(functools.partial(self.stopRequested.emit, project, job_id))

        cancel_path = os.path.join(script_dir, "src_static", "delete.svg")
        cancel_btn = self._create_action_button(cancel_path, "Cancel job", "cancelBtn")
        cancel_btn.clicked.connect(functools.partial(self.cancelRequested.emit, project, job_id))

        logs_path = os.path.join(script_dir, "src_static", "view_logs.svg")
        logs_btn = self._create_action_button(logs_path, "View logs", "logsBtn")
        logs_btn.clicked.connect(functools.partial(self.logsRequested.emit, project, job_id))

        duplicate_path = os.path.join(script_dir, "src_static", "duplicate.svg")
        duplicate_btn = self._create_action_button(duplicate_path, "Duplicate job", "duplicateBtn")
        duplicate_btn.clicked.connect(functools.partial(self.duplicateRequested.emit, project, job_id))

        modify_path = os.path.join(script_dir, "src_static", "edit.svg")
        modify_btn = self._create_action_button(modify_path, "Modify job", "modifyBtn")
        modify_btn.clicked.connect(functools.partial(self.modifyRequested.emit, project, job_id))

        # Enable/disable buttons based on job status
        if job_status:
            job_status = job_status.upper()
            submit_btn.setEnabled(job_status == "NOT_SUBMITTED")
            stop_btn.setEnabled(job_status in ["RUNNING", "PENDING"])
            cancel_btn.setEnabled(job_status in ["NOT_SUBMITTED", "COMPLETED", "FAILED", "CANCELLED"])
            logs_btn.setEnabled(True)
            modify_btn.setEnabled(job_status == "NOT_SUBMITTED")
            duplicate_btn.setEnabled(True)

        # Add buttons to layout
        layout.addWidget(submit_btn)
        layout.addWidget(stop_btn)
        layout.addWidget(cancel_btn)
        layout.addWidget(logs_btn)
        layout.addWidget(duplicate_btn)
        layout.addWidget(modify_btn)

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
                table.setColumnWidth(i, 210)
            elif head in ["CPU", "GPU", "RAM"]:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
                table.setColumnWidth(i, 70)
            elif head == "Name":
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        index = self._stack.addWidget(table)
        self._indices[project_name] = index
        
        # Initialize job tracking for this project
        self._project_jobs[project_name] = {}
        
        return table

    def _apply_state_color(self, item: QTableWidgetItem):
        """Apply color based on job status"""
        txt = item.text().lower()
        if txt in STATE_COLORS:
            color = QtGui.QColor(STATE_COLORS[txt])
            item.setData(Qt.ItemDataRole.ForegroundRole, QtGui.QBrush(color))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def _find_job_row(self, table: QTableWidget, job_id: str) -> int:
        """Find the row index for a given job ID, return -1 if not found"""
        for row in range(table.rowCount()):
            item = table.item(row, 0)  # Job ID is in first column
            if item and item.text() == str(job_id):
                return row
        return -1

    def _update_job_row(self, table: QTableWidget, row: int, job_data: List[Any], project_name: str):
        """Update a specific row with new job data"""
        actions_col = table.columnCount() - 1
        job_id = job_data[0] if job_data else None
        job_status = job_data[2] if len(job_data) > 2 else None

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
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Update action buttons only if status changed
        current_action_widget = table.cellWidget(row, actions_col)
        needs_new_actions = True
        
        if current_action_widget and hasattr(current_action_widget, '_job_status'):
            if current_action_widget._job_status == job_status:
                needs_new_actions = False
        
        if needs_new_actions:
            action_widget = self._create_actions_widget(project_name, job_id, job_status)
            action_widget._job_status = job_status  # Store status for comparison
            table.setCellWidget(row, actions_col, action_widget)

    def _add_job_row(self, table: QTableWidget, job_data: List[Any], project_name: str):
        """Add a new job row to the table"""
        actions_col = table.columnCount() - 1
        row_position = table.rowCount()
        table.insertRow(row_position)
        table.verticalHeader().setDefaultSectionSize(self._ROW_HEIGHT)

        job_id = job_data[0] if job_data else None
        job_status = job_data[2] if len(job_data) > 2 else None

        # Add data to columns
        for col in range(actions_col):
            val = job_data[col] if col < len(job_data) else ""
            item = QTableWidgetItem(str(val))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if col == 2:  # Status column
                self._apply_state_color(item)

            # Resource columns styling
            if 4 <= col <= 6:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            # Apply alternating row colors
            if row_position % 2 == 0:
                item.setBackground(QtGui.QColor(BASE_BG))
            else:
                item.setBackground(QtGui.QColor(ALT_BG))

            table.setItem(row_position, col, item)

        # Add action buttons
        action_widget = self._create_actions_widget(project_name, job_id, job_status)
        action_widget._job_status = job_status
        table.setCellWidget(row_position, actions_col, action_widget)

    def update_jobs(self, project_name: str, rows: Iterable[Sequence[Any]]) -> None:
        """
        Efficiently update jobs for a project.
        Only updates changed rows and adds/removes rows as needed.
        """
        table = self.add_project(project_name)
        rows_list = list(rows)
        
        # Convert new job data to a dictionary keyed by job_id
        new_jobs = {}
        for row in rows_list:
            if row:
                job_id = str(row[0])
                new_jobs[job_id] = list(row)
        
        # Get current jobs for this project
        current_jobs = self._project_jobs.get(project_name, {})
        
        # Find jobs to update, add, or remove
        jobs_to_update = []
        jobs_to_add = []
        jobs_to_remove = []
        
        for job_id, job_data in new_jobs.items():
            if job_id in current_jobs:
                # Check if job data has changed
                if current_jobs[job_id] != job_data:
                    jobs_to_update.append((job_id, job_data))
            else:
                jobs_to_add.append((job_id, job_data))
        
        for job_id in current_jobs:
            if job_id not in new_jobs:
                jobs_to_remove.append(job_id)
        
        # Remove jobs that no longer exist
        for job_id in jobs_to_remove:
            row = self._find_job_row(table, job_id)
            if row >= 0:
                table.removeRow(row)
        
        # Update existing jobs
        for job_id, job_data in jobs_to_update:
            row = self._find_job_row(table, job_id)
            if row >= 0:
                self._update_job_row(table, row, job_data, project_name)
        
        # Add new jobs
        for job_id, job_data in jobs_to_add:
            self._add_job_row(table, job_data, project_name)
        
        # Update our tracking dictionary
        self._project_jobs[project_name] = new_jobs.copy()

    def add_single_job(self, project_name: str, job_data: Sequence[Any]) -> None:
        """Add a single new job to the specified project's table."""
        table = self.add_project(project_name)
        job_id = str(job_data[0]) if job_data else None
        
        if job_id:
            # Check if job already exists
            existing_row = self._find_job_row(table, job_id)
            if existing_row >= 0:
                # Update existing job
                self._update_job_row(table, existing_row, list(job_data), project_name)
            else:
                # Add new job
                self._add_job_row(table, list(job_data), project_name)
            
            # Update tracking
            if project_name not in self._project_jobs:
                self._project_jobs[project_name] = {}
            self._project_jobs[project_name][job_id] = list(job_data)

    def update_single_job_row(self, project_name: str, job_id: str, job_data: List[Any]) -> None:
        """Update a single job row in the specified project's table."""
        if project_name not in self._indices:
            return
            
        table = self._stack.widget(self._indices[project_name])
        if not table:
            return
            
        row = self._find_job_row(table, job_id)
        if row >= 0:
            self._update_job_row(table, row, job_data, project_name)
            
            # Update tracking
            if project_name not in self._project_jobs:
                self._project_jobs[project_name] = {}
            self._project_jobs[project_name][job_id] = job_data.copy()

    def update_job_id(self, project_name: str, old_job_id: str, new_job_id: str, updated_job_data: List[Any]) -> None:
        """
        Update a job's ID (used when temporary job gets submitted and receives real SLURM ID)
        """
        if project_name not in self._indices:
            return
            
        table = self._stack.widget(self._indices[project_name])
        if not table:
            return
            
        # Find and remove the old job row
        old_row = self._find_job_row(table, old_job_id)
        if old_row >= 0:
            table.removeRow(old_row)
            
        # Add the new job with updated ID and data
        self._add_job_row(table, updated_job_data, project_name)
        
        # Update tracking - remove old ID and add new one
        if project_name in self._project_jobs:
            if old_job_id in self._project_jobs[project_name]:
                del self._project_jobs[project_name][old_job_id]
            self._project_jobs[project_name][new_job_id] = updated_job_data.copy()

    def remove_job(self, project_name: str, job_id: str) -> None:
        """Remove a job from the project table."""
        if project_name not in self._indices:
            return
            
        table = self._stack.widget(self._indices[project_name])
        if not table:
            return
            
        row = self._find_job_row(table, job_id)
        if row >= 0:
            table.removeRow(row)
            
            # Update tracking
            if project_name in self._project_jobs and job_id in self._project_jobs[project_name]:
                del self._project_jobs[project_name][job_id]

    def highlight_job_row(self, project_name: str, job_id: str, duration: int = 3000):
        """Briefly highlight a job row to draw attention to status changes."""
        if project_name not in self._indices:
            return
            
        table = self._stack.widget(self._indices[project_name])
        if not table:
            return
            
        row = self._find_job_row(table, job_id)
        if row == -1:
            return
            
        # Temporarily change row background color
        original_colors = []
        highlight_color = QtGui.QColor("#4CAF50")  # Green highlight
        
        for col in range(table.columnCount() - 1):  # Exclude actions column
            item = table.item(row, col)
            if item:
                original_colors.append(item.background())
                item.setBackground(highlight_color)
        
        # Use QTimer to restore original colors after duration
        def restore_colors():
            for col, original_color in enumerate(original_colors):
                item = table.item(row, col)
                if item:
                    item.setBackground(original_color)
        
        QTimer.singleShot(duration, restore_colors)

    def show_project(self, project_name: str) -> None:
        """Show the specified project's table"""
        if project_name not in self._indices:
            self.add_project(project_name)
        idx = self._indices[project_name]
        if self._stack.currentIndex() != idx:
            self._stack.setCurrentIndex(idx)
            self.current_projectChanged.emit(project_name)

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
        
        # Show first available project
        if self._indices:
            first_project = list(self._indices.keys())[0]
            self.show_project(first_project)