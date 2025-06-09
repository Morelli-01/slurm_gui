
from pathlib import Path
from modules.defaults import *


class JobQueueModel:
    """Model: Manages job queue data and state"""
    
    def __init__(self):
        self.current_jobs_data: List[Dict[str, Any]] = []
        self.displayable_fields: Dict[str, bool] = {}
        self.visible_fields: List[str] = []
        
        # Filter state - exactly like original
        self.jobs_filter_text = ""
        self.jobs_filter_list: List[str] = []
        
        # Sorting state - exactly like original  
        self._sorted_by_field_name: Optional[str] = None
        self._sorted_by_order: Optional[Qt.SortOrder] = None
        
        self.load_settings()
    
    def load_settings(self):
        """Load settings exactly like original"""
        self.settings = QSettings(str(Path("./configs/settings.ini")), QSettings.Format.IniFormat)
        self.settings.beginGroup("AppearenceSettings")
        for field in JOB_QUEUE_FIELDS:
            self.displayable_fields[field] = self.settings.value(field, True, type=bool)
        self.settings.endGroup()
        
        self.visible_fields = [field for field in JOB_QUEUE_FIELDS if self.displayable_fields.get(field, False)]
    
    def update_jobs(self, new_jobs_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update job data and return information about what changed
        """
        old_jobs = {job.get("Job ID", ""): job for job in self.current_jobs_data}
        new_jobs = {job.get("Job ID", ""): job for job in new_jobs_data}
        
        changes = {
            'added_jobs': [],
            'updated_jobs': [],
            'removed_job_ids': [],
            'unchanged_jobs': [],
            'needs_full_rebuild': False
        }
        
        # Check if visible fields changed (would require full rebuild)
        if not hasattr(self, '_last_visible_fields'):
            self._last_visible_fields = self.visible_fields.copy()
            changes['needs_full_rebuild'] = True
        elif self._last_visible_fields != self.visible_fields:
            self._last_visible_fields = self.visible_fields.copy()
            changes['needs_full_rebuild'] = True
        
        if not changes['needs_full_rebuild']:
            # Find changes
            for job_id, job in new_jobs.items():
                if job_id not in old_jobs:
                    changes['added_jobs'].append(job)
                elif self._job_data_changed(old_jobs[job_id], job):
                    changes['updated_jobs'].append(job)
                else:
                    changes['unchanged_jobs'].append(job)
            
            for job_id in old_jobs:
                if job_id not in new_jobs:
                    changes['removed_job_ids'].append(job_id)
            
            # If too many changes, do full rebuild
            total_changes = len(changes['added_jobs']) + len(changes['updated_jobs']) + len(changes['removed_job_ids'])
            if total_changes > len(new_jobs_data) * 0.3:  # 30% threshold
                changes['needs_full_rebuild'] = True
        
        self.current_jobs_data = new_jobs_data.copy()
        return changes
    
    def _job_data_changed(self, old_job: Dict[str, Any], new_job: Dict[str, Any]) -> bool:
        """Check if job data changed in any visible field"""
        for field in self.visible_fields:
            if old_job.get(field) != new_job.get(field):
                return True
        return False


