

from pathlib import Path
from modules.defaults import *
from modules.remote_directory_panel import RemoteDirectoryDialog
# Assuming these modules/files exist in your project structure
from utils import create_separator, script_dir
from style import AppStyles
from modules.toast_notify import show_error_toast, show_info_toast, show_success_toast, show_warning_toast


COLOR_BLUE = "#06b0d6"


class CheckableComboBox(QComboBox):
    # Define the signal at the class level
    selection_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.setPlaceholderText("Select constraints...")

        # Set minimum width to ensure text is visible
        self.setMinimumWidth(250)

        # Create and set model
        self.model = QStandardItemModel()
        self.setModel(self.model)

        # Create and set view with better spacing
        self.view = QListView()
        # self.view.setSpacing(4)  # Add spacing between items for better visibility
        self.setView(self.view)

        # Make dropdown wider
        self.view.setMinimumWidth(300)

        # Connect signals
        self.model.itemChanged.connect(self._update_selected_text)

        # Install event filter to handle mouse clicks
        self.view.viewport().installEventFilter(self)

    def showPopup(self):
        """Make sure popup is wide enough to show text"""
        super().showPopup()
        # Make popup at least as wide as combobox
        popup_width = max(self.width(), 300)
        self.view.setFixedWidth(popup_width)

    def eventFilter(self, watched, event):
        """Handle checkbox click events"""
        if watched == self.view.viewport() and event.type() == QEvent.Type.MouseButtonRelease:
            index = self.view.indexAt(event.pos())
            if index.isValid():
                item = self.model.itemFromIndex(index)

                # Toggle checkbox state
                if item.checkState() == Qt.CheckState.Checked:
                    item.setCheckState(Qt.CheckState.Unchecked)
                else:
                    item.setCheckState(Qt.CheckState.Checked)

                # Prevent popup from closing
                return True

        return super().eventFilter(watched, event)

    def hidePopup(self):
        """Keep popup open when clicking inside it"""
        if self.view.underMouse():
            return
        super().hidePopup()

    def add_item(self, text, user_data=None):
        """Add a new checkable item"""
        item = QStandardItem(text)
        # Make sure checkboxes are visible and enabled
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable |
                      Qt.ItemFlag.ItemIsEnabled)
        item.setCheckState(Qt.CheckState.Unchecked)
        if user_data is not None:
            item.setData(user_data, Qt.ItemDataRole.UserRole)
        self.model.appendRow(item)

    def get_checked_items(self):
        """Return all checked item texts"""
        checked_items = []
        for i in range(self.model.rowCount()):
            item = self.model.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked_items.append(item.text())
        return checked_items

    def _update_selected_text(self, item=None):
        """Update the displayed text in the combobox"""
        selected_texts = self.get_checked_items()
        if not selected_texts:
            self.lineEdit().setText("None selected")
        else:
            # Display up to 30 characters, then ellipsis
            text = ", ".join(selected_texts)
            if len(text) > 30:
                self.lineEdit().setText(
                    f"{len(selected_texts)} items selected")
            else:
                self.lineEdit().setText(text)

        # Emit signal about selection change
        self.selection_changed.emit()


