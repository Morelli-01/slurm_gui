from typing import List, Dict, Any
from PyQt6.QtCore import QObject
from core.slurm_api import ConnectionState
from models.cluster_status_model import ClusterStatusModel
from views.cluster_status_view import ClusterStatusView

# CONTROLLER
class ClusterStatusController(QObject):
    """Controller: Coordinates between model and view"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create MVC components
        self.model = ClusterStatusModel()
        self.view = ClusterStatusView()
        
        # Connect model signals to view updates
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect model signals to view updates"""
        self.model.data_updated.connect(self.view.update_display)
        self.model.connection_status_changed.connect(self._on_connection_status_changed)
    
    def _on_connection_status_changed(self, is_connected: bool):
        """Handle connection status changes"""
        if not is_connected:
            self.view._show_connection_error()
    
    def update_status(self, nodes_data: List[Dict[str, Any]], jobs_data: List[Dict[str, Any]]):
        """Update the cluster status with new data"""
        self.model.update_data(nodes_data, jobs_data)
    
    def get_view(self):
        """Get the view widget for embedding in the main application"""
        return self.view
    
    def get_model(self):
        """Get the model for direct access if needed"""
        return self.model

    def _shutdown(self, event_data):
        new_state = event_data.data["new_state"]
        old_state = event_data.data["old_state"]
        if new_state == ConnectionState.DISCONNECTED:
            self.view.shutdown_ui(is_connected=False)
        elif new_state == ConnectionState.CONNECTED:
            self.view.shutdown_ui(is_connected=True)
