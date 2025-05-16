import os
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
                             QGroupBox, QApplication, QScrollArea, QPushButton, QInputDialog, QLineEdit, QDialog)
from PyQt6.QtGui import QFont, QPixmap, QIcon, QMovie
from PyQt6.QtCore import Qt, QSize
from utils import create_separator, get_dark_theme_stylesheet, get_light_theme_stylesheet, script_dir
from modules.defaults import *

# Placeholder for JobsGroup - replace with your actual JobsGroup class


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


class JobsGroup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Job List Placeholder"))
        # self.setStyleSheet("border: 1px dashed red;") # Visual placeholder


class ProjectWidget(QGroupBox):
    def __init__(self, project_name="", parent=None):
        super().__init__("", parent)
        # self.setTitle(project_name)  # Set the GroupBox title
        self.parent_group = parent  # Store parent reference for deletion

        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(8)

        # Project title label inside the box
        self.title_label = QLabel(project_name)
        self.title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.title_label.setContentsMargins(0, 0, 0, 10)
        self.title_label.setStyleSheet(
            "color: #f8f8f2;")  # Match dark theme color
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Top section with title only
        self.layout.addWidget(self.title_label)

        # Status bar and delete button on the same row
        status_layout = QHBoxLayout()

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
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.setToolTip("Delete Project")
        self.delete_button.clicked.connect(self.delete_project)
        status_layout.addWidget(self.delete_button)

        # Add the status bar layout to main layout
        self.layout.addLayout(status_layout)

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
                print(f"Project '{project_name}' deleted")

    def setTitle(self, title):
        """Override to update both the QGroupBox title and the label"""
        super().setTitle(title)  # Set the QGroupBox title
        if hasattr(self, 'title_label'):
            # Update the internal label if it exists
            self.title_label.setText(title)


class ProjectGroup(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Project", parent)
        self.setFixedWidth(350)
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
        new_project = ProjectWidget(project_name, self)
        new_project.setMaximumHeight(150)

        # Add the new project widget to the TOP of the scroll area content
        self.scroll_content_layout.insertWidget(0, new_project)

        # Scroll to the top to show the newly added widget
        self.scroll_area.verticalScrollBar().setValue(0)

    def add_project_widget(self, project_widget):
        """Method to programmatically add project widgets"""
        # Add at the top
        self.scroll_content_layout.insertWidget(0, project_widget)
        self.scroll_area.verticalScrollBar().setValue(0)
        """Method to programmatically add project widgets"""
        self.scroll_content_layout.addWidget(project_widget)
        self.scroll_content_layout.insertWidget(0, project_widget)
        self.scroll_area.verticalScrollBar().setValue(0)


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

# --- End of the new Status Bar Widget Code ---


class JobsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 10, 10)
        self.layout.setSpacing(10)
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

        # --- Header Section ---
        # header_widget = QWidget()
        # header_layout = QHBoxLayout(header_widget)
        # header_layout.setContentsMargins(0, 0, 0, 0)
        # header_layout.setSpacing(10)

        # # Projects Label
        # self.projects_label = QLabel("Jobs")
        # self.projects_label.setStyleSheet("margin-right:50px;")
        # # Match style of QGroupBox title
        # self.projects_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        # header_layout.addWidget(self.projects_label)

        # # --- Add the new StatusBar widget ---
        # self.status_bar = StatusBar()
        # header_layout.addWidget(self.status_bar)

        # # Add stretch to push everything to the left
        # header_layout.addStretch(1)

        # # Add the header widget to the main layout
        # self.layout.addWidget(header_widget)

        # --- Job Submission Section ---
        # Add your job submission widgets here if any
        # Example:
        # self.layout.addWidget(QLabel("Job Submission Area Placeholder"))

        # self.layout.addWidget(create_separator(shape=QFrame.Shape.HLine, color=COLOR_DARK_BORDER if self.current_theme ==
                            #   THEME_DARK else COLOR_LIGHT_BORDER))

        # --- Job List Section ---
        # To make the JobsGroup fill the remaining space, add a stretch factor.
        # A stretch of 1 allows it to expand proportionally.
        lower_layout = QHBoxLayout()
        lower_layout.addWidget(ProjectGroup())
        lower_layout.addWidget(JobsGroup(), stretch=1)

        self.layout.addLayout(lower_layout, stretch=1)
