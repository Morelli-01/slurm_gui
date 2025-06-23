from PyQt6.QtWidgets import QTableView
from core.defaults import *
from PyQt6.QtCore import QAbstractTableModel, QSortFilterProxyModel, Qt
import traceback
from typing import Dict


class JobQueueView(QTableView):  # Changed from QWidget
    """View: Handles table display using the high-performance QTableView."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shutdown_panel = None
        self._setup_table_properties()

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
        source_model = self.model().sourceModel()
        for i in range(source_model.columnCount()):
             header_name = source_model.headerData(i, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
             is_visible = displayable_fields.get(header_name, True)
             self.setColumnHidden(i, not is_visible)
             if is_visible:
                 if header_name == "Job Name":
                    self.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
                 else:
                    self.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)


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