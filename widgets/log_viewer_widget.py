import os
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QWidget, QPlainTextEdit, QPushButton, QHBoxLayout, QLabel
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont
from models.project_model import Job
from core.slurm_api import SlurmAPI
from core.style import AppStyles
from core.defaults import STATUS_RUNNING, STATUS_COMPLETING

class LogViewerDialog(QDialog):
    """
    A dialog for viewing job logs, including the submission script,
    standard output, and standard error. Features auto-refresh for running jobs.
    """

    def __init__(self, job: Job, parent=None):
        super().__init__(parent)
        self.job = job
        self.slurm_api = SlurmAPI()
        
        self.setWindowTitle(f"Logs for Job: {self.job.name} ({self.job.id})")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(AppStyles.get_complete_stylesheet())

        self._setup_ui()
        self._load_initial_data()

        # Setup a timer to refresh logs if the job is in a running state.
        if self.job.status in [STATUS_RUNNING, STATUS_COMPLETING]:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._update_logs)
            self.timer.start(5000)  # Refresh every 5 seconds

    def _setup_ui(self):
        """Initializes the user interface of the dialog."""
        layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Common font for log views
        log_font = QFont("Consolas" if os.name == 'nt' else "Monospace", 10)

        # Tab 1: Job Script
        script_tab = QWidget()
        script_layout = QVBoxLayout(script_tab)
        self.script_view = QPlainTextEdit()
        self.script_view.setReadOnly(True)
        self.script_view.setFont(log_font)
        script_layout.addWidget(self.script_view)
        self.tab_widget.addTab(script_tab, "Job Script")

        # Tab 2: Error Log
        error_tab = QWidget()
        error_layout = QVBoxLayout(error_tab)
        self.error_view = QPlainTextEdit()
        self.error_view.setReadOnly(True)
        self.error_view.setFont(log_font)
        error_layout.addWidget(self.error_view)
        self.tab_widget.addTab(error_tab, "Error Log")

        # Tab 3: Output Log
        output_tab = QWidget()
        output_layout = QVBoxLayout(output_tab)
        self.output_view = QPlainTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setFont(log_font)
        output_layout.addWidget(self.output_view)
        self.tab_widget.addTab(output_tab, "Output Log")

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

    def _resolve_log_path(self, log_path_template: str) -> str:
        """Replaces SLURM filename patterns (%A, %a) with job ID."""
        if not log_path_template or not self.job.id:
            return ""
        # Basic replacement for job ID. A more advanced implementation
        # could handle more SLURM filename patterns.
        return log_path_template.replace("%A", str(self.job.id))

    def _load_initial_data(self):
        """Loads the initial content for all tabs."""
        # Load job script
        script_content = self.job.create_sbatch_script()
        self.script_view.setPlainText(script_content)

        # Load log files
        self._update_logs()

    def _update_logs(self):
        """Fetches and displays the latest content of the log files."""
        # Update error log
        error_path = self._resolve_log_path(self.job.error_file)
        if error_path:
            content, err = self.slurm_api.read_remote_file(error_path)
            if err:
                self.error_view.setPlainText(f"Could not load log file:\n{error_path}\n\nError:\n{err}")
            else:
                self.error_view.setPlainText(content)
        else:
            self.error_view.setPlainText("Error log path not defined for this job.")

        # Update output log
        output_path = self._resolve_log_path(self.job.output_file)
        if output_path:
            content, err = self.slurm_api.read_remote_file(output_path)
            if err:
                self.output_view.setPlainText(f"Could not load log file:\n{output_path}\n\nError:\n{err}")
            else:
                self.output_view.setPlainText(content)
        else:
            self.output_view.setPlainText("Output log path not defined for this job.")

    def closeEvent(self, event):
        """Ensures the timer is stopped when the dialog is closed."""
        if hasattr(self, 'timer'):
            self.timer.stop()
        event.accept()