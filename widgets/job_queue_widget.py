from controllers.job_queue_controller import JobQueueController
from core.defaults import *
from core.event_bus import EventPriority, Events, get_event_bus
from core.style import AppStyles


class JobQueueWidget(QGroupBox):
    """
    Job Queue Widget: pure proxy to the MVC model, no UI/layout logic here.
    """

    def __init__(self, parent=None):
        super().__init__("Job Queue", parent)
        self.controller = JobQueueController(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.controller.view)
        self._event_bus_subscription()
        # No UI/layout code here; visualization is handled by JobQueueView

    def _event_bus_subscription(self):
        get_event_bus().subscribe(
            Events.DISPLAY_SAVE_REQ,
            callback=lambda event: self.controller.model.load_settings() or self.controller.view.setup_columns(
                self.controller.model.displayable_fields,
                self.controller.model.visible_fields
            ),
            priority=EventPriority.LOW
        )
        get_event_bus().subscribe(
            Events.CONNECTION_STATE_CHANGED,
            self.controller._shutdown
        )

    # Public API - proxy to controller/view
    def update_queue_status(self, jobs_data):
        self.controller.update_queue_status(jobs_data)
    
    def filter_table_by_account(self, keywords: list[str], negative=False):
        if not isinstance(keywords, list):
            keywords = [keywords]
        self.controller.filter_table_by_account(keywords, negative=negative)

    def filter_table_by_user(self, keywords: list[str], negative=False):
        if not isinstance(keywords, list):
            keywords = [keywords]
        self.controller.filter_table_by_user(keywords, negative=negative)

    def filter_table(self, kw: str):
        if not isinstance(kw, list):
            kw = [kw]
        self.controller.view.filter_rows(kw)

    def show_all_rows(self):
        self.controller.view.filter_rows([], 0)

    # If you need to access the view for layout, do it from outside this widget:
    @property
    def view(self):
        return self.controller.view
