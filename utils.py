from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import pyqtSignal
import sys, os
from PyQt6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QPushButton, QButtonGroup)
from PyQt6.QtCore import (Qt, pyqtSignal)  # Import pyqtSignal
from modules.defaults import *

# Object Names for Styling
BTN_GREEN = "btnGreen"
BTN_RED = "btnRed"
BTN_BLUE = "btnBlue"


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


class ExclusiveButtonWidget(QWidget):  # Renamed to ExclusiveButtonWidget as it's not a full window anymore

    # Define a custom signal that emits a string
    # This signal will be emitted when the selected button changes
    selectionChanged = pyqtSignal(str)

    # Added optional stylesheet parameter
    def __init__(self, stylesheet=None, parent=None):
        super().__init__(parent)
        self._user_stylesheet = stylesheet  # Store user stylesheet temporarily
        self.initUI()

        # Apply user provided stylesheet AFTER initUI has potentially set a default
        if self._user_stylesheet:
            self.setStyleSheet(self._user_stylesheet)

    def initUI(self):
        # Set a base object name for potential CSS targeting from outside
        self.setObjectName("exclusiveButtonGroupWidget")

        # Define the default stylesheet for this widget and its children
        # Includes the rule for the checked button state
        default_stylesheet = """
        ExclusiveButtonWidget {
            /* Optional: General background or padding for the widget itself */
            /* background-color: #f0f0f0; */
            /* padding: 5px; */
        }
        ExclusiveButtonWidget QPushButton {
            /* Optional: Default styling for all buttons */
             border: 1px solid #cccccc; /* Default border */
             padding: 5px 10px; /* Default padding */
             border-radius: 3px; /* Default border radius */
             background-color: #e0e0e0; /* Default background */
        }
        ExclusiveButtonWidget QPushButton:hover {
             background-color: #d0d0d0; /* Hover effect */
        }
        ExclusiveButtonWidget QPushButton:pressed {
             background-color: #c0c0c0; /* Pressed effect */
        }

        /* Style for the CHECKED button */
        ExclusiveButtonWidget QPushButton:checked {
            border: 2px solid blue; /* Highlight border */
            padding: 4px 9px; /* Adjust padding to keep size consistent with border */
            background-color: #a0c0ff; /* Optional: Different background for checked */
            font-weight: bold; /* Optional: Bold text for checked */
        }
        """
        # Apply the default stylesheet. This will be overridden by _user_stylesheet if provided.
        self.setStyleSheet(default_stylesheet)

        # Create the horizontal layout
        hbox = QHBoxLayout(self)  # Set self as the parent of the layout

        # Create the button group
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)  # Ensure only one button can be checked at a time

        # Define the button texts
        button_texts = ["ALL", "ME", "PROD", "STUD"]

        # Create the buttons and add them to the layout and group
        self.buttons = {}
        for text in button_texts:
            btn = QPushButton(text)


# Assume BTN_GREEN is defined elsewhere, e.g.:

# Assuming necessary imports and BTN_GREEN, BTN_BLUE are defined elsewhere

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

# --- Stylesheet Definitions ---


def get_dark_theme_stylesheet():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(script_dir, "configs", "settings.ini")
    configs_dir = os.path.join(script_dir, "configs")
    default_settings_path = os.path.join(script_dir, "src_static", "defaults.ini")
    dark_theme_path = os.path.join(script_dir, "src_static", "dark_theme.txt")
    with open(str(dark_theme_path), "r") as f:
        stylesheet_template = f.read()

    return stylesheet_template.format(
        COLOR_DARK_BG=COLOR_DARK_BG,
        COLOR_DARK_FG=COLOR_DARK_FG,
        COLOR_DARK_BG_ALT=COLOR_DARK_BG_ALT,
        COLOR_DARK_BG_HOVER=COLOR_DARK_BG_HOVER,
        COLOR_DARK_BORDER=COLOR_DARK_BORDER,
        COLOR_GREEN=COLOR_GREEN,
        COLOR_RED=COLOR_RED,
        COLOR_BLUE=COLOR_BLUE,
        COLOR_ORANGE=COLOR_ORANGE,
        BTN_GREEN=BTN_GREEN,
        BTN_RED=BTN_RED,
        BTN_BLUE=BTN_BLUE,
    )


def get_light_theme_stylesheet():
    """Loads and returns the CSS stylesheet for the light theme from a file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(script_dir, "configs", "settings.ini")
    configs_dir = os.path.join(script_dir, "configs")
    default_settings_path = os.path.join(script_dir, "src_static", "defaults.ini")
    light_theme_path = os.path.join(script_dir, "src_static", "light_theme.txt")
    with open(str(light_theme_path), "r") as f:
        stylesheet = f.read()

    return stylesheet.format(
        COLOR_LIGHT_BG=COLOR_LIGHT_BG,
        COLOR_LIGHT_FG=COLOR_LIGHT_FG,
        COLOR_LIGHT_BG_ALT=COLOR_LIGHT_BG_ALT,
        COLOR_LIGHT_BG_HOVER=COLOR_LIGHT_BG_HOVER,
        COLOR_LIGHT_BORDER=COLOR_LIGHT_BORDER,
        COLOR_GREEN=COLOR_GREEN,
        COLOR_RED=COLOR_RED,
        COLOR_BLUE=COLOR_BLUE,
        COLOR_ORANGE=COLOR_ORANGE,
        BTN_GREEN=BTN_GREEN,
        BTN_RED=BTN_RED,
        BTN_BLUE=BTN_BLUE,
    )
