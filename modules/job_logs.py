import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QTabWidget, QWidget, QMessageBox
)
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt
from modules.defaults import *
from utils import script_dir


class JobLogsDialog(QDialog):
    def __init__(self, project_name, job_id, project_store, parent=None):
        super().__init__(parent)
        self.project_name = project_name
        self.job_id = job_id
        self.project_store = project_store
        
        self.setWindowTitle(f"Job Details - {job_id}")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
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
        
        header_layout.addWidget(title_label)
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
        
        # Future tabs can be added here (Stdout, Stderr, etc.)
        
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
        job = project.get_job(self.job_id)
        if not job:
            self._show_error(f"Job '{self.job_id}' not found in project '{self.project_name}'")
            return
        
        # Generate and display the job script
        self._display_job_script(job)
        
        # Display job information
        self._display_job_info(job)
    
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
        self._load_job_data()
    
    def _show_error(self, message):
        """Show an error message"""
        self.script_text.setText(f"Error: {message}")
        self.info_text.setText(f"Error: {message}")
        QMessageBox.warning(self, "Error", message)