# Add a new dialog for creating a new job
class NewJobDialog(QDialog):
    def __init__(self, selected_project, slurm_connection=None, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"New Job for Project: {selected_project}")
        self.setMinimumSize(800, 600)
        self.selected_project = selected_project
        self.slurm_connection = slurm_connection
        self.discord_webhook_available = self._check_discord_webhook_availability()

        # Prefetchable data
        self.partitions = ["Loading..."] if slurm_connection else [
            "main", "gpu", "long", "debug"]
        self.constraints = ["Loading..."] if slurm_connection else [
            "intel", "amd", "highmem"]
        self.qos_list = ["Loading..."] if slurm_connection else [
            "normal", "debug", "high"]
        self.accounts = ["Loading..."] if slurm_connection else [
            "project1", "project2", "mylab"]
        self.gres = ["Loading..."] if slurm_connection else [
            "gpu:1", "gpu:2", "gpu:rtx5000:1"]

        # IMPROVED COLORS: Better contrast for hover states and text
        # Slightly lighter than background for better contrast
        self.HOVER_DARK_BG = "#3a3d4d"
        self.ACTIVE_TEXT = "#ffffff"    # White text for active elements
        self.HOVER_TEXT = "#000000"     # Black text for hover states to ensure contrast

        # Improved stylesheet with better colors for contrast
        self.setStyleSheet(AppStyles.get_complete_stylesheet(THEME_DARK))

        # If we have a slurm connection, prefetch the data
        self._prefetch_data()

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # Header with title
        header_layout = QHBoxLayout()
        header_label = QLabel(f"New Job for Project: {selected_project}")
        header_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_label.setStyleSheet(f"color: {COLOR_BLUE};")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        self.main_layout.addLayout(header_layout)

        # Add a separator
        separator = create_separator()
        self.main_layout.addWidget(separator)

        # Create tabs for better organization
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # Essential tab
        self.essential_tab = QWidget()
        self.tabs.addTab(self.essential_tab, "Essentials")
        self._setup_essential_tab()

        # Advanced tab
        self.advanced_tab = QWidget()
        self.tabs.addTab(self.advanced_tab, "Advanced")
        self._setup_advanced_tab()

        # Command tab
        self.command_tab = QWidget()
        self.tabs.addTab(self.command_tab, "Command Script")
        self._setup_command_tab()

        # NEW: Job Array Tab
        self.job_array_tab = QWidget()
        self.tabs.addTab(self.job_array_tab, "Job Array")
        self._setup_job_array_tab()  # Call the new setup method

        # NEW: Job Dependencies Tab
        self.job_dependencies_tab = QWidget()
        self.tabs.addTab(self.job_dependencies_tab, "Dependencies")
        self._setup_job_dependencies_tab()  # Call the new setup method

        if self.discord_webhook_available:
            self.notifications_tab = QWidget()
            self.tabs.addTab(self.notifications_tab, "Notifications")
            self._setup_notifications_tab()

        # Buttons at the bottom
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName(BTN_RED)
        self.cancel_button.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "cancel.svg")))
        self.cancel_button.clicked.connect(self.reject)

        self.create_button = QPushButton("Create Job")
        self.create_button.setObjectName(BTN_GREEN)
        self.create_button.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "ok.svg")))
        self.create_button.clicked.connect(self.accept)

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.create_button)
        self.main_layout.addLayout(button_layout)

    def _prefetch_data(self):
        """Prefetch data from SLURM if a connection is available"""
        if not self.slurm_connection or not self.slurm_connection.check_connection():
            return

        try:
            # These should already be populated by the slurm_connection
            self.partitions = self.slurm_connection.partitions
            self.constraints = self.slurm_connection.constraints
            self.qos_list = self.slurm_connection.qos_list
            self.accounts = self.slurm_connection.accounts
            self.gres = self.slurm_connection.gres

            # NEW: Try to fetch running jobs for dependency selection
            self.running_jobs = self.slurm_connection.get_running_jobs()
        except Exception as e:
            print(f"Error prefetching SLURM data: {e}")
            self.running_jobs = []

    def _setup_essential_tab(self):
        layout = QFormLayout(self.essential_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Job Name
        self.job_name_edit = QLineEdit()
        self.job_name_edit.setPlaceholderText("Enter job name")
        layout.addRow(self._create_label("Job Name*:"), self.job_name_edit)

        # Partition
        self.partition_combo = QComboBox()
        self.partition_combo.addItems(self.partitions)
        layout.addRow(self._create_label("Partition*:"), self.partition_combo)

        # Account
        self.account_combo = QComboBox()
        self.account_combo.addItems(self.accounts)
        layout.addRow(self._create_label("Account*:"), self.account_combo)

        # Time Limit
        self.time_limit_edit = QTimeEdit()
        self.time_limit_edit.setDisplayFormat("HH:mm:ss")
        self.time_limit_edit.setTime(QTime(1, 0, 0))  # Default: 1 hour
        layout.addRow(self._create_label("Time Limit*:"), self.time_limit_edit)

        # Nodes
        self.nodes_spin = QSpinBox()
        self.nodes_spin.setMinimum(1)
        self.nodes_spin.setMaximum(1000)
        self.nodes_spin.setValue(1)
        layout.addRow(self._create_label("Number of Nodes:"), self.nodes_spin)

        # # Tasks
        # self.tasks_spin = QSpinBox()
        # self.tasks_spin.setMinimum(1)
        # self.tasks_spin.setMaximum(1000)
        # self.tasks_spin.setValue(1)
        # layout.addRow(self._create_label("Tasks per Node:"), self.tasks_spin)

        # CPU cores per task
        self.cpu_per_task_spin = QSpinBox()
        self.cpu_per_task_spin.setMinimum(1)
        self.cpu_per_task_spin.setMaximum(128)
        self.cpu_per_task_spin.setValue(1)
        layout.addRow(self._create_label(
            "CPUs per Task:"), self.cpu_per_task_spin)

        # Memory
        memory_widget = QWidget()
        self.memory_layout = QHBoxLayout(memory_widget)
        self.memory_layout.setContentsMargins(0, 0, 0, 0)
        self.memory_layout.setSpacing(10)

        self.memory_spin = QSpinBox()
        self.memory_spin.setMinimum(1)
        self.memory_spin.setMaximum(999)
        self.memory_spin.setValue(8)

        self.memory_unit_combo = QComboBox()
        self.memory_unit_combo.addItems(["MB", "GB"])
        self.memory_unit_combo.setCurrentText("GB")

        self.memory_layout.addWidget(self.memory_spin)
        self.memory_layout.addWidget(self.memory_unit_combo)
        self.memory_layout.addStretch()

        layout.addRow(self._create_label("Memory Request:"), memory_widget)

        # Connect signals for updating preview
        self.job_name_edit.textChanged.connect(self._update_preview)
        self.partition_combo.currentIndexChanged.connect(self._update_preview)
        self.account_combo.currentIndexChanged.connect(self._update_preview)
        self.time_limit_edit.timeChanged.connect(self._update_preview)
        self.nodes_spin.valueChanged.connect(self._update_preview)
        self.cpu_per_task_spin.valueChanged.connect(self._update_preview)
        self.memory_spin.valueChanged.connect(self._update_preview)
        self.memory_unit_combo.currentIndexChanged.connect(
            self._update_preview)

    def _setup_advanced_tab(self):
        layout = QFormLayout(self.advanced_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Constraints (Using custom CheckableComboBox)
        self.constraint_combo = CheckableComboBox()
        for constraint_option in self.constraints:
            self.constraint_combo.add_item(constraint_option)
        self.constraint_combo.selection_changed.connect(
            self._update_preview)  # Connect custom signal

        layout.addRow(self._create_label(
            "Node Constraint:"), self.constraint_combo)

        # QoS
        self.qos_combo = QComboBox()
        self.qos_combo.addItems(["None"] + self.qos_list)
        self.qos_combo.currentIndexChanged.connect(
            self._update_preview)  # Connect signal
        layout.addRow(self._create_label(
            "Quality of Service:"), self.qos_combo)

        # GRES (Generic Resources, typically GPUs)
        self.gres_group = QGroupBox("Generic Resources (GRES)")
        gres_layout = QVBoxLayout(self.gres_group)
        gres_layout.setSpacing(10)

        # GPU checkbox and selection
        self.gpu_check = QCheckBox("Request GPU")
        self.gpu_check.stateChanged.connect(self._toggle_gpu_selection)
        self.gpu_check.stateChanged.connect(
            self._update_preview)  # Also update preview
        gres_layout.addWidget(self.gpu_check)

        # GPU selection (type and count)
        gpu_selection_widget = QWidget()
        gpu_selection_layout = QHBoxLayout(gpu_selection_widget)
        gpu_selection_layout.setContentsMargins(0, 0, 0, 0)
        gpu_selection_layout.setSpacing(10)

        self.gpu_type_combo = QComboBox()
        # Parse GPU types from the GRES list
        gpu_types = ["any"]
        for g in self.gres:
            if isinstance(g, str) and "gpu" in g.lower():
                try:
                    # Improved parsing for "gpu:type:count" or "gpu:count"
                    parts = g.split(':')
                    if len(parts) == 3 and parts[0].lower() == 'gpu':
                        gpu_type = parts[1]
                        if gpu_type not in gpu_types:
                            gpu_types.append(gpu_type)
                    elif len(parts) == 2 and parts[0].lower() == 'gpu' and parts[1].isdigit():
                        # This case handles generic "gpu:1", "gpu:2" where type is 'any'
                        pass
                except (IndexError, ValueError):
                    continue

        self.gpu_type_combo.addItems(gpu_types)
        self.gpu_type_combo.setEnabled(False)
        self.gpu_type_combo.currentIndexChanged.connect(
            self._update_preview)  # Connect signal

        self.gpu_count_spin = QSpinBox()
        self.gpu_count_spin.setMinimum(1)
        self.gpu_count_spin.setMaximum(8)
        self.gpu_count_spin.setValue(1)
        self.gpu_count_spin.setEnabled(False)
        self.gpu_count_spin.valueChanged.connect(
            self._update_preview)  # Connect signal

        gpu_selection_layout.addWidget(self._create_label("GPU Type:"))
        gpu_selection_layout.addWidget(self.gpu_type_combo)
        gpu_selection_layout.addWidget(self._create_label("Count:"))
        gpu_selection_layout.addWidget(self.gpu_count_spin)
        gpu_selection_layout.addStretch()

        gres_layout.addWidget(gpu_selection_widget)

        layout.addRow("", self.gres_group)

        # Output and Error Files
        self.output_file_edit = QLineEdit()
        self.output_file_edit.setPlaceholderText("Path for job output")
        self.output_file_edit.setText(".logs/out_%A.log")
        self.output_file_edit.textChanged.connect(
            self._update_preview)  # Connect signal
        layout.addRow(self._create_label(
            "Output File:"), self.output_file_edit)

        self.error_file_edit = QLineEdit()
        self.error_file_edit.setPlaceholderText("Path for job errors")
        self.error_file_edit.setText(".logs/err_%A.log")
        self.error_file_edit.textChanged.connect(
            self._update_preview)  # Connect signal
        layout.addRow(self._create_label("Error File:"), self.error_file_edit)

        # Working Directory
        working_dir_widget = QWidget()
        self.working_dir_layout = QHBoxLayout(working_dir_widget)
        self.working_dir_layout.setContentsMargins(0, 0, 0, 0)
        self.working_dir_layout.setSpacing(10)

        self.working_dir_edit = QLineEdit()
        self.working_dir_edit.setPlaceholderText("Working directory for job")
        self.working_dir_edit.textChanged.connect(
            self._update_preview)  # Connect signal

        self.browse_dir_button = QPushButton("Browse...")
        self.browse_dir_button.setObjectName(BTN_BLUE)
        self.browse_dir_button.clicked.connect(self._browse_working_dir)
        self.browse_dir_button.setFixedWidth(100)

        self.working_dir_layout.addWidget(self.working_dir_edit)
        self.working_dir_layout.addWidget(self.browse_dir_button)

        layout.addRow(self._create_label(
            "Working Directory:"), working_dir_widget)

    def _setup_command_tab(self):
        layout = QVBoxLayout(self.command_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Command/Script
        command_label = self._create_label(
            "Enter the command or script to execute:")
        command_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(command_label)

        self.command_text = QTextEdit()
        self.command_text.setPlaceholderText(
            "Enter your job command or script here\nExample: python3 /path/to/script.py --arg1 value1")
        self.command_text.setMinimumHeight(200)
        self.command_text.textChanged.connect(
            self._update_preview)  # Connect signal
        layout.addWidget(self.command_text)

        # Load from file option
        # file_layout = QHBoxLayout()

        # self.load_script_button = QPushButton("Load Script from File")
        # self.load_script_button.setObjectName(BTN_BLUE)
        # self.load_script_button.setIcon(
        #     QIcon(os.path.join(script_dir, "src_static", "file.svg")))
        # self.load_script_button.clicked.connect(self._load_script_from_file)

        # file_layout.addWidget(self.load_script_button)
        # file_layout.addStretch()
        # layout.addLayout(file_layout)

        # Separator
        layout.addWidget(create_separator())

        # Command preview
        preview_label = self._create_label(
            "Preview of SLURM submission script:")
        preview_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        layout.addWidget(preview_label)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText(
            "Job submission script preview will appear here")
        self.preview_text.setMinimumHeight(150)
        self.preview_text.setStyleSheet(f"""
            background-color: #282a36;
            color: #f8f8f2;
            font-family: monospace;
            padding: 10px;
            border: 1px solid {COLOR_DARK_BORDER};
        """)
        layout.addWidget(self.preview_text)

        # Update preview button
        button_layout = QHBoxLayout()

        self.update_preview_button = QPushButton("Update Preview")
        self.update_preview_button.setObjectName(BTN_BLUE)
        self.update_preview_button.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "refresh.svg")))
        self.update_preview_button.clicked.connect(self._update_preview)

        button_layout.addStretch()
        button_layout.addWidget(self.update_preview_button)
        layout.addLayout(button_layout)

    def _setup_job_array_tab(self):
        """Set up the Job Array tab"""
        layout = QVBoxLayout(self.job_array_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Job Array Group
        self.array_group = QGroupBox("Job Array")
        self.array_group.setCheckable(True)
        self.array_group.setChecked(False)
        self.array_group.toggled.connect(
            self._update_preview)  # Update preview when toggled
        array_layout = QVBoxLayout(self.array_group)
        array_layout.setSpacing(15)

        # Job array explanation
        array_explanation = QLabel(
            "Job arrays let you submit and manage multiple similar jobs with a single job submission.")
        array_explanation.setWordWrap(True)
        array_layout.addWidget(array_explanation)

        # Array format
        array_format_widget = QWidget()
        array_format_layout = QFormLayout(array_format_widget)
        array_format_layout.setContentsMargins(0, 0, 0, 0)

        self.array_format_combo = QComboBox()
        self.array_format_combo.addItems(["Range", "List", "Range with step"])
        self.array_format_combo.currentIndexChanged.connect(
            self._update_array_inputs)
        self.array_format_combo.currentIndexChanged.connect(
            self._update_preview)  # Update preview

        array_format_layout.addRow(self._create_label(
            "Array Format:"), self.array_format_combo)
        array_layout.addWidget(array_format_widget)

        # Range inputs (start, end)
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

        # Step input (for range with step)
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

        self.step_widget.setVisible(False)  # Initially hidden
        array_layout.addWidget(self.step_widget)

        # List input
        self.list_widget = QWidget()
        list_layout = QVBoxLayout(self.list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(10)

        self.array_list_edit = QLineEdit()
        self.array_list_edit.setPlaceholderText(
            "Enter array indices separated by commas (e.g., 1,3,5,7,9)")
        self.array_list_edit.textChanged.connect(self._update_preview)

        list_layout.addWidget(self._create_label("Array Indices:"))
        list_layout.addWidget(self.array_list_edit)

        list_layout.addWidget(self._create_label(
            "Example: 1,2,5,10-15,20-25:2"))

        self.list_widget.setVisible(False)  # Initially hidden
        array_layout.addWidget(self.list_widget)

        # Maximum concurrent jobs
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
        self.max_jobs_check.stateChanged.connect(
            self._update_preview)  # Update preview
        self.max_jobs_spin.setEnabled(False)
        self.max_jobs_spin.valueChanged.connect(self._update_preview)

        max_jobs_layout.addWidget(self.max_jobs_check)
        max_jobs_layout.addWidget(self.max_jobs_spin)
        max_jobs_layout.addStretch()

        array_layout.addWidget(max_jobs_widget)

        # Job Environment Variables
        array_env_label = self._create_label(
            "Environment variables for array jobs:")
        array_env_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        array_layout.addWidget(array_env_label)

        array_env_info = QLabel(
            "The following environment variables will be available in your job scripts:")
        array_env_info.setWordWrap(True)
        array_layout.addWidget(array_env_info)

        array_env_vars = QLabel("• SLURM_ARRAY_JOB_ID - Job ID for the entire job array\n"
                                "• SLURM_ARRAY_TASK_ID - Array index value for this task\n"
                                "• SLURM_ARRAY_TASK_COUNT - Total number of tasks in the array\n"
                                "• SLURM_ARRAY_TASK_MAX - Maximum index value\n"
                                "• SLURM_ARRAY_TASK_MIN - Minimum index value")
        array_env_vars.setStyleSheet(
            "color: #aaaaaa; background-color: #282a36; padding: 10px; border-radius: 4px;")
        array_layout.addWidget(array_env_vars)

        layout.addWidget(self.array_group)
        layout.addStretch()  # Push everything to the top

    def _setup_job_dependencies_tab(self):
        """Set up the Job Dependencies tab"""
        layout = QVBoxLayout(self.job_dependencies_tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Job Dependencies Group
        self.dependency_group = QGroupBox("Job Dependencies")
        # Removed setCheckable and setChecked
        self.dependency_group.setContentsMargins(
            0, 0, 0, 0)  # Adjusted margins
        dependency_layout = QVBoxLayout(self.dependency_group)
        dependency_layout.setSpacing(15)

        # Job dependency explanation
        dep_explanation = QLabel(
            "Dependencies let you specify conditions when this job should start based on the state of other jobs.")
        dep_explanation.setWordWrap(True)
        dep_explanation.setStyleSheet("color: #aaaaaa; font-style: italic;")
        dependency_layout.addWidget(dep_explanation)

        # Dependency type
        self.dep_type_combo = QComboBox()
        self.dep_type_combo.addItems([
            "after - After any specified job starts",
            "afterany - After any specified job ends (regardless of exit code)",
            "afterok - After specified jobs complete successfully",
            "afternotok - After specified jobs fail",
            "singleton - Wait until no other job with this name is running"
        ])
        self.dep_type_combo.currentIndexChanged.connect(
            self._update_preview)  # Connect to update preview
        dependency_layout.addWidget(self.dep_type_combo)

        # Running jobs selection
        self.running_jobs_group = QGroupBox("Select from Running Jobs")
        running_jobs_layout = QVBoxLayout(self.running_jobs_group)

        self.running_jobs_combo = QComboBox()
        if hasattr(self, 'running_jobs') and self.running_jobs:
            job_items = [
                f"{job['Job ID']} - {job['Job Name']} ({job['Status']})" for job in self.running_jobs]
            self.running_jobs_combo.addItems(job_items)
        else:
            self.running_jobs_combo.addItem("No running jobs found")

        self.add_job_button = QPushButton("Add to Dependencies")
        self.add_job_button.setObjectName(BTN_GREEN)
        self.add_job_button.setFixedWidth(300)
        self.add_job_button.clicked.connect(
            self._add_selected_job_to_dependencies)

        refresh_jobs_layout = QHBoxLayout()
        self.refresh_jobs_button = QPushButton("Refresh Job List")
        self.refresh_jobs_button.setObjectName(BTN_BLUE)
        self.refresh_jobs_button.clicked.connect(self._refresh_running_jobs)
        refresh_jobs_layout.addWidget(self.refresh_jobs_button)
        refresh_jobs_layout.addStretch()

        running_jobs_layout.addWidget(self.running_jobs_combo)
        running_jobs_layout.addWidget(
            self.add_job_button, alignment=Qt.AlignmentFlag.AlignCenter)
        running_jobs_layout.addLayout(refresh_jobs_layout)

        dependency_layout.addWidget(self.running_jobs_group)

        # NEW: Group box for displaying and deleting dependencies
        self.delete_dependency_group = QGroupBox("Manage Added Dependencies")
        delete_dep_layout = QVBoxLayout(self.delete_dependency_group)
        delete_dep_layout.setSpacing(10)
        delete_dep_layout.setContentsMargins(
            10, 20, 10, 10)  # Add some padding

        # Job ID input for dependencies (now a QComboBox) - MOVED HERE
        self.dep_id_widget = QWidget()
        dep_id_layout = QVBoxLayout(self.dep_id_widget)
        dep_id_layout.setContentsMargins(0, 0, 0, 0)
        dep_id_layout.setSpacing(10)

        # Changed to QComboBox for displaying added dependencies
        self.dep_id_display_combo = QComboBox()
        self.dep_id_display_combo.setPlaceholderText(
            "Added job IDs will appear here")
        self.dep_id_display_combo.currentIndexChanged.connect(
            self._update_preview)  # Connect to update preview

        self.singleton_label = QLabel(
            "No job IDs needed for singleton dependency type")
        self.singleton_label.setVisible(False)

        dep_id_layout.addWidget(self._create_label("Dependent Job IDs:"))
        dep_id_layout.addWidget(self.dep_id_display_combo)
        dep_id_layout.addWidget(self.singleton_label)

        # Add the dep_id_widget to this new group box
        delete_dep_layout.addWidget(self.dep_id_widget)

        # Add a button to remove selected dependency
        self.remove_dependency_button = QPushButton(
            "Remove Selected Dependency")
        self.remove_dependency_button.setObjectName(BTN_RED)
        self.remove_dependency_button.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "delete.svg")))
        self.remove_dependency_button.clicked.connect(
            self._remove_selected_dependency)
        delete_dep_layout.addWidget(
            self.remove_dependency_button, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.dependency_group)
        layout.addWidget(self.delete_dependency_group)  # Add the new group box
        layout.addStretch()  # Push everything to the top

        # Initial update for dependency inputs
        self._update_dependency_inputs(self.dep_type_combo.currentIndex())

    def _update_array_inputs(self, index):
        """Show/hide array inputs based on selected format"""
        if index == 0:  # Range
            self.range_widget.setVisible(True)
            self.step_widget.setVisible(False)
            self.list_widget.setVisible(False)
        elif index == 1:  # List
            self.range_widget.setVisible(False)
            self.step_widget.setVisible(False)
            self.list_widget.setVisible(True)
        elif index == 2:  # Range with step
            self.range_widget.setVisible(True)
            self.step_widget.setVisible(True)
            self.list_widget.setVisible(False)

    def _toggle_max_jobs(self, state):
        """Enable/disable max jobs spinner based on checkbox state"""
        self.max_jobs_spin.setEnabled(state)

    def _update_dependency_inputs(self, index):
        """Update dependency inputs based on selected type and refresh preview."""
        is_singleton = "singleton" in self.dep_type_combo.currentText()
        # The dep_id_display_combo is always visible, but its content (and thus the preview) changes
        # The singleton_label indicates if IDs are needed
        self.singleton_label.setVisible(is_singleton)
        if is_singleton:
            self.dep_id_display_combo.clear()  # Clear IDs if singleton is selected
            self.dep_id_display_combo.setPlaceholderText(
                "No job IDs needed for singleton dependency type")
            self.dep_id_display_combo.setEnabled(False)
            self.remove_dependency_button.setEnabled(False)
        else:
            self.dep_id_display_combo.setPlaceholderText(
                "Added job IDs will appear here")
            self.dep_id_display_combo.setEnabled(True)
            self.remove_dependency_button.setEnabled(
                self.dep_id_display_combo.count() > 0)
        self._update_preview()  # Update preview whenever dependency type changes

    def _add_selected_job_to_dependencies(self):
        """Add the selected running job ID to the dependency display QComboBox."""
        if not self.running_jobs_combo.currentText() or "No running jobs found" in self.running_jobs_combo.currentText():
            return

        # Extract job ID from the combo box text
        try:
            job_id = self.running_jobs_combo.currentText().split(' ')[0]

            # Add to the dependency display QComboBox if not already present
            if self.dep_id_display_combo.findText(job_id) == -1:
                self.dep_id_display_combo.addItem(job_id)
                self.dep_id_display_combo.setCurrentText(
                    job_id)  # Set the newly added item as current
                self.remove_dependency_button.setEnabled(
                    True)  # Enable remove button
                self._update_preview()  # Update preview after adding dependency
        except (IndexError, ValueError):
            print("Error extracting job ID from selection")

    def _remove_selected_dependency(self):
        """Remove the currently selected job ID from the dependency display QComboBox."""
        current_index = self.dep_id_display_combo.currentIndex()
        if current_index >= 0:
            self.dep_id_display_combo.removeItem(current_index)
            if self.dep_id_display_combo.count() == 0:
                self.remove_dependency_button.setEnabled(False)
            self._update_preview()  # Update preview after removing dependency

    def _refresh_running_jobs(self):
        """Refresh the list of running jobs."""
        if not self.slurm_connection or not self.slurm_connection.check_connection():
            return

        try:
            self.running_jobs = self.slurm_connection.get_running_jobs()
            self.running_jobs_combo.clear()

            if self.running_jobs:
                job_items = [
                    f"{job['Job ID']} - {job['Job Name']} ({job['Status']})" for job in self.running_jobs]
                self.running_jobs_combo.addItems(job_items)
            else:
                self.running_jobs_combo.addItem("No running jobs found")
        except Exception as e:
            print(f"Error refreshing job list: {e}")
            self.running_jobs_combo.clear()
            self.running_jobs_combo.addItem("Error fetching jobs")

    def _create_label(self, text):
        """Create a formatted label"""
        label = QLabel(text)
        label.setFont(QFont("Arial", 10))
        return label

    def _toggle_gpu_selection(self, state):
        """Enable or disable GPU selection based on checkbox state"""
        self.gpu_type_combo.setEnabled(state)
        self.gpu_count_spin.setEnabled(state)

    def _update_preview(self):
        """Update the preview of the SLURM submission script"""
        job_name = self.job_name_edit.text() or "job"
        partition = self.partition_combo.currentText()
        account = self.account_combo.currentText()
        time_limit = self.time_limit_edit.time().toString("HH:mm:ss")
        nodes = self.nodes_spin.value()
        cpus_per_task = self.cpu_per_task_spin.value()

        # Get selected constraints from the custom CheckableComboBox
        selected_constraints = self.constraint_combo.get_checked_items()
        constraint = "|".join(
            selected_constraints) if selected_constraints else None

        qos = self.qos_combo.currentText()
        if qos == "None":
            qos = None

        gres = None
        if self.gpu_check.isChecked():
            gpu_type = self.gpu_type_combo.currentText()
            gpu_count = self.gpu_count_spin.value()
            if gpu_type == "any":
                gres = f"gpu:{gpu_count}"
            else:
                gres = f"gpu:{gpu_type}:{gpu_count}"

        memory = str(self.memory_spin.value()) + \
            self.memory_unit_combo.currentText().lower()

        output_file = self.output_file_edit.text()
        error_file = self.error_file_edit.text()

        working_dir = self.working_dir_edit.text()

        command = self.command_text.toPlainText()

        # Create SLURM script preview
        script_lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name={job_name}",
            f"#SBATCH --partition={partition}",
            f"#SBATCH --time={time_limit}",
            f"#SBATCH --nodes={nodes}",
        ]

        # Add CPU cores per task if more than 1
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

        # Add job array if enabled
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

                # Add max simultaneous jobs if enabled
                if self.max_jobs_check.isChecked():
                    max_jobs = self.max_jobs_spin.value()
                    # Update the array line to include the limit
                    script_lines[-1] += f"%{max_jobs}"

        # Add dependencies if job IDs are selected or singleton is chosen
        dep_type = self.dep_type_combo.currentText().split(" - ")[0].strip()

        # Get all selected dependency IDs from the display combo box
        dep_ids = [self.dep_id_display_combo.itemText(
            i) for i in range(self.dep_id_display_combo.count())]
        dep_ids_str = ":".join(dep_ids)

        if dep_type == "singleton":
            # Only add if singleton is selected
            script_lines.append(f"#SBATCH --dependency={dep_type}")
        elif dep_ids_str:  # Check if there are any IDs
            # Only add if dep_ids_str has content for non-singleton types
            script_lines.append(
                f"#SBATCH --dependency={dep_type}:{dep_ids_str}")

        # Add working directory
        if working_dir:
            script_lines.append(f"\ncd {working_dir}")

        # Add array job environment info if enabled
        if self.array_group.isChecked():
            script_lines.append("\n# Job array information")
            script_lines.append(
                "echo \"Running array job ${SLURM_ARRAY_JOB_ID}, task ID ${SLURM_ARRAY_TASK_ID}\"")
            script_lines.append("")

        script_lines.append("# Job command")
        script_lines.append(command)

        preview_text = "\n".join(script_lines)
        self.preview_text.setText(preview_text)

        # Highlight the preview text for better readability
        self.preview_text.setStyleSheet(f"""
            background-color: #282a36;
            color: #f8f8f2;
            font-family: monospace;
            padding: 10px;
            border: 1px solid {COLOR_DARK_BORDER};
            selection-background-color: {COLOR_BLUE};
        """)

    def get_job_details(self):
        """Return the full job details needed for submission"""
        job_name = self.job_name_edit.text()
        partition = self.partition_combo.currentText()
        account = self.account_combo.currentText()
        time_limit = self.time_limit_edit.time().toString("HH:mm:ss")
        nodes = self.nodes_spin.value()
        cpus_per_task = self.cpu_per_task_spin.value()

        # Get selected constraints from the custom CheckableComboBox
        selected_constraints = self.constraint_combo.get_checked_items()
        constraint = "|".join(
            selected_constraints) if selected_constraints else None

        qos = self.qos_combo.currentText()
        if qos == "None":
            qos = None

        gres = None
        if self.gpu_check.isChecked():
            gpu_type = self.gpu_type_combo.currentText()
            gpu_count = self.gpu_count_spin.value()
            if gpu_type == "any":
                gres = f"gpu:{gpu_count}"
            else:
                gres = f"gpu:{gpu_type}:{gpu_count}"

        output_file = self.output_file_edit.text()
        error_file = self.error_file_edit.text()

        command = self.command_text.toPlainText()
        working_dir = self.working_dir_edit.text()

        # Build the result dictionary
        result = {
            "job_name": job_name,
            "partition": partition,
            "time_limit": time_limit,
            "command": command,
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

        # Job array settings
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

                # Add max simultaneous jobs if enabled
                if self.max_jobs_check.isChecked():
                    max_jobs = self.max_jobs_spin.value()
                    result["array_max_jobs"] = max_jobs

        # Dependencies
        dep_type = self.dep_type_combo.currentText().split(" - ")[0].strip()
        dep_ids = [self.dep_id_display_combo.itemText(
            i) for i in range(self.dep_id_display_combo.count())]
        dep_ids_str = ":".join(dep_ids)

        if dep_type == "singleton":
            result["dependency"] = "singleton"
        elif dep_ids_str:
            result["dependency"] = f"{dep_type}:{dep_ids_str}"
            
        discord_settings = {
            "enabled": False,
            "notify_queued": True,
            "notify_start": True, 
            "notify_complete": True,
            "notify_failed": True,
            "message_prefix": f"[{self.selected_project}]"
        }
        
        # Only collect Discord settings if tab exists and is configured
        if hasattr(self, 'discord_notifications_check'):
            discord_settings["enabled"] = self.discord_notifications_check.isChecked()
            
            if discord_settings["enabled"]:
                # Get individual notification preferences
                discord_settings.update({
                    "notify_queued": getattr(self, 'notify_job_queued', self.discord_options_widget.findChild(QCheckBox)).isChecked(),
                    "notify_start": getattr(self, 'notify_job_start', self.discord_options_widget.findChild(QCheckBox)).isChecked(),
                    "notify_complete": getattr(self, 'notify_job_complete', self.discord_options_widget.findChild(QCheckBox)).isChecked(),
                    "notify_failed": getattr(self, 'notify_job_failed', self.discord_options_widget.findChild(QCheckBox)).isChecked(),
                    "message_prefix": self.custom_message_prefix.text().strip() or f"[{self.selected_project}]"
                })
        
        result["discord_notifications"] = discord_settings
        
        print(f"[DEBUG] Storing Discord settings: {discord_settings}")
        return result

    def _browse_working_dir(self):
        """Open a dialog to select working directory from the SLURM cluster."""
        if not self.slurm_connection or not self.slurm_connection.check_connection():
            show_warning_toast(self, "SLURM Connection Error",
                               "Not connected to SLURM. Cannot browse remote directories.")
            return

        initial_path = self.working_dir_edit.text()
        # Fallback to user's home or root if current path is invalid/empty
        if not initial_path or not self.slurm_connection.remote_path_exists(initial_path):
            if self.slurm_connection.remote_home and self.slurm_connection.remote_path_exists(self.slurm_connection.remote_home):
                initial_path = self.slurm_connection.remote_home
            else:
                initial_path = "/"  # Fallback to root if home is not accessible

        dialog = RemoteDirectoryDialog(
            self.slurm_connection, initial_path=initial_path, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_directory = dialog.get_selected_directory()
            if selected_directory:
                self.working_dir_edit.setText(selected_directory)
                self._update_preview()  # Update preview after changing working directory

    def _check_discord_webhook_availability(self):
        """Check if Discord webhook is configured and available"""
        try:
            settings = QSettings(
                str(Path("./configs/settings.ini")), QSettings.Format.IniFormat)
            settings.beginGroup("NotificationSettings")

            discord_enabled = settings.value(
                "discord_enabled", False, type=bool)
            discord_webhook_url = settings.value(
                "discord_webhook_url", "", type=str)

            settings.endGroup()

            # Return True if Discord is enabled AND webhook URL is not empty
            return discord_enabled and bool(discord_webhook_url.strip())

        except Exception as e:
            print(f"Error checking Discord webhook availability: {e}")
            return False

    def _setup_notifications_tab(self):
        """Set up simplified and reliable notifications tab"""
        layout = QVBoxLayout(self.notifications_tab)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title_label = QLabel("Discord Notifications")
        title_label.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {COLOR_DARK_FG}; margin-bottom: 15px;")
        layout.addWidget(title_label)

        # Status check
        discord_status = self._check_discord_configuration()
        if not discord_status["configured"]:
            warning_label = QLabel("⚠️ Discord notifications are not configured in settings.")
            warning_label.setStyleSheet(f"color: {COLOR_ORANGE}; font-size: 12px; margin-bottom: 15px;")
            layout.addWidget(warning_label)

        # Main enable checkbox - ALWAYS visible
        self.discord_notifications_check = QCheckBox("Enable Discord notifications for this job")
        self.discord_notifications_check.setChecked(discord_status["configured"])  # Default to enabled if configured
        self.discord_notifications_check.setFont(QFont("Inter", 13))
        self.discord_notifications_check.setStyleSheet(f"""
            QCheckBox {{
                color: {COLOR_DARK_FG};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 2px solid {COLOR_DARK_BORDER};
                border-radius: 3px;
                background-color: {COLOR_DARK_BG_ALT};
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLOR_GREEN};
                border: 2px solid {COLOR_GREEN};
            }}
        """)
        self.discord_notifications_check.stateChanged.connect(self._toggle_discord_options)
        layout.addWidget(self.discord_notifications_check)

        # Notification options container
        self.discord_options_widget = QWidget()
        options_layout = QVBoxLayout(self.discord_options_widget)
        options_layout.setContentsMargins(20, 15, 0, 0)
        options_layout.setSpacing(12)

        # Simplified notification options - fewer checkboxes, clearer names
        notification_options = [
            ("notify_job_queued", "📥 When job enters queue (PENDING)", True),
            ("notify_job_start", "🏃 When job starts running", True),
            ("notify_job_complete", "✅ When job completes successfully", True),
            ("notify_job_failed", "❌ When job fails or is cancelled", True),
        ]

        for attr_name, label, default in notification_options:
            checkbox = QCheckBox(label)
            checkbox.setChecked(default)
            checkbox.setFont(QFont("Inter", 11))
            checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: {COLOR_DARK_FG};
                    spacing: 6px;
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 1px solid {COLOR_DARK_BORDER};
                    border-radius: 2px;
                    background-color: {COLOR_DARK_BG_ALT};
                }}
                QCheckBox::indicator:checked {{
                    background-color: {COLOR_GREEN};
                    border: 1px solid {COLOR_GREEN};
                }}
            """)
            setattr(self, attr_name, checkbox)
            options_layout.addWidget(checkbox)

        layout.addWidget(self.discord_options_widget)

        # Message prefix
        prefix_layout = QHBoxLayout()
        prefix_layout.setSpacing(10)
        
        prefix_label = QLabel("Message prefix:")
        prefix_label.setFont(QFont("Inter", 11))
        prefix_label.setStyleSheet(f"color: {COLOR_DARK_FG};")
        
        self.custom_message_prefix = QLineEdit()
        self.custom_message_prefix.setPlaceholderText(f"[{self.selected_project}]")
        self.custom_message_prefix.setText(f"[{self.selected_project}]")
        self.custom_message_prefix.setMaximumWidth(250)
        self.custom_message_prefix.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLOR_DARK_BG_ALT};
                border: 1px solid {COLOR_DARK_BORDER};
                border-radius: 4px;
                padding: 8px;
                font-size: 11px;
                color: {COLOR_DARK_FG};
            }}
            QLineEdit:focus {{
                border: 1px solid {COLOR_BLUE};
            }}
        """)
        
        prefix_layout.addWidget(prefix_label)
        prefix_layout.addWidget(self.custom_message_prefix)
        prefix_layout.addStretch()
        
        layout.addLayout(prefix_layout)

        layout.addStretch()

        # Set initial state
        self._toggle_discord_options(self.discord_notifications_check.isChecked())

    def _check_discord_configuration(self):
        """Check if Discord is properly configured"""
        try:
            settings = QSettings(str(Path("./configs/settings.ini")), QSettings.Format.IniFormat)
            settings.beginGroup("NotificationSettings")
            
            enabled = settings.value("discord_enabled", False, type=bool)
            webhook_url = settings.value("discord_webhook_url", "", type=str)
            
            settings.endGroup()
            
            return {
                "configured": enabled and bool(webhook_url.strip()),
                "enabled": enabled,
                "webhook_url": webhook_url
            }
        except Exception:
            return {"configured": False, "enabled": False, "webhook_url": ""}

    def _toggle_discord_options(self, state):
        """Enable/disable Discord notification options"""
        # Handle both boolean and Qt.CheckState
        if hasattr(state, 'value'):
            enabled = state == Qt.CheckState.Checked
        else:
            enabled = bool(state)
        
        self.discord_options_widget.setEnabled(enabled)
        self.test_notification_btn.setEnabled(enabled)
        
        # Visual feedback
        opacity = "1.0" if enabled else "0.4"
        self.discord_options_widget.setStyleSheet(f"QWidget {{ opacity: {opacity}; }}")

    def _send_test_notification(self):
        """Send a test Discord notification"""
        try:
            from modules.discord_manager import discord_manager
            
            if not discord_manager.is_configured():
                show_warning_toast(self, "Not Configured", "Discord notifications are not configured in settings.")
                return
            
            # Create test job settings
            test_settings = {
                "enabled": True,
                "message_prefix": self.custom_message_prefix.text() or f"[{self.selected_project}]"
            }
            
            success = discord_manager.send_notification(
                project_name=self.selected_project,
                job_id="TEST",
                job_name="Test Notification",
                old_status="",
                new_status="COMPLETED",
                job_settings=test_settings
            )
            
            if success:
                show_success_toast(self, "Test Sent", "Discord test notification sent successfully!")
            else:
                show_error_toast(self, "Test Failed", "Failed to send Discord test notification.")
                
        except Exception as e:
            show_error_toast(self, "Error", f"Error sending test notification: {str(e)}")


