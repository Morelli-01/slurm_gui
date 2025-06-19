from core.defaults import *
from core.event_bus import Events, get_event_bus
from utils import script_dir
from models.project_model import Project, Job
from typing import List


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
        self.startButton.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "submit.svg"))
        )
        layout.addWidget(self.startButton)

        self.stopButton = QPushButton()
        self.stopButton.setObjectName("actionStopBtn")
        self.stopButton.setToolTip("Stop Job")
        self.stopButton.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "stop.svg"))
        )
        layout.addWidget(self.stopButton)

        self.cancelButton = QPushButton()
        self.cancelButton.setObjectName("actionCancelBtn")
        self.cancelButton.setToolTip("Cancel Job")
        self.cancelButton.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "delete.svg"))
        )
        layout.addWidget(self.cancelButton)

        self.logsButton = QPushButton()
        self.logsButton.setObjectName("actionLogsBtn")
        self.logsButton.setToolTip("View Logs")
        self.logsButton.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "view_logs.svg"))
        )
        layout.addWidget(self.logsButton)

        self.duplicateButton = QPushButton()
        self.duplicateButton.setObjectName("actionDuplicateBtn")
        self.duplicateButton.setToolTip("Duplicate Job")
        self.duplicateButton.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "duplicate.svg"))
        )
        layout.addWidget(self.duplicateButton)

        self.modifyButton = QPushButton()
        self.modifyButton.setObjectName("actionModifyBtn")
        self.modifyButton.setToolTip("Modify Job")
        self.modifyButton.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "edit.svg"))
        )
        layout.addWidget(self.modifyButton)

        self.terminalButton = QPushButton()
        self.terminalButton.setObjectName("actionTerminalBtn")
        self.terminalButton.setToolTip("Open Terminal on Node")
        self.terminalButton.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "terminal.svg"))
        )
        layout.addWidget(self.terminalButton)


class JobsTableView(QWidget):
    """
    View to display jobs for projects. It manages a dictionary of QTableWidgets,
    one for each project, and displays them in a QStackedWidget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)

        self.tables = {}  # {project_name: QTableWidget}

        # A placeholder widget for when no project is selected
        self.placeholder_widget = QWidget()
        placeholder_layout = QVBoxLayout(self.placeholder_widget)
        placeholder_label = QLabel("Select or create a project to view its jobs.")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(placeholder_label)
        self.stacked_widget.addWidget(self.placeholder_widget)
        self.stacked_widget.setCurrentWidget(self.placeholder_widget)

    def _create_new_table(self, table_name = ''):
        """Creates and configures a new QTableWidget."""
        table = QTableWidget()
        table.setObjectName(table_name)
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(
            ["Job ID", "Job Name", "Status", "Runtime", "CPU", "RAM", "GPU", "Actions"]
        )
        table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        
        new_jobs_button = QPushButton(
            "New Job", table)  # Set self as parent
        new_jobs_button.setObjectName(BTN_GREEN)
        # new_jobs_button.clicked.connect(self.open_new_job_dialog)
        new_jobs_button.clicked.connect(lambda: print(f"jobs panel {table_name} active")) #TODO
        new_jobs_button.setFixedSize(120, 40)  # Set a fixed size
        new_jobs_button.move(self.width() - new_jobs_button.width() - 20,
                                  self.height() - new_jobs_button.height() - 20)
        return table

    def update_projects(self, projects: List[Project]):
        """Synchronizes the tables with the list of projects from the model."""
        current_projects = set(p.name for p in projects)
        existing_tables = set(self.tables.keys())

        for project_name in existing_tables - current_projects:
            self.remove_project_table(project_name)
        
        for project in projects:
            if project.name not in self.tables:
                self.add_project_table(project.name)
            self.update_jobs_for_project(project.name, project.jobs)

        if len(projects) == 1:
            self.switch_to_project(projects[0].name)


    def add_project_table(self, project_name: str):
        """Adds a new table for a project."""
        if project_name not in self.tables:
            table = self._create_new_table(project_name)
            self.tables[project_name] = table
            self.stacked_widget.addWidget(table)

    def remove_project_table(self, project_name: str):
        """Removes the table for a project."""
        if project_name in self.tables:
            table = self.tables.pop(project_name)
            self.stacked_widget.removeWidget(table)
            table.deleteLater()

    def switch_to_project(self, project_name: str):
        """Switches the view to the table for the selected project."""
        if project_name in self.tables:
            self.stacked_widget.setCurrentWidget(self.tables[project_name])
        else:
            self.stacked_widget.setCurrentWidget(self.placeholder_widget)

    def update_jobs_for_project(self, project_name: str, jobs: List[Job]):
        """Populates a project's table with its jobs."""
        if project_name in self.tables:
            table = self.tables[project_name]
            table.setRowCount(0)
            for job_data in jobs:
                self._add_job_to_table(table, job_data)

    def _add_job_to_table(self, table: QTableWidget, job_data: Job):
        """Adds a single job row to the given table."""
        row_position = table.rowCount()
        table.insertRow(row_position)
        table.setItem(row_position, 0, QTableWidgetItem(job_data.id))
        table.setItem(row_position, 1, QTableWidgetItem(job_data.name))
        table.setItem(row_position, 2, QTableWidgetItem(job_data.status))
        table.setItem(row_position, 3, QTableWidgetItem(job_data.runtime))
        table.setItem(row_position, 4, QTableWidgetItem(job_data.cpu))
        table.setItem(row_position, 5, QTableWidgetItem(job_data.ram))
        table.setItem(row_position, 6, QTableWidgetItem(job_data.gpu))
        table.setCellWidget(row_position, 7, ActionButtonsWidget())