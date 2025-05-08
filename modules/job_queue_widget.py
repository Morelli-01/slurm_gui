from pathlib import Path
from PyQt6.QtWidgets import (
    QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox
)
from PyQt6.QtGui import QColor, QFont, QBrush, QPalette
from PyQt6.QtCore import Qt, QSize, QTimer, QSettings
from modules.defaults import *
from utils import get_dark_theme_stylesheet
# JOB_QUEUE_FIELDS = [
#     "Job ID", "Job Name", "User",
#     "Account", "Priority", "Status",
#     "Time Used", "Partition", "CPUs",
#     "Time Limit", "Reason", "RAM",
#     "GPUs", "Nodelist"
# ]


# Updated Color Palette
# COLOR_DARK_BG = "#282a36"
# COLOR_DARK_FG = "#f8f8f2"
# COLOR_DARK_BG_ALT = "#383a59"
# COLOR_DARK_BG_HOVER = "#44475a"
# COLOR_DARK_BORDER = "#6272a4"
# COLOR_GREEN = "#50fa7b"
# COLOR_RED = "#ff5555"
# COLOR_ORANGE = "#ffb86c"
# COLOR_BLUE = "#8be9fd"
# COLOR_GRAY = "#6272a4"


class JobQueueWidget(QGroupBox):
    """
    A widget to display the current job queue with enhanced styling
    and filtering capabilities across all job data fields.
    """

    def __init__(self, parent=None):
        super().__init__("Job Queue", parent)
        self.displayable_fields = {}
        self.current_jobs_data = []  # Store current raw job data

        self._sorted_by_field_name = None
        self._sorted_by_order = None

        self.load_settings()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        self.queue_table = QTableWidget()

        self.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {COLOR_DARK_BORDER};
                border-radius: 8px;
                margin-top: 10px;
                font-size: 16px;
                font-weight: bold;
                color: {COLOR_DARK_FG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background-color: {COLOR_DARK_BG};
                color: {COLOR_DARK_FG};
                margin-left: 5px;
            }}
        """)

        self._setup_table()
        self.layout.addWidget(self.queue_table)
        self.setMinimumHeight(200)

        self.jobs_filter_text = ""
        self.jobs_filter_list = []  # For filter_table_by_list

    def _setup_table(self):
        self.visible_fields = [field for field in JOB_QUEUE_FIELDS if self.displayable_fields.get(field, False)]

        self.queue_table.setColumnCount(len(self.visible_fields))
        self.queue_table.setHorizontalHeaderLabels(self.visible_fields)

        self.queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.queue_table.verticalHeader().setVisible(False)

        self.queue_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLOR_DARK_BG};
                color: {COLOR_DARK_FG};
                selection-background-color: {COLOR_DARK_BG_HOVER};
                selection-color: {COLOR_DARK_FG};
                border: 1px solid {COLOR_DARK_BORDER};
                border-radius: 5px;
                gridline-color: {COLOR_DARK_BORDER};
                font-size: 14px;
            }}
            QHeaderView::section {{
                background-color: {COLOR_DARK_BG_ALT};
                color: {COLOR_DARK_FG};
                padding: 5px;
                border: 1px solid {COLOR_DARK_BORDER};
                border-bottom: 2px solid {COLOR_BLUE};
                font-weight: bold;
            }}
            QTableWidget::item {{
                padding: 5px;
            }}
            QTableWidget::item:selected {{
                background-color: {COLOR_DARK_BG_HOVER};
                color: {COLOR_DARK_FG};
            }}
        """)

        header = self.queue_table.horizontalHeader()
        for i, field in enumerate(self.visible_fields):
            if field == "Job Name":
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        if self.queue_table.columnCount() > 0:
            header.setStretchLastSection(True)
        else:
            header.setStretchLastSection(False)

        header.setSectionsClickable(True)
        try:
            header.sortIndicatorChanged.disconnect(self._on_sort_indicator_changed)
        except TypeError:
            pass
        header.sortIndicatorChanged.connect(self._on_sort_indicator_changed)

    def _on_sort_indicator_changed(self, logical_index: int, order: Qt.SortOrder):
        if 0 <= logical_index < len(self.visible_fields):
            self._sorted_by_field_name = self.visible_fields[logical_index]
            self._sorted_by_order = order
        else:
            self._sorted_by_field_name = None
            self._sorted_by_order = None

    def update_queue_status(self, jobs_data):
        """
        Populates the job queue table with data for visible fields, applying status coloring.
        Stores the original index of the job data in each table item's UserRole
        to enable filtering on all job attributes (visible or not).
        Re-applies the current filter after updating.
        """
        self.current_jobs_data = list(jobs_data)  # Keep a copy of the raw data

        self.queue_table.setSortingEnabled(False)
        self.queue_table.setRowCount(0)

        for original_job_index, job_dict in enumerate(self.current_jobs_data):
            current_table_row = self.queue_table.rowCount()
            self.queue_table.insertRow(current_table_row)

            for col_idx, field_name in enumerate(self.visible_fields):
                item_text = str(job_dict.get(field_name, "N/A"))
                item = QTableWidgetItem(item_text)

                # Store the original index from self.current_jobs_data.
                # This allows filter functions to retrieve the full job_dict for this row,
                # regardless of sorting or which columns are currently visible.
                item.setData(Qt.ItemDataRole.UserRole, original_job_index)

                # Default foreground for all items
                item.setForeground(QBrush(QColor(COLOR_DARK_FG)))

                if field_name == "Status":
                    status = job_dict.get("Status", "").upper()
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

                if current_table_row % 2 == 0:
                    item.setBackground(QBrush(QColor(COLOR_DARK_BG)))
                else:
                    item.setBackground(QBrush(QColor(COLOR_DARK_BG_ALT)))

                self.queue_table.setItem(current_table_row, col_idx, item)

        self.queue_table.setSortingEnabled(True)

        applied_user_sort = False
        if self._sorted_by_field_name and self._sorted_by_order is not None:
            if self._sorted_by_field_name in self.visible_fields:
                try:
                    column_index_to_sort = self.visible_fields.index(self._sorted_by_field_name)
                    self.queue_table.sortItems(column_index_to_sort, self._sorted_by_order)
                    applied_user_sort = True
                except ValueError:
                    pass

        if not applied_user_sort:
            try:
                user_column_index = self.visible_fields.index("User")
                self.queue_table.sortItems(user_column_index, Qt.SortOrder.AscendingOrder)
            except ValueError:
                pass
            try:
                status_column_index = self.visible_fields.index("Status")
                self.queue_table.sortItems(status_column_index, Qt.SortOrder.DescendingOrder)
            except ValueError:
                pass

        # Re-apply the last used filter.
        # This assumes either jobs_filter_text or jobs_filter_list was active.
        # You might want a more sophisticated way to track the "active" filter type.
        if self.jobs_filter_text:
            self.filter_table(self.jobs_filter_text)
        elif self.jobs_filter_list:  # Check if list filter was active
            self.filter_table_by_list(self.jobs_filter_list)

    def load_settings(self):
        self.settings = QSettings(str(Path("./configs/settings.ini")), QSettings.Format.IniFormat)
        self.settings.beginGroup("AppearenceSettings")
        for field in JOB_QUEUE_FIELDS:
            self.displayable_fields[field] = self.settings.value(field, True, type=bool)
        self.settings.endGroup()

    def reload_settings_and_redraw(self):
        self.load_settings()
        newly_visible_fields = [field for field in JOB_QUEUE_FIELDS if self.displayable_fields.get(field, False)]
        if self._sorted_by_field_name and self._sorted_by_field_name not in newly_visible_fields:
            self._sorted_by_field_name = None
            self._sorted_by_order = None

        self.queue_table.setSortingEnabled(False)
        self.queue_table.clear()
        self._setup_table()

        if self.current_jobs_data:
            self.update_queue_status(self.current_jobs_data)
        else:
            self.queue_table.setSortingEnabled(True)
            if self._sorted_by_field_name and self._sorted_by_field_name in self.visible_fields and self._sorted_by_order is not None:
                try:
                    idx = self.visible_fields.index(self._sorted_by_field_name)
                    self.queue_table.horizontalHeader().setSortIndicator(idx, self._sorted_by_order)
                except ValueError:
                    self.queue_table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            else:
                self.queue_table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)

    def filter_table(self, filter_text: str):
        """
        Filters table rows. Shows a row if filter_text is found in ANY field
        (visible or not) of the corresponding job's data.
        """
        filter_text = str(filter_text).lower()
        self.jobs_filter_text = filter_text
        self.jobs_filter_list = []  # Clear list filter when text filter is used

        # If no actual data or no columns are displayed, effectively hide all rows or do nothing.
        if not self.current_jobs_data or self.queue_table.columnCount() == 0:
            for r_idx in range(self.queue_table.rowCount()):
                self.queue_table.setRowHidden(r_idx, True)  # Hide if no data to reference
            return

        for table_row_idx in range(self.queue_table.rowCount()):
            # Retrieve the first item in the current table row to get the UserRole data.
            # This item should contain the original index of the job in self.current_jobs_data.
            first_item_in_row = self.queue_table.item(table_row_idx, 0)

            if not first_item_in_row:
                # This case should ideally not happen if rows are populated correctly and columns exist.
                self.queue_table.setRowHidden(table_row_idx, True)  # Hide if no item to get data from
                continue

            original_job_idx = first_item_in_row.data(Qt.ItemDataRole.UserRole)

            if original_job_idx is None or \
               not (0 <= original_job_idx < len(self.current_jobs_data)):
                # If UserRole data is missing or index is out of bounds for current_jobs_data
                self.queue_table.setRowHidden(table_row_idx, True)
                continue

            job_data_dict = self.current_jobs_data[original_job_idx]

            row_should_be_visible = False
            if not filter_text:  # If filter_text is empty, all rows are visible
                row_should_be_visible = True
            else:
                # Iterate through ALL fields of the job_data_dict (from JOB_QUEUE_FIELDS)
                for field_key in JOB_QUEUE_FIELDS:
                    field_value_obj = job_data_dict.get(field_key)
                    if field_value_obj is not None:
                        field_value_str_lower = str(field_value_obj).lower()
                        if filter_text in field_value_str_lower:
                            row_should_be_visible = True
                            break  # Match found in this job, no need to check other fields

            self.queue_table.setRowHidden(table_row_idx, not row_should_be_visible)

    def filter_table_by_list(self, filter_list: list):
        """
        Filters table rows. Shows a row if any string from filter_list is found
        in ANY field (visible or not) of the corresponding job's data.
        """
        if not isinstance(filter_list, list):
            processed_filter_list = []
        else:
            # Convert all filter strings to lowercase and remove empty/None items
            processed_filter_list = [str(f).lower() for f in filter_list if f and str(f).strip()]

        self.jobs_filter_list = processed_filter_list  # Store for potential re-application
        self.jobs_filter_text = ""  # Clear text filter when list filter is used

        if not self.current_jobs_data or self.queue_table.columnCount() == 0:
            for r_idx in range(self.queue_table.rowCount()):
                self.queue_table.setRowHidden(r_idx, True)
            return

        for table_row_idx in range(self.queue_table.rowCount()):
            first_item_in_row = self.queue_table.item(table_row_idx, 0)

            if not first_item_in_row:
                self.queue_table.setRowHidden(table_row_idx, True)
                continue

            original_job_idx = first_item_in_row.data(Qt.ItemDataRole.UserRole)

            if original_job_idx is None or \
               not (0 <= original_job_idx < len(self.current_jobs_data)):
                self.queue_table.setRowHidden(table_row_idx, True)
                continue

            job_data_dict = self.current_jobs_data[original_job_idx]

            row_should_be_visible = False
            if not processed_filter_list:  # If filter list is empty, all rows are visible
                row_should_be_visible = True
            else:
                # Iterate through ALL fields of the job_data_dict
                for field_key in JOB_QUEUE_FIELDS:
                    field_value_obj = job_data_dict.get(field_key)
                    if field_value_obj is not None:
                        field_value_str_lower = str(field_value_obj).lower()
                        # Check if any string in the processed_filter_list is a substring
                        for filter_item_lower in processed_filter_list:
                            if filter_item_lower in field_value_str_lower:
                                row_should_be_visible = True
                                break  # Match found for this filter item
                    if row_should_be_visible:
                        break  # Match found for this job_data field

            self.queue_table.setRowHidden(table_row_idx, not row_should_be_visible)

    def filter_negative_table_by_list(self, filter_list: list):
        """
        Filters table rows. Shows a row if any string from filter_list is found
        in ANY field (visible or not) of the corresponding job's data.
        """
        if not isinstance(filter_list, list):
            processed_filter_list = []
        else:
            # Convert all filter strings to lowercase and remove empty/None items
            processed_filter_list = [str(f).lower() for f in filter_list if f and str(f).strip()]

        self.jobs_filter_list = processed_filter_list  # Store for potential re-application
        self.jobs_filter_text = ""  # Clear text filter when list filter is used

        if not self.current_jobs_data or self.queue_table.columnCount() == 0:
            for r_idx in range(self.queue_table.rowCount()):
                self.queue_table.setRowHidden(r_idx, True)
            return

        for table_row_idx in range(self.queue_table.rowCount()):
            first_item_in_row = self.queue_table.item(table_row_idx, 0)

            if not first_item_in_row:
                self.queue_table.setRowHidden(table_row_idx, True)
                continue

            original_job_idx = first_item_in_row.data(Qt.ItemDataRole.UserRole)

            if original_job_idx is None or \
               not (0 <= original_job_idx < len(self.current_jobs_data)):
                self.queue_table.setRowHidden(table_row_idx, True)
                continue

            job_data_dict = self.current_jobs_data[original_job_idx]

            row_should_be_visible = False
            if not processed_filter_list:  # If filter list is empty, all rows are visible
                row_should_be_visible = True
            else:
                # Iterate through ALL fields of the job_data_dict
                for field_key in JOB_QUEUE_FIELDS:
                    field_value_obj = job_data_dict.get(field_key)
                    if field_value_obj is not None:
                        field_value_str_lower = str(field_value_obj).lower()
                        # Check if any string in the processed_filter_list is a substring
                        for filter_item_lower in processed_filter_list:
                            if filter_item_lower in field_value_str_lower:
                                row_should_be_visible = True
                                break  # Match found for this filter item
                    if row_should_be_visible:
                        break  # Match found for this job_data field

            self.queue_table.setRowHidden(table_row_idx, not row_should_be_visible)

    def filter_table_by_negative_keywords(self, negative_keyword_list: list):
        """
        Filters table rows. Hides a row if any string from negative_keyword_list
        is found in ANY field (visible or not) of the corresponding job's data.
        Otherwise, the row is shown. If the negative_keyword_list is empty, all rows are shown.
        """
        if not isinstance(negative_keyword_list, list):
            processed_negative_list = []
        else:
            # Convert all filter strings to lowercase and remove empty/None items
            processed_negative_list = [str(f).lower() for f in negative_keyword_list if f and str(f).strip()]

        self.jobs_negative_filter_list = processed_negative_list
        self.jobs_filter_text = ""  # Clear text filter
        self.jobs_filter_list = []  # Clear list filter

        # If no actual data or no columns are displayed, hide all rows that might exist.
        # This is consistent with other filter methods.
        if not self.current_jobs_data or self.queue_table.columnCount() == 0:
            for r_idx in range(self.queue_table.rowCount()):
                self.queue_table.setRowHidden(r_idx, True)
            return

        for table_row_idx in range(self.queue_table.rowCount()):
            # Retrieve the first item in the current table row to get the UserRole data.
            first_item_in_row = self.queue_table.item(table_row_idx, 0)

            if not first_item_in_row:
                # This case should ideally not happen if rows are populated correctly and columns exist.
                self.queue_table.setRowHidden(table_row_idx, True)  # Hide if no item to get data from
                continue

            original_job_idx = first_item_in_row.data(Qt.ItemDataRole.UserRole)

            if original_job_idx is None or \
               not (0 <= original_job_idx < len(self.current_jobs_data)):
                # If UserRole data is missing or index is out of bounds for current_jobs_data
                self.queue_table.setRowHidden(table_row_idx, True)
                continue

            job_data_dict = self.current_jobs_data[original_job_idx]

            row_should_be_hidden = False  # Default to not hidden (i.e., visible)

            # Only perform checks if there are actual negative keywords to process
            if processed_negative_list:
                # Iterate through ALL fields of the job_data_dict (from JOB_QUEUE_FIELDS)
                for field_key in JOB_QUEUE_FIELDS:
                    field_value_obj = job_data_dict.get(field_key)
                    if field_value_obj is not None:
                        field_value_str_lower = str(field_value_obj).lower()
                        # Check if any string in the processed_negative_list is a substring
                        for negative_item_lower in processed_negative_list:
                            if negative_item_lower in field_value_str_lower:
                                row_should_be_hidden = True  # Found a negative keyword, so hide the row
                                break  # Found a match with a negative keyword, no need to check other negative keywords
                    if row_should_be_hidden:
                        break  # Row is already marked to be hidden, no need to check other fields

            self.queue_table.setRowHidden(table_row_idx, row_should_be_hidden)
