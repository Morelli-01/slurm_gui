from models.job_queue_model import JobQueueModel
from core.defaults import *
from views.job_queue_view import JobQueueView


class JobQueueController:
    """Controller: Manages interaction between model and view"""
    
    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.model = JobQueueModel()
        self.table = QTableWidget()
        self.view = JobQueueView(self.table)
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
        self._do_full_rebuild(jobs_data)
        return

    def _do_full_rebuild(self, jobs_data: List[Dict[str, Any]]):
        """Do a full rebuild when columns change"""
        
        self.view.populate_table_full(jobs_data, self.model.displayable_fields)
        
