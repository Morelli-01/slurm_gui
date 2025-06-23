from pathlib import Path
from core.defaults import *
from utils import settings_path
from PyQt6.QtCore import QAbstractTableModel, Qt
from typing import List, Dict, Any, Optional


class JobQueueTableModel(QAbstractTableModel):
    """A Qt-compliant table model for displaying the job queue efficiently."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._jobs: List[Dict[str, Any]] = []
        self._headers: List[str] = JOB_QUEUE_FIELDS
        self._displayable_fields: Dict[str, bool] = {}

    def rowCount(self, parent=None) -> int:
        return len(self._jobs)

    def columnCount(self, parent=None) -> int:
        return len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        job = self._jobs[index.row()]
        column_name = self._headers[index.column()]
        
        # Handle cell text
        if role == Qt.ItemDataRole.DisplayRole:
            value = job.get(column_name)
            if isinstance(value, list) and len(value) == 2:
                # Handle special 'Time Used' format
                return value[0]
            return value

        # Handle text color for the 'Status' column
        if role == Qt.ItemDataRole.ForegroundRole and column_name == "Status":
            status = str(job.get("Status", "")).lower()
            return QColor(STATE_COLORS.get(status, COLOR_DARK_FG))
            
        # Handle data for sorting
        if role == Qt.ItemDataRole.EditRole:
            value = job.get(column_name)
            if isinstance(value, list) and len(value) == 2:
                # For time, sort by seconds
                return value[1].seconds 
            return value

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if section < len(self._headers):
                return self._headers[section]
        return None

    def update_jobs(self, new_jobs: List[Dict[str, Any]]):
        """Efficiently updates the data and signals the view to redraw."""
        self.beginResetModel()
        self._jobs = new_jobs
        self.endResetModel()

    def set_displayable_fields(self, fields: Dict[str, bool]):
        """Sets which columns are available and visible."""
        self.beginResetModel()
        self._displayable_fields = fields
        # This model is no longer responsible for headers based on visibility
        self.endResetModel()


class JobQueueModel:
    """Model: Manages job queue data and state"""

    def __init__(self):
        self.current_jobs_data: List[Dict[str, Any]] = []
        self.displayable_fields: Dict[str, bool] = {}
        self.visible_fields: List[str] = []

        # Filter state
        self.jobs_filter_text = ""
        self.jobs_filter_list: List[str] = []
        self.jobs_negative_filter_list: List[str] = []

        # Sorting state
        self._sorted_by_field_name: Optional[str] = None
        self._sorted_by_order: Optional[Qt.SortOrder] = None

        self.load_settings()

    def load_settings(self):
        """Load settings for column visibility."""
        self.settings = QSettings(str(Path(settings_path)), QSettings.Format.IniFormat)

        self.settings.beginGroup("AppearenceSettings")
        for field in JOB_QUEUE_FIELDS:
            self.displayable_fields[field] = self.settings.value(field, True, type=bool)
        self.settings.endGroup()

        self.visible_fields = [
            field for field in JOB_QUEUE_FIELDS if self.displayable_fields.get(field, False)
        ]