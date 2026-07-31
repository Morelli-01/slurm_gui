"""
Remote Directory Panel - Refactored with a modern MVC approach.
Features asynchronous directory loading, a breadcrumb trail, a favorites/recents
sidebar, inline folder creation, and an intuitive, unified path/filter bar.
"""

import os
import posixpath
import re
from typing import List, Optional

from PyQt6.QtCore import (QObject, QThread, pyqtSignal, Qt, QSize,
                          QSortFilterProxyModel, QSettings)
from PyQt6.QtGui import QIcon, QStandardItemModel, QStandardItem, QColor, QShortcut, QKeySequence
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListView,
                             QLineEdit, QToolButton, QProgressBar, QLabel,
                             QDialogButtonBox, QAbstractItemView, QSplitter,
                             QWidget, QListWidget, QListWidgetItem, QMenu,
                             QInputDialog, QScrollArea, QFrame, QSizePolicy)

from core.slurm_api import SlurmAPI, ConnectionState
from core.style import AppStyles
from core.defaults import COLOR_DARK_BORDER, COLOR_RED
from utils import script_dir, settings_path
from widgets.toast_widget import show_error_toast, show_warning_toast, show_success_toast

# --- Constants ---
UP_DIRECTORY_TEXT = ".."
HOME_ICON_PATH = os.path.join(script_dir, "src_static", "home.svg")
UP_ICON_PATH = os.path.join(script_dir, "src_static", "prev_folder.svg")
REFRESH_ICON_PATH = os.path.join(script_dir, "src_static", "refresh.svg")
FOLDER_ICON_PATH = os.path.join(script_dir, "src_static", "folder.svg")
STAR_ICON_PATH = os.path.join(script_dir, "src_static", "star.svg")
CLOCK_ICON_PATH = os.path.join(script_dir, "src_static", "clock.svg")
NEW_FOLDER_ICON_PATH = os.path.join(script_dir, "src_static", "new_folder.svg")

SETTINGS_GROUP = "RemoteBrowser"
VALID_FOLDER_NAME_RE = re.compile(r'^[\w][\w .\-]*$')


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
# BOOKMARKS (favorites / recently visited paths, persisted across sessions)
# ============================================================================

class BookmarkStore:
    """Persists favorite and recently visited remote paths in the app settings."""
    MAX_RECENTS = 8

    def get_favorites(self) -> List[str]:
        return self._read_list("favorites")

    def set_favorites(self, favorites: List[str]):
        self._write_list("favorites", favorites)

    def get_recents(self) -> List[str]:
        return self._read_list("recents")

    def set_recents(self, recents: List[str]):
        self._write_list("recents", recents[:self.MAX_RECENTS])

    def add_recent(self, path: str):
        recents = [p for p in self.get_recents() if p != path]
        recents.insert(0, path)
        self.set_recents(recents)

    def remove_recent(self, path: str):
        self.set_recents([p for p in self.get_recents() if p != path])

    def toggle_favorite(self, path: str) -> bool:
        """Adds/removes path from favorites. Returns True if it is now a favorite."""
        favorites = self.get_favorites()
        if path in favorites:
            favorites.remove(path)
            self.set_favorites(favorites)
            return False
        favorites.append(path)
        self.set_favorites(favorites)
        return True

    def remove_favorite(self, path: str):
        self.set_favorites([p for p in self.get_favorites() if p != path])

    def is_favorite(self, path: str) -> bool:
        return path in self.get_favorites()

    def _read_list(self, key: str) -> List[str]:
        settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
        settings.beginGroup(SETTINGS_GROUP)
        value = settings.value(key, [])
        settings.endGroup()
        if not value:
            return []
        if isinstance(value, str):
            return [value]
        return [str(v) for v in value if v]

    def _write_list(self, key: str, values: List[str]):
        settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
        settings.beginGroup(SETTINGS_GROUP)
        settings.setValue(key, values)
        settings.endGroup()


# ============================================================================
# MODEL (Handles data and state logic)
# ============================================================================

