"""
Remote Directory Panel - Refactored with a modern MVC approach.
Features asynchronous directory loading and an intuitive, unified path/filter bar.
"""

import os
import posixpath
from typing import List, Optional

from PyQt6.QtCore import (QObject, QThread, pyqtSignal, Qt, QSize,
                          QSortFilterProxyModel)
from PyQt6.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListView,
                             QLineEdit, QToolButton, QProgressBar, QLabel,
                             QDialogButtonBox, QAbstractItemView)

from core.slurm_api import SlurmAPI, ConnectionState
from core.style import AppStyles
from utils import script_dir
from widgets.toast_widget import show_error_toast, show_warning_toast

# --- Constants ---
UP_DIRECTORY_TEXT = ".."
HOME_ICON_PATH = os.path.join(script_dir, "src_static", "home.svg")
UP_ICON_PATH = os.path.join(script_dir, "src_static", "prev_folder.svg")
REFRESH_ICON_PATH = os.path.join(script_dir, "src_static", "refresh.svg")
FOLDER_ICON_PATH = os.path.join(script_dir, "src_static", "folder.svg")


# ============================================================================
# WORKER THREAD (for non-blocking remote operations)
# ============================================================================

class DirectoryLoaderThread(QThread):
    """Worker thread to fetch remote directories without blocking the UI."""
    result_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, slurm_api: SlurmAPI, path: str, parent=None):
        super().__init__(parent)
        self.slurm_api = slurm_api
        self.path = path

    def run(self):
        """Execute the remote command."""
        try:
            if not self.slurm_api.remote_path_exists(self.path):
                self.error_occurred.emit(f"Path does not exist: {self.path}")
                return

            directories = self.slurm_api.list_remote_directories(self.path)
            self.result_ready.emit(sorted(directories))
        except Exception as e:
            self.error_occurred.emit(f"Failed to load directories: {str(e)}")


# ============================================================================
# MODEL (Handles data and state logic)
# ============================================================================

class RemoteDirectoryModel(QObject):
    """Manages the state and data for the remote directory browser."""
    path_changed = pyqtSignal(str)
    directories_changed = pyqtSignal(list)
    status_changed = pyqtSignal(str)
    loading_state_changed = pyqtSignal(bool)

    def __init__(self, slurm_api: SlurmAPI, initial_path: Optional[str] = None):
        super().__init__()
        self.slurm_api = slurm_api
        self._current_path: str = initial_path or self.slurm_api.remote_home or "/"
        self._directory_cache: dict[str, list[str]] = {}
        self._worker_thread: Optional[DirectoryLoaderThread] = None

    @property
    def current_path(self) -> str:
        return self._current_path

    def set_path(self, new_path: str, force_refresh: bool = False):
        """Sets the current path and fetches its contents asynchronously."""
        new_path = posixpath.normpath(new_path)
        if not new_path.endswith('/'):
            new_path += '/'
            
        if self.slurm_api.connection_status != ConnectionState.CONNECTED:
            self.status_changed.emit("Error: Not connected.")
            return
        
        # Only reload if the path is truly different
        if new_path == self._current_path and not force_refresh:
            return

        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.terminate()

        self._current_path = new_path
        self.path_changed.emit(self._current_path)

        if not force_refresh and self._current_path in self._directory_cache:
            cached_dirs = self._directory_cache[self._current_path]
            self.directories_changed.emit(cached_dirs)
            self.status_changed.emit(f"{len(cached_dirs)} items")
            return

        self.loading_state_changed.emit(True)
        self.status_changed.emit(f"Loading {self._current_path}...")

        self._worker_thread = DirectoryLoaderThread(self.slurm_api, self._current_path)
        self._worker_thread.result_ready.connect(self._on_load_success)
        self._worker_thread.error_occurred.connect(self._on_load_error)
        self._worker_thread.finished.connect(lambda: self.loading_state_changed.emit(False))
        self._worker_thread.start()

    def _on_load_success(self, directories: list[str]):
        self._directory_cache[self._current_path] = directories
        self.directories_changed.emit(directories)
        self.status_changed.emit(f"{len(directories)} items")

    def _on_load_error(self, error_message: str):
        self.status_changed.emit(f"Error: {error_message}")
        self.directories_changed.emit([])

    def refresh(self):
        self.set_path(self._current_path, force_refresh=True)

    def navigate_up(self):
        # Go to parent of current path, ensuring not to go above root
        parent_path = posixpath.dirname(self._current_path.rstrip('/'))
        if not parent_path:
            parent_path = "/"
        self.set_path(parent_path)

    def go_home(self):
        if self.slurm_api.remote_home:
            self.set_path(self.slurm_api.remote_home)
            
    def path_exists(self, path: str) -> bool:
        return self.slurm_api.remote_path_exists(path)


