import functools
from typing import Iterable, Sequence, Any, List
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
from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6 import QtGui
from utils import script_dir
# ---------------------------------------------------------------------------
# Palette & constants from your central defaults module
# ---------------------------------------------------------------------------
from modules.defaults import (
    # colours (Catppuccin-Macchiato Dark)
    COLOR_DARK_BG as BASE_BG,
    COLOR_DARK_BG_ALT as ALT_BG,
    COLOR_DARK_BG_HOVER as HOVER_BG,
    COLOR_DARK_FG as FG,
    COLOR_DARK_BORDER as GRID,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_BLUE,       # used for Logs button
    COLOR_ORANGE,
    COLOR_PURPLE,     # Added for another new action, e.g., Stop
    COLOR_GRAY,
    # statuses
    STATUS_RUNNING,
    STATUS_PENDING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    NOT_SUBMITTED,
    # shared scrollbar qss
    scroll_bar_stylesheet,
)

STATE_COLORS = {
    STATUS_RUNNING.lower(): COLOR_GREEN,
    STATUS_PENDING.lower(): COLOR_ORANGE,
    STATUS_COMPLETED.lower(): COLOR_BLUE,
    STATUS_FAILED.lower(): COLOR_RED,
    NOT_SUBMITTED.lower(): COLOR_GRAY,
}


