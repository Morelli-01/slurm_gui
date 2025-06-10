from controllers.job_queue_controller import JobQueueController
from modules.defaults import *
from core.style import AppStyles


class JobQueueWidget(QGroupBox):
    """
    Refactored Job Queue Widget with MVC pattern but maintaining exact original functionality.
    """

    def __init__(self, parent=None):
        super().__init__("Job Queue", parent)
        self.controller = JobQueueController(self)
        self.queue_table = self.controller.table
        self._setup_ui()
        self._apply_original_styling()

    def _setup_ui(self):
        """Setup UI exactly like original"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        self.layout.addWidget(self.queue_table)
        self.setMinimumHeight(200)

    def _apply_original_styling(self):
        """Apply original styling exactly"""
        self.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {COLOR_DARK_BORDER};
                border-radius: 8px;
                margin-top: 10px;
                font-size: 20px;
                font-weight: bold;
                color: {COLOR_DARK_FG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background-color: {COLOR_DARK_BG};
                color: {COLOR_DARK_FG};
                margin-left: 5px;
            }}
        """)

        # Apply original scrollbar styling
        self.queue_table.verticalScrollBar().setStyleSheet(scroll_bar_stylesheet)
        self.queue_table.horizontalScrollBar().setStyleSheet(scroll_bar_stylesheet)

    # Public API - exactly like original
    def update_queue_status(self, jobs_data):
        """Update queue status - exact same interface as original"""
        self.controller.update_queue_status(jobs_data)

    def filter_table(self, filter_text: str):
        """Filter table - exact same interface as original"""
        self.controller._filter_table(filter_text)

    def filter_table_by_list(self, filter_list: list):
        """Filter table by list - exact same interface as original"""
        self.controller._filter_table_by_list(filter_list)

    def filter_table_by_negative_keywords(self, negative_keyword_list: list):
        """Filter table by negative keywords - exact same interface as original"""
        self.controller._filter_table_by_negative_keywords(negative_keyword_list)

    def reload_settings_and_redraw(self):
        """Reload settings - exact same interface as original"""
        self.controller.model.load_settings()
        # Clear sorting state if sorted field no longer visible
        if (self.controller.model._sorted_by_field_name and 
            self.controller.model._sorted_by_field_name not in self.controller.model.visible_fields):
            self.controller.model._sorted_by_field_name = None
            self.controller.model._sorted_by_order = None

        self.queue_table.setSortingEnabled(False)
        self.queue_table.clear()
        self.controller.view.setup_columns(self.controller.model.visible_fields)

        if self.controller.model.current_jobs_data:
            self.controller.update_queue_status(self.controller.model.current_jobs_data)
        else:
            self.queue_table.setSortingEnabled(True)
            if (self.controller.model._sorted_by_field_name and 
                self.controller.model._sorted_by_field_name in self.controller.model.visible_fields and 
                self.controller.model._sorted_by_order is not None):
                try:
                    idx = self.controller.model.visible_fields.index(self.controller.model._sorted_by_field_name)
                    self.queue_table.horizontalHeader().setSortIndicator(idx, self.controller.model._sorted_by_order)
                except ValueError:
                    self.queue_table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
            else:
                self.queue_table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