# ============================================================================
# CONTROLLER (Connects View and Model)
# ============================================================================
class RemoteDirectoryController(QObject):
    def __init__(self, model: RemoteDirectoryModel, view: 'RemoteDirectoryDialog'):
        super().__init__()
        self.model = model
        self.view = view
        self._connect_signals()
    
    def _connect_signals(self):
        # Model -> View connections
        self.model.path_changed.connect(self.view.path_edit.setText)
        self.model.directories_changed.connect(self.view.update_list_view)
        self.model.status_changed.connect(self.view.status_label.setText)
        self.model.loading_state_changed.connect(self.view.set_loading_state)
        
        # View -> Controller/Model connections
        self.view.up_button.clicked.connect(self.model.navigate_up)
        self.view.home_button.clicked.connect(self.model.go_home)
        self.view.refresh_button.clicked.connect(self.model.refresh)
        self.view.path_edit.textChanged.connect(self._on_path_text_changed)
        self.view.path_edit.returnPressed.connect(self._on_path_return_pressed)
        self.view.list_view.doubleClicked.connect(self._on_item_activated)
        self.view.button_box.accepted.connect(self._on_accept)
        self.view.button_box.rejected.connect(self.view.reject)

    def _on_path_text_changed(self, text: str):
        """Parses the path input to separate the base directory and the filter term."""
        text = text.strip()
        if not text:
            return

        base_path = self.model.current_path
        filter_term = ""

        if text.endswith('/'):
            base_path = text
        else:
            base_path = posixpath.dirname(text)
            if not base_path.endswith('/'):
                base_path += '/'
            filter_term = posixpath.basename(text)

        # Load the base directory if it has changed
        if base_path != self.model.current_path:
            self.model.set_path(base_path)

        # Apply the filter
        self.view.proxy_model.setFilterRegularExpression(filter_term)

    def _on_path_return_pressed(self):
        """Handles the Enter key in the path bar for smart navigation."""
        path = self.view.path_edit.text()
        
        # If the path is a valid directory, navigate into it
        if self.model.path_exists(path):
             self.model.set_path(path)
             return

        # If not a directory, check if it's a filter with a single match
        if self.view.proxy_model.rowCount() == 1:
            match_index = self.view.proxy_model.index(0, 0)
            item_text = self.view.proxy_model.data(match_index)
            if item_text != UP_DIRECTORY_TEXT:
                completed_path = posixpath.join(self.model.current_path, item_text)
                self.model.set_path(completed_path)


    def _on_item_activated(self, index):
        """Handles double-clicking an item in the list."""
        item_text = self.view.proxy_model.data(index)
        if item_text == UP_DIRECTORY_TEXT:
            self.model.navigate_up()
        else:
            new_path = posixpath.join(self.model.current_path, item_text)
            self.model.set_path(new_path)

    def _on_accept(self):
        """Handles the 'OK' button click."""
        path = self.view.get_selected_directory()
        if self.model.path_exists(path):
            self.view.accept()
        else:
            show_warning_toast(self.view, "Invalid Path", f"The path '{path}' does not exist.")

# ============================================================================
# VIEW (The dialog window)
# ============================================================================

class RemoteDirectoryDialog(QDialog):
    """A clean, simple, and responsive remote directory browser dialog."""

    def __init__(self, initial_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.slurm_api = SlurmAPI()
        self.model = RemoteDirectoryModel(self.slurm_api, initial_path)
        
        self._init_ui()
        self.controller = RemoteDirectoryController(self.model, self)
        
        # Trigger initial load
        self.model.set_path(self.model.current_path)

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Browse Remote Directory")
        self.setMinimumSize(550, 450)
        self.setStyleSheet(AppStyles.get_complete_stylesheet())

        main_layout = QVBoxLayout(self)

        # --- Navigation Bar ---
        nav_bar = QHBoxLayout()
        self.up_button = self._create_tool_button(UP_ICON_PATH, "Go Up")
        self.home_button = self._create_tool_button(HOME_ICON_PATH, "Go Home")
        self.refresh_button = self._create_tool_button(REFRESH_ICON_PATH, "Refresh")
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Type a path to navigate or filter...")

        nav_bar.addWidget(self.up_button)
        nav_bar.addWidget(self.home_button)
        nav_bar.addWidget(self.refresh_button)
        nav_bar.addWidget(QLabel("Path:"))
        nav_bar.addWidget(self.path_edit)
        main_layout.addLayout(nav_bar)

        # --- Loading Indicator ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate mode
        main_layout.addWidget(self.progress_bar)

        # --- Directory List View ---
        self.list_view = QListView()
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_model = QStandardItemModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.list_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.list_view.setModel(self.proxy_model)
        main_layout.addWidget(self.list_view)

        # --- Status Label ---
        self.status_label = QLabel("Initializing...")
        main_layout.addWidget(self.status_label)
        
        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        main_layout.addWidget(self.button_box)

    def _create_tool_button(self, icon_path: str, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setIcon(QIcon(icon_path))
        button.setIconSize(QSize(22, 22))
        button.setToolTip(tooltip)
        button.setFixedSize(32, 32)
        return button

    def update_list_view(self, directories: list[str]):
        """Populates the list view with new directory data."""
        self.list_model.clear()
        folder_icon = QIcon(FOLDER_ICON_PATH)
        up_icon = QIcon(UP_ICON_PATH)

        if self.model.current_path != "/":
            up_item = QStandardItem(up_icon, UP_DIRECTORY_TEXT)
            self.list_model.appendRow(up_item)

        for dir_name in directories:
            item = QStandardItem(folder_icon, dir_name)
            self.list_model.appendRow(item)

    def set_loading_state(self, is_loading: bool):
        """Shows/hides the progress bar and enables/disables controls."""
        self.progress_bar.setVisible(is_loading)
        self.list_view.setEnabled(not is_loading)
        self.path_edit.setEnabled(not is_loading)
        self.up_button.setEnabled(not is_loading)
        self.home_button.setEnabled(not is_loading)

    def get_selected_directory(self) -> str:
        """Public method to retrieve the result of the dialog."""
        return self.path_edit.text().rstrip('/')