from modules.defaults import *


# MODEL
class SettingsModel(QObject):
    """Model: Handles settings data and persistence"""
    
    # Signals for data changes
    connection_settings_changed = pyqtSignal(dict)
    display_settings_changed = pyqtSignal(dict)
    notification_settings_changed = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
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
    
    # Connection settings
    def get_connection_settings(self):
        return self._connection_settings.copy()
    
    def update_connection_settings(self, settings):
        self._connection_settings.update(settings)
        self.connection_settings_changed.emit(self._connection_settings.copy())
    
    # Display settings
    def get_display_settings(self):
        return self._display_settings.copy()
    
    def update_display_settings(self, settings):
        self._display_settings.update(settings)
        self.display_settings_changed.emit(self._display_settings.copy())
    
    def update_job_queue_column(self, column, enabled):
        self._display_settings['job_queue_columns'][column] = enabled
        self.display_settings_changed.emit(self._display_settings.copy())
    
    # Notification settings  
    def get_notification_settings(self):
        return self._notification_settings.copy()
    
    def update_notification_settings(self, settings):
        self._notification_settings.update(settings)
        self.notification_settings_changed.emit(self._notification_settings.copy())
    
    # Persistence
    def load_from_qsettings(self, settings):
        """Load settings from QSettings"""
        # Load connection settings
        settings.beginGroup("GeneralSettings")
        self._connection_settings = {
            'cluster_address': settings.value("clusterAddress", ""),
            'username': settings.value("username", ""),
            'password': settings.value("psw", "")
        }
        settings.endGroup()
        
        # Load display settings - match original logic exactly
        settings.beginGroup("AppearenceSettings")
        for field in JOB_QUEUE_FIELDS:
            # Default to True if not set, just like the original
            self._display_settings['job_queue_columns'][field] = settings.value(field, True, type=bool)
        settings.endGroup()
        
        # Load notification settings
        settings.beginGroup("NotificationSettings")
        self._notification_settings = {
            'discord_enabled': settings.value("discord_enabled", False, type=bool),
            'discord_webhook_url': settings.value("discord_webhook_url", "", type=str)
        }
        settings.endGroup()
        
        # Emit change signals
        self.connection_settings_changed.emit(self._connection_settings.copy())
        self.display_settings_changed.emit(self._display_settings.copy())
        self.notification_settings_changed.emit(self._notification_settings.copy())
    
    def save_to_qsettings(self, settings):
        """Save settings to QSettings"""
        # Save connection settings
        settings.beginGroup("GeneralSettings")
        settings.setValue("clusterAddress", self._connection_settings['cluster_address'])
        settings.setValue("username", self._connection_settings['username'])
        settings.setValue("psw", self._connection_settings['password'])
        settings.endGroup()
        
        # Save display settings - match original format exactly
        settings.beginGroup("AppearenceSettings")
        for field, enabled in self._display_settings['job_queue_columns'].items():
            settings.setValue(field, bool(enabled))
        settings.endGroup()
        
        # Save notification settings
        settings.beginGroup("NotificationSettings")
        settings.setValue("discord_enabled", self._notification_settings['discord_enabled'])
        settings.setValue("discord_webhook_url", self._notification_settings['discord_webhook_url'])
        settings.endGroup()
        
        settings.sync()


