import os
import random
import sys
from unittest import result
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGroupBox,
    QApplication, QScrollArea, QPushButton, QInputDialog, QLineEdit,
    QDialog
)
from PyQt6.QtGui import QFont, QPixmap, QIcon, QMovie
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QRect, QTime

# Assuming these modules/files exist in your project structure
from modules import project_store
from utils import create_separator, get_dark_theme_stylesheet, get_light_theme_stylesheet, script_dir
from modules.defaults import *
from modules.project_store import ProjectStore
from modules.jobs_group import JobsGroup
from modules.new_job_dp import NewJobDialog
# Add a new dialog for creating a new job


class CustomInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumSize(400, 180)  # Larger size

        # Set window background color
        self.setStyleSheet("""
            QDialog {
                background-color: #565a70;
                color: #f8f8f2;
            }
            QLabel{
            background-color: #565a70;
            }
            QLineEdit {
                background-color: #44475a;
                color: #f8f8f2;
                border: 1px solid #6272a4;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #6272a4;
                color: #f8f8f2;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7281b5;
            }
            QLabel {
                color: #f8f8f2;
                font-size: 16px;
            }
        """)

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
        self.setStyleSheet("""
            QDialog {
                background-color: #565a70;
                color: #f8f8f2;
            }
            QLabel {
                background-color: #565a70;
                color: #f8f8f2;
                font-size: 16px;
            }
            QPushButton {
                background-color: #6272a4;
                color: #f8f8f2;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7281b5;
            }
            #confirm_btn {
                background-color: #ff5555;
            }
            #confirm_btn:hover {
                background-color: #ff6e6e;
            }
        """)

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
        self.parent_group = parent  # Store parent reference for deletion
        self.project_storer = storer
        self._is_selected = False  # Add selection state
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)

        # Project title label inside the box
        self.title_label = QLabel(project_name)
        self.title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.title_label.setContentsMargins(15, 0, 0, 10)
        self.title_label.setStyleSheet(
            "color: #f8f8f2;")  # Match dark theme color
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

        # Define blocks with smaller size: (icon_color, count_color, icon_path, count)
        blocks = [
            ("#2DCB89", "#1F8A5D", os.path.join(script_dir, "src_static",
             "ok.svg"), 1, "Completed"),  # Green - Placeholder path
            ("#DA5B5B", "#992F2F", os.path.join(script_dir, "src_static",
             "err.svg"), 3, "Crashed"),    # Red - Placeholder path
            ("#8570DB", "#5C4C9D", os.path.join(script_dir, "src_static",
             "pending.svg"), 7, "Pending"),   # Purple - Placeholder path
            ("#6DB8E8", "#345D7E", os.path.join(script_dir, "src_static",
             "loading_2.gif"), 7, "Running jobs"),  # Blue - Placeholder path
        ]

        for icon_color, count_color, icon_path, count, tooltip in blocks:
            # Create smaller status blocks
            mini_block = self.create_mini_status_block(
                icon_color, count_color, icon_path, count, tooltip)
            status_layout.addWidget(mini_block)

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
                        movie.setScaledSize(QSize(16, 16))  # Smaller size
                        icon_label.setMovie(movie)
                        movie.start()
                        # Store movie reference to prevent garbage collection
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
        mini_icon_section.setFixedSize(24, 26)  # Smaller size
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

        mini_count_section = QFrame()
        mini_count_section.setFixedSize(24, 26)  # Smaller size
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

    def update_status_count(self, status_type, count):
        """Update the count for a specific status type"""
        # This is a placeholder - in a real implementation, you'd
        # identify the correct status block and update its count
        pass

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
                # Remove from layout and delete
                parent_layout = self.parent_group.scroll_content_layout
                parent_layout.removeWidget(self)
                self.hide()  # Hide the widget immediately
                self.deleteLater()  # Schedule this widget for deletion
                self.project_storer.remove_project(project_name)
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
        self.projects_keys = self.parent.project_storer.all_projects()
        for proj in self.projects_keys:
            self.add_new_project(proj)
            # self.projects_children[proj].status_bar.children()[1].children()[2].children()[1].setText("10")

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
        rows = [
            (123, "preprocess-data", "RUNNING",  "00:04:12"),
            (random.randint(0, 100), "train-model",     "PENDING",  "—"),
        ]
        self.parent.jobs_group.update_jobs(project_name, rows)

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
        if self._selected_project_widget:
            self._selected_project_widget.set_selected(False)

        # Select the new widget
        selected_widget = self.projects_children.get(project_name)
        if selected_widget:
            selected_widget.set_selected(True)
            self._selected_project_widget = selected_widget
            self.project_selected.emit(project_name)  # Emit the new signal


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
             "ok.svg"), 1, "Completed"),  # Green - Placeholder path
            ("#DA5B5B", "#992F2F", os.path.join(script_dir, "src_static",
             "err.svg"), 3, "Crashed"),    # Red - Placeholder path
            ("#8570DB", "#5C4C9D", os.path.join(script_dir, "src_static",
             "pending.svg"), 7, "Pending"),   # Purple - Placeholder path
            ("#6DB8E8", "#345D7E", os.path.join(script_dir, "src_static",
             "loading_2.gif"), 7, "Running jobs"),  # Blue - Placeholder path
        ]

        for icon_color, count_color, icon_path, count, tooltip in blocks:
            layout.addWidget(StatusBlock(
                icon_color, count_color, icon_path, count, tooltip))

        # layout.addStretch(1) # Add stretch if you want the blocks to stay on the left

        self.setLayout(layout)


