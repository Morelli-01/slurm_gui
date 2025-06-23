from core.defaults import *
import traceback

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
        self._table_refresh = 0
        self._sorted_column = None


    def _setup_ui(self):
        """Setup UI exactly like original"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        self.layout.addWidget(self.table)
        self.setMinimumHeight(200)

    def _setup_table_properties(self):
        """Setup table properties with cell selection and copy functionality"""
        # Allow both row and cell selection
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        
        # Enable text selection within cells
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        # Hide vertical header
        self.table.verticalHeader().setVisible(False)
        
        # Enable sorting
        self.table.setSortingEnabled(True)
        
        # Enable context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Add listener for sorting changes and save the column index
        header = self.table.horizontalHeader()
        header.sortIndicatorChanged.connect(self._on_sort_indicator_changed)
    def _show_context_menu(self, position):
        """Show context menu for copying cell values"""
        if not self.table.itemAt(position):
            return
            
        menu = QMenu(self)
        
        # Copy selected cell(s)
        copy_action = QAction("Copy", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self._copy_selected_cells)
        menu.addAction(copy_action)
        
        # Copy entire row
        copy_row_action = QAction("Copy Row", self)
        copy_row_action.triggered.connect(self._copy_selected_row)
        menu.addAction(copy_row_action)
        
        # Select all in column
        select_column_action = QAction("Select Column", self)
        select_column_action.triggered.connect(self._select_column)
        menu.addAction(select_column_action)
        
        menu.exec(self.table.mapToGlobal(position))
    
    def _copy_selected_cells(self):
        """Copy selected cell values to clipboard"""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
            
        # Group items by row for proper formatting
        rows_data = {}
        for item in selected_items:
            row = item.row()
            col = item.column()
            if row not in rows_data:
                rows_data[row] = {}
            rows_data[row][col] = item.text()
        
        # Create clipboard text
        clipboard_text = []
        for row in sorted(rows_data.keys()):
            row_data = rows_data[row]
            # Sort columns and join with tabs
            row_text = "\t".join(row_data[col] for col in sorted(row_data.keys()))
            clipboard_text.append(row_text)
        
        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(clipboard_text))

    def _copy_selected_row(self):
        """Copy entire row(s) to clipboard"""
        selected_rows = set(item.row() for item in self.table.selectedItems())
        if not selected_rows:
            return
            
        clipboard_text = []
        for row in sorted(selected_rows):
            row_data = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    row_data.append(item.text())
                else:
                    row_data.append("")
            clipboard_text.append("\t".join(row_data))
        
        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(clipboard_text))

    def _select_column(self):
        """Select entire column based on current selection"""
        current_item = self.table.currentItem()
        if current_item:
            column = current_item.column()
            self.table.selectColumn(column)

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

    def update_table(self, jobs_data: List[Dict[str, Any]], displayable_fields: Dict[str, bool], is_recovery: bool = False):
        """
        Incrementally update the table. If an error occurs, it attempts
        a full redraw from scratch as a recovery mechanism.
        """
        try:
            self.table.setUpdatesEnabled(False)
            self.table.setSortingEnabled(False)
            
            # Sort jobs data
            jobs_data = sorted(jobs_data, key=lambda job: (job.get("Status", ""), -ord(job.get("User", " ")[0])-0.01*ord(job.get("User","  ")[1])), reverse=True)
            
            # Create a map of job IDs to their data for efficient lookup
            jobs_data_map = {job["Job ID"]: job for job in jobs_data if "Job ID" in job}
            current_job_ids = set(jobs_data_map.keys())
            
            # Create a map of existing job IDs in the table to their row index
            job_id_to_row = {}
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0) # Job ID is in the first column
                if item:
                    job_id_to_row[item.text()] = row
            
            existing_job_ids = set(job_id_to_row.keys())
            
            # Find jobs to remove
            jobs_to_remove = existing_job_ids - current_job_ids
            rows_to_remove = sorted([job_id_to_row[job_id] for job_id in jobs_to_remove], reverse=True)
            
            for row in rows_to_remove:
                self.table.removeRow(row)

            # Update existing rows and add new ones
            for job_id, job_dict in jobs_data_map.items():
                if job_id in job_id_to_row:
                    # Update existing row
                    row = job_id_to_row[job_id]
                    for col_idx, field_name in enumerate(displayable_fields.keys()):
                        item = self.table.item(row, col_idx)
                        item_data = job_dict.get(field_name, "N/A")
                        
                        # Update item data
                        if isinstance(item_data, (int, str)):
                            item.setData(Qt.ItemDataRole.EditRole, item_data)
                        elif isinstance(item_data, (list, tuple)) and len(item_data) == 2:
                            item.setData(Qt.ItemDataRole.EditRole, item_data[1].seconds)
                            item.setData(Qt.ItemDataRole.DisplayRole, item_data[0])
                        else:
                            item.setData(Qt.ItemDataRole.DisplayRole, str(item_data))
                        
                        if field_name == "Status":
                            status = job_dict.get("Status", "").upper()
                            color = QColor(STATE_COLORS.get(status.lower(), COLOR_DARK_FG))
                            item.setForeground(QBrush(color))
                else:
                    # Add new row
                    row_position = self.table.rowCount()
                    self.table.insertRow(row_position)
                    for col_idx, field_name in enumerate(displayable_fields.keys()):
                        item = QTableWidgetItem()
                        item_data = job_dict.get(field_name, "N/A")
                        
                        if isinstance(item_data, int):
                            item.setData(Qt.ItemDataRole.EditRole, item_data)
                        elif isinstance(item_data, str):
                            item.setData(Qt.ItemDataRole.DisplayRole, item_data)
                        elif isinstance(item_data, (list, tuple)) and len(item_data) == 2:
                            item.setData(Qt.ItemDataRole.EditRole, item_data[1].seconds)
                            item.setData(Qt.ItemDataRole.DisplayRole, item_data[0])
                        else:
                            item.setData(Qt.ItemDataRole.DisplayRole, str(item_data))
                        
                        if field_name == "Status":
                            status = job_dict.get("Status", "").upper()
                            color = QColor(STATE_COLORS.get(status.lower(), COLOR_DARK_FG))
                            item.setForeground(QBrush(color))
                        
                        if row_position % 2 == 0:
                            item.setBackground(QBrush(QColor(COLOR_DARK_BG)))
                        else:
                            item.setBackground(QBrush(QColor(COLOR_DARK_BG_ALT)))
                            
                        self.table.setItem(row_position, col_idx, item)

            if self._filter:
                self.filter_rows(self._filter[0], field_index=self._filter[1], negative=self._filter[2])

        except Exception as e:
            print(f"--- ERROR IN JobQueueView.update_table ---")
            traceback.print_exc()
            print(f"Error: {e}")
            
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)

    def remove_job_from_table(self, job_id: int):
        """Remove a job from the table by job ID"""
        # Find the row containing this job ID
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)  # Job ID is in first column
            if item and item.text() == str(job_id):
                self.table.removeRow(row)
                break
        
        # Remove from tracking dictionary if it exists
        if job_id in self.rows:
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

            if not any(keywords_lower):
                 matches_keyword = True
            elif field_index is not None:
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
