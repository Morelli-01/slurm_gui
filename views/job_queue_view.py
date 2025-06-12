from core.defaults import *


class JobQueueView:
    """View: Handles table display with original styling"""
    
    def __init__(self, table_widget: QTableWidget):
        self.table = table_widget
        self.job_row_map: Dict[str, int] = {}  # job_id -> row
        self._setup_table_properties()
    
    def _setup_table_properties(self):
        """Setup table properties exactly like original"""
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        
        # Apply original styling exactly
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLOR_DARK_BG};
                color: {COLOR_DARK_FG};
                selection-background-color: {COLOR_DARK_BG_HOVER};
                selection-color: {COLOR_DARK_FG};
                border: 1px solid {COLOR_DARK_BORDER};
                border-radius: 5px;
                gridline-color: {COLOR_DARK_BORDER};
                font-size: 16px;
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
    
    def setup_columns(self, visible_fields: List[str]):
        """Setup columns exactly like original"""
        self.table.setColumnCount(len(visible_fields))
        self.table.setHorizontalHeaderLabels(visible_fields)
        
        header = self.table.horizontalHeader()
        for i, field in enumerate(visible_fields):
            if field == "Job Name":
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        if self.table.columnCount() > 0:
            header.setStretchLastSection(True)
        else:
            header.setStretchLastSection(False)
    
    def populate_table_full(self, jobs_data: List[Dict[str, Any]], visible_fields: List[str]):
        """Populate entire table - exactly like original logic"""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.job_row_map.clear()
        
        for original_job_index, job_dict in enumerate(jobs_data):
            current_table_row = self.table.rowCount()
            self.table.insertRow(current_table_row)
            
            job_id = job_dict.get("Job ID", "")
            self.job_row_map[job_id] = current_table_row
            
            for col_idx, field_name in enumerate(visible_fields):
                item_data = job_dict.get(field_name, "N/A")
                
                # Handle different data types exactly like original
                if isinstance(item_data, int):
                    item = QTableWidgetItem()
                    item.setData(Qt.ItemDataRole.EditRole, item_data)
                elif isinstance(item_data, str):
                    item = QTableWidgetItem(item_data)
                else:
                    item = QTableWidgetItem()
                    item.setData(Qt.ItemDataRole.EditRole, item_data[1].seconds)
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
                
                self.table.setItem(current_table_row, col_idx, item)
        
        self.table.setSortingEnabled(True)
    
    def show_connection_error(self):
        """Show connection error exactly like original"""
        self.table.setRowCount(1)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Status"])
        
        error_item = QTableWidgetItem("⚠️ Unavailable Connection - Please check SLURM connection")
        error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        error_item.setForeground(QBrush(QColor(COLOR_RED)))
        error_item.setFlags(error_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        
        self.table.setItem(0, 0, error_item)
        self.table.horizontalHeader().setStretchLastSection(True)
    
    def apply_filter_to_rows(self, jobs_data: List[Dict[str, Any]], filter_func):
        """Apply filter function to table rows - exactly like original logic"""
        if self.table.columnCount() == 0:
            for r_idx in range(self.table.rowCount()):
                self.table.setRowHidden(r_idx, True)
            return
        
        for table_row_idx in range(self.table.rowCount()):
            first_item_in_row = self.table.item(table_row_idx, 0)
            
            if not first_item_in_row:
                self.table.setRowHidden(table_row_idx, True)
                continue
            
            original_job_idx = first_item_in_row.data(Qt.ItemDataRole.UserRole)
            
            if original_job_idx is None or not (0 <= original_job_idx < len(jobs_data)):
                self.table.setRowHidden(table_row_idx, True)
                continue
            
            job_data_dict = jobs_data[original_job_idx]
            row_should_be_visible = filter_func(job_data_dict)
            self.table.setRowHidden(table_row_idx, not row_should_be_visible)
    
    def update_table_incremental(self, jobs_data: List[Dict[str, Any]], visible_fields: List[str]):
        """Update the table incrementally: update values, remove missing jobs, add new jobs."""
        # Build a set of current job IDs and a mapping for quick lookup
        new_job_ids = set()
        new_job_map = {}
        for idx, job in enumerate(jobs_data):
            job_id = job.get("Job ID", "")
            new_job_ids.add(job_id)
            new_job_map[job_id] = (idx, job)

        # Remove rows for jobs that are no longer present
        current_job_ids = set(self.job_row_map.keys())
        jobs_to_remove = current_job_ids - new_job_ids
        rows_to_remove = sorted([self.job_row_map[jid] for jid in jobs_to_remove], reverse=True)
        for row in rows_to_remove:
            self.table.removeRow(row)
        for jid in jobs_to_remove:
            self.job_row_map.pop(jid, None)

        # Update existing jobs and mark which are present
        for jid in (current_job_ids & new_job_ids):
            row = self.job_row_map[jid]
            idx, job = new_job_map[jid]
            for col_idx, field_name in enumerate(visible_fields):
                item_data = job.get(field_name, "N/A")
                item = self.table.item(row, col_idx)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row, col_idx, item)
                # Update value if changed
                if isinstance(item_data, int):
                    item.setData(Qt.ItemDataRole.EditRole, item_data)
                elif isinstance(item_data, str):
                    item.setText(item_data)
                else:
                    item.setData(Qt.ItemDataRole.EditRole, item_data[1].seconds)
                    item.setData(Qt.ItemDataRole.DisplayRole, item_data[0])
                item.setData(Qt.ItemDataRole.UserRole, idx)
                item.setForeground(QBrush(QColor(COLOR_DARK_FG)))
                if field_name == "Status":
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
                if row % 2 == 0:
                    item.setBackground(QBrush(QColor(COLOR_DARK_BG)))
                else:
                    item.setBackground(QBrush(QColor(COLOR_DARK_BG_ALT)))

        # Add new jobs
        for jid in (new_job_ids - current_job_ids):
            idx, job = new_job_map[jid]
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.job_row_map[jid] = row
            for col_idx, field_name in enumerate(visible_fields):
                item_data = job.get(field_name, "N/A")
                if isinstance(item_data, int):
                    item = QTableWidgetItem()
                    item.setData(Qt.ItemDataRole.EditRole, item_data)
                elif isinstance(item_data, str):
                    item = QTableWidgetItem(item_data)
                else:
                    item = QTableWidgetItem()
                    item.setData(Qt.ItemDataRole.EditRole, item_data[1].seconds)
                    item.setData(Qt.ItemDataRole.DisplayRole, item_data[0])
                item.setData(Qt.ItemDataRole.UserRole, idx)
                item.setForeground(QBrush(QColor(COLOR_DARK_FG)))
                if field_name == "Status":
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
                if row % 2 == 0:
                    item.setBackground(QBrush(QColor(COLOR_DARK_BG)))
                else:
                    item.setBackground(QBrush(QColor(COLOR_DARK_BG_ALT)))
                self.table.setItem(row, col_idx, item)

        # Rebuild job_row_map to ensure row indices are correct
        self.job_row_map.clear()
        for row in range(self.table.rowCount()):
            job_id_item = self.table.item(row, 0)
            if job_id_item:
                job_id = job_id_item.text() if isinstance(job_id_item.text(), str) else ""
                self.job_row_map[job_id] = row

