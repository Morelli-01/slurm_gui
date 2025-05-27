from datetime import datetime
from modules.defaults import *
from style import AppStyles
from modules.toast_notify import show_error_toast, show_info_toast, show_success_toast, show_warning_toast

class SettingsWidget(QWidget):
    def __init__(self, parent=None, flags=None):
        super().__init__(parent)
        self.setStyleSheet(AppStyles.get_complete_stylesheet(THEME_DARK))
        self.current_theme = THEME_DARK

        settings_layout = QVBoxLayout(self)
        settings_layout.setContentsMargins(25, 25, 25, 25)

        # Title
        settings_label = QLabel("Application Settings")
        settings_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        settings_layout.addWidget(settings_label)

        # --- Appearance Section ---
        appearance_group = QGroupBox("Display Options")
        appearance_layout = QFormLayout(appearance_group)
        appearance_layout.setSpacing(10)
        appearance_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.jobs_queue_options_group = QGroupBox("Jobs Queue Visible Columns")
        jobs_queue_layout = QGridLayout(self.jobs_queue_options_group)
        self._job_queue_checkboxes = []

        for i, label in enumerate(JOB_QUEUE_FIELDS):
            if label:
                checkbox = QCheckBox(label)
                checkbox.setObjectName(label)
                row, col = divmod(i, 3)
                jobs_queue_layout.addWidget(checkbox, row, col)
                self._job_queue_checkboxes.append(checkbox)

        self.save_appearance_btn = QPushButton("Save Display Settings")
        self.save_appearance_btn.setObjectName(BTN_GREEN)
        self.save_appearance_btn.setMaximumWidth(250)
        jobs_queue_layout.addWidget(self.save_appearance_btn, row + 1, col + 1)
        appearance_layout.addRow(self.jobs_queue_options_group)
        settings_layout.addWidget(appearance_group)

        # --- SLURM Connection Settings ---
        connection_group = QGroupBox("SLURM Connection")
        connection_group.setMinimumHeight(150)
        connection_layout = QFormLayout(connection_group)

        self.cluster_address = QLineEdit()
        self.cluster_address.setClearButtonEnabled(True)
        connection_layout.addRow("Cluster Address:", self.cluster_address)

        self.username = QLineEdit()
        self.username.setClearButtonEnabled(True)
        connection_layout.addRow("Username:", self.username)

        self.password = QLineEdit()
        self.password.setClearButtonEnabled(True)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        connection_layout.addRow("Password:", self.password)

        self.connection_settings_btn = QPushButton("Save Connection Settings")
        self.connection_settings_btn.setObjectName(BTN_GREEN)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.connection_settings_btn)
        connection_layout.addRow(button_layout)
        settings_layout.addWidget(connection_group)

        # --- Notifications Section ---
        notifications_group = QGroupBox("Notifications")
        notifications_layout = QFormLayout(notifications_group)
        notifications_layout.setSpacing(15)

        self.discord_webhook_check = QCheckBox("Enable Discord Notifications")
        self.discord_webhook_check.setChecked(False)
        self.discord_webhook_check.stateChanged.connect(self._toggle_discord_webhook)
        notifications_layout.addRow("", self.discord_webhook_check)

        self.discord_webhook_url = QLineEdit()
        self.discord_webhook_url.setPlaceholderText("https://discord.com/api/webhooks/...")
        self.discord_webhook_url.setEnabled(False)
        notifications_layout.addRow("Discord Webhook URL:", self.discord_webhook_url)

        self.test_discord_btn = QPushButton("Test Discord Webhook")
        self.test_discord_btn.setObjectName(BTN_BLUE)
        self.test_discord_btn.setEnabled(False)
        self.test_discord_btn.clicked.connect(self._test_discord_webhook)
        test_layout = QHBoxLayout()
        test_layout.addStretch()
        test_layout.addWidget(self.test_discord_btn)
        notifications_layout.addRow("", test_layout)

        settings_layout.addWidget(notifications_group)

        # --- Save All Button ---
        self.save_button = QPushButton("Save All Settings")
        self.save_button.setObjectName(BTN_GREEN)
        self.save_button.setIcon(QIcon())
        save_all_layout = QHBoxLayout()
        save_all_layout.addStretch()
        save_all_layout.addWidget(self.save_button)
        settings_layout.addLayout(save_all_layout)
        settings_layout.addStretch()

    def _toggle_discord_webhook(self, state):
        # Accept both int and Qt.CheckState
        enabled = (state == Qt.CheckState.Checked or state == 2)
        self.discord_webhook_url.setEnabled(enabled)
        self.test_discord_btn.setEnabled(enabled)

    def _test_discord_webhook(self):
        webhook_url = self.discord_webhook_url.text().strip()
        if not webhook_url:
            show_warning_toast(self, "Warning", "Please enter a Discord webhook URL first.")
            return
        try:
            import requests, json
            payload = {
                "content": "🔔 **SlurmAIO Test Notification**",
                "embeds": [{
                    "title": "Test Notification",
                    "description": "This is a test message from SlurmAIO to verify Discord webhook configuration.",
                    "color": 0x00ff00,
                    "timestamp": datetime.now().isoformat(),
                    "footer": {"text": "SlurmAIO"}
                }]
            }
            headers = {"Content-Type": "application/json"}
            response = requests.post(webhook_url, data=json.dumps(payload), headers=headers, timeout=10)
            if response.status_code == 204:
                show_success_toast(self, "Success", "Test message sent successfully to Discord!")
            else:
                show_warning_toast(self, "Error", f"Failed to send test message. Status code: {response.status_code}")
        except ImportError:
            show_warning_toast(self, "Error", "The 'requests' library is required for Discord notifications. Please install it with: pip install requests")
        except Exception as e:
            show_error_toast(self, "Error", f"Failed to send test message: {str(e)}")

    def get_notification_settings(self):
        return {
            "discord_enabled": self.discord_webhook_check.isChecked(),
            "discord_webhook_url": self.discord_webhook_url.text().strip()
        }

    def set_notification_settings(self, settings):
        discord_enabled = settings.get("discord_enabled", False)
        discord_url = settings.get("discord_webhook_url", "")
        self.discord_webhook_check.setChecked(discord_enabled)
        self.discord_webhook_url.setText(discord_url)
        self._toggle_discord_webhook(Qt.CheckState.Checked if discord_enabled else Qt.CheckState.Unchecked)