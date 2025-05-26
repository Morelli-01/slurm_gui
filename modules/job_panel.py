from modules import project_store
from modules.job_logs import JobLogsDialog
from modules.toast_notify import show_error_toast, show_info_toast, show_success_toast, show_warning_toast
from slurm_connection import SlurmConnection
from utils import create_separator, script_dir
from modules.defaults import *
from modules.project_store import ProjectStore
from modules.jobs_group import JobsGroup
from modules.new_job_dp import ModifyJobDialog, NewJobDialog
from style import AppStyles


class CustomInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumSize(400, 180)  # Larger size

        self.setStyleSheet(AppStyles.get_dialog_styles() +
                           AppStyles.get_input_styles() +
                           AppStyles.get_button_styles())

        # Create widgets
        self.label = QLabel("Enter project name:")
        self.label.setFont(QFont("Arial", 12))

        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("My Amazing Project")
        self.text_edit.setMinimumHeight(40)

        # Create buttons
        self.ok_button = QPushButton("Create")
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(15)  # More spacing for relaxed feel
        layout.setContentsMargins(25, 25, 25, 20)  # Larger margins

        layout.addWidget(self.label)
        layout.addWidget(self.text_edit)
        layout.addStretch()  # Push buttons to bottom
        layout.addLayout(button_layout)

    def get_input(self):
        """Return the text entered by the user"""
        return self.text_edit.text()


class CustomConfirmDialog(QDialog):
    def __init__(self, parent=None, title="Confirm", message="Are you sure?"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 180)  # Larger size

        # Set window background color - same as CustomInputDialog
        self.setStyleSheet(AppStyles.get_dialog_styles() +
                           AppStyles.get_button_styles())
        # Create widgets
        self.label = QLabel(message)
        self.label.setFont(QFont("Arial", 12))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)

        # Create buttons
        self.confirm_button = QPushButton("Delete")
        self.confirm_button.setObjectName("confirm_btn")
        self.confirm_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.confirm_button)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(15)  # More spacing for relaxed feel
        layout.setContentsMargins(25, 25, 25, 20)  # Larger margins

        layout.addWidget(self.label)
        layout.addStretch()  # Push buttons to bottom
        layout.addLayout(button_layout)


