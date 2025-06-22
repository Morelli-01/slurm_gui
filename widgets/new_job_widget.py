"""
Job Creation Dialog - Simple tabbed interface for creating SLURM jobs
"""


from models.project_model import Job
from core.defaults import *
from core.style import AppStyles
from core.slurm_api import ConnectionState, SlurmAPI
import uuid
import copy

from widgets.remote_directory_widget import RemoteDirectoryDialog
from widgets.toast_widget import show_warning_toast


class ConstraintDialog(QDialog):
    def __init__(self, constraints, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Constraints")
        self.setMinimumWidth(350)
        self.selected = set(selected)
        layout = QVBoxLayout(self)
        self.checkboxes = []
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        vbox = QVBoxLayout(content)
        for c in constraints:
            cb = QCheckBox(c)
            if c in self.selected:
                cb.setChecked(True)
            vbox.addWidget(cb)
            self.checkboxes.append(cb)
        content.setLayout(vbox)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
    def get_selected(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]


class JobCreationDialog(QDialog):
    """Dialog for creating a new SLURM job with tabbed interface"""
    
    def __init__(self, parent=None, project_name=None, job_to_modify=None, cached_job=None):
        super().__init__(parent)
        self.project_name = project_name
        self.job_to_modify = job_to_modify
        
        if job_to_modify:
            self.setWindowTitle("Modify Job")
            self.job = job_to_modify
        else:
            self.setWindowTitle("Create New Job")
            if cached_job:
                self.job = copy.deepcopy(cached_job)
                self.job.name = f"{self.job.name}_new"
                self.job.dependency = None
            else:
                self.job = Job()
            self.job.id = uuid.uuid4().hex[:8].capitalize()

        self.setModal(True)
        self.setMinimumSize(700, 600)
        self.slurm_api = SlurmAPI()
        # Apply dark theme
        self.setStyleSheet(AppStyles.get_complete_stylesheet(THEME_DARK))
            
        self._setup_ui()
        self._populate_fields_from_job()
        self._connect_signals()
        if not self.job_to_modify:
            self.account_edit.setCurrentIndex(0)
            self.partition_edit.setCurrentIndex(0)
        self._update_job()
        self._update_preview()
        
    def _setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel(self.windowTitle())
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Create tabs
        self._create_basic_tab()
        self._create_resources_tab()
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
        
        self.nodes_spin = QSpinBox()
        self.nodes_spin.setMinimum(1)
        self.nodes_spin.setMaximum(1000)
        self.nodes_spin.setValue(int(self.job.nodes) if hasattr(self.job, 'nodes') and str(self.job.nodes).isdigit() else 1)
        cpu_layout.addRow("Nodes:", self.nodes_spin)
        
        layout.addWidget(cpu_group)
        
        # Memory
        mem_group = QGroupBox("Memory")
        mem_layout = QFormLayout(mem_group)
        
        self.mem_spin = QSpinBox()
        self.mem_spin.setMinimum(1)
        self.mem_spin.setMaximum(1024*1024)  # up to 1TB in GB
        self.mem_spin.setValue(int(self.job.mem[:-1]) if hasattr(self.job, 'mem') and isinstance(self.job.mem, str) and self.job.mem[:-1].isdigit() else 1)
        mem_layout.addRow("Memory (GB):", self.mem_spin)
        
        layout.addWidget(mem_group)
        
        # GPU resources
        gpu_group = QGroupBox("GPU Resources")
        gpu_layout = QFormLayout(gpu_group)
        
        self.gpus_spin = QSpinBox()
        self.gpus_spin.setMinimum(0)
        self.gpus_spin.setMaximum(128)
        self.gpus_spin.setValue(int(self.job.gpus) if hasattr(self.job, 'gpus') and str(self.job.gpus).isdigit() else 0)
        gpu_layout.addRow("GPUs:", self.gpus_spin)
        
        self.gpus_per_task_spin = QSpinBox()
        self.gpus_per_task_spin.setMinimum(0)
        self.gpus_per_task_spin.setMaximum(128)
        self.gpus_per_task_spin.setValue(int(self.job.gpus_per_task) if hasattr(self.job, 'gpus_per_task') and str(self.job.gpus_per_task).isdigit() else 0)
        gpu_layout.addRow("GPUs per Task:", self.gpus_per_task_spin)
        
        layout.addWidget(gpu_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Resources")
        
    def _create_dependencies_tab(self):
        """Create the dependencies and arrays tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # Job Arrays
        self.array_group = QGroupBox("Job Arrays")
        self.array_group.setCheckable(True)
        self.array_group.setChecked(False)
        array_layout = QFormLayout(self.array_group)
        array_layout.setSpacing(10)

        self.array_start_spin = QSpinBox()
        self.array_start_spin.setRange(0, 999999)
        self.array_start_spin.setValue(1)
        array_layout.addRow("Start Index:", self.array_start_spin)

        self.array_end_spin = QSpinBox()
        self.array_end_spin.setRange(0, 999999)
        self.array_end_spin.setValue(10)
        array_layout.addRow("End Index:", self.array_end_spin)

        self.array_step_spin = QSpinBox()
        self.array_step_spin.setRange(1, 999999)
        self.array_step_spin.setValue(1)
        array_layout.addRow("Step:", self.array_step_spin)

        self.array_concurrency_spin = QSpinBox()
        self.array_concurrency_spin.setRange(0, 1024)
        self.array_concurrency_spin.setValue(0)
        self.array_concurrency_spin.setToolTip("Maximum number of tasks to run at once (0 for no limit)")
        array_layout.addRow("Concurrency Limit (%):", self.array_concurrency_spin)
        
        layout.addWidget(self.array_group)
        
        # Job Dependencies
        dep_group = QGroupBox("Job Dependencies")
        dep_layout = QFormLayout(dep_group)
        
        self.dep_type_combo = QComboBox()
        self.dep_type_combo.addItems(["", "afterok", "afterany", "afternotok", "singleton"])
        dep_layout.addRow("Dependency Type:", self.dep_type_combo)

        self.dep_job_list = QListWidget()
        self.dep_job_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.dep_job_list.setMaximumHeight(150)
        dep_layout.addRow("On Jobs:", self.dep_job_list)
        
        self._load_user_jobs()
        layout.addWidget(dep_group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Dependencies & Arrays")

    def _load_user_jobs(self):
        """Fetches the user's jobs and populates the dependency list."""
        if self.slurm_api.connection_status != ConnectionState.CONNECTED:
            self.dep_job_list.addItem("Not connected to Slurm")
            self.dep_job_list.setEnabled(False)
            return

        try:
            all_jobs = self.slurm_api.fetch_job_queue()
            current_user = self.slurm_api._config.username
            user_jobs = [j for j in all_jobs if j.get('User') == current_user]

            if not user_jobs:
                self.dep_job_list.addItem("No running/pending jobs found for user")
                self.dep_job_list.setEnabled(False)
                return

            for job in user_jobs:
                job_id = job.get("Job ID")
                job_name = job.get("Job Name", "unnamed")
                item = QListWidgetItem(f"{job_name} ({job_id})")
                item.setData(Qt.ItemDataRole.UserRole, job_id)
                self.dep_job_list.addItem(item)
        except Exception as e:
            self.dep_job_list.addItem("Error fetching jobs")
            self.dep_job_list.setEnabled(False)
            print(f"Error fetching user jobs for dependency list: {e}")

    def _create_advanced_tab(self):
        """Create the advanced settings tab"""
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setSpacing(10)
        
        # QoS
        self.qos_edit = QComboBox()
        self.qos_edit.setEditable(True)
        qos_list = self.slurm_api.fetch_qos() if self.slurm_api.connection_status == ConnectionState.CONNECTED else []
        if qos_list:
            self.qos_edit.addItem("")  # Ensure first item is blank
            self.qos_edit.addItems(qos_list)
        self.qos_edit.setCurrentIndex(-1)  # No selection
        self.qos_edit.setPlaceholderText("Quality of Service")

        layout.addRow("QoS:", self.qos_edit)
        
        # Constraint (custom dialog)
        self.constraint_btn = QPushButton("Select Constraints")
        self.constraint_btn.clicked.connect(self._open_constraint_dialog)
        self.constraint_summary = QLabel()
        self.constraint_summary.setStyleSheet("color: #8be9fd; font-style: italic;")
        self._update_constraint_summary()
        constraint_layout = QVBoxLayout()
        constraint_layout.addWidget(self.constraint_btn)
        constraint_layout.addWidget(self.constraint_summary)
        constraint_frame = QFrame()
        constraint_frame.setLayout(constraint_layout)
        layout.addRow("Constraint(s):", constraint_frame)
        self._all_constraints = self.slurm_api.fetch_constraint() if self.slurm_api.connection_status == ConnectionState.CONNECTED else []
        
        # Nodelist
        self.nodelist_edit = QComboBox()
        self.nodelist_edit.setEditable(True)
        nodelist_list = self.slurm_api.fetch_nodelist() if self.slurm_api.connection_status == ConnectionState.CONNECTED else []
        if nodelist_list:
            self.nodelist_edit.addItem("")  # Ensure no default selection
            self.nodelist_edit.addItems(nodelist_list)
        self.nodelist_edit.setCurrentIndex(-1)
        self.nodelist_edit.setPlaceholderText("e.g., node001, node[001-004], node00[1,3,5]")
        layout.addRow("Nodelist:", self.nodelist_edit)
        
        # Output file
        self.output_edit = QLineEdit(self.job.output_file or f"{self.slurm_api.remote_home}/.slurm_logs/out_%A.log")
        self.output_edit.setPlaceholderText(f"e.g., {self.slurm_api.remote_home}/.slurm_logs/out_%A.log")
        layout.addRow("Output File:", self.output_edit)
        
        # Error file
        self.error_edit = QLineEdit(self.job.error_file or f"{self.slurm_api.remote_home}/.slurm_logs/err_%A.log")
        self.error_edit.setPlaceholderText(f"e.g., {self.slurm_api.remote_home}/.slurm_logs/err_%A.log")
        layout.addRow("Error File:", self.error_edit)
        
        # Nice
        self.nice_spin = QSpinBox()
        self.nice_spin.setValue(self.job.nice or 0)
        layout.addRow("Nice:", self.nice_spin)
        
        # Oversubscribe
        self.oversubscribe_check = QCheckBox("Allow Oversubscribe")
        self.oversubscribe_check.setChecked(self.job.oversubscribe)
        layout.addRow(self.oversubscribe_check)
        
        # Discord Notifications
        self.discord_notify_check = QCheckBox("Enable Discord Notifications")
        self.discord_notify_check.setChecked(self.job.discord_notifications)
        layout.addRow(self.discord_notify_check)
        
        # Optional sbatch options
        layout.addRow(QLabel("Additional SBATCH Options:"))
        self.optional_sbatch_edit = QTextEdit()
        self.optional_sbatch_edit.setPlainText(self.job.optional_sbatch or "")
        self.optional_sbatch_edit.setMaximumHeight(100)
        self.optional_sbatch_edit.setPlaceholderText("#SBATCH --option=value")
        font = QFont("Consolas" if os.name == 'nt' else "Monospace", 10)
        self.optional_sbatch_edit.setFont(font)
        layout.addRow(self.optional_sbatch_edit)
        
        self.tab_widget.addTab(tab, "Advanced")
        
    def _open_constraint_dialog(self):
        dlg = ConstraintDialog(self._all_constraints, self.job.constraint or [], self)
        if dlg.exec():
            selected = dlg.get_selected()
            self.job.constraint = selected if selected else None
            self._update_constraint_summary()
            self._update_job()
            self._update_preview()
            
    def _update_constraint_summary(self):
        if self.job.constraint:
            self.constraint_summary.setText(", ".join(self.job.constraint))
        else:
            self.constraint_summary.setText("No constraints selected")
        
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
        self.name_edit.textChanged.connect(self._handle_input_change)
        self.account_edit.currentTextChanged.connect(self._handle_input_change)
        self.partition_edit.currentTextChanged.connect(self._handle_input_change)
        self.working_dir_edit.textChanged.connect(self._handle_input_change)
        self.venv_edit.textChanged.connect(self._handle_input_change)
        self.script_edit.textChanged.connect(self._handle_input_change)
        
        # Resources tab
        self.cpus_spin.valueChanged.connect(self._handle_input_change)
        self.ntasks_spin.valueChanged.connect(self._handle_input_change)
        self.nodes_spin.valueChanged.connect(self._handle_input_change)
        self.mem_spin.valueChanged.connect(self._handle_input_change)
        self.gpus_spin.valueChanged.connect(self._handle_input_change)
        self.gpus_per_task_spin.valueChanged.connect(self._handle_input_change)
        
        # Dependencies & Arrays tab
        self.array_group.toggled.connect(self._handle_input_change)
        self.array_start_spin.valueChanged.connect(self._handle_input_change)
        self.array_end_spin.valueChanged.connect(self._handle_input_change)
        self.array_step_spin.valueChanged.connect(self._handle_input_change)
        self.array_concurrency_spin.valueChanged.connect(self._handle_input_change)
        self.dep_type_combo.currentTextChanged.connect(self._handle_input_change)
        self.dep_job_list.itemSelectionChanged.connect(self._handle_input_change)
        
        # Advanced tab
        self.qos_edit.editTextChanged.connect(self._handle_input_change)
        self.nodelist_edit.editTextChanged.connect(self._handle_input_change)
        self.nice_spin.valueChanged.connect(self._handle_input_change)
        self.oversubscribe_check.stateChanged.connect(self._handle_input_change)
        self.discord_notify_check.stateChanged.connect(self._handle_input_change)
        self.optional_sbatch_edit.textChanged.connect(self._handle_input_change)
        
        # Update preview when switching to preview tab
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        
    def _handle_input_change(self, *args):
        """Called when any input value changes to update the job and preview."""
        self._update_job()
        # If the user is currently looking at the preview, refresh it.
        if self.tab_widget.currentIndex() == 4: # Preview tab index
            self._update_preview()

    def _update_job(self):
        """Update the job object from UI inputs. This method ONLY updates the object."""
        # Basic
        self.job.name = self.name_edit.text() or "new_job"
        self.job.working_directory = self.working_dir_edit.text() or None
        self.job.venv = self.venv_edit.text() or None
        self.job.script_commands = self.script_edit.toPlainText()
        # Resources
        self.job.cpus_per_task = self.cpus_spin.value()
        self.job.ntasks = self.ntasks_spin.value()
        self.job.nodes = self.nodes_spin.value()
        self.job.mem = f"{self.mem_spin.value()}G"
        self.job.gpus = str(self.gpus_spin.value()) if self.gpus_spin.value() > 0 else None
        self.job.gpus_per_task = str(self.gpus_per_task_spin.value()) if self.gpus_per_task_spin.value() > 0 else None
        # Files
        self.job.output_file = self.output_edit.text() or f"{self.slurm_api.remote_home}/.slurm_logs/out_%A.log"
        self.job.error_file = self.error_edit.text() or f"{self.slurm_api.remote_home}/.slurm_logs/err_%A.log"
        # Advanced
        self.job.account = self.account_edit.currentText() or None
        self.job.partition = self.partition_edit.currentText() or None
        qos_val = self.qos_edit.currentText().strip()
        self.job.qos = qos_val if qos_val else None
        nodelist_val = self.nodelist_edit.currentText().strip()
        self.job.nodelist = nodelist_val if nodelist_val else None
        
        # Job Array
        if self.array_group.isChecked():
            start = self.array_start_spin.value()
            end = self.array_end_spin.value()
            step = self.array_step_spin.value()
            limit = self.array_concurrency_spin.value()

            if start > end:
                self.array_end_spin.setValue(start)
                end = start
            
            array_spec = f"{start}-{end}"
            
            if step > 1:
                array_spec += f":{step}"
                
            if limit > 0:
                array_spec += f"%{limit}"
                
            self.job.array = array_spec
        else:
            self.job.array = None

        # Job Dependency
        dep_type = self.dep_type_combo.currentText()
        is_singleton = (dep_type == 'singleton')
        self.dep_job_list.setEnabled(not is_singleton)

        if not dep_type:
            self.job.dependency = None
        elif is_singleton:
            self.job.dependency = 'singleton'
            self.dep_job_list.blockSignals(True)
            self.dep_job_list.clearSelection()
            self.dep_job_list.blockSignals(False)
        else:
            selected_items = self.dep_job_list.selectedItems()
            if not selected_items:
                self.job.dependency = None
            else:
                job_ids = [str(item.data(Qt.ItemDataRole.UserRole)) for item in selected_items]
                self.job.dependency = f"{dep_type}:{':'.join(job_ids)}"

        self.job.nice = self.nice_spin.value() if self.nice_spin.value() != 0 else None
        self.job.oversubscribe = self.oversubscribe_check.isChecked()
        self.job.discord_notifications = self.discord_notify_check.isChecked()
        self.job.optional_sbatch = self.optional_sbatch_edit.toPlainText() or None

    def _on_tab_changed(self, index):
        """Handle tab change"""
        if index == 4:  # Preview tab is now at index 4
            self._update_job()
            self._update_preview()
            
    def _update_preview(self):
        """Update the script preview from the self.job object."""
        script = self.job.create_sbatch_script()
        self.preview_text.setPlainText(script)
        
    def _browse_directory(self):
        """Browse for working directory on the remote cluster."""
        if self.slurm_api.connection_status != ConnectionState.CONNECTED:
            show_warning_toast(self, "Connection Required", "Please connect to the cluster first.")
            return

        initial_path = self.working_dir_edit.text() or self.slurm_api.remote_home or "/"
        
        dialog = RemoteDirectoryDialog(
            initial_path=initial_path,
            parent=self
        )
        if dialog.exec():
            directory = dialog.get_selected_directory()
            if directory:
                self.working_dir_edit.setText(directory)
            
    def _browse_venv(self):
        """Browse for virtual environment on the remote cluster."""
        if self.slurm_api.connection_status != ConnectionState.CONNECTED:
            show_warning_toast(self, "Connection Required", "Please connect to the cluster first.")
            return

        initial_path = self.venv_edit.text() or self.slurm_api.remote_home or "/"

        dialog = RemoteDirectoryDialog(
            initial_path=initial_path,
            parent=self
        )
        if dialog.exec():
            directory = dialog.get_selected_directory()
            if directory:
                # Check for bin/activate in the selected directory (remote)
                activate_path = os.path.join(directory, "bin", "activate")
                exists = False
                try:
                    exists = self.slurm_api.remote_file_exists(activate_path)
                except Exception:
                    exists = False
                if not exists:
                    show_warning_toast(
                        self,
                        "Virtual Environment Not Detected",
                        f"No 'bin/activate' found in '{directory}'.\nYou can still use this directory, but it may not be a valid Python virtual environment.",
                        duration=1000
                    )
                self.venv_edit.setText(directory)
                       
    def _copy_preview(self):
        """Copy the preview script to clipboard"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.preview_text.toPlainText())
        
        # Show feedback
        button = self.sender()
        original_text = button.text()
        button.setText("Copied!")
        QTimer.singleShot(1500, lambda: button.setText(original_text))
        
    def get_job(self) -> Job:
        """Get the configured job object"""
        return self.job
    
    def _populate_fields_from_job(self):
        """Fills the dialog's fields with the data from self.job."""
        job = self.job

        # Basic Tab
        self.name_edit.setText(job.name)
        self.account_edit.setCurrentText(job.account or "")
        self.partition_edit.setCurrentText(job.partition or "")
        self.working_dir_edit.setText(job.working_directory or "")
        self.venv_edit.setText(job.venv or "")
        self.script_edit.setPlainText(job.script_commands)

        # Resources Tab
        self.cpus_spin.setValue(job.cpus_per_task or 1)
        self.ntasks_spin.setValue(job.ntasks or 1)
        self.nodes_spin.setValue(int(job.nodes) if str(job.nodes).isdigit() else 1)
        if job.mem and 'G' in job.mem:
            self.mem_spin.setValue(int(job.mem.replace('G', '')))
        else:
            self.mem_spin.setValue(1) # default
        self.gpus_spin.setValue(int(job.gpus) if job.gpus and str(job.gpus).isdigit() else 0)
        self.gpus_per_task_spin.setValue(int(job.gpus_per_task) if job.gpus_per_task and str(job.gpus_per_task).isdigit() else 0)

        # Advanced Tab
        self.qos_edit.setCurrentText(job.qos or "")
        if job.nodelist and isinstance(job.nodelist, list):
            self.nodelist_edit.setCurrentText(','.join(job.nodelist))
        elif job.nodelist:
             self.nodelist_edit.setCurrentText(job.nodelist)

        self.output_edit.setText(job.output_file or "")
        self.error_edit.setText(job.error_file or "")
        self.nice_spin.setValue(job.nice or 0)
        self.oversubscribe_check.setChecked(job.oversubscribe or False)
        self.discord_notify_check.setChecked(job.discord_notifications or False)
        self.optional_sbatch_edit.setPlainText(job.optional_sbatch or "")
        if job.constraint:
            self.job.constraint = job.constraint
            self._update_constraint_summary()

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
            
        super().accept()
