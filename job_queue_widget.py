from pathlib import Path
from PyQt6.QtWidgets import (
    QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox
)
from PyQt6.QtGui import QColor, QFont, QBrush, QPalette
from PyQt6.QtCore import Qt, QSize, QTimer, QSettings

JOB_QUEUE_FIELDS = [
    "Job ID", "Job Name", "User",
    "Account", "Priority", "Status",
    "Time Used", "Partition", "CPUs",
    "Time Limit", "Reason", "RAM",
    "GPUs", "Nodelist"
]

# SLURM Statuses
STATUS_RUNNING = "RUNNING"
STATUS_PENDING = "PENDING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_COMPLETING = "COMPLETING"
STATUS_PREEMPTED = "PREEMPTED"
STATUS_SUSPENDED = "SUSPENDED"
STATUS_STOPPED = "STOPPED"

# Updated Color Palette (A more vibrant, modern dark theme inspired by Dracula/Nord)
COLOR_DARK_BG = "#282a36"  # Dark background
COLOR_DARK_FG = "#f8f8f2"  # Foreground text color
COLOR_DARK_BG_ALT = "#383a59"  # Alternate row background
COLOR_DARK_BG_HOVER = "#44475a"  # Hover color
COLOR_DARK_BORDER = "#6272a4"  # Border/Grid color
COLOR_GREEN = "#50fa7b"    # Running status (Dracula Green)
COLOR_RED = "#ff5555"      # Failed/Preempted status (Dracula Red)
COLOR_ORANGE = "#ffb86c"   # Pending/Completing/Suspended status (Dracula Orange)
COLOR_BLUE = "#8be9fd"     # Completed/Stopped status (Dracula Cyan)
COLOR_GRAY = "#6272a4"     # Default text color for non-status fields (Dracula Purple/Gray)


