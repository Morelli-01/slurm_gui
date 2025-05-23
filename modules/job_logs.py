import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QTabWidget, QWidget, QMessageBox
)
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from modules.defaults import *
from utils import script_dir


class LogFetcherThread(QThread):
    """Thread to fetch log files from the remote server"""
    log_fetched = pyqtSignal(str, str)  # stdout, stderr
    error_occurred = pyqtSignal(str)
    
    def __init__(self, slurm_connection, job_id):
        super().__init__()
        self.slurm_connection = slurm_connection
        self.job_id = job_id
        self._stop_requested = False
    
    def run(self):
        """Fetch logs from the remote server"""
        try:
            if not self.slurm_connection or not self.slurm_connection.check_connection():
                self.error_occurred.emit("Not connected to SLURM")
                return
            
            # Get the logs using the existing get_job_logs method
            stdout, stderr = self.slurm_connection.get_job_logs(self.job_id)
            self.log_fetched.emit(stdout, stderr)
            
        except Exception as e:
            self.error_occurred.emit(f"Error fetching logs: {str(e)}")
    
    def stop(self):
        """Stop the thread"""
        self._stop_requested = True


class JobLogsDialog(QDialog):
    def __init__(self, project_name, job_id, project_store, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.job_id = job_id
        self.project_store = project_store
        
        # Get SLURM connection from project store
        self.slurm_connection = None
        if self.project_store and hasattr(self.project_store, 'slurm'):
            self.slurm_connection = self.project_store.slurm
        
        self.setWindowTitle(f"Job Details - {job_id}")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        # Thread and timer for log updates
        self.log_fetcher_thread = None
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._fetch_logs)
        self.refresh_interval = 5000  # 5 seconds
        
        self._setup_stylesheet()
        self._setup_ui()
        self._load_job_data()
    
    def _setup_stylesheet(self):
        """Set up the dialog styling"""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_DARK_BG};
                color: {COLOR_DARK_FG};
            }}
            QLabel {{
                background-color: {COLOR_DARK_BG};
                color: {COLOR_DARK_FG};
                font-size: 14px;
            }}
            QTextEdit {{
                background-color: {COLOR_DARK_BG_ALT};
                color: {COLOR_DARK_FG};
                border: 1px solid {COLOR_DARK_BORDER};
                border-radius: 5px;
                padding: 10px;
                font-family: "Consolas", "Monaco", "Courier New", monospace;
                font-size: 12px;
                line-height: 1.4;
            }}
            QPushButton {{
                background-color: {COLOR_DARK_BORDER};
                color: {COLOR_DARK_FG};
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 14px;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: #3a3d4d;
            }}
            QPushButton[objectName="{BTN_BLUE}"] {{
                background-color: {COLOR_BLUE};
                color: #000000;
                font-weight: bold;
            }}
            QPushButton[objectName="{BTN_BLUE}"]:hover {{
                background-color: #c4f5ff;
            }}
            QTabWidget::pane {{
                border: 1px solid {COLOR_DARK_BORDER};
                background-color: {COLOR_DARK_BG};
                border-radius: 5px;
            }}
            QTabBar::tab {{
                background-color: {COLOR_DARK_BG_ALT};
                color: {COLOR_DARK_FG};
                padding: 8px 16px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLOR_BLUE};
                color: #000000;
                font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: #3a3d4d;
            }}
        """)
    
    def _setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel(f"Job Details: {self.job_id}")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {COLOR_BLUE}; font-size: 18px;")
        
        project_label = QLabel(f"Project: {self.project_name}")
        project_label.setStyleSheet("color: #aaaaaa; font-size: 12px;")
        
        # Status indicator for auto-refresh
        self.status_indicator = QLabel("Status: Unknown")
        self.status_indicator.setStyleSheet("font-size: 12px;")
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(self.status_indicator)
        header_layout.addStretch()
        header_layout.addWidget(project_label)
        
        layout.addLayout(header_layout)
        
        # Tab widget for different views
        self.tab_widget = QTabWidget()
        
        # Job Script Tab
        self.script_tab = QWidget()
        self._setup_script_tab()
        self.tab_widget.addTab(self.script_tab, "Job Script")
        
        # Job Info Tab
        self.info_tab = QWidget()
        self._setup_info_tab()
        self.tab_widget.addTab(self.info_tab, "Job Information")
        
        # Output Log Tab
        self.output_tab = QWidget()
        self._setup_output_tab()
        self.tab_widget.addTab(self.output_tab, "Output Log")
        
        # Error Log Tab
        self.error_tab = QWidget()
        self._setup_error_tab()
        self.tab_widget.addTab(self.error_tab, "Error Log")
        
        layout.addWidget(self.tab_widget)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName(BTN_BLUE)
        self.refresh_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "refresh.svg")))
        self.refresh_button.clicked.connect(self._refresh_data)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def _setup_script_tab(self):
        """Set up the job script tab"""
        layout = QVBoxLayout(self.script_tab)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Description
        desc_label = QLabel("SLURM Job Script:")
        desc_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(desc_label)
        
        # Script content
        self.script_text = QTextEdit()
        self.script_text.setReadOnly(True)
        self.script_text.setPlaceholderText("Job script will be displayed here...")
        layout.addWidget(self.script_text)
    
    def _setup_info_tab(self):
        """Set up the job information tab"""
        layout = QVBoxLayout(self.info_tab)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Description
        desc_label = QLabel("Job Information:")
        desc_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(desc_label)
        
        # Job info content
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setPlaceholderText("Job information will be displayed here...")
        layout.addWidget(self.info_text)
    
    def _setup_output_tab(self):
        """Set up the output log tab"""
        layout = QVBoxLayout(self.output_tab)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header with auto-refresh indicator
        header_layout = QHBoxLayout()
        
        desc_label = QLabel("Job Output Log:")
        desc_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(desc_label)
        
        self.output_refresh_label = QLabel("")
        self.output_refresh_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        header_layout.addWidget(self.output_refresh_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Output content
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setPlaceholderText("Output log will be displayed here...")
        layout.addWidget(self.output_text)
    
    def _setup_error_tab(self):
        """Set up the error log tab"""
        layout = QVBoxLayout(self.error_tab)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header with auto-refresh indicator
        header_layout = QHBoxLayout()
        
        desc_label = QLabel("Job Error Log:")
        desc_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addWidget(desc_label)
        
        self.error_refresh_label = QLabel("")
        self.error_refresh_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        header_layout.addWidget(self.error_refresh_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Error content
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        self.error_text.setPlaceholderText("Error log will be displayed here...")
        layout.addWidget(self.error_text)
    
    def _load_job_data(self):
        """Load and display job data"""
        if not self.project_store:
            self._show_error("Project store not available")
            return
        
        # Get the project
        project = self.project_store.get(self.project_name)
        if not project:
            self._show_error(f"Project '{self.project_name}' not found")
            return
        
        # Get the job
        self.job = project.get_job(self.job_id)
        if not self.job:
            self._show_error(f"Job '{self.job_id}' not found in project '{self.project_name}'")
            return
        
        # Update status indicator
        self._update_status_indicator()
        
        # Generate and display the job script
        self._display_job_script(self.job)
        
        # Display job information
        self._display_job_info(self.job)
        
        # Fetch logs for the first time
        self._fetch_logs()
        
        # Start auto-refresh if job is running
        if self.job.status == "RUNNING":
            self._start_auto_refresh()
    
    def _update_status_indicator(self):
        """Update the status indicator label"""
        if self.job:
            status_color = STATE_COLORS.get(self.job.status.lower(), COLOR_GRAY)
            self.status_indicator.setText(f"Status: {self.job.status}")
            self.status_indicator.setStyleSheet(f"color: {status_color}; font-size: 12px; font-weight: bold;")
    
    def _fetch_logs(self):
        """Fetch logs in a background thread"""
        if not self.slurm_connection:
            self.output_text.setText("Error: SLURM connection not available")
            self.error_text.setText("Error: SLURM connection not available")
            return
        
        # Create and start the thread
        self.log_fetcher_thread = LogFetcherThread(self.slurm_connection, self.job_id)
        self.log_fetcher_thread.log_fetched.connect(self._update_logs)
        self.log_fetcher_thread.error_occurred.connect(self._handle_log_error)
        self.log_fetcher_thread.start()
    
    def _update_logs(self, stdout, stderr):
        """Update the log displays with fetched content"""
        # Update output log
        if stdout:
            self.output_text.setText(stdout)
        else:
            self.output_text.setText("No output log available yet.")
        
        # Update error log
        if stderr:
            self.error_text.setText(stderr)
        else:
            self.error_text.setText("No error log available yet.")
        
        # Update refresh labels
        if self.job and self.job.status == "RUNNING":
            self.output_refresh_label.setText("(Auto-refreshing every 5 seconds)")
            self.error_refresh_label.setText("(Auto-refreshing every 5 seconds)")
        else:
            self.output_refresh_label.setText("")
            self.error_refresh_label.setText("")
    
    def _handle_log_error(self, error_message):
        """Handle errors when fetching logs"""
        error_text = f"Error fetching logs: {error_message}"
        self.output_text.setText(error_text)
        self.error_text.setText(error_text)
    
    def _start_auto_refresh(self):
        """Start the auto-refresh timer for running jobs"""
        if self.job and self.job.status == "RUNNING":
            self.refresh_timer.start(self.refresh_interval)
    
    def _stop_auto_refresh(self):
        """Stop the auto-refresh timer"""
        self.refresh_timer.stop()
    
    def _display_job_script(self, job):
        """Generate and display the SLURM job script"""
        try:
            script_lines = self._generate_slurm_script(job)
            script_content = "\n".join(script_lines)
            self.script_text.setText(script_content)
        except Exception as e:
            self.script_text.setText(f"Error generating job script:\n{str(e)}")
    
    def _generate_slurm_script(self, job):
        """Generate SLURM script lines from job data"""
        script_lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name=\"{job.name}\"",
        ]
        
        # Add basic parameters
        if job.partition:
            script_lines.append(f"#SBATCH --partition={job.partition}")
        
        if job.time_limit:
            script_lines.append(f"#SBATCH --time={job.time_limit}")
        
        if job.nodes and job.nodes > 0:
            script_lines.append(f"#SBATCH --nodes={job.nodes}")
        
        if job.cpus and job.cpus > 1:
            script_lines.append(f"#SBATCH --cpus-per-task={job.cpus}")
        
        if job.memory:
            script_lines.append(f"#SBATCH --mem={job.memory}")
        
        # Add optional parameters
        if job.account:
            script_lines.append(f"#SBATCH --account={job.account}")
        
        if job.constraints and job.constraints.strip() and "None" not in job.constraints:
            script_lines.append(f"#SBATCH --constraint={job.constraints}")
        
        if job.qos and job.qos.strip() and job.qos != "None":
            script_lines.append(f"#SBATCH --qos={job.qos}")
        
        if job.gres and job.gres.strip():
            script_lines.append(f"#SBATCH --gres={job.gres}")
        
        if job.output_file:
            script_lines.append(f"#SBATCH --output={job.output_file}")
        
        if job.error_file:
            script_lines.append(f"#SBATCH --error={job.error_file}")
        
        # Add job array specification if present
        if job.array_spec:
            array_line = f"#SBATCH --array={job.array_spec}"
            if job.array_max_jobs:
                array_line += f"%{job.array_max_jobs}"
            script_lines.append(array_line)
        
        # Add job dependencies if present
        if job.dependency:
            script_lines.append(f"#SBATCH --dependency={job.dependency}")
        
        # Add working directory change if specified
        if job.working_dir:
            script_lines.append(f"\ncd {job.working_dir}")
        
        # Add job array information if it's an array job
        if job.array_spec:
            script_lines.extend([
                "\n# Job array information",
                "echo \"Running array job ${SLURM_ARRAY_JOB_ID}, task ID ${SLURM_ARRAY_TASK_ID}\"",
                ""
            ])
        
        # Add the command
        script_lines.append("# Job command")
        if job.command:
            script_lines.append(job.command)
        else:
            script_lines.append("# No command specified")
        
        return script_lines
    
    def _display_job_info(self, job):
        """Display job information in a readable format"""
        info_lines = [
            f"Job ID: {job.id}",
            f"Job Name: {job.name}",
            f"Status: {job.status}",
            f"Project: {self.project_name}",
            "",
            "=== Resource Requirements ===",
            f"Partition: {job.partition or 'Not specified'}",
            f"Nodes: {job.nodes}",
            f"CPUs: {job.cpus}",
            f"GPUs: {job.gpus}",
            f"Memory: {job.memory or 'Not specified'}",
            f"Time Limit: {job.time_limit or 'Not specified'}",
            "",
            "=== Advanced Settings ===",
            f"Account: {job.account or 'Not specified'}",
            f"QoS: {job.qos or 'Not specified'}",
            f"Constraints: {job.constraints or 'Not specified'}",
            f"GRES: {job.gres or 'Not specified'}",
            "",
            "=== File Paths ===",
            f"Working Directory: {job.working_dir or 'Not specified'}",
            f"Output File: {job.output_file or 'Not specified'}",
            f"Error File: {job.error_file or 'Not specified'}",
            "",
            "=== Timing Information ===",
            f"Submission Time: {job.submission_time.strftime('%Y-%m-%d %H:%M:%S') if job.submission_time else 'Not submitted'}",
            f"Start Time: {job.start_time.strftime('%Y-%m-%d %H:%M:%S') if job.start_time else 'Not started'}",
            f"End Time: {job.end_time.strftime('%Y-%m-%d %H:%M:%S') if job.end_time else 'Not finished'}",
            f"Runtime: {job.get_runtime_str()}",
            "",
            "=== Job Array & Dependencies ===",
            f"Array Specification: {job.array_spec or 'Not an array job'}",
            f"Max Concurrent Jobs: {job.array_max_jobs or 'Not specified'}",
            f"Dependencies: {job.dependency or 'None'}",
            "",
            "=== Additional Information ===",
            f"Priority: {job.priority}",
            f"Node List: {job.nodelist or 'Not allocated'}",
            f"Reason: {job.reason or 'Not specified'}",
        ]
        
        # Add any extra info from the info dictionary
        if job.info:
            info_lines.append("\n=== Extended Information ===")
            for key, value in job.info.items():
                if key != "submission_details":  # Skip internal submission details
                    info_lines.append(f"{key}: {value}")
        
        info_content = "\n".join(info_lines)
        self.info_text.setText(info_content)
    
    def _refresh_data(self):
        """Refresh the displayed job data"""
        # Reload job data
        self._load_job_data()
        
        # Update status indicator
        self._update_status_indicator()
        
        # Check if we need to stop auto-refresh
        if self.job and self.job.status != "RUNNING":
            self._stop_auto_refresh()
    
    def _show_error(self, message):
        """Show an error message"""
        self.script_text.setText(f"Error: {message}")
        self.info_text.setText(f"Error: {message}")
        self.output_text.setText(f"Error: {message}")
        self.error_text.setText(f"Error: {message}")
        QMessageBox.warning(self, "Error", message)
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        # Stop auto-refresh timer
        self._stop_auto_refresh()
        
        # Stop any running threads
        if self.log_fetcher_thread and self.log_fetcher_thread.isRunning():
            self.log_fetcher_thread.stop()
            self.log_fetcher_thread.wait()
        
        event.accept()