
from modules.defaults import *
from utils import script_dir

BUTTON_SIZE = 36  # Larger button size (was 36)
ICON_SIZE = 24 

class DirectoryWorker(QThread):
    """Background worker to fetch directories without blocking the UI"""
    finished = pyqtSignal(list, str, bool)
    progress = pyqtSignal(int)
    
    def __init__(self, slurm_connection, path):
        super().__init__()
        self.slurm_connection = slurm_connection
        self.path = path
        
    def run(self):
        try:
            # Check if path exists
            path_exists = self.slurm_connection.remote_path_exists(self.path)
            if not path_exists:
                self.finished.emit([], self.path, False)
                return
                
            # Get directory list
            dirs = self.slurm_connection.list_remote_directories(self.path)
            
            # Sort directories alphabetically
            dirs.sort()
            
            # Emit progress updates
            for i in range(1, 101):
                self.progress.emit(i)
                
            self.finished.emit(dirs, self.path, True)
        except Exception as e:
            print(f"Directory worker error: {e}")
            self.finished.emit([], self.path, False)


class RemoteDirectoryDialog(QDialog):
    def __init__(self, slurm_connection, initial_path="/home/", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Browse Remote Directory")
        self.setMinimumSize(600, 400)
        self.slurm_connection = slurm_connection
        self.current_remote_path = initial_path
        self.selected_path = initial_path
        self.all_directories = []
        self.worker = None
        
        # Cache directory listings to prevent repeated network calls
        self.directory_cache = {}
        
        self._setup_stylesheet()
        self._setup_ui()
        
        # Start loading initial path
        self._load_current_path()
        
    def _setup_stylesheet(self):
        self.HOVER_DARK_BG = "#3a3d4d"
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLOR_DARK_BG};
                color: {COLOR_DARK_FG};
            }}
            QLineEdit, QListView {{
                background-color: {COLOR_DARK_BG_ALT};
                color: {COLOR_DARK_FG};
                border: 1px solid {COLOR_DARK_BORDER};
                border-radius: 4px;
                padding: 8px;
            }}
            QPushButton, QToolButton {{
                background-color: {COLOR_DARK_BORDER};
                color: {COLOR_DARK_FG};
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover, QToolButton:hover {{
                background-color: {self.HOVER_DARK_BG};
            }}
            QPushButton[objectName="selectBtn"] {{
                background-color: {COLOR_BLUE};
                color: #000000;
            }}
            QPushButton[objectName="selectBtn"]:hover {{
                background-color: #c4f5ff;
            }}
            QListView::item:selected {{
                background-color: {COLOR_BLUE};
                color: #000000;
            }}
            QProgressBar {{
                border: 1px solid {COLOR_DARK_BORDER};
                border-radius: 4px;
                text-align: center;
                background-color: {COLOR_DARK_BG_ALT};
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_BLUE};
                border-radius: 3px;
            }}
        """)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # Navigation bar
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(5)
        
        self.up_button = QToolButton()
        self.up_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "prev_folder.svg")))
        self.up_button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))  # Set larger icon size
        self.up_button.setToolTip("Go Up")
        self.up_button.clicked.connect(self._go_up_directory)
        self.up_button.setFixedSize(QSize(BUTTON_SIZE, BUTTON_SIZE))  # Increase button size
        nav_layout.addWidget(self.up_button)

        # Home button
        self.home_button = QToolButton()
        self.home_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "home.svg")))
        self.home_button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))  # Set larger icon size
        self.home_button.setToolTip("Go to Home Directory")
        self.home_button.clicked.connect(self._go_home)
        self.home_button.setFixedSize(QSize(BUTTON_SIZE, BUTTON_SIZE))  # Increase button size
        nav_layout.addWidget(self.home_button)

        # Refresh button
        self.refresh_button = QToolButton()
        self.refresh_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "refresh.svg")))
        self.refresh_button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))  # Set larger icon size
        self.refresh_button.setToolTip("Refresh")
        self.refresh_button.clicked.connect(self._refresh)
        self.refresh_button.setFixedSize(QSize(BUTTON_SIZE, BUTTON_SIZE))  # Increase button size
        nav_layout.addWidget(self.refresh_button)
        
        # Path display
        path_label = QLabel("Path:")
        nav_layout.addWidget(path_label)
        
        self.path_display_edit = QLineEdit(self.current_remote_path)
        self.path_display_edit.returnPressed.connect(self._path_entered)
        nav_layout.addWidget(self.path_display_edit)
        
        main_layout.addLayout(nav_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Search/filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter directories...")
        self.search_input.textChanged.connect(self._filter_directories)
        self.search_input.setClearButtonEnabled(True)
        filter_layout.addWidget(self.search_input)
        main_layout.addLayout(filter_layout)
        
        # Directory list
        self.dir_list_model = QStandardItemModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.dir_list_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        
        self.dir_list_view = QListView()
        self.dir_list_view.setModel(self.proxy_model)
        self.dir_list_view.clicked.connect(self._on_item_clicked)
        self.dir_list_view.doubleClicked.connect(self._on_item_double_clicked)
        main_layout.addWidget(self.dir_list_view)
        
        # Status label
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.select_button = QPushButton("Select")
        self.select_button.setObjectName("selectBtn")
        self.select_button.clicked.connect(self._select_directory)
        button_layout.addWidget(self.select_button)
        
        main_layout.addLayout(button_layout)

    def _load_current_path(self):
        """Load directory contents in a background thread"""
        self.dir_list_model.clear()
        self.path_display_edit.setText(self.current_remote_path)
        self.search_input.clear()
        
        # Check connection
        if not self.slurm_connection.check_connection():
            item = QStandardItem("Not connected to SLURM.")
            item.setEnabled(False)
            self.dir_list_model.appendRow(item)
            self.status_label.setText("Error: Not connected to SLURM")
            return
            
        # Show loading progress
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"Loading {self.current_remote_path}...")
        
        # Check cache first
        if self.current_remote_path in self.directory_cache:
            dirs = self.directory_cache[self.current_remote_path]
            self._process_directory_results(dirs, self.current_remote_path, True)
            return
            
        # Create and start worker
        self.worker = DirectoryWorker(self.slurm_connection, self.current_remote_path)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self._process_directory_results)
        self.worker.start()

    def _process_directory_results(self, directories, path, success):
        """Process directory listing results from worker thread"""
        self.progress_bar.setVisible(False)
        
        if path != self.current_remote_path:
            # Path changed while worker was running, ignore results
            return
            
        if not success:
            # Path doesn't exist or access denied
            self.status_label.setText(f"Error: Cannot access {path}")
            
            # Try to recover by going to home or root
            if path != self.slurm_connection.remote_home and self.slurm_connection.remote_home:
                self.current_remote_path = self.slurm_connection.remote_home
                self._load_current_path()
            elif path != "/":
                self.current_remote_path = "/"
                self._load_current_path()
            return
            
        # Cache results
        self.directory_cache[path] = directories
        self.all_directories = directories
        
        # Add parent directory if not at root
        if path != "/":
            up_item = QStandardItem("..")
            up_item.setIcon(QIcon(os.path.join(script_dir, "src_static", "prev_folder.svg")))
            self.dir_list_model.appendRow(up_item)
        
        # Add directories
        if not directories:
            self.status_label.setText(f"Directory {path} is empty")
        else:
            for d in directories:
                item = QStandardItem(d)
                item.setIcon(QIcon(os.path.join(script_dir, "src_static", "folder.svg")))
                self.dir_list_model.appendRow(item)
                
            self.status_label.setText(f"Found {len(directories)} directories")

    def _filter_directories(self, text):
        """Filter directories based on user input"""
        self.proxy_model.setFilterRegularExpression(text)
        
        # Show count of visible items
        visible_count = self.proxy_model.rowCount()
        if text:
            self.status_label.setText(f"Showing {visible_count} directories matching '{text}'")
        else:
            self.status_label.setText(f"Showing all {len(self.all_directories)} directories")

    def _on_item_clicked(self, index):
        """Handle item click in directory list"""
        source_index = self.proxy_model.mapToSource(index)
        item_text = self.dir_list_model.itemFromIndex(source_index).text()
        
        if item_text == "..":
            parent_path = os.path.dirname(self.current_remote_path.rstrip('/'))
            self.selected_path = parent_path if parent_path else "/"
        else:
            self.selected_path = os.path.join(self.current_remote_path, item_text)
            
        self.path_display_edit.setText(self.selected_path)

    def _on_item_double_clicked(self, index):
        """Handle double-click on directory item"""
        source_index = self.proxy_model.mapToSource(index)
        item_text = self.dir_list_model.itemFromIndex(source_index).text()
        
        if item_text == "..":
            self._go_up_directory()
        else:
            new_path = os.path.join(self.current_remote_path, item_text)
            if self.slurm_connection.remote_path_exists(new_path):
                self.current_remote_path = new_path
                self.selected_path = new_path
                self._load_current_path()
            else:
                QMessageBox.warning(self, "Navigation Error",
                                  f"'{new_path}' is not accessible.")

    def _go_up_directory(self):
        """Navigate to parent directory"""
        if self.current_remote_path == "/":
            return
            
        parent_path = os.path.dirname(self.current_remote_path.rstrip('/'))
        if not parent_path:
            parent_path = "/"
            
        if self.slurm_connection.remote_path_exists(parent_path):
            self.current_remote_path = parent_path
            self.selected_path = parent_path
            self._load_current_path()

    def _go_home(self):
        """Navigate to user's home directory"""
        if self.slurm_connection.remote_home:
            home_path = self.slurm_connection.remote_home
            if self.slurm_connection.remote_path_exists(home_path):
                self.current_remote_path = home_path
                self.selected_path = home_path
                self._load_current_path()
        else:
            QMessageBox.warning(self, "Error", "Home directory not found")

    def _refresh(self):
        """Refresh current directory listing"""
        # Remove from cache to force reload
        if self.current_remote_path in self.directory_cache:
            del self.directory_cache[self.current_remote_path]
        self._load_current_path()

    def _path_entered(self):
        """Handle manual path entry"""
        new_path = self.path_display_edit.text().strip()
        if new_path and self.slurm_connection.remote_path_exists(new_path):
            self.current_remote_path = new_path
            self.selected_path = new_path
            self._load_current_path()
        else:
            QMessageBox.warning(self, "Invalid Path", 
                              f"Path '{new_path}' does not exist or is not accessible.")
            self.path_display_edit.setText(self.current_remote_path)

    def _select_directory(self):
        """Select current directory and accept dialog"""
        if self.slurm_connection.remote_path_exists(self.selected_path):
            self.accept()
        else:
            QMessageBox.warning(self, "Invalid Selection", 
                              "Please select a valid directory.")

    def get_selected_directory(self):
        """Return the selected directory path"""
        return self.selected_path