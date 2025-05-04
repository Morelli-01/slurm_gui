import sys
import os
import subprocess
import re
import random  # For demo refresh
import time  # Added for demo delay

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QComboBox, QFrame, QSizePolicy, QStackedWidget, QFormLayout, QGroupBox,
    QTextEdit, QSpinBox, QFileDialog, QProgressBar, QMessageBox
)
from PyQt6.QtGui import QIcon, QColor, QPalette, QFont, QPixmap
from PyQt6.QtCore import Qt, QSize, QTimer, QThread, QObject, pyqtSignal

# Assuming slurm_connection is a separate module you have
# import slurm_connection
# For this example, we'll use a mock object if the module isn't available
try:
    import slurm_connection
except ImportError:
    print("Warning: 'slurm_connection' module not found. Using mock connection.")

    class MockSlurmConnection:
        def __init__(self, config_path):
            print(f"MockSlurmConnection initialized with config: {config_path}")
            self._connected = False
            self.host = "mock_host"
            self.user = "mock_user"
            self.password = "mock_password"  # Insecure, use proper secrets management

        def is_connected(self):
            # Simulate connection status change
            if random.random() < 0.1:  # 10% chance to disconnect
                self._connected = False
            elif random.random() < 0.8:  # 80% chance to connect if disconnected
                self._connected = True
            return self._connected

        def update_credentials_and_reconnect(self, new_user, new_host, new_psw):
            print(f"MockSlurmConnection: Updating credentials and reconnecting...")
            self.user = new_user
            self.host = new_host
            self.password = new_psw
            # Simulate connection attempt
            self._connected = random.random() > 0.2  # 80% chance of success
            print(f"MockSlurmConnection: Reconnected status: {self._connected}")

    slurm_connection = MockSlurmConnection  # Use the mock class


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
STATUS_CANCELLED = "CANCELLED"  # Added cancelled status

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
    # In a real app, handle file not found gracefully
    try:
        with open("src_static/dark_theme.txt", "r") as f:
            stylesheet_template = f.read()
    except FileNotFoundError:
        print("Warning: dark_theme.txt not found. Using fallback styles.")
        stylesheet_template = """
            QMainWindow {{ background-color: {COLOR_DARK_BG}; color: {COLOR_DARK_FG}; }}
            QWidget {{ background-color: {COLOR_DARK_BG}; color: {COLOR_DARK_FG}; }}
            QGroupBox {{ border: 1px solid {COLOR_DARK_BORDER}; margin-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; color: {COLOR_DARK_FG}; }}
            QPushButton {{ background-color: {COLOR_DARK_BG_ALT}; color: {COLOR_DARK_FG}; border: 1px solid {COLOR_DARK_BORDER}; padding: 5px 10px; border-radius: 5px; }}
            QPushButton:hover {{ background-color: {COLOR_DARK_BG_HOVER}; }}
            QPushButton:pressed {{ background-color: {COLOR_DARK_BORDER}; }}
            QPushButton#navButton {{ background-color: transparent; border: none; padding: 5px 10px; }}
            QPushButton#navButton:hover {{ background-color: {COLOR_DARK_BG_HOVER}; }}
            QPushButton#navButtonActive {{ background-color: {COLOR_DARK_BG_ALT}; border: 1px solid {COLOR_DARK_BORDER}; border-bottom-color: transparent; border-radius: 5px 5px 0 0; }}
            QPushButton#{BTN_GREEN} {{ background-color: {COLOR_GREEN}; color: {COLOR_DARK_BG}; font-weight: bold; }}
            QPushButton#{BTN_RED} {{ background-color: {COLOR_RED}; color: {COLOR_DARK_BG}; font-weight: bold; }}
            QPushButton#{BTN_BLUE} {{ background-color: {COLOR_BLUE}; color: {COLOR_DARK_BG}; font-weight: bold; }}
            QLineEdit {{ background-color: {COLOR_DARK_BG_ALT}; color: {COLOR_DARK_FG}; border: 1px solid {COLOR_DARK_BORDER}; padding: 5px; border-radius: 3px; }}
            QTextEdit {{ background-color: {COLOR_DARK_BG_ALT}; color: {COLOR_DARK_FG}; border: 1px solid {COLOR_DARK_BORDER}; padding: 5px; border-radius: 3px; }}
            QComboBox {{ background-color: {COLOR_DARK_BG_ALT}; color: {COLOR_DARK_FG}; border: 1px solid {COLOR_DARK_BORDER}; padding: 5px; border-radius: 3px; }}
            QTableWidget {{ background-color: {COLOR_DARK_BG}; color: {COLOR_DARK_FG}; border: 1px solid {COLOR_DARK_BORDER}; gridline-color: {COLOR_DARK_BORDER}; }}
            QTableWidget QHeaderView::section {{ background-color: {COLOR_DARK_BG_ALT}; color: {COLOR_DARK_FG}; padding: 5px; border: 1px solid {COLOR_DARK_BORDER}; }}
            QTableWidget::item {{ padding: 5px; }}
            QTableWidget::item:selected {{ background-color: {COLOR_DARK_BG_HOVER}; }}
            QProgressBar {{ border: 1px solid {COLOR_DARK_BORDER}; border-radius: 5px; text-align: center; background-color: {COLOR_DARK_BG_ALT}; }}
            QProgressBar::chunk {{ background-color: {COLOR_BLUE}; border-radius: 5px; }}
            QLabel#clusterStatValue {{ font-size: 14px; font-weight: bold; }}
            QLabel#clusterStatValueAvail {{ color: {COLOR_GREEN}; }}
            QLabel#clusterStatValueRunning {{ color: {COLOR_BLUE}; }}
            QLabel#clusterStatValuePending {{ color: {COLOR_ORANGE}; }}
            QPushButton#statusButton {{ border: none; font-weight: bold; }}
        """

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
    # In a real app, handle file not found gracefully
    try:
        with open("/home/nicola/Desktop/slurm_gui/src_static/light_theme.txt", "r") as f:
            stylesheet = f.read()
    except FileNotFoundError:
        print("Warning: light_theme.txt not found. Using fallback styles.")
        stylesheet = """
             QMainWindow {{ background-color: {COLOR_LIGHT_BG}; color: {COLOR_LIGHT_FG}; }}
             QWidget {{ background-color: {COLOR_LIGHT_BG}; color: {COLOR_LIGHT_FG}; }}
             QGroupBox {{ border: 1px solid {COLOR_LIGHT_BORDER}; margin-top: 10px; }}
             QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px; color: {COLOR_LIGHT_FG}; }}
             QPushButton {{ background-color: {COLOR_LIGHT_BG_ALT}; color: {COLOR_LIGHT_FG}; border: 1px solid {COLOR_LIGHT_BORDER}; padding: 5px 10px; border-radius: 5px; }}
             QPushButton:hover {{ background-color: {COLOR_LIGHT_BG_HOVER}; }}
             QPushButton:pressed {{ background-color: {COLOR_LIGHT_BORDER}; }}
             QPushButton#navButton {{ background-color: transparent; border: none; padding: 5px 10px; }}
             QPushButton#navButton:hover {{ background-color: {COLOR_LIGHT_BG_HOVER}; }}
             QPushButton#navButtonActive {{ background-color: {COLOR_LIGHT_BG_ALT}; border: 1px solid {COLOR_LIGHT_BORDER}; border-bottom-color: transparent; border-radius: 5px 5px 0 0; }}
             QPushButton#{BTN_GREEN} {{ background-color: {COLOR_GREEN}; color: white; font-weight: bold; }}
             QPushButton#{BTN_RED} {{ background-color: {COLOR_RED}; color: white; font-weight: bold; }}
             QPushButton#{BTN_BLUE} {{ background-color: {COLOR_BLUE}; color: white; font-weight: bold; }}
             QLineEdit {{ background-color: {COLOR_LIGHT_BG_ALT}; color: {COLOR_LIGHT_FG}; border: 1px solid {COLOR_LIGHT_BORDER}; padding: 5px; border-radius: 3px; }}
             QTextEdit {{ background-color: {COLOR_LIGHT_BG_ALT}; color: {COLOR_LIGHT_FG}; border: 1px solid {COLOR_LIGHT_BORDER}; padding: 5px; border-radius: 3px; }}
             QComboBox {{ background-color: {COLOR_LIGHT_BG_ALT}; color: {COLOR_LIGHT_FG}; border: 1px solid {COLOR_LIGHT_BORDER}; padding: 5px; border-radius: 3px; }}
             QTableWidget {{ background-color: {COLOR_LIGHT_BG}; color: {COLOR_LIGHT_FG}; border: 1px solid {COLOR_LIGHT_BORDER}; gridline-color: {COLOR_LIGHT_BORDER}; }}
             QTableWidget QHeaderView::section {{ background-color: {COLOR_LIGHT_BG_ALT}; color: {COLOR_LIGHT_FG}; padding: 5px; border: 1px solid {COLOR_LIGHT_BORDER}; }}
             QTableWidget::item {{ padding: 5px; }}
             QTableWidget::item:selected {{ background-color: {COLOR_LIGHT_BG_HOVER}; }}
             QProgressBar {{ border: 1px solid {COLOR_LIGHT_BORDER}; border-radius: 5px; text-align: center; background-color: {COLOR_LIGHT_BG_ALT}; }}
             QProgressBar::chunk {{ background-color: {COLOR_BLUE}; border-radius: 5px; }}
             QLabel#clusterStatValue {{ font-size: 14px; font-weight: bold; }}
             QLabel#clusterStatValueAvail {{ color: {COLOR_GREEN}; }}
             QLabel#clusterStatValueRunning {{ color: {COLOR_BLUE}; }}
             QLabel#clusterStatValuePending {{ color: {COLOR_ORANGE}; }}
             QPushButton#statusButton {{ border: none; font-weight: bold; }}
         """

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


