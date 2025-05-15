import os
import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
                             QGroupBox, QApplication) # Added QApplication for example usage
from PyQt6.QtGui import QFont, QPixmap, QIcon
from PyQt6.QtCore import Qt, QSize
from utils import create_separator, get_dark_theme_stylesheet, get_light_theme_stylesheet, script_dir
from modules.defaults import *

# Placeholder for JobsGroup - replace with your actual JobsGroup class
class JobsGroup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Job List Placeholder"))
        # self.setStyleSheet("border: 1px dashed red;") # Visual placeholder

# --- Start of the new Status Bar Widget Code ---

class BlockSection(QFrame):
    def __init__(self, bg_color, content_widget, rounded_side=None):
        super().__init__()
        self.setFixedSize(35, 40) # Fixed size as per the provided code
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
    def __init__(self, icon_color, count_color, icon_path, count):
        super().__init__()
        layout = QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Icon section
        icon_label = QLabel()
        # Check if icon_path is not empty before creating QPixmap
        if icon_path:
             try:
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    icon_label.setPixmap(pixmap.scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    print(f"Warning: Could not load icon from path: {icon_path}") # Add a warning for debugging
                    # Optional: Set a placeholder text or default icon if loading fails
                    icon_label.setText("?")
                    icon_label.setStyleSheet("color: white;") # Style placeholder text
             except Exception as e:
                 print(f"Error loading icon {icon_path}: {e}")
                 icon_label.setText("?")
                 icon_label.setStyleSheet("color: white;")
        else:
            icon_label.setText("?")
            icon_label.setStyleSheet("color: white;")


        icon_section = BlockSection(icon_color, icon_label, rounded_side="left")

        # Count section
        count_label = QLabel(str(count))
        count_label.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        count_section = BlockSection(count_color, count_label, rounded_side="right")

        layout.addWidget(icon_section)
        layout.addWidget(count_section)
        self.setLayout(layout)


class StatusBar(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0) # Removed padding to align better in the header

        # Define blocks: (icon_color, count_color, icon_path, count)
        # Using placeholder paths for icons as they are local to your system
        blocks = [
            ("#2DCB89", "#1F8A5D", os.path.join(script_dir, "src_static", "ok.svg"), 1),  # Green - Placeholder path
            ("#DA5B5B", "#992F2F", "", 0),    # Red - Placeholder path
            ("#8570DB", "#5C4C9D", "", 7),   # Purple - Placeholder path
            ("#6DB8E8", "#345D7E", "", 7),  # Blue - Placeholder path
        ]

        for icon_color, count_color, icon_path, count in blocks:
            layout.addWidget(StatusBlock(icon_color, count_color, icon_path, count))

        # layout.addStretch(1) # Add stretch if you want the blocks to stay on the left

        self.setLayout(layout)

# --- End of the new Status Bar Widget Code ---


class JobsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        self.current_theme = THEME_DARK # Using dark theme for initial styling

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
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        # Projects Label
        self.projects_label = QLabel("Jobs")
        self.projects_label.setStyleSheet("margin-right:100px;")
        self.projects_label.setFont(QFont("Arial", 16, QFont.Weight.Bold)) # Match style of QGroupBox title
        header_layout.addWidget(self.projects_label)

        # --- Add the new StatusBar widget ---
        self.status_bar = StatusBar()
        header_layout.addWidget(self.status_bar)

        # Add stretch to push everything to the left
        header_layout.addStretch(1)

        # Add the header widget to the main layout
        self.layout.addWidget(header_widget)


        # --- Job Submission Section ---
        # Add your job submission widgets here if any
        # Example:
        # self.layout.addWidget(QLabel("Job Submission Area Placeholder"))


        self.layout.addWidget(create_separator(shape=QFrame.Shape.HLine, color=COLOR_DARK_BORDER if self.current_theme ==
                              THEME_DARK else COLOR_LIGHT_BORDER))

        # --- Job List Section ---
        # To make the JobsGroup fill the remaining space, add a stretch factor.
        # A stretch of 1 allows it to expand proportionally.
        self.layout.addWidget(JobsGroup(), stretch=1)
