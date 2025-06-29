from pathlib import Path
from core.defaults import *
from core.slurm_api import ConnectionState, SlurmAPI
from utils import settings_path
from core.event_bus import Event, Events, get_event_bus
from PyQt6.QtCore import QSettings
import tempfile
import os

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

    def save_to_remote_server(func):
        """Decorator to save configuration to a remote server after the method execution."""
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)  # Execute the original method
            try:
                # Assuming `slurm_api` is available and has a method to save settings remotely
                # Copy all settings except GeneralSettings to a temporary ini file

                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".ini")
                tmp_settings = QSettings(tmp_path, QSettings.Format.IniFormat)

                for group in self.settings.childGroups():
                    if group == "GeneralSettings":
                        continue
                    self.settings.beginGroup(group)
                    tmp_settings.beginGroup(group)
                    for key in self.settings.childKeys():
                        tmp_settings.setValue(key, self.settings.value(key))
                    tmp_settings.endGroup()
                    self.settings.endGroup()
                tmp_settings.sync()

                SlurmAPI().save_settings_remotely(tmp_path)
                os.close(tmp_fd)
                os.remove(tmp_path)

                print("Settings saved to remote server.")
            except Exception as e:
                print(f"Failed to save settings to remote server: {e}")
            return result
        return wrapper

    def load_remote(self, event_data):
        new_state = event_data.data["new_state"]
        if new_state == ConnectionState.CONNECTED:
            try:
                remote_ini_result = SlurmAPI().read_remote_file(f"{SlurmAPI().remote_home}/.slurm_gui/remote_settings.ini")
                # If read_remote_file returns (content, ...) tuple, extract content
                if remote_ini_result:
                    if isinstance(remote_ini_result, tuple):
                        remote_ini = remote_ini_result[0]
                    else:
                        remote_ini = remote_ini_result
                    remote_settings_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ini")
                    remote_settings_file.write(remote_ini.encode("utf-8"))
                    remote_settings_file.close()
                    remote_settings = QSettings(remote_settings_file.name, QSettings.Format.IniFormat)
                    for group in remote_settings.childGroups():
                        if group == "GeneralSettings":
                            continue
                        remote_settings.beginGroup(group)
                        self.settings.beginGroup(group)
                        for key in remote_settings.childKeys():
                            self.settings.setValue(key, remote_settings.value(key))
                        self.settings.endGroup()
                        remote_settings.endGroup()
                    self.settings.sync()
                    os.remove(remote_settings_file.name)
                    print("Remote settings loaded and synced.")
            except Exception as e:
                print(f"Failed to load remote settings: {e}")

    # Apply the decorator to the relevant methods
    @save_to_remote_server
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

    @save_to_remote_server
    def update_connection_settings(self, event_data):
        settings = event_data.data["settings"]
        self._connection_settings.update(settings)
        self.settings.beginGroup("GeneralSettings")
        self.settings.setValue("clusterAddress",
                          self._connection_settings['cluster_address'])
        self.settings.setValue("username", self._connection_settings['username'])
        self.settings.setValue("psw", self._connection_settings['password'])
        self.settings.endGroup()
        self.settings.sync()
        print("Connection settings saved!")

    @save_to_remote_server
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

    @save_to_remote_server
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
        # print("Notification settings saved!")
