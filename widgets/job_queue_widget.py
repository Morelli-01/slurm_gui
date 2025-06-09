from controllers.job_queue_controller import JobQueueController
from modules.defaults import *
from style import AppStyles
class JobQueueWidget(QGroupBox):
    """
    Refactored Job Queue Widget using MVC pattern with efficient updates.
    Only updates changed rows instead of rebuilding the entire table.
    """
    
    def __init__(self, parent=None):
        super().__init__("Job Queue", parent)
        self.controller = JobQueueController(self)
        self._setup_ui()
        self._apply_styling()
    
    def _setup_ui(self):
        """Setup the UI layout"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        # Add the table from controller
        self.queue_table = self.controller.get_table_widget()
        self.layout.addWidget(self.queue_table)
        
        self.setMinimumHeight(200)
    
    def _apply_styling(self):
        """Apply widget styling"""
        self.setStyleSheet(AppStyles.get_job_queue_style())
        
        # Apply scrollbar styling
        self.queue_table.verticalScrollBar().setStyleSheet(scroll_bar_stylesheet)
        self.queue_table.horizontalScrollBar().setStyleSheet(scroll_bar_stylesheet)
        

    
    # Public API methods that delegate to controller
    def update_queue_status(self, jobs_data: List[Dict[str, Any]]):
        """Update the job queue with new data"""
        self.controller.update_jobs(jobs_data)
    
    def filter_table(self, filter_text: str):
        """Filter table by text"""
        self.controller.filter_by_text(filter_text)
    
    def filter_table_by_list(self, filter_list: List[str]):
        """Filter table by list of keywords"""
        self.controller.filter_by_list(filter_list)
    
    def filter_table_by_negative_keywords(self, negative_keyword_list: List[str]):
        """Filter table by excluding keywords"""
        self.controller.filter_by_negative_keywords(negative_keyword_list)
    
    def reload_settings_and_redraw(self):
        """Reload settings and redraw the table"""
        self.controller.reload_settings()