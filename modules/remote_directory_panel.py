# In new_job_dp.py, define this class before NewJobDialog
from modules.defaults import *
from utils import script_dir

class RemoteDirectoryDialog(QDialog):
    def __init__(self, slurm_connection, initial_path="/home/", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Browse Remote Directory")
        self.setMinimumSize(600, 400)
        self.slurm_connection = slurm_connection
        self.current_remote_path = initial_path
        self.selected_path = None

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
            QPushButton {{
                background-color: {COLOR_DARK_BORDER};
                color: {COLOR_DARK_FG};
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
            }}
            QPushButton:hover {{
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
        """)

        self._setup_ui()
        self._load_current_path()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Current Path display
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Current Path:"))
        self.path_display_edit = QLineEdit(self.current_remote_path)
        self.path_display_edit.setReadOnly(True)
        path_layout.addWidget(self.path_display_edit)
        main_layout.addLayout(path_layout)

        # Directory list
        self.dir_list_model = QStandardItemModel()
        self.dir_list_view = QListView()
        self.dir_list_view.setModel(self.dir_list_model)
        self.dir_list_view.clicked.connect(self._on_item_clicked)
        self.dir_list_view.doubleClicked.connect(self._on_item_double_clicked)
        main_layout.addWidget(self.dir_list_view)

        # Buttons
        button_layout = QHBoxLayout()
        self.up_button = QPushButton("Up")
        self.up_button.setIcon(QIcon(os.path.join(script_dir, "src_static", "up_arrow.svg")))
        self.up_button.clicked.connect(self._go_up_directory)
        button_layout.addWidget(self.up_button)

        self.select_button = QPushButton("Select")
        self.select_button.setObjectName("selectBtn")
        self.select_button.clicked.connect(self._select_directory)
        button_layout.addWidget(self.select_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)

    def _load_current_path(self):
        self.dir_list_model.clear()
        self.path_display_edit.setText(self.current_remote_path)

        if not self.slurm_connection.check_connection():
            item = QStandardItem("Not connected to SLURM.")
            item.setEnabled(False)
            self.dir_list_model.appendRow(item)
            return

        # Add ".." for parent directory
        if self.current_remote_path != "/":
            up_item = QStandardItem("..")
            up_item.setIcon(QIcon(os.path.join(script_dir, "src_static", "folder_up.svg"))) # You might need a folder-up icon
            self.dir_list_model.appendRow(up_item)


        directories = self.slurm_connection.list_remote_directories(self.current_remote_path)
        if not directories:
            # Check if current_remote_path is a valid directory
            if not self.slurm_connection.remote_path_exists(self.current_remote_path):
                # If the initial_path is invalid, try to go to home directory
                if self.current_remote_path != "/home/" and self.slurm_connection.remote_path_exists("/home/"):
                    self.current_remote_path = "/home/"
                    self._load_current_path()
                    return
                elif self.current_remote_path != "/" and self.slurm_connection.remote_path_exists("/"):
                    self.current_remote_path = "/"
                    self._load_current_path()
                    return
                else:
                    item = QStandardItem("Could not access directory or no subdirectories found.")
                    item.setEnabled(False)
                    self.dir_list_model.appendRow(item)
                    return


        for d in sorted(directories):
            item = QStandardItem(d)
            item.setIcon(QIcon(os.path.join(script_dir, "src_static", "folder.svg"))) # You might need a folder icon
            self.dir_list_model.appendRow(item)

    def _on_item_clicked(self, index):
        item_text = self.dir_list_model.itemFromIndex(index).text()
        if item_text == "..":
            self.selected_path = os.path.dirname(self.current_remote_path.rstrip('/'))
            if not self.selected_path: # Handle root directory case
                self.selected_path = "/"
        else:
            self.selected_path = os.path.join(self.current_remote_path, item_text)


    def _on_item_double_clicked(self, index):
        item_text = self.dir_list_model.itemFromIndex(index).text()
        if item_text == "..":
            self._go_up_directory()
        else:
            new_path = os.path.join(self.current_remote_path, item_text)
            if self.slurm_connection.remote_path_exists(new_path): # Verify it's a directory
                self.current_remote_path = new_path
                self._load_current_path()
            else:
                # Optionally, show an error or just don't navigate if it's not a directory
                print(f"'{new_path}' is not a directory or is inaccessible.")


    def _go_up_directory(self):
        parent_path = os.path.dirname(self.current_remote_path.rstrip('/'))
        if not parent_path: # If we are at root, parent is still root
            parent_path = "/"
        if parent_path != self.current_remote_path:
            self.current_remote_path = parent_path
            self._load_current_path()

    def _select_directory(self):
        if self.selected_path:
            # Ensure the selected path is a directory before accepting
            if self.slurm_connection.remote_path_exists(self.selected_path):
                self.accept()
            else:
                QMessageBox.warning(self, "Invalid Selection", "Please select a valid directory.")
        else:
            # If nothing was explicitly selected, but we are in a valid directory, select current.
            if self.slurm_connection.remote_path_exists(self.current_remote_path):
                self.selected_path = self.current_remote_path
                self.accept()
            else:
                QMessageBox.warning(self, "No Directory Selected", "Please select a directory or navigate to one.")


    def get_selected_directory(self):
        return self.selected_path