from modules.defaults import *


class JobQueueView:
    """View: Handles the UI display and user interactions"""
    
    def __init__(self, table_widget: QTableWidget):
        self.table = table_widget
        self.row_job_map: Dict[int, str] = {}  # row -> job_id mapping
        self._setup_table()
    
    def _setup_table(self):
        """Setup table widget properties"""
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        
        # Apply styling
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
        """Setup table columns based on visible fields"""
        self.table.setColumnCount(len(visible_fields))
        self.table.setHorizontalHeaderLabels(visible_fields)
        
        # Configure column resize modes
        header = self.table.horizontalHeader()
        for i, field in enumerate(visible_fields):
            if field == "Job Name":
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        if visible_fields:
            header.setStretchLastSection(True)
    
    def add_job_row(self, job: Dict[str, Any], visible_fields: List[str]) -> int:
        """Add a new job row and return the row index"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        job_id = job.get("Job ID", "")
        self.row_job_map[row] = job_id
        
        self._populate_row(row, job, visible_fields)
        return row
    
    def update_job_row(self, row: int, job: Dict[str, Any], visible_fields: List[str]):
        """Update an existing job row"""
        if 0 <= row < self.table.rowCount():
            self._populate_row(row, job, visible_fields)
    
    def remove_job_row(self, row: int):
        """Remove a job row"""
        if 0 <= row < self.table.rowCount():
            # Update row mappings for rows that will shift up
            job_id = self.row_job_map.get(row)
            self.table.removeRow(row)
            
            # Rebuild row mapping since indices changed
            self._rebuild_row_mapping()
    
    def _populate_row(self, row: int, job: Dict[str, Any], visible_fields: List[str]):
        """Populate a table row with job data"""
        for col, field in enumerate(visible_fields):
            item_data = job.get(field, "N/A")
            
            # Handle different data types
            if isinstance(item_data, int):
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.EditRole, item_data)
            elif isinstance(item_data, str):
                item = QTableWidgetItem(item_data)
            elif isinstance(item_data, list) and len(item_data) == 2:
                # Handle time used format [display_string, timedelta]
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.EditRole, item_data[1].seconds if hasattr(item_data[1], 'seconds') else 0)
                item.setData(Qt.ItemDataRole.DisplayRole, str(item_data[0]))
            else:
                item = QTableWidgetItem(str(item_data))
            
            # Apply status coloring for Status column
            if field == "Status":
                self._apply_status_color(item, str(item_data).upper())
            
            # Apply alternating row colors
            if row % 2 == 0:
                item.setBackground(QBrush(QColor(COLOR_DARK_BG)))
            else:
                item.setBackground(QBrush(QColor(COLOR_DARK_BG_ALT)))
            
            # Set default foreground color
            item.setForeground(QBrush(QColor(COLOR_DARK_FG)))
            
            self.table.setItem(row, col, item)
    
    def _apply_status_color(self, item: QTableWidgetItem, status: str):
        """Apply color based on job status"""
        status_colors = {
            "RUNNING": COLOR_GREEN,
            "PENDING": COLOR_ORANGE,
            "COMPLETED": COLOR_BLUE,
            "FAILED": COLOR_RED,
            "COMPLETING": COLOR_ORANGE,
            "PREEMPTED": COLOR_RED,
            "SUSPENDED": COLOR_ORANGE,
            "STOPPED": COLOR_BLUE,
            "CANCELLED": COLOR_PURPLE,
        }
        
        color = status_colors.get(status, COLOR_DARK_FG)
        item.setForeground(QBrush(QColor(color)))
    
    def _rebuild_row_mapping(self):
        """Rebuild the row to job ID mapping after row operations"""
        new_mapping = {}
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)  # Job ID is in first column
            if item:
                job_id = item.text()
                new_mapping[row] = job_id
        self.row_job_map = new_mapping
    
    def find_job_row(self, job_id: str) -> int:
        """Find the row index for a given job ID"""
        for row, mapped_job_id in self.row_job_map.items():
            if mapped_job_id == job_id:
                return row
        return -1
    
    def clear_table(self):
        """Clear all table contents"""
        self.table.setRowCount(0)
        self.row_job_map.clear()
    
    def show_connection_error(self):
        """Show connection error message"""
        self.clear_table()
        self.table.setRowCount(1)
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Status"])
        
        error_item = QTableWidgetItem("⚠️ Unavailable Connection - Please check SLURM connection")
        error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        error_item.setForeground(QBrush(QColor(COLOR_RED)))
        error_item.setFlags(error_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        
        self.table.setItem(0, 0, error_item)
        self.table.horizontalHeader().setStretchLastSection(True)
