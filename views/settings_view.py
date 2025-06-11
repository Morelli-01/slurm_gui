from functools import partial
from pathlib import Path
from core.event_bus import Events, get_event_bus
from modules.defaults import *
from core.style import AppStyles
from utils import settings_path
# VIEW


class SettingsView(QWidget):
    """View: Handles UI presentation"""

    # Signals for user actions
    discord_test_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.event_bus = get_event_bus()
        self.setStyleSheet(AppStyles.get_complete_stylesheet(THEME_DARK))
        self._job_queue_checkboxes = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Create and layout UI components"""
        # Main scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        main_layout.addWidget(scroll)

        # Content widget with fixed width
        content = QWidget()
        content.setMinimumWidth(500)
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Connection section
        self._setup_connection_section(layout)

        # Display section
        self._setup_display_section(layout)

        # Notifications section
        self._setup_notifications_section(layout)

        layout.addStretch()
        self.load_settings()

    def _setup_connection_section(self, layout):
        """Setup connection settings section"""
        conn_group = QGroupBox("SLURM Connection")
        conn_layout = QFormLayout(conn_group)
        conn_layout.setSpacing(8)

        self.cluster_address = QLineEdit()
        self.cluster_address.setFixedHeight(30)
        self.cluster_address.setPlaceholderText("cluster.example.com")
        conn_layout.addRow("Address:", self.cluster_address)

        self.username = QLineEdit()
        self.username.setFixedHeight(30)
        self.username.setPlaceholderText("username")
        conn_layout.addRow("Username:", self.username)

        self.password = QLineEdit()
        self.password.setFixedHeight(30)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("password")
        conn_layout.addRow("Password:", self.password)

        self.connection_settings_btn = QPushButton("Save Connection")
        self.connection_settings_btn.setObjectName(BTN_GREEN)
        self.connection_settings_btn.setFixedWidth(180)
        conn_layout.addRow("", self.connection_settings_btn)

        layout.addWidget(conn_group)

    def _setup_display_section(self, layout):
        """Setup display settings section"""
        display_group = QGroupBox("Display Options")
        display_layout = QVBoxLayout(display_group)
        display_layout.setSpacing(8)

        self.jobs_queue_options_group = QGroupBox("Job Queue Columns")
        queue_layout = QGridLayout(self.jobs_queue_options_group)
        queue_layout.setSpacing(5)

        for i, label in enumerate(JOB_QUEUE_FIELDS):
            if label:
                checkbox = QCheckBox(label)
                checkbox.setObjectName(label)
                row, col = divmod(i, 3)
                queue_layout.addWidget(checkbox, row, col)
                self._job_queue_checkboxes.append(checkbox)

        display_layout.addWidget(self.jobs_queue_options_group)

        self.save_appearance_btn = QPushButton("Save Display Settings")
        self.save_appearance_btn.setObjectName(BTN_GREEN)
        self.save_appearance_btn.setFixedWidth(250)
        display_layout.addWidget(self.save_appearance_btn)

        layout.addWidget(display_group)

    def _setup_notifications_section(self, layout):
        """Setup notifications settings section"""
        notif_group = QGroupBox("Notifications")
        notif_layout = QVBoxLayout(notif_group)
        notif_layout.setSpacing(8)

        self.discord_webhook_check = QCheckBox("Enable Discord Notifications")
        notif_layout.addWidget(self.discord_webhook_check)

        self.discord_webhook_url = QLineEdit()
        self.discord_webhook_url.setFixedHeight(30)
        self.discord_webhook_url.setPlaceholderText(
            "https://discord.com/api/webhooks/...")
        # self.discord_webhook_url.setEnabled(False)
        notif_layout.addWidget(self.discord_webhook_url)

        self.test_discord_btn = QPushButton("Test Discord Webhook")
        self.test_discord_btn.setObjectName(BTN_BLUE)
        self.test_discord_btn.setFixedWidth(250)
        # self.test_discord_btn.setEnabled(False)
        notif_layout.addWidget(self.test_discord_btn)

        layout.addWidget(notif_group)

    def _connect_signals(self):
        """Connect UI signals to internal signals"""

        self.connection_settings_btn.clicked.connect(
            self._emit_connection_save)
        self.save_appearance_btn.clicked.connect(self._emit_display_opt_save)
        self.discord_webhook_check.stateChanged.connect(
            self._emit_noti_opt_save)
        self.discord_webhook_url.textChanged.connect(self._emit_noti_opt_save)
        self.test_discord_btn.clicked.connect(self._emit_discord_test)


    def _emit_connection_save(self):
        """Emit connection save signal with current values"""
        settings = {
            'cluster_address': self.cluster_address.text().strip(),
            'username': self.username.text().strip(),
            'password': self.password.text().strip()
        }
        self.event_bus.emit(
            Events.CONNECTION_SAVE_REQ,
            {"settings": settings},
            source="settings.view"
        )

    def _emit_display_opt_save(self):
        print(" --- Saving Display Settings --- ")
        display_settings = {}
        for checkbox in self._job_queue_checkboxes:
            display_settings[checkbox.objectName()] = bool(checkbox.checkState().value)
        
        self.event_bus.emit(Events.DISPLAY_SAVE_REQ,
                            data={"display_settings": display_settings},
                            source="settings.view")

    def _emit_discord_test(self):
        """Emit discord test signal with current URL"""
        self.discord_test_requested.emit(
            self.discord_webhook_url.text().strip())
    
    def _emit_noti_opt_save(self, *args):
        notification_settings = {
            "discord_enabled":bool(self.discord_webhook_check.checkState().value),
            "discord_webhook_url": self.discord_webhook_url.text()
        }
        self.event_bus.emit(Events.NOTIF_SAVE_REQ, notification_settings, source="settings.view")

    def load_settings(self):
        """Loads settings from QSettings."""
        print("--- Loading Settings ---")

        self.settings = QSettings(str(Path(settings_path)),
                                  QSettings.Format.IniFormat)

        # Load general settings
        self.settings.beginGroup("GeneralSettings")

        cluster_address = self.settings.value("clusterAddress", "")
        self.cluster_address.setText(cluster_address)

        username = self.settings.value("username", "")
        self.username.setText(username)

        psw = self.settings.value("psw", "")
        self.password.setText(psw)
        self.settings.endGroup()

        # Load appearance settings (jobs queue options)
        self.settings.beginGroup("AppearenceSettings")
        for i, obj in enumerate(self._job_queue_checkboxes):
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
        self.discord_webhook_check.setChecked(notification_settings["discord_enabled"])
        self.discord_webhook_url.setText(notification_settings["discord_webhook_url"])
        self.settings.endGroup()

        print("--- Settings Loaded ---")
