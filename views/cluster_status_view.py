from core.defaults import *
from core.style import AppStyles

# VIEW
class ClusterStatusView(QWidget):
    """View: Handles UI presentation for cluster status"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_theme = THEME_DARK
        self.theme_stylesheet = self._get_theme_stylesheet()
        self._setup_ui()
        self._apply_styling()
    
    def _get_theme_stylesheet(self):
        """Get theme stylesheet"""
        return AppStyles.get_cluster_status_styles(self.current_theme)
    
    def _setup_ui(self):
        """Set up the main UI layout"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Create the QTabWidget
        self.tab_widget = QTabWidget()

        # Create the individual tab widgets
        self.node_status_tab = NodeStatusTabView(parent=self.tab_widget, theme_stylesheet=self.theme_stylesheet)
        self.cpu_usage_tab = CpuUsageTabView(parent=self.tab_widget, theme_stylesheet=self.theme_stylesheet)
        self.ram_usage_tab = RamUsageTabView(parent=self.tab_widget, theme_stylesheet=self.theme_stylesheet)

        # Add the tab widgets to the QTabWidget
        self.tab_widget.addTab(self.node_status_tab, "Node Status")
        self.tab_widget.addTab(self.cpu_usage_tab, "CPU Usage")
        self.tab_widget.addTab(self.ram_usage_tab, "RAM Usage")

        # Add the tab widget to the main layout
        self.main_layout.addWidget(self.tab_widget)
    
    def _apply_styling(self):
        """Apply styling to the view"""
        self.setStyleSheet(self.theme_stylesheet)
        self.tab_widget.setStyleSheet(self.theme_stylesheet)
    
    def update_display(self, processed_data: dict):
        """Update all tab displays with processed data"""
        if not processed_data.get('is_connected', False):
            self._show_connection_error()
            return
        
        # Update each tab with its specific data
        self.node_status_tab.update_content(processed_data.get('node_data', {}))
        self.cpu_usage_tab.update_content(processed_data.get('node_data', {}))
        self.ram_usage_tab.update_content(processed_data.get('node_data', {}))
    
    def _show_connection_error(self):
        """Show connection error in all tabs"""
        self.node_status_tab.show_connection_error()
        self.cpu_usage_tab.show_connection_error()
        self.ram_usage_tab.show_connection_error()

    def shutdown_ui(self, is_connected=False):
        """Show only a 'No connection' panel if not connected, else restore normal UI."""
        print(f"i've been called with is_connected: {is_connected}")
        if not hasattr(self, '_no_connection_panel'):
            # Create the no connection panel only once
            self._no_connection_panel = QWidget()
            layout = QVBoxLayout(self._no_connection_panel)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel("No connection")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 22px; color: #EA3323; padding: 60px;")
            layout.addWidget(label)

        # Remove all widgets from main_layout
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        if not is_connected:
            self.main_layout.addWidget(self._no_connection_panel)
        else:
            self.main_layout.addWidget(self.tab_widget)
            self._apply_styling()
        