# --- Worker Class for Background Operations ---
class SlurmWorker(QObject):
    # Define signals to communicate with the main thread
    jobs_data_fetched = pyqtSignal(list)
    cluster_data_fetched = pyqtSignal(dict, list)  # Pass cluster stats dict and partitions list
    connection_status_fetched = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)  # Signal for reporting errors

    def __init__(self, slurm_connection_instance):
        super().__init__()
        self._slurm_connection = slurm_connection_instance
        self._is_running = True  # Flag to control the worker loop

    def stop(self):
        """Safely stops the worker's main loop."""
        self._is_running = False

    def fetch_all_data(self):
        while (True):
            """Fetches all data (jobs, cluster, connection) in the worker thread."""
            if not self._is_running:
                return

            print("Worker: Fetching all data...")
            try:
                # Fetch connection status first
                connected = self._slurm_connection.is_connected()
                self.connection_status_fetched.emit(connected)

                if connected:
                    # --- Fetch Job Data (Replace with actual squeue call) ---
                    # try:
                    #    cmd = ["squeue", "-u", os.environ.get("USER"), "-o", "%i %j %P %T %M %D"] # Example format
                    #    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
                    #    output_lines = result.stdout.strip().split('\n')
                    #    # Parse output_lines into jobs_data list of dicts
                    #    jobs_data = [] # Populate this list
                    #    # Example parsing (adjust based on your squeue format)
                    #    if len(output_lines) > 1: # Check if there's data beyond header
                    #        for line in output_lines[1:]:
                    #            parts = line.split() # Simple split, might need regex
                    #            if len(parts) >= 6:
                    #                job = {"id": parts[0], "name": parts[1], "partition": parts[2],
                    #                       "status": parts[3], "time": parts[4], "nodes": parts[5]}
                    #                jobs_data.append(job)
                    #    self.jobs_data_fetched.emit(jobs_data)
                    # except Exception as e:
                    #    self.error_occurred.emit(f"Error fetching job data: {e}")
                    #    self.jobs_data_fetched.emit([]) # Emit empty list on error

                    # --- Demo Job Data ---
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
                        {"id": "123461", "name": "cancelled_job", "partition": "compute",
                         "status": STATUS_CANCELLED, "time": "0:05:00", "nodes": "1"},
                    ]
                    # Randomly change status for demo refresh effect
                    for job in sample_jobs:
                        if random.random() < 0.1 and job["status"] == STATUS_PENDING:
                            job["status"] = STATUS_RUNNING
                            job["time"] = "0:00:10"
                        elif random.random() < 0.05 and job["status"] == STATUS_RUNNING:
                            job["status"] = random.choice([STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED])
                            job["time"] = f"{random.randint(1, 5)}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"

                    # Simulate some work
                    time.sleep(0.5)  # Simulate network latency/processing time
                    self.jobs_data_fetched.emit(sample_jobs)

                    # --- Fetch Cluster Data (Replace with actual sinfo/scontrol calls) ---
                    # try:
                    #    # Fetch cluster stats (total, avail nodes, job counts)
                    #    # Fetch partition data (sinfo)
                    #    cluster_stats = {} # Populate this dict
                    #    partitions_data = [] # Populate this list
                    #    self.cluster_data_fetched.emit(cluster_stats, partitions_data)
                    # except Exception as e:
                    #    self.error_occurred.emit(f"Error fetching cluster data: {e}")
                    #    self.cluster_data_fetched.emit({}, []) # Emit empty data on error

                    # --- Demo Cluster Data ---
                    total_nodes = 64
                    avail_nodes = random.randint(30, 55)
                    running_jobs = random.randint(10, 20)
                    pending_jobs = random.randint(5, 15)
                    cpu_usage = random.randint(40, 85)
                    mem_usage = random.randint(30, 70)
                    gpu_usage = random.randint(50, 90)  # Assuming some GPUs exist

                    cluster_stats = {
                        "total_nodes": total_nodes,
                        "avail_nodes": avail_nodes,
                        "running_jobs": running_jobs,
                        "pending_jobs": pending_jobs,
                        "cpu_usage": cpu_usage,
                        "mem_usage": mem_usage,
                        "gpu_usage": gpu_usage,
                    }

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

                    # Simulate some work
                    time.sleep(0.5)  # Simulate network latency/processing time
                    self.cluster_data_fetched.emit(cluster_stats, sample_partitions)

                else:
                    print("Worker: Not connected, skipping data fetch.")

            except Exception as e:
                # Catch any unexpected errors during the process
                self.error_occurred.emit(f"An unexpected error occurred in worker: {e}")

            time.sleep(2)

