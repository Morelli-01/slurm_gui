"""
Remote Directory Panel - MVC Architecture Implementation
Separates data management, UI, and control logic for better maintainability.
"""

import os, posixpath
from typing import List, Optional, Dict, Any
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListView, QLineEdit, 
    QToolButton, QProgressBar, QLabel, QPushButton
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, QSize

from core.defaults import *
from core.slurm_api import ConnectionState, SlurmAPI
from utils import script_dir
from core.style import AppStyles
from widgets.toast_widget import show_error_toast, show_warning_toast

# ============================================================================
# MODEL - Data and Business Logic
# ============================================================================

class RemoteDirectoryModel(QObject):
    """
    Model class handling directory data, caching, and SLURM operations.
    Emits signals when data changes.
    """
    
    # Data change signals
    directoriesChanged = pyqtSignal(list)  # List of directory names
    currentPathChanged = pyqtSignal(str)   # Current path
    errorOccurred = pyqtSignal(str)        # Error message
    loadingStarted = pyqtSignal()
    loadingFinished = pyqtSignal()
    
    def __init__(self, initial_path: str = "/"):
        super().__init__()
        self.slurm_api = SlurmAPI()
        self._current_path = initial_path
        self._directories = []
        self._directory_cache: Dict[str, List[str]] = {}
        
    @property
    def current_path(self) -> str:
        return self._current_path
    
    @property 
    def directories(self) -> List[str]:
        return self._directories.copy()
    
    def set_current_path(self, path: str):
        """Set current path and load directories"""
        if path != self._current_path:
            self._current_path = path
            self.currentPathChanged.emit(path)
            self.load_directories()
    
    def load_directories(self, force_refresh: bool = False):
        """Load directories for current path"""
        if not self.slurm_api or not self.slurm_api.connection_status == ConnectionState.CONNECTED:
            self.errorOccurred.emit("Not connected to SLURM")
            return
            
        # Check cache first
        if not force_refresh and self._current_path in self._directory_cache:
            self._directories = self._directory_cache[self._current_path]
            self.directoriesChanged.emit(self._directories)
            return
            
        # Load from remote
        self.loadingStarted.emit()
        self._load_remote_directories()
    
    def _load_remote_directories(self):
        """Load directories from remote server"""
        try:
            if not self.slurm_api.remote_path_exists(self._current_path):
                self.errorOccurred.emit(f"Path does not exist: {self._current_path}")
                self.loadingFinished.emit()
                return
                
            directories = self.slurm_api.list_remote_directories(self._current_path)
            directories.sort()
            
            # Cache the result
            self._directory_cache[self._current_path] = directories
            self._directories = directories
            
            self.directoriesChanged.emit(directories)
            self.loadingFinished.emit()
            
        except Exception as e:
            self.errorOccurred.emit(f"Failed to load directories: {str(e)}")
            self.loadingFinished.emit()
    
    def navigate_up(self) -> bool:
        """Navigate to parent directory"""
        if self._current_path == "/":
            return False
            
        parent_path = posixpath.dirname(self._current_path.rstrip('/'))
        if not parent_path:
            parent_path = "/"
            
        if self.slurm_api.remote_path_exists(parent_path):
            self.set_current_path(parent_path)
            return True
        return False
    
    def navigate_to_home(self) -> bool:
        """Navigate to home directory"""
        if self.slurm_api.remote_home:
            home_path = self.slurm_api.remote_home
            if self.slurm_api.remote_path_exists(home_path):
                self.set_current_path(home_path)
                return True
        return False
    
    def navigate_to_subdirectory(self, dir_name: str) -> bool:
        """Navigate to a subdirectory"""
        if dir_name == "..":
            return self.navigate_up()
            
        new_path = posixpath.join(self._current_path, dir_name)
        if self.slurm_api.remote_path_exists(new_path):
            self.set_current_path(new_path)
            return True
        return False
    
    def path_exists(self, path: str) -> bool:
        """Check if a path exists"""
        return self.slurm_api.remote_path_exists(path)
    
    def clear_cache(self):
        """Clear directory cache"""
        self._directory_cache.clear()


