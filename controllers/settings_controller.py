from datetime import datetime
from models.settings_model import SettingsModel
from modules.defaults import *
from widgets.toast_widget import *
from views.settings_view import SettingsView
from utils import settings_path
from pathlib import Path
# CONTROLLER
class SettingsController(QObject):
    """Controller: Handles user interactions and coordinates model/view"""
    
    def __init__(self, model, view):
        super().__init__()
        self.model = model
        self.view = view
        self._connect_signals()
        self._load_settings()
    
    def _connect_signals(self):
        """Connect model and view signals"""
        # Model to view updates
        self.model.connection_settings_changed.connect(self.view.update_connection_settings)
        self.model.display_settings_changed.connect(self.view.update_display_settings)
        self.model.notification_settings_changed.connect(self.view.update_notification_settings)
        
        # View to controller actions
        self.view.connection_save_requested.connect(self._save_connection_settings)
        self.view.display_save_requested.connect(self._save_display_settings)
        self.view.all_save_requested.connect(self._save_all_settings)
        self.view.discord_test_requested.connect(self._test_discord_webhook)
        
        # Live updates from view to model
        self.view.connection_field_changed.connect(self._update_connection_field)
        self.view.job_queue_column_changed.connect(self.model.update_job_queue_column)
        self.view.discord_enabled_changed.connect(self._update_discord_enabled)
        self.view.discord_url_changed.connect(self._update_discord_url)
    
    def _update_connection_field(self, field_name, value):
        """Update a single connection field in model"""
        current_settings = self.model.get_connection_settings()
        current_settings[field_name] = value
        self.model.update_connection_settings(current_settings)
    
    def _update_discord_enabled(self, enabled):
        """Update Discord enabled status in model"""
        current_settings = self.model.get_notification_settings()
        current_settings['discord_enabled'] = enabled
        self.model.update_notification_settings(current_settings)
    
    def _update_discord_url(self, url):
        """Update Discord URL in model"""
        current_settings = self.model.get_notification_settings()
        current_settings['discord_webhook_url'] = url
        self.model.update_notification_settings(current_settings)
    
    def _save_connection_settings(self, settings):
        """Save connection settings"""
        self.model.update_connection_settings(settings)
        self._persist_settings()
    
    def _save_display_settings(self):
        """Save display settings"""
        self._persist_settings()
    
    def _save_all_settings(self):
        """Save all settings"""
        self._persist_settings()
    
    def _test_discord_webhook(self, webhook_url):
        """Test Discord webhook"""
        if not webhook_url:
            show_warning_toast(self.view, "Missing URL", "Please enter a Discord webhook URL first.")
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
                show_success_toast(self.view, "Test Successful", "Message sent to Discord!")
            else:
                show_warning_toast(self.view, "Test Failed", f"Status code: {response.status_code}")
                
        except ImportError:
            show_warning_toast(self.view, "Missing Library", "Install requests: pip install requests")
        except Exception as e:
            show_error_toast(self.view, "Test Failed", str(e))
    
    def _load_settings(self):
        """Load settings from QSettings"""
        
        settings = QSettings(str(Path(settings_path)), QSettings.Format.IniFormat)
        self.model.load_from_qsettings(settings)
    
    def _persist_settings(self):
        """Persist settings to QSettings"""
        
        settings = QSettings(str(Path(settings_path)), QSettings.Format.IniFormat)
        self.model.save_to_qsettings(settings)
    
    # Public methods for external interface compatibility
    def get_notification_settings(self):
        """Get notification settings - for external interface compatibility"""
        return self.model.get_notification_settings()
    
    def set_notification_settings(self, settings):
        """Set notification settings - for external interface compatibility"""
        self.model.update_notification_settings(settings)


