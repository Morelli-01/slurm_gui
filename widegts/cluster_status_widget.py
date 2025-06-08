from controllers.cluster_status_controller import ClusterStatusController
from modules.defaults import *

# --- Constants ---
APP_TITLE = "Cluster Status Representation"
MIN_WIDTH = 400
MIN_HEIGHT = 700
REFRESH_INTERVAL_MS = 10000  # Refresh every 10 seconds

# MAIN WIDGET (Facade)
class ClusterStatusWidget(QWidget):
    """Main Cluster Status Widget - acts as a facade maintaining the original interface"""
    
    def __init__(self, parent=None, slurm_connection=None):
        super().__init__(parent)
        
        # Create MVC controller which manages model and view
        self.controller = ClusterStatusController(slurm_connection, self)
        
        # Setup layout to contain the view
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.controller.get_view())
        
        # Set window properties to maintain original interface
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(QSize(MIN_WIDTH, MIN_HEIGHT))
        
        # Store SLURM connection reference
        self.sc_ = slurm_connection
    
    def update_status(self, nodes_data, jobs_data):
        """Update the cluster status - maintains original interface"""
        self.controller.update_status(nodes_data, jobs_data)