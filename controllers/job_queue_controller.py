from core.slurm_api import ConnectionState
from models.job_queue_model import JobQueueModel
from core.defaults import *
from views.job_queue_view import JobQueueView


class JobQueueController:
    """Controller: Manages interaction between model and view"""
    
    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.model = JobQueueModel()
        self.view = JobQueueView()
        self.table = self.view.table
        self.view.setup_columns(self.model.displayable_fields , self.model.visible_fields)
        
        # Connect sorting signal exactly like original
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.sortIndicatorChanged.connect(self._on_sort_indicator_changed)
    
    def _on_sort_indicator_changed(self, logical_index: int, order: Qt.SortOrder):
        """Handle sort indicator changes exactly like original"""
        if 0 <= logical_index < len(self.model.visible_fields):
            self.model._sorted_by_field_name = self.model.visible_fields[logical_index]
            self.model._sorted_by_order = order
        else:
            self.model._sorted_by_field_name = None
            self.model._sorted_by_order = None
    
    def update_queue_status(self, jobs_data: List[Dict[str, Any]]):
        """Update queue status with incremental updates"""
        
        # Check if columns need to be updated
        self.view.update_table(jobs_data, self.model.displayable_fields)
        return

    def filter_table_by_account(self, kws:list[str], negative=False):
        account_index = list(self.model.displayable_fields.keys()).index("Account")
        self.view.filter_rows(kws, field_index=account_index, negative=negative)

    def filter_table_by_user(self, kws:list[str], negative=False):
        account_index = list(self.model.displayable_fields.keys()).index("User")
        self.view.filter_rows(kws, field_index=account_index, negative=negative)
    
    def _shutdown(self, event_data):
        new_state = event_data.data["new_state"]
        old_state = event_data.data["old_state"]
        if new_state == ConnectionState.DISCONNECTED:
            self.view.shutdown_ui(is_connected=False)
        elif new_state == ConnectionState.CONNECTED:
            self.view.shutdown_ui(is_connected=True)