# Individual Tab Views
class NodeStatusTabView(QWidget):
    """View for displaying node status visualization"""

    def __init__(self, parent=None, theme_stylesheet=None):
        super().__init__(parent)
        self.theme_stylesheet = theme_stylesheet
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI layout"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        # Use QGridLayout for the node status content
        self.node_status_grid_layout = QGridLayout()
        self.node_status_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.node_status_grid_layout.setHorizontalSpacing(3)
        self.node_status_grid_layout.setVerticalSpacing(6)

        # Create title and legend layout
        title_legend_layout = QHBoxLayout()
        title_legend_layout.setContentsMargins(0, 0, 0, 0)
        title_legend_layout.setSpacing(0)

        section_title = QLabel("Node Status")
        section_title.setObjectName("sectionTitle")
        title_legend_layout.addWidget(section_title)

        vertical_separator = QFrame()
        vertical_separator.setObjectName("verticalSeparator")
        vertical_separator.setFrameShape(QFrame.Shape.VLine)
        vertical_separator.setFrameShadow(QFrame.Shadow.Sunken)
        title_legend_layout.addWidget(vertical_separator)

        self.status_key_layout = self._create_status_key_section()
        title_legend_layout.addLayout(self.status_key_layout)

        title_legend_layout.addStretch()
        self.main_layout.addLayout(title_legend_layout)
        self.main_layout.addLayout(self.node_status_grid_layout)
        self.main_layout.addStretch()

    def _create_status_key_section(self):
        """Create the status key legend"""
        status_key_layout = QVBoxLayout()
        status_key_layout.setContentsMargins(0, 0, 0, 0)
        status_key_layout.setSpacing(5)
        
        key_items = [
            ("prod_used", "Used GPU for prod"),
            ("stud_used", "Used GPU by stud"),
            ("available", "Available GPU"),
            ("unavailable", "Unavailable Node/GPU"),
            ("reserved", "Reserved Node/GPU"),
        ]

        for color_name, text in key_items:
            key_row_layout = QHBoxLayout()
            key_row_layout.setContentsMargins(0, 0, 0, 0)
            key_row_layout.setSpacing(8)

            color_widget = QWidget()
            block_size = 16
            color_widget.setFixedSize(QSize(block_size, block_size))
            color_widget.setObjectName("coloredBlock")
            color_widget.setProperty("data-state", color_name.lower())
            
            if self.theme_stylesheet:
                color_widget.setStyleSheet(self.theme_stylesheet)

            key_row_layout.addWidget(color_widget)

            text_label = QLabel(text)
            key_row_layout.addWidget(text_label)
            key_row_layout.addStretch()

            status_key_layout.addLayout(key_row_layout)

        return status_key_layout

    def update_content(self, node_status_data: dict):
        """Update the node status display"""
        if not node_status_data or not node_status_data.get('nodes'):
            return

        nodes = node_status_data['nodes']

        # Clear existing grid layout content
        for i in reversed(range(self.node_status_grid_layout.count())):
            item = self.node_status_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        row_offset = 0
        prev_partition = ""
        
        for row_index, node_data in enumerate(nodes):
            # Add partition separator if needed
            if prev_partition != node_data.get("Partitions", ""):
                prev_partition = node_data["Partitions"]
                
                # Create and add partition separator
                separator_container = QWidget()
                separator_layout = QHBoxLayout(separator_container)
                separator_layout.setContentsMargins(0, 0, 0, 0)
                separator_layout.setSpacing(0)

                left_line = QFrame()
                left_line.setFrameShape(QFrame.Shape.HLine)
                left_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                line_color = COLOR_DARK_BORDER
                separator_style = f"border: none; border-top: 1px dotted {line_color};"
                left_line.setStyleSheet(separator_style)

                partition_label_text = str(prev_partition).replace(" ", "_")
                partition_label = QLabel(partition_label_text)
                partition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label_color = COLOR_DARK_FG
                partition_label.setStyleSheet(f"color: {label_color};")

                right_line = QFrame()
                right_line.setFrameShape(QFrame.Shape.HLine)
                right_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                right_line.setStyleSheet(separator_style)

                separator_layout.addWidget(left_line, 1)
                separator_layout.addWidget(partition_label, 0)
                separator_layout.addWidget(right_line, 1)

                self.node_status_grid_layout.addWidget(separator_container, row_index + row_offset, 0, 1, max(1, 35))
                row_offset += 1

            # Add node data
            node_name = node_data['NodeName']
            block_states = node_data['block_states']
            tooltips = node_data['tooltips']
            total_gpus = node_data['total_gpus']

            # Add node name label
            name_label = QLabel(node_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.node_status_grid_layout.addWidget(name_label, row_index + row_offset, 0)

            # Handle nodes with more than 8 GPUs
            if total_gpus > 8:
                extra_rows = (total_gpus - 1) // 8
                for r in range(extra_rows):
                    self.node_status_grid_layout.addWidget(QLabel(""), row_index + 1 + r + row_offset, 0)

            # Add GPU blocks
            block_size = 16
            i = 0
            col_start = 1

            for block_index, block_state in enumerate(block_states):
                if i >= 8:
                    row_offset += 1
                    i = 0

                block_widget = QWidget()
                block_widget.setFixedSize(QSize(block_size, block_size))
                block_widget.setObjectName("coloredBlock")

                if block_index < len(tooltips) and tooltips[block_index]:
                    block_widget.setToolTip(tooltips[block_index])

                block_widget.setProperty("data-state", block_state)
                if self.theme_stylesheet:
                    block_widget.setStyleSheet(self.theme_stylesheet)

                self.node_status_grid_layout.addWidget(
                    block_widget, row_index + row_offset, col_start + i)
                i += 1

        # Adjust column stretches
        self.node_status_grid_layout.setColumnStretch(0, 0)
        for i in range(1, 1 + 8):
            self.node_status_grid_layout.setColumnStretch(i, 0)
        self.node_status_grid_layout.setColumnStretch(1 + 8, 1)

        if nodes:
            max_row_used = len(nodes) + row_offset
            self.node_status_grid_layout.setRowStretch(max_row_used, 1)

    def show_connection_error(self):
        """Show connection error message"""
        # Clear existing content
        for i in reversed(range(self.node_status_grid_layout.count())):
            item = self.node_status_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        text_color = COLOR_DARK_FG
        error_label = QLabel("⚠️ Unavailable Connection\n\nPlease check SLURM connection")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet(f"color: {text_color}; font-size: 16px; padding: 40px;")
        
        self.node_status_grid_layout.addWidget(error_label, 0, 0, 1, -1)


class CpuUsageTabView(QWidget):
    """View for displaying CPU usage visualization"""

    def __init__(self, parent=None, theme_stylesheet=None):
        super().__init__(parent)
        self.theme_stylesheet = theme_stylesheet
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI layout"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        self.usage_grid_layout = QGridLayout()
        self.usage_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.usage_grid_layout.setHorizontalSpacing(10)
        self.usage_grid_layout.setVerticalSpacing(6)

        title_legend_layout = QHBoxLayout()
        title_legend_layout.setContentsMargins(0, 0, 0, 0)
        title_legend_layout.setSpacing(0)

        section_title = QLabel("CPU Usage per Node")
        section_title.setObjectName("sectionTitle")
        title_legend_layout.addWidget(section_title)
        title_legend_layout.addStretch()

        self.main_layout.addLayout(title_legend_layout)
        self.main_layout.addLayout(self.usage_grid_layout)
        self.main_layout.addStretch()

        if self.theme_stylesheet:
            self.setStyleSheet(self.theme_stylesheet)
            section_title.setStyleSheet(f"color: {COLOR_DARK_FG};")

    def update_content(self, cpu_usage_data: dict):
        """Update the CPU usage display"""
        if not cpu_usage_data or not cpu_usage_data.get('nodes'):
            return

        nodes = cpu_usage_data['nodes']
        
        # Clear existing content
        for i in reversed(range(self.usage_grid_layout.count())):
            item = self.usage_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        row_offset = 0
        prev_partition = ""
        
        for row_index, node_data in enumerate(nodes):
            # Add partition separator if needed
            if prev_partition != node_data.get("Partitions", ""):
                prev_partition = node_data["Partitions"]
                
                separator_container = QWidget()
                separator_layout = QHBoxLayout(separator_container)
                separator_layout.setContentsMargins(0, 0, 0, 0)
                separator_layout.setSpacing(0)
                
                left_line = QFrame()
                left_line.setFrameShape(QFrame.Shape.HLine)
                left_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                line_color = COLOR_DARK_BORDER
                separator_style = f"border: none; border-top: 1px dotted {line_color};"
                left_line.setStyleSheet(separator_style)
                
                partition_label_text = str(prev_partition).replace(" ", "_")
                partition_label = QLabel(partition_label_text)
                partition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label_color = COLOR_DARK_FG
                partition_label.setStyleSheet(f"color: {label_color};")
                
                right_line = QFrame()
                right_line.setFrameShape(QFrame.Shape.HLine)
                right_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                right_line.setStyleSheet(separator_style)
                
                separator_layout.addWidget(left_line, 1)
                separator_layout.addWidget(partition_label, 0)
                separator_layout.addWidget(right_line, 1)
                
                self.usage_grid_layout.addWidget(separator_container, row_index + row_offset, 0, 1, 3)
                row_offset += 1

            # Add node usage data
            
            node_name = node_data['NodeName']
            total_cpu = node_data['total_cpu']
            alloc_cpu = node_data['alloc_cpu']
            cpu_usage_percent = node_data['cpu_usage_percent']

            name_label = QLabel(node_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_label.setMinimumWidth(120)

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

            if self.theme_stylesheet:
                progress_bar.setStyleSheet(self.theme_stylesheet)

            self.usage_grid_layout.addWidget(name_label, row_index + row_offset, 0)
            self.usage_grid_layout.addWidget(progress_bar, row_index + row_offset, 1)

        self.usage_grid_layout.setColumnStretch(0, 0)
        self.usage_grid_layout.setColumnStretch(1, 1)

        if nodes:
            max_row_used = len(nodes) + row_offset
            self.usage_grid_layout.setRowStretch(max_row_used, 1)

    def show_connection_error(self):
        """Show connection error message"""
        # Clear existing content
        for i in reversed(range(self.usage_grid_layout.count())):
            item = self.usage_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        error_label = QLabel("⚠️ Unavailable Connection\n\nPlease check SLURM connection")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet(f"color: {COLOR_RED}; font-size: 16px; padding: 40px;")
        self.usage_grid_layout.addWidget(error_label, 0, 0)


class RamUsageTabView(QWidget):
    """View for displaying RAM usage visualization"""

    def __init__(self, parent=None, theme_stylesheet=None):
        super().__init__(parent)
        self.theme_stylesheet = theme_stylesheet
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI layout"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        self.usage_grid_layout = QGridLayout()
        self.usage_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.usage_grid_layout.setHorizontalSpacing(10)
        self.usage_grid_layout.setVerticalSpacing(6)

        title_legend_layout = QHBoxLayout()
        title_legend_layout.setContentsMargins(0, 0, 0, 0)
        title_legend_layout.setSpacing(0)

        section_title = QLabel("RAM Usage per Node")
        section_title.setObjectName("sectionTitle")
        title_legend_layout.addWidget(section_title)
        title_legend_layout.addStretch()

        self.main_layout.addLayout(title_legend_layout)
        self.main_layout.addLayout(self.usage_grid_layout)
        self.main_layout.addStretch()

        if self.theme_stylesheet:
            self.setStyleSheet(self.theme_stylesheet)
            section_title.setStyleSheet(f"color: {COLOR_DARK_FG};")

    def update_content(self, ram_usage_data: dict):
        """Update the RAM usage display"""
        if not ram_usage_data or not ram_usage_data.get('nodes'):
            return

        nodes = ram_usage_data['nodes']
        
        # Clear existing content
        for i in reversed(range(self.usage_grid_layout.count())):
            item = self.usage_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        row_offset = 0
        prev_partition = ""
        
        for row_index, node_data in enumerate(nodes):
            # Add partition separator if needed
            if prev_partition != node_data.get("Partitions", ""):
                prev_partition = node_data["Partitions"]
                
                separator_container = QWidget()
                separator_layout = QHBoxLayout(separator_container)
                separator_layout.setContentsMargins(0, 0, 0, 0)
                separator_layout.setSpacing(0)
                
                left_line = QFrame()
                left_line.setFrameShape(QFrame.Shape.HLine)
                left_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                line_color = COLOR_DARK_BORDER
                separator_style = f"border: none; border-top: 1px dotted {line_color};"
                left_line.setStyleSheet(separator_style)
                
                partition_label_text = str(prev_partition).replace(" ", "_")
                partition_label = QLabel(partition_label_text)
                partition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label_color = COLOR_DARK_FG
                partition_label.setStyleSheet(f"color: {label_color};")
                
                right_line = QFrame()
                right_line.setFrameShape(QFrame.Shape.HLine)
                right_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                right_line.setStyleSheet(separator_style)
                
                separator_layout.addWidget(left_line, 1)
                separator_layout.addWidget(partition_label, 0)
                separator_layout.addWidget(right_line, 1)
                
                self.usage_grid_layout.addWidget(separator_container, row_index + row_offset, 0, 1, 3)
                row_offset += 1

            # Add node usage data
            node_name = node_data['NodeName']
            total_mem_mb = node_data['total_mem_mb']
            alloc_mem_mb = node_data['alloc_mem_mb']
            ram_usage_percent = node_data['ram_usage_percent']

            name_label = QLabel(node_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_label.setMinimumWidth(120)

            # Convert MB to GB for display if large enough, otherwise show MB
            total_mem_display = f"{total_mem_mb / 1024**3:.1f}G" if total_mem_mb >= 1024 else f"{total_mem_mb}M"
            alloc_mem_display = f"{alloc_mem_mb / 1024**3:.1f}G" if alloc_mem_mb >= 1024 else f"{alloc_mem_mb}M"

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

            if self.theme_stylesheet:
                progress_bar.setStyleSheet(self.theme_stylesheet)

            self.usage_grid_layout.addWidget(name_label, row_index + row_offset, 0)
            self.usage_grid_layout.addWidget(progress_bar, row_index + row_offset, 1)

        self.usage_grid_layout.setColumnStretch(0, 0)
        self.usage_grid_layout.setColumnStretch(1, 1)

        if nodes:
            max_row_used = len(nodes) + row_offset
            self.usage_grid_layout.setRowStretch(max_row_used, 1)

    def show_connection_error(self):
        """Show connection error message"""
        # Clear existing content
        for i in reversed(range(self.usage_grid_layout.count())):
            item = self.usage_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        error_label = QLabel("⚠️ Unavailable Connection\n\nPlease check SLURM connection")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet(f"color: {COLOR_RED}; font-size: 16px; padding: 40px;")
        self.usage_grid_layout.addWidget(error_label, 0, 0)