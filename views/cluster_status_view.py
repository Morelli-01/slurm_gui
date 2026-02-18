from core.defaults import *
from core.style import AppStyles


def _clear_layout(layout):
    for i in reversed(range(layout.count())):
        item = layout.takeAt(i)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def _create_partition_separator(partition: str) -> QWidget:
    separator_container = QWidget()
    separator_layout = QHBoxLayout(separator_container)
    separator_layout.setContentsMargins(0, 0, 0, 0)
    separator_layout.setSpacing(8)

    line_style = f"border: none; border-top: 1px dotted {COLOR_DARK_BORDER};"

    left_line = QFrame()
    left_line.setFrameShape(QFrame.Shape.HLine)
    left_line.setStyleSheet(line_style)

    partition_text = str(partition).replace(" ", "_")
    if len(partition_text) > 18:
        short_text = f"{partition_text[:15]}..."
    else:
        short_text = partition_text

    partition_label = QLabel(short_text)
    partition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    partition_label.setStyleSheet(f"color: {COLOR_GRAY}; font-weight: 600;")
    partition_label.setToolTip(partition_text)

    right_line = QFrame()
    right_line.setFrameShape(QFrame.Shape.HLine)
    right_line.setStyleSheet(line_style)

    separator_layout.addWidget(left_line, 1)
    separator_layout.addWidget(partition_label, 0)
    separator_layout.addWidget(right_line, 1)
    return separator_container


