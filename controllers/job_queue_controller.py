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
        """Update queue status - simplified to always use full rebuild"""
        
        # Setup columns (handles format changes)
        self.view.setup_columns(self.model.visible_fields)
        
        # Always do full rebuild for reliability
        self.view.populate_table_full(jobs_data, self.model.visible_fields)
        
        # Store current jobs data in model
        self.model.current_jobs_data = jobs_data.copy()
        
        # Apply sorting exactly like original
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
        
        # Re-apply filters exactly like original
        if self.model.jobs_filter_text:
            self._filter_table(self.model.jobs_filter_text)
        elif self.model.jobs_filter_list:
            self._filter_table_by_list(self.model.jobs_filter_list)
    
    def _filter_table(self, filter_text: str):
        """Filter table by text exactly like original"""
        filter_text = str(filter_text).lower()
        self.model.jobs_filter_text = filter_text
        self.model.jobs_filter_list = []  # Clear list filter when text filter is used
        
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