class DirectoryWorker(QThread):
    """Background worker for loading directories without blocking UI"""
    finished = pyqtSignal(list, str, bool)
    progress = pyqtSignal(int)

    def __init__(self, model: RemoteDirectoryModel, path: str):
        super().__init__()
        self.model = model
        self.path = path

    def run(self):
        try:
            path_exists = self.model.path_exists(self.path)
            if not path_exists:
                self.finished.emit([], self.path, False)
                return
                
            dirs = self.model.slurm_api.list_remote_directories(self.path)
            dirs.sort()
            
            # Simulate progress for user feedback
            for i in range(1, 101):
                self.progress.emit(i)
                
            self.finished.emit(dirs, self.path, True)
        except Exception as e:
            print(f"Directory worker error: {e}")
            self.finished.emit([], self.path, False)


# ============================================================================
# VIEW - UI Components and Presentation
# ============================================================================

class RemoteDirectoryView(QDialog):
    """
    View class handling UI components and user interactions.
    Emits signals for user actions.
    """
    
    # User action signals
    navigationRequested = pyqtSignal(str)  # "up", "home", "refresh"
    directorySelected = pyqtSignal(str)    # Directory name
    pathEntered = pyqtSignal(str)          # Manual path entry
    itemClicked = pyqtSignal(str)          # Item clicked
    itemDoubleClicked = pyqtSignal(str)    # Item double-clicked
    filterChanged = pyqtSignal(str)        # Filter text
    dialogAccepted = pyqtSignal(str)       # Selected path
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Browse Remote Directory")
        self.setMinimumSize(600, 400)
        self._setup_stylesheet()
        self._setup_ui()
        
    def _setup_stylesheet(self):
        self.setStyleSheet(AppStyles.get_complete_stylesheet(THEME_DARK))

    def _setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout(self)

        # Navigation bar
        nav_layout = self._create_navigation_bar()
        main_layout.addLayout(nav_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Filter bar
        filter_layout = self._create_filter_bar()
        main_layout.addLayout(filter_layout)

        # Directory list
        self.dir_list_view = self._create_directory_list()
        main_layout.addWidget(self.dir_list_view)

        # Status label
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)

        # Button bar
        button_layout = self._create_button_bar()
        main_layout.addLayout(button_layout)

    def _create_navigation_bar(self) -> QHBoxLayout:
        """Create navigation bar with up, home, refresh buttons"""
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(5)

        # Up button
        self.up_button = QToolButton()
        self.up_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "prev_folder.svg")))
        self.up_button.setIconSize(QSize(24, 24))
        self.up_button.setToolTip("Go Up")
        self.up_button.setFixedSize(QSize(36, 36))
        self.up_button.clicked.connect(lambda: self.navigationRequested.emit("up"))
        nav_layout.addWidget(self.up_button)

        # Home button
        self.home_button = QToolButton()
        self.home_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "home.svg")))
        self.home_button.setIconSize(QSize(24, 24))
        self.home_button.setToolTip("Go to Home Directory")
        self.home_button.setFixedSize(QSize(36, 36))
        self.home_button.clicked.connect(lambda: self.navigationRequested.emit("home"))
        nav_layout.addWidget(self.home_button)

        # Refresh button
        self.refresh_button = QToolButton()
        self.refresh_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "refresh.svg")))
        self.refresh_button.setIconSize(QSize(24, 24))
        self.refresh_button.setToolTip("Refresh")
        self.refresh_button.setFixedSize(QSize(36, 36))
        self.refresh_button.clicked.connect(lambda: self.navigationRequested.emit("refresh"))
        nav_layout.addWidget(self.refresh_button)

        # Path display
        path_label = QLabel("Path:")
        nav_layout.addWidget(path_label)

        self.path_display_edit = QLineEdit()
        self.path_display_edit.returnPressed.connect(
            lambda: self.pathEntered.emit(self.path_display_edit.text()))
        nav_layout.addWidget(self.path_display_edit)

        return nav_layout

    def _create_filter_bar(self) -> QHBoxLayout:
        """Create filter bar"""
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter directories...")
        self.search_input.textChanged.connect(self.filterChanged.emit)
        self.search_input.setClearButtonEnabled(True)
        filter_layout.addWidget(self.search_input)
        
        return filter_layout

    def _create_directory_list(self) -> QListView:
        """Create directory list view with model"""
        self.dir_list_model = QStandardItemModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.dir_list_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        list_view = QListView()
        list_view.setModel(self.proxy_model)
        list_view.clicked.connect(self._on_item_clicked)
        list_view.doubleClicked.connect(self._on_item_double_clicked)
        
        return list_view

    def _create_button_bar(self) -> QHBoxLayout:
        """Create dialog button bar"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.select_button = QPushButton("Select")
        self.select_button.setObjectName("selectBtn")
        self.select_button.clicked.connect(self._select_current_path)
        button_layout.addWidget(self.select_button)

        return button_layout

    def _on_item_clicked(self, index):
        """Handle item click"""
        source_index = self.proxy_model.mapToSource(index)
        item_text = self.dir_list_model.itemFromIndex(source_index).text()
        self.itemClicked.emit(item_text)

    def _on_item_double_clicked(self, index):
        """Handle item double click"""
        source_index = self.proxy_model.mapToSource(index)
        item_text = self.dir_list_model.itemFromIndex(source_index).text()
        self.itemDoubleClicked.emit(item_text)

    def _select_current_path(self):
        """Emit dialog accepted with current path"""
        current_path = self.path_display_edit.text()
        self.dialogAccepted.emit(current_path)

    # View update methods
    def update_path_display(self, path: str):
        """Update path in the display"""
        self.path_display_edit.setText(path)

    def update_directories(self, directories: List[str], current_path: str):
        """Update directory list"""
        self.dir_list_model.clear()
        
        # Add parent directory if not at root
        if current_path != "/":
            up_item = QStandardItem("..")
            up_item.setIcon(QIcon(posixpath.join(script_dir, "src_static", "prev_folder.svg")))
            self.dir_list_model.appendRow(up_item)

        # Add directories
        for directory in directories:
            item = QStandardItem(directory)
            item.setIcon(QIcon(posixpath.join(script_dir, "src_static", "folder.svg")))
            self.dir_list_model.appendRow(item)

    def update_filter(self, filter_text: str):
        """Update directory filter"""
        self.proxy_model.setFilterRegularExpression(filter_text)

    def show_progress(self, visible: bool):
        """Show/hide progress bar"""
        self.progress_bar.setVisible(visible)

    def update_progress(self, value: int):
        """Update progress bar value"""
        self.progress_bar.setValue(value)

    def update_status(self, message: str):
        """Update status message"""
        self.status_label.setText(message)

    def show_error(self, message: str):
        """Show error message"""
        show_error_toast(self, "Directory Error", message)

    def show_warning(self, message: str):
        """Show warning message"""
        show_warning_toast(self, "Directory Warning", message)


# ============================================================================
# CONTROLLER - Coordination and Business Logic
# ============================================================================

class RemoteDirectoryController(QObject):
    """
    Controller class coordinating between model and view.
    Handles user interactions and business logic.
    """
    
    def __init__(self, model: RemoteDirectoryModel, view: RemoteDirectoryView):
        super().__init__()
        self.model = model
        self.view = view
        self.worker = None
        self._setup_connections()
        self._initialize()
        
    def _setup_connections(self):
        """Setup signal-slot connections between model and view"""
        # Model to View connections
        self.model.currentPathChanged.connect(self.view.update_path_display)
        self.model.directoriesChanged.connect(self._on_directories_changed)
        self.model.errorOccurred.connect(self._on_error_occurred)
        self.model.loadingStarted.connect(lambda: self.view.show_progress(True))
        self.model.loadingFinished.connect(lambda: self.view.show_progress(False))
        
        # View to Controller connections
        self.view.navigationRequested.connect(self._handle_navigation)
        self.view.pathEntered.connect(self._handle_path_entry)
        self.view.itemClicked.connect(self._handle_item_click)
        self.view.itemDoubleClicked.connect(self._handle_item_double_click)
        self.view.filterChanged.connect(self.view.update_filter)
        self.view.dialogAccepted.connect(self._handle_dialog_accept)
        
    def _initialize(self):
        """Initialize the controller"""
        self.model.load_directories()
        
    def _on_directories_changed(self, directories: List[str]):
        """Handle directory list changes"""
        self.view.update_directories(directories, self.model.current_path)
        
        if not directories:
            self.view.update_status(f"Directory {self.model.current_path} is empty")
        else:
            self.view.update_status(f"Found {len(directories)} directories")
            
    def _on_error_occurred(self, error_message: str):
        """Handle model errors"""
        self.view.update_status(f"Error: {error_message}")
        self.view.show_error(error_message)
        
        # Try fallback navigation
        if self.model.current_path != "/" and "Cannot access" in error_message:
            if self.model.slurm_api.remote_home:
                self.model.set_current_path(self.model.slurm_api.remote_home)
            else:
                self.model.set_current_path("/")
                
    def _handle_navigation(self, action: str):
        """Handle navigation actions"""
        if action == "up":
            if not self.model.navigate_up():
                self.view.show_warning("Already at root directory")
        elif action == "home":
            if not self.model.navigate_to_home():
                self.view.show_warning("Home directory not found")
        elif action == "refresh":
            self.model.clear_cache()
            self.model.load_directories(force_refresh=True)
            
    def _handle_path_entry(self, path: str):
        """Handle manual path entry"""
        path = path.strip()
        if path and self.model.path_exists(path):
            self.model.set_current_path(path)
        else:
            self.view.show_warning(f"Path '{path}' does not exist or is not accessible.")
            self.view.update_path_display(self.model.current_path)
            
    def _handle_item_click(self, item_text: str):
        """Handle item click"""
        if item_text == "..":
            parent_path = os.path.dirname(self.model.current_path.rstrip('/'))
            selected_path = parent_path if parent_path else "/"
        else:
            selected_path = os.path.join(self.model.current_path, item_text)
        
        self.view.update_path_display(selected_path)
        
    def _handle_item_double_click(self, item_text: str):
        """Handle item double click"""
        if item_text == "..":
            self.model.navigate_up()
        else:
            if not self.model.navigate_to_subdirectory(item_text):
                self.view.show_warning(f"'{item_text}' is not accessible.")
                
    def _handle_dialog_accept(self, selected_path: str):
        """Handle dialog acceptance"""
        if self.model.path_exists(selected_path):
            self.view.accept()
        else:
            self.view.show_warning("Please select a valid directory.")
            
    def get_selected_directory(self) -> str:
        """Get the currently selected directory"""
        return self.view.path_display_edit.text()


# ============================================================================
# DIALOG FACADE - Simplified Interface
# ============================================================================

class RemoteDirectoryDialog(QDialog):
    """
    Simplified facade dialog that encapsulates the MVC architecture.
    Provides the same interface as the original dialog.
    """
    
    def __init__(self, initial_path="/", parent=None):
        super().__init__(parent)
        
        # Create MVC components
        self.model = RemoteDirectoryModel(initial_path)
        self.view = RemoteDirectoryView(parent)
        self.controller = RemoteDirectoryController(self.model, self.view)
        
        # Setup dialog
        self.setWindowTitle(self.view.windowTitle())
        self.setMinimumSize(self.view.minimumSize())
        
        # Use view's layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        
        # Connect view's dialog signals to this dialog
        self.view.accepted.connect(self.accept)
        self.view.rejected.connect(self.reject)
        
    def get_selected_directory(self) -> str:
        """Get the selected directory path"""
        return self.controller.get_selected_directory()
    
    def exec(self) -> int:
        """Execute the dialog"""
        return self.view.exec()