class JobQueueWidget(QGroupBox):
    """
    A widget to display the current job queue with enhanced styling.
    """

    def __init__(self, parent=None):
        super().__init__("Job Queue", parent)
        self.displayable_fields = {}
        self.current_jobs_data = []  # Store current job data

        # --- Added for sort persistence ---
        self._sorted_by_field_name = None
        self._sorted_by_order = None  # Qt.SortOrder
        # --- End of addition ---

        self.load_settings()  # Load settings to populate displayable_fields

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        self.queue_table = QTableWidget()

        # Apply overall widget styling
        self.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {COLOR_DARK_BORDER};
                border-radius: 8px;
                margin-top: 10px; /* Space for title */
                font-size: 16px;
                font-weight: bold;
                color: {COLOR_DARK_FG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left; /* Position title */
                padding: 0 3px;
                background-color: {COLOR_DARK_BG}; /* Match background */
                color: {COLOR_DARK_FG};
                margin-left: 5px;
            }}
        """)

        self._setup_table()  # Initial table setup based on loaded settings

        self.layout.addWidget(self.queue_table)

        self.setMinimumHeight(200)

        # Set palette for consistent dark mode appearance
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(COLOR_DARK_BG))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(COLOR_DARK_FG))
        palette.setColor(QPalette.ColorRole.Base, QColor(COLOR_DARK_BG))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLOR_DARK_BG_ALT))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLOR_DARK_BG))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLOR_DARK_FG))
        palette.setColor(QPalette.ColorRole.Text, QColor(COLOR_DARK_FG))
        palette.setColor(QPalette.ColorRole.Button, QColor(COLOR_DARK_BG_ALT))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLOR_DARK_FG))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(COLOR_GREEN))  # Example bright text
        palette.setColor(QPalette.ColorRole.Link, QColor(COLOR_BLUE))  # Example link color
        palette.setColor(QPalette.ColorRole.Highlight, QColor(COLOR_DARK_BG_HOVER))  # Selection background
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(COLOR_DARK_FG))  # Selection text color
        self.setPalette(palette)
        self.jobs_filter_text = ""

    def _setup_table(self):
        """Sets up the table columns and headers based on current settings with styling."""
        self.visible_fields = [field for field in JOB_QUEUE_FIELDS if self.displayable_fields.get(field, False)]

        self.queue_table.setColumnCount(len(self.visible_fields))
        self.queue_table.setHorizontalHeaderLabels(self.visible_fields)

        self.queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.queue_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.queue_table.verticalHeader().setVisible(False)

        # Apply table specific styling
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
                border-bottom: 2px solid {COLOR_BLUE}; /* Highlight bottom border */
                font-weight: bold;
            }}
            QTableWidget::item {{
                padding: 5px; /* Add some padding to items */
            }}
            QTableWidget::item:selected {{
                background-color: {COLOR_DARK_BG_HOVER};
                color: {COLOR_DARK_FG};
            }}
        """)

        header = self.queue_table.horizontalHeader()
        # Dynamically set resize mode based on visible fields
        for i, field in enumerate(self.visible_fields):
            if field == "Job Name":
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        if self.queue_table.columnCount() > 0:
            header.setStretchLastSection(True)
        else:
            header.setStretchLastSection(False)

        # --- Added for sort persistence ---
        header.setSectionsClickable(True)  # Ensure clickable
        try:  # Disconnect first to avoid multiple connections if _setup_table is called multiple times
            header.sortIndicatorChanged.disconnect(self._on_sort_indicator_changed)
        except TypeError:  # No connection existed
            pass
        header.sortIndicatorChanged.connect(self._on_sort_indicator_changed)
        # --- End of addition ---

    # --- Added for sort persistence ---
    def _on_sort_indicator_changed(self, logical_index: int, order: Qt.SortOrder):
        """
        Callback when the user clicks a header to sort. Stores the sort preference.
        """
        if 0 <= logical_index < len(self.visible_fields):
            self._sorted_by_field_name = self.visible_fields[logical_index]
            self._sorted_by_order = order
            # print(f"User sorted by: {self._sorted_by_field_name}, Order: {self._sorted_by_order}")
        else:
            # This case can happen if sort is cleared programmatically (e.g., set to -1)
            self._sorted_by_field_name = None
            self._sorted_by_order = None
            # print("Sort indicator cleared or invalid index.")
    # --- End of addition ---

    def update_queue_status(self, jobs_data):
        """
        Populates the job queue table with data for visible fields, applying status coloring.
        Takes a list of job dictionaries as input.
        Re-applies the current filter after updating.
        """
        self.current_jobs_data = jobs_data

        self.queue_table.setSortingEnabled(False)  # Disable sorting during population
        self.queue_table.setRowCount(0)  # Clear existing rows

        for row, job in enumerate(jobs_data):
            self.queue_table.insertRow(row)
            column = 0
            for field in self.visible_fields:
                item_text = str(job.get(field, "N/A"))
                item = QTableWidgetItem(item_text)

                # Apply text color based on status for the 'Status' column
                if field == "Status":
                    status = job.get("Status", "").upper()
                    color = QColor(COLOR_DARK_FG)  # Default color

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

                    item.setForeground(QBrush(color))  # Use QBrush for color

                # Set alternating row colors
                if row % 2 == 0:
                    item.setBackground(QBrush(QColor(COLOR_DARK_BG)))
                else:
                    item.setBackground(QBrush(QColor(COLOR_DARK_BG_ALT)))

                # Ensure text color is set for all items, not just status
                item.setForeground(QBrush(QColor(COLOR_DARK_FG)))
                if field == "Status":  # Re-apply status color if it's the status column
                    status = job.get("Status", "").upper()
                    color = QColor(COLOR_DARK_FG)
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

                self.queue_table.setItem(row, column, item)
                column += 1

        self.queue_table.setSortingEnabled(True)  # Re-enable sorting

        # --- Modified for sort persistence ---
        applied_user_sort = False
        if self._sorted_by_field_name and self._sorted_by_order is not None:
            if self._sorted_by_field_name in self.visible_fields:
                try:
                    column_index_to_sort = self.visible_fields.index(self._sorted_by_field_name)
                    self.queue_table.sortItems(column_index_to_sort, self._sorted_by_order)
                    applied_user_sort = True
                except ValueError:
                    # This should not happen if self._sorted_by_field_name in self.visible_fields
                    # print(f"Error: Could not find column for sorted field '{self._sorted_by_field_name}'")
                    pass  # Fall through to default sort
            # else:
                # print(f"Previously sorted field '{self._sorted_by_field_name}' is no longer visible. Applying default sort.")
                # Sorted field is not visible, fall through to default sort

        if not applied_user_sort:
            # Apply original default sort logic if no user sort was applied or applicable
            # Note: The original code's double sortItems call means the *last* one effectively
            # becomes the primary sort key if both columns are visible.
            # We replicate that behavior here.
            # These calls will trigger _on_sort_indicator_changed, updating the "last sorted" state.
            try:
                user_column_index = self.visible_fields.index("User")
                self.queue_table.sortItems(user_column_index, Qt.SortOrder.AscendingOrder)
            except ValueError:
                pass  # User column not visible

            try:
                status_column_index = self.visible_fields.index("Status")
                self.queue_table.sortItems(status_column_index, Qt.SortOrder.DescendingOrder)
            except ValueError:
                pass  # Status column not visible
        # --- End of modification ---

        # --- Add this block to re-apply the filter after updating ---
        current_filter_text = self.jobs_filter_text
        if current_filter_text:  # Only apply filter if the text box is not empty
            self.filter_table(current_filter_text)
        # --- End of added block ---

    def load_settings(self):
        """Loads settings from QSettings."""

        # Using the original path structure
        self.settings = QSettings(str(Path("./configs/settings.ini")), QSettings.Format.IniFormat)

        self.settings.beginGroup("AppearenceSettings")  # Original spelling
        for field in JOB_QUEUE_FIELDS:
            self.displayable_fields[field] = self.settings.value(field, True, type=bool)

        self.settings.endGroup()

    def reload_settings_and_redraw(self):
        """
        Reloads display settings and redraws the widget with the current data
        based on the new settings.
        """
        print("--- Reloading settings and redrawing widget ---")
        self.load_settings()  # Re-load settings

        # --- Added for sort persistence: Check if sorted field is still visible ---
        # Determine what fields will be visible *after* loading settings
        newly_visible_fields = [field for field in JOB_QUEUE_FIELDS if self.displayable_fields.get(field, False)]
        if self._sorted_by_field_name and self._sorted_by_field_name not in newly_visible_fields:
            # print(f"Sorted field '{self._sorted_by_field_name}' will be hidden. Resetting sort.")
            self._sorted_by_field_name = None
            self._sorted_by_order = None
            # The sort indicator will be cleared/updated by update_queue_status or if no data, below
        # --- End of addition ---

        self.queue_table.setSortingEnabled(False)  # Disable sorting before clearing
        self.queue_table.clear()  # Clear existing content and headers
        self._setup_table()  # Setup table with new column configuration

        # Repopulate with current data if available
        if self.current_jobs_data:
            self.update_queue_status(self.current_jobs_data)  # This will handle applying sort
        else:
            # If no data, but a sort order was remembered for a now-visible column, set the indicator
            self.queue_table.setSortingEnabled(True)  # Must be enabled to show indicator
            if self._sorted_by_field_name and self._sorted_by_field_name in self.visible_fields and self._sorted_by_order is not None:
                try:
                    idx = self.visible_fields.index(self._sorted_by_field_name)
                    self.queue_table.horizontalHeader().setSortIndicator(idx, self._sorted_by_order)
                except ValueError:  # Should not happen
                    self.queue_table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)  # Clear
            else:  # Clear sort indicator if no valid remembered sort or no data
                self.queue_table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)

        print("--- Widget redraw complete ---")

    def filter_table(self, filter_text: str):
        """
        Filters the table rows to show only those that contain the filter_text
        in any visible column.
        """
        # Ensure filter_text is a string and handle case-insensitivity
        filter_text = str(filter_text).lower()
        self.jobs_filter_text = filter_text
        # Iterate through all rows
        for row in range(self.queue_table.rowCount()):
            row_matches = False
            # Iterate through all visible columns for the current row
            for col in range(self.queue_table.columnCount()):
                item = self.queue_table.item(row, col)
                if item is not None:
                    # Get item text and check if filter_text is a substring (case-insensitive)
                    if filter_text in item.text().lower():
                        row_matches = True
                        break  # Found a match in this row, no need to check other columns

            # Set the row visibility based on whether a match was found
            self.queue_table.setRowHidden(row, not row_matches)