class RemoteDirectoryModel(QObject):
    """Manages the state and data for the remote directory browser."""
    path_changed = pyqtSignal(str)
    directories_changed = pyqtSignal(list)
    status_changed = pyqtSignal(str)
    loading_state_changed = pyqtSignal(bool)
    error_state_changed = pyqtSignal(bool)
    load_succeeded = pyqtSignal(str)

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
            self.error_state_changed.emit(True)
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
            self.error_state_changed.emit(False)
            self.directories_changed.emit(cached_dirs)
            self.status_changed.emit(f"{len(cached_dirs)} items")
            self.load_succeeded.emit(self._current_path)
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
        self.error_state_changed.emit(False)
        self.directories_changed.emit(directories)
        self.status_changed.emit(f"{len(directories)} items")
        self.load_succeeded.emit(self._current_path)

    def _on_load_error(self, error_message: str):
        self.error_state_changed.emit(True)
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
        self.bookmarks = BookmarkStore()
        self._connect_signals()
        self._rebuild_sidebar()

    def _connect_signals(self):
        # Model -> View connections
        self.model.path_changed.connect(self.view.path_edit.setText)
        self.model.path_changed.connect(self.view.breadcrumb.set_path)
        self.model.path_changed.connect(self._on_path_changed)
        self.model.directories_changed.connect(self.view.update_list_view)
        self.model.status_changed.connect(self.view.status_label.setText)
        self.model.loading_state_changed.connect(self.view.set_loading_state)
        self.model.error_state_changed.connect(self.view.set_error_state)
        self.model.load_succeeded.connect(self._on_load_succeeded)

        # View -> Controller/Model connections
        self.view.up_button.clicked.connect(self.model.navigate_up)
        self.view.home_button.clicked.connect(self.model.go_home)
        self.view.refresh_button.clicked.connect(self.model.refresh)
        self.view.favorite_button.clicked.connect(self._on_toggle_favorite)
        self.view.new_folder_button.clicked.connect(self._on_new_folder)
        self.view.path_edit.textChanged.connect(self._on_path_text_changed)
        self.view.path_edit.returnPressed.connect(self._on_path_return_pressed)
        self.view.list_view.activated.connect(self._on_item_activated)
        self.view.breadcrumb.path_clicked.connect(self.model.set_path)
        self.view.sidebar.itemClicked.connect(self._on_sidebar_item_clicked)
        self.view.sidebar.customContextMenuRequested.connect(self._on_sidebar_context_menu)
        self.view.up_shortcut.activated.connect(self.model.navigate_up)
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

        # Apply the filter (treated as a literal substring, not a regex)
        self.view.proxy_model.setFilterFixedString(filter_term)

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
        """Handles double-clicking (or pressing Enter on) an item in the list."""
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

    def _on_path_changed(self, path: str):
        self.view.favorite_button.setChecked(self.bookmarks.is_favorite(path.rstrip('/') + '/'))

    def _on_load_succeeded(self, path: str):
        self.bookmarks.add_recent(path)
        self._rebuild_sidebar()

    def _rebuild_sidebar(self):
        self.view.populate_sidebar(
            home_path=self.model.slurm_api.remote_home,
            favorites=self.bookmarks.get_favorites(),
            recents=self.bookmarks.get_recents(),
        )

    def _on_sidebar_item_clicked(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.model.set_path(path)

    def _on_sidebar_context_menu(self, pos):
        item = self.view.sidebar.itemAt(pos)
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        section = item.data(Qt.ItemDataRole.UserRole + 1)
        if not path or section not in ("favorite", "recent"):
            return

        menu = QMenu(self.view)
        label = "Remove from Favorites" if section == "favorite" else "Remove from Recent"
        action = menu.addAction(label)
        chosen = menu.exec(self.view.sidebar.mapToGlobal(pos))
        if chosen != action:
            return

        if section == "favorite":
            self.bookmarks.remove_favorite(path)
        else:
            self.bookmarks.remove_recent(path)
        self._rebuild_sidebar()
        self._on_path_changed(self.model.current_path)

    def _on_toggle_favorite(self):
        path = self.model.current_path
        is_favorite = self.bookmarks.toggle_favorite(path)
        self.view.favorite_button.setChecked(is_favorite)
        self._rebuild_sidebar()

    def _on_new_folder(self):
        if self.model.slurm_api.connection_status != ConnectionState.CONNECTED:
            show_warning_toast(self.view, "Not Connected", "Connect to the cluster first.")
            return

        name, ok = QInputDialog.getText(self.view, "New Folder", "Folder name:")
        if not ok:
            return
        name = name.strip()
        if not name or not VALID_FOLDER_NAME_RE.match(name):
            show_warning_toast(
                self.view, "Invalid Name",
                "Folder name may only contain letters, numbers, spaces, dots, dashes and underscores."
            )
            return

        new_path = posixpath.join(self.model.current_path, name)
        success, error = self.model.slurm_api.create_remote_directory(new_path)
        if success:
            show_success_toast(self.view, "Folder Created", f"'{name}' was created.")
            self.model.set_path(new_path, force_refresh=True)
        else:
            show_error_toast(self.view, "Failed to Create Folder", error or "Unknown error")

# ============================================================================
# BREADCRUMB BAR
# ============================================================================

class BreadcrumbBar(QScrollArea):
    """A horizontal, clickable trail of path segments for quick navigation."""
    path_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(36)

        container = QWidget()
        self._layout = QHBoxLayout(container)
        self._layout.setContentsMargins(4, 2, 4, 2)
        self._layout.setSpacing(0)
        self.setWidget(container)

    def set_path(self, path: str):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        parts = [p for p in path.strip('/').split('/') if p]

        self._layout.addWidget(self._make_segment("/", "/", is_last=not parts))

        accumulated = ""
        for i, part in enumerate(parts):
            accumulated += "/" + part
            separator = QLabel("/")
            separator.setObjectName("breadcrumbSeparator")
            self._layout.addWidget(separator)
            self._layout.addWidget(self._make_segment(part, accumulated + "/", is_last=(i == len(parts) - 1)))

        self._layout.addStretch(1)
        # Scroll so the current (rightmost) segment is visible once layout settles.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.horizontalScrollBar().setValue(self.horizontalScrollBar().maximum()))

    def _make_segment(self, text: str, full_path: str, is_last: bool) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setAutoRaise(True)
        button.setObjectName("breadcrumbSegmentCurrent" if is_last else "breadcrumbSegment")
        if is_last:
            button.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, p=full_path: self.path_clicked.emit(p))
        return button