class ClusterStatusView(QWidget):
    """View: Handles UI presentation for cluster status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_theme = THEME_DARK
        self.theme_stylesheet = AppStyles.get_cluster_status_styles(self.current_theme)
        self._setup_ui()
        self._apply_styling()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("clusterStatusTabs")
        self.tab_widget.tabBar().setExpanding(True)
        self.tab_widget.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        self.tab_widget.tabBar().setUsesScrollButtons(True)
        self.tab_widget.setMinimumWidth(0)
        self.tab_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.node_status_tab = NodeStatusTabView(parent=self.tab_widget, theme_stylesheet=self.theme_stylesheet)
        self.cpu_usage_tab = CpuUsageTabView(parent=self.tab_widget, theme_stylesheet=self.theme_stylesheet)
        self.ram_usage_tab = RamUsageTabView(parent=self.tab_widget, theme_stylesheet=self.theme_stylesheet)
        self.tab_widget.addTab(self.node_status_tab, "Node")
        self.tab_widget.addTab(self.cpu_usage_tab, "CPU")
        self.tab_widget.addTab(self.ram_usage_tab, "RAM")
        self.tab_widget.setTabToolTip(0, "Node Status")
        self.tab_widget.setTabToolTip(1, "CPU Usage")
        self.tab_widget.setTabToolTip(2, "RAM Usage")
        self.main_layout.addWidget(self.tab_widget, 1)

    def _apply_styling(self):
        self.setStyleSheet(self.theme_stylesheet)
        self.tab_widget.setStyleSheet(self.theme_stylesheet)

    def update_display(self, processed_data: dict):
        if not processed_data.get("is_connected", False):
            self._show_connection_error()
            return

        node_payload = processed_data.get("node_data", {})
        self.node_status_tab.update_content(node_payload)
        self.cpu_usage_tab.update_content(node_payload)
        self.ram_usage_tab.update_content(node_payload)

    def _show_connection_error(self):
        self.node_status_tab.show_connection_error()
        self.cpu_usage_tab.show_connection_error()
        self.ram_usage_tab.show_connection_error()

    def shutdown_ui(self, is_connected=False):
        if not hasattr(self, "_no_connection_panel"):
            self._no_connection_panel = QWidget()
            layout = QVBoxLayout(self._no_connection_panel)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel("No connection")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 22px; color: #EA3323; padding: 60px;")
            layout.addWidget(label)

        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        if not is_connected:
            self.main_layout.addWidget(self._no_connection_panel)
            return

        self.main_layout.addWidget(self.tab_widget, 1)
        self._apply_styling()


class NodeStatusTabView(QWidget):
    """View for displaying node status visualization."""

    def __init__(self, parent=None, theme_stylesheet=None):
        super().__init__(parent)
        self.theme_stylesheet = theme_stylesheet
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(8)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._last_node_status_data = {}

        header_bar = QFrame()
        header_bar.setObjectName("nodeStatusHeaderBar")
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(6, 4, 6, 4)
        header_layout.setSpacing(8)

        section_title = QLabel("Node Status")
        section_title.setObjectName("sectionTitle")
        section_title.setStyleSheet(
            f"font-size: 14pt; font-weight: 700; color: {COLOR_DARK_FG}; margin: 0;"
        )
        header_layout.addWidget(section_title, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header_layout.addStretch(1)

        self.status_key_layout = self._create_status_key_section()
        header_layout.addWidget(
            self.status_key_layout,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        self.main_layout.addWidget(header_bar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(6)

        self.node_status_grid_layout = QGridLayout()
        self.node_status_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.node_status_grid_layout.setHorizontalSpacing(4)
        self.node_status_grid_layout.setVerticalSpacing(6)

        self.scroll_layout.addLayout(self.node_status_grid_layout)
        self.scroll_layout.addStretch(1)
        self.scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll_area, 1)

    def _create_status_key_section(self):
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        status_key_layout = QGridLayout(container)
        status_key_layout.setContentsMargins(0, 0, 0, 0)
        status_key_layout.setHorizontalSpacing(8)
        status_key_layout.setVerticalSpacing(2)

        key_items = [
            ("prod_used", "Prod", "Used GPU for prod"),
            ("stud_used", "Stud", "Used GPU by students"),
            ("available", "Free", "Available GPU"),
            ("unavailable", "Down", "Unavailable node/GPU"),
            ("reserved", "Resv", "Reserved node/GPU"),
        ]

        for idx, (color_name, text, tooltip) in enumerate(key_items):
            row = idx // 3
            col = idx % 3

            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(4)

            color_widget = QWidget()
            color_widget.setFixedSize(QSize(12, 12))
            color_widget.setObjectName("coloredBlock")
            color_widget.setProperty("data-state", color_name.lower())
            color_widget.setToolTip(tooltip)

            text_label = QLabel(text)
            text_label.setStyleSheet(f"color: {COLOR_DARK_FG}; font-size: 11px;")
            text_label.setToolTip(tooltip)

            item_layout.addWidget(color_widget, 0, Qt.AlignmentFlag.AlignVCenter)
            item_layout.addWidget(text_label, 0, Qt.AlignmentFlag.AlignVCenter)
            status_key_layout.addWidget(item_widget, row, col)

        return container

    def _compute_max_blocks_per_row(self) -> int:
        """Fit blocks to available width, never exceeding 8 per row."""
        viewport_width = self.scroll_area.viewport().width()
        if viewport_width <= 0:
            viewport_width = max(200, self.width())

        name_column_width = 124
        block_size = 14
        block_spacing = self.node_status_grid_layout.horizontalSpacing() or 4
        side_padding = 20

        usable_width = max(1, viewport_width - name_column_width - side_padding)
        blocks_fit = (usable_width + block_spacing) // (block_size + block_spacing)
        return max(1, min(8, int(blocks_fit)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._last_node_status_data:
            QTimer.singleShot(0, lambda: self.update_content(self._last_node_status_data))

    def update_content(self, node_status_data: dict):
        self._last_node_status_data = node_status_data or {}
        nodes = node_status_data.get("nodes", []) if node_status_data else []
        _clear_layout(self.node_status_grid_layout)

        if not nodes:
            self.show_info_message("No node data available.")
            return

        max_blocks_per_row = self._compute_max_blocks_per_row()
        current_row = 0
        previous_partition = None

        for node_data in nodes:
            partition = node_data.get("Partitions", "")
            if partition != previous_partition:
                previous_partition = partition
                separator = _create_partition_separator(partition)
                self.node_status_grid_layout.addWidget(separator, current_row, 0, 1, max_blocks_per_row + 2)
                current_row += 1

            full_node_name = str(node_data.get("NodeName", ""))
            name_label = QLabel(full_node_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_label.setMinimumWidth(64)
            name_label.setMaximumWidth(114)
            name_label.setToolTip(full_node_name)
            name_label.setText(
                QFontMetrics(name_label.font()).elidedText(
                    full_node_name, Qt.TextElideMode.ElideRight, 110
                )
            )
            self.node_status_grid_layout.addWidget(name_label, current_row, 0)

            block_states = node_data.get("block_states", [])
            tooltips = node_data.get("tooltips", [])

            for index, block_state in enumerate(block_states):
                row = current_row + (index // max_blocks_per_row)
                col = 1 + (index % max_blocks_per_row)

                block_widget = QWidget()
                block_widget.setFixedSize(QSize(14, 14))
                block_widget.setObjectName("coloredBlock")
                block_widget.setProperty("data-state", block_state)
                if index < len(tooltips):
                    block_widget.setToolTip(tooltips[index] or "")
                self.node_status_grid_layout.addWidget(block_widget, row, col)

            used_rows = max(1, (len(block_states) + max_blocks_per_row - 1) // max_blocks_per_row)
            current_row += used_rows

        self.node_status_grid_layout.setColumnStretch(max_blocks_per_row + 2, 1)
        self.node_status_grid_layout.setRowStretch(current_row + 1, 1)

    def show_info_message(self, message: str):
        _clear_layout(self.node_status_grid_layout)
        info_label = QLabel(message)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet(f"color: {COLOR_GRAY}; font-size: 14px; padding: 30px;")
        self.node_status_grid_layout.addWidget(info_label, 0, 0, 1, -1)

    def show_connection_error(self):
        self.show_info_message("⚠️ Unavailable Connection\n\nPlease check SLURM connection")


class CpuUsageTabView(QWidget):
    """View for displaying CPU usage visualization."""

    def __init__(self, parent=None, theme_stylesheet=None):
        super().__init__(parent)
        self.theme_stylesheet = theme_stylesheet
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        section_title = QLabel("CPU Usage per Node")
        section_title.setObjectName("sectionTitle")
        self.main_layout.addWidget(section_title)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(6)

        self.usage_grid_layout = QGridLayout()
        self.usage_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.usage_grid_layout.setHorizontalSpacing(10)
        self.usage_grid_layout.setVerticalSpacing(6)

        self.scroll_layout.addLayout(self.usage_grid_layout)
        self.scroll_layout.addStretch(1)
        self.scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll_area, 1)

    def update_content(self, cpu_usage_data: dict):
        nodes = cpu_usage_data.get("nodes", []) if cpu_usage_data else []
        _clear_layout(self.usage_grid_layout)

        if not nodes:
            self.show_info_message("No CPU data available.")
            return

        current_row = 0
        previous_partition = None
        for node_data in nodes:
            partition = node_data.get("Partitions", "")
            if partition != previous_partition:
                previous_partition = partition
                self.usage_grid_layout.addWidget(_create_partition_separator(partition), current_row, 0, 1, 3)
                current_row += 1

            node_name = node_data.get("NodeName", "")
            total_cpu = int(node_data.get("total_cpu", 0))
            alloc_cpu = int(node_data.get("alloc_cpu", 0))
            cpu_usage_percent = float(node_data.get("cpu_usage_percent", 0.0))

            name_label = QLabel(str(node_name))
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_label.setMinimumWidth(140)

            progress_bar = QProgressBar()
            progress_bar.setObjectName("cpuUsageBar")
            progress_bar.setValue(int(cpu_usage_percent))
            progress_bar.setFormat(f"{alloc_cpu}/{total_cpu} ({cpu_usage_percent:.1f}%)")
            progress_bar.setFixedHeight(20)

            if cpu_usage_percent >= 90:
                progress_bar.setProperty("crit", "true")
            elif cpu_usage_percent >= 70:
                progress_bar.setProperty("warn", "true")
            else:
                progress_bar.setProperty("crit", "false")
                progress_bar.setProperty("warn", "false")

            self.usage_grid_layout.addWidget(name_label, current_row, 0)
            self.usage_grid_layout.addWidget(progress_bar, current_row, 1)
            current_row += 1

        self.usage_grid_layout.setColumnStretch(0, 0)
        self.usage_grid_layout.setColumnStretch(1, 1)
        self.usage_grid_layout.setRowStretch(current_row + 1, 1)

    def show_info_message(self, message: str):
        _clear_layout(self.usage_grid_layout)
        info_label = QLabel(message)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet(f"color: {COLOR_GRAY}; font-size: 14px; padding: 30px;")
        self.usage_grid_layout.addWidget(info_label, 0, 0, 1, -1)

    def show_connection_error(self):
        self.show_info_message("⚠️ Unavailable Connection\n\nPlease check SLURM connection")


class RamUsageTabView(QWidget):
    """View for displaying RAM usage visualization."""

    def __init__(self, parent=None, theme_stylesheet=None):
        super().__init__(parent)
        self.theme_stylesheet = theme_stylesheet
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(10)

        section_title = QLabel("RAM Usage per Node")
        section_title.setObjectName("sectionTitle")
        self.main_layout.addWidget(section_title)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(6)

        self.usage_grid_layout = QGridLayout()
        self.usage_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.usage_grid_layout.setHorizontalSpacing(10)
        self.usage_grid_layout.setVerticalSpacing(6)

        self.scroll_layout.addLayout(self.usage_grid_layout)
        self.scroll_layout.addStretch(1)
        self.scroll_area.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll_area, 1)

    def update_content(self, ram_usage_data: dict):
        nodes = ram_usage_data.get("nodes", []) if ram_usage_data else []
        _clear_layout(self.usage_grid_layout)

        if not nodes:
            self.show_info_message("No RAM data available.")
            return

        current_row = 0
        previous_partition = None
        for node_data in nodes:
            partition = node_data.get("Partitions", "")
            if partition != previous_partition:
                previous_partition = partition
                self.usage_grid_layout.addWidget(_create_partition_separator(partition), current_row, 0, 1, 3)
                current_row += 1

            node_name = node_data.get("NodeName", "")
            total_mem_bytes = int(node_data.get("total_mem_mb", 0))
            alloc_mem_bytes = int(node_data.get("alloc_mem_mb", 0))
            ram_usage_percent = float(node_data.get("ram_usage_percent", 0.0))

            name_label = QLabel(str(node_name))
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_label.setMinimumWidth(140)

            total_mem_display = self._format_bytes_short(total_mem_bytes)
            alloc_mem_display = self._format_bytes_short(alloc_mem_bytes)

            progress_bar = QProgressBar()
            progress_bar.setObjectName("ramUsageBar")
            progress_bar.setValue(int(ram_usage_percent))
            progress_bar.setFormat(f"{alloc_mem_display}/{total_mem_display} ({ram_usage_percent:.1f}%)")
            progress_bar.setFixedHeight(20)

            if ram_usage_percent >= 90:
                progress_bar.setProperty("crit", "true")
            elif ram_usage_percent >= 70:
                progress_bar.setProperty("warn", "true")
            else:
                progress_bar.setProperty("crit", "false")
                progress_bar.setProperty("warn", "false")

            self.usage_grid_layout.addWidget(name_label, current_row, 0)
            self.usage_grid_layout.addWidget(progress_bar, current_row, 1)
            current_row += 1

        self.usage_grid_layout.setColumnStretch(0, 0)
        self.usage_grid_layout.setColumnStretch(1, 1)
        self.usage_grid_layout.setRowStretch(current_row + 1, 1)

    def show_info_message(self, message: str):
        _clear_layout(self.usage_grid_layout)
        info_label = QLabel(message)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet(f"color: {COLOR_GRAY}; font-size: 14px; padding: 30px;")
        self.usage_grid_layout.addWidget(info_label, 0, 0, 1, -1)

    def show_connection_error(self):
        self.show_info_message("⚠️ Unavailable Connection\n\nPlease check SLURM connection")

    def _format_bytes_short(self, value: int) -> str:
        value = max(0, int(value))
        units = ["B", "K", "M", "G", "T", "P"]
        idx = 0
        scaled = float(value)
        while scaled >= 1024 and idx < len(units) - 1:
            scaled /= 1024.0
            idx += 1
        if idx == 0:
            return f"{int(scaled)}{units[idx]}"
        return f"{scaled:.1f}{units[idx]}"
