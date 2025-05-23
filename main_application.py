from modules.job_panel import JobsPanel
from modules.defaults import *
import modules.cluster_status_widget as cluster_status_widget
from modules.job_queue_widget import JobQueueWidget
from utils import *
from pathlib import Path
import shutil
from modules.settings_widget import SettingsWidget
import sys
import slurm_connection

import threading
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QComboBox, QFrame, QSizePolicy, QStackedWidget, QFormLayout, QGroupBox,
    QTextEdit, QSpinBox, QFileDialog, QProgressBar, QMessageBox, QGridLayout, QScrollArea,
    QDialog, QDialogButtonBox
)
from PyQt6.QtGui import QIcon, QColor, QPalette, QFont, QPixmap, QMovie, QFontMetrics, QScreen
from PyQt6.QtCore import Qt, QSize, QTimer, QSettings, QStandardPaths

# Get the script directory to construct relative paths
script_dir = os.path.dirname(os.path.abspath(__file__))

# --- Constants ---
APP_TITLE = "SlurmAIO"
# Base dimensions as percentages of screen size
SCREEN_WIDTH_PERCENTAGE = 0.8  # Use 80% of screen width
SCREEN_HEIGHT_PERCENTAGE = 0.85  # Use 80% of screen height
MIN_WIDTH_PERCENTAGE = 0.6  # Minimum 60% of screen width
MIN_HEIGHT_PERCENTAGE = 0.85  # Minimum 60% of screen height
REFRESH_INTERVAL_MS = 5000  # 5 seconds


# --- Helper Functions ---
def get_dpi_aware_size(base_size, screen=None):
    """Calculate DPI-aware size based on screen DPI"""
    if screen is None:
        screen = QApplication.primaryScreen()
    
    # Get the device pixel ratio for high DPI displays
    dpr = screen.devicePixelRatio()
    
    # Get logical DPI (typical is 96 on Windows, 72 on macOS)
    logical_dpi = screen.logicalDotsPerInch()
    
    # Calculate scaling factor (96 DPI is considered 100% on most systems)
    dpi_scale = logical_dpi / 96.0
    
    # Apply both DPI scaling and device pixel ratio
    return int(base_size * dpi_scale)


def get_scaled_dimensions(screen=None):
    """Get window dimensions scaled to screen size and DPI"""
    if screen is None:
        screen = QApplication.primaryScreen()
    
    geometry = screen.geometry()
    
    # Calculate dimensions based on screen percentages
    width = int(geometry.width() * SCREEN_WIDTH_PERCENTAGE)
    height = int(geometry.height() * SCREEN_HEIGHT_PERCENTAGE)
    min_width = int(geometry.width() * MIN_WIDTH_PERCENTAGE)
    min_height = int(geometry.height() * MIN_HEIGHT_PERCENTAGE)
    
    return width, height, min_width, min_height


def show_message(parent, title, text, icon=QMessageBox.Icon.Information):
    """Displays a simple message box."""
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(icon)
    msg_box.exec()


