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
from PyQt6.QtCore import pyqtSignal, Qt, QPropertyAnimation, QEasingCurve
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
    # statuses
    STATUS_RUNNING,
    STATUS_PENDING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    # shared scrollbar qss
    scroll_bar_stylesheet,
)

STATE_COLORS = {
    STATUS_RUNNING.lower(): COLOR_GREEN,
    STATUS_PENDING.lower(): COLOR_ORANGE,
    STATUS_COMPLETED.lower(): COLOR_BLUE,
    STATUS_FAILED.lower(): COLOR_RED,
}

class JobsGroup(QWidget):
    """Container for project-specific job tables."""

    current_projectChanged = pyqtSignal(str)
    startRequested = pyqtSignal(str, object)   # project, job_id
    cancelRequested = pyqtSignal(str, object)  # project, job_id
    logsRequested = pyqtSignal(str, object)    # project, job_id

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
            "Actions",
        ]

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_stylesheet()
        self._hovered_row = -1 # Keep track of the currently hovered row

    # ------------------------------------------------------------------ styles
    def _apply_stylesheet(self):
        style = f"""
            /* ------------------------------------------------ base table */
            QTableWidget {{
                background-color: {BASE_BG};
                color: {FG};
                selection-background-color: {HOVER_BG};
                selection-color: {FG};
                gridline-color: {GRID};
                border: 1px solid {GRID};
                border-radius: 6px;
                font-size: 14px;
                /* Enable hover events for items */
                show-decoration-selected: 1;
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
                border: 1px solid {GRID};
                border-bottom: 2px solid {COLOR_BLUE};
                font-weight: bold;
            }}
            /* ------------------------------------------------ action buttons (flat) */
            QPushButton[actionType="start"] {{
                background-color: #2DCB89;
            }}
            QPushButton[actionType="cancel"] {{
                background-color: #DA5B5B;
            }}
            QPushButton[actionType="logs"] {{
                background-color: #6DB8E8;
            }}
            QPushButton[actionType] {{
                border-radius: 5px;
                padding: 6px 6px;
                color: white; /* Ensure icons/text are visible */
            }}
            /* Style for the widget containing action buttons when row is hovered */


        """ + scroll_bar_stylesheet
        self.setStyleSheet(style)

    # ---------------------------------------------------------------- helpers
    def _btn(self, label: str, tooltip: str, role: str, cb):
        b = QPushButton()
        # Load SVG and set as icon
        icon = QtGui.QIcon(label)
        if icon.isNull():
             print(f"Warning: Could not load icon from {label}")
        b.setIcon(icon)

        b.setProperty("actionType", role)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setToolTip(tooltip)
        b.setFixedHeight(28)
        b.clicked.connect(cb)
        return b

    def _create_actions_widget(self, project: str, job_id: Any) -> QWidget:
        w = QWidget()
        w.setObjectName("actionWidget") # Set an object name for styling
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # Construct full icon paths
        start_icon_path = os.path.join(script_dir, "src_static", "start.svg")
        delete_icon_path = os.path.join(script_dir, "src_static", "delete.svg")
        logs_icon_path = os.path.join(script_dir, "src_static", "view_logs.svg")


        lay.addWidget(self._btn(start_icon_path, "Start job", "start", lambda: self.startRequested.emit(project, job_id)))
        lay.addWidget(self._btn(delete_icon_path, "Cancel job", "cancel", lambda: self.cancelRequested.emit(project, job_id)))
        lay.addWidget(self._btn(logs_icon_path, "View logs", "logs", lambda: self.logsRequested.emit(project, job_id)))
        lay.addStretch(1) # Add stretch to push buttons to the left

        # REMOVE THIS LINE:
        # w.setStyleSheet("background-color: transparent;")

        return w

    # ------------------------------------------------------------- public API
    def add_project(self, project_name: str, headers: List[str] | None = None) -> QTableWidget:
        if project_name in self._indices:
            return self._stack.widget(self._indices[project_name])  # type: ignore[arg-type]

        headers = headers or self._default_headers
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(table.SelectionBehavior.SelectRows)
        table.setEditTriggers(table.EditTrigger.NoEditTriggers)
        table.setMouseTracking(True) # Enable mouse tracking for hover events


        # column stretch – keep Actions auto-width
        h = table.horizontalHeader()
        h.setStretchLastSection(False)
        for i, head in enumerate(headers):
            mode = QHeaderView.ResizeMode.Stretch if head != "Actions" else QHeaderView.ResizeMode.ResizeToContents
            h.setSectionResizeMode(i, mode)

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
                     item.setBackground(QtGui.QColor(BASE_BG if r % 2 == 0 else ALT_BG))


        for r, row in enumerate(rows_list):
            for c in range(actions_col):
                val = row[c] if c < len(row) else ""
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(r, c, it)
                if c == 2:  # Status column
                    self._apply_state_color(it)

            job_id = row[0] if row else None
            table.setCellWidget(r, actions_col, self._create_actions_widget(project_name, job_id))




    def show_project(self, project_name: str) -> None:
        if project_name not in self._indices:
            self.add_project(project_name)
        idx = self._indices[project_name]
        if self._stack.currentIndex() != idx:
            self._stack.setCurrentIndex(idx)
            self.current_projectChanged.emit(project_name)