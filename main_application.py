import os
# os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
# os.environ["QT_SCALE_FACTOR"] = "1"
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

from threading import Thread

import PyQt6.QtCore as Qt
from modules.defaults import *
from modules.job_panel import JobsPanel
import modules.cluster_status_widget as cluster_status_widget
from modules.job_queue_widget import JobQueueWidget
import slurm_connection
from style import AppStyles
from utils import *
from pathlib import Path
import shutil
from modules.settings_widget import SettingsWidget
from modules.toast_notify import show_info_toast, show_success_toast, show_warning_toast, show_error_toast
from modules.project_store import ProjectStore
import platform
import subprocess
import random
import threading
import tempfile
import sys
from utils import script_dir, except_utility_path, plink_utility_path, tmux_utility_path

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
        self.slurm_connection = slurm_connection.SlurmConnection(settings_path)
        self.slurm_worker = slurm_connection.SlurmWorker(self.slurm_connection)
        self.slurm_worker.connected.connect(self.set_connection_status)
        self.slurm_worker.data_ready.connect(self.update_ui_with_data)

        # Attempt to connect immediately
        try:
            self.slurm_connection.connect()
        except Exception as e:
            print(f"Initial connection failed: {e}")
            show_error_toast(self, "Connection Error",
                             f"Failed to connect to the cluster: {e}. Please check settings.")

        self.setWindowTitle(APP_TITLE)

        # Set window size - Qt 6 handles DPI scaling automatically
        width, height, min_width, min_height = get_scaled_dimensions()
        self.resize(width, height)
        self.setMinimumSize(min_width, min_height)

        # Set window icon
        window_icon_path = os.path.join(script_dir, "src_static", "icon3.png")
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
        self.setup_refresh_timer()
        self.set_connection_status(self.slurm_connection.is_connected())
        self.refresh_all()
        self.load_settings()

    def set_connection_status(self, connected: bool, connecting=False):
        """Enhanced connection status handling with proper project store recovery"""
        previous_status = getattr(self, 'connection_status_', None)

        if previous_status == False and connected:
            print("Connection restored - reinitializing project store and jobs panel")
            self._handle_connection_recovery()

        self.connection_status_ = True if connected else False

        # Use device-independent icon size
        icon_size = QSize(28, 28)

        if connecting:
            loading_gif_path = os.path.join(script_dir, "src_static", "loading.gif")
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

        if connected:
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

    def _handle_connection_recovery(self):
        """Handle complete recovery when connection is restored"""
        try:
            # Step 1: Reinitialize the project store
            print("Reinitializing project store...")
            if hasattr(self, 'jobs_panel'):
                # Stop existing job monitoring if any
                if self.jobs_panel.project_storer:
                    self.jobs_panel.project_storer.stop_job_monitoring()

                # Create new project store with restored connection
                self.jobs_panel.project_storer = ProjectStore(
                    self.slurm_connection)
                self.jobs_panel._connect_project_store_signals()
                print("Project store reinitialized successfully")

                # Step 2: Reload projects and jobs
                print("Reloading projects...")
                self._reload_projects_after_reconnection()

            else:
                print("No jobs panel found - this shouldn't happen")

        except Exception as e:
            print(f"Error during connection recovery: {e}")
            import traceback
            traceback.print_exc()

            # Show error to user
            show_error_toast(self, "Recovery Error",
                             f"Failed to restore project data after reconnection: {str(e)}")

    def _reload_projects_after_reconnection(self):
        """Reload all projects and their jobs after connection recovery"""
        try:
            if not hasattr(self, 'jobs_panel') or not self.jobs_panel.project_storer:
                return

            # Get all projects from the restored project store
            project_names = self.jobs_panel.project_storer.all_projects()
            print(f"Found {len(project_names)} projects to reload")

            # Clear existing project widgets
            self._clear_existing_projects()

            # Reload each project
            for project_name in project_names:
                print(f"Reloading project: {project_name}")

                # Add project widget back to UI
                self.jobs_panel.project_group.add_new_project(project_name)

                # Get project data
                project = self.jobs_panel.project_storer.get(project_name)
                if project and project.jobs:
                    # Convert jobs to table rows
                    job_rows = [job.to_table_row() for job in project.jobs]

                    # Update jobs UI
                    self.jobs_panel.jobs_group.update_jobs(
                        project_name, job_rows)

                    # Update project status counts
                    if project_name in self.jobs_panel.project_group.projects_children:
                        project_widget = self.jobs_panel.project_group.projects_children[
                            project_name]
                        if hasattr(project_widget, 'update_status_counts'):
                            job_stats = project.get_job_stats()
                            project_widget.update_status_counts(job_stats)

            # Select the first project if available
            if project_names:
                first_project = project_names[0]
                self.jobs_panel.project_group.handle_project_selection(
                    first_project)
                self.jobs_panel.on_project_selected(first_project)
                self.jobs_panel.jobs_group.show_project(first_project)
                print(f"Selected project: {first_project}")

            print("Project reload completed successfully")
            show_success_toast(self, "Connection Restored",
                               f"")

        except Exception as e:
            print(f"Error reloading projects: {e}")
            import traceback
            traceback.print_exc()
            show_error_toast(self, "Reload Error",
                             f"Failed to reload projects: {str(e)}")

    def _clear_existing_projects(self):
        """Clear existing project widgets from the UI"""
        try:
            if not hasattr(self, 'jobs_panel'):
                return

            # Clear project group widgets
            project_group = self.jobs_panel.project_group

            # Remove all project widgets from the scroll area
            for project_name in list(project_group.projects_children.keys()):
                project_widget = project_group.projects_children[project_name]
                project_group.scroll_content_layout.removeWidget(
                    project_widget)
                project_widget.hide()
                project_widget.deleteLater()

            # Clear the projects dictionary
            project_group.projects_children.clear()
            project_group.project_counter = 0
            project_group._selected_project_widget = None

            # Clear jobs group
            for project_name in list(self.jobs_panel.jobs_group._indices.keys()):
                self.jobs_panel.jobs_group.remove_project(project_name)

            print("Cleared existing project widgets")

        except Exception as e:
            print(f"Error clearing existing projects: {e}")
            import traceback
            traceback.print_exc()

    def setup_refresh_timer(self):
        """Sets up the timer for automatic data refreshing."""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_all)
        self.refresh_timer.start(REFRESH_INTERVAL_MS)

    def refresh_all(self):
        self.slurm_worker.start()
        t = Thread(target=self.set_connection_status(
            self.slurm_connection.is_connected()))
        t.start()

    def update_ui_with_data(self, nodes_data, queue_jobs):
        # Add connection check
        if not self.slurm_connection.check_connection():
            # Show error messages instead of updating with empty data
            # Will trigger connection error display
            self.job_queue_widget.update_queue_status([])
            self.cluster_status_overview_widget.update_status(
                None, [])  # Will trigger connection error display

            # Update jobs panels to show connection error
            if hasattr(self, 'jobs_panel') and self.jobs_panel.jobs_group:
                for project_name in self.jobs_panel.project_group.projects_children.keys():
                    self.jobs_panel.jobs_group.show_connection_error(
                        project_name)
            return

        # Normal update if connection is good
        self.refresh_cluster_jobs_queue(queue_jobs)
        self.cluster_status_overview_widget.update_status(
            nodes_data, queue_jobs)

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
        
        logo_path = os.path.join(script_dir, "src_static", "icon3.png")
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
        self.connection_status.clicked.connect(self.update_connection_setting)
        nav_layout.addWidget(self.connection_status)

        self.main_layout.addWidget(nav_widget)

    def open_terminal(self):
        """Open a terminal with SSH connection to the cluster"""
        if not self.slurm_connection or not self.slurm_connection.check_connection():
            show_warning_toast(self, "Connection Required",
                               "Please establish a SLURM connection first.")
            return

        try:
            # Get connection details
            host = self.slurm_connection.host
            username = self.slurm_connection.user
            password = self.slurm_connection.password

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

    def _create_expect_script(self, host, username, password):
        """Create an expect script for automatic password authentication"""
        script_content = f'''#!{except_utility_path} -f
set timeout 30
spawn ssh {username}@{host}
expect {{
    "password:" {{
        send "{password}\\r"
        interact
    }}
    "yes/no" {{
        send "yes\\r"
        expect "password:"
        send "{password}\\r"
        interact
    }}
    timeout {{
        puts "Connection timeout"
        exit 1
    }}
    eof {{
        puts "Connection failed"
        exit 1
    }}
}}
'''

        # Create temporary expect script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.exp', delete=False) as f:
            f.write(script_content)
            script_path = f.name

        # Make script executable
        os.chmod(script_path, 0o755)
        return script_path

    def _open_windows_terminal(self, host, username, password):
        """Open terminal on Windows using plink for direct password authentication"""
        try:
            # Check if plink is available
            plink_path = plink_utility_path

            if plink_path:
                cmd = [
                    plink_path,
                    "-ssh",           # Use SSH protocol
                    # Non-interactive (don't prompt for anything)
                    "-batch",
                    "-pw", password,  # Provide password directly
                    f"{username}@{host}"
                ]

                try:
                    # Try Windows Terminal first
                    wt_cmd = ["wt.exe", "new-tab",
                              "--title", f"SSH - {host}"] + cmd
                    subprocess.Popen(
                        wt_cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    show_success_toast(self, "Terminal Opened",
                                       f"SSH terminal opened for {username}@{host}")
                    return
                except FileNotFoundError:
                    # Fallback to cmd.exe
                    cmd_command = ["cmd.exe", "/c",
                                   "start", "cmd.exe", "/k"] + cmd
                    subprocess.Popen(cmd_command)
                    show_success_toast(self, "Terminal Opened",
                                       f"SSH session opened for {username}@{host}")
                    return
            else:
                # Plink not found - suggest installation or use basic SSH
                self._open_windows_terminal_fallback(host, username, password)

        except Exception as e:
            show_error_toast(self, "Terminal Error",
                             f"Failed to open Windows terminal: {str(e)}")

    def _open_windows_terminal_fallback(self, host, username, password):
        """Fallback method when plink is not available"""
        try:
            # Create a simple batch file for SSH connection
            import tempfile

            batch_content = f'''@echo off
    title SSH - {host}
    echo Connecting to {username}@{host}...
    echo.
    echo Note: For automatic password entry, install PuTTY/plink
    echo Download from: https://www.putty.org/
    echo.
    ssh {username}@{host}
    echo.
    echo Connection closed. Press any key to exit...
    pause >nul
    '''

            # Create temporary batch file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False) as f:
                f.write(batch_content)
                batch_path = f.name

            try:
                # Try Windows Terminal first
                wt_cmd = ["wt.exe", "new-tab", "--title",
                          f"SSH - {host}", "cmd.exe", "/c", batch_path]
                subprocess.Popen(wt_cmd)
                show_info_toast(self, "Terminal Opened",
                                f"SSH terminal opened. Install PuTTY for automatic password entry.")
            except FileNotFoundError:
                # Fallback to cmd.exe
                subprocess.Popen(
                    ["cmd.exe", "/c", "start", "cmd.exe", "/c", batch_path])
                show_info_toast(self, "Terminal Opened",
                                f"SSH session opened. Install PuTTY for automatic password entry.")

            # Clean up batch file after delay
            QTimer.singleShot(
                30000, lambda: self._cleanup_temp_file(batch_path))

        except Exception as e:
            show_error_toast(self, "Terminal Error",
                             f"Failed to open terminal: {str(e)}")

    def _open_macos_terminal(self, host, username, password):
        """Open terminal on macOS with tmux session for SSH connection"""
        try:
            # Create tmux session for SSH connection
            session_name = f"slurm_{random.randint(1000, 9999)}"

            # Create tmux session and send SSH commands
            tmux_commands = [
                f"{tmux_utility_path} new-session -d -s {session_name}",
                f"{tmux_utility_path} send-keys -t {session_name} 'ssh {username}@{host}' Enter",
                f"sleep 2",  # Wait for SSH prompt
                f"{tmux_utility_path} send-keys -t {session_name} '{password}' Enter",
            ]

            # Use AppleScript to open Terminal and attach to tmux session
            applescript = f'''
            tell application "Terminal"
                activate
                do script "{'; '.join(tmux_commands)}; {tmux_utility_path} attach -t {session_name}"
            end tell
            '''
            subprocess.Popen(["osascript", "-e", applescript])

            show_success_toast(self, "Terminal Opened",
                               f"Tmux session opened for {username}@{host}")

        except Exception as e:
            show_error_toast(self, "Terminal Error",
                             f"Failed to open macOS terminal: {str(e)}")

    def _open_linux_terminal(self, node_name, username, password):
        """Open terminal on Linux with tmux session for chained SSH: first to head node, then to compute node"""
        try:
            # Create tmux session for chained SSH connection
            head_node = self.slurm_connection.host
            session_name = f"slurm_{random.randint(1000, 9999)}"

            # Create tmux session and send SSH commands
            tmux_commands = [
                f"{tmux_utility_path} new-session -d -s {session_name}",
                f"{tmux_utility_path} send-keys -t {session_name} 'ssh {username}@{head_node}' Enter",
                f"sleep 2",  # Wait for SSH prompt
                f"{tmux_utility_path} send-keys -t {session_name} '{password}' Enter",
            ]

            # List of terminal emulators to try with tmux
            terminals = [
                ["gnome-terminal", "--", "bash", "-c",
                    f"{'; '.join(tmux_commands)}; {tmux_utility_path} attach -t {session_name}; exec bash"],
                ["konsole", "-e", "bash", "-c",
                    f"{'; '.join(tmux_commands)}; {tmux_utility_path} attach -t {session_name}; exec bash"],
                ["xfce4-terminal", "-e",
                    f"bash -c '{'; '.join(tmux_commands)}; {tmux_utility_path} attach -t {session_name}; exec bash'"],
                ["lxterminal", "-e",
                    f"bash -c '{'; '.join(tmux_commands)}; {tmux_utility_path} attach -t {session_name}; exec bash'"],
                ["mate-terminal", "-e",
                    f"bash -c '{'; '.join(tmux_commands)}; {tmux_utility_path} attach -t {session_name}; exec bash'"],
                ["terminator", "-e",
                    f"bash -c '{'; '.join(tmux_commands)}; {tmux_utility_path} attach -t {session_name}; exec bash'"],
                ["alacritty", "-e", "bash", "-c",
                    f"{'; '.join(tmux_commands)}; {tmux_utility_path} attach -t {session_name}; exec bash"],
                ["kitty", "bash", "-c",
                    f"{'; '.join(tmux_commands)}; {tmux_utility_path} attach -t {session_name}; exec bash"],
                ["xterm", "-e",
                    f"bash -c '{'; '.join(tmux_commands)}; {tmux_utility_path} attach -t {session_name}; exec bash'"]
            ]

            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd)
                    show_success_toast(self, "Terminal Opened",
                                       f"Tmux session opened: {head_node}")
                    return
                except FileNotFoundError:
                    continue

            # If no terminal emulator found
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
    # --- Panel Creation Methods ---

    def create_jobs_panel(self):
        """Creates the main panel for submitting and viewing jobs."""
        self.jobs_panel = JobsPanel(slurm_connection=self.slurm_connection)
        self.stacked_widget.addWidget(self.jobs_panel)

    def create_cluster_panel(self):
        """Creates the panel displaying cluster status information."""
        cluster_panel = QWidget()
        cluster_layout = QVBoxLayout(cluster_panel)
        cluster_layout.setSpacing(15)  # Device-independent spacing

        # Header with refresh button
        header_layout = QHBoxLayout()
        cluster_label = QLabel("Cluster Status Overview")
        # Use device-independent font size - Qt handles DPI scaling
        cluster_label.setFont(QFont("Inter", 16))
        cluster_label.setStyleSheet("font-weight: bold;")

        header_layout.addWidget(cluster_label)
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
        refresh_cluster_btn.clicked.connect(self.refresh_all)
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

        self.cluster_status_overview_widget = cluster_status_widget.ClusterStatusWidget(
            slurm_connection=self.slurm_connection)
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
        self.settings_panel.save_appearance_btn.clicked.connect(
            self.save_appearence_settings)
        self.settings_panel.connection_settings_btn.clicked.connect(
            self.update_connection_setting)
        self.settings_panel.save_button.clicked.connect(self.save_settings)
        self.stacked_widget.addWidget(self.settings_panel)

    # --- Action & Data Methods ---
    def filter_by_accounts(self, account_type):
        if account_type == "ME":
            self.job_queue_widget.filter_table(
                self.settings_panel.username.text())
        elif account_type == "ALL":
            self.job_queue_widget.filter_table("")
        elif account_type == "STUD":
            self.job_queue_widget.filter_table_by_list(STUDENTS_JOBS_KEYWORD)
        elif account_type == "PROD":
            self.job_queue_widget.filter_table_by_negative_keywords(
                STUDENTS_JOBS_KEYWORD)

    def update_connection_setting(self):
        """Enhanced connection update with proper project store reinitialization"""
        print("Updating connection settings...")

        # Save settings first
        self.save_settings()

        # Show connecting status
        self.set_connection_status(None, connecting=True)

        # Run connection update in a separate thread to avoid blocking UI
        def connection_update_worker():
            try:
                # Update credentials and reconnect
                self.slurm_connection.update_credentials_and_reconnect()

                # Check if connection was successful
                if self.slurm_connection.check_connection():
                    print("Connection update successful")

                    # Use QTimer to safely update UI from main thread
                    QTimer.singleShot(
                        0, lambda: self._finalize_connection_update(True))
                else:
                    print("Connection update failed")
                    QTimer.singleShot(
                        0, lambda: self._finalize_connection_update(False))

            except Exception as e:
                print(f"Error during connection update: {e}")
                QTimer.singleShot(
                    0, lambda: self._finalize_connection_update(False, str(e)))

        # Start the worker thread
        thread = threading.Thread(target=connection_update_worker)
        thread.daemon = True
        thread.start()

    def _finalize_connection_update(self, success, error_message=None):
        """Finalize the connection update on the main thread"""
        if success:
            # Update connection status
            self.set_connection_status(True)

            # Reinitialize project store if we have a jobs panel
            if hasattr(self, 'jobs_panel'):
                try:
                    self.jobs_panel.setup_project_storer()
                    show_success_toast(self, "Connection Updated",
                                       "SLURM connection updated successfully!")
                except Exception as e:
                    print(f"Error setting up project store: {e}")
                    show_error_toast(self, "Setup Error",
                                     f"Connection established but failed to setup projects: {str(e)}")
            else:
                show_success_toast(self, "Connection Updated",
                                   "SLURM connection updated successfully!")
        else:
            # Update connection status to disconnected
            self.set_connection_status(False)

            error_msg = "Failed to update SLURM connection."
            if error_message:
                error_msg += f" Error: {error_message}"

            show_error_toast(self, "Connection Failed", error_msg)

    def refresh_cluster_jobs_queue(self, queue_jobs=None):
        """Refreshes the cluster status widgets (demo)."""
        print("Refreshing cluster status...")
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
        for i, obj in enumerate(self.settings_panel.jobs_queue_options_group.children()[1:-1]):
            self.settings.setValue(
                obj.objectName(), bool(obj.checkState().value))
        self.settings.endGroup()

        self.settings.sync()
        self.job_queue_widget.reload_settings_and_redraw()

    def save_settings(self):
        """Saves the current settings using QSettings."""
        print("--- Saving Settings ---")

        # Save general settings (SLURM connection)
        self.settings.beginGroup("GeneralSettings")
        self.settings.setValue(
            "clusterAddress", self.settings_panel.cluster_address.text())
        self.settings.setValue("username", self.settings_panel.username.text())
        self.settings.setValue("psw", self.settings_panel.password.text())
        self.settings.endGroup()

        # Save notification settings (including Discord webhook)
        self.settings.beginGroup("NotificationSettings")
        notification_settings = self.settings_panel.get_notification_settings()
        self.settings.setValue(
            "discord_enabled", notification_settings["discord_enabled"])
        self.settings.setValue("discord_webhook_url",
                               notification_settings["discord_webhook_url"])
        self.settings.endGroup()

        self.settings.sync()
        print("--- Settings Saved ---")

    def load_settings(self):
        """Loads settings from QSettings."""
        print("--- Loading Settings ---")

        self.settings = QSettings(str(Path("./configs/settings.ini")),
                                  QSettings.Format.IniFormat)

        # Load general settings
        self.settings.beginGroup("GeneralSettings")
        theme = self.settings.value("theme", "Dark")

        cluster_address = self.settings.value("clusterAddress", "")
        if hasattr(self, 'settings_panel') and self.settings_panel.cluster_address:
            self.settings_panel.cluster_address.setText(cluster_address)

        username = self.settings.value("username", "")
        if hasattr(self, 'settings_panel') and self.settings_panel.username:
            self.settings_panel.username.setText(username)

        cluster_psw = self.settings.value("psw", "")
        if hasattr(self, 'settings_panel') and self.settings_panel.password:
            self.settings_panel.password.setText(cluster_psw)
        self.settings.endGroup()

        # Load appearance settings (jobs queue options)
        self.settings.beginGroup("AppearenceSettings")
        if hasattr(self, 'settings_panel') and self.settings_panel.jobs_queue_options_group:
            for i, obj in enumerate(self.settings_panel.jobs_queue_options_group.children()[1:-1]):
                value = self.settings.value(
                    obj.objectName(), 'false', type=bool)
                obj.setCheckState(
                    Qt.CheckState.Checked if value else Qt.CheckState.Unchecked)
        self.settings.endGroup()

        # Load notification settings (including Discord webhook)
        self.settings.beginGroup("NotificationSettings")
        notification_settings = {
            "discord_enabled": self.settings.value("discord_enabled", False, type=bool),
            "discord_webhook_url": self.settings.value("discord_webhook_url", "", type=str)
        }

        # Apply notification settings to the settings panel
        if hasattr(self, 'settings_panel'):
            self.settings_panel.set_notification_settings(
                notification_settings)
        self.settings.endGroup()

        print("--- Settings Loaded ---")

    def _update_window_title(self):
        """Update window title to show active jobs count"""
        if not hasattr(self, 'jobs_panel') or not self.jobs_panel.project_storer:
            return

        try:
            active_jobs = self.jobs_panel.project_storer.get_active_jobs()
            active_count = len(active_jobs)

            base_title = APP_TITLE
            if active_count > 0:
                self.setWindowTitle(
                    f"{base_title} - {active_count} active jobs")
            else:
                self.setWindowTitle(base_title)
        except Exception as e:
            print(f"Error updating window title: {e}")

    def closeEvent(self, event):
        """Handles the window close event."""
        if hasattr(self, 'jobs_panel') and self.jobs_panel.project_storer:
            self.jobs_panel.project_storer.stop_job_monitoring()

        self.slurm_connection.close()
        print("Closing application.")
        event.accept()
    
    def apply_theme(self):
        """Apply the current theme using centralized styles"""
        stylesheet = AppStyles.get_complete_stylesheet(self.current_theme)
        self.setStyleSheet(stylesheet)

# --- Main Execution ---

if __name__ == "__main__":
    # Simple DPI handling - let Qt handle it automatically
    # QApplication.setHighDpiScaleFactorRoundingPolicy(
    #     Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

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
                script_dir, "src_static", "icon3.png")
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

        window_icon_path = os.path.join(script_dir, "src_static", "icon3.png")
        app.setWindowIcon(QIcon(window_icon_path))
        window = SlurmJobManagerApp()
        window.show()
        sys.exit(app.exec())