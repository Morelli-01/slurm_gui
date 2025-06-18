from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget, QListView,
    QPushButton, QSplitter, QAbstractItemView, QHeaderView, QTableWidgetItem, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QStandardItemModel, QStandardItem
import os
from core.defaults import *
from utils import script_dir
from models.project_model import Project

import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableWidget,
    QPushButton, QSplitter, QAbstractItemView, QHeaderView, QTableWidgetItem, QLabel,
    QGroupBox, QSizePolicy, QScrollArea, QFrame, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QMovie, QPixmap, QFontMetrics, QColor

from core.defaults import *
from utils import script_dir
from models.project_model import Project

class StatusBlock(QWidget):
    """A small, purely visual block showing a status icon and a count."""
    def __init__(self, icon_color, count_color, icon_path, count, tooltip=None, parent=None):
        super().__init__(parent)
        self.setToolTip(tooltip)
        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Icon Section
        icon_label = QLabel()
        self.movie = None
        if icon_path:
            if icon_path.lower().endswith('.gif'):
                self.movie = QMovie(icon_path)
                if self.movie.isValid():
                    self.movie.setScaledSize(QSize(16, 16))
                    icon_label.setMovie(self.movie)
                    self.movie.start()
            else:
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    icon_label.setPixmap(pixmap.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        icon_label.setContentsMargins(0, 0, 0, 0)
        icon_section = QFrame()
        icon_section.setFixedSize(28, 28)
        icon_section.setStyleSheet(f"background-color: {icon_color}; border-top-left-radius: 6px; border-bottom-left-radius: 6px;")
        icon_layout = QVBoxLayout(icon_section)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.setContentsMargins(0,0,0,0)
        icon_layout.addWidget(icon_label)
        
        # Count Section
        self.count_label = QLabel(str(count))
        self.count_label.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")
        count_section = QFrame()
        count_section.setFixedSize(28, 28)
        count_section.setStyleSheet(f"background-color: {count_color}; border-top-right-radius: 6px; border-bottom-right-radius: 6px;")
        count_layout = QVBoxLayout(count_section)
        count_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_layout.addWidget(self.count_label)

        layout.addWidget(icon_section)
        layout.addWidget(count_section)

class ProjectWidget(QGroupBox):
    """A widget to display a single project, inspired by your design."""
    selected = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

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
        self.delete_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "delete.svg")))
        self.delete_button.setFixedSize(28, 28)
        self.delete_button.setToolTip("Delete Project")
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self.title_label.text()))
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
            ("#2DCB89", "#1F8A5D", os.path.join(script_dir, "src_static", "ok.svg"), "COMPLETED"),
            ("#DA5B5B", "#992F2F", os.path.join(script_dir, "src_static", "err.svg"), "FAILED"),
            ("#8570DB", "#5C4C9D", os.path.join(script_dir, "src_static", "pending.svg"), "PENDING"),
            ("#6DB8E8", "#345D7E", os.path.join(script_dir, "src_static", "loading_2.gif"), "RUNNING"),
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
        self.setStyleSheet(f"""
            ProjectWidget, QGroupBox {{
                border: {border_thickness}px solid {border_color};
                border-radius: 8px; margin-top: 5px; background-color: {COLOR_DARK_BG};
            }}
            QLabel#projectWidgetTitle {{ font-size: 16pt; font-weight: bold; padding-left: 5px; }}
        """)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.selected.emit(self.title_label.text())

class ProjectGroup(QGroupBox):
    """A scrollable container for ProjectWidgets."""
    project_selected = pyqtSignal(str)
    add_project_requested = pyqtSignal(str)
    delete_project_requested = pyqtSignal(str)

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

    def _prompt_for_new_project(self):
        name, ok = QInputDialog.getText(self, "New Project", "Enter the project name:")
        if ok and name:
            self.add_project_requested.emit(name)

    def update_view(self, projects: list[Project]):
        """Re-renders the entire project list based on the model state."""
        active_project_name = self._selected_widget.title_label.text() if self._selected_widget else None
        
        for widget in self._project_widgets.values():
            widget.deleteLater()
        self._project_widgets.clear()
        
        
        for project in projects:
            widget = ProjectWidget(project.name, self)
            widget.update_status_counts(project.get_job_stats())
            widget.selected.connect(self.handle_project_selection)
            widget.delete_requested.connect(self.delete_project_requested)
            self.scroll_content_layout.addWidget(widget)
            self._project_widgets[project.name] = widget
        
        # Restore selection
        if active_project_name and active_project_name in self._project_widgets:
             self.handle_project_selection(active_project_name)
        elif projects:
            self.handle_project_selection(projects[0].name)


    def handle_project_selection(self, name: str):
        if self._selected_widget:
            self._selected_widget.set_selected(False)
        
        widget = self._project_widgets.get(name)
        if widget:
            widget.set_selected(True)
            self._selected_widget = widget
            self.project_selected.emit(name)