class JobsGroup(QWidget):
    """Container for project-specific job tables."""

    current_projectChanged = pyqtSignal(str)
    # project, job_id (can be re-purposed for 'Submit')
    startRequested = pyqtSignal(str, object)
    stopRequested = pyqtSignal(str, object)    # project, job_id (NEW)
    cancelRequested = pyqtSignal(str, object)  # project, job_id
    logsRequested = pyqtSignal(str, object)    # project, job_id
    submitRequested = pyqtSignal(str, object)
    duplicateRequested = pyqtSignal(str, object)  # project, job_id (NEW)
    modifyRequested = pyqtSignal(str, object)  # project, job_id (NEW)
    _ROW_HEIGHT = 50  # px – comfy touch-friendly rows

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._stack = QStackedLayout(self)
        self._indices: dict[str, int] = {}

        self._default_headers = [
            "Job ID",
            "Name",
            "Status",
            "Runtime",
            "CPU",    # New column
            "GPU",    # New column
            "RAM",    # New column
            "Actions",
        ]

        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)
        self._apply_stylesheet()
        self._hovered_row = -1  # Keep track of the currently hovered row

    # ------------------------------------------------------------------ styles

    def _apply_stylesheet(self):
        style = f"""
            /* ------------------------------------------------ base table */
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
            QTableWidget::item{{
                background-color: {ALT_BG};
                border: 0px solid {GRID};
                border-radius: 14px;
                margin-top: 2px;
                margin-bottom: 2px;
                padding: 5px;
            }}
            /* ------------------------------------------------ hover row item*/
            QTableWidget::item:hover {{
                background-color: {HOVER_BG};
            }}
            /* ------------------------------------------------ header */
            QHeaderView::section {{
                background-color: {ALT_BG};
                color: {FG};
                padding: 6px;
                border: 0px solid {GRID};
                border-bottom: 2px solid {COLOR_BLUE};
                font-weight: bold;
                border-radius: 14px;
            }}
            
            /* BASIC BUTTON STYLES - Simplify to fix issues */
            QPushButton {{
                border: none;
                border-radius: 14px;
                min-width: 30px;
                min-height: 30px;
                max-width: 30px;
                max-height: 30px;
                padding: 0px;
            }}
            
            /* Color-specific styles */
            QPushButton#submitBtn {{
                background-color: {COLOR_GREEN};
            }}
            QPushButton#stopBtn {{
                background-color: {COLOR_PURPLE};
            }}
            QPushButton#cancelBtn {{
                background-color: {COLOR_RED};
            }}
            QPushButton#logsBtn {{
                background-color: #6DB8E8;
            }}
            QPushButton#duplicateBtn {{
                background-color: {COLOR_ORANGE};
            }}
            QPushButton#modifyBtn {{
                background-color: #6272a4;  /* A muted blue-gray color */
            }}
            
            /* Action widget container */
            QWidget#actionContainer {{
                background: transparent;
            }}
        """ + scroll_bar_stylesheet
        self.setStyleSheet(style)

    # ---------------------------------------------------------------- helpers
    def _create_action_button(self, icon_path, tooltip, button_id):
        """Create an action button with a simple ID-based style"""
        button = QPushButton()
        # Use ID instead of actionType property
        button.setObjectName(button_id)
        button.setToolTip(tooltip)

        # Set fixed size
        button.setFixedSize(30, 30)

        # Load icon
        icon = QtGui.QIcon(icon_path)
        if icon.isNull():
            print(f"Warning: Could not load icon from {icon_path}")
        button.setIcon(icon)
        button.setIconSize(QSize(16, 16))

        # Set cursor
        button.setCursor(Qt.CursorShape.PointingHandCursor)

        return button

    def _create_actions_widget(self, project: str, job_id: Any, job_status: str = None) -> QWidget:
        """
        Creates a widget containing action buttons for a job row.

        Args:
            project: Project name
            job_id: Job ID
            job_status: Current job status (optional) - used to determine which buttons to enable

        Returns:
            Widget containing action buttons
        """
        # Create container widget
        container = QWidget()
        container.setObjectName("actionContainer")

        # Create horizontal layout with no margins
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Create buttons with simple IDs
        submit_path = os.path.join(script_dir, "src_static", "submit.svg")
        submit_btn = self._create_action_button(
            submit_path, "Submit job", "submitBtn")
        submit_btn.clicked.connect(
            # Using functools.partial
            functools.partial(self.submitRequested.emit, project, job_id))

        stop_path = os.path.join(script_dir, "src_static", "stop.svg")
        stop_btn = self._create_action_button(stop_path, "Stop job", "stopBtn")
        stop_btn.clicked.connect(
            # Using functools.partial
            functools.partial(self.stopRequested.emit, project, job_id))

        cancel_path = os.path.join(script_dir, "src_static", "delete.svg")
        cancel_btn = self._create_action_button(
            cancel_path, "Cancel job", "cancelBtn")
        cancel_btn.clicked.connect(functools.partial(
            self.cancelRequested.emit, project, job_id))  # Using functools.partial

        logs_path = os.path.join(script_dir, "src_static", "view_logs.svg")
        logs_btn = self._create_action_button(
            logs_path, "View logs", "logsBtn")
        logs_btn.clicked.connect(
            # Using functools.partial
            functools.partial(self.logsRequested.emit, project, job_id))

        # New action buttons
        duplicate_path = os.path.join(
            script_dir, "src_static", "duplicate.svg")
        duplicate_btn = self._create_action_button(
            duplicate_path, "Duplicate job", "duplicateBtn")
        duplicate_btn.clicked.connect(
            # Using functools.partial
            functools.partial(self.duplicateRequested.emit, project, job_id))

        modify_path = os.path.join(script_dir, "src_static", "edit.svg")
        modify_btn = self._create_action_button(
            modify_path, "Modify job", "modifyBtn")
        modify_btn.clicked.connect(
            # Using functools.partial
            functools.partial(self.modifyRequested.emit, project, job_id))

        # Enable/disable buttons based on job status
        if job_status:
            job_status = job_status.upper()

            # Submit button is only enabled for NOT_SUBMITTED jobs
            submit_btn.setEnabled(job_status == "NOT_SUBMITTED")

            # Stop button is only enabled for RUNNING jobs
            stop_btn.setEnabled(job_status == "RUNNING")

            # Cancel button is enabled for PENDING, RUNNING, and NOT_SUBMITTED jobs
            cancel_btn.setEnabled(
                job_status in ["PENDING", "RUNNING", "NOT_SUBMITTED"])

            # Logs button is enabled for all statuses except NOT_SUBMITTED
            logs_btn.setEnabled(job_status != "NOT_SUBMITTED")

            # Modify button is only enabled for NOT_SUBMITTED jobs
            modify_btn.setEnabled(job_status == "NOT_SUBMITTED")

            # Duplicate button is enabled for all job statuses
            duplicate_btn.setEnabled(True)

        # Add buttons to layout
        layout.addWidget(submit_btn)
        layout.addWidget(stop_btn)
        layout.addWidget(cancel_btn)
        layout.addWidget(logs_btn)
        layout.addWidget(duplicate_btn)
        layout.addWidget(modify_btn)

        return container

    # ------------------------------------------------------------- public API
    def add_project(self, project_name: str, headers: List[str] | None = None) -> QTableWidget:
        if project_name in self._indices:
            # type: ignore[arg-type]
            return self._stack.widget(self._indices[project_name])

        headers = headers or self._default_headers
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
        table.setEditTriggers(table.EditTrigger.NoEditTriggers)
        table.setMouseTracking(True)  # Enable mouse tracking for hover events

        # column stretch – keep Actions auto-width
        h = table.horizontalHeader()
        h.setStretchLastSection(False)
        for i, head in enumerate(headers):
            if head == "Actions":
                # Set fixed width for actions column - now with 6 buttons
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(i, 210)  # Increased width for 6 buttons
            elif head in ["CPU", "GPU", "RAM"]:
                # Compact width for resource columns
                h.setSectionResizeMode(
                    i, QHeaderView.ResizeMode.ResizeToContents)
                # Default width for resource columns
                table.setColumnWidth(i, 70)
            elif head == "Name":
                # Name gets the most space
                h.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                # Other columns resize to content
                h.setSectionResizeMode(
                    i, QHeaderView.ResizeMode.ResizeToContents)

        index = self._stack.addWidget(table)
        self._indices[project_name] = index
        return table

    def _apply_state_color(self, item: QTableWidgetItem):
        txt = item.text().lower()
        if txt in STATE_COLORS:
            color = QtGui.QColor(STATE_COLORS[txt])
            item.setData(Qt.ItemDataRole.ForegroundRole, QtGui.QBrush(color))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = item.font()
            item.setFont(font)

    def update_jobs(self, project_name: str, rows: Iterable[Sequence[Any]]) -> None:
        table = self.add_project(project_name)
        actions_col = table.columnCount() - 1

        rows_list = list(rows)
        table.setRowCount(len(rows_list))
        table.verticalHeader().setDefaultSectionSize(self._ROW_HEIGHT)

        # clear existing action widgets and reset styles
        for r in range(table.rowCount()):
            if w := table.cellWidget(r, actions_col):
                w.setParent(None)
            # Also reset style for the item itself to clear any lingering effects
            for c in range(table.columnCount()):
                item = table.item(r, c)
                if item:
                    item.setBackground(QtGui.QColor(
                        BASE_BG if r % 2 == 0 else ALT_BG))

        for r, row in enumerate(rows_list):
            # Get job status for action buttons (index 2 is typically status)
            job_status = row[2] if len(row) > 2 else None

            # Need to handle potentially shorter row data (if old data format)
            for c in range(actions_col):
                # Fill in the value if available, else empty string
                val = row[c] if c < len(row) else ""
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(r, c, it)
                if c == 2:  # Status column
                    self._apply_state_color(it)

                # Resource columns styling - right-align and compact
                if 4 <= c <= 6:  # CPU, GPU, RAM columns
                    it.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            job_id = row[0] if row else None
            action_widget = self._create_actions_widget(
                project_name, job_id, job_status)
            table.setCellWidget(r, actions_col, action_widget)

    def add_single_job(self, project_name: str, job_data: Sequence[Any]) -> None:
        """
        Adds a single new job to the specified project's table.

        Args:
            project_name: Name of the project to add the job to
            job_data: Sequence containing the job details (ID, name, status, etc.)
        """
        table = self.add_project(project_name)
        actions_col = table.columnCount() - 1

        row_position = table.rowCount()
        table.insertRow(row_position)
        table.verticalHeader().setDefaultSectionSize(self._ROW_HEIGHT)

        # Handle the job data, ensuring it has at least enough elements for our columns
        extended_job_data = list(job_data)
        while len(extended_job_data) < actions_col:
            extended_job_data.append("")  # Pad with empty strings if needed

        # Get job status for action buttons (index 2 is typically status)
        job_status = extended_job_data[2] if len(
            extended_job_data) > 2 else None

        for c in range(actions_col):
            val = extended_job_data[c] if c < len(extended_job_data) else ""
            it = QTableWidgetItem(str(val))

            # Center alignment for most items
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # Apply specific formatting for different columns
            if c == 2:  # Status column
                self._apply_state_color(it)

            # Resource columns styling - right-align
            if 4 <= c <= 6:  # CPU, GPU, RAM columns
                it.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            # Apply alternating row colors
            if row_position % 2 == 0:
                it.setBackground(QtGui.QColor(BASE_BG))
            else:
                it.setBackground(QtGui.QColor(ALT_BG))

            table.setItem(row_position, c, it)

        job_id = extended_job_data[0] if extended_job_data else None
        action_widget = self._create_actions_widget(
            project_name, job_id, job_status)
        table.setCellWidget(row_position, actions_col, action_widget)

        # Auto-adjust row heights and column widths for better display
        # table.resizeRowsToContents()
        # for i in range(actions_col):
        #     table.resizeColumnToContents(i)

    def show_project(self, project_name: str) -> None:
        if project_name not in self._indices:
            self.add_project(project_name)
        idx = self._indices[project_name]
        if self._stack.currentIndex() != idx:
            self._stack.setCurrentIndex(idx)
            self.current_projectChanged.emit(project_name)