# --- New Connection Setup Dialog ---
class ConnectionSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setup Initial Connection")
        
        # Scale dialog width based on DPI
        base_width = 400
        scaled_width = get_dpi_aware_size(base_width)
        self.setMinimumWidth(scaled_width)

        layout = QVBoxLayout(self)
        
        # Scale spacing based on DPI
        spacing = get_dpi_aware_size(10)
        layout.setSpacing(spacing)
        layout.setContentsMargins(spacing, spacing, spacing, spacing)

        info_label = QLabel(
            "Settings file not found. Please enter connection details to set up the first SSH connection.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        form_layout = QFormLayout()
        form_layout.setSpacing(get_dpi_aware_size(8))
        
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
        
        # Initialize DPI-aware dimensions
        self.setup_dpi_aware_dimensions()
        
        # The slurm_connection is initialized here
        self.slurm_connection = slurm_connection.SlurmConnection(settings_path)
        self.slurm_worker = slurm_connection.SlurmWorker(self.slurm_connection)
        self.slurm_worker.connected.connect(self.set_connection_status)
        self.slurm_worker.data_ready.connect(self.update_ui_with_data)

        # Attempt to connect immediately
        try:
            self.slurm_connection.connect()
        except Exception as e:
            print(f"Initial connection failed: {e}")
            show_message(self, "Connection Error",
                         f"Failed to connect to the cluster:\n{e}\nPlease check settings.", 
                         QMessageBox.Icon.Critical)

        self.setWindowTitle(APP_TITLE)
        
        # Set window size based on screen dimensions
        width, height, min_width, min_height = get_scaled_dimensions()
        self.resize(width, height)
        self.setMinimumSize(min_width, min_height)

        # Use relative path for the window icon
        window_icon_path = os.path.join(script_dir, "src_static", "icon3.png")
        self.setWindowIcon(QIcon(window_icon_path))

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
        
        # Scale margins and spacing
        margin = get_dpi_aware_size(10)
        spacing = get_dpi_aware_size(10)
        self.main_layout.setContentsMargins(margin, margin, margin, margin)
        self.main_layout.setSpacing(spacing)

        # --- UI Elements ---
        self.nav_buttons = {}
        self.create_navigation_bar()
        self.main_layout.addWidget(create_separator(
            color=COLOR_DARK_BORDER if self.current_theme == THEME_DARK else COLOR_LIGHT_BORDER))

        self.stacked_widget = QStackedWidget()
        self.main_layout.addWidget(self.stacked_widget)

        # Create panels (views)
        self.create_jobs_panel()
        self.create_cluster_panel()
        self.create_settings_panel()

        # --- Initialization ---
        self.update_nav_styles(self.nav_buttons["Jobs"])
        self.stacked_widget.setCurrentIndex(0)
        self.setup_refresh_timer()
        self.set_connection_status(self.slurm_connection.is_connected())
        self.refresh_all()
        self.load_settings()
    
    def setup_dpi_aware_dimensions(self):
        """Setup commonly used DPI-aware dimensions"""
        self.base_spacing = get_dpi_aware_size(5)
        self.base_margin = get_dpi_aware_size(10)
        self.icon_size_small = get_dpi_aware_size(16)
        self.icon_size_medium = get_dpi_aware_size(24)
        self.icon_size_large = get_dpi_aware_size(32)
    
    def set_connection_status(self, connected: bool, connecting=False):
        """Enhanced connection status handling"""
        if hasattr(self, "connection_status_") and self.connection_status_ == False and connected and hasattr(self, "jobs_panel"):
            self.jobs_panel.setup_project_storer()
            self._setup_job_monitoring()

        self.connection_status_ = True if connected else False
        
        # Use pre-calculated icon size
        icon_size = QSize(self.icon_size_medium, self.icon_size_medium)

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
                    border-radius: 5px;
                    font-weight: bold;
                    padding: 6px 12px;
                }
            """)
            return

        # Restore text after movie is done or connection status changes
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
                    border-radius: 5px;
                    font-weight: bold;
                    padding: 6px 12px;
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
        self.slurm_worker.start()

    def update_ui_with_data(self, nodes_data, queue_jobs):
        self.refresh_cluster_jobs_queue(queue_jobs)
        self.cluster_status_overview_widget.update_status(nodes_data, queue_jobs)

    # --- Theme Handling ---
    def change_theme(self, theme_name):
        """Applies the selected theme stylesheet."""
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.setStyleSheet(self.themes[theme_name])
            self.cluster_status_overview_widget.setStyleSheet(
                self.cluster_status_overview_widget.themes[theme_name]
            )
            self.job_queue_widget.setStyleSheet(self.themes[theme_name])
            separator_color = COLOR_DARK_BORDER if self.current_theme == THEME_DARK else COLOR_LIGHT_BORDER
            for i in range(self.main_layout.count()):
                widget = self.main_layout.itemAt(i).widget()
                if isinstance(widget, QFrame) and widget.frameShape() == QFrame.Shape.HLine:
                    widget.setStyleSheet(f"background-color: {separator_color};")
                    break
            self.update_nav_styles()
        else:
            print(f"Error: Theme '{theme_name}' not found.")

    # --- Navigation Bar ---
    def create_navigation_bar(self):
        """Creates the top navigation bar with logo, buttons, and search."""
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(self.base_spacing * 2)

        # Logo
        logo_label = QLabel()
        logo_size = self.icon_size_large
        logo_label.setFixedSize(logo_size, logo_size)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_layout.addWidget(logo_label)
        logo_path = os.path.join(script_dir, "src_static", "icon3.png")
        pixmap = QPixmap(logo_path)
        scaled_pixmap = pixmap.scaled(logo_size, logo_size, 
                                     Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
        logo_label.setPixmap(scaled_pixmap)

        nav_layout.addSpacing(self.base_spacing * 4)

        # Navigation buttons
        button_names = ["Jobs", "Cluster Status", "Settings"]
        for i, name in enumerate(button_names):
            btn = QPushButton(name)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, index=i, button=btn: self.switch_panel(index, button))
            nav_layout.addWidget(btn)
            self.nav_buttons[name] = btn

        nav_layout.addStretch()

        self.connection_status = ClickableLabel(" Connection status...")
        self.connection_status.setObjectName("statusButton")
        
        # Set initial icon
        initial_status_icon_path = os.path.join(
            script_dir, "src_static", "cloud_off_24dp_EA3323_FILL0_wght400_GRAD0_opsz24.png")
        icon_size = QSize(self.icon_size_medium, self.icon_size_medium)
        self.connection_status.setPixmap(
            QPixmap(initial_status_icon_path).scaled(icon_size, 
                                                    Qt.AspectRatioMode.KeepAspectRatio, 
                                                    Qt.TransformationMode.SmoothTransformation))
        self.connection_status.clicked.connect(self.update_connection_setting)
        nav_layout.addWidget(self.connection_status)

        self.main_layout.addWidget(nav_widget)

    def switch_panel(self, index, clicked_button):
        """Switches the visible panel in the QStackedWidget."""
        self.stacked_widget.setCurrentIndex(index)
        self.update_nav_styles(clicked_button)

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

    # --- Panel Creation Methods ---
    def create_jobs_panel(self):
        """Creates the main panel for submitting and viewing jobs."""
        self.jobs_panel = JobsPanel(slurm_connection=self.slurm_connection)
        self.stacked_widget.addWidget(self.jobs_panel)

    def create_cluster_panel(self):
        """Creates the panel displaying cluster status information."""
        cluster_panel = QWidget()
        cluster_layout = QVBoxLayout(cluster_panel)
        cluster_layout.setSpacing(self.base_spacing * 2)

        # Header with refresh button
        header_layout = QHBoxLayout()
        cluster_label = QLabel("Cluster Status Overview")
        # Scale font size based on DPI
        base_font_size = 14
        scaled_font_size = get_dpi_aware_size(base_font_size)
        cluster_label.setFont(QFont("Inter", scaled_font_size))
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
        # Scale width based on DPI
        filter_width = get_dpi_aware_size(200)
        self.filter_jobs.setFixedWidth(filter_width)
        header_layout.addWidget(self.filter_jobs)
        
        self.filter_btn = QPushButton()
        filter_icon_path = os.path.join(script_dir, "src_static", "filter.png")
        
        # Use pre-calculated icon size
        icon_size = QSize(self.icon_size_small, self.icon_size_small)
        self.filter_btn.setIcon(QIcon(filter_icon_path))
        self.filter_btn.setIconSize(icon_size)
        button_size = get_dpi_aware_size(24)
        self.filter_btn.setFixedSize(button_size, button_size)
        
        header_layout.addWidget(self.filter_btn)
        self.filter_btn.clicked.connect(
            lambda: self.job_queue_widget.filter_table(self.filter_jobs.text()))
        self.filter_jobs.textChanged.connect(
            lambda: self.job_queue_widget.filter_table(self.filter_jobs.text()))

        refresh_cluster_btn = QPushButton("Refresh Status")
        refresh_cluster_btn.clicked.connect(self.refresh_all)
        header_layout.addWidget(refresh_cluster_btn)

        cluster_layout.addLayout(header_layout)

        # --- Main Content Layout (Horizontal) ---
        content_layout = QHBoxLayout()
        content_layout.setSpacing(self.base_spacing * 2)

        # --- Left Section: Job Queue ---
        self.job_queue_widget = JobQueueWidget()
        content_layout.addWidget(self.job_queue_widget)
        self.job_queue_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # --- Right Section: Cluster Overview (Nodes Status) ---
        overview_group = QGroupBox("Real-time Usage")
        overview_layout = QVBoxLayout(overview_group)
        overview_layout.setSpacing(self.base_spacing * 2)
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
        # self.settings_panel.theme_combo.currentTextChanged.connect(self.change_theme)
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
        print("Updating connection settings...")
        self.save_settings()
        self.set_connection_status(None, connecting=True)
        thread = threading.Thread(
            target=self.slurm_connection.update_credentials_and_reconnect)
        thread.start()

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
        self.settings.setValue("theme", self.settings_panel.theme_combo.currentText())
        for i, obj in enumerate(self.settings_panel.jobs_queue_options_group.children()[1:-1]):
            self.settings.setValue(obj.objectName(), bool(obj.checkState().value))
        self.settings.endGroup()

        self.settings.sync()
        self.job_queue_widget.reload_settings_and_redraw()

    def save_settings(self):
        """Saves the current settings using QSettings."""
        print("--- Saving Settings ---")

        self.settings.beginGroup("GeneralSettings")
        self.settings.setValue("clusterAddress", self.settings_panel.cluster_address.text())
        self.settings.setValue("username", self.settings_panel.username.text())
        self.settings.setValue("psw", self.settings_panel.password.text())
        self.settings.endGroup()

        self.settings.sync()
        print("--- Settings Saved ---")

    def load_settings(self):
        """Loads settings from QSettings."""
        print("--- Loading Settings ---")

        self.settings = QSettings(str(Path("./configs/settings.ini")),
                                  QSettings.Format.IniFormat)

        self.settings.beginGroup("GeneralSettings")
        theme = self.settings.value("theme", "Dark")
        # if hasattr(self, 'settings_panel') and self.settings_panel.theme_combo:
        #     self.settings_panel.theme_combo.setCurrentText(theme)

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

        self.settings.beginGroup("AppearenceSettings")
        if hasattr(self, 'settings_panel') and self.settings_panel.jobs_queue_options_group:
            for i, obj in enumerate(self.settings_panel.jobs_queue_options_group.children()[1:-1]):
                value = self.settings.value(obj.objectName(), 'false', type=bool)
                obj.setCheckState(Qt.CheckState.Checked if value else Qt.CheckState.Unchecked)

        self.settings.endGroup()
        print("--- Settings Loaded ---")

    def _setup_job_monitoring(self):
        """Set up job status monitoring after UI initialization"""
        if hasattr(self, 'jobs_panel') and self.jobs_panel.project_storer:
            self.jobs_panel.project_storer.signals.job_status_changed.connect(self._on_global_job_status_change)
            self.jobs_panel.project_storer.signals.project_stats_changed.connect(self._on_project_stats_updated)

    def _on_global_job_status_change(self, project_name: str, job_id: str, old_status: str, new_status: str):
        """Handle global job status changes for main window notifications"""
        message = f"Job {job_id} in {project_name}: {old_status} → {new_status}"
        if hasattr(self, 'statusBar'):
            self.statusBar().showMessage(message, 5000)
        self._update_window_title()

    def _on_jobs_batch_updated(self, updated_projects: dict):
        """Handle batch job updates"""
        total_updates = sum(len(jobs) for jobs in updated_projects.values())
        if total_updates > 0:
            message = f"Updated {total_updates} jobs across {len(updated_projects)} projects"
            if hasattr(self, 'statusBar'):
                self.statusBar().showMessage(message, 3000)

    def _on_project_stats_updated(self, project_name: str, stats: dict):
        """Handle project statistics updates"""
        self._update_window_title()

    def _update_window_title(self):
        """Update window title to show active jobs count"""
        if not hasattr(self, 'jobs_panel') or not self.jobs_panel.project_storer:
            return
            
        try:
            active_jobs = self.jobs_panel.project_storer.get_active_jobs()
            active_count = len(active_jobs)
            
            base_title = APP_TITLE
            if active_count > 0:
                self.setWindowTitle(f"{base_title} - {active_count} active jobs")
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


# --- Main Execution ---
if __name__ == "__main__":
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
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
    default_settings_path = Path(script_dir) / "configs" / "default_settings.ini"

    if not os.path.isfile(settings_path):
        print(f"Settings file not found at: {settings_path}")

        if not configs_dir.exists():
            os.makedirs(configs_dir)
            print(f"Created configs directory at: {configs_dir}")

        shutil.copy2(default_settings_path, settings_path)
        print(f"Created settings file at: {settings_path} using defaults")

        app = QApplication(sys.argv)
        
        # Set default font with fallback
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

            window_icon_path = os.path.join(script_dir, "src_static", "icon3.png")
            app.setWindowIcon(QIcon(window_icon_path))
            window = SlurmJobManagerApp()
            window.show()
            sys.exit(app.exec())
        else:
            print("Connection setup cancelled. Exiting.")
            sys.exit(0)
    else:
        print(f"Settings file found at: {settings_path}")
        app = QApplication(sys.argv)
        
        # Set default font with fallback
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