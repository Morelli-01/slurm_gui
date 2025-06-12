from datetime import datetime
from core.event_bus import EventPriority, Events, get_event_bus
from models.settings_model import SettingsModel
from core.defaults import *
from widgets.toast_widget import *
from views.settings_view import SettingsView
from utils import settings_path
from pathlib import Path
# CONTROLLER
class SettingsController(QObject):
    """Controller: Handles user interactions and coordinates model/view"""
    
    def __init__(self, model, view):
        super().__init__()
        self.event_bus = get_event_bus()
        self.model: SettingsModel = model
        self.view: SettingsView = view
        self._connect_signals()
        self._event_bus_subscription()

    def _connect_signals(self):
        """Connect model and view signals"""
        
        # # View to controller actions
        self.view.discord_test_requested.connect(self._test_discord_webhook)
        
    def _event_bus_subscription(self):
        self.event_bus.subscribe(Events.CONNECTION_SAVE_REQ,
                                 callback=self.model.update_connection_settings,
                                 priority=EventPriority.HIGH)        
        self.event_bus.subscribe(Events.DISPLAY_SAVE_REQ,
                                 callback=self.model.save_display_settigngs,
                                 priority=EventPriority.HIGH)        
        self.event_bus.subscribe(Events.NOTIF_SAVE_REQ,
                                 callback=self.model.update_notification_settings,
                                 priority=EventPriority.HIGH)
        
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
    

