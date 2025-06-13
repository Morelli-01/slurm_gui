from core.defaults import *
from core.style import AppStyles


class JobQueueView:
    """View: Handles table display with original styling"""

    def __init__(self, table_widget: QTableWidget):
        self.table = table_widget
        self._setup_table_properties()
        self.rows: Dict[int, list[Any]] = {}

    def _setup_table_properties(self):
        """Setup table properties exactly like original"""
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

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

    def populate_table_full(self, jobs_data: List[Dict[str, Any]], displayable_fields: Dict[str, bool]):
        """Populate entire table"""
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

