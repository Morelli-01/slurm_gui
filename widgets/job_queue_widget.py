from torch import neg
from controllers.job_queue_controller import JobQueueController
from core.defaults import *
from core.event_bus import EventPriority, Events, get_event_bus
from core.style import AppStyles


class JobQueueWidget(QGroupBox):
    """
    Job Queue Widget with simplified MVC pattern maintaining exact original functionality.
    """

    def __init__(self, parent=None):
        super().__init__("Job Queue", parent)
        self.controller = JobQueueController(self)
        self.queue_table = self.controller.table
        self._setup_ui()
        self._apply_original_styling()
        self._event_bus_subscription()

    def _event_bus_subscription(self):
        get_event_bus().subscribe(
            Events.DISPLAY_SAVE_REQ,
            callback=lambda event: self.controller.model.load_settings() or self.controller.view.setup_columns(
                self.controller.model.displayable_fields,
                self.controller.model.visible_fields
            ),
            priority=EventPriority.LOW
        )

    def _setup_ui(self):
        """Setup UI exactly like original"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        self.layout.addWidget(self.queue_table)
        self.setMinimumHeight(200)

    def _apply_original_styling(self):
        """Apply original styling exactly"""
        self.setStyleSheet(AppStyles.get_job_queue_style())

        # Apply original scrollbar styling
        self.queue_table.verticalScrollBar().setStyleSheet(scroll_bar_stylesheet)
        self.queue_table.horizontalScrollBar().setStyleSheet(scroll_bar_stylesheet)

    # Public API - exactly like original
    def update_queue_status(self, jobs_data):
        """Update queue status - exact same interface as original"""

        self.controller.update_queue_status(jobs_data)
    
    def filter_table_by_account(self, keywords: list[str], negative=False):
        if not isinstance(keywords, list):
            keywords = [keywords]
        self.controller.filter_table_by_account(keywords, negative=negative)

    def filter_table(self, kw: str):
        if not isinstance(kw, list):
            kw = [kw]
        self.controller.view.filter_rows(kw)

    def show_all_rows(self):
        self.controller.view.filter_rows([], 0)
        