class ProjectWidget(QGroupBox):
    selected = pyqtSignal(str)

    def __init__(self, project_name="", parent=None, storer=None):
        super().__init__("", parent)
        self.parent_group = parent
        self.project_storer = storer
        self._is_selected = False

        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)

        # Project title label inside the box
        self.title_label = QLabel(project_name)
        self.title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.title_label.setContentsMargins(15, 0, 0, 10)
        self.title_label.setStyleSheet("color: #f8f8f2;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Top section with title only
        self.layout.addWidget(self.title_label)

        # Status bar and delete button on the same row
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(15, 0, 15, 0)

        # Status bar (smaller version of the main status bar)
        self.status_bar = self.create_project_status_bar()
        status_layout.addWidget(self.status_bar)

        # Spacer to push delete button to the right
        status_layout.addStretch(1)

        # Delete button
        self.delete_button = QPushButton()
        self.delete_button.setObjectName(BTN_RED)
        self.delete_button.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "delete.svg")))
        self.delete_button.setFixedSize(26, 26)
        self.delete_button.setToolTip("Delete Project")
        self.delete_button.clicked.connect(self.delete_project)
        status_layout.addWidget(self.delete_button)

        # Add the status bar layout to main layout
        self.layout.addLayout(status_layout)

        # Apply initial style
        self.update_style()

    def update_style(self):
        """Updates the stylesheet based on the selection state."""
        base_style = """
            QGroupBox {{
                border: {border_thickness}px solid {border_color};
                border-radius: 8px;
                margin-top: 10px;
                font-size: 16px;
                font-weight: bold;
                color: {text_color};
                background-color: {bg_color};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background-color: {bg_color};
                color: {text_color};
                margin-left: 5px;
            }}
        """
        if self._is_selected:
            # Highlighted style with a more distinct border color and thickness
            border_color = "#8be9fd"  # A lighter blue/cyan from a similar palette
            border_thickness = 3  # Thicker border
            bg_color = COLOR_DARK_BG  # Keep the slightly darker background
            text_color = "#f8f8f2"
        else:
            # Default style
            border_color = COLOR_DARK_BORDER
            border_thickness = 2  # Default border thickness
            bg_color = COLOR_DARK_BG
            text_color = COLOR_DARK_FG

        self.setStyleSheet(base_style.format(
            border_thickness=border_thickness,
            border_color=border_color,
            bg_color=bg_color,
            text_color=text_color
        ))

    def set_selected(self, selected):
        """Sets the selection state and updates the style."""
        if self._is_selected != selected:
            self._is_selected = selected
            self.update_style()

    def create_project_status_bar(self):
        """Creates a smaller version of the status bar for individual projects"""
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setSpacing(5)
        status_layout.setContentsMargins(0, 0, 0, 0)

        # Store references to the status blocks for updating
        self.status_blocks = {}

        # Define blocks with smaller size: (icon_color, count_color, icon_path, initial_count, tooltip, status_key)
        blocks_config = [
            ("#2DCB89", "#1F8A5D", os.path.join(script_dir,
             "src_static", "ok.svg"), 0, "Completed", "COMPLETED"),
            ("#DA5B5B", "#992F2F", os.path.join(script_dir,
             "src_static", "err.svg"), 0, "Failed", "FAILED"),
            ("#8570DB", "#5C4C9D", os.path.join(script_dir,
             "src_static", "pending.svg"), 0, "Pending", "PENDING"),
            ("#6DB8E8", "#345D7E", os.path.join(script_dir,
             "src_static", "loading_2.gif"), 0, "Running", "RUNNING"),
        ]

        for icon_color, count_color, icon_path, count, tooltip, status_key in blocks_config:
            mini_block = self.create_mini_status_block(
                icon_color, count_color, icon_path, count, tooltip)
            status_layout.addWidget(mini_block)

            # Store reference to this block for updating
            self.status_blocks[status_key] = mini_block

        return status_container

    def create_mini_status_block(self, icon_color, count_color, icon_path, count, tooltip):
        """Creates a smaller version of StatusBlock for projects"""
        block = QWidget()
        block.setToolTip(tooltip)
        block_layout = QHBoxLayout()
        block_layout.setSpacing(0)
        block_layout.setContentsMargins(0, 0, 0, 0)

        # Icon section (smaller)
        icon_label = QLabel()
        movie = None

        if icon_path:
            try:
                if icon_path.lower().endswith('.gif'):
                    movie = QMovie(icon_path)
                    if not movie.isValid():
                        icon_label.setText("?")
                    else:
                        movie.setScaledSize(QSize(16, 16))
                        icon_label.setMovie(movie)
                        movie.start()
                        icon_label.movie = movie
                else:
                    pixmap = QPixmap(icon_path)
                    if not pixmap.isNull():
                        icon_label.setPixmap(pixmap.scaled(16, 16,
                                                           Qt.AspectRatioMode.KeepAspectRatio,
                                                           Qt.TransformationMode.SmoothTransformation))
                    else:
                        icon_label.setText("?")
            except Exception as e:
                print(f"Error loading media {icon_path}: {e}")
                icon_label.setText("?")

        # Create smaller blocks
        mini_icon_section = QFrame()
        mini_icon_section.setFixedSize(24, 26)
        mini_icon_section.setStyleSheet(f"""
            background-color: {icon_color};
            border-top-left-radius: 6px;
            border-bottom-left-radius: 6px;
        """)
        icon_layout = QVBoxLayout(mini_icon_section)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_label)

        # Count section (smaller)
        count_label = QLabel(str(count))

        # Store reference to count label for updates
        block.count_label = count_label

        mini_count_section = QFrame()
        mini_count_section.setFixedSize(24, 26)
        mini_count_section.setStyleSheet(f"""
            background-color: {count_color};
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
        """)
        count_layout = QVBoxLayout(mini_count_section)
        count_layout.setContentsMargins(0, 0, 0, 0)
        count_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_layout.addWidget(count_label)

        block_layout.addWidget(mini_icon_section)
        block_layout.addWidget(mini_count_section)
        block.setLayout(block_layout)

        return block

    def delete_project(self):
        """Remove this project from the parent's layout using custom styled dialog"""
        if self.parent_group and hasattr(self.parent_group, 'scroll_content_layout'):
            # Get the project name from the title label
            project_name = self.title_label.text()

            # Create and show custom confirmation dialog
            confirm_dialog = CustomConfirmDialog(
                self,
                title="Delete Project",
                message=f"Are you sure you want to delete '{project_name}'?"
            )

            if confirm_dialog.exec() == QDialog.DialogCode.Accepted:
                # previously change selected project or else everything will crash
                if len(self.parent_group.projects_children.keys()) > 1:
                    new_selected_project = list(self.parent_group.projects_children.keys())[-1] if list(
                        self.parent_group.projects_children.keys())[-1] != project_name else list(self.parent_group.projects_children.keys())[-2]
                    self.parent_group.handle_project_selection(
                        new_selected_project)
                    # Remove from layout and delete
                parent_layout = self.parent_group.scroll_content_layout
                parent_layout.removeWidget(self)
                self.hide()  # Hide the widget immediately
                self.deleteLater()  # Schedule this widget for deletion
                self.project_storer.remove_project(project_name)
                self.parent_group.parent.jobs_group.remove_project(
                    project_name)

                print(f"Project '{project_name}' deleted")

    def setTitle(self, title):
        """Override to update both the QGroupBox title and the label"""
        super().setTitle(title)  # Set the QGroupBox title
        if hasattr(self, 'title_label'):
            # Update the internal label if it exists
            self.title_label.setText(title)

    def mousePressEvent(self, event):
        # Emit the selected signal
        self.selected.emit(self.title_label.text())
        # Call the parent's mousePressEvent
        super().mousePressEvent(event)

    def update_status_counts(self, job_stats):
        """Update the status counts based on job statistics"""
        if not hasattr(self, 'status_blocks') or not self.status_blocks:
            return

        # Map of status keys to counts
        status_mapping = {
            "COMPLETED": job_stats.get("COMPLETED", 0),
            # Count cancelled as failed
            "FAILED": job_stats.get("FAILED", 0) + job_stats.get("CANCELLED", 0),
            "PENDING": job_stats.get("PENDING", 0) + job_stats.get("NOT_SUBMITTED", 0),
            "RUNNING": job_stats.get("RUNNING", 0),
        }

        # Update each status block
        for status_key, count in status_mapping.items():
            if status_key in self.status_blocks:
                block = self.status_blocks[status_key]
                if hasattr(block, 'count_label'):
                    block.count_label.setText(str(count))


