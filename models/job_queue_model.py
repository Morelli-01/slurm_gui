from pathlib import Path
from core.defaults import *
from utils import settings_path

class JobQueueModel:
    """Model: Manages job queue data and state"""
    
    def __init__(self):
        self.current_jobs_data: List[Dict[str, Any]] = []
        self.displayable_fields: Dict[str, bool] = {}
        self.visible_fields: List[str] = []
        
        # Filter state - exactly like original
        self.jobs_filter_text = ""
        self.jobs_filter_list: List[str] = []
        self.jobs_negative_filter_list: List[str] = []  # Add missing attribute
        
        # Sorting state - exactly like original  
        self._sorted_by_field_name: Optional[str] = None
        self._sorted_by_order: Optional[Qt.SortOrder] = None
        
        self.load_settings()

    def load_settings(self):
        """Load settings exactly like original"""
        self.settings = QSettings(str(Path(settings_path)), QSettings.Format.IniFormat)
            
        self.settings.beginGroup("AppearenceSettings")
        for field in JOB_QUEUE_FIELDS:
            self.displayable_fields[field] = self.settings.value(field, True, type=bool)
        self.settings.endGroup()
        
        self.visible_fields = [field for field in JOB_QUEUE_FIELDS if self.displayable_fields.get(field, False)]