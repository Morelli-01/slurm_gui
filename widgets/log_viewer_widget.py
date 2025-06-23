import os
import re
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTabWidget,
    QWidget,
    QPlainTextEdit,
    QPushButton,
    QHBoxLayout,
    QLabel,
)
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
        log_font = QFont("Consolas" if os.name == "nt" else "Monospace", 10)

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

    def _process_log_for_display(self, content: str) -> str:
        """
        Processes log content to correctly render progress bars and carriage returns.
        """
        if not content:
            return ""

        # Remove ANSI escape codes
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        content = ansi_escape.sub("", content)

        # Normalize line endings
        content = content.replace("\r\n", "\n")

        lines = content.split("\n")
        final_lines = []
        for line in lines:
            # The last part of a \r-split line is the final visual state.
            final_lines.append(line.split("\r")[-1])

        return "\n".join(final_lines)

    
    def _update_logs(self):
        """Fetches and displays the latest content of the log files, preserving scroll position if possible."""

        def update_view(view, path, not_defined_msg):
            if path:
                content, err = self.slurm_api.read_remote_file(path)
                if err:
                    new_text = f"Could not load log file:\n{path}\n\nError:\n{err}"
                else:
                    new_text = self._process_log_for_display(content)
            else:
                new_text = not_defined_msg

            # Only update if content changed
            old_text = view.toPlainText()
            if old_text != new_text:
                # Save scroll position
                scrollbar = view.verticalScrollBar()
                old_value = scrollbar.value()
                max_value = scrollbar.maximum()
                at_bottom = old_value == max_value

                view.setPlainText(new_text)

                # Restore scroll position
                if at_bottom:
                    scrollbar.setValue(scrollbar.maximum())
                else:
                    # Try to restore previous position (may not be perfect if line count changed)
                    scrollbar.setValue(min(old_value, scrollbar.maximum()))

        # Update error log
        error_path = self._resolve_log_path(self.job.error_file)
        update_view(
            self.error_view, error_path, "Error log path not defined for this job."
        )

        # Update output log
        output_path = self._resolve_log_path(self.job.output_file)
        update_view(
            self.output_view, output_path, "Output log path not defined for this job."
        )

    def closeEvent(self, event):
        """Ensures the timer is stopped when the dialog is closed."""
        if hasattr(self, "timer"):
            self.timer.stop()
        event.accept()
