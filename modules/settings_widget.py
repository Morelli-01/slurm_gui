from datetime import datetime
from modules.defaults import *
from style import AppStyles
from modules.toast_notify import show_error_toast, show_info_toast, show_success_toast, show_warning_toast

class SettingsWidget(QWidget):
    def __init__(self, parent=None, flags=None):
        super().__init__(parent)
        self.setStyleSheet(AppStyles.get_complete_stylesheet(THEME_DARK))
        self.current_theme = THEME_DARK

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

        # Connection
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
        self.connection_settings_btn.setFixedWidth(180  )
        conn_layout.addRow("", self.connection_settings_btn)

        layout.addWidget(conn_group)

        # Display
        display_group = QGroupBox("Display Options")
        display_layout = QVBoxLayout(display_group)
        display_layout.setSpacing(8)

        self.jobs_queue_options_group = QGroupBox("Job Queue Columns")
        queue_layout = QGridLayout(self.jobs_queue_options_group)
        queue_layout.setSpacing(5)
        
        self._job_queue_checkboxes = []
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

        # Notifications
        notif_group = QGroupBox("Notifications")
        notif_layout = QVBoxLayout(notif_group)
        notif_layout.setSpacing(8)

        self.discord_webhook_check = QCheckBox("Enable Discord Notifications")
        self.discord_webhook_check.stateChanged.connect(self._toggle_discord_webhook)
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
        self.test_discord_btn.clicked.connect(self._test_discord_webhook)
        notif_layout.addWidget(self.test_discord_btn)

        layout.addWidget(notif_group)

        # Save All
        self.save_button = QPushButton("Save All Settings")
        self.save_button.setObjectName(BTN_GREEN)
        self.save_button.setFixedWidth(200)
        layout.addWidget(self.save_button)

        layout.addStretch()

    def _toggle_discord_webhook(self, state):
        enabled = (state == Qt.CheckState.Checked or state == 2)
        self.discord_webhook_url.setEnabled(enabled)
        self.test_discord_btn.setEnabled(enabled)

    def _test_discord_webhook(self):
        webhook_url = self.discord_webhook_url.text().strip()
        if not webhook_url:
            show_warning_toast(self, "Missing URL", "Please enter a Discord webhook URL first.")
            return
            
        try:
            import requests, json
            payload = {
                "content": "🔔 **SlurmAIO Test Notification**",
                "embeds": [{
                    "title": "Test Notification",
                    "description": "This is a test message from SlurmAIO.",
                    "color": 0x00ff00,
                    "timestamp": datetime.now().isoformat(),
                    "footer": {"text": "SlurmAIO"}
                }]
            }
            
            response = requests.post(webhook_url, data=json.dumps(payload), 
                                   headers={"Content-Type": "application/json"}, timeout=10)
            
            if response.status_code == 204:
                show_success_toast(self, "Test Successful", "Message sent to Discord!")
            else:
                show_warning_toast(self, "Test Failed", f"Status code: {response.status_code}")
                
        except ImportError:
            show_warning_toast(self, "Missing Library", "Install requests: pip install requests")
        except Exception as e:
            show_error_toast(self, "Test Failed", str(e))

    def get_notification_settings(self):
        return {
            "discord_enabled": self.discord_webhook_check.isChecked(),
            "discord_webhook_url": self.discord_webhook_url.text().strip()
        }

    def set_notification_settings(self, settings):
        self.discord_webhook_check.setChecked(settings.get("discord_enabled", False))
        self.discord_webhook_url.setText(settings.get("discord_webhook_url", ""))
        self._toggle_discord_webhook(Qt.CheckState.Checked if settings.get("discord_enabled", False) else Qt.CheckState.Unchecked)