# ============================================================================
# VIEW (The dialog window)
# ============================================================================

class RemoteDirectoryDialog(QDialog):
    """A clean, responsive remote directory browser dialog with quick-access sidebar."""

    def __init__(self, initial_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.slurm_api = SlurmAPI()
        self.model = RemoteDirectoryModel(self.slurm_api, initial_path)

        self._init_ui()
        self._restore_geometry()
        self.controller = RemoteDirectoryController(self.model, self)

        # Trigger initial load. Using refresh() (force_refresh=True) rather than
        # set_path() is required here: set_path() no-ops when the target path
        # already equals the current path, which is always true on first load.
        self.model.refresh()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Browse Remote Directory")
        self.setMinimumSize(760, 500)
        self.setStyleSheet(AppStyles.get_complete_stylesheet() + AppStyles.get_remote_browser_styles())

        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, 1)

        # --- Sidebar (Quick Access / Favorites / Recent) ---
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebarList")
        self.sidebar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sidebar.setMinimumWidth(160)
        self.sidebar.setMaximumWidth(260)
        splitter.addWidget(self.sidebar)

        # --- Main content area ---
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(content)
        splitter.setSizes([190, 570])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        # --- Toolbar ---
        toolbar = QHBoxLayout()
        self.up_button = self._create_tool_button(UP_ICON_PATH, "Go Up (Backspace)")
        self.home_button = self._create_tool_button(HOME_ICON_PATH, "Go Home")
        self.refresh_button = self._create_tool_button(REFRESH_ICON_PATH, "Refresh")
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Type a path to navigate or filter...")
        self.new_folder_button = self._create_tool_button(NEW_FOLDER_ICON_PATH, "Create New Folder")
        self.favorite_button = self._create_tool_button(STAR_ICON_PATH, "Toggle Favorite")
        self.favorite_button.setObjectName("favoriteButton")
        self.favorite_button.setCheckable(True)

        toolbar.addWidget(self.up_button)
        toolbar.addWidget(self.home_button)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.path_edit, 1)
        toolbar.addWidget(self.new_folder_button)
        toolbar.addWidget(self.favorite_button)
        content_layout.addLayout(toolbar)

        # --- Breadcrumb Trail ---
        self.breadcrumb = BreadcrumbBar()
        content_layout.addWidget(self.breadcrumb)

        # --- Loading Indicator ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate mode
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        content_layout.addWidget(self.progress_bar)

        # --- Directory List View ---
        self.list_view = QListView()
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_view.setIconSize(QSize(20, 20))
        self.list_model = QStandardItemModel()
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.list_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.list_view.setModel(self.proxy_model)
        content_layout.addWidget(self.list_view, 1)

        # Backspace on the list navigates up, mirroring common file-manager conventions.
        self.up_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self.list_view)
        self.up_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)

        # Ctrl+L focuses the path bar for quick typing, another common convention.
        self.focus_path_shortcut = QShortcut(QKeySequence("Ctrl+L"), self)
        self.focus_path_shortcut.activated.connect(self._focus_path_edit)

        # --- Status Label ---
        self.status_label = QLabel("Initializing...")
        content_layout.addWidget(self.status_label)

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        main_layout.addWidget(self.button_box)

        self._has_error = False

    def _focus_path_edit(self):
        self.path_edit.setFocus()
        self.path_edit.selectAll()

    def _create_tool_button(self, icon_path: str, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setIcon(QIcon(icon_path))
        button.setIconSize(QSize(22, 22))
        button.setToolTip(tooltip)
        button.setFixedSize(32, 32)
        return button

    def populate_sidebar(self, home_path: Optional[str], favorites: List[str], recents: List[str]):
        """Rebuilds the Quick Access / Favorites / Recent sections of the sidebar."""
        self.sidebar.clear()

        self._add_sidebar_header("QUICK ACCESS")
        self._add_sidebar_item("Home", HOME_ICON_PATH, home_path or "/", "quick")
        self._add_sidebar_item("Root", FOLDER_ICON_PATH, "/", "quick")

        if favorites:
            self._add_sidebar_header("FAVORITES")
            for path in favorites:
                item = self._add_sidebar_item(self._display_name(path), STAR_ICON_PATH, path, "favorite")
                item.setToolTip(path)

        if recents:
            self._add_sidebar_header("RECENT")
            for path in recents:
                item = self._add_sidebar_item(self._display_name(path), CLOCK_ICON_PATH, path, "recent")
                item.setToolTip(path)

    @staticmethod
    def _display_name(path: str) -> str:
        return posixpath.basename(path.rstrip('/')) or path

    def _add_sidebar_header(self, text: str):
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = item.font()
        font.setBold(True)
        font.setPointSize(max(8, font.pointSize() - 1))
        item.setFont(font)
        item.setForeground(QColor(COLOR_DARK_BORDER))
        self.sidebar.addItem(item)

    def _add_sidebar_item(self, text: str, icon_path: str, path: str, section: str) -> QListWidgetItem:
        item = QListWidgetItem(QIcon(icon_path), text)
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setData(Qt.ItemDataRole.UserRole + 1, section)
        self.sidebar.addItem(item)
        return item

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

        if not directories and not self._has_error:
            placeholder = QStandardItem("This folder has no subdirectories")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QColor(COLOR_DARK_BORDER))
            font = placeholder.font()
            font.setItalic(True)
            placeholder.setFont(font)
            self.list_model.appendRow(placeholder)

    def set_loading_state(self, is_loading: bool):
        """Shows/hides the progress bar and enables/disables controls."""
        self.progress_bar.setVisible(is_loading)
        self.list_view.setEnabled(not is_loading)
        self.path_edit.setEnabled(not is_loading)
        self.up_button.setEnabled(not is_loading)
        self.home_button.setEnabled(not is_loading)
        self.new_folder_button.setEnabled(not is_loading)

    def set_error_state(self, is_error: bool):
        """Visually flags the status label when the last navigation failed."""
        self._has_error = is_error
        self.status_label.setStyleSheet(f"color: {COLOR_RED}; font-weight: 600;" if is_error else "")

    def get_selected_directory(self) -> str:
        """Public method to retrieve the result of the dialog."""
        return self.path_edit.text().rstrip('/')

    def _restore_geometry(self):
        settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
        settings.beginGroup(SETTINGS_GROUP)
        geometry = settings.value("geometry")
        settings.endGroup()
        if geometry:
            self.restoreGeometry(geometry)

    def done(self, result):
        settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
        settings.beginGroup(SETTINGS_GROUP)
        settings.setValue("geometry", self.saveGeometry())
        settings.endGroup()
        super().done(result)
