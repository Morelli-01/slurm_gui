from core.slurm_api import ConnectionState
from models.job_queue_model import JobQueueModel, JobQueueTableModel
from core.defaults import *
from views.job_queue_view import JobQueueView
from PyQt6.QtCore import QSortFilterProxyModel
from typing import List, Dict, Any

class JobQueueFilterProxyModel(QSortFilterProxyModel):
    """
    A custom filter proxy model to handle combined filtering:
    1. A text filter that searches across all columns.
    2. A column-specific keyword filter that can be inverted (negative).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text_filter_string = ""
        self._column_filter_keywords = []
        self._column_filter_column = -1
        self._is_negative = False

    def set_text_filter(self, text: str):
        """Sets the string for the general text filter."""
        self._text_filter_string = text.lower()
        self.invalidateFilter() # Force the view to re-filter

    def set_column_filter(self, keywords: list, column: int, negative: bool = False):
        """Sets the keywords for the column-specific filter."""
        self._column_filter_keywords = [kw.lower() for kw in keywords if kw]
        self._column_filter_column = column
        self._is_negative = negative
        self.invalidateFilter() # Force the view to re-filter

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        """
        Overrides the base class method to implement custom filtering logic.
        A row is accepted if it matches both the text filter and the column filter.
        """
        # 1. Column-specific keyword filter (for 'ME', 'PROD', 'STUD')
        column_match = True
        if self._column_filter_keywords and self._column_filter_column >= 0:
            index = self.sourceModel().index(source_row, self._column_filter_column, source_parent)
            cell_data = str(self.sourceModel().data(index)).lower()
            
            # Check if any of the keywords are present in the cell data
            match_found = any(kw in cell_data for kw in self._column_filter_keywords)

            # Apply negative logic if required
            if self._is_negative:
                column_match = not match_found
            else:
                column_match = match_found
        
        # 2. General text filter (searches all columns)
        text_match = True
        if self._text_filter_string:
            text_match = False # Assume no match until one is found
            for i in range(self.sourceModel().columnCount()):
                index = self.sourceModel().index(source_row, i, source_parent)
                cell_data = str(self.sourceModel().data(index)).lower()
                if self._text_filter_string in cell_data:
                    text_match = True
                    break # Found a match, no need to check other columns
            
        return text_match and column_match


class JobQueueController:
    """Controller: Manages interaction between the model and view."""

    def __init__(self, parent_widget):
        self.parent = parent_widget
        
        self.settings_model = JobQueueModel()
        self.table_model = JobQueueTableModel()
        # Use the new custom proxy model
        self.proxy_model = JobQueueFilterProxyModel()
        
        self.proxy_model.setSourceModel(self.table_model)
        
        self.view = JobQueueView()
        self.view.setModel(self.proxy_model)
        
        self.view.setup_columns(self.settings_model.displayable_fields)
        
        header = self.view.horizontalHeader()
        header.setSectionsClickable(True)

    def update_queue_status(self, jobs_data: List[Dict[str, Any]]):
        """Update queue status by passing the full dataset to the model."""
        self.table_model.update_jobs(jobs_data)

    def filter_table_by_account(self, kws: list[str], negative=False):
        """Applies a keyword filter to the 'Account' column."""
        try:
            col_index = JOB_QUEUE_FIELDS.index("Account")
            self.proxy_model.set_column_filter(kws, col_index, negative)
        except ValueError:
            # This should not happen if "Account" is in JOB_QUEUE_FIELDS
            print("Error: 'Account' column not found in JOB_QUEUE_FIELDS definition.")

    def filter_table_by_user(self, kws: list[str], negative=False):
        """Applies a keyword filter to the 'User' column."""
        try:
            col_index = JOB_QUEUE_FIELDS.index("User")
            self.proxy_model.set_column_filter(kws, col_index, negative)
        except ValueError:
            # This should not happen if "User" is in JOB_QUEUE_FIELDS
            print("Error: 'User' column not found in JOB_QUEUE_FIELDS definition.")

    def filter_table(self, text: str):
        """Applies a text filter across all columns."""
        self.proxy_model.set_text_filter(text)

    def _shutdown(self, event_data):
        new_state = event_data.data["new_state"]
        old_state = event_data.data["old_state"]
        is_connected = new_state == ConnectionState.CONNECTED
        self.view.shutdown_ui(is_connected=is_connected)

