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
        
        # Track current jobs by ID for incremental updates
        self._job_id_to_row = {}  # Maps job_id -> table row
        
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
        if self._needs_column_update():
            self._do_full_rebuild(jobs_data)
            return
        
        # Disable sorting during update
        # self.table.setSortingEnabled(False)
        
        # Create sets for tracking
        new_job_ids = {job.get("Job ID") for job in jobs_data if job.get("Job ID")}
        existing_job_ids = set(self._job_id_to_row.keys())
        
        # Find jobs to remove, update, and add
        jobs_to_remove = existing_job_ids - new_job_ids
        jobs_to_update = existing_job_ids & new_job_ids
        jobs_to_add = new_job_ids - existing_job_ids
        
        # Remove jobs that are no longer present
        for job_id in jobs_to_remove:
            row = self._job_id_to_row[job_id]
            self.table.removeRow(row)
            del self._job_id_to_row[job_id]
            # Update row mappings for jobs after the removed row
            for jid, r in self._job_id_to_row.items():
                if r > row:
                    self._job_id_to_row[jid] = r - 1
        
        # Update existing jobs
        jobs_dict = {job.get("Job ID"): job for job in jobs_data if job.get("Job ID")}
        for job_id in jobs_to_update:
            job_data = jobs_dict[job_id]
            row = self._job_id_to_row[job_id]
            self._update_row(row, job_data, jobs_data.index(job_data))
        
        # Add new jobs
        for job_id in jobs_to_add:
            job_data = jobs_dict[job_id]
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._job_id_to_row[job_id] = row
            self._update_row(row, job_data, jobs_data.index(job_data))
        
        # Store current jobs data in model
        self.model.current_jobs_data = jobs_data.copy()
        
        # Re-enable sorting and apply sort
        # self.table.setSortingEnabled(True)
        self._apply_sorting()
        
        # Re-apply filters
        self._reapply_filters()
    
    def _needs_column_update(self):
        """Check if columns need to be updated"""
        # Check if table has columns and if they match visible fields
        if self.table.columnCount() != len(self.model.visible_fields):
            return True
        
        # Check if column headers match
        for i, field in enumerate(self.model.visible_fields):
            header_item = self.table.horizontalHeaderItem(i)
            if not header_item or header_item.text() != field:
                return True
        
        return False
    
    def _do_full_rebuild(self, jobs_data: List[Dict[str, Any]]):
        """Do a full rebuild when columns change"""
        # Setup columns
        self.view.setup_columns(self.model.visible_fields)
        
        # Clear job tracking
        self._job_id_to_row.clear()
        
        # Populate table
        self.view.populate_table_full(jobs_data, self.model.visible_fields)
        
        # Rebuild job tracking
        for row in range(self.table.rowCount()):
            # Get job ID from first column's user data
            if self.table.item(row, 0):
                original_idx = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                if 0 <= original_idx < len(jobs_data):
                    job_id = jobs_data[original_idx].get("Job ID")
                    if job_id:
                        self._job_id_to_row[job_id] = row
        
        # Store current jobs data
        self.model.current_jobs_data = jobs_data.copy()
        
        # Apply sorting
        self._apply_sorting()
        
        # Re-apply filters
        self._reapply_filters()
    
    def _update_row(self, row: int, job_data: Dict[str, Any], original_index: int):
        """Update a single row with job data"""
        for col_idx, field_name in enumerate(self.model.visible_fields):
            item_data = job_data.get(field_name, "N/A")
            
            # Get or create item
            item = self.table.item(row, col_idx)
            if not item:
                item = QTableWidgetItem()
                self.table.setItem(row, col_idx, item)
            
            # Handle different data types exactly like original
            if isinstance(item_data, int):
                item.setData(Qt.ItemDataRole.EditRole, item_data)
            elif isinstance(item_data, str):
                item.setText(item_data)
            else:
                item.setData(Qt.ItemDataRole.EditRole, item_data[1].seconds)
                item.setData(Qt.ItemDataRole.DisplayRole, item_data[0])
            
            # Store original index for filtering
            item.setData(Qt.ItemDataRole.UserRole, original_index)
            
            # Default foreground for all items
            item.setForeground(QBrush(QColor(COLOR_DARK_FG)))
            
            # Status coloring exactly like original
            if field_name == "Status":
                status = job_data.get("Status", "").upper()
                color = QColor(COLOR_DARK_FG)  # Default
                if status == STATUS_RUNNING:
                    color = QColor(COLOR_GREEN)
                elif status == STATUS_PENDING:
                    color = QColor(COLOR_ORANGE)
                elif status == STATUS_COMPLETED:
                    color = QColor(COLOR_BLUE)
                elif status == STATUS_FAILED:
                    color = QColor(COLOR_RED)
                elif status == STATUS_COMPLETING:
                    color = QColor(COLOR_ORANGE)
                elif status == STATUS_PREEMPTED:
                    color = QColor(COLOR_RED)
                elif status == STATUS_SUSPENDED:
                    color = QColor(COLOR_ORANGE)
                elif status == STATUS_STOPPED:
                    color = QColor(COLOR_BLUE)
                item.setForeground(QBrush(color))
            
            # Alternating row colors
            if row % 2 == 0:
                item.setBackground(QBrush(QColor(COLOR_DARK_BG)))
            else:
                item.setBackground(QBrush(QColor(COLOR_DARK_BG_ALT)))
    
    def _apply_sorting(self):
        """Apply sorting exactly like original"""
        applied_user_sort = False
        if self.model._sorted_by_field_name and self.model._sorted_by_order is not None:
            if self.model._sorted_by_field_name in self.model.visible_fields:
                try:
                    column_index_to_sort = self.model.visible_fields.index(self.model._sorted_by_field_name)
                    self.table.sortItems(column_index_to_sort, self.model._sorted_by_order)
                    applied_user_sort = True
                except ValueError:
                    pass
        
        if not applied_user_sort:
            # Default sorting exactly like original
            try:
                user_column_index = self.model.visible_fields.index("User")
                self.table.sortItems(user_column_index, Qt.SortOrder.AscendingOrder)
            except ValueError:
                pass
            try:
                status_column_index = self.model.visible_fields.index("Status")
                self.table.sortItems(status_column_index, Qt.SortOrder.DescendingOrder)
            except ValueError:
                pass
    
    def _reapply_filters(self):
        """Re-apply filters exactly like original"""
        if self.model.jobs_filter_text:
            self._filter_table(self.model.jobs_filter_text)
        elif self.model.jobs_filter_list:
            self._filter_table_by_list(self.model.jobs_filter_list)
        elif self.model.jobs_negative_filter_list:
            self._filter_table_by_negative_keywords(self.model.jobs_negative_filter_list)
    
    def _filter_table(self, filter_text: str):
        """Filter table by text exactly like original"""
        filter_text = str(filter_text).lower()
        self.model.jobs_filter_text = filter_text
        self.model.jobs_filter_list = []  # Clear list filter when text filter is used
        self.model.jobs_negative_filter_list = []  # Clear negative filter
        
        def text_filter_func(job_data_dict):
            if not filter_text:  # If filter_text is empty, all rows are visible
                return True
            
            # Check all fields exactly like original
            for field_key in JOB_QUEUE_FIELDS:
                field_value_obj = job_data_dict.get(field_key)
                if field_value_obj is not None:
                    field_value_str_lower = str(field_value_obj).lower()
                    if filter_text in field_value_str_lower:
                        return True
            return False
        
        self.view.apply_filter_to_rows(self.model.current_jobs_data, text_filter_func)
    
    def _filter_table_by_list(self, filter_list: List[str]):
        """Filter table by list exactly like original"""
        if not isinstance(filter_list, list):
            processed_filter_list = []
        else:
            processed_filter_list = [str(f).lower() for f in filter_list if f and str(f).strip()]
        
        self.model.jobs_filter_list = processed_filter_list
        self.model.jobs_filter_text = ""  # Clear text filter when list filter is used
        self.model.jobs_negative_filter_list = []  # Clear negative filter
        
        def list_filter_func(job_data_dict):
            if not processed_filter_list:  # If filter list is empty, all rows are visible
                return True
            
            # Check all fields exactly like original
            for field_key in JOB_QUEUE_FIELDS:
                field_value_obj = job_data_dict.get(field_key)
                if field_value_obj is not None:
                    field_value_str_lower = str(field_value_obj).lower()
                    for filter_item_lower in processed_filter_list:
                        if filter_item_lower in field_value_str_lower:
                            return True
            return False
        
        self.view.apply_filter_to_rows(self.model.current_jobs_data, list_filter_func)
    
    def _filter_table_by_negative_keywords(self, negative_keyword_list: List[str]):
        """Filter table by negative keywords exactly like original"""
        if not isinstance(negative_keyword_list, list):
            processed_negative_list = []
        else:
            processed_negative_list = [str(f).lower() for f in negative_keyword_list if f and str(f).strip()]
        
        self.model.jobs_negative_filter_list = processed_negative_list
        self.model.jobs_filter_text = ""
        self.model.jobs_filter_list = []
        
        def negative_filter_func(job_data_dict):
            if not processed_negative_list:
                return True
            
            # Check all fields exactly like original
            for field_key in JOB_QUEUE_FIELDS:
                field_value_obj = job_data_dict.get(field_key)
                if field_value_obj is not None:
                    field_value_str_lower = str(field_value_obj).lower()
                    for negative_item_lower in processed_negative_list:
                        if negative_item_lower in field_value_str_lower:
                            return False  # Hide row if negative keyword found
            return True
        
        self.view.apply_filter_to_rows(self.model.current_jobs_data, negative_filter_func)