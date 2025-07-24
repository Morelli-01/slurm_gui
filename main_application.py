from core.slurm_worker import SlurmWorker
from widgets.job_queue_widget import JobQueueWidget
import re
from datetime import datetime
import sys
import subprocess
from widgets.jobs_panel_widget import JobsPanelWidget
from widgets.toast_widget import (
    show_info_toast,
    show_success_toast,
    show_warning_toast,
    show_error_toast,
)
from widgets.settings_widget import SettingsWidget
import shutil
from pathlib import Path
from utils import *
from core.style import AppStyles
from core.defaults import *
from widgets.cluster_status_widget import ClusterStatusWidget
from core.slurm_api import ConnectionState, SlurmAPI
from core.event_bus import EventPriority, Events, get_event_bus
import platform
from functools import partial, wraps
import os
from threading import Thread
from core.terminal_helper import *
import requests
from packaging.version import parse as parse_version
import toml
import importlib.metadata

script_dir = os.path.dirname(os.path.abspath(__file__))

system = platform.system()
if system == "Windows":
    # Windows: Use Qt's built-in high DPI handling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

# --- Constants ---
APP_TITLE = "SlurmAIO"
# Use percentages for responsive design - Qt handles the DPI scaling
SCREEN_WIDTH_PERCENTAGE = 0.8
SCREEN_HEIGHT_PERCENTAGE = 0.85
MIN_WIDTH_PERCENTAGE = 0.4
MIN_HEIGHT_PERCENTAGE = 0.4
REFRESH_INTERVAL_MS = 5000


# --- Helper Functions ---
def get_dpi_ratio(app):
    """
    Gets the device pixel ratio from the primary screen.
    A temporary QApplication might be needed if one isn't running.
    """
    # If no application instance is passed, create a temporary one

    screen = app.primaryScreen()
    if screen is None:
        print("Error: Could not get primary screen.")
        return 1.0  # Return a default value

    dpi_ratio = screen.devicePixelRatio()


    return dpi_ratio


# Updated get_scaled_dimensions function
def get_scaled_dimensions(screen=None):
    """Get window dimensions that work consistently across different DPI settings"""
    if screen is None:
        screen = QApplication.primaryScreen()

    # Get the physical geometry (actual pixels)
    geometry = screen.geometry()

    # Get DPI scaling factor
    dpi_ratio = screen.devicePixelRatio()

    # Calculate base dimensions (these should be consistent regardless of DPI)
    base_width = 1500
    base_height = 950

    # Don't scale these values - let Qt handle the DPI scaling automatically
    width = base_width
    height = base_height
    min_width = int(base_width * 0.6)  # 60% of base width as minimum
    min_height = int(base_height * 0.6)  # 60% of base height as minimum

    print(f"Screen DPI ratio: {dpi_ratio}")
    print(f"Screen geometry: {geometry.width()}x{geometry.height()}")
    print(f"Window size: {width}x{height}")
    return width, height, min_width, min_height


class ConnectionSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setup Initial Connection")

        # Use device-independent pixels - Qt handles DPI scaling automatically
        self.setMinimumWidth(400)
        self.setStyleSheet(
            AppStyles.get_dialog_styles()
            + AppStyles.get_input_styles()
            + AppStyles.get_button_styles()
        )
        layout = QVBoxLayout(self)

        # Use consistent spacing in device-independent pixels
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        info_label = QLabel(
            "Settings file not found. Please enter connection details to set up the first SSH connection."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.cluster_address_input = QLineEdit()
        self.cluster_address_input.setPlaceholderText("e.g., your.cluster.address")
        form_layout.addRow("Cluster Address:", self.cluster_address_input)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Your username")
        form_layout.addRow("Username:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Your password (optional, or use key)")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Password:", self.password_input)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_connection_details(self):
        """Returns the entered connection details."""
        return {
            "clusterAddress": self.cluster_address_input.text().strip(),
            "username": self.username_input.text().strip(),
            "psw": self.password_input.text().strip(),
        }


# --- Main Application Class ---


class SlurmJobManagerApp(QMainWindow):

    def __init__(self):
        super().__init__()
        # Initialize SLURM connection
        self.slurm_api = SlurmAPI()

        self.setWindowTitle(APP_TITLE)

        # Set window size - Qt 6 handles DPI scaling automatically
        width, height, min_width, min_height = get_scaled_dimensions()
        self.resize(width, height)
        self.setMinimumSize(min_width, min_height)

        # Set window icon
        window_icon_path = os.path.join(script_dir, "src_static", "app_logo.png")
        self.setWindowIcon(QIcon(window_icon_path))

        # Theme setup
        self.current_theme = THEME_DARK
        self.apply_theme()

        # Central widget and layout - use device-independent pixels
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Consistent margins and spacing in device-independent pixels
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        # Create UI elements
        self.nav_buttons = {}
        self.create_navigation_bar()
        self.main_layout.addWidget(
            create_separator(
                color=(
                    COLOR_DARK_BORDER
                    if self.current_theme == THEME_DARK
                    else COLOR_LIGHT_BORDER
                )
            )
        )

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # Create panels
        self.create_jobs_panel()
        self.slurm_worker = SlurmWorker(self.slurm_api, self.jobs_panel.model)
        self.slurm_worker.data_ready.connect(self.handle_worker_data)
        self.slurm_worker.error_occurred.connect(self.handle_worker_error)
        self.create_cluster_panel()
        self.create_settings_panel()

        # Initialize
        self.update_nav_styles(self.nav_buttons["Jobs"])
        self.stacked_widget.setCurrentIndex(0)

        self.event_bus = get_event_bus()
        self._event_bus_subscription()

        # Attempt to connect immediately
        try:
            self.slurm_api.connect()
        except Exception as e:
            print(f"Initial connection failed: {e}")
            show_error_toast(
                self,
                "Connection Error",
                f"Failed to connect to the cluster: {e}. Please check settings.",
            )
        self.slurm_worker.start()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.slurm_worker.start)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)
        # self.load_settings()

    def _event_bus_subscription(self):
        self.event_bus.subscribe(
            Events.DATA_READY, self.update_ui_with_data, priority=EventPriority.HIGH
        )
        self.event_bus.subscribe(
            Events.CONNECTION_STATE_CHANGED, self.set_connection_status
        )
        self.event_bus.subscribe(
            Events.CONNECTION_SAVE_REQ, self.new_connection, priority=EventPriority.LOW
        )

    def new_connection(self, event_data):
        self.refresh_timer.stop()

        self.slurm_worker.stop()
        self.slurm_worker.wait(1000)

        self.slurm_api = SlurmAPI.reset_instance()
        self.slurm_worker = SlurmWorker(self.slurm_api, self.jobs_panel.model)

        self.slurm_worker.data_ready.connect(self.handle_worker_data)
        self.slurm_worker.error_occurred.connect(self.handle_worker_error)

        if self.slurm_api.connect():
            show_success_toast(
                self, "Connected", "Successfully connected to SLURM cluster"
            )
        else:
            print(f"Initial connection failed")
            show_error_toast(
                self,
                "Connection Error",
                f"Failed to connect to the cluster. Please check settings.",
            )

        self.slurm_worker.start()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.slurm_worker.start)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)

    def handle_worker_data(self, data_dict):
        """
        This slot receives data from the SlurmWorker thread safely.
        It then emits an event on the event bus, which will now be processed
        synchronously and safely in the main GUI thread.
        """
        self.event_bus.emit(
            Events.DATA_READY, data=data_dict, source="SlurmJobManagerApp"
        )

    def handle_worker_error(self, error_message):
        """This slot receives error messages from the SlurmWorker thread safely."""
        show_error_toast(self, "Worker Thread Error", error_message)
        self.event_bus.emit(
            Events.ERROR_OCCURRED,
            data={"error": error_message},
            source="SlurmJobManagerApp",
        )

    def set_connection_status(self, event_data):
        """connection status handling"""
        new_state = event_data.data["new_state"]
        old_state = event_data.data["old_state"]

        # Use device-independent icon size
        icon_size = QSize(28, 28)

        if new_state == ConnectionState.CONNECTING:
            loading_gif_path = os.path.join(script_dir, "src_static", "loading.gif")
            loading_movie = QMovie(loading_gif_path)
            loading_movie.setScaledSize(icon_size)
            loading_movie.start()
            self.connection_status.setMovie(loading_movie)
            self.connection_status.setText("")
            self.connection_status.setToolTip("Connecting...")
            self.connection_status.setStyleSheet(
                """
                QPushButton#statusButton {
                    background-color: #9e9e9e;
                    color: white;
                    border-radius: 6px;
                    font-weight: bold;
                    padding: 8px 15px;
                }
            """
            )
            return

        # Restore text after movie is done
        self.connection_status.setMovie(None)
        self.connection_status.setText(" Connection status...")

        if new_state == ConnectionState.CONNECTED:
            self.connection_status.setToolTip("Connected")
            good_connection_icon_path = os.path.join(
                script_dir, "src_static", "good_connection.png"
            )
            self.connection_status.setPixmap(
                QIcon(good_connection_icon_path).pixmap(icon_size)
            )
            self.connection_status.setStyleSheet(
                """
                QPushButton#statusButton {
                    background-color: #4caf50;
                    color: white;
                    border-radius: 10px;
                    font-weight: bold;
                    padding: 10px 18px;
                    border: 2px solid #4caf50;
                }
                QPushButton#statusButton:hover {
                    background-color: #66bb6a;
                    border: 2px solid #ffffff;
                }
            """
            )
            self.setup_maintenances()
        else:
            self.connection_status.setToolTip("Disconnected")
            bad_connection_icon_path = os.path.join(
                script_dir, "src_static", "bad_connection.png"
            )
            self.connection_status.setPixmap(
                QIcon(bad_connection_icon_path).pixmap(icon_size)
            )
            self.connection_status.setStyleSheet(
                """
                QPushButton#statusButton {
                    background-color: #f44336;
                    color: white;
                    border-radius: 10px;
                    font-weight: bold;
                    padding: 10px 18px;
                    border: 2px solid #f44336;
                }
                QPushButton#statusButton:hover {
                    background-color: #ef5350;
                    border: 2px solid #ffffff;
                }
            """
            )

    def update_ui_with_data(self, event):
        """Updates the UI with new data from SLURM."""
        nodes_data = event.data.get("nodes")
        queue_jobs = event.data.get("jobs")
        job_details = event.data.get("job_details")

        if job_details:
            self.jobs_panel.controller.model.update_jobs_from_sacct(job_details)

        # print("Updating job queue...")
        if hasattr(self, "job_queue_widget") and queue_jobs:
            self.job_queue_widget.update_queue_status(queue_jobs)

        # print("Updating cluster status...")
        if hasattr(self, "cluster_status_overview_widget") and nodes_data:
            self.cluster_status_overview_widget.update_status(nodes_data, queue_jobs)

    # --- Navigation Bar ---
    def switch_panel(self, index, clicked_button):
        """Switches the visible panel in the QStackedWidget."""
        self.stacked_widget.setCurrentIndex(index)
        self.update_nav_styles(clicked_button)

    def create_navigation_bar(self):
            """Creates the top navigation bar with logo, buttons, and search."""
            nav_widget = QWidget()
            nav_layout = QHBoxLayout(nav_widget)
            nav_layout.setContentsMargins(0, 0, 0, 0)
            nav_layout.setSpacing(15)  # Device-independent pixels

            # Logo - use device-independent size
            logo_label = QLabel()
            logo_size = 40  # Device-independent pixels
            logo_label.setFixedSize(logo_size, logo_size)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            nav_layout.addWidget(logo_label)

            logo_path = os.path.join(script_dir, "src_static", "app_logo.png")
            pixmap = QPixmap(logo_path)
            # Qt automatically handles DPI scaling for pixmaps
            scaled_pixmap = pixmap.scaled(
                logo_size,
                logo_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo_label.setPixmap(scaled_pixmap)

            nav_layout.addSpacing(25)  # Device-independent spacing

            # Navigation buttons
            button_names = ["Jobs", "Cluster Status", "Settings"]
            for i, name in enumerate(button_names):
                btn = QPushButton(name)
                btn.setObjectName("navButton")
                btn.setCheckable(True)
                btn.clicked.connect(
                    lambda checked, index=i, button=btn: self.switch_panel(index, button)
                )
                nav_layout.addWidget(btn)
                self.nav_buttons[name] = btn

            # Add maintenance label to navigation bar
            self.maintenance_label = QLabel()
            self.maintenance_label.setStyleSheet("""
                color: #FF6B6B;
                font-weight: bold;
                background-color: rgba(255, 107, 107, 0.1);
                border: 1px solid #FF6B6B;
                border-radius: 4px;
                padding: 6px 12px;
                margin: 0px 10px;
            """)
            self.maintenance_label.hide()  # Initially hidden
            nav_layout.addWidget(self.maintenance_label)

            nav_layout.addStretch()

            # Terminal button
            self.terminal_button = QPushButton("Terminal")
            self.terminal_button.setObjectName("terminalButton")
            self.terminal_button.setIcon(
                QIcon(os.path.join(script_dir, "src_static", "terminal.svg"))
            )
            self.terminal_button.setToolTip("Open SSH Terminal")
            self.terminal_button.clicked.connect(self.open_terminal)
            nav_layout.addWidget(self.terminal_button)

            # Connection status
            self.connection_status = ClickableLabel(" Connection status...")
            self.connection_status.setObjectName("statusButton")

            # Set initial icon - Qt handles DPI scaling for icons automatically
            initial_status_icon_path = os.path.join(
                script_dir,
                "src_static",
                "cloud_off_24dp_EA3323_FILL0_wght400_GRAD0_opsz24.png",
            )
            # Use device-independent size - Qt scales automatically
            icon_size = QSize(28, 28)
            self.connection_status.setPixmap(
                QPixmap(initial_status_icon_path).scaled(
                    icon_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            nav_layout.addWidget(self.connection_status)

            self.main_layout.addWidget(nav_widget)

    def open_terminal(self):
        """Open a terminal with SSH connection to the cluster"""
        if (
            not self.slurm_api
            or self.slurm_api.connection_status != ConnectionState.CONNECTED
        ):
            show_warning_toast(
                self,
                "Connection Required",
                "Please establish a SLURM connection first.",
            )
            return

        try:

            helper = TerminalHelper()
            connection = SSHConnectionDetails(
                self.slurm_api._config.host,
                self.slurm_api._config.username,
                self.slurm_api._config.password,
            )
            helper.open_ssh_terminal(connection, parent_widget=self)

        except Exception as e:
            show_error_toast(
                self, "Terminal Error", f"Failed to open terminal: {str(e)}"
            )

    # --- Panel Creation Methods ---

    def create_jobs_panel(self):
        """Creates the main panel for submitting and viewing jobs."""
        self.jobs_panel = JobsPanelWidget()  # <-- Changed this line
        self.stacked_widget.addWidget(self.jobs_panel)

    def create_cluster_panel(self):
        """Creates the panel displaying cluster status information."""
        cluster_panel = QWidget()
        cluster_layout = QVBoxLayout(cluster_panel)
        cluster_layout.setSpacing(15)  # Device-independent spacing

        # Header with refresh button (maintenance label removed from here)
        header_layout = QHBoxLayout()
        self.cluster_label = QLabel("Cluster Status Overview")
        self.cluster_label.setObjectName("sectionTitle")
        # Use device-independent font size - Qt handles DPI scaling

        header_layout.addWidget(self.cluster_label)
        header_layout.addStretch()

        self.filter_btn_by_users = ButtonGroupWidget()
        self.filter_btn_by_users.selectionChanged.connect(
            lambda text: self.filter_by_accounts(text)
        )
        header_layout.addWidget(self.filter_btn_by_users)

        self.filter_jobs = QLineEdit()
        self.filter_jobs.setClearButtonEnabled(True)
        self.filter_jobs.setPlaceholderText("Filter jobs...")
        # Use device-independent width
        self.filter_jobs.setFixedWidth(220)
        header_layout.addWidget(self.filter_jobs)

        self.filter_jobs.textChanged.connect(
            lambda: self.job_queue_widget.filter_table(self.filter_jobs.text())
        )

        refresh_cluster_btn = QPushButton("Refresh Status")
        refresh_cluster_btn.clicked.connect(self.slurm_worker.run)
        header_layout.addWidget(refresh_cluster_btn)

        cluster_layout.addLayout(header_layout)

        # Main Content Layout
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)  # Device-independent spacing

        # Left Section: Job Queue
        self.job_queue_widget = JobQueueWidget()
        content_layout.addWidget(self.job_queue_widget)
        self.job_queue_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Right Section: Cluster Overview
        overview_group = QGroupBox("Real-time Usage")
        overview_layout = QVBoxLayout(overview_group)
        overview_layout.setSpacing(15)  # Device-independent spacing
        overview_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.cluster_status_overview_widget = ClusterStatusWidget()
        overview_layout.addWidget(
            self.cluster_status_overview_widget,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )

        content_layout.addWidget(overview_group)
        content_layout.setStretchFactor(self.job_queue_widget, 1)
        content_layout.setStretchFactor(overview_group, 0)

        cluster_layout.addLayout(content_layout)
        self.stacked_widget.addWidget(cluster_panel)

    def create_settings_panel(self):
        """Creates the panel for application settings."""
        self.settings_panel = SettingsWidget()
        self.stacked_widget.addWidget(self.settings_panel)

    # --- Action & Data Methods ---

    def setup_maintenances(self):
        try:
            maintenance_info = self.slurm_api.read_maintenances()
            if maintenance_info:
                # Extract maintenance details
                maintenance_details = parse_slurm_reservations(maintenance_info)

                if maintenance_details:
                    # Create a readable maintenance warning
                    warning_messages = []
                    
                    for maintenance in maintenance_details:
                        reservation_name = maintenance.get('ReservationName', 'Unknown')
                        start_time_str = maintenance.get('StartTime', '')
                        end_time_str = maintenance.get('EndTime', '')
                        state = maintenance.get('State', 'Unknown')
                        nodes = maintenance.get('Nodes', [])
                        
                        # Parse start time to calculate time until maintenance
                        if start_time_str:
                            try:
                                start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
                                now = datetime.now()
                                
                                if state == 'ACTIVE':
                                    # Maintenance is currently active
                                    if end_time_str:
                                        end_time = datetime.strptime(end_time_str, "%Y-%m-%dT%H:%M:%S")
                                        time_remaining = end_time - now
                                        if time_remaining.total_seconds() > 0:
                                            hours_remaining = int(time_remaining.total_seconds() // 3600)
                                            warning_messages.append(f"ACTIVE maintenance ({hours_remaining}h remaining)")
                                        else:
                                            warning_messages.append(f"Maintenance ending soon")
                                    else:
                                        warning_messages.append(f"ACTIVE maintenance")
                                        
                                elif state == 'INACTIVE' and start_time > now:
                                    # Maintenance is scheduled for the future
                                    time_to_start = start_time - now
                                    days_until = time_to_start.days
                                    hours_until = int((time_to_start.total_seconds() % 86400) // 3600)
                                    
                                    if days_until > 0:
                                        warning_messages.append(f"Scheduled in {days_until}d {hours_until}h")
                                    elif hours_until > 0:
                                        warning_messages.append(f"Scheduled in {hours_until}h")
                                    else:
                                        minutes_until = int((time_to_start.total_seconds() % 3600) // 60)
                                        warning_messages.append(f"Scheduled in {minutes_until}m")
                                
                            except ValueError as e:
                                print(f"Error parsing maintenance time: {e}")
                                warning_messages.append(f"Maintenance scheduled")
                    
                    if warning_messages:
                        # Limit to most urgent/relevant messages and keep it concise
                        display_message = " • ".join(warning_messages[:2])  # Show max 2 maintenance events
                        if len(warning_messages) > 2:
                            display_message += f" (+{len(warning_messages)-2} more)"
                        
                        self.maintenance_label.setText(f"⚠️ {display_message}")
                        self.maintenance_label.setToolTip(self._create_detailed_maintenance_tooltip(maintenance_details))
                        self.maintenance_label.show()
                    else:
                        self.maintenance_label.hide()
                else:
                    self.maintenance_label.hide()
            else:
                self.maintenance_label.hide()
        except Exception as e:
            print(f"Error checking maintenance status: {e}")
            self.maintenance_label.hide()
    
    def _create_detailed_maintenance_tooltip(self, maintenance_details):
        """Create a detailed tooltip with full maintenance information"""
        tooltip_lines = []
        
        for maintenance in maintenance_details:
            name = maintenance.get('ReservationName', 'Unknown')
            start = maintenance.get('StartTime', 'Unknown')
            end = maintenance.get('EndTime', 'Unknown')
            state = maintenance.get('State', 'Unknown')
            nodes = maintenance.get('Nodes', [])
            
            # Format the time strings for better readability
            try:
                if start != 'Unknown':
                    start_dt = datetime.strptime(start, "%Y-%m-%dT%H:%M:%S")
                    start_formatted = start_dt.strftime("%Y-%m-%d %H:%M")
                else:
                    start_formatted = start
                    
                if end != 'Unknown':
                    end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%S")
                    end_formatted = end_dt.strftime("%Y-%m-%d %H:%M")
                else:
                    end_formatted = end
            except ValueError:
                start_formatted = start
                end_formatted = end
            
            node_count = len(nodes) if nodes else 0
            node_info = f"{node_count} nodes" if node_count > 5 else f"Nodes: {', '.join(nodes[:5])}"
            if node_count > 5:
                node_info += f" (+{node_count-5} more)"
            
            tooltip_lines.append(f"• {name} [{state}]")
            tooltip_lines.append(f"  Time: {start_formatted} → {end_formatted}")
            tooltip_lines.append(f"  {node_info}")
            tooltip_lines.append("")  # Empty line for separation
        
        return "\n".join(tooltip_lines)

    def filter_by_accounts(self, account_type):
        if account_type == "ME":
            self.job_queue_widget.filter_table_by_user(
                self.settings_panel.username.text()
            )
        elif account_type == "ALL":
            self.job_queue_widget.filter_table_by_account("")
        elif account_type == "STUD":
            self.job_queue_widget.filter_table_by_account(STUDENTS_JOBS_KEYWORD)
        elif account_type == "PROD":
            self.job_queue_widget.filter_table_by_account(
                STUDENTS_JOBS_KEYWORD, negative=True
            )

    def closeEvent(self, event):
        """Handles the window close event."""
        # if hasattr(self, 'jobs_panel') and self.jobs_panel.project_storer:
        #     self.jobs_panel.project_storer.stop_job_monitoring()
        self.slurm_worker.stop()
        self.slurm_api.disconnect()
        print("Closing application.")
        event.accept()

    # --------------------- Styles ------------------------

    def apply_theme(self):
        """Apply the current theme using centralized styles"""
        stylesheet = AppStyles.get_complete_stylesheet(self.current_theme)
        self.setStyleSheet(stylesheet)

    def update_nav_styles(self, active_button=None):
        """Updates the visual style of navigation buttons to show the active one."""
        if active_button is None:
            current_index = self.stacked_widget.currentIndex()
            button_list = list(self.nav_buttons.values())
            if 0 <= current_index < len(button_list):
                active_button = button_list[current_index]

        for name, btn in self.nav_buttons.items():
            if btn == active_button:
                btn.setObjectName("navButtonActive")
                btn.setChecked(True)
            else:
                btn.setObjectName("navButton")
                btn.setChecked(False)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # Style the terminal button separately (it's not a nav button)
        if hasattr(self, "terminal_button"):
            self.terminal_button.style().unpolish(self.terminal_button)
            self.terminal_button.style().polish(self.terminal_button)


# --- Main Execution ---


def check_for_updates(parent):
    """
    Checks for a new version of the application on PyPI and shows a notification if an update is available.
    """
    package_name = "slurm-aio-gui"
    try:
        # Get the currently installed version from pyproject.toml
        # In a real application, you might get this from importlib.metadata

        current_version_str = importlib.metadata.version(package_name)
        current_version = parse_version(current_version_str)
        # Get the latest version from PyPI
        response = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=5)
        response.raise_for_status()
        latest_version_str = response.json()["info"]["version"]
        latest_version = parse_version(latest_version_str)

        if latest_version > current_version:
            show_info_toast(
                parent,
                "Update Available",
                f"A new version ({latest_version_str}) of Slurm AIO is available!\n"
                f"Please run 'pip install --upgrade {package_name}' to update.",
                duration=10000,
            )
    except Exception as e:
        print(f"Failed to check for updates: {e}")


def main():
    if "linux" in platform.system().lower():
        if os.environ.get("XDG_SESSION_TYPE") != "wayland":
            try:

                temp_app = QApplication([])
                dpi_ratio = get_dpi_ratio(temp_app)
                temp_app.closeAllWindows()
                del temp_app # otherwise when the application get closed a segmentation fault is thrown

                os.environ["QT_SCALE_FACTOR"] = str(dpi_ratio)

                output = subprocess.check_output("xdpyinfo", shell=True).decode()
                match = re.search(r"resolution:\s*(\d+)x(\d+)\s*dots per inch", output)

                if match:
                    dpi_x = int(match.group(1))

                    # Map DPI to scale factor
                    dpi_scale_map = {
                        96: "1.0",  # 100%
                        108: "1.5",
                        120: "1.25",  # 125%
                        144: "0.9",  # 150%
                        168: "0.6",
                        192: "0.5",
                    }

                    closest_dpi = min(
                        dpi_scale_map.keys(), key=lambda k: abs(k - dpi_x)
                    )
                    scale = dpi_scale_map[closest_dpi]
                    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
                    os.environ["QT_FONT_DPI"] = str(closest_dpi)

                    print(f"Set scale: {scale} for DPI: {dpi_x}")
                else:
                    print("Could not determine DPI.")
            except Exception as e:
                print("Error reading DPI:", e)
        else:
            print("Wayland session detected — using automatic scaling.")
            os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    elif "darwin" in platform.system().lower():
        print("macOS detected — using automatic scaling.")
        try:

            from screeninfo import get_monitors

            monitor = get_monitors()[0]  # assume main monitor
            width_px = monitor.width
            height_px = monitor.height

            # Heuristic: macbooks are usually ~13" with 2560x1600 (Retina)
            # So we assume physical width ~11.3 inches → DPI = px / in
            estimated_width_in = 11.3
            dpi_x = width_px / estimated_width_in
            dpi_scale_map = {
                90: "0.6",  # 100%
                96: "0.7",  # 100%
                120: "0.8",  # 125%
                144: "0.9",  # 150%
                168: "1",
                192: "0.5",
            }

            closest_dpi = min(dpi_scale_map.keys(), key=lambda k: abs(k - dpi_x))
            scale = dpi_scale_map[closest_dpi]
            os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
            os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
            # os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "RoundPreferFloor"
            os.environ["QT_SCALE_FACTOR"] = f"{scale}"
            print("env variables setted")

            print(f"Set scale: {scale} for DPI: {dpi_x}")
        except Exception as e:
            print("Error reading DPI:", e)

    app = QApplication(sys.argv)
    # Get system-specific configuration directory
    config_dir_name = "SlurmAIO"
    configs_dir = (
        Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppConfigLocation
            )
        )
        / config_dir_name
    )
    if not configs_dir.is_dir():
        configs_dir = (
            Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.GenericConfigLocation
                )
            )
            / config_dir_name
        )
        if not configs_dir.is_dir():
            configs_dir = Path(script_dir) / "configs"

    settings_path = configs_dir / "settings.ini"

    if not os.path.isfile(settings_path):
        print(f"Settings file not found at: {settings_path}")

        if not configs_dir.exists():
            os.makedirs(configs_dir)
            print(f"Created configs directory at: {configs_dir}")

        shutil.copy2(default_settings_path, settings_path)
        print(f"Created settings file at: {settings_path} using defaults")

        # Set default font with fallback - let Qt handle DPI scaling
        font_families = ["Inter", "Segoe UI", "Arial", "sans-serif"]
        for family in font_families:
            font = QFont(family, 10)
            if font.exactMatch():
                app.setFont(font)
                break

        dialog = ConnectionSetupDialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            connection_details = dialog.get_connection_details()

            settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
            settings.beginGroup("GeneralSettings")
            settings.setValue("clusterAddress", connection_details["clusterAddress"])
            settings.setValue("username", connection_details["username"])
            settings.setValue("psw", connection_details["psw"])
            settings.endGroup()
            settings.sync()
            print(f"Updated settings file at: {settings_path} with user input")

            window_icon_path = os.path.join(script_dir, "src_static", "app_logo.png")
            app.setWindowIcon(QIcon(window_icon_path))
            window = SlurmJobManagerApp()
            check_for_updates(window)
            window.show()
            sys.exit(app.exec())
        else:
            print("Connection setup cancelled. Exiting.")
            sys.exit(0)
    else:
        print(f"Settings file found at: {settings_path}")

        # Set default font with fallback - let Qt handle DPI scaling
        font_families = ["Inter", "Segoe UI", "Arial", "sans-serif"]
        for family in font_families:
            font = QFont(family, 10)
            if font.exactMatch():
                app.setFont(font)
                break

        window_icon_path = os.path.join(script_dir, "src_static", "app_logo.png")
        app.setWindowIcon(QIcon(window_icon_path))
        window = SlurmJobManagerApp()
        check_for_updates(window)
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