class JobsPanelView(QWidget):
    """The main view for the Jobs Panel, combining projects and jobs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        self.project_group = ProjectGroup()
        splitter.addWidget(self.project_group)

        self.jobs_table_view = JobsTableView()
        splitter.addWidget(self.jobs_table_view)
        splitter.setSizes([200, 600])

class ActionButtonsWidget(QWidget):
    """Widget containing the seven action buttons for a job."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)

        self.startButton = QPushButton()
        self.startButton.setObjectName("actionSubmitBtn")
        self.startButton.setToolTip("Start Job")
        self.startButton.setIcon(QIcon(os.path.join(script_dir, 'src_static', 'submit.svg')))
        layout.addWidget(self.startButton)

        self.stopButton = QPushButton()
        self.stopButton.setObjectName("actionStopBtn")
        self.stopButton.setToolTip("Stop Job")
        self.stopButton.setIcon(QIcon(os.path.join(script_dir, 'src_static', 'stop.svg')))
        layout.addWidget(self.stopButton)

        self.cancelButton = QPushButton()
        self.cancelButton.setObjectName("actionCancelBtn")
        self.cancelButton.setToolTip("Cancel Job")
        self.cancelButton.setIcon(QIcon(os.path.join(script_dir, 'src_static', 'delete.svg')))
        layout.addWidget(self.cancelButton)

        self.logsButton = QPushButton()
        self.logsButton.setObjectName("actionLogsBtn")
        self.logsButton.setToolTip("View Logs")
        self.logsButton.setIcon(QIcon(os.path.join(script_dir, 'src_static', 'view_logs.svg')))
        layout.addWidget(self.logsButton)

        self.duplicateButton = QPushButton()
        self.duplicateButton.setObjectName("actionDuplicateBtn")
        self.duplicateButton.setToolTip("Duplicate Job")
        self.duplicateButton.setIcon(QIcon(os.path.join(script_dir, 'src_static', 'duplicate.svg')))
        layout.addWidget(self.duplicateButton)

        self.modifyButton = QPushButton()
        self.modifyButton.setObjectName("actionModifyBtn")
        self.modifyButton.setToolTip("Modify Job")
        self.modifyButton.setIcon(QIcon(os.path.join(script_dir, 'src_static', 'edit.svg')))
        layout.addWidget(self.modifyButton)

        self.terminalButton = QPushButton()
        self.terminalButton.setObjectName("actionTerminalBtn")
        self.terminalButton.setToolTip("Open Terminal on Node")
        self.terminalButton.setIcon(QIcon(os.path.join(script_dir, 'src_static', 'terminal.svg')))
        layout.addWidget(self.terminalButton)

class JobsTableView(QTableWidget):
    """Table to display jobs for a project."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(8)
        self.setHorizontalHeaderLabels([
            "Job ID", "Job Name", "Status", "Runtime",
            "CPU", "RAM", "GPU", "Actions"
        ])
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Job Name
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)

    def add_job(self, job_data):
        row_position = self.rowCount()
        self.insertRow(row_position)
        self.setItem(row_position, 0, QTableWidgetItem(job_data.id))
        self.setItem(row_position, 1, QTableWidgetItem(job_data.name))
        self.setItem(row_position, 2, QTableWidgetItem(job_data.status))
        self.setItem(row_position, 3, QTableWidgetItem(job_data.runtime))
        self.setItem(row_position, 4, QTableWidgetItem(job_data.cpu))
        self.setItem(row_position, 5, QTableWidgetItem(job_data.ram))
        self.setItem(row_position, 6, QTableWidgetItem(job_data.gpu))
        self.setCellWidget(row_position, 7, ActionButtonsWidget())

class ProjectListView(QWidget):
    """Left panel for project selection."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)
        layout.setSpacing(5)

        title = QLabel("Projects")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.list_view = QListView()
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.model = QStandardItemModel()
        self.list_view.setModel(self.model)
        layout.addWidget(self.list_view)

        button_layout = QHBoxLayout()
        self.add_project_button = QPushButton("Add")
        button_layout.addWidget(self.add_project_button)
        layout.addLayout(button_layout)

    def update_project_list(self, projects: List[Project]):
        self.model.clear()
        for project in projects:
            item = QStandardItem(project.name)
            self.model.appendRow(item)
