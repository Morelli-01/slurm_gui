"""
Job Creation Dialog - Simple tabbed interface for creating SLURM jobs
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLineEdit, QSpinBox, QTextEdit, QDialogButtonBox,
    QLabel, QComboBox, QCheckBox, QGroupBox, QPushButton,
    QFileDialog, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from models.project_model import Job
from core.defaults import *
from core.style import AppStyles
from core.slurm_api import ConnectionState, SlurmAPI
import uuid


class JobCreationDialog(QDialog):
    """Dialog for creating a new SLURM job with tabbed interface"""
    
    jobCreated = pyqtSignal(object)  # Emits Job object
    
    def __init__(self, parent=None, project_name=None):
        super().__init__(parent)
        self.project_name = project_name
        self.setWindowTitle("Create New Job")
        self.setModal(True)
        self.setMinimumSize(700, 600)
        self.slurm_api = SlurmAPI()
        # Apply dark theme
        self.setStyleSheet(AppStyles.get_complete_stylesheet(THEME_DARK))
        
        # Create the job object
        self.job = Job()
        self.job.id = str(uuid.uuid4())
        if project_name:
            self.job.project_name = project_name
            
        self._setup_ui()
        self._connect_signals()
        self._update_preview()
        
    def _setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("Create New SLURM Job")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self._create_basic_tab()
        self._create_resources_tab()
        self._create_files_tab()
        self._create_dependencies_tab()
        self._create_advanced_tab()
        self._create_preview_tab()
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
    def _create_basic_tab(self):
        """Create the basic settings tab"""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)
        
        # Job name
        self.name_edit = QLineEdit(self.job.name)
        self.name_edit.setPlaceholderText("Enter job name")
        layout.addRow("Job Name:", self.name_edit)
        
        # Account
        self.account_edit = QComboBox()
        self.account_edit.setEditable(True)
        self.account_edit.setPlaceholderText("Account to charge")
        if self.slurm_api.connection_status == ConnectionState.CONNECTED:
            accounts = self.slurm_api.fetch_accounts()
            if accounts:
                self.account_edit.addItems(accounts)
        self.account_edit.setCurrentText(self.job.account or "")
        layout.addRow("Account:", self.account_edit)
        self.account_edit.setCurrentIndex(0)

        # Partition
        self.partition_edit = QComboBox()
        self.partition_edit.setEditable(True)
        self.partition_edit.setPlaceholderText("e.g., gpu, cpu, short")
        if self.slurm_api.connection_status == ConnectionState.CONNECTED:
            partitions = self.slurm_api.fetch_partitions()
            if partitions:
                self.partition_edit.addItems(partitions)
        self.partition_edit.setCurrentText(self.job.partition or "")
        layout.addRow("Partition:", self.partition_edit)
        self.partition_edit.setCurrentIndex(0)
        # Working directory
        dir_layout = QHBoxLayout()
        self.working_dir_edit = QLineEdit(self.job.working_directory or "")
        self.working_dir_edit.setPlaceholderText("Leave empty for current directory")
        dir_layout.addWidget(self.working_dir_edit)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_directory)
        dir_layout.addWidget(browse_btn)
        layout.addRow("Working Directory:", dir_layout)
        
        # Virtual environment
        venv_layout = QHBoxLayout()
        self.venv_edit = QLineEdit(self.job.venv or "")
        self.venv_edit.setPlaceholderText("Path to virtual environment (optional)")
        venv_layout.addWidget(self.venv_edit)
        
        venv_browse_btn = QPushButton("Browse...")
        venv_browse_btn.clicked.connect(self._browse_venv)
        venv_layout.addWidget(venv_browse_btn)
        layout.addRow("Virtual Environment:", venv_layout)
        
        # Script commands
        layout.addRow(QLabel("Script Commands:"))
        self.script_edit = QTextEdit()
        self.script_edit.setPlainText(self.job.script_commands)
        self.script_edit.setMinimumHeight(200)
        self.script_edit.setPlaceholderText("Enter your bash commands here...")
        font = QFont("Consolas" if os.name == 'nt' else "Monospace", 10)
        self.script_edit.setFont(font)
        layout.addRow(self.script_edit)
        
        self.tab_widget.addTab(tab, "Basic")
        
    def _create_resources_tab(self):
        """Create the resources tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # CPU resources
        cpu_group = QGroupBox("CPU Resources")
        cpu_layout = QFormLayout(cpu_group)
        
        self.cpus_spin = QSpinBox()
        self.cpus_spin.setMinimum(1)
        self.cpus_spin.setMaximum(128)
        self.cpus_spin.setValue(self.job.cpus_per_task or 1)
        cpu_layout.addRow("CPUs per Task:", self.cpus_spin)
        
        self.ntasks_spin = QSpinBox()
        self.ntasks_spin.setMinimum(1)
        self.ntasks_spin.setMaximum(1000)
        self.ntasks_spin.setValue(self.job.ntasks or 1)
        cpu_layout.addRow("Number of Tasks:", self.ntasks_spin)
        
        self.nodes_edit = QLineEdit(str(self.job.nodes or 1))
        self.nodes_edit.setPlaceholderText("e.g., 1 or 1-4")
        cpu_layout.addRow("Nodes:", self.nodes_edit)
        
        layout.addWidget(cpu_group)
        
        # Memory
        mem_group = QGroupBox("Memory")
        mem_layout = QFormLayout(mem_group)
        
        self.mem_edit = QLineEdit(self.job.mem or "1G")
        self.mem_edit.setPlaceholderText("e.g., 1G, 500M, 16G")
        mem_layout.addRow("Memory:", self.mem_edit)
        
        layout.addWidget(mem_group)
        
        # GPU resources
        gpu_group = QGroupBox("GPU Resources")
        gpu_layout = QFormLayout(gpu_group)
        
        self.gpus_edit = QLineEdit(self.job.gpus or "")
        self.gpus_edit.setPlaceholderText("e.g., 1, 2, a100:1")
        gpu_layout.addRow("GPUs:", self.gpus_edit)
        
        self.gpus_per_task_edit = QLineEdit(self.job.gpus_per_task or "")
        self.gpus_per_task_edit.setPlaceholderText("e.g., 1")
        gpu_layout.addRow("GPUs per Task:", self.gpus_per_task_edit)
        
        layout.addWidget(gpu_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Resources")
        
    def _create_files_tab(self):
        """Create the files tab"""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)
        
        # Output file
        self.output_edit = QLineEdit(self.job.output_file or "")
        self.output_edit.setPlaceholderText("e.g., job_%j.out (default: slurm-%j.out)")
        layout.addRow("Output File:", self.output_edit)
        
        # Error file
        self.error_edit = QLineEdit(self.job.error_file or "")
        self.error_edit.setPlaceholderText("e.g., job_%j.err (default: same as output)")
        layout.addRow("Error File:", self.error_edit)
        
        # Info label
        info_label = QLabel(
            "<b>Variable substitutions:</b><br>"
            "%j - Job ID<br>"
            "%a - Array task ID<br>"
            "%u - Username<br>"
            "%x - Job name"
        )
        info_label.setStyleSheet("color: #8be9fd; padding: 10px; background: rgba(68, 71, 90, 0.5); border-radius: 5px;")
        layout.addRow(info_label)
        
        self.tab_widget.addTab(tab, "Files")
        
    def _create_dependencies_tab(self):
        """Create the dependencies and arrays tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # Job Arrays
        array_group = QGroupBox("Job Arrays")
        array_layout = QFormLayout(array_group)
        
        self.array_edit = QLineEdit(self.job.array or "")
        self.array_edit.setPlaceholderText("e.g., 1-10, 1-100:10, 1,3,5,7")
        array_layout.addRow("Array Specification:", self.array_edit)
        
        array_info = QLabel(
            "<b>Array Examples:</b><br>"
            "• 1-10: Run 10 array tasks (1 through 10)<br>"
            "• 1-100:10: Run every 10th task from 1 to 100<br>"
            "• 1,3,5,7: Run specific task IDs<br>"
            "• 0-15%4: Run max 4 tasks at a time"
        )
        array_info.setStyleSheet("color: #8be9fd; padding: 10px; background: rgba(68, 71, 90, 0.5); border-radius: 5px;")
        array_layout.addRow(array_info)
        
        layout.addWidget(array_group)
        
        # Job Dependencies
        dep_group = QGroupBox("Job Dependencies")
        dep_layout = QFormLayout(dep_group)
        
        self.dependency_edit = QLineEdit(self.job.dependency or "")
        self.dependency_edit.setPlaceholderText("e.g., afterok:12345, afterany:12345:12346")
        dep_layout.addRow("Dependency:", self.dependency_edit)
        
        dep_info = QLabel(
            "<b>Dependency Types:</b><br>"
            "• afterok:jobid - Start after job completes successfully<br>"
            "• afternotok:jobid - Start after job fails<br>"
            "• afterany:jobid - Start after job completes (any exit)<br>"
            "• after:jobid - Start after job begins<br>"
            "• singleton - Only one job with this name at a time"
        )
        dep_info.setStyleSheet("color: #8be9fd; padding: 10px; background: rgba(68, 71, 90, 0.5); border-radius: 5px;")
        dep_layout.addRow(dep_info)
        
        layout.addWidget(dep_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Dependencies & Arrays")
        
    def _create_advanced_tab(self):
        """Create the advanced settings tab"""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)
        
        # QoS
        self.qos_edit = QLineEdit(self.job.qos or "")
        self.qos_edit.setPlaceholderText("Quality of Service")
        layout.addRow("QoS:", self.qos_edit)
        
        # Constraint
        self.constraint_edit = QLineEdit(self.job.constraint or "")
        self.constraint_edit.setPlaceholderText("e.g., gpu80gb, cpu_gen:cascadelake")
        layout.addRow("Constraint:", self.constraint_edit)
        
        # Nodelist
        self.nodelist_edit = QLineEdit(getattr(self.job, 'nodelist', None) or "")
        self.nodelist_edit.setPlaceholderText("e.g., node001, node[001-004], node00[1,3,5]")
        layout.addRow("Nodelist:", self.nodelist_edit)
        
        # Nice
        self.nice_spin = QSpinBox()
        self.nice_spin.setValue(self.job.nice or 0)
        self.nice_spin.setSpecialValueText("Default")
        layout.addRow("Nice:", self.nice_spin)
        
        # Oversubscribe
        self.oversubscribe_check = QCheckBox("Allow Oversubscribe")
        self.oversubscribe_check.setChecked(self.job.oversubscribe)
        layout.addRow(self.oversubscribe_check)
        
        # Optional sbatch options
        layout.addRow(QLabel("Additional SBATCH Options:"))
        self.optional_sbatch_edit = QTextEdit()
        self.optional_sbatch_edit.setPlainText(self.job.optional_sbatch or "")
        self.optional_sbatch_edit.setMaximumHeight(100)
        self.optional_sbatch_edit.setPlaceholderText("#SBATCH --option=value")
        font = QFont("Consolas" if os.name == 'nt' else "Monospace", 10)
        self.optional_sbatch_edit.setFont(font)
        layout.addRow(self.optional_sbatch_edit)
        
        # Constraint and Nodelist examples
        constraint_info = QLabel(
            "<b>Common Constraints:</b><br>"
            "• gpu80gb - Request 80GB GPU<br>"
            "• cpu_gen:cascadelake - Specific CPU generation<br>"
            "• avx512 - AVX-512 instruction support<br>"
            "• ib - InfiniBand network<br><br>"
            "<b>Nodelist Examples:</b><br>"
            "• node001 - Single specific node<br>"
            "• node[001-004] - Range of nodes<br>"
            "• node00[1,3,5] - Specific nodes"
        )
        constraint_info.setStyleSheet("color: #8be9fd; padding: 10px; background: rgba(68, 71, 90, 0.5); border-radius: 5px;")
        layout.addRow(constraint_info)
        
        self.tab_widget.addTab(tab, "Advanced")
        
    def _create_preview_tab(self):
        """Create the script preview tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)
        
        # Preview label
        preview_label = QLabel("Generated SBATCH Script:")
        preview_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(preview_label)
        
        # Preview text
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        font = QFont("Consolas" if os.name == 'nt' else "Monospace", 10)
        self.preview_text.setFont(font)
        self.preview_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #464647;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.preview_text)
        
        # Copy button
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setObjectName(BTN_BLUE)
        copy_btn.clicked.connect(self._copy_preview)
        layout.addWidget(copy_btn)
        
        self.tab_widget.addTab(tab, "Preview")
        
    def _connect_signals(self):
        """Connect all input signals to update the job and preview"""
        # Basic tab
        self.name_edit.textChanged.connect(self._update_job)
        self.account_edit.currentTextChanged.connect(self._update_job)
        self.partition_edit.currentTextChanged.connect(self._update_job)
        self.working_dir_edit.textChanged.connect(self._update_job)
        self.venv_edit.textChanged.connect(self._update_job)
        self.script_edit.textChanged.connect(self._update_job)
        
        # Resources tab
        self.cpus_spin.valueChanged.connect(self._update_job)
        self.ntasks_spin.valueChanged.connect(self._update_job)
        self.nodes_edit.textChanged.connect(self._update_job)
        self.mem_edit.textChanged.connect(self._update_job)
        self.gpus_edit.textChanged.connect(self._update_job)
        self.gpus_per_task_edit.textChanged.connect(self._update_job)
        
        # Files tab
        self.output_edit.textChanged.connect(self._update_job)
        self.error_edit.textChanged.connect(self._update_job)
        
        # Dependencies & Arrays tab
        self.array_edit.textChanged.connect(self._update_job)
        self.dependency_edit.textChanged.connect(self._update_job)
        
        # Advanced tab
        self.qos_edit.textChanged.connect(self._update_job)
        self.constraint_edit.textChanged.connect(self._update_job)
        self.nodelist_edit.textChanged.connect(self._update_job)
        self.nice_spin.valueChanged.connect(self._update_job)
        self.oversubscribe_check.stateChanged.connect(self._update_job)
        self.optional_sbatch_edit.textChanged.connect(self._update_job)
        
        # Update preview when switching to preview tab
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        
    def _update_job(self):
        """Update the job object from UI inputs"""
        # Basic
        self.job.name = self.name_edit.text() or "my_slurm_job"
        self.job.working_directory = self.working_dir_edit.text() or None
        self.job.venv = self.venv_edit.text() or None
        self.job.script_commands = self.script_edit.toPlainText()
        
        # Resources
        self.job.cpus_per_task = self.cpus_spin.value()
        self.job.ntasks = self.ntasks_spin.value()
        self.job.nodes = self.nodes_edit.text() or "1"
        self.job.mem = self.mem_edit.text() or "1G"
        self.job.gpus = self.gpus_edit.text() or None
        self.job.gpus_per_task = self.gpus_per_task_edit.text() or None
        
        # Files
        self.job.output_file = self.output_edit.text() or None
        self.job.error_file = self.error_edit.text() or None
        
        # Advanced
        self.job.account = self.account_edit.currentText() or None
        self.job.partition = self.partition_edit.currentText() or None
        self.job.qos = self.qos_edit.text() or None
        self.job.array = self.array_edit.text() or None
        self.job.constraint = self.constraint_edit.text() or None
        self.job.dependency = self.dependency_edit.text() or None
        self.job.nice = self.nice_spin.value() if self.nice_spin.value() != 0 else None
        self.job.oversubscribe = self.oversubscribe_check.isChecked()
        self.job.optional_sbatch = self.optional_sbatch_edit.toPlainText() or None
        
        # Update preview if on preview tab
        if self.tab_widget.currentIndex() == 5:  # Preview tab
            self._update_preview()
            
    def _on_tab_changed(self, index):
        """Handle tab change"""
        if index == 5:  # Preview tab
            self._update_preview()
            
    def _update_preview(self):
        """Update the script preview"""
        script = self.job.create_sbatch_script()
        self.preview_text.setPlainText(script)
        
    def _browse_directory(self):
        """Browse for working directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Working Directory", 
            self.working_dir_edit.text() or ""
        )
        if directory:
            self.working_dir_edit.setText(directory)
            
    def _browse_venv(self):
        """Browse for virtual environment"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Virtual Environment", 
            self.venv_edit.text() or ""
        )
        if directory:
            self.venv_edit.setText(directory)
            
    def _copy_preview(self):
        """Copy the preview script to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.preview_text.toPlainText())
        
        # Show feedback
        original_text = self.sender().text()
        self.sender().setText("Copied!")
        QTimer.singleShot(1500, lambda: self.sender().setText(original_text))
        
    def get_job(self) -> Job:
        """Get the configured job object"""
        return self.job
        
    def accept(self):
        """Validate and accept the dialog"""
        # Basic validation
        if not self.job.name.strip():
            from widgets.toast_widget import show_warning_toast
            show_warning_toast(self, "Validation Error", "Job name is required")
            self.tab_widget.setCurrentIndex(0)
            self.name_edit.setFocus()
            return
            
        if not self.job.script_commands.strip():
            from widgets.toast_widget import show_warning_toast
            show_warning_toast(self, "Validation Error", "Script commands are required")
            self.tab_widget.setCurrentIndex(0)
            self.script_edit.setFocus()
            return
            
        # Emit signal and close
        self.jobCreated.emit(self.job)
        super().accept()