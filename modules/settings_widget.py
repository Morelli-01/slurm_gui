from datetime import datetime
from modules.defaults import *
from style import AppStyles
from modules.toast_notify import show_error_toast, show_info_toast, show_success_toast, show_warning_toast


class SettingsWidget(QWidget):
    def __init__(self, parent=..., flags=...):
        super().__init__()
        self.setStyleSheet(AppStyles.get_complete_stylesheet(THEME_DARK))
        self.current_theme = THEME_DARK
        settings_layout = QVBoxLayout(self)
        settings_layout.setContentsMargins(25, 25, 25, 25)

        # Title
        settings_label = QLabel("Application Settings")
        settings_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        settings_layout.addWidget(settings_label)

        # Appearance section - only showing jobs queue options
        appearance_group = QGroupBox("Display Options")
        appearance_layout = QFormLayout(appearance_group)
        appearance_layout.setSpacing(10)
        appearance_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.jobs_queue_options_group = QGroupBox("Jobs Queue Visible Columns")
        jobs_queue_layout = QGridLayout(self.jobs_queue_options_group)

        for i, label in enumerate(JOB_QUEUE_FIELDS):
            if label:
                checkbox = QCheckBox(label)
                checkbox.setObjectName(label)
                row = i // 3
                col = i % 3
                jobs_queue_layout.addWidget(checkbox, row, col)

        # Save Button for appearance
        self.save_appearance_btn = QPushButton("Save Display Settings")
        self.save_appearance_btn.setObjectName(BTN_GREEN)
        self.save_appearance_btn.setMaximumWidth(250)
        save_layout = QHBoxLayout()
        save_layout.addStretch()
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

        # Replace SSH key with password field
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

        # --- Updated Notifications Section ---
        notifications_group = QGroupBox("Notifications")
        notifications_layout = QFormLayout(notifications_group)
        notifications_layout.setSpacing(15)

        # Discord webhook URL field
        self.discord_webhook_check = QCheckBox("Enable Discord Notifications")
        self.discord_webhook_check.setChecked(False)  # Default to False
        # IMPORTANT: Connect the signal AFTER setting the default value
        self.discord_webhook_check.stateChanged.connect(
            self._toggle_discord_webhook)
        notifications_layout.addRow("", self.discord_webhook_check)

        self.discord_webhook_url = QLineEdit()
        self.discord_webhook_url.setPlaceholderText(
            "https://discord.com/api/webhooks/...")
        self.discord_webhook_url.setEnabled(False)  # Default to disabled
        notifications_layout.addRow(
            "Discord Webhook URL:", self.discord_webhook_url)

        # Test Discord webhook button
        self.test_discord_btn = QPushButton("Test Discord Webhook")
        self.test_discord_btn.setObjectName(BTN_BLUE)
        self.test_discord_btn.setEnabled(False)  # Default to disabled
        self.test_discord_btn.clicked.connect(self._test_discord_webhook)
        test_layout = QHBoxLayout()
        test_layout.addStretch()
        test_layout.addWidget(self.test_discord_btn)
        notifications_layout.addRow("", test_layout)

        settings_layout.addWidget(notifications_group)

        # --- Save Button ---
        self.save_button = QPushButton("Save All Settings")
        self.save_button.setObjectName(BTN_GREEN)
        self.save_button.setIcon(QIcon())  # Placeholder icon

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        settings_layout.addLayout(button_layout)

        settings_layout.addStretch()  # Pushes settings to the top

    def _toggle_discord_webhook(self, state):
        """Enable/disable Discord webhook URL field based on checkbox state"""
        # Handle both int and Qt.CheckState values
        if hasattr(state, 'value'):
            enabled = state == Qt.CheckState.Checked
        else:
            # Qt.CheckState.Checked.value is 2
            enabled = state == Qt.CheckState.Checked.value or state == 2

        self.discord_webhook_url.setEnabled(enabled)
        self.test_discord_btn.setEnabled(enabled)

    def _test_discord_webhook(self):
        """Test the Discord webhook by sending a test message"""
        webhook_url = self.discord_webhook_url.text().strip()

        if not webhook_url:
            show_warning_toast(
                self, "Warning", "Please enter a Discord webhook URL first.")
            return

        try:
            import requests
            import json

            # Test message payload
            payload = {
                "content": "🔔 **SlurmAIO Test Notification**",
                "embeds": [{
                    "title": "Test Notification",
                    "description": "This is a test message from SlurmAIO to verify Discord webhook configuration.",
                    "color": 0x00ff00,  # Green color
                    "timestamp": datetime.now().isoformat(),
                    "footer": {
                        "text": "SlurmAIO"
                    }
                }]
            }

            headers = {
                "Content-Type": "application/json"
            }

            response = requests.post(webhook_url, data=json.dumps(
                payload), headers=headers, timeout=10)

            if response.status_code == 204:
                show_success_toast(
                    self, "Success", "Test message sent successfully to Discord!")
            else:
                show_warning_toast(
                    self, "Error", f"Failed to send test message. Status code: {response.status_code}")

        except ImportError:
            show_warning_toast(
                self, "Error", "The 'requests' library is required for Discord notifications. Please install it with: pip install requests")
        except Exception as e:
            show_error_toast(
                self, "Error", f"Failed to send test message: {str(e)}")

    def get_notification_settings(self):
        """Get current notification settings as a dictionary"""
        return {
            "discord_enabled": self.discord_webhook_check.isChecked(),
            "discord_webhook_url": self.discord_webhook_url.text().strip()
        }

    def set_notification_settings(self, settings):
        """Set notification settings from a dictionary"""
        discord_enabled = settings.get("discord_enabled", False)
        discord_url = settings.get("discord_webhook_url", "")

        # Set checkbox state
        self.discord_webhook_check.setChecked(discord_enabled)

        # Set URL
        self.discord_webhook_url.setText(discord_url)

        # Manually trigger the toggle to ensure UI state is correct
        # This is the key fix - we need to manually call the toggle method
        self._toggle_discord_webhook(
            Qt.CheckState.Checked if discord_enabled else Qt.CheckState.Unchecked)
