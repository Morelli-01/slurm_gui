from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGroupBox,
    QApplication, QScrollArea, QPushButton, QInputDialog, QLineEdit,
    QDialog, QComboBox, QSpinBox, QCheckBox, QTimeEdit, QTextEdit,
    QFormLayout, QFileDialog, QDoubleSpinBox, QTabWidget, QListView, QStyledItemDelegate, QMessageBox,QAbstractItemView,
    QProgressBar, QToolButton, QSizePolicy, QSplitter
)
from PyQt6.QtGui import QFont, QPixmap, QIcon, QMovie, QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRect, QTime, QSortFilterProxyModel, QThread, QTimer, QEvent
import os, sys, time
JOB_QUEUE_FIELDS = [
    "Job ID", "Job Name", "User",
    "Account", "Priority", "Status",
    "Time Used", "Partition", "CPUs",
    "Time Limit", "Reason", "RAM",
    "GPUs", "Nodelist"
]

STUDENTS_JOBS_KEYWORD = [
    "tesi",
    "cvcs",
    "ai4bio"
]

BTN_GREEN = "btnGreen"
BTN_RED = "btnRed"
BTN_BLUE = "btnBlue"

THEME_DARK = "Dark"
THEME_LIGHT = "Light"

# SLURM Statuses
STATUS_RUNNING = "RUNNING"
STATUS_PENDING = "PENDING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_COMPLETING = "COMPLETING"
STATUS_PREEMPTED = "PREEMPTED"
STATUS_SUSPENDED = "SUSPENDED"
STATUS_STOPPED = "STOPPED"
NOT_SUBMITTED = "NOT_SUBMITTED"

NODE_STATE_IDLE = "IDLE"
NODE_STATE_ALLOC = "ALLOCATED"  # Or RUNNING, MIXED
NODE_STATE_DOWN = "DOWN"
NODE_STATE_DRAIN = "DRAIN"
NODE_STATE_UNKNOWN = "UNKNOWN"


# Colors (Catppuccin Macchiato inspired for Dark, simple Light)
# COLOR_DARK_BG = "#1e1e2f"
# COLOR_DARK_FG = "#f8f8f2"
# COLOR_DARK_BG_ALT = "#2e2e3f"
# COLOR_DARK_BG_HOVER = "#3e3e5f"
# COLOR_DARK_BORDER = "#44475a"
# COLOR_GREEN = "#50fa7b"  # Brighter Green
# COLOR_RED = "#ff5555"   # Brighter Red
# COLOR_BLUE = "#2196F3"  # Brighter Blue
# COLOR_ORANGE = "#ffb86c"  # Brighter Orange
# COLOR_GRAY = "#6272a4"   # Gray (Unknown/Offline) - Was Blue

# general colors

COLOR_LIGHT_BG = "#eff1f5"  # Light Background
COLOR_LIGHT_FG = "#4c4f69"  # Light Foreground
COLOR_LIGHT_BG_ALT = "#ccd0da"  # Light Alt Background
COLOR_LIGHT_BG_HOVER = "#bcc0cc"  # Light Hover
COLOR_LIGHT_BORDER = "#bcc0cc"  # Light Border

COLOR_DARK_BG = "#282a36"
COLOR_DARK_FG = "#f8f8f2"
COLOR_DARK_BG_ALT = "#383a59"
COLOR_DARK_BG_HOVER = "#44475a"
COLOR_DARK_BORDER = "#6272a4"
COLOR_GREEN = "#0ab836"
COLOR_RED = "#f13232"
COLOR_ORANGE = "#ffb86c"
COLOR_BLUE = "#8be9fd"
COLOR_GRAY = "#6272a4"
COLOR_PURPLE = "#8403fc"
# color for thw cluster status widget
COLOR_AVAILABLE = "#4CAF50"     # Green for Available
COLOR_USED = "#2196F3"          # Blue for Used
COLOR_UNAVAILABLE = "#F44336"   # Red for Unavailable (Drain/Down/Unknown)
COLOR_USED_BY_STUD = "#00AAAA"
COLOR_USED_PROD = "#AA00AA"
COLOR_MID_CONSTRAINT = "#EBC83F"
COLOR_UNAVAILABLE_RAM = "#d41406"
COLOR_MID_CONSTRAINT_RAM = "#dba021"

# Mapping internal states to colors
BLOCK_COLOR_MAP = {
    "available": COLOR_AVAILABLE,    # Available GPU on IDLE node
    "used": COLOR_USED,         # Used GPU on ALLOCATED/MIXED node
    "unavailable": COLOR_UNAVAILABLE,  # GPU on DRAIN/DOWN/UNKNOWN node
    "stud_used": COLOR_USED,
    "prod_used": COLOR_USED_PROD,
    "high-constraint": COLOR_UNAVAILABLE,
    "mid-constraint": COLOR_MID_CONSTRAINT,
    "high-constraint-ram_cpu": COLOR_UNAVAILABLE_RAM,
    "mid-constraint-ram_cpu": COLOR_MID_CONSTRAINT_RAM,
}

STATE_COLORS = {
    STATUS_RUNNING.lower(): COLOR_GREEN,
    STATUS_PENDING.lower(): COLOR_ORANGE,
    STATUS_COMPLETED.lower(): COLOR_BLUE,
    STATUS_FAILED.lower(): COLOR_RED,
    "cancelled": COLOR_PURPLE,  # Add cancelled status
    "suspended": COLOR_GRAY,    # Add suspended status
    "stopped": COLOR_GRAY,      # Add stopped status
    NOT_SUBMITTED.lower(): COLOR_GRAY,
}

scroll_bar_stylesheet = """
            QScrollBar:vertical {
                border: none;
                background: #2A2F3A;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #5D6167;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """