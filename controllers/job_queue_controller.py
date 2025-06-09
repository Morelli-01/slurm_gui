from models.job_queue_model import JobQueueModel
from modules.defaults import *
from views.job_queue_view import JobQueueView



class JobQueueController:
    """Controller: Coordinates between model and view, handles user interactions"""
    
    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.model = JobQueueModel()
        
        # Setup view
        self.table = QTableWidget()
        self.view = JobQueueView(self.table)
        
        # Setup table with initial columns
        self.view.setup_columns(self.model.get_visible_fields())
        
        # Connect signals
        self._connect_signals()
        
        # Enable sorting
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().sortIndicatorChanged.connect(self._on_sort_changed)
    
    def _connect_signals(self):
        """Connect table signals to controller methods"""
        # Add any additional signal connections here if needed
        pass
    
    def get_table_widget(self) -> QTableWidget:
        """Get the table widget for embedding in parent"""
        return self.table
    
    def update_jobs(self, new_jobs: List[Dict[str, Any]]):
        """Update jobs with efficient incremental updates"""
        if not new_jobs and hasattr(self.parent, 'slurm_connection'):
            # Check for connection issues
            if (hasattr(self.parent, 'slurm_connection') and 
                self.parent.slurm_connection and 
                not self.parent.slurm_connection.check_connection()):
                self.view.show_connection_error()
                return
        
        # Get changes from model
        changes = self.model.update_jobs(new_jobs)
        
        # Determine if we need full rebuild or can do incremental updates
        visible_fields = self.model.get_visible_fields()
        current_columns = [self.table.horizontalHeaderItem(i).text() 
                          for i in range(self.table.columnCount())] if self.table.columnCount() > 0 else []
        
        needs_column_rebuild = current_columns != visible_fields
        
        if needs_column_rebuild or len(changes['added']) + len(changes['removed']) > len(new_jobs) * 0.5:
            # Rebuild if columns changed or too many changes (>50% of data)
            self._full_rebuild()
        else:
            # Incremental update
            self._incremental_update(changes, visible_fields)
        
        # Apply current filter and sorting
        self._apply_display_state()
    
    def _full_rebuild(self):
        """Completely rebuild the table"""
        self.table.setSortingEnabled(False)
        
        visible_fields = self.model.get_visible_fields()
        self.view.setup_columns(visible_fields)
        self.view.clear_table()
        
        # Add all filtered jobs
        for job in self.model.get_filtered_jobs():
            self.view.add_job_row(job, visible_fields)
        
        self.table.setSortingEnabled(True)
    
    def _incremental_update(self, changes: Dict[str, Any], visible_fields: List[str]):
        """Apply incremental updates to the table"""
        self.table.setSortingEnabled(False)
        
        # Remove jobs
        for removed in reversed(changes['removed']):  # Remove from bottom up
            job_id = removed['job_id']
            row = self.view.find_job_row(job_id)
            if row >= 0:
                self.view.remove_job_row(row)
        
        # Update existing jobs
        for updated in changes['updated']:
            job_id = updated['job_id']
            row = self.view.find_job_row(job_id)
            if row >= 0:
                self.view.update_job_row(row, updated['new'], visible_fields)
        
        # Add new jobs
        for added in changes['added']:
            self.view.add_job_row(added, visible_fields)
        
        self.table.setSortingEnabled(True)
    
    def _apply_display_state(self):
        """Apply current sorting and filtering state"""
        # Apply sorting if set
        if self.model.sort_field and self.model.sort_field in self.model.get_visible_fields():
            try:
                column_index = self.model.get_visible_fields().index(self.model.sort_field)
                self.table.sortItems(column_index, self.model.sort_order)
            except ValueError:
                pass
        else:
            # Default sorting: Status descending, then User ascending
            try:
                if "Status" in self.model.get_visible_fields():
                    status_col = self.model.get_visible_fields().index("Status")
                    self.table.sortItems(status_col, Qt.SortOrder.DescendingOrder)
                elif "User" in self.model.get_visible_fields():
                    user_col = self.model.get_visible_fields().index("User")
                    self.table.sortItems(user_col, Qt.SortOrder.AscendingOrder)
            except ValueError:
                pass
    
    def _on_sort_changed(self, logical_index: int, order: Qt.SortOrder):
        """Handle sort indicator changes"""
        visible_fields = self.model.get_visible_fields()
        if 0 <= logical_index < len(visible_fields):
            field_name = visible_fields[logical_index]
            self.model.set_sort(field_name, order)
    
    def filter_by_text(self, filter_text: str):
        """Apply text filter"""
        self.model.set_text_filter(filter_text)
        self._full_rebuild()  # Rebuild to apply filter
    
    def filter_by_list(self, filter_list: List[str]):
        """Apply list filter"""
        self.model.set_list_filter(filter_list)
        self._full_rebuild()  # Rebuild to apply filter
    
    def filter_by_negative_keywords(self, negative_list: List[str]):
        """Apply negative filter"""
        self.model.set_negative_filter(negative_list)
        self._full_rebuild()  # Rebuild to apply filter
    
    def reload_settings(self):
        """Reload settings and update display"""
        self.model.reload_field_settings()
        self._full_rebuild()
