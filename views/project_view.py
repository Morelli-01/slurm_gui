from core.defaults import *
from core.event_bus import Events, get_event_bus
from utils import script_dir
from models.project_model import Project, Job
from typing import List


class StatusBlock(QWidget):
    """A small, purely visual block showing a status icon and a count."""

    def __init__(
        self, icon_color, count_color, icon_path, count, tooltip=None, parent=None
    ):
        super().__init__(parent)
        self.setToolTip(tooltip)
        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Icon Section
        icon_label = QLabel()
        self.movie = None
        if icon_path:
            if icon_path.lower().endswith(".gif"):
                self.movie = QMovie(icon_path)
                if self.movie.isValid():
                    self.movie.setScaledSize(QSize(16, 16))
                    icon_label.setMovie(self.movie)
                    self.movie.start()
            else:
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    icon_label.setPixmap(
                        pixmap.scaled(
                            16,
                            16,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
        icon_label.setContentsMargins(0, 0, 0, 0)
        icon_section = QFrame()
        icon_section.setFixedSize(28, 28)
        icon_section.setStyleSheet(
            f"background-color: {icon_color}; border-top-left-radius: 6px; border-bottom-left-radius: 6px;"
        )
        icon_layout = QVBoxLayout(icon_section)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.addWidget(icon_label)

        # Count Section
        self.count_label = QLabel(str(count))
        self.count_label.setStyleSheet(
            "color: white; font-weight: bold; font-size: 11px;"
        )
        count_section = QFrame()
        count_section.setFixedSize(28, 28)
        count_section.setStyleSheet(
            f"background-color: {count_color}; border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
        )
        count_layout = QVBoxLayout(count_section)
        count_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_layout.addWidget(self.count_label)

        layout.addWidget(icon_section)
        layout.addWidget(count_section)


class ProjectWidget(QGroupBox):
    """A widget to display a single project, inspired by your design."""

    def __init__(self, project_name="", parent=None):
        super().__init__("", parent)
        self._is_selected = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)

        self.title_label = QLabel(project_name)
        self.title_label.setObjectName("projectWidgetTitle")
        self.layout.addWidget(self.title_label)

        status_layout = QHBoxLayout()
        self.status_bar = self._create_status_bar()
        status_layout.addWidget(self.status_bar)
        status_layout.addStretch(1)

        self.delete_button = QPushButton()
        self.delete_button.setObjectName(BTN_RED)
        self.delete_button.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "delete.svg"))
        )
        self.delete_button.setFixedSize(28, 28)
        self.delete_button.setToolTip("Delete Project")
        self.delete_button.clicked.connect(
            lambda: get_event_bus().emit(
                Events.DEL_PROJECT,
                {"project_name": self.title_label.text()},
                source="JobsPanelView.ProjectGroup.ProjectWidget",
            )
        )

        status_layout.addWidget(self.delete_button)

        self.layout.addLayout(status_layout)
        self.update_style()

    def _create_status_bar(self):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)
        self.status_blocks = {}
        configs = [
            (
                "#2DCB89",
                "#1F8A5D",
                os.path.join(script_dir, "src_static", "ok.svg"),
                "COMPLETED",
            ),
            (
                "#DA5B5B",
                "#992F2F",
                os.path.join(script_dir, "src_static", "err.svg"),
                "FAILED",
            ),
            (
                "#8570DB",
                "#5C4C9D",
                os.path.join(script_dir, "src_static", "pending.svg"),
                "PENDING",
            ),
            (
                "#6DB8E8",
                "#345D7E",
                os.path.join(script_dir, "src_static", "loading_2.gif"),
                "RUNNING",
            ),
        ]
        for icon_color, count_color, icon_path, key in configs:
            block = StatusBlock(icon_color, count_color, icon_path, 0, key.title())
            layout.addWidget(block)
            self.status_blocks[key] = block
        return container

    def update_status_counts(self, stats: dict):
        """Updates the count on each status block."""
        status_map = {
            "COMPLETED": stats.get("COMPLETED", 0),
            "FAILED": stats.get("FAILED", 0) + stats.get("CANCELLED", 0),
            "PENDING": stats.get("PENDING", 0) + stats.get("NOT_SUBMITTED", 0),
            "RUNNING": stats.get("RUNNING", 0),
        }
        for key, block in self.status_blocks.items():
            block.count_label.setText(str(status_map.get(key, 0)))

    def set_selected(self, is_selected: bool):
        if self._is_selected != is_selected:
            self._is_selected = is_selected
            self.update_style()

    def update_style(self):
        border_color = "#8be9fd" if self._is_selected else COLOR_DARK_BORDER
        border_thickness = 3 if self._is_selected else 2
        self.setStyleSheet(
            f"""
            ProjectWidget, QGroupBox {{
                border: {border_thickness}px solid {border_color};
                border-radius: 8px; margin-top: 5px; background-color: {COLOR_DARK_BG};
            }}
            QLabel#projectWidgetTitle {{ font-size: 16pt; font-weight: bold; padding-left: 5px; }}
        """
        )

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        get_event_bus().emit(
            Events.PROJECT_SELECTED,
            {"project": self.title_label.text()},
            source="JobsPanelView.ProjectGroup.ProjectWidget",
        )


class ProjectGroup(QGroupBox):
    """A scrollable container for ProjectWidgets."""

    project_selected = pyqtSignal(str)  # internal signal

    def __init__(self, parent=None):
        super().__init__("Projects", parent)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(150)
        self.layout = QVBoxLayout(self)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_content = QWidget()
        self.scroll_content_layout = QVBoxLayout(self.scroll_content)
        self.scroll_content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)
        self.add_button = QPushButton("New Project")
        self.add_button.setObjectName(BTN_GREEN)
        self.add_button.clicked.connect(self._prompt_for_new_project)
        self.layout.addWidget(self.scroll_area)
        self.layout.addWidget(self.add_button)
        self._project_widgets = {}
        self._selected_widget = None

        get_event_bus().subscribe(
            Events.PROJECT_SELECTED,
            lambda event: self.handle_project_selection(event.data["project"]),
        )

    def _prompt_for_new_project(self):
        name, ok = QInputDialog.getText(self, "New Project", "Enter the project name:")
        if ok and name:
            get_event_bus().emit(
                Events.ADD_PROJECT,
                {"project_name": name},
                source="JobsPanelView.ProjectGroup",
            )

    def update_view(self, projects: list[Project]):
        """Re-renders the entire project list based on the model state."""
        if self._selected_widget is not None and sip.isdeleted(self._selected_widget):
            active_project_name = None
        else:
            active_project_name = (
                self._selected_widget.title_label.text()
                if self._selected_widget
                else None
            )

        for widget in self._project_widgets.values():
            widget.deleteLater()
        self._project_widgets.clear()

        for project in projects:
            widget = ProjectWidget(project.name, self)
            widget.update_status_counts(project.get_job_stats())
            self.scroll_content_layout.addWidget(widget)
            self._project_widgets[project.name] = widget

        # Restore selection
        name = ""
        if active_project_name and active_project_name in self._project_widgets:
            name = active_project_name
        elif projects:
            name = projects[0].name

        
        get_event_bus().emit(
                Events.PROJECT_SELECTED,
                {"project": name},
                source="JobsPanelView.ProjectGroup",
            ) 

    def handle_project_selection(self, name: str):
        if self._selected_widget:
            self._selected_widget.set_selected(False)

        widget = self._project_widgets.get(name)
        if widget:
            widget.set_selected(True)
            self._selected_widget = widget
            self.project_selected.emit(name)
