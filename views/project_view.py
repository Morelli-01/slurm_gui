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
        icon_section.setFixedSize(24, 24)
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
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_section = QFrame()
        count_section.setFixedHeight(24)
        count_section.setStyleSheet(
            f"background-color: {count_color}; border-top-right-radius: 6px; border-bottom-right-radius: 6px;"
        )
        count_layout = QVBoxLayout(count_section)
        count_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_layout.setContentsMargins(4, 0, 4, 0)
        count_layout.addWidget(self.count_label)
        self.count_section = count_section

        layout.addWidget(icon_section)
        layout.addWidget(count_section)
        self.set_count(count)

    def set_count(self, count):
        """Update count text and size the badge so multi-digit numbers are visible."""
        text = str(count)
        self.count_label.setText(text)
        metrics = QFontMetrics(self.count_label.font())
        needed_width = max(24, metrics.horizontalAdvance(text) + 12)
        self.count_section.setFixedWidth(needed_width)


class ProjectWidget(QGroupBox):
    """A widget to display a single project, inspired by your design."""

    def __init__(self, project_name="", parent=None):
        super().__init__("", parent)
        self._is_selected = False
        self._project_name = project_name
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)
        self.layout.setContentsMargins(10, 10, 10, 10)

        self.title_label = QLabel(project_name)
        self.title_label.setObjectName("projectWidgetTitle")
        self.title_label.setWordWrap(False)
        self.layout.addWidget(self.title_label)

        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)
        self.status_bar = self._create_status_bar()
        status_layout.addWidget(self.status_bar)
        status_layout.addStretch(1)

        self.delete_button = QPushButton()
        self.delete_button.setObjectName(BTN_RED)
        self.delete_button.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "delete.svg"))
        )
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.setToolTip("Delete Project")
        self.delete_button.clicked.connect(
            lambda: get_event_bus().emit(
                Events.DEL_PROJECT,
                {"project_name": self._project_name},
                source="JobsPanelView.ProjectGroup.ProjectWidget",
            )
        )

        status_layout.addWidget(self.delete_button)

        self.layout.addLayout(status_layout)
        self._refresh_title_elide()
        self.update_style()

    def _create_status_bar(self):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setSpacing(4)
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
            block.set_count(status_map.get(key, 0))

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
            {"project": self._project_name},
            source="JobsPanelView.ProjectGroup.ProjectWidget",
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_title_elide()

    def _refresh_title_elide(self):
        metrics = QFontMetrics(self.title_label.font())
        max_width = max(40, self.width() - 28)
        elided = metrics.elidedText(
            self._project_name,
            Qt.TextElideMode.ElideRight,
            max_width,
        )
        self.title_label.setText(elided)
        self.title_label.setToolTip(self._project_name)