class ModifyJobDialog(NewJobDialog):
    """
    Dialog for modifying existing job parameters.
    Inherits from NewJobDialog and pre-fills fields with existing job data.
    """

    def __init__(self, job, project_name, slurm_connection=None, parent=None):
        self.job = job
        self.project_name = project_name

        # Call parent constructor but override the window title
        super().__init__(project_name, slurm_connection, parent)

        # Update window title and header
        self.setWindowTitle(f"Modify Job: {job.name}")
        self._update_header_for_modify()

        # Pre-fill all fields with existing job data
        self._populate_fields_from_job()

    def _update_header_for_modify(self):
        """Update the dialog header to reflect modify mode"""
        # Find and update the header label
        for i in range(self.main_layout.count()):
            item = self.main_layout.itemAt(i)
            if item and item.layout():
                layout = item.layout()
                for j in range(layout.count()):
                    widget = layout.itemAt(j).widget()
                    if isinstance(widget, QLabel) and "New Job for Project" in widget.text():
                        widget.setText(f"Modify Job: {self.job.name}")
                        widget.setStyleSheet(
                            f"color: {COLOR_ORANGE}; font-size: 14px; font-weight: bold;")
                        break

        # Update the create button text and icon
        self.create_button.setText("Save Changes")
        self.create_button.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "ok.svg")))

    def _populate_fields_from_job(self):
        """Pre-fill all dialog fields with data from the existing job"""

        # Essential tab fields
        if self.job.name:
            self.job_name_edit.setText(self.job.name)

        if self.job.partition:
            index = self.partition_combo.findText(self.job.partition)
            if index >= 0:
                self.partition_combo.setCurrentIndex(index)

        if self.job.account:
            index = self.account_combo.findText(self.job.account)
            if index >= 0:
                self.account_combo.setCurrentIndex(index)

        if self.job.time_limit:
            try:
                # Parse time limit string (HH:MM:SS format)
                time_parts = self.job.time_limit.split(':')
                if len(time_parts) == 3:
                    hours, minutes, seconds = map(int, time_parts)
                    time = QTime(hours, minutes, seconds)
                    self.time_limit_edit.setTime(time)
            except (ValueError, AttributeError):
                pass

        if self.job.nodes:
            self.nodes_spin.setValue(self.job.nodes)

        if self.job.cpus:
            self.cpu_per_task_spin.setValue(self.job.cpus)

        # Parse memory
        if self.job.memory:
            try:
                memory_str = self.job.memory.upper()
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

        # Advanced tab fields
        if self.job.constraints:
            # Handle constraints - need to check items in the CheckableComboBox
            constraints_str = self.job.constraints.strip(
                '"') if self.job.constraints else ""
            if constraints_str:
                constraints = constraints_str.split('|')
                for i in range(self.constraint_combo.model.rowCount()):
                    item = self.constraint_combo.model.item(i)
                    if item and item.text() in constraints:
                        item.setCheckState(Qt.CheckState.Checked)
                self.constraint_combo._update_selected_text()

        if self.job.qos:
            index = self.qos_combo.findText(self.job.qos)
            if index >= 0:
                self.qos_combo.setCurrentIndex(index)
            else:
                # If QoS not in list, set to "None"
                none_index = self.qos_combo.findText("None")
                if none_index >= 0:
                    self.qos_combo.setCurrentIndex(none_index)

        # GPU settings
        if self.job.gres and "gpu" in self.job.gres.lower():
            self.gpu_check.setChecked(True)
            self._toggle_gpu_selection(True)

            try:
                # Parse GPU specification (e.g., "gpu:rtx5000:2" or "gpu:2")
                gpu_parts = self.job.gres.split(':')
                if len(gpu_parts) == 2:  # gpu:count
                    gpu_count = int(gpu_parts[1])
                    self.gpu_type_combo.setCurrentText("any")
                    self.gpu_count_spin.setValue(gpu_count)
                elif len(gpu_parts) == 3:  # gpu:type:count
                    gpu_type = gpu_parts[1]
                    gpu_count = int(gpu_parts[2])
                    type_index = self.gpu_type_combo.findText(gpu_type)
                    if type_index >= 0:
                        self.gpu_type_combo.setCurrentIndex(type_index)
                    self.gpu_count_spin.setValue(gpu_count)
            except (ValueError, IndexError, AttributeError):
                pass

        if self.job.output_file:
            self.output_file_edit.setText(self.job.output_file)

        if self.job.error_file:
            self.error_file_edit.setText(self.job.error_file)

        if self.job.working_dir:
            self.working_dir_edit.setText(self.job.working_dir)

        # Command tab
        if self.job.command:
            self.command_text.setPlainText(self.job.command)

        # Job Array tab
        if self.job.array_spec:
            self.array_group.setChecked(True)

            # Parse array specification
            array_spec = self.job.array_spec
            if '-' in array_spec and ':' in array_spec:
                # Range with step (e.g., "1-10:2")
                self.array_format_combo.setCurrentIndex(2)  # Range with step
                try:
                    range_part, step = array_spec.split(':')
                    start, end = range_part.split('-')
                    self.array_start_spin.setValue(int(start))
                    self.array_end_spin.setValue(int(end))
                    self.array_step_spin.setValue(int(step))
                except ValueError:
                    pass
            elif '-' in array_spec:
                # Simple range (e.g., "1-10")
                self.array_format_combo.setCurrentIndex(0)  # Range
                try:
                    start, end = array_spec.split('-')
                    self.array_start_spin.setValue(int(start))
                    self.array_end_spin.setValue(int(end))
                except ValueError:
                    pass
            else:
                # Assume it's a list format
                self.array_format_combo.setCurrentIndex(1)  # List
                self.array_list_edit.setText(array_spec)

            self._update_array_inputs(self.array_format_combo.currentIndex())

            # Set max concurrent jobs if specified
            if self.job.array_max_jobs:
                self.max_jobs_check.setChecked(True)
                self.max_jobs_spin.setValue(self.job.array_max_jobs)
                self._toggle_max_jobs(True)

        # Dependencies tab
        if self.job.dependency:
            dep_parts = self.job.dependency.split(':')
            if len(dep_parts) >= 1:
                dep_type = dep_parts[0]

                # Find matching dependency type in combo
                for i in range(self.dep_type_combo.count()):
                    item_text = self.dep_type_combo.itemText(i)
                    if item_text.startswith(dep_type):
                        self.dep_type_combo.setCurrentIndex(i)
                        break

                # Add job IDs if not singleton
                if dep_type != "singleton" and len(dep_parts) > 1:
                    job_ids = dep_parts[1].split(
                        ',') if len(dep_parts) > 1 else []
                    for job_id in job_ids:
                        if job_id.strip():
                            self.dep_id_display_combo.addItem(job_id.strip())

        # Update the preview after populating all fields
        self._update_preview()

    def get_job_details(self):
        """
        Override to return modified job details.
        This method is called when the user clicks "Save Changes"
        """
        # Get the base job details from parent class
        details = super().get_job_details()

        # Add any additional information needed for modification
        details["original_job_id"] = self.job.id
        details["is_modification"] = True

        return details
