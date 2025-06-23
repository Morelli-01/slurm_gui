from core.slurm_api import ConnectionState
from models.job_queue_model import JobQueueModel, JobQueueTableModel
from core.defaults import *
from views.job_queue_view import JobQueueView
from PyQt6.QtCore import QSortFilterProxyModel


class JobQueueController:
    """Controller: Manages interaction between the model and view."""

    def __init__(self, parent_widget):
        self.parent = parent_widget
        
        # --- MVC REFACTOR ---
        self.settings_model = JobQueueModel()  # The original model for settings
        self.table_model = JobQueueTableModel()  # The new high-performance table model
        self.proxy_model = QSortFilterProxyModel() # For filtering and sorting
        
        self.proxy_model.setSourceModel(self.table_model)
        
        self.view = JobQueueView()
        self.view.setModel(self.proxy_model)
        
        # Initial setup of columns from settings
        self.table_model.set_displayable_fields(self.settings_model.displayable_fields)
        self.view.setup_columns(self.table_model)
        
        # The view's header is now the proxy model's header
        header = self.view.horizontalHeader()
        header.setSectionsClickable(True)

    def update_queue_status(self, jobs_data: List[Dict[str, Any]]):
        """Update queue status by passing the full dataset to the model."""
        self.table_model.update_jobs(jobs_data)

    def filter_table_by_account(self, kws: list[str], negative=False):
        # The proxy model handles filtering efficiently
        self.proxy_model.setFilterKeyColumn(self.settings_model.visible_fields.index("Account"))
        self.proxy_model.setFilterRegularExpression("|".join(kws))
        # Note: Negative filtering with QSortFilterProxyModel is more complex
        # and might require subclassing it if that feature is critical.

    def filter_table_by_user(self, kws: list[str], negative=False):
        self.proxy_model.setFilterKeyColumn(self.settings_model.visible_fields.index("User"))
        self.proxy_model.setFilterRegularExpression("|".join(kws))
        
    def _shutdown(self, event_data):
        new_state = event_data.data["new_state"]
        old_state = event_data.data["old_state"]
        is_connected = new_state == ConnectionState.CONNECTED
        self.view.shutdown_ui(is_connected=is_connected)