# --- Main Application Class ---


class SlurmJobManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # Initialize the SLURM connection object
        self.slurm_connection = slurm_connection.SlurmConnection(
            "/home/nicola/Desktop/slurm_gui/configs/slurm_config.yaml")

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        # Add an icon path here if you have one, handle file not found
        icon_path = "/home/nicola/Desktop/slurm_gui/src_static/logo.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Warning: Icon file not found at {icon_path}")

        # --- Theme Setup ---
        self.themes = {
            THEME_DARK: get_dark_theme_stylesheet(),
            THEME_LIGHT: get_light_theme_stylesheet(),
        }
        self.current_theme = THEME_DARK
        self.setStyleSheet(self.themes[self.current_theme])

        # --- Central Widget and Layout ---
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15)  # Increased margins
        self.main_layout.setSpacing(15)  # Increased spacing

        # --- UI Elements ---
        self.nav_buttons = {}  # Store nav buttons for easier access
        self.create_navigation_bar()
        # Initial separator color based on current theme
        separator_color = COLOR_DARK_BORDER if self.current_theme == THEME_DARK else COLOR_LIGHT_BORDER
        self.main_layout.addWidget(create_separator(color=separator_color))

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # Create panels (views)
        self.create_jobs_panel()
        self.create_cluster_panel()
        self.create_settings_panel()

        self.connection_status = QPushButton(" Connecting...")  # Initial status
        self.connection_status.setObjectName("statusButton")  # Use object name for styling
        self.connection_status.setCheckable(True)  # Make buttons checkable for active state
        # Handle icon file not found
        cloud_off_icon_path = "/home/nicola/Desktop/slurm_gui/src_static/cloud_off_24dp_EA3323_FILL0_wght400_GRAD0_opsz24.png"
        if os.path.exists(cloud_off_icon_path):
            self.connection_status.setIcon(QIcon(cloud_off_icon_path))
        else:
            print(f"Warning: Cloud off icon not found at {cloud_off_icon_path}")

        self.main_layout.addWidget(self.connection_status, alignment=Qt.AlignmentFlag.AlignLeft |
                                   Qt.AlignmentFlag.AlignBottom)

        # --- Threading Setup ---
        self.worker_thread = QThread()
        self.slurm_worker = SlurmWorker(self.slurm_connection)  # Pass the connection object to the worker

        # Move the worker object to the thread
        self.slurm_worker.moveToThread(self.worker_thread)

        # Connect signals and slots
        # When the thread starts, execute the worker's fetch_all_data method
        self.worker_thread.started.connect(self.slurm_worker.fetch_all_data)

        # When worker finishes fetching jobs data, update the jobs table in the main thread
        self.slurm_worker.jobs_data_fetched.connect(self.populate_jobs_table)

        # When worker finishes fetching cluster data, update cluster widgets in the main thread
        self.slurm_worker.cluster_data_fetched.connect(self.update_cluster_widgets)

        # When worker fetches connection status, update the status button in the main thread
        self.slurm_worker.connection_status_fetched.connect(self.set_connection_status)

        # Connect error signal to a slot for displaying messages
        self.slurm_worker.error_occurred.connect(lambda msg: show_message(
            self, "Worker Error", msg, QMessageBox.Icon.Warning))

        # Clean up the worker and thread when the worker finishes (optional but good practice)
        # self.slurm_worker.finished.connect(self.worker_thread.quit)
        # self.slurm_worker.finished.connect(self.slurm_worker.deleteLater)
        # self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        # --- Initialization ---
        self.update_nav_styles(self.nav_buttons["Jobs"])  # Set initial active nav
        self.stacked_widget.setCurrentIndex(0)
        self.setup_refresh_timer()
        self.refresh_all()  # Initial data load - this now *starts* the worker thread
        # Initial connection status is set by the first worker run

    def set_connection_status(self, connected: bool):
        """Updates the visual status of the connection button."""
        if connected:
            self.connection_status.setText("Connected")
            # Handle icon file not found
            good_icon_path = "/home/nicola/Desktop/slurm_gui/src_static/good_connection.png"
            if os.path.exists(good_icon_path):
                self.connection_status.setIcon(QIcon(good_icon_path))
            else:
                print(f"Warning: Good connection icon not found at {good_icon_path}")

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
            self.connection_status.setText("Disconnected")
            # Handle icon file not found
            bad_icon_path = "/home/nicola/Desktop/slurm_gui/src_static/bad_connection.png"
            if os.path.exists(bad_icon_path):
                self.connection_status.setIcon(QIcon(bad_icon_path))
            else:
                print(f"Warning: Bad connection icon not found at {bad_icon_path}")

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
        # Connect the timer timeout to refresh_all, which now starts the worker
        self.refresh_timer.timeout.connect(self.refresh_all)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)

    def refresh_all(self):
        """Triggers a full data refresh by starting the worker thread."""
        print("Triggering data refresh...")
        # Only start the worker if it's not already running
        if not self.worker_thread.isRunning():
            self.worker_thread.start()
        else:
            print("Worker is already running, skipping start.")

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
        # Handle logo file not found
        logo_path = "/home/nicola/Desktop/slurm_gui/src_static/logo.png"
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)  # Use .svg or .ico if needed
            scaled_pixmap = pixmap.scaled(35, 35, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            print(f"Warning: Logo file not found at {logo_path}")
            logo_label.setText("Logo")  # Fallback text

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
        # Separator color based on current theme
        separator_color = COLOR_DARK_BORDER if self.current_theme == THEME_DARK else COLOR_LIGHT_BORDER
        jobs_layout.addWidget(create_separator(color=separator_color))
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
        # Connect refresh button to refresh_all, which starts the worker
        refresh_btn.clicked.connect(self.refresh_all)
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
        header_layout.setContentsMargins(0, 0, 0, 0)
        cluster_label = QLabel("Cluster Status Overview")
        cluster_label.setStyleSheet("font-size: 18px; font-weight: bold;")  # Slightly smaller title
        header_layout.addWidget(cluster_label)
        header_layout.addStretch()
        refresh_cluster_btn = QPushButton("Refresh Status")
        refresh_cluster_btn.setIcon(QIcon())  # Placeholder icon
        # Connect refresh button to refresh_all, which starts the worker
        refresh_cluster_btn.clicked.connect(self.refresh_all)
        header_layout.addWidget(refresh_cluster_btn)
        cluster_layout.addLayout(header_layout)

        # --- Cluster Overview Group ---
        overview_group = QGroupBox("Real-time Usage")
        overview_layout = QVBoxLayout(overview_group)
        overview_layout.setSpacing(15)

        # Cluster stats grid
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(20)  # Space between stats

        # Helper to create stat widgets
        def create_stat_widget(label_text, value_id, object_name=None):
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
            label = QLabel(label_text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value = QLabel("N/A")  # Default value
            value.setObjectName("clusterStatValue")
            if object_name:
                value.setProperty("statusColor", object_name)  # Custom property for styling if needed
                value.setObjectName(f"clusterStatValue{object_name}")  # Specific object name for styling
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            layout.addWidget(value)
            setattr(self, value_id, value)  # Store value label reference
            return widget

        stats_layout.addWidget(create_stat_widget("Total Nodes", "total_nodes_value"))
        stats_layout.addWidget(create_stat_widget("Available Nodes", "avail_nodes_value", "Avail"))
        stats_layout.addWidget(create_stat_widget("Running Jobs", "running_jobs_value", "Running"))
        stats_layout.addWidget(create_stat_widget("Pending Jobs", "pending_jobs_value", "Pending"))

        overview_layout.addLayout(stats_layout)

        # Usage bars
        usage_layout = QFormLayout()  # Use form layout for better alignment
        usage_layout.setSpacing(10)

        # Helper to create progress bar row
        def create_progress_row(label_text, progress_id, percent_id):
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            progress = QProgressBar()
            progress.setValue(0)
            progress.setTextVisible(False)  # Show percentage in separate label
            percent_label = QLabel("0%")
            percent_label.setFixedWidth(40)  # Fixed width for alignment
            layout.addWidget(progress)
            layout.addWidget(percent_label)
            setattr(self, progress_id, progress)
            setattr(self, percent_id, percent_label)
            return label_text, layout

        usage_layout.addRow(*create_progress_row("CPU Usage:", "cpu_progress", "cpu_percent_label"))
        usage_layout.addRow(*create_progress_row("Memory Usage:", "mem_progress", "mem_percent_label"))
        usage_layout.addRow(*create_progress_row("GPU Usage:", "gpu_progress", "gpu_percent_label"))

        overview_layout.addLayout(usage_layout)
        cluster_layout.addWidget(overview_group)

        # --- Partition Status Group ---
        partitions_group = QGroupBox("Partition Status")
        partitions_layout = QVBoxLayout(partitions_group)

        self.partitions_table = QTableWidget()
        self.partitions_table.setColumnCount(5)
        self.partitions_table.setHorizontalHeaderLabels(
            ["Partition", "Available", "Total", "Usage %", "State"])
        self.partitions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.partitions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # self.partitions_table.setAlternatingRowColors(True)
        self.partitions_table.verticalHeader().setVisible(False)

        header = self.partitions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Partition name takes space
        for i in range(1, 5):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)  # Other columns fit content

        partitions_layout.addWidget(self.partitions_table)
        cluster_layout.addWidget(partitions_group)

        cluster_layout.addStretch()
        self.stacked_widget.addWidget(cluster_panel)

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
        connection_layout = QFormLayout(connection_group)
        # Handle potential None values if slurm_connection init failed
        self.cluster_address = QLineEdit(getattr(self.slurm_connection, 'host', ''))
        connection_layout.addRow("Cluster Address:", self.cluster_address)
        self.username = QLineEdit(getattr(self.slurm_connection, 'user', ''))
        connection_layout.addRow("Username:", self.username)

        # Replace SSH key with password field
        self.password = QLineEdit(getattr(self.slurm_connection, 'password', ''))  # Insecure storage
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

    # --- Action & Data Methods (Slots connected to worker signals) ---

    def update_connection_setting(self):
        """Updates connection settings and triggers a reconnect attempt."""
        print("Updating connection settings...")
        # This call might still block if the reconnect logic is synchronous.
        # For a fully non-blocking approach, the reconnect logic itself
        # would need to be moved to a separate thread or use async methods.
        # For now, we'll keep it here as it's user-initiated.
        self.slurm_connection.update_credentials_and_reconnect(
            new_user=self.username.text(),
            new_host=self.cluster_address.text(),
            new_psw=self.password.text()  # Insecure
        )
        # After attempting reconnect, trigger a status update via the worker
        # self.refresh_all()

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
        # You might want to run this in a separate thread as well if it blocks
        # try:
        #     # Consider using SSH if running remotely
        #     result = subprocess.run(sbatch_cmd, capture_output=True, text=True, check=True, timeout=10)
        #     output = result.stdout
        #     match = re.search(r'Submitted batch job (\d+)', output)
        #     if match:
        #         job_id = match.group(1)
        #         show_message(self, "Job Submitted", f"Job '{job_name}' submitted successfully.\nJob ID: {job_id}")
        #         self.clear_submission_form()
        #         self.refresh_all() # Trigger a refresh via the worker
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
        # Simulate adding the job and refreshing by triggering the worker
        self.refresh_all()

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

    # Slot to receive job data from the worker and update the table
    def populate_jobs_table(self, jobs_data):
        """Populates the jobs table with data received from the worker."""
        print("Main Thread: Populating jobs table...")
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
            elif status == STATUS_CANCELLED:
                item_status.setForeground(QColor(Qt.GlobalColor.darkGray))  # Use a different color for cancelled
            # Add more statuses (TIMEOUT, etc.) if needed

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
        self.filter_jobs(self.search_input.text())  # Re-apply filter after refresh

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
        # This might also need to be run in a separate thread if it blocks
        # try:
        #     subprocess.run(["scancel", job_id], check=True, capture_output=True, text=True)
        #     show_message(self, "Job Cancelled", f"Job {job_id} cancelled successfully.")
        #     self.refresh_all() # Trigger a refresh via the worker
        # except Exception as e:
        #     show_message(self, "Error", f"Failed to cancel job {job_id}:\n{str(e)}", QMessageBox.Icon.Warning)

        # Demo
        show_message(self, "Cancel Job (Demo)", f"Would attempt to cancel job {job_id}.")
        # Simulate removal or status change by triggering a refresh
        self.refresh_all()

    def show_job_details(self, job_id):
        """Handles the 'Show Details' action (demo)."""
        print(f"Fetching details for job {job_id}")
        # ** In a real application, run 'scontrol show job job_id' and display output **
        # This might also need to be run in a separate thread if it blocks
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
        demo_details = f"JobId={job_id} Name=some_job\nUserId=user(1001) GroupId=group(1001)\nPriority=100 Nice=0 Account=default QOS=normal\nJobState={random.choice(['RUNNING', 'PENDING', 'COMPLETED', 'FAILED', 'CANCELLED'])} Reason=None Dependency=(null)\nTimeLimit=01:00:00 TimeLeft=00:{random.randint(0, 59):02d}:{random.randint(0, 59):02d} SubmitTime=...\nStartTime=... EndTime=...\nPartition=compute NodeList=node01\nNumNodes=1 NumCPUs=4 Mem=4G\nWorkDir=/path/to/workdir\nStdOut=/path/to/output.log"
        details_dialog = QMessageBox(self)
        details_dialog.setWindowTitle(f"Job Details (Demo): {job_id}")
        details_dialog.setTextFormat(Qt.TextFormat.PlainText)
        details_dialog.setText(demo_details)
        details_dialog.setIcon(QMessageBox.Icon.Information)
        # Make the dialog wider for better readability
        details_dialog.layout().setColumnStretch(1, 1)  # Allow text area to expand
        details_dialog.exec()

    # Slot to receive cluster data from the worker and update widgets
    def update_cluster_widgets(self, cluster_stats, partitions_data):
        """Updates cluster status widgets and partitions table with data from the worker."""
        print("Main Thread: Updating cluster widgets...")
        # Update overview stats
        self.total_nodes_value.setText(str(cluster_stats.get("total_nodes", "N/A")))
        self.avail_nodes_value.setText(str(cluster_stats.get("avail_nodes", "N/A")))
        self.running_jobs_value.setText(str(cluster_stats.get("running_jobs", "N/A")))
        self.pending_jobs_value.setText(str(cluster_stats.get("pending_jobs", "N/A")))

        # Update progress bars
        cpu_usage = cluster_stats.get("cpu_usage", 0)
        mem_usage = cluster_stats.get("mem_usage", 0)
        gpu_usage = cluster_stats.get("gpu_usage", 0)

        self.cpu_progress.setValue(cpu_usage)
        self.cpu_percent_label.setText(f"{cpu_usage}%")
        self.mem_progress.setValue(mem_usage)
        self.mem_percent_label.setText(f"{mem_usage}%")
        self.gpu_progress.setValue(gpu_usage)
        self.gpu_percent_label.setText(f"{gpu_usage}%")

        # Populate partitions table
        self.populate_partitions_table(partitions_data)

    def populate_partitions_table(self, partitions_data):
        """Populates the partitions table with data received from the worker."""
        print("Main Thread: Populating partitions table...")
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

    def refresh_job_status(self):
        """Deprecated: Use refresh_all() to trigger threaded refresh."""
        print("refresh_job_status called directly - this is deprecated. Use refresh_all().")
        self.refresh_all()  # Redirect to the new method

    def refresh_cluster_status(self):
        """Deprecated: Use refresh_all() to trigger threaded refresh."""
        print("refresh_cluster_status called directly - this is deprecated. Use refresh_all().")
        self.refresh_all()  # Redirect to the new method

    def save_settings(self):
        """Saves the current settings (demo)."""
        # In a real app, save to a config file (e.g., JSON, INI, QSettings)
        print("--- Saving Settings (Demo) ---")
        print(f"Theme: {self.theme_combo.currentText()}")
        print(f"Cluster Address: {self.cluster_address.text()}")
        print(f"Username: {self.username.text()}")
        # print(f"SSH Key Path: {self.ssh_key_path.text()}") # If using SSH key
        print(f"Desktop Notifications: {self.desktop_notify_check.isChecked()}")
        print(f"Email Notifications: {self.email_notify_check.isChecked()}")
        print(f"Sound Notifications: {self.sound_notify_check.isChecked()}")
        print(f"Default Partition: {self.default_partition_combo.currentText()}")
        print(f"Default Memory: {self.default_memory_input.text()}")
        print("-----------------------------")
        show_message(self, "Settings Saved", "Settings have been saved (demo).")

    def closeEvent(self, event):
        """Handles the window close event."""
        # Stop the worker thread gracefully before closing
        if self.worker_thread.isRunning():
            self.slurm_worker.stop()  # Signal the worker to stop
            self.worker_thread.quit()  # Request the thread to quit
            self.worker_thread.wait()  # Wait for the thread to finish

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