class ProjectGroup(QGroupBox):
    # New signal to emit selected project name
    project_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Project", parent)
        self.setFixedWidth(350)
        self.parent = parent
        self.project_counter = 0
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(
            QScrollArea.Shape.NoFrame)  # Hide outline
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setStyleSheet(scroll_bar_stylesheet)
        # self.scroll_area.setFixedWidth(500)
        # Create widget to hold content inside scroll area
        self.scroll_content = QWidget()
        # self.scroll_content.setStyleSheet("background: transparent;")

        # Create layout for the content widget
        self.scroll_content_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_content_layout.setContentsMargins(
            0, 0, 0, 0)  # Remove margins
        self.scroll_content_layout.setSpacing(
            10)  # Add spacing between widgets
        self.scroll_content_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop)  # Align content to top
        self.scroll_content_layout.addStretch(1)

        self.add_button = QPushButton("New Project")
        self.add_button.setIcon(
            QIcon(os.path.join(script_dir, "src_static", "plus.png")))
        self.add_button.setObjectName(BTN_GREEN)
        self.add_button.clicked.connect(self.prompt_new_project)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.scroll_area)
        self.layout.addWidget(self.add_button)
        self.projects_children = {}
        # Keep track of the currently selected widget
        self._selected_project_widget = None

    def start(self):
        """
        Load and display all projects from the project storer.
        For each project, populate the UI with project widgets.
        """
        if not hasattr(self.parent, 'project_storer') or self.parent.project_storer is None:
            print("Project storer not initialized")
            return

        try:
            # Get all projects from the store
            self.projects_keys = self.parent.project_storer.all_projects()

            # Add project widgets to UI
            for proj_name in self.projects_keys:
                self.add_new_project(proj_name)

                # Get the project from the store
                project = self.parent.project_storer.get(proj_name)

                if project and project.jobs:
                    # Convert jobs to rows for display
                    job_rows = [job.to_table_row() for job in project.jobs]

                    # Update jobs UI
                    self.parent.jobs_group.update_jobs(proj_name, job_rows)

                    # Update project status visualization (using job counts)
                    if hasattr(self.projects_children.get(proj_name, None), 'status_bar'):
                        job_stats = project.get_job_stats()

                        # Find status bar widgets and update counts
                        status_bar = self.projects_children[proj_name].status_bar
                        if hasattr(status_bar, 'children'):
                            widgets = status_bar.children()

                            # This is a simplistic approach - in a real implementation,
                            # you would have a more reliable way to map widgets to statuses
                            if len(widgets) >= 5:  # Assuming the 4 status blocks + layout
                                # Set counts if widgets are found (simplistic mapping)
                                # widgets[1] is likely completed jobs block
                                self._update_widget_count(
                                    widgets[1], job_stats.get("COMPLETED", 0))

                                # widgets[2] is likely failed jobs block
                                self._update_widget_count(
                                    widgets[2], job_stats.get("FAILED", 0))

                                # widgets[3] is likely pending jobs block (includes NOT_SUBMITTED)
                                pending_count = job_stats.get("PENDING", 0)
                                not_submitted = sum(
                                    1 for job in project.jobs if job.status == "NOT_SUBMITTED")
                                self._update_widget_count(
                                    widgets[3], pending_count + not_submitted)

                                # widgets[4] is likely running jobs block
                                self._update_widget_count(
                                    widgets[4], job_stats.get("RUNNING", 0))
        except Exception as e:
            print(f"Error loading projects: {e}")
            import traceback
            traceback.print_exc()

    def _update_widget_count(self, widget, count):
        """Helper method to update the count displayed in a status block widget"""
        try:
            # Navigate through widget hierarchy to find the count label
            # This is a simplified approach and might need adjustment based on actual widget structure
            for child in widget.findChildren(QLabel)[::-1]:
                # Try to update text directly (with string conversion for safety)
                child.setText(str(count))
                return True
        except Exception as e:
            print(f"Error updating widget count: {e}")
        return False

    def prompt_new_project(self):
        """Open a custom dialog to ask for project name"""
        dialog = CustomInputDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            project_name = dialog.get_input()
            if project_name:  # Check if name is not empty
                self.add_new_project(project_name)

    def add_new_project(self, project_name):
        """Add a new ProjectWidget with the given name"""
        self.project_counter += 1
        new_project = ProjectWidget(
            project_name, self, storer=self.parent.project_storer)
        self.parent.jobs_group.add_project(project_name)

        # Connect the selected signal to the handler
        new_project.selected.connect(self.handle_project_selection)
        new_project.selected.connect(self.parent.jobs_group.show_project)

        new_project.setMaximumHeight(150)
        self.parent.project_storer.add_project(project_name)
        # Add the new project widget to the TOP of the scroll area content
        self.scroll_content_layout.insertWidget(0, new_project)

        # Scroll to the top to show the newly added widget
        self.scroll_area.verticalScrollBar().setValue(0)
        self.projects_children[project_name] = new_project

        if self.project_counter == 1:
            self.handle_project_selection(project_name)

    def add_project_widget(self, project_widget):
        """Method to programmatically add project widgets"""
        # Add at the top
        self.scroll_content_layout.insertWidget(0, project_widget)
        self.scroll_area.verticalScrollBar().setValue(0)
        """Method to programmatically add project widgets"""
        self.scroll_content_layout.addWidget(project_widget)
        self.scroll_content_layout.insertWidget(0, project_widget)
        self.scroll_area.verticalScrollBar().setValue(0)

    def handle_project_selection(self, project_name):
        """Handles the selection of a project widget."""
        # Deselect the previously selected widget
        try:
            if self._selected_project_widget:
                self._selected_project_widget.set_selected(False)

            # Select the new widget
            selected_widget = self.projects_children.get(project_name)
            if selected_widget:
                selected_widget.set_selected(True)
                self._selected_project_widget = selected_widget
                self.project_selected.emit(project_name)  # Emit the new signal
        except Exception as e:
            print(e)


class BlockSection(QFrame):
    def __init__(self, bg_color, content_widget, rounded_side=None):
        super().__init__()
        self.setFixedSize(35, 40)  # Fixed size as per the provided code
        border_radius = {
            "left": "border-top-left-radius: 8px; border-bottom-left-radius: 8px;",
            "right": "border-top-right-radius: 8px; border-bottom-right-radius: 8px;",
            None: ""
        }[rounded_side]

        self.setStyleSheet(f"""
            background-color: {bg_color};
            {border_radius}
        """)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content_widget)
        self.setLayout(layout)


class StatusBlock(QWidget):
    def __init__(self, icon_color, count_color, icon_path, count, tooltip=None):
        super().__init__()
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setToolTip(tooltip)

        # Icon section
        icon_label = QLabel()
        self.movie = None  # Store movie as instance variable to prevent garbage collection

        # Check if icon_path is not empty before creating media
        if icon_path:
            try:
                # Check if the icon path is a GIF
                if icon_path.lower().endswith('.gif'):
                    # Handle GIF animation
                    self.movie = QMovie(icon_path)
                    if not self.movie.isValid():
                        print(
                            f"Warning: Could not load GIF from path: {icon_path}")
                        icon_label.setText("?")
                        icon_label.setStyleSheet("color: white;")
                    else:
                        # Set size for the movie
                        self.movie.setScaledSize(QSize(22, 22))
                        icon_label.setMovie(self.movie)
                        self.movie.start()
                else:
                    # Handle static image
                    pixmap = QPixmap(icon_path)
                    if not pixmap.isNull():
                        icon_label.setPixmap(pixmap.scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio,
                                                           Qt.TransformationMode.SmoothTransformation))
                    else:
                        print(
                            f"Warning: Could not load icon from path: {icon_path}")
                        icon_label.setText("?")
                        icon_label.setStyleSheet("color: white;")
            except Exception as e:
                print(f"Error loading media {icon_path}: {e}")
                icon_label.setText("?")
                icon_label.setStyleSheet("color: white;")
        else:
            icon_label.setText("?")
            icon_label.setStyleSheet("color: white;")

        icon_section = BlockSection(
            icon_color, icon_label, rounded_side="left")

        # Count section
        count_label = QLabel(str(count))
        count_label.setStyleSheet(
            "color: white; font-weight: bold; font-size: 14px;")
        count_section = BlockSection(
            count_color, count_label, rounded_side="right")

        layout.addWidget(icon_section)
        layout.addWidget(count_section)
        self.setLayout(layout)


