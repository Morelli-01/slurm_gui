import sys, slurm_connection
import threading
import os
import subprocess
import re
import random  # For demo refresh
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QComboBox, QFrame, QSizePolicy, QStackedWidget, QFormLayout, QGroupBox,
    QTextEdit, QSpinBox, QFileDialog, QProgressBar, QMessageBox, QGridLayout, QScrollArea
)
from PyQt6.QtGui import QIcon, QColor, QPalette, QFont, QPixmap, QMovie
from PyQt6.QtCore import Qt, QSize, QTimer
from utils import *

# --- Constants ---
APP_TITLE = "SLURM Job Manager"
MIN_WIDTH = 1200
MIN_HEIGHT = 800
REFRESH_INTERVAL_MS = 10000  # 10 seconds

# Theme Keys
THEME_DARK = "Dark"
THEME_LIGHT = "Light"

# Colors (Catppuccin Macchiato inspired for Dark, simple Light)
COLOR_DARK_BG = "#1e1e2f"
COLOR_DARK_FG = "#f8f8f2"
COLOR_DARK_BG_ALT = "#2e2e3f"
COLOR_DARK_BG_HOVER = "#3e3e5f"
COLOR_DARK_BORDER = "#44475a"
COLOR_GREEN = "#50fa7b"  # Brighter Green
COLOR_RED = "#ff5555"   # Brighter Red
COLOR_BLUE = "#6272a4"  # Brighter Blue
COLOR_ORANGE = "#ffb86c"  # Brighter Orange
COLOR_GRAY = "#6272a4"   # Gray (Unknown/Offline) - Was Blue

COLOR_LIGHT_BG = "#eff1f5"  # Light Background
COLOR_LIGHT_FG = "#4c4f69"  # Light Foreground
COLOR_LIGHT_BG_ALT = "#ccd0da"  # Light Alt Background
COLOR_LIGHT_BG_HOVER = "#bcc0cc"  # Light Hover
COLOR_LIGHT_BORDER = "#bcc0cc"  # Light Border

# Object Names for Styling
BTN_GREEN = "btnGreen"
BTN_RED = "btnRed"
BTN_BLUE = "btnBlue"

# Default Job Values
DEFAULT_PARTITION = "compute"
DEFAULT_NODES = 1
DEFAULT_TASKS = 1
DEFAULT_MEMORY = "4G"
DEFAULT_TIME = "1:00:00"

# SLURM Statuses
STATUS_RUNNING = "RUNNING"
STATUS_PENDING = "PENDING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"  # Added for completeness

# SLURM Statuses (Node States - simplified)
NODE_STATE_IDLE = "IDLE"
NODE_STATE_ALLOC = "ALLOCATED"  # Or RUNNING, MIXED
NODE_STATE_DOWN = "DOWN"
NODE_STATE_DRAIN = "DRAIN"
NODE_STATE_UNKNOWN = "UNKNOWN"
# --- Helper Functions ---


def create_separator(shape=QFrame.Shape.HLine, color=COLOR_DARK_BORDER):
    """Creates a styled separator QFrame."""
    separator = QFrame()
    separator.setFrameShape(shape)
    separator.setFrameShadow(QFrame.Shadow.Sunken)
    separator.setStyleSheet(f"background-color: {color};")
    if shape == QFrame.Shape.HLine:
        separator.setFixedHeight(1)
    else:
        separator.setFixedWidth(1)
    return separator


def show_message(parent, title, text, icon=QMessageBox.Icon.Information):
    """Displays a simple message box."""
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(icon)
    msg_box.exec()

# --- Stylesheet Definitions ---


def get_dark_theme_stylesheet():
    with open("src_static/dark_theme.txt", "r") as f:
        stylesheet_template = f.read()

    return stylesheet_template.format(
        COLOR_DARK_BG=COLOR_DARK_BG,
        COLOR_DARK_FG=COLOR_DARK_FG,
        COLOR_DARK_BG_ALT=COLOR_DARK_BG_ALT,
        COLOR_DARK_BG_HOVER=COLOR_DARK_BG_HOVER,
        COLOR_DARK_BORDER=COLOR_DARK_BORDER,
        COLOR_GREEN=COLOR_GREEN,
        COLOR_RED=COLOR_RED,
        COLOR_BLUE=COLOR_BLUE,
        COLOR_ORANGE=COLOR_ORANGE,
        BTN_GREEN=BTN_GREEN,
        BTN_RED=BTN_RED,
        BTN_BLUE=BTN_BLUE,
    )


def get_light_theme_stylesheet():
    """Loads and returns the CSS stylesheet for the light theme from a file."""
    with open("/home/nicola/Desktop/slurm_gui/src_static/light_theme.txt", "r") as f:
        stylesheet = f.read()

    return stylesheet.format(
        COLOR_LIGHT_BG=COLOR_LIGHT_BG,
        COLOR_LIGHT_FG=COLOR_LIGHT_FG,
        COLOR_LIGHT_BG_ALT=COLOR_LIGHT_BG_ALT,
        COLOR_LIGHT_BG_HOVER=COLOR_LIGHT_BG_HOVER,
        COLOR_LIGHT_BORDER=COLOR_LIGHT_BORDER,
        COLOR_GREEN=COLOR_GREEN,
        COLOR_RED=COLOR_RED,
        COLOR_BLUE=COLOR_BLUE,
        COLOR_ORANGE=COLOR_ORANGE,
        BTN_GREEN=BTN_GREEN,
        BTN_RED=BTN_RED,
        BTN_BLUE=BTN_BLUE,
    )

# --- Main Application Class ---


class SlurmJobManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.slurm_connection = slurm_connection.SlurmConnection(
            "/home/nicola/Desktop/slurm_gui/configs/slurm_config.yaml")

        t = threading.Thread(target=self.slurm_connection.connect())
        t.start()

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.setWindowIcon(QIcon("/home/nicola/Desktop/slurm_gui/src_static/logo.png")
                           )  # Add an icon path here if you have one

        # --- Theme Setup ---
        self.themes = {
            THEME_DARK: get_dark_theme_stylesheet(),
            THEME_LIGHT: get_light_theme_stylesheet(),
        }
        self.current_theme = THEME_DARK
        self.setStyleSheet(self.themes[self.current_theme])

        # --- Central Widget and Layout ---
        self.central_widget = QWidget()
        self.central_widget.setMinimumSize(QSize(600, 900))
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15)  # Increased margins
        self.main_layout.setSpacing(15)  # Increased spacing

        # --- UI Elements ---
        self.nav_buttons = {}  # Store nav buttons for easier access
        self.create_navigation_bar()
        self.main_layout.addWidget(create_separator(color=COLOR_DARK_BORDER if self.current_theme ==
                                   THEME_DARK else COLOR_LIGHT_BORDER))  # Initial separator

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # Create panels (views)
        self.create_jobs_panel()
        self.create_cluster_panel()
        self.create_settings_panel()

        # --- Initialization ---
        self.update_nav_styles(self.nav_buttons["Jobs"])  # Set initial active nav
        self.stacked_widget.setCurrentIndex(0)
        self.setup_refresh_timer()
        self.refresh_all()  # Initial data load
        self.set_connection_status(self.slurm_connection.is_connected())

    def set_connection_status(self, connected: bool, connecting=False):
        if connecting:
            loading_movie = QMovie("/home/nicola/Desktop/slurm_gui/src_static/loading.gif")
            loading_movie.setScaledSize(QSize(32, 32))
            loading_movie.start()
            self.connection_status.setMovie(loading_movie)
            self.connection_status.setToolTip("Connecting...")
            self.connection_status.setStyleSheet("""
                QPushButton#statusButton {
                    background-color: #9e9e9e;
                    color: white;
                    border-radius: 5px;
                    font-weight: bold;
                    padding: 6px 12px;
                }
            """)

            return

        if connected:
            self.connection_status.setToolTip("Connected")
            self.connection_status.setPixmap(
                QIcon("/home/nicola/Desktop/slurm_gui/src_static/good_connection.png").pixmap(QSize(32, 32)))
            self.connection_status.setStyleSheet("""
                QPushButton#statusButton {
                    background-color: #4caf50;
                    color: white;
                    border-radius: 5px;
                    font-weight: bold;
                    padding: 6px 12px;
                }
            """)
        else:
            self.connection_status.setToolTip("Disconnected")
            self.connection_status.setPixmap(
                QIcon("/home/nicola/Desktop/slurm_gui/src_static/bad_connection.png").pixmap(QSize(32, 32)))
            self.connection_status.setStyleSheet("""
                QPushButton#statusButton {
                    background-color: #f44336;
                    color: white;
                    border-radius: 5px;
                    font-weight: bold;
                    padding: 6px 12px;
                }
            """)

    def setup_refresh_timer(self):
        """Sets up the timer for automatic data refreshing."""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_all)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)

    def refresh_all(self):
        """Refreshes data for all relevant panels."""
        print("Refreshing all data...")
        self.refresh_job_status()
        self.refresh_cluster_status()
        self.set_connection_status(self.slurm_connection.is_connected())

    # --- Theme Handling ---
    def change_theme(self, theme_name):
        """Applies the selected theme stylesheet."""
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.setStyleSheet(self.themes[theme_name])
            # Update separator color based on theme
            separator_color = COLOR_DARK_BORDER if self.current_theme == THEME_DARK else COLOR_LIGHT_BORDER
            # Find and update the main separator (assuming it's the first QFrame after nav)
            for i in range(self.main_layout.count()):
                widget = self.main_layout.itemAt(i).widget()
                if isinstance(widget, QFrame) and widget.frameShape() == QFrame.Shape.HLine:
                    widget.setStyleSheet(f"background-color: {separator_color};")
                    break
            self.update_nav_styles()  # Update nav styles to reflect theme change
        else:
            print(f"Error: Theme '{theme_name}' not found.")

    # --- Navigation Bar ---
    def create_navigation_bar(self):
        """Creates the top navigation bar with logo, buttons, and search."""
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)  # No margins for the nav layout itself
        nav_layout.setSpacing(10)

        # Logo
        logo_label = QLabel()  # Simple Text Logo
        # logo_label.setObjectName("logoLabel")
        logo_label.setFixedSize(35, 35)  # Slightly larger
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(logo_label)
        pixmap = QPixmap("/home/nicola/Desktop/slurm_gui/src_static/logo.png")  # Use .svg or .ico if needed
        scaled_pixmap = pixmap.scaled(35, 35, Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        logo_label.setPixmap(scaled_pixmap)

        # logo_label.setWindowIconText(QIcon("/home/nicola/Desktop/slurm_gui/src_static/logo.png"))

        nav_layout.addSpacing(15)

        # Navigation buttons
        button_names = ["Jobs", "Cluster Status", "Settings"]
        for i, name in enumerate(button_names):
            btn = QPushButton(name)
            btn.setObjectName("navButton")  # Use object name for styling
            btn.setCheckable(True)  # Make buttons checkable for active state
            btn.clicked.connect(lambda checked, index=i, button=btn: self.switch_panel(index, button))
            nav_layout.addWidget(btn)
            self.nav_buttons[name] = btn  # Store button reference

        nav_layout.addStretch()

        # User controls (Example: Search)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search jobs...")
        self.search_input.setFixedWidth(250)  # Wider search
        self.search_input.textChanged.connect(self.filter_jobs)  # Connect search
        nav_layout.addWidget(self.search_input)

        self.connection_status = ClickableLabel(" Connection status...")
        self.connection_status.setObjectName("statusButton")  # Use object name for styling
        self.connection_status.setPixmap(
            QPixmap("/home/nicola/Desktop/slurm_gui/src_static/cloud_off_24dp_EA3323_FILL0_wght400_GRAD0_opsz24.png"))
        self.connection_status.clicked.connect(self.update_connection_setting)
        nav_layout.addWidget(self.connection_status)

        self.main_layout.addWidget(nav_widget)

    def switch_panel(self, index, clicked_button):
        """Switches the visible panel in the QStackedWidget."""
        self.stacked_widget.setCurrentIndex(index)
        self.update_nav_styles(clicked_button)

    def update_nav_styles(self, active_button=None):
        """Updates the visual style of navigation buttons to show the active one."""
        if active_button is None:  # Find the currently active button if none provided
            current_index = self.stacked_widget.currentIndex()
            button_list = list(self.nav_buttons.values())
            if 0 <= current_index < len(button_list):
                active_button = button_list[current_index]

        for name, btn in self.nav_buttons.items():
            if btn == active_button:
                btn.setObjectName("navButtonActive")  # Active style
                btn.setChecked(True)
            else:
                btn.setObjectName("navButton")  # Normal style
                btn.setChecked(False)
            # Re-apply stylesheet to update appearance based on object name
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # --- Panel Creation Methods ---
    def create_jobs_panel(self):
        """Creates the main panel for submitting and viewing jobs."""
        jobs_panel = QWidget()
        jobs_layout = QVBoxLayout(jobs_panel, spacing=15)
        # --- Job Submission Section ---
        jobs_layout.addWidget(self._create_job_submission_group())
        jobs_layout.addWidget(create_separator(color=COLOR_DARK_BORDER if self.current_theme ==
                              THEME_DARK else COLOR_LIGHT_BORDER))
        # --- Job List Section ---
        jobs_layout.addWidget(self._create_job_list_group())
        jobs_layout.addStretch()
        self.stacked_widget.addWidget(jobs_panel)

    def _create_job_submission_group(self):
        """Helper to create the 'Submit SLURM Job' group box."""
        group = QGroupBox("Submit SLURM Job")
        layout = QFormLayout(group)
        layout.setSpacing(10)  # Spacing within the form
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)  # Allow fields to expand

        # Job Name
        self.job_name_input = QLineEdit()
        self.job_name_input.setPlaceholderText("e.g., analysis_run_1")
        layout.addRow("Job Name:", self.job_name_input)

        # Script File
        self.script_path_input = QLineEdit()
        self.script_path_input.setPlaceholderText("Path to your .sh script")
        browse_script_btn = QPushButton("Browse...")
        browse_script_btn.clicked.connect(self.browse_script)
        script_layout = QHBoxLayout()
        script_layout.addWidget(self.script_path_input)
        script_layout.addWidget(browse_script_btn)
        layout.addRow("Script File:", script_layout)

        # --- Parameters Sub-Section ---
        params_widget = QWidget()
        parameters_layout = QHBoxLayout(params_widget)
        parameters_layout.setContentsMargins(0, 0, 0, 0)
        parameters_layout.setSpacing(20)

        # Left column
        params_left_layout = QFormLayout()
        self.partition_combo = QComboBox()
        self.partition_combo.addItems(["compute", "gpu", "bigmem", "debug"])  # TODO: Populate dynamically?
        params_left_layout.addRow("Partition:", self.partition_combo)
        self.nodes_spin = QSpinBox()
        self.nodes_spin.setMinimum(1)
        self.nodes_spin.setMaximum(128)  # Increased max
        self.nodes_spin.setValue(DEFAULT_NODES)
        params_left_layout.addRow("Nodes:", self.nodes_spin)
        self.tasks_spin = QSpinBox()
        self.tasks_spin.setMinimum(1)
        self.tasks_spin.setMaximum(256)  # Increased max
        self.tasks_spin.setValue(DEFAULT_TASKS)
        params_left_layout.addRow("Tasks per Node:", self.tasks_spin)  # Clarified label
        parameters_layout.addLayout(params_left_layout)

        # Right column
        params_right_layout = QFormLayout()
        self.memory_input = QLineEdit(DEFAULT_MEMORY)
        self.memory_input.setPlaceholderText("e.g., 4G, 500M")
        params_right_layout.addRow("Memory per Node:", self.memory_input)  # Clarified label
        self.time_input = QLineEdit(DEFAULT_TIME)
        self.time_input.setPlaceholderText("HH:MM:SS")
        params_right_layout.addRow("Time Limit:", self.time_input)
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Optional: your@email.com")
        params_right_layout.addRow("Email Notify:", self.email_input)
        parameters_layout.addLayout(params_right_layout)

        layout.addRow("Parameters:", params_widget)
        # --- End Parameters Sub-Section ---

        # Additional SLURM options
        self.additional_options = QTextEdit()
        self.additional_options.setPlaceholderText("Enter additional SLURM directives (e.g., --gres=gpu:1)")
        self.additional_options.setMaximumHeight(100)
        layout.addRow("Additional Options:", self.additional_options)

        # Submit button
        submit_btn = QPushButton("Submit Job")
        submit_btn.setObjectName(BTN_GREEN)
        submit_btn.setIcon(QIcon())  # Placeholder for icon
        submit_btn.clicked.connect(self.submit_job)
        submit_layout = QHBoxLayout()
        submit_layout.addStretch()
        submit_layout.addWidget(submit_btn)
        layout.addRow("", submit_layout)  # Add button row

        return group

    def _create_job_list_group(self):
        """Helper to create the 'My SLURM Jobs' group box."""
        group = QGroupBox("My SLURM Jobs")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        # Table header and refresh button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        # Removed the label, groupbox title is enough
        header_layout.addStretch()
        refresh_btn = QPushButton("Refresh List")
        refresh_btn.setIcon(QIcon())  # Placeholder for icon
        refresh_btn.clicked.connect(self.refresh_job_status)
        header_layout.addWidget(refresh_btn)
        layout.addLayout(header_layout)

        # Job table
        self.jobs_table = QTableWidget()
        self.jobs_table.setColumnCount(7)
        self.jobs_table.setHorizontalHeaderLabels(
            ["Job ID", "Name", "Partition", "Status", "Time Used", "Nodes", "Actions"])
        self.jobs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)  # Select whole row
        self.jobs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Read-only
        # self.jobs_table.setAlternatingRowColors(True)  # Improves readability
        self.jobs_table.verticalHeader().setVisible(False)  # Hide row numbers

        header = self.jobs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Name takes available space
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Actions fixed size

        layout.addWidget(self.jobs_table)
        return group

    def create_cluster_panel(self):
        """Creates the panel displaying detailed cluster node status using a table."""
        cluster_panel = QWidget()
        cluster_layout = QVBoxLayout(cluster_panel)
        cluster_layout.setSpacing(15)
        cluster_layout.setContentsMargins(15, 15, 15, 15)  # Consistent margins

        # --- Header ---
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        cluster_label = QLabel("Cluster Node Status")
        cluster_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(cluster_label)
        header_layout.addStretch()
        refresh_cluster_btn = QPushButton("Refresh Status")
        # Add an icon if desired: refresh_cluster_btn.setIcon(QIcon("path/to/refresh_icon.png"))
        # The refresh logic itself will be implemented later by the user
        # refresh_cluster_btn.clicked.connect(self.refresh_cluster_status_detailed) # Connect to a future refresh method
        refresh_cluster_btn.setToolTip("Refresh functionality to be implemented later.")
        header_layout.addWidget(refresh_cluster_btn)
        cluster_layout.addLayout(header_layout)

        # --- Node Information Table ---
        node_info_group = QGroupBox("Node Details")
        node_info_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        node_info_layout = QVBoxLayout(node_info_group)

        self.nodes_table = QTableWidget()
        # Define columns based on expected keys from _fetch_nodes_infos()
        # Adjust these based on the actual keys available
        self.node_table_headers = [
            "NodeName", "State", "Partitions", "CPULoad",
            "AllocCPUs", "TotalCPUs", "RealMemory", "AllocMem",
            "FreeMem", "Features", "GRES", "Reason"
        ]
        self.nodes_table.setColumnCount(len(self.node_table_headers))
        self.nodes_table.setHorizontalHeaderLabels(self.node_table_headers)

        self.nodes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.nodes_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Read-only
        self.nodes_table.setSortingEnabled(True)  # Allow sorting by column
        self.nodes_table.verticalHeader().setVisible(False)  # Hide row numbers
        # self.nodes_table.setAlternatingRowColors(True) # Optional: Improves readability

        # --- Column Resizing ---
        header = self.nodes_table.horizontalHeader()
        # Resize specific columns to content, stretch others
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)  # NodeName
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # State
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)  # Partitions
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # CPULoad
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # AllocCPUs
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # TotalCPUs
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # RealMemory
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # AllocMem
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  # FreeMem
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)  # Features (can be long)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)  # GRES (can be long)
        header.setSectionResizeMode(11, QHeaderView.ResizeMode.Stretch)  # Reason (can be long)
        # Adjust initial widths if needed
        self.nodes_table.setColumnWidth(0, 120)  # NodeName initial width
        self.nodes_table.setColumnWidth(2, 100)  # Partitions initial width

        node_info_layout.addWidget(self.nodes_table)
        # Make the table expand to fill available space
        cluster_layout.addWidget(node_info_group, 1)  # The '1' makes this section expand

        # --- Placeholder for Initial Data Load (or call refresh method) ---
        # You would call a method here to fetch and populate the table initially.
        # For now, it's just set up.
        self.populate_nodes_table()  # Example call to a future population method

        # --- (Optional) Add Overall Stats Section ---
        # You could add a summary section below the table if needed, similar to before.
        # stats_group = QGroupBox("Overall Statistics")
        # ... (add labels for total nodes, idle, alloc, down etc.) ...
        # cluster_layout.addWidget(stats_group)

        # Add the main panel widget to the stacked widget
        self.stacked_widget.addWidget(cluster_panel)

    def populate_nodes_table(self):
        """
        Placeholder method to populate the nodes table.
        (The actual data fetching and population logic will be added later)
        """
        print("Fetching node data (implementation pending)...")
        try:
            # --- Fetch data ---
            # This is where you'll call your function
            # nodes_data = self.slurm_connection._fetch_nodes_infos()
            # --- Mock Data for Demonstration ---
            nodes_data = [
                {'NodeName': 'node01', 'State': 'IDLE', 'Partitions': 'compute', 'CPULoad': '0.10', 'AllocCPUs': '0', 'TotalCPUs': '32',
                    'RealMemory': '128000', 'AllocMem': '0', 'FreeMem': '127500', 'Features': 'intel,skylake', 'GRES': 'gpu:tesla:2', 'Reason': 'none'},
                {'NodeName': 'node02', 'State': 'ALLOCATED', 'Partitions': 'compute', 'CPULoad': '28.50', 'AllocCPUs': '32', 'TotalCPUs': '32',
                    'RealMemory': '128000', 'AllocMem': '100000', 'FreeMem': '25000', 'Features': 'intel,skylake', 'GRES': 'gpu:tesla:2', 'Reason': 'none'},
                {'NodeName': 'node03', 'State': 'MIXED', 'Partitions': 'compute', 'CPULoad': '15.00', 'AllocCPUs': '16', 'TotalCPUs': '32',
                    'RealMemory': '128000', 'AllocMem': '64000', 'FreeMem': '63000', 'Features': 'intel,skylake', 'GRES': 'gpu:tesla:2', 'Reason': 'none'},
                {'NodeName': 'node04', 'State': 'DOWN', 'Partitions': 'compute', 'CPULoad': 'N/A', 'AllocCPUs': '0', 'TotalCPUs': '32',
                    'RealMemory': '128000', 'AllocMem': '0', 'FreeMem': 'N/A', 'Features': 'intel,skylake', 'GRES': 'gpu:tesla:2', 'Reason': 'Not responding'},
                {'NodeName': 'gpu01', 'State': 'IDLE', 'Partitions': 'gpu', 'CPULoad': '0.50', 'AllocCPUs': '0', 'TotalCPUs': '64',
                    'RealMemory': '256000', 'AllocMem': '0', 'FreeMem': '255000', 'Features': 'amd,epyc,a100', 'GRES': 'gpu:a100:4', 'Reason': 'none'},
            ]
            # --- End Mock Data ---

            if not nodes_data:
                print("No node data received.")
                self.nodes_table.setRowCount(0)
                return

            self.nodes_table.setSortingEnabled(False)  # Disable sorting during population
            self.nodes_table.setRowCount(len(nodes_data))

            # --- Color mapping for states (adjust as needed) ---
            state_colors = {
                "IDLE": QColor(COLOR_GREEN),
                "ALLOCATED": QColor(COLOR_BLUE),
                "MIXED": QColor(COLOR_ORANGE),  # Or a different color for mixed
                "DOWN": QColor(COLOR_RED),
                "DRAIN": QColor(COLOR_ORANGE),
                "MAINT": QColor(COLOR_ORANGE),
                "UNKNOWN": QColor(COLOR_GRAY),
                # Add other SLURM states as needed
            }
            default_color = QColor(COLOR_DARK_FG if self.current_theme == THEME_DARK else COLOR_LIGHT_FG)
            state_column_index = self.node_table_headers.index("State")  # Find State column index

            for row, node_info in enumerate(nodes_data):
                node_state = node_info.get("State", "UNKNOWN").upper().split(
                    '+')[0]  # Get base state (e.g., ignore +DRAINING)

                for col, header in enumerate(self.node_table_headers):
                    value = str(node_info.get(header, "N/A"))  # Get value or N/A
                    item = QTableWidgetItem(value)

                    # --- Apply State Coloring to the entire row (optional) ---
                    # state_color = state_colors.get(node_state, default_color)
                    # item.setBackground(state_color.lighter(180) if self.current_theme == THEME_DARK else state_color.lighter(110)) # Subtle background tint
                    # item.setForeground(default_color) # Ensure text is readable

                    # --- Or Apply Coloring only to the State cell ---
                    if col == state_column_index:
                        state_color = state_colors.get(node_state, default_color)
                        item.setForeground(state_color)
                        # Make state bold
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)

                    # --- Alignment for numeric columns (example) ---
                    if header in ["CPULoad", "AllocCPUs", "TotalCPUs", "RealMemory", "AllocMem", "FreeMem"]:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                    self.nodes_table.setItem(row, col, item)

            self.nodes_table.setSortingEnabled(True)  # Re-enable sorting

        except Exception as e:
            print(f"Error populating nodes table: {e}")
            # Optionally display an error message in the UI
            self.nodes_table.setRowCount(0)  # Clear table on error

    # You will need a method like this, connected to the refresh button
    # def refresh_cluster_status_detailed(self):
    #    print("Refreshing detailed cluster status...")
    #    self.populate_nodes_table() # Call the population method

    # def create_cluster_panel(self):
    #     """Creates the panel displaying cluster status using a node grid."""
    #     self.slurm_connection._fetch_nodes_infos()
    #     cluster_panel = QWidget()
    #     cluster_layout = QVBoxLayout(cluster_panel)
    #     cluster_layout.setSpacing(15)

    #     # --- Header ---
    #     header_layout = QHBoxLayout()
    #     header_layout.setContentsMargins(0, 0, 0, 0)
    #     cluster_label = QLabel("Cluster Node Status")  # Changed title
    #     cluster_label.setStyleSheet("font-size: 16px; font-weight: bold;")  # Adjusted size
    #     header_layout.addWidget(cluster_label)
    #     header_layout.addStretch()
    #     refresh_cluster_btn = QPushButton("Refresh Status")
    #     # refresh_cluster_btn.setIcon(QIcon()) # Placeholder icon
    #     refresh_cluster_btn.clicked.connect(self.refresh_cluster_status)
    #     header_layout.addWidget(refresh_cluster_btn)
    #     cluster_layout.addLayout(header_layout)

    #     # --- Legend ---
    #     legend_layout = QHBoxLayout()
    #     legend_layout.setSpacing(10)
    #     legend_layout.addWidget(QLabel("Legend:"))

    #     def create_legend_item(color, text):
    #         item_layout = QHBoxLayout()
    #         color_label = QLabel()
    #         color_label.setFixedSize(15, 15)
    #         color_label.setStyleSheet(f"background-color: {color}; border: 1px solid gray;")
    #         item_layout.addWidget(color_label)
    #         item_layout.addWidget(QLabel(text))
    #         widget = QWidget()
    #         widget.setLayout(item_layout)
    #         return widget

    #     legend_layout.addWidget(create_legend_item(COLOR_GREEN, NODE_STATE_IDLE))
    #     legend_layout.addWidget(create_legend_item(COLOR_BLUE, NODE_STATE_ALLOC))
    #     legend_layout.addWidget(create_legend_item(COLOR_ORANGE, NODE_STATE_DRAIN))
    #     legend_layout.addWidget(create_legend_item(COLOR_RED, NODE_STATE_DOWN))
    #     legend_layout.addWidget(create_legend_item(COLOR_GRAY, NODE_STATE_UNKNOWN))
    #     legend_layout.addStretch()
    #     cluster_layout.addLayout(legend_layout)

    #     # --- Node Grid Group ---
    #     node_grid_group = QGroupBox("Node Occupancy")
    #     node_grid_outer_layout = QVBoxLayout(node_grid_group)  # Use QVBoxLayout to contain the grid

    #     # The grid layout itself
    #     self.node_grid_layout = QGridLayout()
    #     self.node_grid_layout.setSpacing(4)  # Small spacing between nodes

    #     # We will populate this grid in refresh_cluster_status
    #     # Add the grid layout to the group box layout
    #     node_grid_outer_layout.addLayout(self.node_grid_layout)
    #     node_grid_outer_layout.addStretch()  # Allow grid to be at the top

    #     cluster_layout.addWidget(node_grid_group)

    #     # --- Overall Stats (Optional - can be kept or removed) ---
    #     # You might want to keep a summary section
    #     stats_group = QGroupBox("Overall Statistics")
    #     stats_layout = QFormLayout(stats_group)
    #     self.total_nodes_label = QLabel("N/A")
    #     self.idle_nodes_label = QLabel("N/A")
    #     self.alloc_nodes_label = QLabel("N/A")
    #     self.down_nodes_label = QLabel("N/A")
    #     stats_layout.addRow("Total Nodes:", self.total_nodes_label)
    #     stats_layout.addRow("Idle Nodes:", self.idle_nodes_label)
    #     stats_layout.addRow("Allocated Nodes:", self.alloc_nodes_label)
    #     stats_layout.addRow("Down/Drained Nodes:", self.down_nodes_label)
    #     cluster_layout.addWidget(stats_group)
    #     # --- End Optional Stats ---

    #     cluster_layout.addStretch()  # Pushes content upwards
    #     self.stacked_widget.addWidget(cluster_panel)
    #     self.node_widgets = {}  # Dictionary to hold references to node labels {node_name: QLabel}

    # def create_cluster_panel(self):
    #     """Creates the panel displaying cluster status information."""
    #     cluster_panel = QWidget()
    #     cluster_layout = QVBoxLayout(cluster_panel)
    #     cluster_layout.setSpacing(15)

    #     # Header with refresh button
    #     header_layout = QHBoxLayout()
    #     header_layout.setContentsMargins(0, 0, 0, 0)
    #     cluster_label = QLabel("Cluster Status Overview")
    #     cluster_label.setStyleSheet("font-size: 18px; font-weight: bold;")  # Slightly smaller title
    #     header_layout.addWidget(cluster_label)
    #     header_layout.addStretch()
    #     refresh_cluster_btn = QPushButton("Refresh Status")
    #     refresh_cluster_btn.setIcon(QIcon())  # Placeholder icon
    #     refresh_cluster_btn.clicked.connect(self.refresh_cluster_status)
    #     header_layout.addWidget(refresh_cluster_btn)
    #     cluster_layout.addLayout(header_layout)

    #     # --- Cluster Overview Group ---
    #     overview_group = QGroupBox("Real-time Usage")
    #     overview_layout = QVBoxLayout(overview_group)
    #     overview_layout.setSpacing(15)

    #     # Cluster stats grid
    #     stats_layout = QHBoxLayout()
    #     stats_layout.setSpacing(20)  # Space between stats

    #     # Helper to create stat widgets
    #     def create_stat_widget(label_text, value_id, object_name=None):
    #         widget = QWidget()
    #         layout = QVBoxLayout(widget)
    #         layout.setContentsMargins(0, 0, 0, 0)
    #         label = QLabel(label_text)
    #         label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    #         value = QLabel("N/A")  # Default value
    #         value.setObjectName("clusterStatValue")
    #         if object_name:
    #             value.setProperty("statusColor", object_name)  # Custom property for styling if needed
    #             value.setObjectName(f"clusterStatValue{object_name}")  # Specific object name for styling
    #         value.setAlignment(Qt.AlignmentFlag.AlignCenter)
    #         layout.addWidget(label)
    #         layout.addWidget(value)
    #         setattr(self, value_id, value)  # Store value label reference
    #         return widget

    #     stats_layout.addWidget(create_stat_widget("Total Nodes", "total_nodes_value"))
    #     stats_layout.addWidget(create_stat_widget("Available Nodes", "avail_nodes_value", "Avail"))
    #     stats_layout.addWidget(create_stat_widget("Running Jobs", "running_jobs_value", "Running"))
    #     stats_layout.addWidget(create_stat_widget("Pending Jobs", "pending_jobs_value", "Pending"))

    #     overview_layout.addLayout(stats_layout)

    #     # Usage bars
    #     usage_layout = QFormLayout()  # Use form layout for better alignment
    #     usage_layout.setSpacing(10)

    #     # Helper to create progress bar row
    #     def create_progress_row(label_text, progress_id, percent_id):
    #         layout = QHBoxLayout()
    #         layout.setContentsMargins(0, 0, 0, 0)
    #         progress = QProgressBar()
    #         progress.setValue(0)
    #         progress.setTextVisible(False)  # Show percentage in separate label
    #         percent_label = QLabel("0%")
    #         percent_label.setFixedWidth(40)  # Fixed width for alignment
    #         layout.addWidget(progress)
    #         layout.addWidget(percent_label)
    #         setattr(self, progress_id, progress)
    #         setattr(self, percent_id, percent_label)
    #         return label_text, layout

    #     usage_layout.addRow(*create_progress_row("CPU Usage:", "cpu_progress", "cpu_percent_label"))
    #     usage_layout.addRow(*create_progress_row("Memory Usage:", "mem_progress", "mem_percent_label"))
    #     usage_layout.addRow(*create_progress_row("GPU Usage:", "gpu_progress", "gpu_percent_label"))

    #     overview_layout.addLayout(usage_layout)
    #     cluster_layout.addWidget(overview_group)

    #     # --- Partition Status Group ---
    #     partitions_group = QGroupBox("Partition Status")
    #     partitions_layout = QVBoxLayout(partitions_group)

    #     self.partitions_table = QTableWidget()
    #     self.partitions_table.setColumnCount(5)
    #     self.partitions_table.setHorizontalHeaderLabels(
    #         ["Partition", "Available", "Total", "Usage %", "State"])
    #     self.partitions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    #     self.partitions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    #     # self.partitions_table.setAlternatingRowColors(True)
    #     self.partitions_table.verticalHeader().setVisible(False)

    #     header = self.partitions_table.horizontalHeader()
    #     header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Partition name takes space
    #     for i in range(1, 5):
    #         header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)  # Other columns fit content

    #     partitions_layout.addWidget(self.partitions_table)
    #     cluster_layout.addWidget(partitions_group)

    #     cluster_layout.addStretch()
    #     self.stacked_widget.addWidget(cluster_panel)

    def create_settings_panel(self):
        """Creates the panel for application settings."""
        settings_panel = QWidget()
        settings_layout = QVBoxLayout(settings_panel)
        settings_layout.setSpacing(20)
        settings_layout.setContentsMargins(25, 25, 25, 25)  # More padding for settings

        # Title
        settings_label = QLabel("Application Settings")
        settings_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        settings_layout.addWidget(settings_label)

        # --- Appearance Section ---
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(self.themes.keys())
        self.theme_combo.setCurrentText(self.current_theme)
        self.theme_combo.currentTextChanged.connect(self.change_theme)
        appearance_layout.addRow("UI Theme:", self.theme_combo)
        settings_layout.addWidget(appearance_group)

        # --- SLURM Connection Settings ---
        connection_group = QGroupBox("SLURM Connection (Example)")
        connection_group.setMinimumHeight(150)
        connection_layout = QFormLayout(connection_group)
        self.cluster_address = QLineEdit(self.slurm_connection.host)
        connection_layout.addRow("Cluster Address:", self.cluster_address)
        # self.username = QLineEdit(os.environ.get("USER", self.slurm_connection.use))
        self.username = QLineEdit(self.slurm_connection.user)
        connection_layout.addRow("Username:", self.username)

        # Replace SSH key with password field
        self.password = QLineEdit(self.slurm_connection.password)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)  # Correct way to set password mode
        connection_layout.addRow("Password:", self.password)

        connection_settings_btn = QPushButton("Save connection settings")
        connection_settings_btn.setObjectName(BTN_GREEN)
        connection_settings_btn.clicked.connect(self.update_connection_setting)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(connection_settings_btn)
        connection_layout.addRow(button_layout)

        # self.ssh_key_path = QLineEdit(os.path.expanduser("~/.ssh/id_rsa"))
        # browse_ssh_btn = QPushButton("Browse...")
        # browse_ssh_btn.clicked.connect(self.browse_ssh_key)
        # ssh_key_layout = QHBoxLayout()
        # ssh_key_layout.addWidget(self.ssh_key_path)
        # ssh_key_layout.addWidget(browse_ssh_btn)
        # connection_layout.addRow("SSH Key:", ssh_key_layout)
        settings_layout.addWidget(connection_group)

        # --- Notifications Section ---
        notifications_group = QGroupBox("Notifications")
        notifications_layout = QVBoxLayout(notifications_group)
        notifications_layout.setSpacing(10)
        self.desktop_notify_check = QCheckBox("Enable Desktop Notifications")
        self.desktop_notify_check.setChecked(True)
        self.email_notify_check = QCheckBox("Send Email Notifications (if email provided in job)")
        self.email_notify_check.setChecked(True)
        self.sound_notify_check = QCheckBox("Play Sound on Job Completion/Failure")
        notifications_layout.addWidget(self.desktop_notify_check)
        notifications_layout.addWidget(self.email_notify_check)
        notifications_layout.addWidget(self.sound_notify_check)
        settings_layout.addWidget(notifications_group)

        # --- Job Defaults Section (Example - not fully implemented) ---
        defaults_group = QGroupBox("Default Job Parameters")
        defaults_layout = QFormLayout(defaults_group)
        self.default_partition_combo = QComboBox()
        self.default_partition_combo.addItems(["compute", "gpu", "bigmem", "debug"])
        self.default_partition_combo.setCurrentText(DEFAULT_PARTITION)
        defaults_layout.addRow("Default Partition:", self.default_partition_combo)
        self.default_memory_input = QLineEdit(DEFAULT_MEMORY)
        defaults_layout.addRow("Default Memory:", self.default_memory_input)
        settings_layout.addWidget(defaults_group)

        # --- Save Button ---
        save_button = QPushButton("Save Settings")
        save_button.setObjectName(BTN_GREEN)
        save_button.setIcon(QIcon())  # Placeholder icon
        save_button.clicked.connect(self.save_settings)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        settings_layout.addLayout(button_layout)

        settings_layout.addStretch()  # Pushes settings to the top
        self.stacked_widget.addWidget(settings_panel)

    # --- Action & Data Methods ---

    def update_connection_setting(self):
        print("Updateding connection settings...")

        self.set_connection_status(None, connecting=True)
        # def update_fn_():

        #     self.slurm_connection.update_credentials_and_reconnect(self.username.text(),
        #                                                            self.cluster_address.text(),
        #                                                            self.password.text())

        thread = threading.Thread(target=self.slurm_connection.update_credentials_and_reconnect, args=(
            self.username.text(),
            self.cluster_address.text(),
            self.password.text()
        ))

        thread.start()

        # self.slurm_connection.update_credentials_and_reconnect(
        #     new_user=self.username.text(),
        #     new_host=self.cluster_address.text(),
        #     new_psw=self.password.text()
        # )
        # self.set_connection_status(self.slurm_connection.is_connected())

    def filter_jobs(self, text):
        """Filters the jobs table based on the search input."""
        search_term = text.lower().strip()
        for row in range(self.jobs_table.rowCount()):
            job_id_item = self.jobs_table.item(row, 0)
            job_name_item = self.jobs_table.item(row, 1)
            match = False
            if job_id_item and search_term in job_id_item.text().lower():
                match = True
            elif job_name_item and search_term in job_name_item.text().lower():
                match = True

            self.jobs_table.setRowHidden(row, not match)

    def browse_script(self):
        """Opens a file dialog to select a SLURM script file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select SLURM Script File", "", "Shell Scripts (*.sh);;All Files (*)")
        if file_path:
            self.script_path_input.setText(file_path)

    def browse_ssh_key(self):
        """Opens a file dialog to select an SSH key file."""
        # Be cautious with security when handling private keys
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Private Key File", os.path.expanduser("~/.ssh"), "Key Files (*.pem *.key id_*);;All Files (*)")
        if file_path:
            self.ssh_key_path.setText(file_path)

    def submit_job(self):
        """Validates input and constructs the sbatch command (demo)."""
        job_name = self.job_name_input.text().strip()
        script_path = self.script_path_input.text().strip()

        # --- Input Validation ---
        if not job_name:
            show_message(self, "Input Error", "Job Name cannot be empty.", QMessageBox.Icon.Warning)
            self.job_name_input.setFocus()
            return
        if not script_path:
            show_message(self, "Input Error", "Script File path cannot be empty.", QMessageBox.Icon.Warning)
            self.script_path_input.setFocus()
            return
        if not os.path.exists(script_path):
            show_message(self, "Input Error", f"Script file not found:\n{script_path}", QMessageBox.Icon.Warning)
            self.script_path_input.setFocus()
            return
        # Add more validation for time, memory format etc. if needed

        # --- Build sbatch command (Example) ---
        sbatch_cmd = ["sbatch"]
        sbatch_cmd.extend(["-J", job_name])
        sbatch_cmd.extend(["-p", self.partition_combo.currentText()])
        sbatch_cmd.extend(["-N", str(self.nodes_spin.value())])
        sbatch_cmd.extend(["-n", str(self.tasks_spin.value())])  # tasks per node
        sbatch_cmd.extend(["--mem", self.memory_input.text()])
        sbatch_cmd.extend(["-t", self.time_input.text()])

        email = self.email_input.text().strip()
        if email:
            sbatch_cmd.extend(["--mail-user", email])
            sbatch_cmd.extend(["--mail-type", "ALL"])  # Notify on BEGIN, END, FAIL

        additional_opts = self.additional_options.toPlainText().strip()
        if additional_opts:
            # Basic split, might need more robust parsing for complex options
            for opt in additional_opts.split("\n"):
                opt_strip = opt.strip()
                if opt_strip:
                    sbatch_cmd.extend(opt_strip.split())  # Split option and value if needed

        sbatch_cmd.append(script_path)

        # --- Execute Command (Demo) ---
        command_str = " ".join(sbatch_cmd)
        print(f"Attempting to submit job with command:\n{command_str}")

        # ** In a real application, replace the print with subprocess execution **
        # try:
        #     # Consider using SSH if running remotely
        #     result = subprocess.run(sbatch_cmd, capture_output=True, text=True, check=True, timeout=10)
        #     output = result.stdout
        #     match = re.search(r'Submitted batch job (\d+)', output)
        #     if match:
        #         job_id = match.group(1)
        #         show_message(self, "Job Submitted", f"Job '{job_name}' submitted successfully.\nJob ID: {job_id}")
        #         self.clear_submission_form()
        #         self.refresh_job_status() # Refresh list immediately
        #     else:
        #         show_message(self, "Submission Info", f"Job submitted, but couldn't parse Job ID.\nOutput:\n{output}", QMessageBox.Icon.Information)
        #
        # except FileNotFoundError:
        #      show_message(self, "Error", "'sbatch' command not found. Is SLURM installed and in PATH?", QMessageBox.Icon.Critical)
        # except subprocess.CalledProcessError as e:
        #     show_message(self, "Submission Failed", f"Error submitting job:\n{e.stderr}", QMessageBox.Icon.Critical)
        # except subprocess.TimeoutExpired:
        #      show_message(self, "Error", "sbatch command timed out.", QMessageBox.Icon.Warning)
        # except Exception as e:
        #     show_message(self, "Error", f"An unexpected error occurred:\n{str(e)}", QMessageBox.Icon.Critical)

        # --- Demo Success ---
        show_message(self, "Job Submitted (Demo)",
                     f"Job '{job_name}' would be submitted.\nCommand (printed to console):\n{command_str}")
        self.clear_submission_form()
        # Simulate adding the job and refreshing
        self.refresh_job_status()

    def clear_submission_form(self):
        """Clears the input fields in the job submission form."""
        self.job_name_input.clear()
        self.script_path_input.clear()
        self.partition_combo.setCurrentIndex(0)  # Reset to first item
        self.nodes_spin.setValue(DEFAULT_NODES)
        self.tasks_spin.setValue(DEFAULT_TASKS)
        self.memory_input.setText(DEFAULT_MEMORY)
        self.time_input.setText(DEFAULT_TIME)
        self.email_input.clear()
        self.additional_options.clear()

    def populate_jobs_table(self, jobs_data):
        """Populates the jobs table with data."""
        self.jobs_table.setRowCount(0)  # Clear existing rows
        self.jobs_table.setSortingEnabled(False)  # Disable sorting during population

        for row, job in enumerate(jobs_data):
            self.jobs_table.insertRow(row)

            # --- Create Table Items ---
            item_id = QTableWidgetItem(job.get("id", "N/A"))
            item_name = QTableWidgetItem(job.get("name", "N/A"))
            item_partition = QTableWidgetItem(job.get("partition", "N/A"))
            item_status = QTableWidgetItem(job.get("status", "N/A"))
            item_time = QTableWidgetItem(job.get("time", "N/A"))
            item_nodes = QTableWidgetItem(job.get("nodes", "N/A"))

            # --- Status Coloring ---
            status = job.get("status", "").upper()
            if status == STATUS_RUNNING:
                item_status.setForeground(QColor(COLOR_GREEN))
            elif status == STATUS_PENDING:
                item_status.setForeground(QColor(COLOR_ORANGE))
            elif status == STATUS_COMPLETED:
                item_status.setForeground(QColor(COLOR_BLUE))
            elif status == STATUS_FAILED:
                item_status.setForeground(QColor(COLOR_RED))
            # Add more statuses (CANCELLED, TIMEOUT, etc.) if needed

            # --- Set Items in Table ---
            self.jobs_table.setItem(row, 0, item_id)
            self.jobs_table.setItem(row, 1, item_name)
            self.jobs_table.setItem(row, 2, item_partition)
            self.jobs_table.setItem(row, 3, item_status)
            self.jobs_table.setItem(row, 4, item_time)
            self.jobs_table.setItem(row, 5, item_nodes)

            # --- Action Buttons ---
            actions_widget = self._create_job_action_buttons(job.get("id"), status)
            self.jobs_table.setCellWidget(row, 6, actions_widget)

        self.jobs_table.setSortingEnabled(True)  # Re-enable sorting

    def _create_job_action_buttons(self, job_id, status):
        """Creates a widget containing action buttons for a job row."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center buttons

        # Details Button (Always show)
        details_btn = QPushButton("Details")
        details_btn.setObjectName(BTN_BLUE)
        details_btn.setFixedSize(70, 28)  # Consistent size
        if job_id:  # Only connect if job_id is valid
            details_btn.clicked.connect(lambda _, jid=job_id: self.show_job_details(jid))
        else:
            details_btn.setEnabled(False)
        layout.addWidget(details_btn)

        # Cancel Button (Only for Running/Pending)
        if status in [STATUS_RUNNING, STATUS_PENDING]:
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setObjectName(BTN_RED)
            cancel_btn.setFixedSize(70, 28)
            if job_id:
                cancel_btn.clicked.connect(lambda _, jid=job_id: self.cancel_job(jid))
            else:
                cancel_btn.setEnabled(False)
            layout.addWidget(cancel_btn)

        # Add other buttons like 'Resubmit', 'View Output' etc. here if needed

        return widget

    def cancel_job(self, job_id):
        """Handles the 'Cancel Job' action (demo)."""
        print(f"Attempting to cancel job {job_id}")
        # ** In a real application, run 'scancel job_id' **
        # try:
        #     subprocess.run(["scancel", job_id], check=True, capture_output=True, text=True)
        #     show_message(self, "Job Cancelled", f"Job {job_id} cancelled successfully.")
        #     self.refresh_job_status() # Refresh list
        # except Exception as e:
        #     show_message(self, "Error", f"Failed to cancel job {job_id}:\n{str(e)}", QMessageBox.Icon.Warning)

        # Demo
        show_message(self, "Cancel Job (Demo)", f"Would attempt to cancel job {job_id}.")
        # Simulate removal or status change
        self.refresh_job_status()

    def show_job_details(self, job_id):
        """Handles the 'Show Details' action (demo)."""
        print(f"Fetching details for job {job_id}")
        # ** In a real application, run 'scontrol show job job_id' and display output **
        # try:
        #     result = subprocess.run(["scontrol", "show", "job", job_id], check=True, capture_output=True, text=True, timeout=5)
        #     details = result.stdout
        #     # Display details in a new dialog or dedicated text area
        #     details_dialog = QMessageBox(self)
        #     details_dialog.setWindowTitle(f"Job Details: {job_id}")
        #     details_dialog.setTextFormat(Qt.TextFormat.PlainText) # Use PlainText for monospace/preformatted
        #     details_dialog.setText(details)
        #     details_dialog.setIcon(QMessageBox.Icon.Information)
        #     details_dialog.exec()
        # except Exception as e:
        #     show_message(self, "Error", f"Failed to get details for job {job_id}:\n{str(e)}", QMessageBox.Icon.Warning)

        # Demo
        demo_details = f"JobId={job_id} Name=some_job\nUserId=user(1001) GroupId=group(1001)\nPriority=100 Nice=0 Account=default QOS=normal\nJobState=RUNNING Reason=None Dependency=(null)\nTimeLimit=01:00:00 TimeLeft=00:45:12 SubmitTime=...\nStartTime=... EndTime=...\nPartition=compute NodeList=node01\nNumNodes=1 NumCPUs=4 Mem=4G\nWorkDir=/path/to/workdir\nStdOut=/path/to/output.log"
        details_dialog = QMessageBox(self)
        details_dialog.setWindowTitle(f"Job Details (Demo): {job_id}")
        details_dialog.setTextFormat(Qt.TextFormat.PlainText)
        details_dialog.setText(demo_details)
        details_dialog.setIcon(QMessageBox.Icon.Information)
        # Make the dialog wider for better readability
        details_dialog.layout().setColumnStretch(1, 1)  # Allow text area to expand
        details_dialog.exec()

    def refresh_job_status(self):
        """Refreshes the job list table (demo)."""
        print("Refreshing job status...")
        # ** In a real application, call squeue, parse output, and update table **
        # try:
        #    cmd = ["squeue", "-u", os.environ.get("USER"), "-o", "%i %j %P %T %M %D"] # Example format
        #    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        #    output_lines = result.stdout.strip().split('\n')
        #    headers = output_lines[0].split() # Assuming first line is header
        #    jobs_data = []
        #    for line in output_lines[1:]:
        #        # Parse line based on your squeue format
        #        parts = line.split() # Simple split, might need regex for complex names
        #        if len(parts) >= 6: # Basic check
        #             job = {"id": parts[0], "name": parts[1], "partition": parts[2],
        #                    "status": parts[3], "time": parts[4], "nodes": parts[5]}
        #             jobs_data.append(job)
        #    self.populate_jobs_table(jobs_data)
        # except Exception as e:
        #    print(f"Error refreshing job status: {e}")
        #    # Maybe show an error indicator in the UI

        # --- Demo Data ---
        sample_jobs = [
            {"id": "123456", "name": "RNA-seq_analysis_long_name_test", "partition": "compute",
             "status": STATUS_RUNNING, "time": "1:23:45", "nodes": "2"},
            {"id": "123457", "name": "protein_folding_sim", "partition": "gpu",
             "status": STATUS_PENDING, "time": "0:00:00", "nodes": "4"},
            {"id": "123458", "name": "genome_assembly", "partition": "bigmem",
             "status": STATUS_COMPLETED, "time": "5:37:12", "nodes": "1"},
            {"id": "123459", "name": "ml_training_job", "partition": "gpu",
             "status": STATUS_RUNNING, "time": "12:05:22", "nodes": "2"},
            {"id": "123460", "name": "failed_experiment", "partition": "debug",
             "status": STATUS_FAILED, "time": "0:01:15", "nodes": "1"},
        ]
        # Randomly change status for demo refresh effect
        for job in sample_jobs:
            if random.random() < 0.1 and job["status"] == STATUS_PENDING:
                job["status"] = STATUS_RUNNING
                job["time"] = "0:00:10"
            elif random.random() < 0.05 and job["status"] == STATUS_RUNNING:
                job["status"] = STATUS_COMPLETED
                job["time"] = f"{random.randint(1, 5)}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"

        self.populate_jobs_table(sample_jobs)
        self.filter_jobs(self.search_input.text())  # Re-apply filter after refresh

    def populate_partitions_table(self, partitions_data):
        """Populates the partitions table with data."""
        self.partitions_table.setRowCount(0)  # Clear table
        self.partitions_table.setSortingEnabled(False)

        for row, partition in enumerate(partitions_data):
            self.partitions_table.insertRow(row)

            # --- Create Items ---
            item_name = QTableWidgetItem(partition.get("name", "N/A"))
            item_avail = QTableWidgetItem(partition.get("avail", "N/A"))
            item_total = QTableWidgetItem(partition.get("total", "N/A"))
            item_usage = QTableWidgetItem(partition.get("usage", "N/A"))
            item_state = QTableWidgetItem(partition.get("state", "N/A"))

            # --- State Coloring ---
            state = partition.get("state", "").lower()
            if state == "up" or state == "idle" or state == "alloc":  # Consider different 'up' states
                item_state.setForeground(QColor(COLOR_GREEN))
            elif state == "down" or state == "drain":
                item_state.setForeground(QColor(COLOR_RED))
            else:
                item_state.setForeground(QColor(COLOR_ORANGE))  # Unknown/other state

            # Align numeric columns to the right
            for col_idx, item in enumerate([item_avail, item_total, item_usage]):
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.partitions_table.setItem(row, col_idx + 1, item)  # Offset by 1

            self.partitions_table.setItem(row, 0, item_name)
            self.partitions_table.setItem(row, 4, item_state)

        self.partitions_table.setSortingEnabled(True)

    def refresh_cluster_status(self):
        """Refreshes the cluster status widgets (demo)."""
        print("Refreshing cluster status...")
        # ** In a real application, call sinfo, scontrol show nodes, etc. parse output **
        # try:
        #    # Get partition info (sinfo)
        #    # Get node info (sinfo -N -o "%N %t %c %m %f")
        #    # Get job counts (squeue -t PD,R -h | wc -l)
        #    # Aggregate data
        # except Exception as e:
        #    print(f"Error refreshing cluster status: {e}")

        # --- Demo Data Update ---
        total_nodes = 64
        avail_nodes = random.randint(30, 55)
        running_jobs = random.randint(10, 20)
        pending_jobs = random.randint(5, 15)
        cpu_usage = random.randint(40, 85)
        mem_usage = random.randint(30, 70)
        gpu_usage = random.randint(50, 90)  # Assuming some GPUs exist

        # self.total_nodes_label.setText(str(total_nodes))
        # self.avail_nodes_value.setText(str(avail_nodes))
        # self.running_jobs_value.setText(str(running_jobs))
        # self.pending_jobs_value.setText(str(pending_jobs))

        # self.cpu_progress.setValue(cpu_usage)
        # self.cpu_percent_label.setText(f"{cpu_usage}%")
        # self.mem_progress.setValue(mem_usage)
        # self.mem_percent_label.setText(f"{mem_usage}%")
        # self.gpu_progress.setValue(gpu_usage)
        # self.gpu_percent_label.setText(f"{gpu_usage}%")

        # --- Demo Partition Data ---
        sample_partitions = [
            {"name": "compute", "avail": str(random.randint(20, 40)), "total": "48",
             "usage": f"{random.randint(50, 80)}%", "state": "up"},
            {"name": "gpu", "avail": str(random.randint(1, 6)), "total": "8",
             "usage": f"{random.randint(60, 95)}%", "state": "up"},
            {"name": "bigmem", "avail": str(random.randint(0, 4)), "total": "8",
             "usage": f"{random.randint(40, 60)}%", "state": "up"},
            {"name": "debug", "avail": str(random.randint(
                0, 2)), "total": "2", "usage": f"{random.randint(0, 10)}%", "state": random.choice(["up", "down", "idle"])},
        ]
        # self.populate_partitions_table(sample_partitions)

    def save_settings(self):
        """Saves the current settings (demo)."""
        # In a real app, save to a config file (e.g., JSON, INI, QSettings)
        print("--- Saving Settings (Demo) ---")
        print(f"Theme: {self.theme_combo.currentText()}")
        print(f"Cluster Address: {self.cluster_address.text()}")
        print(f"Username: {self.username.text()}")
        print(f"SSH Key Path: {self.ssh_key_path.text()}")
        print(f"Desktop Notifications: {self.desktop_notify_check.isChecked()}")
        print(f"Email Notifications: {self.email_notify_check.isChecked()}")
        print(f"Sound Notifications: {self.sound_notify_check.isChecked()}")
        print(f"Default Partition: {self.default_partition_combo.currentText()}")
        print(f"Default Memory: {self.default_memory_input.text()}")
        print("-----------------------------")
        show_message(self, "Settings Saved", "Settings have been saved (demo).")

    def closeEvent(self, event):
        """Handles the window close event."""
        # Optional: Add confirmation dialog
        # reply = QMessageBox.question(self, 'Confirm Exit',
        #                              "Are you sure you want to exit?",
        #                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        #                              QMessageBox.StandardButton.No)
        # if reply == QMessageBox.StandardButton.Yes:
        #     event.accept()
        # else:
        #     event.ignore()
        print("Closing application.")
        event.accept()


# --- Main Execution ---
if __name__ == "__main__":
    # Enable high DPI scaling for better visuals on modern displays
    # QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    # QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # Apply a base font
    font = QFont("Inter", 10)  # Use Inter font if available, adjust size as needed
    app.setFont(font)

    window = SlurmJobManagerApp()
    window.show()
    sys.exit(app.exec())
