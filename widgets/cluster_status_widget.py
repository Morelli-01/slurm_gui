from controllers.cluster_status_controller import ClusterStatusController
from core.defaults import *
from core.event_bus import Events, get_event_bus
from views.cluster_entities import Cluster

# --- Constants ---
APP_TITLE = "Cluster Status Representation"
MIN_WIDTH = 400
MIN_HEIGHT = 700
REFRESH_INTERVAL_MS = 10000  # Refresh every 10 seconds

# MAIN WIDGET (Facade)
class ClusterStatusWidget(QWidget):
    """Main Cluster Status Widget - acts as a facade maintaining the original interface"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create MVC controller which manages model and view
        self.controller = ClusterStatusController(self)
        self.cluster = Cluster()

        # Setup layout to contain the view
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.controller.get_view())
        
        # Set window properties to maintain original interface
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(QSize(MIN_WIDTH, MIN_HEIGHT))
        self._event_bus_subscription()
        # Store SLURM connection reference
    def _event_bus_subscription(self):
        get_event_bus().subscribe(
            Events.CONNECTION_STATE_CHANGED,
            self.controller._shutdown
        )
    def update_status(self, nodes_data=None, jobs_data=None):
        """Refresh cluster data and update the view."""
        if nodes_data is not None and jobs_data is not None:
            # Use provided data to update the internal cluster representation
            self.cluster.update_from_data(nodes_data, jobs_data)
        else:
            return

        # Always pass the enriched dataclass data to the controller
        nodes_data = self.cluster.as_dicts()
        jobs_data = self.cluster.jobs

        self.controller.update_status(nodes_data, jobs_data)