class JobsPanel(QWidget):
    def __init__(self, parent=None, slurm_connection=None):
        super().__init__(parent)
        self.slurm_connection = slurm_connection
        try:
            self.project_storer = ProjectStore(self.slurm_connection)
        except ConnectionError as e:
            print(e)
            self.project_storer = None
        self.current_project = None  # Add attribute to store selected project

        # Use a base layout for the main content (ProjectGroup and JobsGroup)
        self.base_layout = QHBoxLayout()
        self.base_layout.setContentsMargins(10, 0, 10, 10)
        self.base_layout.setSpacing(10)

        self.jobs_group = JobsGroup()
        self.project_group = ProjectGroup(parent=self)
        if self.project_storer is not None:
            self.project_group.start()

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
        self.new_jobs_button.setFixedSize(100, 40)  # Set a fixed size

        # Initially position the button (will be adjusted in resizeEvent)
        self.new_jobs_button.move(self.width() - self.new_jobs_button.width() - 20,
                                  self.height() - self.new_jobs_button.height() - 20)

        # --- Initial Project Selection ---
        # After loading projects, select the first one if available
        if self.project_storer is not None and self.project_group.projects_keys:
            first_project_name = self.project_group.projects_keys[-1]
            # Programmatically trigger the selection
            self.project_group.handle_project_selection(first_project_name)
            # Manually call the slot in JobsPanel to set the current_project
            self.on_project_selected(first_project_name)

    def on_project_selected(self, project_name):
        """Slot to update the currently selected project."""
        self.current_project = project_name
        # For debugging
        print(f"Selected Project in JobsPanel: {self.current_project}")

    def open_new_job_dialog(self):
        """Opens the dialog to create a new job for the selected project."""
        if self.current_project:
            dialog = NewJobDialog(
                selected_project=self.current_project, slurm_connection=self.slurm_connection)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                result = dialog.get_job_details()
                print(result)
                # Here you would add the logic to create the new job
                # based on job_name and project_name
        else:
            print("No project selected.")  # Or show a message to the user

    def resizeEvent(self, event):
        """Adjust the position of the floating button when the widget is resized."""
        # Position the button in the bottom right corner with some margin
        self.new_jobs_button.move(self.width() - self.new_jobs_button.width() - 20,
                                  self.height() - self.new_jobs_button.height() - 20)
        super().resizeEvent(event)

    def setup_project_storer(self):
        try:
            self.project_storer = ProjectStore(self.slurm_connection)
            self.project_storer._init(self.slurm_connection, remote_path=None)
            # while not hasattr(self.project_storer, "_projects"): continue
            self.project_group.start()
        except ConnectionError as e:
            print(e)
            self.project_storer = None
