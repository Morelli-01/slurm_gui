from pathlib import Path
from modules.settings_widget import SettingsWidget
import sys, slurm_connection

from networkx import nodes
import threading
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QComboBox, QFrame, QSizePolicy, QStackedWidget, QFormLayout, QGroupBox,
    QTextEdit, QSpinBox, QFileDialog, QProgressBar, QMessageBox, QGridLayout, QScrollArea
)
from PyQt6.QtGui import QIcon, QColor, QPalette, QFont, QPixmap, QMovie
from PyQt6.QtCore import Qt, QSize, QTimer, QSettings
from utils import *
from modules.job_queue_widget import JobQueueWidget
import modules.cluster_status_widget as cluster_status_widget
from modules.defaults import *
# --- Constants ---
APP_TITLE = "SLURM Job Manager"
MIN_WIDTH = 1600
MIN_HEIGHT = 900
REFRESH_INTERVAL_MS = 5000  # 10 seconds

# Theme Keys


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


# --- Main Application Class ---


class SlurmJobManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.slurm_connection = slurm_connection.SlurmConnection(
            "./configs/settings.ini")

        self.slurm_connection.connect()

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        # self.setMaximumSize(MIN_WIDTH, MIN_HEIGHT)
        self.setFixedHeight(MIN_HEIGHT)

        self.setWindowIcon(QIcon("/home/nicola/Desktop/slurm_gui/src_static/logo.png"))

        # --- Theme Setup ---
        self.themes = {
            THEME_DARK: get_dark_theme_stylesheet(),
            THEME_LIGHT: get_light_theme_stylesheet(),
        }
        self.current_theme = THEME_DARK
        self.setStyleSheet(self.themes[self.current_theme])

        # --- Central Widget and Layout ---
        self.central_widget = QWidget()
        self.central_widget.setMinimumSize(QSize(MIN_WIDTH, MIN_HEIGHT))
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
        self.set_connection_status(self.slurm_connection.is_connected())
        self.refresh_all()  # Initial data load
        self.load_settings()

    def set_connection_status(self, connected: bool, connecting=False):
        self.connection_status_ = True if connected else False
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
        nodes_data = None
        queue_jobs = None
        try:
            nodes_data = self.slurm_connection._fetch_nodes_infos()
            queue_jobs = self.slurm_connection._fetch_squeue()
        except ConnectionError as e:
            print(e)

        print("Refreshing all data...")
        self.refresh_job_status()
        self.refresh_cluster_jobs_queue(queue_jobs)
        self.cluster_status_overview_widget.update_status(nodes_data, queue_jobs)

        # self.set_connection_status(self.slurm_connection.is_connected())

    # --- Theme Handling ---
    def change_theme(self, theme_name):
        """Applies the selected theme stylesheet."""
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.setStyleSheet(self.themes[theme_name])
            self.cluster_status_overview_widget.setStyleSheet(
                self.cluster_status_overview_widget.themes[theme_name]
            )

            # Update separator color based on theme
            separator_color = COLOR_DARK_BORDER if self.current_theme == THEME_DARK else COLOR_LIGHT_BORDER
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
        """Creates the panel displaying cluster status information."""
        cluster_panel = QWidget()
        cluster_layout = QVBoxLayout(cluster_panel)
        cluster_layout.setSpacing(15)

        # Header with refresh button
        header_layout = QHBoxLayout()
        cluster_label = QLabel("Cluster Status Overview")
        header_layout.addWidget(cluster_label)
        header_layout.addStretch()

        self.filter_btn_by_users = ButtonGroupWidget()
        self.filter_btn_by_users.selectionChanged.connect(lambda text: self.filter_by_accounts(text))
        header_layout.addWidget(self.filter_btn_by_users)

        self.filter_jobs = QLineEdit()
        self.filter_jobs.setClearButtonEnabled(True)
        self.filter_jobs.setPlaceholderText("Filter jobs...")
        self.filter_jobs.setFixedWidth(250)  # Wider search
        header_layout.addWidget(self.filter_jobs)
        self.filter_btn = QPushButton()
        self.filter_btn.setIcon(QIcon("/home/nicola/Desktop/slurm_gui/src_static/filter.png"))
        self.filter_btn.setMaximumSize(32, 32)
        header_layout.addWidget(self.filter_btn)
        self.filter_btn.clicked.connect(lambda: self.job_queue_widget.filter_table(self.filter_jobs.text()))
        self.filter_jobs.textChanged.connect(lambda: self.job_queue_widget.filter_table(self.filter_jobs.text()))

        refresh_cluster_btn = QPushButton("Refresh Status")
        refresh_cluster_btn.clicked.connect(self.refresh_all)
        header_layout.addWidget(refresh_cluster_btn)

        cluster_layout.addLayout(header_layout)

        # --- Main Content Layout (Horizontal) ---
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)

        # --- Left Section: Job Queue ---
        self.job_queue_widget = JobQueueWidget()  # Instantiate the new widget
        content_layout.addWidget(self.job_queue_widget)  # Add it to the left side

        # --- Right Section: Cluster Overview (Nodes Status) ---
        overview_group = QGroupBox("Real-time Usage")
        overview_layout = QVBoxLayout(overview_group)
        overview_layout.setSpacing(15)

        # Set fixed width for the nodes status panel group box
        overview_group.setFixedWidth(450)

        self.cluster_status_overview_widget = cluster_status_widget.ClusterStatusWidget(
            slurm_connection=self.slurm_connection)
        overview_layout.addWidget(self.cluster_status_overview_widget,
                                  alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        content_layout.addWidget(overview_group)

        content_layout.setStretchFactor(self.job_queue_widget, 1)
        content_layout.setStretchFactor(overview_group, 0)  # Fixed width, no stretch

        cluster_layout.addLayout(content_layout)

        cluster_layout.addStretch()  # Push content to the top
        self.stacked_widget.addWidget(cluster_panel)

    def create_settings_panel(self):
        """Creates the panel for application settings."""
        self.settings_panel = SettingsWidget()
        self.settings_panel.theme_combo.currentTextChanged.connect(self.change_theme)
        self.settings_panel.save_appearance_btn.clicked.connect(self.save_appearence_settings)
        self.settings_panel.connection_settings_btn.clicked.connect(self.update_connection_setting)
        self.settings_panel.save_button.clicked.connect(self.save_settings)
        self.stacked_widget.addWidget(self.settings_panel)

    # --- Action & Data Methods ---

    def filter_by_accounts(self, account_type):
        if account_type == "ME":
            self.job_queue_widget.filter_table(self.settings_panel.username.text())
        elif account_type == "ALL":
            self.job_queue_widget.filter_table("")
        elif account_type == "STUD":
            self.job_queue_widget.filter_table_by_list(STUDENTS_JOBS_KEYWORD)
        elif account_type == "PROD":
            self.job_queue_widget.filter_table_by_negative_keywords(STUDENTS_JOBS_KEYWORD)

    def update_connection_setting(self):
        print("Updateding connection settings...")

        self.set_connection_status(None, connecting=True)
        thread = threading.Thread(target=self.slurm_connection.update_credentials_and_reconnect, args=(
            self.username.text(),
            self.cluster_address.text(),
            self.password.text()
        ))

        thread.start()

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
        ...

    def refresh_cluster_jobs_queue(self, queue_jobs=None):
        """Refreshes the cluster status widgets (demo)."""
        print("Refreshing cluster status...")
        # Update the job queue widget
        if queue_jobs is None:
            try:
                queue_jobs = self.slurm_connection._fetch_squeue()
            except ConnectionError as e:
                print(e)
                queue_jobs = []
        if hasattr(self, 'job_queue_widget'):
            self.job_queue_widget.update_queue_status(queue_jobs)

    def save_appearence_settings(self):
        print("--- Saving Appearence Settings ---")
        self.settings.beginGroup("AppearenceSettings")
        self.settings.setValue("theme", self.settings_panel.theme_combo.currentText())
        for i, obj in enumerate(self.settings_panel.jobs_queue_options_group.children()[1:-1]):
            self.settings.setValue(obj.objectName(), bool(obj.checkState().value))
        self.settings.endGroup()

        self.settings.sync()
        self.job_queue_widget.reload_settings_and_redraw()

    def save_settings(self):
        """Saves the current settings using QSettings."""
        print("--- Saving Settings ---")  # You can keep the print for debugging if you like

        # Use beginGroup to group related settings
        self.settings.beginGroup("GeneralSettings")
        self.settings.setValue("clusterAddress", self.slurm_connection.host)
        self.settings.setValue("username", self.slurm_connection.user)
        self.settings.setValue("psw", self.slurm_connection.password)
        self.settings.endGroup()  # End the group

        # self.settings.beginGroup("NotificationSettings")
        # self.settings.setValue("desktopNotifications", self.desktop_notify_check.isChecked())
        # self.settings.setValue("emailNotifications", self.email_notify_check.isChecked())
        # self.settings.setValue("soundNotifications", self.sound_notify_check.isChecked())
        # self.settings.endGroup()

        # self.settings.beginGroup("JobDefaults")
        # self.settings.setValue("defaultPartition", self.default_partition_combo.currentText())
        # self.settings.setValue("defaultMemory", self.default_memory_input.text())
        # self.settings.endGroup()

        # You can call sync() to ensure settings are written to permanent storage immediately,
        # although QSettings often does this automatically when the application exits.
        self.settings.sync()

        print("--- Settings Saved ---")
        show_message(self, "Settings Saved", "Settings have been saved.")

    def load_settings(self):
        """Loads settings from QSettings."""
        print("--- Loading Settings ---")

        self.settings = QSettings(str(Path("./configs/settings.ini")),
                                  QSettings.Format.IniFormat)  # Ensure settings object is available

        # Load General Settings
        self.settings.beginGroup("GeneralSettings")
        theme = self.settings.value("theme", "Dark")  # Provide a default value
        self.settings_panel.theme_combo.setCurrentText(theme)  # Make sure the theme exists in the combo box

        cluster_address = self.settings.value("clusterAddress", "")
        self.settings_panel.cluster_address.setText(cluster_address)

        username = self.settings.value("username", "")
        self.settings_panel.username.setText(username)

        cluster_psw = self.settings.value("psw", "")
        self.settings_panel.password.setText(cluster_psw)
        self.settings.endGroup()

        self.settings.beginGroup("AppearenceSettings")
        for i, obj in enumerate(self.settings_panel.jobs_queue_options_group.children()[1:-1]):
            value = self.settings.value(obj.objectName(), 'false', type=bool)
            obj.setCheckState(Qt.CheckState.Checked if value else Qt.CheckState.Unchecked)

        self.settings.endGroup()
        # # Load Notification Settings
        # self.settings.beginGroup("NotificationSettings")
        # desktop_notify = self.settings.value("desktopNotifications", True, type=bool)  # Specify type for boolean
        # self.desktop_notify_check.setChecked(desktop_notify)

        # email_notify = self.settings.value("emailNotifications", False, type=bool)
        # self.email_notify_check.setChecked(email_notify)

        # sound_notify = self.settings.value("soundNotifications", True, type=bool)
        # self.sound_notify_check.setChecked(sound_notify)
        # self.settings.endGroup()

        print("--- Settings Loaded ---")

    def closeEvent(self, event):
        """Handles the window close event."""
        self.slurm_connection.close()
        print("Closing application.")
        event.accept()


# --- Main Execution ---
if __name__ == "__main__":

    app = QApplication(sys.argv)

    # Apply a base font
    font = QFont("Inter", 10)  # Use Inter font if available, adjust size as needed
    app.setFont(font)
    app.setWindowIcon(QIcon("/home/nicola/Desktop/slurm_gui/src_static/logo.png"))
    window = SlurmJobManagerApp()
    window.show()
    sys.exit(app.exec())
