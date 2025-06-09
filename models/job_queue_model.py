
from pathlib import Path
from modules.defaults import *


class JobQueueModel:
    """Model: Manages job queue data, filtering, and sorting"""
    
    def __init__(self):
        self.raw_jobs: List[Dict[str, Any]] = []
        self.filtered_jobs: List[Dict[str, Any]] = []
        self.job_index_map: Dict[str, int] = {}  # job_id -> index in raw_jobs
        
        # Filter state
        self.text_filter = ""
        self.list_filter: List[str] = []
        self.negative_filter: List[str] = []
        self.filter_mode = "text"  # "text", "list", "negative"
        
        # Visible fields configuration
        self.visible_fields: List[str] = []
        self.displayable_fields: Dict[str, bool] = {}
        
        # Sorting state
        self.sort_field: Optional[str] = None
        self.sort_order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
        
        self._load_field_settings()
    
    def _load_field_settings(self):
        """Load which fields should be displayed from settings"""
        settings = QSettings(str(Path("./configs/settings.ini")), QSettings.Format.IniFormat)
        settings.beginGroup("AppearenceSettings")
        
        for field in JOB_QUEUE_FIELDS:
            self.displayable_fields[field] = settings.value(field, True, type=bool)
        
        settings.endGroup()
        self._update_visible_fields()
    
    def _update_visible_fields(self):
        """Update the list of visible fields based on settings"""
        self.visible_fields = [
            field for field in JOB_QUEUE_FIELDS 
            if self.displayable_fields.get(field, False)
        ]
    
    def reload_field_settings(self):
        """Reload field settings from file"""
        self._load_field_settings()
    
    def update_jobs(self, new_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update job data and return change information for efficient UI updates
        
        Returns:
            Dict with 'added', 'updated', 'removed' job information
        """
        old_job_map = {job.get("Job ID", ""): job for job in self.raw_jobs}
        new_job_map = {job.get("Job ID", ""): job for job in new_jobs}
        
        changes = {
            'added': [],
            'updated': [],
            'removed': [],
            'requires_full_rebuild': False
        }
        
        # Find added jobs
        for job_id, job in new_job_map.items():
            if job_id not in old_job_map:
                changes['added'].append(job)
        
        # Find updated jobs
        for job_id, job in new_job_map.items():
            if job_id in old_job_map:
                old_job = old_job_map[job_id]
                if self._jobs_differ(old_job, job):
                    changes['updated'].append({
                        'old': old_job,
                        'new': job,
                        'job_id': job_id
                    })
        
        # Find removed jobs
        for job_id in old_job_map:
            if job_id not in new_job_map:
                changes['removed'].append({
                    'job_id': job_id,
                    'job': old_job_map[job_id]
                })
        
        # Update internal data
        self.raw_jobs = new_jobs.copy()
        self._rebuild_job_index_map()
        
        # Reapply current filter
        self._apply_current_filter()
        
        return changes
    
    def _jobs_differ(self, job1: Dict[str, Any], job2: Dict[str, Any]) -> bool:
        """Check if two jobs are different in visible fields"""
        for field in self.visible_fields:
            if job1.get(field) != job2.get(field):
                return True
        return False
    
    def _rebuild_job_index_map(self):
        """Rebuild the job ID to index mapping"""
        self.job_index_map = {
            job.get("Job ID", ""): idx 
            for idx, job in enumerate(self.raw_jobs)
        }
    
    def set_text_filter(self, filter_text: str):
        """Set text filter and apply it"""
        self.text_filter = filter_text.lower()
        self.filter_mode = "text"
        self._apply_current_filter()
    
    def set_list_filter(self, filter_list: List[str]):
        """Set list filter and apply it"""
        self.list_filter = [f.lower() for f in filter_list if f]
        self.filter_mode = "list"
        self._apply_current_filter()
    
    def set_negative_filter(self, negative_list: List[str]):
        """Set negative filter and apply it"""
        self.negative_filter = [f.lower() for f in negative_list if f]
        self.filter_mode = "negative"
        self._apply_current_filter()
    
    def clear_filters(self):
        """Clear all filters"""
        self.text_filter = ""
        self.list_filter = []
        self.negative_filter = []
        self.filter_mode = "text"
        self._apply_current_filter()
    
    def _apply_current_filter(self):
        """Apply the current filter to raw jobs"""
        if self.filter_mode == "text" and self.text_filter:
            self.filtered_jobs = [
                job for job in self.raw_jobs 
                if self._job_matches_text_filter(job)
            ]
        elif self.filter_mode == "list" and self.list_filter:
            self.filtered_jobs = [
                job for job in self.raw_jobs 
                if self._job_matches_list_filter(job)
            ]
        elif self.filter_mode == "negative" and self.negative_filter:
            self.filtered_jobs = [
                job for job in self.raw_jobs 
                if not self._job_matches_list_filter(job, self.negative_filter)
            ]
        else:
            self.filtered_jobs = self.raw_jobs.copy()
    
    def _job_matches_text_filter(self, job: Dict[str, Any]) -> bool:
        """Check if job matches text filter"""
        if not self.text_filter:
            return True
        
        for field in JOB_QUEUE_FIELDS:
            value = job.get(field)
            if value is not None and self.text_filter in str(value).lower():
                return True
        return False
    
    def _job_matches_list_filter(self, job: Dict[str, Any], filter_list: Optional[List[str]] = None) -> bool:
        """Check if job matches list filter"""
        if filter_list is None:
            filter_list = self.list_filter
        
        if not filter_list:
            return True
        
        for field in JOB_QUEUE_FIELDS:
            value = job.get(field)
            if value is not None:
                value_str = str(value).lower()
                for filter_item in filter_list:
                    if filter_item in value_str:
                        return True
        return False
    
    def get_filtered_jobs(self) -> List[Dict[str, Any]]:
        """Get the current filtered job list"""
        return self.filtered_jobs.copy()
    
    def get_visible_fields(self) -> List[str]:
        """Get the list of visible fields"""
        return self.visible_fields.copy()
    
    def set_sort(self, field: str, order: Qt.SortOrder):
        """Set sorting parameters"""
        self.sort_field = field
        self.sort_order = order