class ProjectGroup(QGroupBox):
    """A scrollable container for ProjectWidgets."""

    project_selected = pyqtSignal(str)  # internal signal

    def __init__(self, parent=None):
        super().__init__("Projects", parent)
        self.setObjectName("projectGroup")
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(300)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self.filter_input = QLineEdit()
        self.filter_input.setObjectName("projectFilterInput")
        self.filter_input.setPlaceholderText("Filter projects...")
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.textChanged.connect(self._handle_filter_changed)
        controls_layout.addWidget(self.filter_input, 1)

        self.project_count_label = QLabel("0 projects")
        self.project_count_label.setObjectName("projectCountLabel")
        controls_layout.addWidget(self.project_count_label)

        self.layout.addLayout(controls_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

        self._apply_local_styles()

    def _prompt_for_new_project(self):
        name, ok = QInputDialog.getText(self, "New Project", "Enter the project name:")
        if ok and name:
            get_event_bus().emit(
                Events.ADD_PROJECT,
                {"project_name": name},
                source="JobsPanelView.ProjectGroup",
            )

    def update_view(self, projects: list[Project]):
        """Incrementally updates the project list without recreating every widget."""
        if self._selected_widget is not None and sip.isdeleted(self._selected_widget):
            self._selected_widget = None

        previous_selected_name = (
            self._selected_widget._project_name if self._selected_widget else None
        )

        incoming_names = [project.name for project in projects]
        incoming_set = set(incoming_names)

        # Remove deleted projects.
        for existing_name in list(self._project_widgets.keys()):
            if existing_name not in incoming_set:
                widget = self._project_widgets.pop(existing_name)
                if widget == self._selected_widget:
                    self._selected_widget = None
                self.scroll_content_layout.removeWidget(widget)
                widget.deleteLater()

        # Insert new projects and move existing ones to preserve model order.
        for index, project in enumerate(projects):
            widget = self._project_widgets.get(project.name)
            if widget is None:
                widget = ProjectWidget(project.name, self)
                self._project_widgets[project.name] = widget
                self.scroll_content_layout.insertWidget(index, widget)
            else:
                current_index = self.scroll_content_layout.indexOf(widget)
                if current_index != index:
                    self.scroll_content_layout.removeWidget(widget)
                    self.scroll_content_layout.insertWidget(index, widget)
            widget.update_status_counts(project.get_job_stats())

        visible_project_names = self._apply_project_filter()

        # Keep prior selection if still valid, else select first project if available.
        selected_name = None
        if previous_selected_name and previous_selected_name in visible_project_names:
            selected_name = previous_selected_name
        elif visible_project_names:
            selected_name = visible_project_names[0]

        if selected_name:
            self.handle_project_selection(selected_name)
            if selected_name != previous_selected_name:
                get_event_bus().emit(
                    Events.PROJECT_SELECTED,
                    {"project": selected_name},
                    source="JobsPanelView.ProjectGroup",
                )
            return

        if self._selected_widget:
            self._selected_widget.set_selected(False)
            self._selected_widget = None

        # When no project exists, force the jobs table to fallback placeholder.
        if previous_selected_name is not None:
            get_event_bus().emit(
                Events.PROJECT_SELECTED,
                {"project": ""},
                source="JobsPanelView.ProjectGroup",
            )

    def handle_project_selection(self, name: str):
        if self._selected_widget and not sip.isdeleted(self._selected_widget):
            self._selected_widget.set_selected(False)

        self._selected_widget = None
        widget = self._project_widgets.get(name)
        if widget and widget.isVisible():
            widget.set_selected(True)
            self._selected_widget = widget
            self.project_selected.emit(name)

    def _handle_filter_changed(self):
        visible_project_names = self._apply_project_filter()
        if self._selected_widget and self._selected_widget._project_name in visible_project_names:
            return

        if visible_project_names:
            get_event_bus().emit(
                Events.PROJECT_SELECTED,
                {"project": visible_project_names[0]},
                source="JobsPanelView.ProjectGroup",
            )
            return

        if self._selected_widget:
            self._selected_widget.set_selected(False)
            self._selected_widget = None

        get_event_bus().emit(
            Events.PROJECT_SELECTED,
            {"project": ""},
            source="JobsPanelView.ProjectGroup",
        )

    def _apply_project_filter(self) -> list[str]:
        filter_text = self.filter_input.text().strip().lower()
        visible_names = []
        for name, widget in self._project_widgets.items():
            visible = not filter_text or filter_text in name.lower()
            widget.setVisible(visible)
            if visible:
                visible_names.append(name)

        total_projects = len(self._project_widgets)
        if filter_text:
            self.project_count_label.setText(f"{len(visible_names)}/{total_projects}")
        else:
            label = "project" if total_projects == 1 else "projects"
            self.project_count_label.setText(f"{total_projects} {label}")
        return visible_names

    def _apply_local_styles(self):
        self.setStyleSheet(
            f"""
            QLineEdit#projectFilterInput {{
                min-height: 34px;
            }}
            QLabel#projectCountLabel {{
                color: {COLOR_GRAY};
                font-size: 12px;
                padding-right: 2px;
            }}
            """
        )
