import platform
import subprocess
from PyQt6.QtWidgets import QLabel, QFrame
from PyQt6.QtCore import pyqtSignal
import sys, os
from PyQt6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QPushButton, QButtonGroup)
from PyQt6.QtCore import (Qt, pyqtSignal)  # Import pyqtSignal
from datetime import datetime, timedelta

COLOR_DARK_BORDER = "#6272a4"

script_dir = os.path.dirname(os.path.abspath(__file__))
settings_path = os.path.join(script_dir, "configs", "settings.ini")
configs_dir = os.path.join(script_dir, "configs")
default_settings_path = os.path.join(script_dir, "src_static", "defaults.ini")
font_directory = os.path.join("src_static", "Open_Sans")
# Object Names for Styling
BTN_GREEN = "btnGreen"
BTN_RED = "btnRed"
BTN_BLUE = "btnBlue"


def parse_duration(s: str) -> timedelta:
    """Parse a duration string in SLURM format to a timedelta object."""
    days = 0
    if '-' in s:
        # Format: D-HH:MM:SS
        day_part, time_part = s.split('-')
        days = int(day_part)
    else:
        time_part = s

    parts = [int(p) for p in time_part.split(':')]

    if len(parts) == 2:        # MM:SS
        h, m, s = 0, parts[0], parts[1]
    elif len(parts) == 3:      # HH:MM:SS
        h, m, s = parts
    else:
        raise ValueError(f"Invalid time format: {s}")

    return timedelta(days=days, hours=h, minutes=m, seconds=s)


def determine_job_status(state: str, exit_code: str = None) -> str:
    """
    Determine the actual job status based on SLURM state and exit code.

    Args:
        state: SLURM job state (e.g., 'COMPLETED', 'FAILED', etc.)
        exit_code: Job exit code (e.g., '0:0', '1:0', etc.)

    Returns:
        str: Refined job status
    """
    # Handle basic state mapping
    if state in ["COMPLETED"]:
        # For completed jobs, check exit code to determine if truly successful
        if exit_code:
            try:
                # Exit code format is usually "exit_status:signal"
                exit_status = exit_code.split(':')[0]
                exit_num = int(exit_status)

                if exit_num == 0:
                    return "COMPLETED"  # Successful completion
                else:
                    return "FAILED"     # Non-zero exit code = failure
            except (ValueError, IndexError):
                # If we can't parse exit code, assume success for COMPLETED state
                return "COMPLETED"
        else:
            # No exit code available, trust the COMPLETED state
            return "COMPLETED"

    elif state in ["FAILED", "NODE_FAIL", "BOOT_FAIL", "OUT_OF_MEMORY"]:
        return "FAILED"

    elif state in ["CANCELLED", "TIMEOUT", "REVOKED", "DEADLINE"]:
        return "CANCELLED"

    elif state in ["RUNNING", "COMPLETING"]:
        return "RUNNING"

    elif state in ["PENDING"]:
        return "PENDING"

    elif state in ["SUSPENDED", "PREEMPTED"]:
        return "SUSPENDED"

    elif state in ["STOPPED"]:
        return "STOPPED"

    else:
        return state  # Return original state if unknown


def parse_memory_size(size_str):
    """Convert memory size string with suffix to bytes as integer"""

    # Strip any whitespace and make uppercase for consistency
    size_str = size_str.strip().upper()

    # Define the multipliers for each unit
    multipliers = {
        'B': 1,
        'K': 1024,
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4,
        'P': 1024 ** 5
    }

    # Extract the number and unit
    if size_str[-2:] in ['KB', 'MB', 'GB', 'TB', 'PB']:
        number = float(size_str[:-2])
        unit = size_str[-2:-1]
    else:
        number = float(size_str[:-1])
        unit = size_str[-1]

    # Convert to bytes
    bytes_value = int(number * multipliers.get(unit, 1))

    return bytes_value


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

class ButtonGroupWidget(QWidget):  # Assuming this is a QWidget subclass
    selectionChanged = pyqtSignal(str)  # Signal that emits a string

    def __init__(self, parent=None):
        super().__init__(parent)

        hbox = QHBoxLayout(self)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)  # Ensure only one button can be checked

        self.buttons = {}

        button_texts = ["ALL", "ME", "PROD", "STUD"]
        for text in button_texts:
            btn = QPushButton(text)
            btn.setObjectName(BTN_GREEN)
            btn.setCheckable(True)  # Make the button retain its state
            hbox.addWidget(btn)
            self.button_group.addButton(btn)
            self.buttons[text] = btn

        if "ALL" in self.buttons:
            all_btn = self.buttons["ALL"]
            all_btn.setChecked(True)
            self.selectionChanged.emit("ALL")
            self._update_button_styles(all_btn)

        self.button_group.buttonClicked.connect(self._handle_button_click_and_emit)
        self.button_group.buttonClicked.connect(self._update_button_styles)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(5)

        # Layout is set automatically by passing 'self' to QHBoxLayout constructor

    # This slot is connected to button_group.buttonClicked for handling selectionChanged signal
    def _handle_button_click_and_emit(self, clicked_button):
        """
        Internal slot connected to QButtonGroup.buttonClicked.
        It receives the clicked button object and emits our custom signal.
        """
        # The clicked_button argument is the button that was just clicked.
        # Since QButtonGroup is exclusive, this button *should* now be the checked button.
        selected_text = clicked_button.text()
        self.selectionChanged.emit(selected_text)

    def _update_button_styles(self, clicked_button):
        """
        Slot connected to QButtonGroup.buttonClicked.
        Updates the objectName of buttons based on which one was clicked.
        """
        # clicked_button is the button that was clicked (and is now checked due to exclusivity)
        for text, btn in self.buttons.items():
            if btn is clicked_button:
                # Set the clicked button's objectName to BTN_BLUE
                btn.setObjectName(BTN_BLUE)
            else:
                # Set all other buttons' objectName to BTN_GREEN
                btn.setObjectName(BTN_GREEN)

            btn.style().polish(btn)

    def get_checked_button_text(self):
        """Convenience method to get the text of the currently checked button."""
        checked_btn = self.button_group.checkedButton()
        if checked_btn:
            return checked_btn.text()
        return None


def create_separator(shape=QFrame.Shape.HLine, color=COLOR_DARK_BORDER):
    """Creates a styled separator QFrame."""
    separator = QFrame()
    separator.setFrameShape(shape)
    separator.setFrameShadow(QFrame.Shadow.Sunken)
    separator.setStyleSheet(f"background-color: {color};")
    if shape == QFrame.Shape.HLine:
        separator.setFixedHeight(1)
    else:
        separator.setFixedWidth(1)
    return separator
