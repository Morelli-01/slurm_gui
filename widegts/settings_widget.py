
from controllers.settings_controller import SettingsController
from models.settings_model import SettingsModel
from modules.defaults import *
from views.settings_view import SettingsView

# MAIN WIDGET (Facade)
class SettingsWidget(QWidget):
    """Main Settings Widget - acts as a facade maintaining the original interface"""
    
    def __init__(self, parent=None, flags=None):
        super().__init__(parent)
        
        # Create MVC components
        self.model = SettingsModel()
        self.view = SettingsView(self)
        self.controller = SettingsController(self.model, self.view)
        
        # Setup layout to contain the view
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        
        # Expose buttons for external access (maintaining original interface)
        self.save_appearance_btn = self.view.save_appearance_btn
        self.connection_settings_btn = self.view.connection_settings_btn  
        self.save_button = self.view.save_button
        
        # Expose other necessary attributes for compatibility
        self.cluster_address = self.view.cluster_address
        self.username = self.view.username
        self.password = self.view.password
        self.jobs_queue_options_group = self.view.jobs_queue_options_group
    
    def get_notification_settings(self):
        """Get notification settings - maintains original interface"""
        return self.controller.get_notification_settings()
    
    def set_notification_settings(self, settings):
        """Set notification settings - maintains original interface"""
        self.controller.set_notification_settings(settings)
