from pathlib import Path
from PyQt6.QtWidgets import QTableView
from core.defaults import *
from PyQt6.QtCore import QAbstractTableModel, QSettings, QSortFilterProxyModel, Qt, QTimer
from utils import settings_path
import traceback
from typing import Dict


class JobQueueView(QTableView):  # Changed from QWidget
    """View: Handles table display using the high-performance QTableView."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shutdown_panel = None
        self._setup_table_properties()
        self._setup_column_width_persistence()

    def _setup_table_properties(self):
        """Setup table properties with cell selection and copy functionality"""
        # --- MODIFICATION: Allow item (cell) selection ---
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.setMinimumHeight(200)

        # --- MODIFICATION: Restore the context menu ---
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, position):
        """Show context menu for copying cell values."""
        menu = QMenu(self)

        copy_action = QAction("Copy", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(self._copy_selected_cells)
        menu.addAction(copy_action)
        
        copy_row_action = QAction("Copy Row", self)
        copy_row_action.triggered.connect(self._copy_selected_row)
        menu.addAction(copy_row_action)
        
        select_column_action = QAction("Select Column", self)
        select_column_action.triggered.connect(self._select_column)
        menu.addAction(select_column_action)
        
        menu.exec(self.mapToGlobal(position))

    def _copy_selected_cells(self):
        """Copy selected cell values to clipboard."""
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return

        rows_data = {}
        for index in indexes:
            row, col = index.row(), index.column()
            if row not in rows_data:
                rows_data[row] = {}
            rows_data[row][col] = index.data(Qt.ItemDataRole.DisplayRole)

        clipboard_text = []
        for row in sorted(rows_data.keys()):
            row_data = rows_data[row]
            row_text = "\t".join(row_data[col] for col in sorted(row_data.keys()))
            clipboard_text.append(row_text)

        QApplication.clipboard().setText("\n".join(clipboard_text))

    def _copy_selected_row(self):
        """Copy entire selected row(s) to clipboard."""
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return

        selected_rows = sorted(list(set(index.row() for index in indexes)))
        
        clipboard_text = []
        model = self.model() # Get the underlying model (could be the proxy model)
        
        for row in selected_rows:
            row_data = []
            for col in range(model.columnCount()):
                # Get the index for the specific cell in the row
                index = model.index(row, col)
                cell_data = index.data(Qt.ItemDataRole.DisplayRole) or ""
                row_data.append(str(cell_data))
            clipboard_text.append("\t".join(row_data))
            
        QApplication.clipboard().setText("\n".join(clipboard_text))

    def _select_column(self):
        """Select the entire column of the currently selected cell."""
        current_index = self.currentIndex()
        if current_index.isValid():
            self.selectColumn(current_index.column())

    def setup_columns(self, displayable_fields: Dict[str, bool]):
        """Hides or shows columns based on settings."""
        header = self.horizontalHeader()
        self._applying_widths = True
        try:
            # Interactive mode lets the user drag column borders to resize them
            # (double-clicking a border still auto-fits the column to its content).
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setMinimumSectionSize(40)
            source_model = self.model().sourceModel()
            for i in range(source_model.columnCount()):
                 header_name = source_model.headerData(i, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
                 is_visible = displayable_fields.get(header_name, True)
                 self.setColumnHidden(i, not is_visible)
        finally:
            self._applying_widths = False

    # --- Column widths ---

    def _setup_column_width_persistence(self):
        """Persist user-adjusted column widths to the local settings file."""
        self._applying_widths = False
        self._widths_initialized = False
        self._save_widths_timer = QTimer(self)
        self._save_widths_timer.setSingleShot(True)
        self._save_widths_timer.setInterval(400)
        self._save_widths_timer.timeout.connect(self.save_column_widths)
        self.horizontalHeader().sectionResized.connect(self._on_section_resized)
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._flush_pending_width_save)

    def _column_name(self, logical_index: int) -> str:
        return self.model().headerData(logical_index, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)

    def _last_visible_section(self) -> int:
        header = self.horizontalHeader()
        for visual in reversed(range(header.count())):
            logical = header.logicalIndex(visual)
            if not header.isSectionHidden(logical):
                return logical
        return -1

    def _on_section_resized(self, logical_index: int, old_size: int, new_size: int):
        # Ignore programmatic resizes and the stretched last column, whose
        # width just follows the window size.
        if self._applying_widths or not self._widths_initialized:
            return
        if self.horizontalHeader().stretchLastSection() and logical_index == self._last_visible_section():
            return
        self._save_widths_timer.start()

    def _flush_pending_width_save(self):
        if self._save_widths_timer.isActive():
            self._save_widths_timer.stop()
            self.save_column_widths()

    def _widths_settings(self) -> QSettings:
        return QSettings(str(Path(settings_path)), QSettings.Format.IniFormat)

    def save_column_widths(self):
        """Store the width of each visible column, keyed by column name."""
        header = self.horizontalHeader()
        last_visible = self._last_visible_section() if header.stretchLastSection() else -1
        settings = self._widths_settings()
        settings.beginGroup(JOB_QUEUE_COLUMN_WIDTHS_GROUP)
        for i in range(header.count()):
            if header.isSectionHidden(i) or i == last_visible:
                continue
            settings.setValue(self._column_name(i), header.sectionSize(i))
        settings.endGroup()
        settings.sync()

    def fit_columns_to_contents(self, max_width: int = 350):
        """Size columns to their content, capping overly wide ones."""
        self.resizeColumnsToContents()
        header = self.horizontalHeader()
        for i in range(header.count()):
            if header.sectionSize(i) > max_width:
                header.resizeSection(i, max_width)

    def ensure_column_widths(self):
        """Apply initial widths once: saved user widths, else fit to content.

        Called on every data load but only acts the first time, so later
        refreshes don't override widths the user has adjusted manually.
        """
        if self._widths_initialized:
            return
        settings = self._widths_settings()
        settings.beginGroup(JOB_QUEUE_COLUMN_WIDTHS_GROUP)
        saved = {key: settings.value(key, 0, type=int) for key in settings.childKeys()}
        settings.endGroup()

        header = self.horizontalHeader()
        self._applying_widths = True
        try:
            self.fit_columns_to_contents()
            for i in range(header.count()):
                width = saved.get(self._column_name(i), 0)
                if width > 0:
                    header.resizeSection(i, max(width, header.minimumSectionSize()))
        finally:
            self._applying_widths = False
        self._widths_initialized = True

    def reset_column_widths(self):
        """Forget saved column widths and go back to the default fit-to-content."""
        self._save_widths_timer.stop()
        settings = self._widths_settings()
        settings.remove(JOB_QUEUE_COLUMN_WIDTHS_GROUP)
        settings.sync()
        self._widths_initialized = False
        if self.model() is not None and self.model().rowCount() > 0:
            self.ensure_column_widths()


    def shutdown_ui(self, is_connected=False):
        """Show/hide the table based on connection status."""
        if not is_connected:
            if not self._shutdown_panel:
                self._shutdown_panel = QWidget(self.parent())
                layout = QVBoxLayout(self._shutdown_panel)
                layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label = QLabel("No connection")
                label.setStyleSheet("font-size: 22px; color: #EA3323; padding: 60px;")
                layout.addWidget(label)
                
                parent_layout = self.parent().layout()
                if parent_layout:
                    parent_layout.replaceWidget(self, self._shutdown_panel)
                self.setVisible(False)
                self._shutdown_panel.setVisible(True)

        elif self._shutdown_panel:
            parent_layout = self.parent().layout()
            if parent_layout:
                parent_layout.replaceWidget(self._shutdown_panel, self)
            self._shutdown_panel.setVisible(False)
            self.setVisible(True)
            self._shutdown_panel.deleteLater()
            self._shutdown_panel = None