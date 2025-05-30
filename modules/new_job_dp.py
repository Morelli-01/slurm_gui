from pathlib import Path
from modules.defaults import *
from modules.remote_directory_panel import RemoteDirectoryDialog
from utils import create_separator, script_dir
from style import AppStyles
from modules.toast_notify import show_error_toast, show_info_toast, show_success_toast, show_warning_toast

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QGroupBox, QLabel, QLineEdit, QSpinBox,
    QComboBox, QCheckBox, QPushButton, QTextEdit, QTimeEdit, QWidget, QFrame
)
from PyQt6.QtCore import Qt, QTime, QDateTime, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from utils import settings_path

COLOR_BLUE = "#06b0d6"

class CheckableComboBox(QComboBox):
    selection_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = self.model()
        self.view().pressed.connect(self.handle_item_pressed)
        self.setEditable(False)
        self._checked_items = set()

    def add_item(self, text):
        self.addItem(text)
        idx = self.model.index(self.count() - 1, 0)
        self.model.setData(idx, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)

    def handle_item_pressed(self, index):
        state = self.model.data(index, Qt.ItemDataRole.CheckStateRole)
        new_state = Qt.CheckState.Unchecked if state == Qt.CheckState.Checked else Qt.CheckState.Checked
        self.model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
        self.selection_changed.emit()

    def get_checked_items(self):
        checked = []
        for i in range(self.count()):
            idx = self.model.index(i, 0)
            if self.model.data(idx, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked:
                checked.append(self.itemText(i))
        return checked

    def _update_selected_text(self):
        checked = self.get_checked_items()
        self.setEditText(", ".join(checked) if checked else "")

class NewJobDialog(QDialog):
    def __init__(self, selected_project, slurm_connection=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"New Job for Project: {selected_project}")
        self.setMinimumSize(800, 600)
        self.selected_project = selected_project
        self.slurm_connection = slurm_connection

        # Prefetchable data
        self.partitions = ["Loading..."] if slurm_connection else ["main", "gpu", "long", "debug"]
        self.constraints = ["Loading..."] if slurm_connection else ["intel", "amd", "highmem"]
        self.qos_list = ["Loading..."] if slurm_connection else ["normal", "debug", "high"]
        self.accounts = ["Loading..."] if slurm_connection else ["project1", "project2", "mylab"]
        self.gres = ["Loading..."] if slurm_connection else ["gpu:1", "gpu:2", "gpu:rtx5000:1"]

        self.setStyleSheet(AppStyles.get_complete_stylesheet(THEME_DARK))
        self._prefetch_data()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel(f"New Job for Project: {selected_project}")
        header_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_label.setStyleSheet(f"color: {COLOR_BLUE};")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        self.main_layout.addLayout(header_layout)
        self.main_layout.addWidget(create_separator())

        # Tabs
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # Essentials Tab
        self.essential_tab = QWidget()
        self.tabs.addTab(self.essential_tab, "Essentials")
        self._setup_essential_tab()

        # Advanced Tab
        self.advanced_tab = QWidget()
        self.tabs.addTab(self.advanced_tab, "Advanced")
        self._setup_advanced_tab()

        # Command Tab
        self.command_tab = QWidget()
        self.tabs.addTab(self.command_tab, "Command Script")
        self._setup_command_tab()

        # Job Array Tab
        self.job_array_tab = QWidget()
        self.tabs.addTab(self.job_array_tab, "Job Array")
        self._setup_job_array_tab()

        # Dependencies Tab
        self.job_dependencies_tab = QWidget()
        self.tabs.addTab(self.job_dependencies_tab, "Dependencies")
        self._setup_job_dependencies_tab()

        # Bottom Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName(BTN_RED)
        self.cancel_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "cancel.svg")))
        self.cancel_button.clicked.connect(self.reject)
        self.create_button = QPushButton("Create Job")
        self.create_button.setObjectName(BTN_GREEN)
        self.create_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "ok.svg")))
        self.create_button.clicked.connect(self.accept)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.create_button)
        self.main_layout.addLayout(button_layout)

    def _prefetch_data(self):
        if not self.slurm_connection or not self.slurm_connection.check_connection():
            return
        try:
            self.partitions = self.slurm_connection.partitions
            self.constraints = self.slurm_connection.constraints
            self.qos_list = self.slurm_connection.qos_list
            self.accounts = self.slurm_connection.accounts
            self.gres = self.slurm_connection.gres
            self.running_jobs = self.slurm_connection.get_running_jobs()
        except Exception as e:
            print(f"Error prefetching SLURM data: {e}")
            self.running_jobs = []

    def _setup_essential_tab(self):
        # Main layout with scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        
        # Job Information Group
        job_info_group = QGroupBox("Job Information")
        job_info_layout = QFormLayout(job_info_group)
        job_info_layout.setSpacing(10)
        job_info_layout.setContentsMargins(10, 15, 10, 15)
        
        self.job_name_edit = QLineEdit()
        self.job_name_edit.setPlaceholderText("Enter job name")
        job_info_layout.addRow(self._create_label("Job Name*:"), self.job_name_edit)
        
        self.job_comment_edit = QLineEdit()
        self.job_comment_edit.setPlaceholderText("Optional description for the job")
        job_info_layout.addRow(self._create_label("Job Comment:"), self.job_comment_edit)
        
        # Resource Allocation Group
        resource_group = QGroupBox("Resource Allocation")
        resource_layout = QFormLayout(resource_group)
        resource_layout.setSpacing(10)
        resource_layout.setContentsMargins(10, 15, 10, 15)
        
        # Partition and Account
        partition_account_widget = QWidget()
        partition_account_layout = QHBoxLayout(partition_account_widget)
        partition_account_layout.setContentsMargins(0, 0, 0, 0)
        partition_account_layout.setSpacing(10)
        
        self.partition_combo = QComboBox()
        self.partition_combo.addItems(self.partitions)
        partition_account_layout.addWidget(QLabel("Partition*:"))
        partition_account_layout.addWidget(self.partition_combo)
        partition_account_layout.addSpacing(20)
        
        self.account_combo = QComboBox()
        self.account_combo.addItems(self.accounts)
        partition_account_layout.addWidget(QLabel("Account*:"))
        partition_account_layout.addWidget(self.account_combo)
        partition_account_layout.addStretch()
        
        resource_layout.addRow(partition_account_widget)
        
        # Time and Nodes
        time_nodes_widget = QWidget()
        time_nodes_layout = QHBoxLayout(time_nodes_widget)
        time_nodes_layout.setContentsMargins(0, 0, 0, 0)
        time_nodes_layout.setSpacing(10)
        
        self.time_limit_edit = QTimeEdit()
        self.time_limit_edit.setDisplayFormat("HH:mm:ss")
        self.time_limit_edit.setTime(QTime(1, 0, 0))
        time_nodes_layout.addWidget(QLabel("Time Limit*:"))
        time_nodes_layout.addWidget(self.time_limit_edit)
        time_nodes_layout.addSpacing(20)
        
        self.nodes_spin = QSpinBox()
        self.nodes_spin.setMinimum(1)
        self.nodes_spin.setMaximum(1000)
        self.nodes_spin.setValue(1)
        time_nodes_layout.addWidget(QLabel("Nodes:"))
        time_nodes_layout.addWidget(self.nodes_spin)
        time_nodes_layout.addStretch()
        
        resource_layout.addRow(time_nodes_widget)
        
        # CPU and Memory
        cpu_mem_widget = QWidget()
        cpu_mem_layout = QHBoxLayout(cpu_mem_widget)
        cpu_mem_layout.setContentsMargins(0, 0, 0, 0)
        cpu_mem_layout.setSpacing(10)
        
        self.cpu_per_task_spin = QSpinBox()
        self.cpu_per_task_spin.setMinimum(1)
        self.cpu_per_task_spin.setMaximum(128)
        self.cpu_per_task_spin.setValue(1)
        cpu_mem_layout.addWidget(QLabel("CPUs per Task:"))
        cpu_mem_layout.addWidget(self.cpu_per_task_spin)
        cpu_mem_layout.addSpacing(20)
        
        memory_widget = QWidget()
        memory_layout = QHBoxLayout(memory_widget)
        memory_layout.setContentsMargins(0, 0, 0, 0)
        memory_layout.setSpacing(5)
        self.memory_spin = QSpinBox()
        self.memory_spin.setMinimum(1)
        self.memory_spin.setMaximum(9999)
        self.memory_spin.setValue(8)
        self.memory_unit_combo = QComboBox()
        self.memory_unit_combo.addItems(["MB", "GB"])
        self.memory_unit_combo.setCurrentText("GB")
        memory_layout.addWidget(self.memory_spin)
        memory_layout.addWidget(self.memory_unit_combo)
        cpu_mem_layout.addWidget(QLabel("Memory per CPU:"))
        cpu_mem_layout.addWidget(memory_widget)
        cpu_mem_layout.addStretch()
        
        resource_layout.addRow(cpu_mem_widget)
        
        # Tasks and CPUs per Node
        tasks_cpus_node_widget = QWidget()
        tasks_cpus_node_layout = QHBoxLayout(tasks_cpus_node_widget)
        tasks_cpus_node_layout.setContentsMargins(0, 0, 0, 0)
        tasks_cpus_node_layout.setSpacing(10)
        
        self.ntasks_spin = QSpinBox()
        self.ntasks_spin.setMinimum(1)
        self.ntasks_spin.setMaximum(1000)
        self.ntasks_spin.setValue(1)
        tasks_cpus_node_layout.addWidget(QLabel("Number of Tasks:"))
        tasks_cpus_node_layout.addWidget(self.ntasks_spin)
        tasks_cpus_node_layout.addSpacing(20)
        
        self.cpus_per_node_spin = QSpinBox()
        self.cpus_per_node_spin.setMinimum(1)
        self.cpus_per_node_spin.setMaximum(128)
        self.cpus_per_node_spin.setValue(1)
        tasks_cpus_node_layout.addWidget(QLabel("CPUs per Node:"))
        tasks_cpus_node_layout.addWidget(self.cpus_per_node_spin)
        tasks_cpus_node_layout.addStretch()
        
        resource_layout.addRow(tasks_cpus_node_widget)
        
        # Add groups to main layout
        layout.addWidget(job_info_group)
        layout.addWidget(resource_group)
        
        # Add stretch to push content to top
        layout.addStretch()
        
        # Set the scroll content
        scroll.setWidget(scroll_content)
        
        # Create a main layout for the tab
        tab_layout = QVBoxLayout(self.essential_tab)
        tab_layout.addWidget(scroll)
        
        # Connect signals for updating preview
        for widget in [self.job_name_edit, self.job_comment_edit, self.partition_combo, 
                      self.account_combo, self.time_limit_edit, self.nodes_spin, 
                      self.cpu_per_task_spin, self.memory_spin, self.memory_unit_combo,
                      self.ntasks_spin, self.cpus_per_node_spin]:
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._update_preview)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._update_preview)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._update_preview)
            elif isinstance(widget, QTimeEdit):
                widget.timeChanged.connect(self._update_preview)

    def _setup_advanced_tab(self):
        # Main layout with scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        
        # Resource Constraints Group
        constraints_group = QGroupBox("Resource Constraints")
        constraints_layout = QFormLayout(constraints_group)
        constraints_layout.setSpacing(10)
        constraints_layout.setContentsMargins(10, 15, 10, 15)
        
        # Node Constraints
        self.constraint_combo = CheckableComboBox()
        for constraint_option in self.constraints:
            self.constraint_combo.add_item(constraint_option)
        self.constraint_combo.selection_changed.connect(self._update_preview)
        constraints_layout.addRow(self._create_label("Node Constraints:"), self.constraint_combo)
        
        # QoS
        qos_widget = QWidget()
        qos_layout = QHBoxLayout(qos_widget)
        qos_layout.setContentsMargins(0, 0, 0, 0)
        qos_layout.setSpacing(10)
        
        self.qos_combo = QComboBox()
        self.qos_combo.addItems(["None"] + self.qos_list)
        self.qos_combo.currentIndexChanged.connect(self._update_preview)
        qos_layout.addWidget(QLabel("QoS:"))
        qos_layout.addWidget(self.qos_combo)
        qos_layout.addStretch()
        
        constraints_layout.addRow(qos_widget)
        
        # GRES (GPU) Group
        self.gres_group = QGroupBox("GPU Resources (GRES)")
        gres_layout = QVBoxLayout(self.gres_group)
        gres_layout.setSpacing(10)
        gres_layout.setContentsMargins(10, 15, 10, 15)
        
        self.gpu_check = QCheckBox("Request GPU Resources")
        self.gpu_check.stateChanged.connect(self._toggle_gpu_selection)
        gres_layout.addWidget(self.gpu_check)
        
        gpu_selection_widget = QWidget()
        gpu_selection_layout = QHBoxLayout(gpu_selection_widget)
        gpu_selection_layout.setContentsMargins(0, 0, 0, 0)
        gpu_selection_layout.setSpacing(10)
        
        self.gpu_type_combo = QComboBox()
        gpu_types = ["any"]
        for g in self.gres:
            if isinstance(g, str) and "gpu" in g.lower():
                try:
                    parts = g.split(':')
                    if len(parts) == 3 and parts[0].lower() == 'gpu':
                        gpu_type = parts[1]
                        if gpu_type not in gpu_types:
                            gpu_types.append(gpu_type)
                except (IndexError, ValueError):
                    continue
        self.gpu_type_combo.addItems(gpu_types)
        self.gpu_type_combo.setEnabled(False)
        self.gpu_type_combo.currentIndexChanged.connect(self._update_preview)
        
        self.gpu_count_spin = QSpinBox()
        self.gpu_count_spin.setRange(1, 16)
        self.gpu_count_spin.setValue(1)
        self.gpu_count_spin.setEnabled(False)
        self.gpu_count_spin.valueChanged.connect(self._update_preview)
        
        gpu_selection_layout.addWidget(QLabel("GPU Type:"))
        gpu_selection_layout.addWidget(self.gpu_type_combo, 1)
        gpu_selection_layout.addWidget(QLabel("Count:"))
        gpu_selection_layout.addWidget(self.gpu_count_spin)
        
        gres_layout.addWidget(gpu_selection_widget)
        
        # Add virtual environment selection
        venv_widget = QWidget()
        venv_layout = QHBoxLayout(venv_widget)
        venv_layout.setContentsMargins(0, 0, 0, 0)
        venv_layout.setSpacing(10)
        
        self.venv_combo = QComboBox()
        self.venv_combo.addItem("None")
        # Add common virtual environment paths
        venv_paths = [
            "~/miniconda3/envs",
            "~/anaconda3/envs",
            "/opt/miniconda3/envs",
            "/opt/anaconda3/envs",
            "~/.virtualenvs"
        ]
        
        # Add discovered environments
        for path in venv_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path) and os.path.isdir(expanded_path):
                for env in os.listdir(expanded_path):
                    self.venv_combo.addItem(os.path.join(expanded_path, env))
        
        self.venv_combo.setEditable(True)
        self.venv_combo.currentIndexChanged.connect(self._update_preview)
        venv_layout.addWidget(QLabel("Python Virtual Environment:"))
        venv_layout.addWidget(self.venv_combo, 1)
        
        venv_browse_btn = QPushButton("Browse...")
        venv_browse_btn.clicked.connect(self._browse_venv)
        venv_layout.addWidget(venv_browse_btn)
        
        gres_layout.addWidget(venv_widget)
        
        # File Management Group
        file_group = QGroupBox("File Management")
        file_layout = QFormLayout(file_group)
        file_layout.setSpacing(10)
        file_layout.setContentsMargins(10, 15, 10, 15)
        
        # Output and Error Files
        self.output_file_edit = QLineEdit()
        self.output_file_edit.setPlaceholderText("Path for job output")
        self.output_file_edit.setText(".logs/out_%A_%a.log")
        self.output_file_edit.textChanged.connect(self._update_preview)
        file_layout.addRow(self._create_label("Output File:"), self.output_file_edit)
        
        self.error_file_edit = QLineEdit()
        self.error_file_edit.setPlaceholderText("Path for job errors")
        self.error_file_edit.setText(".logs/err_%A_%a.log")
        self.error_file_edit.textChanged.connect(self._update_preview)
        file_layout.addRow(self._create_label("Error File:"), self.error_file_edit)
        
        # Working Directory
        working_dir_widget = QWidget()
        working_dir_layout = QHBoxLayout(working_dir_widget)
        working_dir_layout.setContentsMargins(0, 0, 0, 0)
        working_dir_layout.setSpacing(10)
        
        self.working_dir_edit = QLineEdit()
        self.working_dir_edit.setPlaceholderText("Working directory for job")
        self.working_dir_edit.setText(os.getcwd())
        self.working_dir_edit.textChanged.connect(self._update_preview)
        
        self.browse_dir_button = QPushButton("Browse...")
        self.browse_dir_button.setObjectName(BTN_BLUE)
        self.browse_dir_button.clicked.connect(self._browse_working_dir)
        font_metrics = QFontMetrics(self.browse_dir_button.font())
        char_width = font_metrics.horizontalAdvance('M')
        total_width = len("Browse...") * char_width + 20
        self.browse_dir_button.setFixedWidth(total_width)
        
        working_dir_layout.addWidget(self.working_dir_edit)
        working_dir_layout.addWidget(self.browse_dir_button)
        
        file_layout.addRow(self._create_label("Working Directory:"), working_dir_widget)
        
        # Add groups to main layout
        layout.addWidget(constraints_group)
        layout.addWidget(self.gres_group)
        layout.addWidget(file_group)
        layout.addStretch()
        
        # Set the scroll content
        scroll.setWidget(scroll_content)
        
        # Create a main layout for the tab
        tab_layout = QVBoxLayout(self.advanced_tab)
        tab_layout.addWidget(scroll)
        
        # Connect signals for updating preview
        for widget in [self.constraint_combo, self.qos_combo, self.gpu_check, 
                     self.gpu_type_combo, self.gpu_count_spin, self.output_file_edit,
                     self.error_file_edit, self.working_dir_edit]:
            if hasattr(widget, 'selection_changed'):
                widget.selection_changed.connect(self._update_preview)
            elif hasattr(widget, 'currentIndexChanged'):
                widget.currentIndexChanged.connect(self._update_preview)
            elif hasattr(widget, 'valueChanged'):
                widget.valueChanged.connect(self._update_preview)
            elif hasattr(widget, 'textChanged'):
                widget.textChanged.connect(self._update_preview)
            elif hasattr(widget, 'stateChanged'):
                widget.stateChanged.connect(self._update_preview)

    def _setup_command_tab(self):
        layout = QVBoxLayout(self.command_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        command_label = self._create_label("Enter the command or script to execute:")
        command_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(command_label)
        self.command_text = QTextEdit()
        self.command_text.setPlaceholderText("Enter your job command or script here\nExample: python3 /path/to/script.py --arg1 value1")
        self.command_text.setMinimumHeight(200)
        self.command_text.textChanged.connect(self._update_preview)
        layout.addWidget(self.command_text)
        layout.addWidget(create_separator())
        preview_label = self._create_label("Preview of SLURM submission script:")
        preview_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(preview_label)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("Job submission script preview will appear here")
        self.preview_text.setMinimumHeight(150)
        self.preview_text.setStyleSheet(f"""
            background-color: #282a36;
            color: #f8f8f2;
            font-family: monospace;
            padding: 10px;
            border: 1px solid {COLOR_DARK_BORDER};
            selection-background-color: {COLOR_BLUE};
        """)
        layout.addWidget(self.preview_text)
        button_layout = QHBoxLayout()
        self.update_preview_button = QPushButton("Update Preview")
        self.update_preview_button.setObjectName(BTN_BLUE)
        self.update_preview_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "refresh.svg")))
        self.update_preview_button.clicked.connect(self._update_preview)
        button_layout.addStretch()
        button_layout.addWidget(self.update_preview_button)
        layout.addLayout(button_layout)

    def _setup_job_array_tab(self):
        layout = QVBoxLayout(self.job_array_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        self.array_group = QGroupBox("Job Array")
        self.array_group.setCheckable(True)
        self.array_group.setChecked(False)
        self.array_group.toggled.connect(self._update_preview)
        array_layout = QVBoxLayout(self.array_group)
        array_layout.setSpacing(15)
        array_explanation = QLabel("Job arrays let you submit and manage multiple similar jobs with a single job submission.")
        array_explanation.setWordWrap(True)
        array_layout.addWidget(array_explanation)
        array_format_widget = QWidget()
        array_format_layout = QFormLayout(array_format_widget)
        array_format_layout.setContentsMargins(0, 0, 0, 0)
        self.array_format_combo = QComboBox()
        self.array_format_combo.addItems(["Range", "List", "Range with step"])
        self.array_format_combo.currentIndexChanged.connect(self._update_array_inputs)
        self.array_format_combo.currentIndexChanged.connect(self._update_preview)
        array_format_layout.addRow(self._create_label("Array Format:"), self.array_format_combo)
        array_layout.addWidget(array_format_widget)
        # Range inputs
        self.range_widget = QWidget()
        range_layout = QHBoxLayout(self.range_widget)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(10)
        self.array_start_spin = QSpinBox()
        self.array_start_spin.setMinimum(0)
        self.array_start_spin.setMaximum(9999)
        self.array_start_spin.setValue(0)
        self.array_start_spin.valueChanged.connect(self._update_preview)
        self.array_end_spin = QSpinBox()
        self.array_end_spin.setMinimum(1)
        self.array_end_spin.setMaximum(9999)
        self.array_end_spin.setValue(10)
        self.array_end_spin.valueChanged.connect(self._update_preview)
        range_layout.addWidget(self._create_label("Start:"))
        range_layout.addWidget(self.array_start_spin)
        range_layout.addWidget(self._create_label("End:"))
        range_layout.addWidget(self.array_end_spin)
        range_layout.addStretch()
        array_layout.addWidget(self.range_widget)
        # Step input
        self.step_widget = QWidget()
        step_layout = QHBoxLayout(self.step_widget)
        step_layout.setContentsMargins(0, 0, 0, 0)
        step_layout.setSpacing(10)
        self.array_step_spin = QSpinBox()
        self.array_step_spin.setMinimum(1)
        self.array_step_spin.setMaximum(100)
        self.array_step_spin.setValue(1)
        self.array_step_spin.valueChanged.connect(self._update_preview)
        step_layout.addWidget(self._create_label("Step:"))
        step_layout.addWidget(self.array_step_spin)
        step_layout.addStretch()
        array_layout.addWidget(self.step_widget)
        # List input
        self.list_widget = QWidget()
        list_layout = QHBoxLayout(self.list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(10)
        self.array_list_edit = QLineEdit()
        self.array_list_edit.setPlaceholderText("e.g. 1,2,3,5,8")
        self.array_list_edit.textChanged.connect(self._update_preview)
        list_layout.addWidget(self._create_label("List:"))
        list_layout.addWidget(self.array_list_edit)
        list_layout.addStretch()
        array_layout.addWidget(self.list_widget)
        # Max concurrent jobs
        max_jobs_widget = QWidget()
        max_jobs_layout = QHBoxLayout(max_jobs_widget)
        max_jobs_layout.setContentsMargins(0, 0, 0, 0)
        max_jobs_layout.setSpacing(10)
        self.max_jobs_spin = QSpinBox()
        self.max_jobs_spin.setMinimum(1)
        self.max_jobs_spin.setMaximum(1000)
        self.max_jobs_spin.setValue(10)
        self.max_jobs_check = QCheckBox("Limit concurrent jobs")
        self.max_jobs_check.stateChanged.connect(self._toggle_max_jobs)
        self.max_jobs_check.stateChanged.connect(self._update_preview)
        self.max_jobs_spin.setEnabled(False)
        self.max_jobs_spin.valueChanged.connect(self._update_preview)
        max_jobs_layout.addWidget(self.max_jobs_check)
        max_jobs_layout.addWidget(self.max_jobs_spin)
        max_jobs_layout.addStretch()
        array_layout.addWidget(max_jobs_widget)
        # Job Environment Variables
        array_env_label = self._create_label("Environment variables for array jobs:")
        array_env_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        array_layout.addWidget(array_env_label)
        array_env_info = QLabel("The following environment variables will be available in your job scripts:")
        array_env_info.setWordWrap(True)
        array_layout.addWidget(array_env_info)
        array_env_vars = QLabel(
            "• SLURM_ARRAY_JOB_ID - Job ID for the entire job array\n"
            "• SLURM_ARRAY_TASK_ID - Array index value for this task\n"
            "• SLURM_ARRAY_TASK_COUNT - Total number of tasks in the array\n"
            "• SLURM_ARRAY_TASK_MAX - Maximum index value\n"
            "• SLURM_ARRAY_TASK_MIN - Minimum index value"
        )
        array_env_vars.setStyleSheet("color: #aaaaaa; background-color: #282a36; padding: 10px; border-radius: 4px;")
        array_layout.addWidget(array_env_vars)
        layout.addWidget(self.array_group)
        layout.addStretch()
        self._update_array_inputs(0)

    def _setup_job_dependencies_tab(self):
        layout = QVBoxLayout(self.job_dependencies_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        self.dependency_group = QGroupBox("Job Dependencies")
        self.dependency_group.setContentsMargins(0, 0, 0, 0)
        dependency_layout = QVBoxLayout(self.dependency_group)
        dependency_layout.setSpacing(15)
        dep_explanation = QLabel("Dependencies let you specify conditions when this job should start based on the state of other jobs.")
        dep_explanation.setWordWrap(True)
        dep_explanation.setStyleSheet("color: #aaaaaa; font-style: italic;")
        dependency_layout.addWidget(dep_explanation)
        self.dep_type_combo = QComboBox()
        self.dep_type_combo.addItems([
            "after - After any specified job starts",
            "afterany - After any specified job ends (regardless of exit code)",
            "afterok - After specified jobs complete successfully",
            "afternotok - After specified jobs fail",
            "singleton - Wait until no other job with this name is running"
        ])
        self.dep_type_combo.currentIndexChanged.connect(self._update_preview)
        dependency_layout.addWidget(self.dep_type_combo)
        self.running_jobs_group = QGroupBox("Select from Running Jobs")
        running_jobs_layout = QVBoxLayout(self.running_jobs_group)
        self.running_jobs_combo = QComboBox()
        if hasattr(self, 'running_jobs') and self.running_jobs:
            job_items = [f"{job['Job ID']} - {job['Job Name']} ({job['Status']})" for job in self.running_jobs]
            self.running_jobs_combo.addItems(job_items)
        else:
            self.running_jobs_combo.addItem("No running jobs found")
        running_jobs_layout.addWidget(self.running_jobs_combo)
        self.add_job_button = QPushButton("Add to Dependencies")
        self.add_job_button.setObjectName(BTN_GREEN)
        self.add_job_button.setFixedWidth(300)
        self.add_job_button.clicked.connect(self._add_selected_job_to_dependencies)
        refresh_jobs_layout = QHBoxLayout()
        self.refresh_jobs_button = QPushButton("Refresh Job List")
        self.refresh_jobs_button.setObjectName(BTN_BLUE)
        self.refresh_jobs_button.clicked.connect(self._refresh_running_jobs)
        refresh_jobs_layout.addWidget(self.refresh_jobs_button)
        refresh_jobs_layout.addStretch()
        running_jobs_layout.addWidget(self.add_job_button, alignment=Qt.AlignmentFlag.AlignCenter)
        running_jobs_layout.addLayout(refresh_jobs_layout)
        dependency_layout.addWidget(self.running_jobs_group)
        self.delete_dependency_group = QGroupBox("Manage Added Dependencies")
        delete_dep_layout = QVBoxLayout(self.delete_dependency_group)
        delete_dep_layout.setSpacing(10)
        delete_dep_layout.setContentsMargins(10, 20, 10, 10)
        self.dep_id_widget = QWidget()
        dep_id_layout = QVBoxLayout(self.dep_id_widget)
        dep_id_layout.setContentsMargins(0, 0, 0, 0)
        dep_id_layout.setSpacing(10)
        self.dep_id_display_combo = QComboBox()
        self.dep_id_display_combo.setPlaceholderText("Added job IDs will appear here")
        self.dep_id_display_combo.currentIndexChanged.connect(self._update_preview)
        self.singleton_label = QLabel("No job IDs needed for singleton dependency type")
        self.singleton_label.setVisible(False)
        dep_id_layout.addWidget(self._create_label("Dependent Job IDs:"))
        dep_id_layout.addWidget(self.dep_id_display_combo)
        dep_id_layout.addWidget(self.singleton_label)
        delete_dep_layout.addWidget(self.dep_id_widget)
        self.remove_dependency_button = QPushButton("Remove Selected Dependency")
        self.remove_dependency_button.setObjectName(BTN_RED)
        self.remove_dependency_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "delete.svg")))
        self.remove_dependency_button.clicked.connect(self._remove_selected_dependency)
        delete_dep_layout.addWidget(self.remove_dependency_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.dependency_group)
        layout.addWidget(self.delete_dependency_group)
        layout.addStretch()
        self._update_dependency_inputs(self.dep_type_combo.currentIndex())

    # --- Helper Methods ---
    def _create_label(self, text):
        label = QLabel(text)
        label.setFont(QFont("Arial", 10))
        return label

    def _toggle_gpu_selection(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.gpu_type_combo.setEnabled(enabled)
        self.gpu_count_spin.setEnabled(enabled)

    def _update_array_inputs(self, index):
        self.range_widget.setVisible(index == 0 or index == 2)
        self.step_widget.setVisible(index == 2)
        self.list_widget.setVisible(index == 1)

    def _toggle_max_jobs(self, state):
        self.max_jobs_spin.setEnabled(bool(state))

    def _update_dependency_inputs(self, index):
        dep_type = self.dep_type_combo.currentText().split(" - ")[0].strip()
        is_singleton = dep_type == "singleton"
        self.running_jobs_group.setVisible(not is_singleton)
        self.dep_id_widget.setVisible(not is_singleton)
        self.singleton_label.setVisible(is_singleton)

    def _add_selected_job_to_dependencies(self):
        job_text = self.running_jobs_combo.currentText()
        job_id = job_text.split(" - ")[0].strip() if job_text else ""
        if job_id and self.dep_id_display_combo.findText(job_id) == -1:
            self.dep_id_display_combo.addItem(job_id)
            self._update_preview()

    def _remove_selected_dependency(self):
        idx = self.dep_id_display_combo.currentIndex()
        if idx >= 0:
            self.dep_id_display_combo.removeItem(idx)
            self._update_preview()

    def _refresh_running_jobs(self):
        if not self.slurm_connection or not self.slurm_connection.check_connection():
            return
        try:
            self.running_jobs = self.slurm_connection.get_running_jobs()
            self.running_jobs_combo.clear()
            if self.running_jobs:
                job_items = [f"{job['Job ID']} - {job['Job Name']} ({job['Status']})" for job in self.running_jobs]
                self.running_jobs_combo.addItems(job_items)
            else:
                self.running_jobs_combo.addItem("No running jobs found")
        except Exception as e:
            print(f"Error refreshing job list: {e}")
            self.running_jobs_combo.clear()
            self.running_jobs_combo.addItem("Error fetching jobs")

    def _browse_working_dir(self):
        if not self.slurm_connection or not self.slurm_connection.check_connection():
            show_warning_toast(self, "SLURM Connection Error", "Not connected to SLURM. Cannot browse remote directories.")
            return
        initial_path = self.working_dir_edit.text()
        if not initial_path or not self.slurm_connection.remote_path_exists(initial_path):
            if self.slurm_connection.remote_home and self.slurm_connection.remote_path_exists(self.slurm_connection.remote_home):
                initial_path = self.slurm_connection.remote_home
            else:
                initial_path = "/"
        dialog = RemoteDirectoryDialog(self.slurm_connection, initial_path=initial_path, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_directory = dialog.get_selected_directory()
            if selected_directory:
                self.working_dir_edit.setText(selected_directory)
                self._update_preview()
                
    def _browse_venv(self):
        """Open a directory selection dialog for virtual environment."""
        if not self.slurm_connection or not self.slurm_connection.check_connection():
            show_warning_toast(self, "SLURM Connection Error", "Not connected to SLURM. Cannot browse remote directories.")
            return
            
        current_path = self.venv_combo.currentText()
        if current_path == "None" or not self.slurm_connection.remote_path_exists(current_path):
            if self.slurm_connection.remote_home and self.slurm_connection.remote_path_exists(self.slurm_connection.remote_home):
                current_path = self.slurm_connection.remote_home
            else:
                current_path = "/"
                
        dialog = RemoteDirectoryDialog(self.slurm_connection, initial_path=current_path, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_directory = dialog.get_selected_directory()
            if selected_directory:
                # Check if the selected directory has a bin/activate file (common in Python virtual environments)
                if not self.slurm_connection.remote_path_exists(os.path.join(selected_directory, "bin", "activate")):
                    show_warning_toast(self, "Warning", "The selected directory doesn't appear to be a Python virtual environment (no bin/activate found).")
                
                # Update the combo box with the selected path
                if self.venv_combo.findText(selected_directory) == -1:
                    self.venv_combo.addItem(selected_directory)
                self.venv_combo.setCurrentText(selected_directory)
                self._update_preview()

    def _update_preview(self):
        try:
            # Job Information
            job_name = self.job_name_edit.text().strip() or "job"
            job_comment = self.job_comment_edit.text().strip()
            
            # Resource Allocation
            partition = self.partition_combo.currentText()
            account = self.account_combo.currentText()
            
            # Time Limit
            time = self.time_limit_edit.time()
            hours = time.hour()
            minutes = time.minute()
            seconds = time.second()
            # Format as days-hours:minutes:seconds (SLURM format)
            days = hours // 24
            hours = hours % 24
            time_limit = f"{days}-{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # Node and CPU Configuration
            nodes = self.nodes_spin.value()
            ntasks = self.ntasks_spin.value()
            cpus_per_task = self.cpu_per_task_spin.value()
            cpus_per_node = self.cpus_per_node_spin.value()
            
            # Memory Configuration
            memory = f"{self.memory_spin.value()}{self.memory_unit_combo.currentText()}"
            
            # Resource Constraints
            selected_constraints = self.constraint_combo.get_checked_items()
            constraint = "|".join(selected_constraints) if selected_constraints else None
            
            # QoS
            qos = self.qos_combo.currentText()
            qos = None if qos == "None" else qos
            
            # GPU Configuration
            gres = None
            if self.gpu_check.isChecked():
                gpu_type = self.gpu_type_combo.currentText()
                gpu_count = self.gpu_count_spin.value()
                gres = f"gpu:{gpu_count}" if gpu_type == "any" else f"gpu:{gpu_type}:{gpu_count}"
            
            # File Management
            output_file = self.output_file_edit.text().strip()
            error_file = self.error_file_edit.text().strip()
            working_dir = self.working_dir_edit.text().strip()
            
            # Command
            command = self.command_text.toPlainText().strip()
            
            # Build SLURM Script
            script_lines = [
                "#!/bin/bash -l",
                "",
                "# ============================================",
                f"# Job Name: {job_name}",
                f"# Job Comment: {job_comment or 'N/A'}",
                f"# Submission Time: {QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss')}",
                "# ============================================\n"
            ]
            
            # Basic Directives
            script_lines.extend([
                "# Basic Job Configuration",
                f"#SBATCH --job-name={job_name}",
                f"#SBATCH --partition={partition}",
                f"#SBATCH --time={time_limit}",
                f"#SBATCH --nodes={nodes}",
                f"#SBATCH --ntasks={ntasks}",
                f"#SBATCH --cpus-per-task={cpus_per_task}",
                f"#SBATCH --cpus-per-node={cpus_per_node}",
                f"#SBATCH --mem={memory}",
            ])
            
            # Optional Directives
            if qos:
                script_lines.append(f"#SBATCH --qos={qos}")
            if account:
                script_lines.append(f"#SBATCH --account={account}")
            if constraint:
                script_lines.append(f'#SBATCH --constraint="{constraint}"')
            if gres:
                script_lines.append(f"#SBATCH --gres={gres}")
            if output_file:
                script_lines.append(f"#SBATCH --output={output_file}")
            if error_file:
                script_lines.append(f"#SBATCH --error={error_file}")
            
            # Job Array
            if hasattr(self, 'array_group') and self.array_group.isChecked():
                array_spec = ""
                if self.array_format_combo.currentIndex() == 0:  # Range
                    start = self.array_start_spin.value()
                    end = self.array_end_spin.value()
                    array_spec = f"{start}-{end}"
                elif self.array_format_combo.currentIndex() == 1:  # List
                    array_spec = self.array_list_edit.text()
                elif self.array_format_combo.currentIndex() == 2:  # Range with step
                    start = self.array_start_spin.value()
                    end = self.array_end_spin.value()
                    step = self.array_step_spin.value()
                    array_spec = f"{start}-{end}:{step}"
                if array_spec:
                    script_lines.append(f"#SBATCH --array={array_spec}")
                    if hasattr(self, 'max_jobs_check') and self.max_jobs_check.isChecked():
                        max_jobs = self.max_jobs_spin.value()
                        script_lines[-1] += f"%{max_jobs}"
            
            # Dependencies
            if hasattr(self, 'dep_type_combo'):
                dep_type = self.dep_type_combo.currentText().split(" - ")[0].strip()
                dep_ids = [self.dep_id_display_combo.itemText(i) for i in range(self.dep_id_display_combo.count())]
                dep_ids_str = ":".join(dep_ids)
                if dep_type == "singleton":
                    script_lines.append(f"#SBATCH --dependency={dep_type}")
                elif dep_ids_str:
                    script_lines.append(f"#SBATCH --dependency={dep_type}:{dep_ids_str}")
            
            # Working Directory
            if working_dir:
                script_lines.extend([
                    "# Change to working directory",
                    f"cd {working_dir} || {{ echo \"Failed to change to directory: {working_dir}\"; exit 1; }}",
                ])
            
            # Activate Virtual Environment if specified
            venv_path = self.venv_combo.currentText()
            if venv_path and venv_path != "None":
                script_lines.extend([
                    "# Activate Python virtual environment",
                    f'if [ -f "{venv_path}/bin/activate" ]; then',
                    f'    source "{venv_path}/bin/activate"',
                    'else',
                    f'    echo "Warning: Virtual environment not found at {venv_path}"',
                    '    echo "Falling back to system Python"',
                    'fi\n'
                ])
            
            
            # Command Execution
            if command:
                script_lines.extend([
                    "# ============================================",
                    "# Command Execution",
                    "# ============================================\n",
                    f"{command}\n",
                ])
            else:
                script_lines.extend([
                    'echo "No command specified. Exiting..."',
                    'exit 1'
                ])
            
            # Set the script content
            script_content = '\n'.join(script_lines)
            self.preview_text.setText(script_content)
            
        except Exception as e:
            self.preview_text.setText(f"Error generating preview: {str(e)}")
        self.preview_text.setStyleSheet(f"""
            background-color: #282a36;
            color: #f8f8f2;
            font-family: monospace;
            padding: 10px;
            border: 1px solid {COLOR_DARK_BORDER};
            selection-background-color: {COLOR_BLUE};
        """)

    def get_job_details(self):
        job_name = self.job_name_edit.text()
        partition = self.partition_combo.currentText()
        account = self.account_combo.currentText()
        time_limit = self.time_limit_edit.time().toString("HH:mm:ss")
        nodes = self.nodes_spin.value()
        cpus_per_task = self.cpu_per_task_spin.value()
        selected_constraints = self.constraint_combo.get_checked_items()
        constraint = "|".join(selected_constraints) if selected_constraints else "None"
        qos = self.qos_combo.currentText()
        if qos == "None":
            qos = None
        gres = None
        if self.gpu_check.isChecked():
            gpu_type = self.gpu_type_combo.currentText()
            gpu_count = self.gpu_count_spin.value()
            gres = f"gpu:{gpu_count}" if gpu_type == "any" else f"gpu:{gpu_type}:{gpu_count}"
        output_file = self.output_file_edit.text()
        error_file = self.error_file_edit.text()
        working_dir = self.working_dir_edit.text()
        venv_path = self.venv_combo.currentText()
        if venv_path == "None":
            venv_path = None
        command = self.command_text.toPlainText()
        script_lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={job_name}",
            f"#SBATCH --partition={partition}",
            f"#SBATCH --time={time_limit}",
            f"#SBATCH --nodes={nodes}",
        ]
        if cpus_per_task > 1:
            script_lines.append(f"#SBATCH --cpus-per-task={cpus_per_task}")
        script_lines.append(f"#SBATCH --mem={memory}")
        if constraint:
            script_lines.append(f"#SBATCH --constraint=\"{constraint}\"")
        if qos:
            script_lines.append(f"#SBATCH --qos={qos}")
        if account:
            script_lines.append(f"#SBATCH --account={account}")
        if gres:
            script_lines.append(f"#SBATCH --gres={gres}")
        if output_file:
            script_lines.append(f"#SBATCH --output={output_file}")
        if error_file:
            script_lines.append(f"#SBATCH --error={error_file}")
        # Job array
        if self.array_group.isChecked():
            array_spec = ""
            if self.array_format_combo.currentIndex() == 0:  # Range
                start = self.array_start_spin.value()
                end = self.array_end_spin.value()
                array_spec = f"{start}-{end}"
            elif self.array_format_combo.currentIndex() == 1:  # List
                array_spec = self.array_list_edit.text()
            elif self.array_format_combo.currentIndex() == 2:  # Range with step
                start = self.array_start_spin.value()
                end = self.array_end_spin.value()
                step = self.array_step_spin.value()
                array_spec = f"{start}-{end}:{step}"
            if array_spec:
                script_lines.append(f"#SBATCH --array={array_spec}")
                if self.max_jobs_check.isChecked():
                    max_jobs = self.max_jobs_spin.value()
                    script_lines[-1] += f"%{max_jobs}"
        # Dependencies
        dep_type = self.dep_type_combo.currentText().split(" - ")[0].strip()
        dep_ids = [self.dep_id_display_combo.itemText(i) for i in range(self.dep_id_display_combo.count())]
        dep_ids_str = ":".join(dep_ids)
        if dep_type == "singleton":
            script_lines.append(f"#SBATCH --dependency={dep_type}")
        elif dep_ids_str:
            script_lines.append(f"#SBATCH --dependency={dep_type}:{dep_ids_str}")
        if working_dir:
            script_lines.append(f"\ncd {working_dir}")
        if self.array_group.isChecked():
            script_lines.append("\n# Job array information")
            script_lines.append("echo \"Running array job ${SLURM_ARRAY_JOB_ID}, task ID ${SLURM_ARRAY_TASK_ID}\"")
            script_lines.append("")
        script_lines.append("# Job command")
        script_lines.append(command)
        preview_text = "\n".join(script_lines)
        self.preview_text.setText(preview_text)
        self.preview_text.setStyleSheet(f"""
            background-color: #282a36;
            color: #f8f8f2;
            font-family: monospace;
            padding: 10px;
            border: 1px solid {COLOR_DARK_BORDER};
            selection-background-color: {COLOR_BLUE};
        """)

    def get_job_details(self):
        job_name = self.job_name_edit.text()
        partition = self.partition_combo.currentText()
        account = self.account_combo.currentText()
        time_limit = self.time_limit_edit.time().toString("HH:mm:ss")
        nodes = self.nodes_spin.value()
        cpus_per_task = self.cpu_per_task_spin.value()
        selected_constraints = self.constraint_combo.get_checked_items()
        constraint = "|".join(selected_constraints) if selected_constraints else "None"
        qos = self.qos_combo.currentText()
        if qos == "None":
            qos = None
        gres = None
        if self.gpu_check.isChecked():
            gpu_type = self.gpu_type_combo.currentText()
            gpu_count = self.gpu_count_spin.value()
            gres = f"gpu:{gpu_count}" if gpu_type == "any" else f"gpu:{gpu_type}:{gpu_count}"
        output_file = self.output_file_edit.text()
        error_file = self.error_file_edit.text()
        working_dir = self.working_dir_edit.text()
        result = {
            "job_name": job_name,
            "partition": partition,
            "time_limit": time_limit,
            "command": self.command_text.toPlainText(),
            "account": account,
            "constraint": f"\"{constraint}\"",
            "qos": qos,
            "gres": gres,
            "nodes": nodes,
            "memory": str(self.memory_spin.value()) + self.memory_unit_combo.currentText().replace("B", ""),
            "cpus_per_task": cpus_per_task,
            "output_file": output_file,
            "error_file": error_file,
            "project": self.selected_project,
            "working_dir": working_dir
        }
        # Job array
        if self.array_group.isChecked():
            array_spec = ""
            if self.array_format_combo.currentIndex() == 0:  # Range
                start = self.array_start_spin.value()
                end = self.array_end_spin.value()
                array_spec = f"{start}-{end}"
            elif self.array_format_combo.currentIndex() == 1:  # List
                array_spec = self.array_list_edit.text()
            elif self.array_format_combo.currentIndex() == 2:  # Range with step
                start = self.array_start_spin.value()
                end = self.array_end_spin.value()
                step = self.array_step_spin.value()
                array_spec = f"{start}-{end}:{step}"
            if array_spec:
                result["array"] = array_spec
                if self.max_jobs_check.isChecked():
                    max_jobs = self.max_jobs_spin.value()
                    result["array_max_jobs"] = max_jobs
        # Dependencies
        dep_type = self.dep_type_combo.currentText().split(" - ")[0].strip()
        dep_ids = [self.dep_id_display_combo.itemText(i) for i in range(self.dep_id_display_combo.count())]
        dep_ids_str = ":".join(dep_ids)
        if dep_type == "singleton":
            result["dependency"] = "singleton"
        elif dep_ids_str:
            result["dependency"] = f"{dep_type}:{dep_ids_str}"
        # Discord notifications
        discord_settings = self._get_discord_settings_from_config()
        
        result["discord_notifications"] = discord_settings
        return result
    
    def _get_discord_settings_from_config(self):
        """Get Discord settings from application configuration"""
        try:
            
            settings = QSettings(str(Path(settings_path)), QSettings.Format.IniFormat)
            settings.beginGroup("NotificationSettings")
            
            discord_config = {
                "enabled": settings.value("discord_enabled", False, type=bool),
                "notify_start": True,  # Default behaviors
                "notify_complete": True,
                "notify_failed": True,
                "message_prefix": f"[{self.selected_project}]"
            }
            
            settings.endGroup()
            return discord_config
            
        except Exception as e:
            print(f"Error loading Discord settings: {e}")
            return {"enabled": False}
        
class ModifyJobDialog(NewJobDialog):
    """
    Dialog for modifying existing job parameters.
    Inherits from NewJobDialog and pre-fills fields with existing job data.
    """

    def __init__(self, job, project_name, slurm_connection=None, parent=None):
        self.job = job
        self.project_name = project_name
        super().__init__(project_name, slurm_connection, parent)
        self.setWindowTitle(f"Modify Job: {job.name}")
        self._update_header_for_modify()
        self._populate_fields_from_job()

    def _update_header_for_modify(self):
        for i in range(self.main_layout.count()):
            item = self.main_layout.itemAt(i)
            if item and item.layout():
                layout = item.layout()
                for j in range(layout.count()):
                    widget = layout.itemAt(j).widget()
                    if isinstance(widget, QLabel) and "New Job for Project" in widget.text():
                        widget.setText(f"Modify Job: {self.job.name}")
                        widget.setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 14px; font-weight: bold;")
                        break
        self.create_button.setText("Save Changes")
        self.create_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "ok.svg")))

    def _populate_fields_from_job(self):
        # Fill all dialog fields with data from the existing job
        job = self.job
        if job.name:
            self.job_name_edit.setText(job.name)
        if job.partition:
            index = self.partition_combo.findText(job.partition)
            if index >= 0:
                self.partition_combo.setCurrentIndex(index)
        if job.account:
            index = self.account_combo.findText(job.account)
            if index >= 0:
                self.account_combo.setCurrentIndex(index)
        if job.time_limit:
            try:
                time_parts = job.time_limit.split(':')
                if len(time_parts) == 3:
                    hours, minutes, seconds = map(int, time_parts)
                    time = QTime(hours, minutes, seconds)
                    self.time_limit_edit.setTime(time)
            except (ValueError, AttributeError):
                pass
        if job.nodes:
            self.nodes_spin.setValue(job.nodes)
        if job.cpus:
            self.cpu_per_task_spin.setValue(job.cpus)
        if job.memory:
            try:
                memory_str = job.memory.upper()
                if memory_str.endswith('G') or memory_str.endswith('GB'):
                    value = float(memory_str.rstrip('GB'))
                    self.memory_spin.setValue(int(value))
                    self.memory_unit_combo.setCurrentText("GB")
                elif memory_str.endswith('M') or memory_str.endswith('MB'):
                    value = float(memory_str.rstrip('MB'))
                    self.memory_spin.setValue(int(value))
                    self.memory_unit_combo.setCurrentText("MB")
            except (ValueError, AttributeError):
                pass
        if job.constraints:
            constraints_str = job.constraints.strip('"') if job.constraints else ""
            if constraints_str:
                constraints = constraints_str.split('|')
                for i in range(self.constraint_combo.model.rowCount()):
                    item = self.constraint_combo.model.item(i)
                    if item and item.text() in constraints:
                        item.setCheckState(Qt.CheckState.Checked)
                self.constraint_combo._update_selected_text()
        if job.qos:
            index = self.qos_combo.findText(job.qos)
            if index >= 0:
                self.qos_combo.setCurrentIndex(index)
            else:
                none_index = self.qos_combo.findText("None")
                if none_index >= 0:
                    self.qos_combo.setCurrentIndex(none_index)
        if job.gres and "gpu" in job.gres.lower():
            self.gpu_check.setChecked(True)
            self._toggle_gpu_selection(True)
            try:
                gpu_parts = job.gres.split(':')
                if len(gpu_parts) == 2:
                    gpu_count = int(gpu_parts[1])
                    self.gpu_type_combo.setCurrentText("any")
                    self.gpu_count_spin.setValue(gpu_count)
                elif len(gpu_parts) == 3:
                    gpu_type = gpu_parts[1]
                    gpu_count = int(gpu_parts[2])
                    type_index = self.gpu_type_combo.findText(gpu_type)
                    if type_index >= 0:
                        self.gpu_type_combo.setCurrentIndex(type_index)
                    self.gpu_count_spin.setValue(gpu_count)
            except (ValueError, IndexError, AttributeError):
                pass
        if job.output_file:
            self.output_file_edit.setText(job.output_file)
        if job.error_file:
            self.error_file_edit.setText(job.error_file)
        if job.working_dir:
            self.working_dir_edit.setText(job.working_dir)
        if job.command:
            self.command_text.setPlainText(job.command)
        if job.array_spec:
            self.array_group.setChecked(True)
            array_spec = job.array_spec
            if '-' in array_spec and ':' in array_spec:
                self.array_format_combo.setCurrentIndex(2)
                try:
                    range_part, step = array_spec.split(':')
                    start, end = range_part.split('-')
                    self.array_start_spin.setValue(int(start))
                    self.array_end_spin.setValue(int(end))
                    self.array_step_spin.setValue(int(step))
                except ValueError:
                    pass
            elif '-' in array_spec:
                self.array_format_combo.setCurrentIndex(0)
                try:
                    start, end = array_spec.split('-')
                    self.array_start_spin.setValue(int(start))
                    self.array_end_spin.setValue(int(end))
                except ValueError:
                    pass
            else:
                self.array_format_combo.setCurrentIndex(1)
                self.array_list_edit.setText(array_spec)
            self._update_array_inputs(self.array_format_combo.currentIndex())
            if job.array_max_jobs:
                self.max_jobs_check.setChecked(True)
                self.max_jobs_spin.setValue(job.array_max_jobs)
                self._toggle_max_jobs(True)
        if job.dependency:
            dep_parts = job.dependency.split(':')
            if len(dep_parts) >= 1:
                dep_type = dep_parts[0]
                for i in range(self.dep_type_combo.count()):
                    item_text = self.dep_type_combo.itemText(i)
                    if item_text.startswith(dep_type):
                        self.dep_type_combo.setCurrentIndex(i)
                        break
                if dep_type != "singleton" and len(dep_parts) > 1:
                    job_ids = dep_parts[1].split(',') if len(dep_parts) > 1 else []
                    for job_id in job_ids:
                        if job_id.strip():
                            self.dep_id_display_combo.addItem(job_id.strip())
        self._update_preview()

    def get_job_details(self):
        job_name = self.job_name_edit.text()
        partition = self.partition_combo.currentText()
        account = self.account_combo.currentText()
        time_limit = self.time_limit_edit.time().toString("HH:mm:ss")
        nodes = self.nodes_spin.value()
        cpus_per_task = self.cpu_per_task_spin.value()
        selected_constraints = self.constraint_combo.get_checked_items()
        constraint = "|".join(selected_constraints) if selected_constraints else "None"
        qos = self.qos_combo.currentText()
        if qos == "None":
            qos = None
        gres = None
        if self.gpu_check.isChecked():
            gpu_type = self.gpu_type_combo.currentText()
            gpu_count = self.gpu_count_spin.value()
            gres = f"gpu:{gpu_count}" if gpu_type == "any" else f"gpu:{gpu_type}:{gpu_count}"
        output_file = self.output_file_edit.text()
        error_file = self.error_file_edit.text()
        working_dir = self.working_dir_edit.text()
        result = {
            "job_name": job_name,
            "partition": partition,
            "time_limit": time_limit,
            "command": self.command_text.toPlainText(),
            "account": account,
            "constraint": f"\"{constraint}\"",
            "qos": qos,
            "gres": gres,
            "nodes": nodes,
            "memory": str(self.memory_spin.value()) + self.memory_unit_combo.currentText().replace("B", ""),
            "cpus_per_task": cpus_per_task,
            "output_file": output_file,
            "error_file": error_file,
            "project": self.selected_project,
            "working_dir": working_dir
        }
        # Job array
        if self.array_group.isChecked():
            array_spec = ""
            if self.array_format_combo.currentIndex() == 0:  # Range
                start = self.array_start_spin.value()
                end = self.array_end_spin.value()
                array_spec = f"{start}-{end}"
            elif self.array_format_combo.currentIndex() == 1:  # List
                array_spec = self.array_list_edit.text()
            elif self.array_format_combo.currentIndex() == 2:  # Range with step
                start = self.array_start_spin.value()
                end = self.array_end_spin.value()
                step = self.array_step_spin.value()
                array_spec = f"{start}-{end}:{step}"
            if array_spec:
                result["array"] = array_spec
                if self.max_jobs_check.isChecked():
                    max_jobs = self.max_jobs_spin.value()
                    result["array_max_jobs"] = max_jobs
        # Dependencies
        dep_type = self.dep_type_combo.currentText().split(" - ")[0].strip()
        dep_ids = [self.dep_id_display_combo.itemText(i) for i in range(self.dep_id_display_combo.count())]
        dep_ids_str = ":".join(dep_ids)
        if dep_type == "singleton":
            result["dependency"] = "singleton"
        elif dep_ids_str:
            result["dependency"] = f"{dep_type}:{dep_ids_str}"
        # Discord notifications
        discord_settings = self._get_discord_settings_from_config()
        
        result["discord_notifications"] = discord_settings
        return result
    
    def _get_discord_settings_from_config(self):
        """Get Discord settings from application configuration"""
        try:
            
            settings = QSettings(str(Path(settings_path)), QSettings.Format.IniFormat)
            settings.beginGroup("NotificationSettings")
            
            discord_config = {
                "enabled": settings.value("discord_enabled", False, type=bool),
                "notify_start": True,  # Default behaviors
                "notify_complete": True,
                "notify_failed": True,
                "message_prefix": f"[{self.selected_project}]"
            }
            
            settings.endGroup()
            return discord_config
            
        except Exception as e:
            print(f"Error loading Discord settings: {e}")
            return {"enabled": False}
        
        details = super().get_job_details()
        details["original_job_id"] = self.job.id
        details["is_modification"] = True
        return details