class StatusBar(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        layout.setSpacing(10)
        # Removed padding to align better in the header
        layout.setContentsMargins(0, 0, 0, 0)

        # Define blocks: (icon_color, count_color, icon_path, count)
        # Using placeholder paths for icons as they are local to your system
        blocks = [
            ("#2DCB89", "#1F8A5D", os.path.join(script_dir, "src_static",
             "ok.svg"), 0, "Completed"),  # Green - Placeholder path
            ("#DA5B5B", "#992F2F", os.path.join(script_dir, "src_static",
             "err.svg"), 0, "Crashed"),    # Red - Placeholder path
            ("#8570DB", "#5C4C9D", os.path.join(script_dir, "src_static",
             "pending.svg"), 0, "Pending"),   # Purple - Placeholder path
            ("#6DB8E8", "#345D7E", os.path.join(script_dir, "src_static",
             "loading_2.gif"), 0, "Running jobs"),  # Blue - Placeholder path
        ]

        for icon_color, count_color, icon_path, count, tooltip in blocks:
            layout.addWidget(StatusBlock(
                icon_color, count_color, icon_path, count, tooltip))

        # layout.addStretch(1) # Add stretch if you want the blocks to stay on the left

        self.setLayout(layout)


class JobsPanel(QWidget):
# In modules/job_panel.py - Replace the JobsPanel.__init__ method

    def __init__(self, parent=None, slurm_connection: SlurmConnection = None):
        super().__init__(parent)
        self.slurm_connection = slurm_connection
        self.project_storer = None  # Initialize to None
        
        # Try to initialize project store if connection is available
        if slurm_connection and slurm_connection.check_connection():
            try:
                self.project_storer = ProjectStore(self.slurm_connection)
                self._connect_project_store_signals()
                print("Project store initialized successfully")
            except Exception as e:
                print(f"Failed to initialize project store: {e}")
                self.project_storer = None
        else:
            print("No SLURM connection available - project store will be initialized later")
        
        self.current_project = None  # Add attribute to store selected project

        # Use a base layout for the main content (ProjectGroup and JobsGroup)
        self.base_layout = QHBoxLayout()
        self.base_layout.setContentsMargins(10, 0, 10, 10)
        self.base_layout.setSpacing(10)

        self.jobs_group = JobsGroup()
        self.project_group = ProjectGroup(parent=self)
        
        # Only start loading projects if project_storer is available
        if self.project_storer is not None:
            self.project_group.start()
        else:
            # Show a message that connection is needed
            self._show_connection_required_message()

        self.base_layout.addWidget(self.project_group)
        self.base_layout.addWidget(self.jobs_group)

        # Set the base layout as the main layout for the JobsPanel
        self.setLayout(self.base_layout)

        self.current_theme = THEME_DARK  # Using dark theme for initial styling

        # Apply base stylesheet for the panel and GroupBox
        self.setStyleSheet(f"""
            QGroupBox {{
                border: 2px solid {COLOR_DARK_BORDER};
                border-radius: 8px;
                margin-top: 10px;
                font-size: 16px;
                font-weight: bold;
                color: {COLOR_DARK_FG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                background-color: {COLOR_DARK_BG};
                color: {COLOR_DARK_FG};
                margin-left: 5px;
            }}
        """)

        # Connect the project_selected signal from ProjectGroup to a slot in JobsPanel
        self.project_group.project_selected.connect(self.on_project_selected)

        # Add the "New Jobs" floating button
        self.new_jobs_button = QPushButton(
            "New Job", self)  # Set self as parent
        # Using a placeholder object name, replace with appropriate style
        self.new_jobs_button.setObjectName(BTN_GREEN)
        self.new_jobs_button.clicked.connect(self.open_new_job_dialog)
        self.new_jobs_button.setFixedSize(120, 40)  # Set a fixed size

        # Initially position the button (will be adjusted in resizeEvent)
        self.new_jobs_button.move(self.width() - self.new_jobs_button.width() - 20,
                                self.height() - self.new_jobs_button.height() - 20)

        # --- Initial Project Selection ---
        # After loading projects, select the first one if available
        if self.project_storer is not None and hasattr(self.project_group, 'projects_keys') and self.project_group.projects_keys:
            first_project_name = self.project_group.projects_keys[-1]
            # Programmatically trigger the selection
            self.project_group.handle_project_selection(first_project_name)
            # Manually call the slot in JobsPanel to set the current_project
            self.on_project_selected(first_project_name)
            # FIXED: Explicitly show the project in JobsGroup to sync the stacked view
            self.jobs_group.show_project(first_project_name)

        # Connect job action signals
        self.jobs_group.submitRequested.connect(self.submit_job)
        self.jobs_group.cancelRequested.connect(self.delete_job)
        self.jobs_group.stopRequested.connect(self.stop_job)
        self.jobs_group.logsRequested.connect(self.show_job_logs)
        self.jobs_group.duplicateRequested.connect(self.duplicate_job)
        self.jobs_group.modifyRequested.connect(self.modify_job)

    def _show_connection_required_message(self):
        """Show a message indicating that SLURM connection is required"""
        try:
            # Add a temporary project to show the message
            temp_project = ProjectWidget("⚠️ Connection Required", self.project_group, storer=None)
            temp_project.setMaximumHeight(100)
            
            # Remove the delete button and status bar for this special widget
            if hasattr(temp_project, 'delete_button'):
                temp_project.delete_button.hide()
            if hasattr(temp_project, 'status_bar'):
                temp_project.status_bar.hide()
                
            # Update the title to show the message
            temp_project.title_label.setText("⚠️ SLURM Connection Required")
            temp_project.title_label.setStyleSheet("color: #ffb86c; font-weight: bold;")
            
            # Add to the project group
            self.project_group.scroll_content_layout.insertWidget(0, temp_project)
            self.project_group.projects_children["connection_required"] = temp_project
            
            # Show message in jobs area too
            self.jobs_group.show_connection_error("connection_required")
            
            print("Showing connection required message")
            
        except Exception as e:
            print(f"Error showing connection required message: {e}")

    def setup_project_storer(self):
        """
        Initialize the project store when a connection becomes available.
        Enhanced version with proper cleanup and reinitialization.
        """
        try:
            # Remove connection required message if it exists
            if "connection_required" in self.project_group.projects_children:
                temp_widget = self.project_group.projects_children["connection_required"]
                self.project_group.scroll_content_layout.removeWidget(temp_widget)
                temp_widget.hide()
                temp_widget.deleteLater()
                del self.project_group.projects_children["connection_required"]
                
            # Create/recreate the ProjectStore instance with the current connection
            if self.project_storer:
                # Stop existing monitoring
                self.project_storer.stop_job_monitoring()
                
            self.project_storer = ProjectStore(self.slurm_connection)

            # Connect signals for real-time updates
            self._connect_project_store_signals()

            # Start loading projects
            self.project_group.start()
            
            print("Project store setup completed successfully")

        except Exception as e:
            print(f"Failed to setup project store: {e}")
            import traceback
            traceback.print_exc()
            self.project_storer = None
            
            # Show error message
            show_error_toast(self, "Setup Error", 
                            f"Failed to initialize project store: {str(e)}")

    # Also add this method to handle cases where project_storer is None
    def _check_project_storer(self):
        """Check if project_storer is available and show appropriate message"""
        if not self.project_storer:
            show_warning_toast(self, "No Connection", 
                            "Please establish SLURM connection first.")
            return False
        return True

    # Update methods that use project_storer to check if it's available first
    def open_new_job_dialog(self):
        """Opens the dialog to create a new job for the selected project."""
        if not self._check_project_storer():
            return
            
        if self.current_project:
            dialog = NewJobDialog(
                selected_project=self.current_project, slurm_connection=self.slurm_connection)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                job_details = dialog.get_job_details()

                try:
                    # Create the job via the project storer WITHOUT submitting to SLURM
                    job_id = self.project_storer.add_new_job(
                        self.current_project, job_details)

                    if job_id:
                        # Parse GPU count from gres if available
                        gpu_count = 0
                        gres = job_details.get("gres")
                        if gres and "gpu:" in gres:
                            try:
                                gpu_parts = gres.split(":")
                                if len(gpu_parts) == 2:  # Format: gpu:N
                                    gpu_count = int(gpu_parts[1])
                                elif len(gpu_parts) == 3:  # Format: gpu:type:N
                                    gpu_count = int(gpu_parts[2])
                            except (ValueError, IndexError):
                                pass

                        # Get memory setting
                        memory = job_details.get("memory", "1G")
                        if not memory:
                            memory_value = job_details.get("memory_spin", 1)
                            memory_unit = job_details.get("memory_unit", "GB")
                            memory = f"{memory_value}{memory_unit}"

                        # Create a job row for the UI display
                        job_row = [
                            job_id,
                            job_details.get("job_name", "Unnamed Job"),
                            "NOT_SUBMITTED",  # Special status to indicate job needs to be submitted
                            "00:00:00",  # Initial runtime is zero
                            job_details.get("cpus_per_task", 1),  # CPU count
                            gpu_count,  # GPU count parsed from gres
                            memory,  # Memory
                        ]

                        # Add the job to the jobs group UI
                        self.jobs_group.add_single_job(
                            self.current_project, job_row)

                        show_success_toast(self, "Job Created",
                                        f"Job '{job_details.get('job_name')}' has been created!")
                    else:
                        show_warning_toast(
                            self,
                            "Creation Failed",
                            "Failed to create job. Please check logs for more information."
                        )
                except Exception as e:
                    show_error_toast(
                        self,
                        "Job Creation Error",
                        f"An error occurred while creating the job: {str(e)}"
                    )

        else:
            show_warning_toast(
                self,
                "No Project Selected",
                "Please select a project first before creating a new job."
            )

    def submit_job(self, project_name, job_id):
        """Submit job - Enhanced version with project_storer check"""
        if not self._check_project_storer():
            return
            
        try:
            # Get job and validate
            project = self.project_storer.get(project_name)
            if not project:
                show_warning_toast(
                    self, "Error", f"Project '{project_name}' not found.")
                return

            job = project.get_job(job_id)
            if not job:
                show_warning_toast(self, "Error", f"Job '{job_id}' not found.")
                return

            if job.status != "NOT_SUBMITTED":
                show_info_toast(
                    self,
                    "Already Submitted",
                    f"Job '{job_id}' has already been submitted with status: {job.status}."
                )
                return

            # Store the old job ID for UI updates
            old_job_id = str(job_id)

            # Submit the job
            new_job_id = self.project_storer.submit_job(project_name, job_id)

            if new_job_id:
                # Get the updated job with the new ID
                updated_job = project.get_job(new_job_id)
                if updated_job:
                    job_row = updated_job.to_table_row()

                    # Update the UI to reflect the ID change efficiently
                    self.jobs_group.update_job_id(
                        project_name, old_job_id, str(new_job_id), job_row)

                # Show success message
                show_success_toast(
                    self, "Job Submitted", f"Job has been submitted with ID {new_job_id}")

            else:
                show_warning_toast(
                    self, "Submission Failed", "Failed to submit job. Please check logs for more information.")

        except Exception as e:
            show_error_toast(self, "Submission Error",
                            f"An error occurred during job submission: {str(e)}")
            import traceback
            traceback.print_exc()
    
    
    def on_project_selected(self, project_name):
        """Slot to update the currently selected project."""
        self.current_project = project_name
        # For debugging
        print(f"Selected Project in JobsPanel: {self.current_project}")

    def resizeEvent(self, event):
        """Adjust the position of the floating button when the widget is resized."""
        # Position the button in the bottom right corner with some margin
        self.new_jobs_button.move(self.width() - self.new_jobs_button.width() - 20,
                                  self.height() - self.new_jobs_button.height() - 20)
        super().resizeEvent(event)

    def _update_job_in_table(self, project_name: str, job_id: str):
        """Update a specific job row in the jobs table"""
        if not self.project_storer:
            return

        project = self.project_storer.get(project_name)
        if not project:
            return

        job = project.get_job(job_id)
        if not job:
            return

        # Check if this project's table exists
        if project_name not in self.jobs_group._indices:
            return

        # Get the table widget for this project
        table = self.jobs_group._stack.widget(
            self.jobs_group._indices[project_name])
        if not table:
            return

        # Find the row with this job ID
        for row in range(table.rowCount()):
            item = table.item(row, 0)  # Job ID column
            if item and item.text() == str(job_id):
                # Update the job row
                job_row = job.to_table_row()
                self._update_table_row(
                    table, row, job_row, project_name, job_id)
                break

    def _update_table_row(self, table, row, job_data, project_name, job_id):
        """Update a specific table row with new job data"""
        actions_col = table.columnCount() - 1

        # Update data columns (exclude actions column)
        for col in range(actions_col):
            if col < len(job_data):
                item = table.item(row, col)
                if item:
                    item.setText(str(job_data[col]))

                    # Apply status color if this is the status column (index 2)
                    if col == 2:
                        self.jobs_group._apply_state_color(item)

        # Update action buttons based on new status
        job_status = job_data[2] if len(job_data) > 2 else None
        action_widget = self.jobs_group._create_actions_widget(
            project_name, job_id, job_status)
        table.setCellWidget(row, actions_col, action_widget)

    def _show_job_status_notification(self, project_name: str, job_id: str, old_status: str, new_status: str):
        """Show notifications for important status changes"""
        important_changes = {
            'COMPLETED': ('Job Completed', f'Job {job_id} in {project_name} has completed successfully!'),
            'FAILED': ('Job Failed', f'Job {job_id} in {project_name} has failed.'),
            'RUNNING': ('Job Started', f'Job {job_id} in {project_name} is now running.'),
            'CANCELLED': ('Job Cancelled', f'Job {job_id} in {project_name} was cancelled.'),
            'TIMEOUT': ('Job Timeout', f'Job {job_id} in {project_name} has timed out.')
        }

        if new_status in important_changes:
            title, message = important_changes[new_status]

            # Show system notification (optional)
            self._show_system_notification(title, message)

            # Show status bar message (brief)
            if hasattr(self.parent(), 'statusBar'):
                self.parent().statusBar().showMessage(message, 5000)  # 5 seconds

    def _show_system_notification(self, title: str, message: str):
        """Show system desktop notification"""
        try:
            # Try to use system notifications
            from PyQt6.QtWidgets import QSystemTrayIcon
            if QSystemTrayIcon.isSystemTrayAvailable():
                # This is a basic implementation
                # You might want to create a proper system tray icon
                pass
        except ImportError:
            pass

    def closeEvent(self, event):
        """Handle widget close event"""
        # Stop job monitoring when panel is closed
        if self.project_storer:
            self.project_storer.stop_job_monitoring()
        super().closeEvent(event)

    def _connect_project_store_signals(self):
        """Connect to project store signals for real-time updates"""
        if not self.project_storer:
            return

        # Connect to job status changes using the signals object
        self.project_storer.signals.job_status_changed.connect(
            self._on_job_status_changed)
        self.project_storer.signals.job_updated.connect(self._on_job_updated)
        self.project_storer.signals.project_stats_changed.connect(
            self._on_project_stats_changed)

    def _on_job_status_changed(self, project_name: str, job_id: str, old_status: str, new_status: str):
        """Handle job status changes from project store with optimized notifications"""
        print(f"Job {job_id} in {project_name}: {old_status} -> {new_status}")

        # Update the specific job row efficiently
        self._update_single_job_from_store(project_name, job_id)

        # Show immediate toast notification (optimized)
        self._show_immediate_job_toast(
            project_name, job_id, old_status, new_status)

        # Show brief notification for important status changes (status bar)
        self._show_status_notification(
            project_name, job_id, old_status, new_status)

    def _on_job_updated(self, project_name: str, job_id: str):
        """Handle general job updates (timing, resources, etc.) - SIMPLIFIED VERSION"""
        self._update_single_job_from_store(project_name, job_id)

    def _on_project_stats_changed(self, project_name: str, stats: dict):
        """Handle project statistics changes - SIMPLIFIED VERSION"""
        self._update_project_status_display(project_name, stats)

    def _update_single_job_from_store(self, project_name: str, job_id: str):
        """Update a single job row from the project store - CORE EFFICIENT METHOD"""
        if not self.project_storer:
            return

        # Get the updated job from store
        project = self.project_storer.get(project_name)
        if not project:
            return

        job = project.get_job(job_id)
        if not job:
            return

        # Convert job to table row format
        job_row = job.to_table_row()

        # Update the specific row in the jobs table
        self.jobs_group.update_single_job_row(
            project_name, str(job_id), job_row)

    def _show_status_notification(self, project_name: str, job_id: str, old_status: str, new_status: str):
        """Show brief notifications for important status changes"""
        # Only show notifications for significant status changes
        important_changes = {
            'COMPLETED': f'✅ Job {job_id} completed successfully!',
            'FAILED': f'❌ Job {job_id} failed.',
            'RUNNING': f'🏃 Job {job_id} started running.',
            'CANCELLED': f'🛑 Job {job_id} was cancelled.'
        }

        if new_status in important_changes:
            message = important_changes[new_status]

            # Show in status bar if parent has one
            if hasattr(self.parent(), 'statusBar'):
                self.parent().statusBar().showMessage(message, 3000)  # 3 seconds

            # print(f"📢 {message}")

    def _update_project_status_display(self, project_name: str, stats: dict):
        """Update project status display (status bars in project widgets) - SIMPLIFIED VERSION"""
        if project_name not in self.project_group.projects_children:
            return

        project_widget = self.project_group.projects_children[project_name]

        # Update status counts in project widget if it has the method
        if hasattr(project_widget, 'update_status_counts'):
            project_widget.update_status_counts(stats)

    def delete_job(self, project_name, job_id):
        """Delete job - SIMPLIFIED VERSION with efficient UI update"""
        if not self.project_storer:
            QMessageBox.warning(self, "Error", "Not connected to SLURM.")
            return

        try:
            # Get job and validate
            project = self.project_storer.get(project_name)
            if not project:
                QMessageBox.warning(
                    self, "Error", f"Project '{project_name}' not found.")
                return

            job = project.get_job(job_id)
            if not job:
                QMessageBox.warning(
                    self, "Error", f"Job '{job_id}' not found.")
                return

            if job.status not in ["NOT_SUBMITTED", "COMPLETED", "FAILED", "STOPPED", "CANCELLED"]:
                QMessageBox.warning(self, "Error",
                                    f"Job can't be deleted since it is {job.status} status\n"
                                    f"Job '{job_id}' needs to be stopped before deleting.")
                return

            # Remove the job from store
            self.project_storer.remove_job(project_name, job_id)

            # Remove from UI efficiently
            self.jobs_group.remove_job(project_name, job_id)

            print(f"Job {job_id} deleted successfully")

        except Exception as e:
            QMessageBox.critical(self, "Deletion Error",
                                 f"An error occurred during job deletion: {str(e)}")
            import traceback
            traceback.print_exc()

    def stop_job(self, project_name, job_id):
        if not self.project_storer:
            QMessageBox.warning(self, "Error", "Not connected to SLURM.")
            return

        try:
            # Get job and validate
            project = self.project_storer.get(project_name)
            if not project:
                QMessageBox.warning(
                    self, "Error", f"Project '{project_name}' not found.")
                return

            job = project.get_job(job_id)
            if not job:
                QMessageBox.warning(
                    self, "Error", f"Job '{job_id}' not found.")
                return

            if job.status in ["NOT_SUBMITTED", "COMPLETED", "FAILED", "STOPPED"]:
                QMessageBox.warning(self, "Error",
                                    f"Job can't be deleted since it is {job.status} status\n")
                return

            stdout, stderr = self.slurm_connection.run_command(
                f"scancel {job_id}")
            if stderr:
                QMessageBox.warning(
                    self, "Error", f"Something went wrong with command:", f"scancel --full {job_id}")
                return

        except Exception as e:
            QMessageBox.critical(self, "Deletion Error",
                                 f"An error occurred during job deletion: {str(e)}")
            import traceback
            traceback.print_exc()

    def show_job_logs(self, project_name, job_id):
        """Show the job logs dialog"""
        if not self.project_storer:
            QMessageBox.warning(
                self, "Error", "Not connected to project store.")
            return

        try:
            # Create and show the logs dialog
            dialog = JobLogsDialog(
                project_name=project_name,
                job_id=job_id,
                project_store=self.project_storer,
                parent=self
            )
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Opening Logs",
                f"Failed to open job logs:\n{str(e)}"
            )
            import traceback
            traceback.print_exc()

    def duplicate_job(self, project_name, job_id):
        """Duplicate an existing job with a new name"""
        if not self.project_storer:
            QMessageBox.warning(
                self, "Error", "Not connected to project store.")
            return

        try:
            # Get the original job
            project = self.project_storer.get(project_name)
            if not project:
                QMessageBox.warning(
                    self, "Error", f"Project '{project_name}' not found.")
                return

            original_job = project.get_job(job_id)
            if not original_job:
                QMessageBox.warning(
                    self, "Error", f"Job '{job_id}' not found.")
                return

            # Ask user for new job name
            new_name, ok = QInputDialog.getText(
                self,
                "Duplicate Job",
                f"Enter name for duplicated job (original: '{original_job.name}'):",
                text=f"{original_job.name}_copy"
            )

            if not ok or not new_name.strip():
                return  # User cancelled or entered empty name

            # Create job details from the original job
            job_details = {
                "job_name": new_name.strip(),
                "partition": original_job.partition,
                "time_limit": original_job.time_limit,
                "command": original_job.command,
                "account": original_job.account,
                "constraint": original_job.constraints,
                "qos": original_job.qos,
                "gres": original_job.gres,
                "nodes": original_job.nodes,
                "cpus_per_task": original_job.cpus,
                "memory": original_job.memory,
                "output_file": original_job.output_file,
                "error_file": original_job.error_file,
                "working_dir": original_job.working_dir,
            }

            # Add optional array and dependency settings if they exist
            if original_job.array_spec:
                job_details["array"] = original_job.array_spec
                if original_job.array_max_jobs:
                    job_details["array_max_jobs"] = original_job.array_max_jobs

            if original_job.dependency:
                job_details["dependency"] = original_job.dependency

            # Create the duplicated job
            new_job_id = self.project_storer.add_new_job(
                project_name, job_details)

            if new_job_id:
                # Parse GPU count from gres if available
                gpu_count = 0
                if original_job.gres and "gpu:" in original_job.gres:
                    try:
                        gpu_parts = original_job.gres.split(":")
                        if len(gpu_parts) == 2:  # Format: gpu:N
                            gpu_count = int(gpu_parts[1])
                        elif len(gpu_parts) == 3:  # Format: gpu:type:N
                            gpu_count = int(gpu_parts[2])
                    except (ValueError, IndexError):
                        pass

                # Create a job row for the UI display
                job_row = [
                    new_job_id,
                    new_name.strip(),
                    "NOT_SUBMITTED",  # New job starts as not submitted
                    "00:00:00",  # Initial runtime is zero
                    original_job.cpus,  # CPU count
                    gpu_count,  # GPU count
                    original_job.memory,  # Memory
                ]

                # Add the job to the jobs group UI
                self.jobs_group.add_single_job(project_name, job_row)

                # Update project status display
                # self.project_group.update_project_status(project_name)
                if project_name in self.project_group.projects_children:
                    project_widget = self.project_group.projects_children[project_name]
                    if hasattr(project_widget, 'update_status_counts'):
                        job_stats = project.get_job_stats()
                        project_widget.update_status_counts(job_stats)
            else:
                QMessageBox.warning(
                    self,
                    "Duplication Failed",
                    "Failed to duplicate job. Please check logs for more information."
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Duplication Error",
                f"An error occurred while duplicating the job: {str(e)}"
            )
            import traceback
            traceback.print_exc()

    def modify_job(self, project_name, job_id):
        """Modify an existing job"""
        if not self.project_storer:
            QMessageBox.warning(
                self, "Error", "Not connected to project store.")
            return

        try:
            # Get the job to modify
            project = self.project_storer.get(project_name)
            if not project:
                QMessageBox.warning(
                    self, "Error", f"Project '{project_name}' not found.")
                return

            job = project.get_job(job_id)
            if not job:
                QMessageBox.warning(
                    self, "Error", f"Job '{job_id}' not found.")
                return

            # Only allow modification of NOT_SUBMITTED jobs
            if job.status != "NOT_SUBMITTED":
                show_warning_toast(
                    self,
                    "Cannot Modify Job",
                    f"Job '{job_id}' cannot be modified because it has status '{job.status}'. Only jobs with status 'NOT_SUBMITTED' can be modified."
                )
                return

            # Open the modify dialog
            dialog = ModifyJobDialog(
                job=job,
                project_name=project_name,
                slurm_connection=self.slurm_connection,
                parent=self
            )

            if dialog.exec() == QDialog.DialogCode.Accepted:
                modified_details = dialog.get_job_details()

                try:
                    # Update the job in the project store
                    self._update_job_from_details(job, modified_details)

                    # Update the job in the store
                    self.project_storer.add_job(project_name, job)

                    # Update the UI
                    job_row = job.to_table_row()
                    self.jobs_group.update_single_job_row(
                        project_name, str(job_id), job_row)

                    # Show success message
                    show_success_toast(
                        self, "Job Modified", f"Job '{job.name}' has been successfully modified.")

                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Modification Error",
                        f"An error occurred while modifying the job: {str(e)}"
                    )
                    import traceback
                    traceback.print_exc()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Modification Error",
                f"An error occurred while opening the modify dialog: {str(e)}"
            )
            import traceback
            traceback.print_exc()

    def _update_job_from_details(self, job, details):
        """Update job object with new details from the modify dialog"""

        # Update basic job information
        job.name = details.get("job_name", job.name)
        job.partition = details.get("partition", job.partition)
        job.account = details.get("account", job.account)
        job.time_limit = details.get("time_limit", job.time_limit)
        job.command = details.get("command", job.command)
        job.nodes = details.get("nodes", job.nodes)
        job.cpus = details.get("cpus_per_task", job.cpus)
        job.memory = details.get("memory", job.memory)

        # Update optional fields
        job.constraints = details.get("constraint", job.constraints)
        job.qos = details.get("qos", job.qos)
        job.gres = details.get("gres", job.gres)
        job.output_file = details.get("output_file", job.output_file)
        job.error_file = details.get("error_file", job.error_file)
        job.working_dir = details.get("working_dir", job.working_dir)

        # Update GPU count from GRES if available
        if job.gres and "gpu:" in job.gres:
            try:
                gpu_parts = job.gres.split(":")
                if len(gpu_parts) == 2:  # Format: gpu:N
                    job.gpus = int(gpu_parts[1])
                elif len(gpu_parts) == 3:  # Format: gpu:type:N
                    job.gpus = int(gpu_parts[2])
            except (ValueError, IndexError):
                pass  # Keep existing GPU count if parsing fails

        # Update job array settings
        if "array" in details:
            job.array_spec = details["array"]
            if "array_max_jobs" in details:
                job.array_max_jobs = details["array_max_jobs"]
        else:
            job.array_spec = None
            job.array_max_jobs = None

        # Update dependencies
        if "dependency" in details:
            job.dependency = details["dependency"]
        else:
            job.dependency = None

        # Update submission details for later use
        job.info["submission_details"] = details

    def start_project_loading(self):
        """
        Load and display all projects from the project storer - SIMPLIFIED VERSION.
        """
        if not hasattr(self.parent, 'project_storer') or self.parent.project_storer is None:
            print("Project storer not initialized")
            return

        try:
            # Get all projects from the store
            projects_keys = self.parent.project_storer.all_projects()

            # Add project widgets to UI and load their jobs
            for proj_name in projects_keys:
                # Add project widget
                self.add_new_project(proj_name)

                # Get the project from the store
                project = self.parent.project_storer.get(proj_name)
                if project and project.jobs:
                    # Convert jobs to rows for display
                    job_rows = [job.to_table_row() for job in project.jobs]

                    # Update jobs UI efficiently - this will use the new efficient update system
                    self.parent.jobs_group.update_jobs(proj_name, job_rows)

        except Exception as e:
            print(f"Error loading projects: {e}")
            import traceback
            traceback.print_exc()

    def _show_immediate_job_toast(self, project_name: str, job_id: str, old_status: str, new_status: str):
        """Show immediate toast notifications with minimal processing"""

        # Get job name quickly (with fallback)
        job_name = self._get_job_name_fast(project_name, job_id)

        # Simplified notification config for better performance
        notifications = {
            'COMPLETED': {
                'title': '✅ Job Completed',
                'message': f"'{job_name}' finished successfully!",
                'show_func': show_success_toast,
                'duration': 5000
            },
            'FAILED': {
                'title': '❌ Job Failed',
                'message': f"'{job_name}' failed - check logs",
                'show_func': show_error_toast,
                'duration': 6000
            },
            'RUNNING': {
                'title': '🏃 Job Started',
                'message': f"'{job_name}' is now running",
                'show_func': show_info_toast,
                'duration': 3000
            },
            'CANCELLED': {
                'title': '🛑 Job Cancelled',
                'message': f"'{job_name}' was cancelled",
                'show_func': show_warning_toast,
                'duration': 4000
            },
            'TIMEOUT': {
                'title': '⏰ Job Timed Out',
                'message': f"'{job_name}' exceeded time limit",
                'show_func': show_error_toast,
                'duration': 5000
            }
        }

        # Show notification immediately if status is in our config
        if new_status in notifications:
            config = notifications[new_status]

            # Use Qt's queued connection to ensure UI thread execution
            QTimer.singleShot(0, lambda: config['show_func'](
                self,
                config['title'],
                config['message'],
                config['duration']
            ))

    def _get_job_name_fast(self, project_name: str, job_id: str):
        """Get job name with minimal overhead and fallback"""
        try:
            if self.project_storer:
                project = self.project_storer.get(project_name)
                if project:
                    job = project.get_job(job_id)
                    if job and job.name:
                        return job.name
        except:
            pass

        # Fast fallback - just use job ID
        return f"Job {job_id}"

