from core.defaults import *

TABLE_TIMEOUT = 30  

class JobQueueView(QWidget):
    """View: Handles table display with original styling"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = QTableWidget()
        self._setup_ui()
        self._setup_table_properties()
        self.rows: Dict[int, list[Any]] = {}
        self._filter: list = None
        self._table_refresh = TABLE_TIMEOUT
        self._sorted_column = None


    def _setup_ui(self):
        """Setup UI exactly like original"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        self.layout.addWidget(self.table)
        self.setMinimumHeight(200)

    def _setup_table_properties(self):
        """Setup table properties exactly like original"""
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)

        # Add listener for sorting changes and save the column index
        header = self.table.horizontalHeader()
        header.sortIndicatorChanged.connect(self._on_sort_indicator_changed)

    def _on_sort_indicator_changed(self, logicalIndex, order):
        """Listener for sorting changes, saves the sorted column index"""
        self._sorted_column = logicalIndex

    def setup_columns(self, displayable_fields: Dict[str, bool],  visible_fields: List[str]):
        """Setup columns exactly like original"""
        self.table.setColumnCount(len(displayable_fields))
        self.table.setHorizontalHeaderLabels(displayable_fields.keys())

        header = self.table.horizontalHeader()
        for i, field in enumerate(displayable_fields.keys()):
            if field not in visible_fields:
                self.table.setColumnHidden(i, True)
            else:
                self.table.setColumnHidden(i, False)
            if field == "Job Name":
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(
                    i, QHeaderView.ResizeMode.ResizeToContents)

        if self.table.columnCount() > 0:
            header.setStretchLastSection(True)
        else:
            header.setStretchLastSection(False)

    def update_table(self, jobs_data: List[Dict[str, Any]], displayable_fields: Dict[str, bool]):
        """Incremental updated table"""

        if self._table_refresh >= TABLE_TIMEOUT:
            
            self.table.clearContents()
            self.table.setRowCount(0)
            self.rows = {}
            self._table_refresh=0
            # self.table.sortItems(list(displayable_fields.keys()).index("Status"), Qt.SortOrder.DescendingOrder)


        # Get current job IDs from new data
        current_job_ids = {int(job_dict["Job ID"]) for job_dict in jobs_data}

        # Find jobs that need to be removed (exist in table but not in new data)
        jobs_to_remove = set(self.rows.keys()) - current_job_ids

        # Remove completed/missing jobs
        for job_id in jobs_to_remove:
            self.remove_job_from_table(job_id)

        for original_job_index, job_dict in enumerate(jobs_data):
            current_table_row = self.table.rowCount()

            if int(job_dict["Job ID"]) in self.rows.keys():
                row = self.rows[int(job_dict["Job ID"])]
                for col_idx, field_name in enumerate(displayable_fields.keys()):
                    item_data = job_dict.get(field_name, "N/A")
                    item = row[col_idx]

                    if isinstance(item_data, int):
                        item.setData(Qt.ItemDataRole.EditRole, item_data)
                    elif isinstance(item_data, str):
                        item.setData(Qt.ItemDataRole.EditRole, item_data)
                    else:
                        item.setData(Qt.ItemDataRole.EditRole,
                                     item_data[1].seconds)
                        item.setData(Qt.ItemDataRole.DisplayRole, item_data[0])

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
            else:
                self.table.insertRow(current_table_row)
                row = []
                job_id = None
                for col_idx, field_name in enumerate(displayable_fields.keys()):
                    item_data = job_dict.get(field_name, "N/A")

                    if field_name == "Job ID":
                        job_id = int(item_data)

                    # Handle different data types exactly like original
                    if isinstance(item_data, int):
                        item = QTableWidgetItem()
                        item.setData(Qt.ItemDataRole.EditRole, item_data)
                    elif isinstance(item_data, str):
                        item = QTableWidgetItem(item_data)
                    else:
                        item = QTableWidgetItem()
                        item.setData(Qt.ItemDataRole.EditRole,
                                     item_data[1].seconds)
                        item.setData(Qt.ItemDataRole.DisplayRole, item_data[0])

                    # Store original index for filtering - exactly like original
                    item.setData(Qt.ItemDataRole.UserRole, original_job_index)

                    # Default foreground for all items
                    item.setForeground(QBrush(QColor(COLOR_DARK_FG)))

                    # Status coloring exactly like original
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

                    # Alternating row colors exactly like original
                    if current_table_row % 2 == 0:
                        item.setBackground(QBrush(QColor(COLOR_DARK_BG)))
                    else:
                        item.setBackground(QBrush(QColor(COLOR_DARK_BG_ALT)))

                    row.append(item)
                    self.table.setItem(current_table_row, col_idx, item)

                self.rows[job_id] = row

        if self._filter:
            self.filter_rows(self._filter[0], field_index=self._filter[1], negative=self._filter[2])

        self._table_refresh+=1
        if self._sorted_column is None:
            self.table.sortItems(list(displayable_fields.keys()).index("Status"), Qt.SortOrder.DescendingOrder)

    def remove_job_from_table(self, job_id: int):
        """Remove a job from the table by job ID"""
        if job_id not in self.rows:
            return

        # Find the row in the table that contains this job
        job_items = self.rows[job_id]
        first_item = job_items[0]  # Get first item to find row position

        # Find which table row contains this item
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0) is first_item:
                self.table.removeRow(row)
                break

        # Remove from our tracking dictionary
        del self.rows[job_id]

    def filter_rows(self, keywords: list[str], field_index: int = None, negative=False):
        """Filter table rows based on keywords in specified field or all columns"""
        self._filter = []
        self._filter.append(keywords)
        self._filter.append(field_index)
        self._filter.append(negative)
        # Convert keywords to lowercase for case-insensitive matching
        keywords_lower = [keyword.lower() for keyword in keywords]

        for row in range(self.table.rowCount()):
            matches_keyword = False

            if field_index is not None:
                # Search in specific column only
                item = self.table.item(row, field_index)
                if item is not None:
                    item_text = item.text().lower()
                    matches_keyword = any(
                        keyword in item_text for keyword in keywords_lower)
            else:
                # Search in all columns
                for col in range(self.table.columnCount()):
                    # Skip hidden columns
                    # if self.table.isColumnHidden(col):
                    #     continue

                    item = self.table.item(row, col)
                    if item is not None:
                        item_text = item.text().lower()
                        if any(keyword in item_text for keyword in keywords_lower):
                            matches_keyword = True
                            break  # Found match, no need to check other columns

            if negative:
                # Hide rows that DO match the keywords
                self.table.setRowHidden(row, matches_keyword)
            else:
                # Hide rows that DON'T match the keywords
                self.table.setRowHidden(row, not matches_keyword)

    def shutdown_ui(self, is_connected=False):
        """Show only a 'No connection' panel if not connected, else restore normal UI."""
        if not hasattr(self, '_no_connection_panel'):
            self._no_connection_panel = QWidget()
            layout = QVBoxLayout(self._no_connection_panel)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel("No connection")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 22px; color: #EA3323; padding: 60px;")
            layout.addWidget(label)

        # Remove all widgets from the layout
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        if not is_connected:
            self.layout.addWidget(self._no_connection_panel)
        else:
            self.layout.addWidget(self.table)
            self.setMinimumHeight(200)