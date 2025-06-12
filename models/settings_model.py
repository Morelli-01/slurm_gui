from pathlib import Path
from core.defaults import *
from utils import settings_path
from core.event_bus import Event

# MODEL
class SettingsModel(QObject):
    """Model: Handles settings data and persistence"""

    def __init__(self):
        super().__init__()
        self.settings = QSettings(str(Path(settings_path)), QSettings.Format.IniFormat)
        self._connection_settings = {
            'cluster_address': '',
            'username': '',
            'password': ''
        }
        self._display_settings = {
            'job_queue_columns': {field: True for field in JOB_QUEUE_FIELDS}
        }
        self._notification_settings = {
            'discord_enabled': False,
            'discord_webhook_url': ''
        }
        self.load_from_qsettings()

    def update_connection_settings(self, event_data):
        settings = event_data.data["settings"]
        self._connection_settings.update(settings)
        self.settings.beginGroup("GeneralSettings")
        self.settings.setValue("clusterAddress",
                          self._connection_settings['cluster_address'])
        self.settings.setValue("username", self._connection_settings['username'])
        self.settings.setValue("psw", self._connection_settings['password'])
        self.settings.endGroup()
        print("Connection settings saved!")

    def save_display_settigngs(self, event_data):
        display_settings = event_data.data["display_settings"]
        self._display_settings = {
            'job_queue_columns': display_settings
        }
        self.settings.beginGroup("AppearenceSettings")
        for field, enabled in self._display_settings['job_queue_columns'].items():
            self.settings.setValue(field, bool(enabled))
        self.settings.endGroup()
        self.settings.sync()
        print("Display settings saved!")

    def update_notification_settings(self, event_data):
        if isinstance(event_data, Event):
            settings = event_data.data
        else:
            settings = event_data
        self._notification_settings.update(settings)
        # Save notification settings
        self.settings.beginGroup("NotificationSettings")
        self.settings.setValue("discord_enabled",
                          self._notification_settings['discord_enabled'])
        self.settings.setValue("discord_webhook_url",
                          self._notification_settings['discord_webhook_url'])
        self.settings.endGroup()
        print("Notification settings saved!")

    def load_from_qsettings(self):
        """Load settings from QSettings"""
        # Load connection settings
        self.settings.beginGroup("GeneralSettings")
        self._connection_settings = {
            'cluster_address': self.settings.value("clusterAddress", ""),
            'username': self.settings.value("username", ""),
            'password': self.settings.value("psw", "")
        }
        self.settings.endGroup()

        # Load display settings - match original logic exactly
        self.settings.beginGroup("AppearenceSettings")
        for field in JOB_QUEUE_FIELDS:
            # Default to True if not set, just like the original
            self._display_settings['job_queue_columns'][field] = self.settings.value(
                field, True, type=bool)
        self.settings.endGroup()

        # Load notification settings
        self.settings.beginGroup("NotificationSettings")
        self._notification_settings = {
            'discord_enabled': self.settings.value("discord_enabled", False, type=bool),
            'discord_webhook_url': self.settings.value("discord_webhook_url", "", type=str)
        }
        self.settings.endGroup()

    def save_to_qsettings(self):
        """Save settings to QSettings"""
        # Save connection settings

        self.settings.beginGroup("GeneralSettings")
        self.settings.setValue("clusterAddress",
                          self._connection_settings['cluster_address'])
        self.settings.setValue("username", self._connection_settings['username'])
        self.settings.setValue("psw", self._connection_settings['password'])
        self.settings.endGroup()

        # Save display settings - match original format exactly
        self.settings.beginGroup("AppearenceSettings")
        for field, enabled in self._display_settings['job_queue_columns'].items():
            self.settings.setValue(field, bool(enabled))
        self.settings.endGroup()

        # Save notification settings
        self.settings.beginGroup("NotificationSettings")
        self.settings.setValue("discord_enabled",
                          self._notification_settings['discord_enabled'])
        self.settings.setValue("discord_webhook_url",
                          self._notification_settings['discord_webhook_url'])
        self.settings.endGroup()

        self.settings.sync()
