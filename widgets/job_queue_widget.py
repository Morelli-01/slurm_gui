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

    def _event_bus_subscription(self):
        get_event_bus().subscribe(
            Events.DISPLAY_SAVE_REQ,
            callback=self._handle_display_settings_change,
            priority=EventPriority.LOW
        )
        get_event_bus().subscribe(
            Events.CONNECTION_STATE_CHANGED,
            self.controller._shutdown
        )

    def _handle_display_settings_change(self, event):
        """
        Handles the event fired when display settings are saved.
        It reloads the settings in the model and instructs the view to update its columns.
        """
        # 1. Reload the settings in the settings_model
        self.controller.settings_model.load_settings()
        # 2. Update the view's columns based on the newly loaded settings
        self.controller.view.setup_columns(self.controller.settings_model.displayable_fields)

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
        self.controller.filter_table(kw)

    def show_all_rows(self):
        self.controller.filter_table("")

    # If you need to access the view for layout, do it from outside this widget:
    @property
    def view(self):
        return self.controller.view