from modules.defaults import *
from core.style import AppStyles

# VIEW
class SettingsView(QWidget):
    """View: Handles UI presentation"""
    
    # Signals for user actions
    connection_save_requested = pyqtSignal(dict)
    display_save_requested = pyqtSignal()
    all_save_requested = pyqtSignal()
    discord_test_requested = pyqtSignal(str)
    connection_field_changed = pyqtSignal(str, str)  # field_name, value
    job_queue_column_changed = pyqtSignal(str, bool)  # column_name, enabled
    discord_enabled_changed = pyqtSignal(bool)
    discord_url_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
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

        # Save All button
        self.save_button = QPushButton("Save All Settings")
        self.save_button.setObjectName(BTN_GREEN)
        self.save_button.setFixedWidth(200)
        layout.addWidget(self.save_button)

        layout.addStretch()
    
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
        self.discord_webhook_url.setPlaceholderText("https://discord.com/api/webhooks/...")
        self.discord_webhook_url.setEnabled(False)
        notif_layout.addWidget(self.discord_webhook_url)

        self.test_discord_btn = QPushButton("Test Discord Webhook")
        self.test_discord_btn.setObjectName(BTN_BLUE)
        self.test_discord_btn.setFixedWidth(250)
        self.test_discord_btn.setEnabled(False)
        notif_layout.addWidget(self.test_discord_btn)

        layout.addWidget(notif_group)
    
    def _connect_signals(self):
        """Connect UI signals to internal signals"""
        # Connection fields
        self.cluster_address.textChanged.connect(
            lambda text: self.connection_field_changed.emit('cluster_address', text))
        self.username.textChanged.connect(
            lambda text: self.connection_field_changed.emit('username', text))
        self.password.textChanged.connect(
            lambda text: self.connection_field_changed.emit('password', text))
        
        # Job queue checkboxes - state is an int (0=unchecked, 2=checked)
        for checkbox in self._job_queue_checkboxes:
            checkbox.stateChanged.connect(
                lambda state, name=checkbox.objectName(): 
                self.job_queue_column_changed.emit(name, bool(state)))
        
        # Discord settings - state is an int (0=unchecked, 2=checked)
        self.discord_webhook_check.stateChanged.connect(
            lambda state: self.discord_enabled_changed.emit(bool(state)))
        self.discord_webhook_url.textChanged.connect(self.discord_url_changed.emit)
        
        # Buttons
        self.connection_settings_btn.clicked.connect(self._emit_connection_save)
        self.save_appearance_btn.clicked.connect(self.display_save_requested.emit)
        self.save_button.clicked.connect(self.all_save_requested.emit)
        self.test_discord_btn.clicked.connect(self._emit_discord_test)
        
        # Discord enable/disable toggle
        self.discord_webhook_check.stateChanged.connect(self._toggle_discord_webhook)
    
    def _emit_connection_save(self):
        """Emit connection save signal with current values"""
        settings = {
            'cluster_address': self.cluster_address.text().strip(),
            'username': self.username.text().strip(),
            'password': self.password.text().strip()
        }
        self.connection_save_requested.emit(settings)
    
    def _emit_discord_test(self):
        """Emit discord test signal with current URL"""
        self.discord_test_requested.emit(self.discord_webhook_url.text().strip())
    
    def _toggle_discord_webhook(self, state):
        """Enable/disable Discord webhook controls"""
        enabled = (state == Qt.CheckState.Checked or state == 2)
        self.discord_webhook_url.setEnabled(enabled)
        self.test_discord_btn.setEnabled(enabled)
    
    # Public methods to update UI from model
    def update_connection_settings(self, settings):
        """Update connection UI from settings"""
        self.cluster_address.setText(settings.get('cluster_address', ''))
        self.username.setText(settings.get('username', ''))
        self.password.setText(settings.get('password', ''))
    
    def update_display_settings(self, settings):
        """Update display UI from settings"""
        job_queue_columns = settings.get('job_queue_columns', {})
        for checkbox in self._job_queue_checkboxes:
            field_name = checkbox.objectName()
            enabled = job_queue_columns.get(field_name, True)
            checkbox.setChecked(enabled)
    
    def update_notification_settings(self, settings):
        """Update notification UI from settings"""
        discord_enabled = settings.get('discord_enabled', False)
        discord_url = settings.get('discord_webhook_url', '')
        
        self.discord_webhook_check.setChecked(discord_enabled)
        self.discord_webhook_url.setText(discord_url)
        self._toggle_discord_webhook(Qt.CheckState.Checked if discord_enabled else Qt.CheckState.Unchecked)

