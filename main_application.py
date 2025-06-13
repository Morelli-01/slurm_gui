from functools import partial
import os
from threading import Thread
script_dir = os.path.dirname(os.path.abspath(__file__))

import platform
from core.event_bus import EventPriority, Events, get_event_bus
from core.slurm_api import ConnectionState, SlurmAPI, SlurmWorker, refresh_func
from widgets.cluster_status_widget import ClusterStatusWidget
from core.defaults import *
system = platform.system()
if system == "Windows":
    # Windows: Use Qt's built-in high DPI handling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "RoundPreferFloor"
    os.environ["QT_FONT_DPI"] = "96"
    print("Windows: Qt DPI scaling enabled")
from widgets.job_queue_widget import JobQueueWidget 
from core.style import AppStyles
from utils import *
from pathlib import Path
import shutil
from widgets.settings_widget import SettingsWidget
from widgets.toast_widget import show_info_toast, show_success_toast, show_warning_toast, show_error_toast
import subprocess
import sys
from datetime import datetime
import re



# --- Constants ---
APP_TITLE = "SlurmAIO"
# Use percentages for responsive design - Qt handles the DPI scaling
SCREEN_WIDTH_PERCENTAGE = 0.8
SCREEN_HEIGHT_PERCENTAGE = 0.85
MIN_WIDTH_PERCENTAGE = 0.4
MIN_HEIGHT_PERCENTAGE = 0.4
REFRESH_INTERVAL_MS = 5000

# --- Helper Functions ---


def get_scaled_dimensions(screen=None):
    """Get window dimensions as device-independent pixels (Qt handles DPI automatically)"""
    if screen is None:
        screen = QApplication.primaryScreen()
    # Qt 6: geometry() returns device-independent pixels, so we don't need to worry about DPI
    geometry = screen.geometry()

    width = int(geometry.width() * SCREEN_WIDTH_PERCENTAGE)
    height = int(geometry.height() * SCREEN_HEIGHT_PERCENTAGE)
    min_width = int(geometry.width() * MIN_WIDTH_PERCENTAGE)
    min_height = int(geometry.height() * MIN_HEIGHT_PERCENTAGE)

    width = min_width = 1500
    height = min_height = 950
    return width, height, min_width, min_height


class ConnectionSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setup Initial Connection")

        # Use device-independent pixels - Qt handles DPI scaling automatically
        self.setMinimumWidth(400)
        self.setStyleSheet(AppStyles.get_dialog_styles() +
                           AppStyles.get_input_styles() +
                           AppStyles.get_button_styles())
        layout = QVBoxLayout(self)

        # Use consistent spacing in device-independent pixels
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        info_label = QLabel(
            "Settings file not found. Please enter connection details to set up the first SSH connection.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.cluster_address_input = QLineEdit()
        self.cluster_address_input.setPlaceholderText(
            "e.g., your.cluster.address")
        form_layout.addRow("Cluster Address:", self.cluster_address_input)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Your username")
        form_layout.addRow("Username:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText(
            "Your password (optional, or use key)")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Password:", self.password_input)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
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
        self.slurm_worker = SlurmWorker(self.slurm_api)
            
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
        self.main_layout.addWidget(create_separator(
            color=COLOR_DARK_BORDER if self.current_theme == THEME_DARK else COLOR_LIGHT_BORDER))

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # Create panels
        self.create_jobs_panel()
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
            show_error_toast(self, "Connection Error",
                             f"Failed to connect to the cluster: {e}. Please check settings.")
        self.slurm_worker.start()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.slurm_worker.start)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)
        # self.load_settings()


    def _event_bus_subscription(self):
        self.event_bus.subscribe(Events.DATA_READY, self.update_ui_with_data, priority=EventPriority.HIGH)
        self.event_bus.subscribe(Events.CONNECTION_STATE_CHANGED, self.set_connection_status)
        self.event_bus.subscribe(Events.CONNECTION_SAVE_REQ, self.new_connection, priority=EventPriority.LOW)

    def new_connection(self, event_data):
            self.refresh_timer.stop()
            
            self.slurm_worker.stop()
            self.slurm_worker.wait(1000)
            
            self.slurm_api = SlurmAPI.reset_instance()
            self.slurm_worker = SlurmWorker(self.slurm_api)
            try:
                self.slurm_api.connect()
            except Exception as e:
                print(f"Initial connection failed: {e}")
                show_error_toast(self, "Connection Error",
                                f"Failed to connect to the cluster: {e}. Please check settings.")
            self.slurm_worker.start()
            self.refresh_timer = QTimer(self)
            self.refresh_timer.timeout.connect(self.slurm_worker.start)
            self.refresh_timer.start(REFRESH_INTERVAL_MS)
        


    def set_connection_status(self, event_data):
        """connection status handling"""
        new_state = event_data.data["new_state"]
        old_state = event_data.data["old_state"]


        # Use device-independent icon size
        icon_size = QSize(28, 28)

        if new_state == ConnectionState.CONNECTING:
            loading_gif_path = os.path.join(
                script_dir, "src_static", "loading.gif")
            loading_movie = QMovie(loading_gif_path)
            loading_movie.setScaledSize(icon_size)
            loading_movie.start()
            self.connection_status.setMovie(loading_movie)
            self.connection_status.setText("")
            self.connection_status.setToolTip("Connecting...")
            self.connection_status.setStyleSheet("""
                QPushButton#statusButton {
                    background-color: #9e9e9e;
                    color: white;
                    border-radius: 6px;
                    font-weight: bold;
                    padding: 8px 15px;
                }
            """)
            return

        # Restore text after movie is done
        self.connection_status.setMovie(None)
        self.connection_status.setText(" Connection status...")

        if new_state == ConnectionState.CONNECTED:
            self.connection_status.setToolTip("Connected")
            good_connection_icon_path = os.path.join(
                script_dir, "src_static", "good_connection.png")
            self.connection_status.setPixmap(
                QIcon(good_connection_icon_path).pixmap(icon_size))
            self.connection_status.setStyleSheet("""
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
            """)
        else:
            self.connection_status.setToolTip("Disconnected")
            bad_connection_icon_path = os.path.join(
                script_dir, "src_static", "bad_connection.png")
            self.connection_status.setPixmap(
                QIcon(bad_connection_icon_path).pixmap(icon_size))
            self.connection_status.setStyleSheet("""
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
            """)

    def update_ui_with_data(self, event):
        """Updates the UI with new data from SLURM."""
        nodes_data = event.data["nodes"]
        queue_jobs = event.data["jobs"]
        

        # Update job queue with incremental updates
        print("Updating job queue...")
        if hasattr(self, 'job_queue_widget'):
            self.job_queue_widget.update_queue_status(queue_jobs)
        
        # Update cluster status
        print("Updating cluster status...")
        if hasattr(self, 'cluster_status_overview_widget'):
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
        scaled_pixmap = pixmap.scaled(logo_size, logo_size,
                                      Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation)
        logo_label.setPixmap(scaled_pixmap)

        nav_layout.addSpacing(25)  # Device-independent spacing

        # Navigation buttons
        button_names = ["Jobs", "Cluster Status", "Settings"]
        for i, name in enumerate(button_names):
            btn = QPushButton(name)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, index=i,
                                button=btn: self.switch_panel(index, button))
            nav_layout.addWidget(btn)
            self.nav_buttons[name] = btn

        nav_layout.addStretch()

        # Terminal button
        self.terminal_button = QPushButton("Terminal")
        self.terminal_button.setObjectName("terminalButton")
        self.terminal_button.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "terminal.svg")))
        self.terminal_button.setToolTip("Open SSH Terminal")
        self.terminal_button.clicked.connect(self.open_terminal)
        nav_layout.addWidget(self.terminal_button)

        # Connection status
        self.connection_status = ClickableLabel(" Connection status...")
        self.connection_status.setObjectName("statusButton")

        # Set initial icon - Qt handles DPI scaling for icons automatically
        initial_status_icon_path = os.path.join(
            script_dir, "src_static", "cloud_off_24dp_EA3323_FILL0_wght400_GRAD0_opsz24.png")
        # Use device-independent size - Qt scales automatically
        icon_size = QSize(28, 28)
        self.connection_status.setPixmap(
            QPixmap(initial_status_icon_path).scaled(icon_size,
                                                     Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation))
        nav_layout.addWidget(self.connection_status)

        self.main_layout.addWidget(nav_widget)

    def open_terminal(self):
        """Open a terminal with SSH connection to the cluster"""
        if not self.slurm_api or self.slurm_api.connection_status != ConnectionState.CONNECTED:
            show_warning_toast(self, "Connection Required",
                               "Please establish a SLURM connection first.")
            return

        try:
            # Get connection details
            host = self.slurm_api._config.host
            username = self.slurm_api._config.username
            password = self.slurm_api._config.password

            system = platform.system().lower()

            if system == "windows":
                self._open_windows_terminal(host, username, password)
            elif system == "darwin":  # macOS
                self._open_macos_terminal(host, username, password)
            elif system == "linux":
                self._open_linux_terminal(host, username, password)
            else:
                show_error_toast(self, "Unsupported Platform",
                                 f"Terminal opening not supported on {system}")

        except Exception as e:
            show_error_toast(self, "Terminal Error",
                             f"Failed to open terminal: {str(e)}")

    def _open_windows_terminal(self, host, username, password):
        """Open terminal on Windows using PuTTY for SSH connection"""
        try:
            # Check if putty.exe is available in common locations
            putty_paths = [
                "putty.exe",  # In PATH
                r"C:\Program Files\PuTTY\putty.exe",
                r"C:\Program Files (x86)\PuTTY\putty.exe",
                os.path.join(script_dir, "src_static",
                             "putty.exe"),  # Local copy
            ]

            putty_path = None
            for path in putty_paths:
                if shutil.which(path) or os.path.exists(path):
                    putty_path = path
                    break

            if putty_path:
                # Use PuTTY with saved session or direct connection
                putty_cmd = [
                    putty_path,
                    f"{username}@{host}",
                    "-ssh",
                    "-pw", password
                ]

                subprocess.Popen(putty_cmd)
                show_success_toast(self, "Terminal Opened",
                                   f"PuTTY SSH session opened for {username}@{host}")
            else:
                # PuTTY not found - show error with installation suggestion
                show_error_toast(self, "PuTTY Not Found",
                                 "PuTTY is required for SSH connections on Windows.\n"
                                 "Please install PuTTY from https://www.putty.org/")

        except Exception as e:
            show_error_toast(self, "Terminal Error",
                             f"Failed to open Windows terminal: {str(e)}")

    def _open_macos_terminal(self, host, username, password):
        """Open terminal on macOS using sshpass for automatic SSH login."""
        try:
            # Check if sshpass is available
            sshpass_path = shutil.which("sshpass")
            if not sshpass_path:
                show_error_toast(self, "sshpass Not Found",
                                 "sshpass is required for automatic password entry. Please install sshpass (e.g., 'brew install sshpass').")
                return

            # Build the sshpass command
            ssh_cmd = f"{sshpass_path} -p '{password}' ssh {username}@{host}"

            # List of terminal emulators to try for macOS
            terminals = [
                # Default Terminal.app
                ["open", "-a", "Terminal", f"{ssh_cmd}"],
                ["open", "-a", "iTerm", f"{ssh_cmd}"],     # iTerm2
                # AppleScript fallback
                ["osascript", "-e",
                    f'tell application "Terminal" to do script "{ssh_cmd}"'],
            ]

            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd)
                    show_success_toast(self, "Terminal Opened",
                                       f"SSH session opened for {username}@{host}")
                    return
                except FileNotFoundError:
                    continue

            # If no terminal emulator found, try AppleScript approach
            try:
                applescript = f'''
                tell application "Terminal"
                    activate
                    do script "{ssh_cmd}"
                end tell
                '''
                subprocess.Popen(["osascript", "-e", applescript])
                show_success_toast(self, "Terminal Opened",
                                   f"SSH session opened for {username}@{host}")
            except Exception as e:
                show_error_toast(self, "No Terminal Found",
                                 f"No supported terminal emulator found on this system: {str(e)}")

        except Exception as e:
            show_error_toast(self, "Terminal Error",
                             f"Failed to open macOS terminal: {str(e)}")

    def _open_linux_terminal(self, host, username, password):
        """Open terminal on Linux using sshpass for automatic SSH login."""
        try:
            # Check if sshpass is available
            sshpass_path = shutil.which("sshpass")
            if not sshpass_path:
                show_error_toast(self, "sshpass Not Found",
                                 "sshpass is required for automatic password entry. Please install sshpass (e.g., 'sudo apt install sshpass').")
                return

            # Build the sshpass command
            ssh_cmd = f"{sshpass_path} -p '{password}' ssh {username}@{host}"

            # List of terminal emulators to try
            terminals = [
                ["gnome-terminal", "--", "bash", "-c", f"{ssh_cmd}"],
                ["konsole", "-e", "bash", "-c", f"{ssh_cmd}"],
                ["xfce4-terminal", "-e", f"bash -c {ssh_cmd}"],
                ["lxterminal", "-e", f"bash -c {ssh_cmd}"],
                ["mate-terminal", "-e", f"bash -c {ssh_cmd}"],
                ["terminator", "-e", f"bash -c {ssh_cmd}"],
                ["alacritty", "-e", "bash", "-c", f"{ssh_cmd}"],
                ["kitty", "bash", "-c", f"{ssh_cmd}"],
                ["xterm", "-e", f"bash -c {ssh_cmd}"]
            ]

            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd)
                    show_success_toast(self, "Terminal Opened",
                                       f"SSH session opened for {username}@{host}")
                    return
                except FileNotFoundError:
                    continue

            show_error_toast(self, "No Terminal Found",
                             "No supported terminal emulator found on this system.")

        except Exception as e:
            show_error_toast(self, "Terminal Error",
                             f"Failed to open Linux terminal: {str(e)}")

    def _cleanup_temp_file(self, file_path):
        """Clean up temporary script files"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(
                f"Warning: Could not clean up temporary file {file_path}: {e}")

    # --- Panel Creation Methods ---

    def create_jobs_panel(self):
        """Creates the main panel for submitting and viewing jobs."""
        # self.jobs_panel = JobsPanel(slurm_connection=self.slurm_connection)
        self.jobs_panel = QFrame()
        
        self.stacked_widget.addWidget(self.jobs_panel)

    def create_cluster_panel(self):
        """Creates the panel displaying cluster status information."""
        cluster_panel = QWidget()
        cluster_layout = QVBoxLayout(cluster_panel)
        cluster_layout.setSpacing(15)  # Device-independent spacing

        # Header with refresh button
        header_layout = QHBoxLayout()
        self.cluster_label = QLabel("Cluster Status Overview")
        self.cluster_label.setObjectName("sectionTitle")
        # Use device-independent font size - Qt handles DPI scaling

        self.maintenance_label = QLabel()
        self.maintenance_label.setStyleSheet(
            "color: #FF0000;")  # Red color for warning
        self.maintenance_label.hide()  # Initially hidden
        try:
            maintenance_info = self.slurm_api.read_maintenances()
            if maintenance_info:
                # Extract maintenance details
                maintenance_details = []
                for line in maintenance_info.split('\n'):
                    if 'ReservationName=' in line:
                        name = line.split('ReservationName=')[1].split()[0]
                        start_time = line.split(" ")[1].split("=")[1]
                        end_time = line.split(" ")[2].split("=")[1]
                        time_to_maintenance = datetime.strptime(
                            start_time, "%Y-%m-%dT%H:%M:%S") - datetime.now()
                        maintenance_details.append(
                            f" in {time_to_maintenance.days} days, {time_to_maintenance.seconds//3600} hours")
                        break

                if maintenance_details:
                    self.maintenance_label.setText(
                        f"⚠️ Maintenance: {', '.join(maintenance_details)}")
                    self.maintenance_label.show()
                else:
                    self.maintenance_label.hide()
            else:
                self.maintenance_label.hide()
        except Exception as e:
            print(f"Error checking maintenance status: {e}")
            self.maintenance_label.hide()


        header_layout.addWidget(self.cluster_label)
        header_layout.addWidget(self.maintenance_label)
        header_layout.addStretch()

        self.filter_btn_by_users = ButtonGroupWidget()
        self.filter_btn_by_users.selectionChanged.connect(
            lambda text: self.filter_by_accounts(text))
        header_layout.addWidget(self.filter_btn_by_users)

        self.filter_jobs = QLineEdit()
        self.filter_jobs.setClearButtonEnabled(True)
        self.filter_jobs.setPlaceholderText("Filter jobs...")
        # Use device-independent width
        self.filter_jobs.setFixedWidth(220)
        header_layout.addWidget(self.filter_jobs)

        self.filter_jobs.textChanged.connect(
            lambda: self.job_queue_widget.filter_table(self.filter_jobs.text()))

        refresh_cluster_btn = QPushButton("Refresh Status")
        refresh_cluster_btn.clicked.connect(self.slurm_worker.start)
        header_layout.addWidget(refresh_cluster_btn)

        cluster_layout.addLayout(header_layout)

        # Main Content Layout
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)  # Device-independent spacing

        # Left Section: Job Queue
        self.job_queue_widget = JobQueueWidget()
        content_layout.addWidget(self.job_queue_widget)
        self.job_queue_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Right Section: Cluster Overview
        overview_group = QGroupBox("Real-time Usage")
        overview_layout = QVBoxLayout(overview_group)
        overview_layout.setSpacing(15)  # Device-independent spacing
        overview_group.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.cluster_status_overview_widget = ClusterStatusWidget(
            slurm_connection=self.slurm_api)
        overview_layout.addWidget(self.cluster_status_overview_widget,
                                  alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

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
    def filter_by_accounts(self, account_type):
        if account_type == "ME":
            self.job_queue_widget.filter_table_by_account(
                self.settings_panel.username.text())
        elif account_type == "ALL":
            self.job_queue_widget.filter_table_by_account("")
        elif account_type == "STUD":
            self.job_queue_widget.filter_table_by_account(STUDENTS_JOBS_KEYWORD)
        elif account_type == "PROD":
            self.job_queue_widget.filter_table_by_account(STUDENTS_JOBS_KEYWORD, negative=True)

    def closeEvent(self, event):
        """Handles the window close event."""
        # if hasattr(self, 'jobs_panel') and self.jobs_panel.project_storer:
        #     self.jobs_panel.project_storer.stop_job_monitoring()
        self.slurm_worker.stop()
        self.slurm_api.disconnect()
        print("Closing application.")
        event.accept()

    #--------------------- Styles ------------------------

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
        if hasattr(self, 'terminal_button'):
            self.terminal_button.style().unpolish(self.terminal_button)
            self.terminal_button.style().polish(self.terminal_button)
    
# --- Main Execution ---


if __name__ == "__main__":

    if "linux" in platform.system().lower():
        if os.environ.get("XDG_SESSION_TYPE") != "wayland":
            try:
                output = subprocess.check_output(
                    "xdpyinfo", shell=True).decode()
                match = re.search(
                    r"resolution:\s*(\d+)x(\d+)\s*dots per inch", output)

                if match:
                    dpi_x = int(match.group(1))

                    # Map DPI to scale factor
                    dpi_scale_map = {
                        96: "1.0",    # 100%
                        120: "1.25",  # 125%
                        144: "0.9",   # 150%
                        168: "0.6",
                        192: "0.5"
                    }

                    closest_dpi = min(dpi_scale_map.keys(),
                                      key=lambda k: abs(k - dpi_x))
                    scale = dpi_scale_map[closest_dpi]

                    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
                    os.environ["QT_SCALE_FACTOR"] = scale
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
                90: "0.6",    # 100%
                96: "0.7",    # 100%
                120: "0.8",  # 125%
                144: "0.9",   # 150%
                168: "1",
                192: "0.5"
            }

            closest_dpi = min(dpi_scale_map.keys(),
                              key=lambda k: abs(k - dpi_x))
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
    configs_dir = Path(QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation)) / config_dir_name
    if not configs_dir.is_dir():
        configs_dir = Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.GenericConfigLocation)) / config_dir_name
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

            settings = QSettings(str(settings_path),
                                 QSettings.Format.IniFormat)
            settings.beginGroup("GeneralSettings")
            settings.setValue("clusterAddress",
                              connection_details["clusterAddress"])
            settings.setValue("username", connection_details["username"])
            settings.setValue("psw", connection_details["psw"])
            settings.endGroup()
            settings.sync()
            print(f"Updated settings file at: {settings_path} with user input")

            window_icon_path = os.path.join(
                script_dir, "src_static", "app_logo.png")
            app.setWindowIcon(QIcon(window_icon_path))
            window = SlurmJobManagerApp()
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
        window.show()
        sys.exit(app.exec())
