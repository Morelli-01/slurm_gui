import sys
import re
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QGridLayout, QFrame, QSizePolicy,
                             QTabWidget, QTableWidget, QTableWidgetItem,
                             QHeaderView, QGroupBox,
                             QProgressBar)  # Import QProgressBar
from PyQt6.QtCore import Qt, QSize, QTimer
from slurm_connection import SlurmConnection
from utils import parse_memory_size
from modules.defaults import *
from style import AppStyles
# --- Constants ---
APP_TITLE = "Cluster Status Representation"
# Using a more flexible size, but keeping a minimum
MIN_WIDTH = 400
MIN_HEIGHT = 700
REFRESH_INTERVAL_MS = 10000  # Refresh every 10 seconds

# --- Helper Functions ---

def get_dark_theme_stylesheet():
    return AppStyles.get_cluster_status_styles(THEME_DARK)

def get_light_theme_stylesheet():
    return AppStyles.get_cluster_status_styles(THEME_LIGHT)

def sort_nodes_data(nodes_data: list[dict]):
    # Function to extract numeric part from total_mem string (removing 'M' suffix)
    new_nodes_data = []
    for n in nodes_data:
        if "Partitions" in n.keys():
            new_nodes_data.append(n)
    nodes_data = new_nodes_data

    def extract_mem_value(node):
        mem_str = node['total_mem']
        if mem_str.endswith('M'):
            return int(mem_str[:-1])  # Remove 'M' and convert to int
        return int(mem_str)  # Just in case there's no 'M'

    # Sort first by 'Partitions', then by the numeric value of 'total_mem'

    return sorted(nodes_data, key=lambda x: (x['Partitions'], extract_mem_value(x)), reverse=True)

# --- Tab Widgets ---


class NodeStatusTab(QWidget):
    """Widget for displaying node status visualization."""

    def __init__(self, parent=None, theme_stylesheet=None):
        super().__init__(parent)
        self.theme_stylesheet = theme_stylesheet  # Store theme stylesheet

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        # Use QGridLayout for the node status content
        self.node_status_grid_layout = QGridLayout()
        self.node_status_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.node_status_grid_layout.setHorizontalSpacing(3)  # Increased spacing for clarity
        self.node_status_grid_layout.setVerticalSpacing(6)   # Increased spacing between rows

        # Create a horizontal layout for the title and legend
        title_legend_layout = QHBoxLayout()
        title_legend_layout.setContentsMargins(0, 0, 0, 0)
        title_legend_layout.setSpacing(0)  # Set spacing to 0 here, spacing is handled by the vertical separator margins

        # Add section title to the horizontal layout
        section_title = QLabel("Node Status")
        section_title.setObjectName("sectionTitle")
        title_legend_layout.addWidget(section_title)

        # Add a vertical separator
        vertical_separator = QFrame()
        vertical_separator.setObjectName("verticalSeparator")
        vertical_separator.setFrameShape(QFrame.Shape.VLine)
        vertical_separator.setFrameShadow(QFrame.Shadow.Sunken)
        title_legend_layout.addWidget(vertical_separator)

        # Create and add the status key section to the horizontal layout
        self.status_key_layout = self.create_status_key_section()  # Keep reference to update later
        title_legend_layout.addLayout(self.status_key_layout)

        title_legend_layout.addStretch()
        self.main_layout.addLayout(title_legend_layout)
        self.main_layout.addLayout(self.node_status_grid_layout)  # Add the grid layout to main layout

        self.main_layout.addStretch()  # Push content to the top

    def create_status_key_section(self):
        status_key_layout = QVBoxLayout()
        status_key_layout.setContentsMargins(0, 0, 0, 0)
        status_key_layout.setSpacing(5)
        key_items = [
            # ("used", "Used GPU"),
            ("prod_used", "Used GPU for prod"),
            ("stud_used", "Used GPU by stud"),
            ("available", "Available GPU"),
            ("unavailable", "Unavailable Node/GPU"),
        ]

        for color_name, text in key_items:
            key_row_layout = QHBoxLayout()
            key_row_layout.setContentsMargins(0, 0, 0, 0)
            key_row_layout.setSpacing(8)

            color_widget = QWidget()
            block_size = 16
            color_widget.setFixedSize(QSize(block_size, block_size))
            color_widget.setObjectName("coloredBlock")
            # Use dynamic property to apply specific styles
            color_widget.setProperty("data-state", color_name.lower())
            # Apply stylesheet again to ensure dynamic property is considered
            # Use the stored theme stylesheet
            if self.theme_stylesheet:
                color_widget.setStyleSheet(self.theme_stylesheet)

            key_row_layout.addWidget(color_widget)

            text_label = QLabel(text)
            key_row_layout.addWidget(text_label)
            key_row_layout.addStretch()

            status_key_layout.addLayout(key_row_layout)

        return status_key_layout

    def update_content(self, nodes_data, jobs_data):
        """
        Updates the node status visualization based on the provided data.
        """
        if nodes_data is None:
            return
        nodes_data = sort_nodes_data(nodes_data)
        self.total_gpu_used = 0
        self.total_gpu = 0
        # Clear existing grid layout content
        for i in reversed(range(self.node_status_grid_layout.count())):
            item = self.node_status_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        max_gpu_count = 0
        for node_info in nodes_data:
            max_gpu_count = max(int(node_info.get("total_gres/gpu", 0)), max_gpu_count)

        row_offset = 0
        prev_partition = ""
        for row_index, node_info in enumerate(nodes_data):
            if prev_partition != node_info["Partitions"]:
                prev_partition = node_info["Partitions"]

                # Create container widget for the separator with text
                separator_container = QWidget()
                separator_layout = QHBoxLayout(separator_container)
                separator_layout.setContentsMargins(0, 0, 0, 0)
                separator_layout.setSpacing(0)

                # Left dotted line
                left_line = QFrame()
                left_line.setFrameShape(QFrame.Shape.HLine)
                left_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                # Use theme colors for the separator line
                line_color = COLOR_DARK_BORDER if self.theme_stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_BORDER
                separator_style = f"border: none; border-top: 1px dotted {line_color};"
                left_line.setStyleSheet(separator_style)

                # Label with partition name
                partition_label_text = str(node_info['Partitions']).replace(" ", "_")
                partition_label = QLabel(partition_label_text)
                partition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                # Use theme colors for the partition label
                label_color = COLOR_DARK_FG if self.theme_stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG
                partition_label.setStyleSheet(f"color: {label_color};")

                # Right dotted line
                right_line = QFrame()
                right_line.setFrameShape(QFrame.Shape.HLine)
                right_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                right_line.setStyleSheet(separator_style)  # Use the same style as the left line

                # Add widgets to container layout with stretch
                separator_layout.addWidget(left_line, 1)  # Stretch factor 1
                separator_layout.addWidget(partition_label, 0)  # No stretch
                separator_layout.addWidget(right_line, 1)  # Stretch factor 1

                # Add the container to your grid
                self.node_status_grid_layout.addWidget(separator_container, row_index + row_offset, 0, 1, max(1, 35))
                row_offset += 1

            node_name = node_info.get("NodeName")
            state = node_info.get("State", "").upper()
            gres = node_info.get("total_gres/gpu", "")
            gres_used = node_info.get("alloc_gres/gpu", "")

            if not node_name:
                continue

            # Add node name to the first column (column 0)
            name_label = QLabel(node_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            # Set a fixed width policy for the name label to prevent it from expanding too much
            name_label.setSizePolicy(
                name_label.sizePolicy().horizontalPolicy(),
                name_label.sizePolicy().verticalPolicy()
            )

            total_gpus = int(node_info.get("total_gres/gpu", 0))
            used_gpus = int(node_info.get("alloc_gres/gpu", 0))

            self.node_status_grid_layout.addWidget(name_label, row_index + row_offset, 0)
            # Adjust row offset for nodes with more than 8 GPUs to ensure blocks wrap correctly
            if total_gpus > 8:
                # Calculate how many extra rows are needed for blocks
                extra_rows = (total_gpus - 1) // 8  # Integer division to find number of full 8-block rows minus 1
                for r in range(extra_rows):
                    self.node_status_grid_layout.addWidget(QLabel(""), row_index + 1 + r + row_offset, 0)

            block_states = []
            # Prioritize unavailable states
            if "DRAIN" in state or "DOWN" in state or "UNKNOWN" in state:
                block_states = ["unavailable"] * total_gpus
            # Then check for allocated/mixed
            elif "ALLOCATED" in state or "MIXED" in state:

                filtered_jobs = [job for job in jobs_data if node_info["NodeName"] == job.get("Nodelist", "")]
                stud_used = 0
                prod_used = 0
                for job in filtered_jobs:
                    # Ensure job["Account"] is a string before checking for keywords
                    if isinstance(job.get("Account"), str):
                        for k in STUDENTS_JOBS_KEYWORD:
                            if k in job["Account"]:
                                # Ensure job["GPUs"] is convertible to int
                                try:
                                    stud_used += int(job.get("GPUs", 0))
                                except ValueError:
                                    print(f"Warning: Could not convert job['GPUs'] to int for job {job.get('JobID')}")

                total_cpu = int(node_info.get("total_cpu", 1))
                alloc_cpu = int(node_info.get("alloc_cpu", 0))
                # Handle potential errors in memory parsing
                try:
                    total_mem = parse_memory_size(node_info.get("total_mem", "1M")) // 1024**3
                except (ValueError, IndexError):
                    print(f"Warning: Could not parse total_mem for node {node_name}: {node_info.get('total_mem')}")
                    total_mem = 1  # Default to 1 to avoid division by zero

                try:
                    alloc_mem = parse_memory_size(node_info.get("alloc_mem", "0M")) // 1024**3
                except (ValueError, IndexError):
                    print(f"Warning: Could not parse alloc_mem for node {node_name}: {node_info.get('alloc_mem')}")
                    alloc_mem = 0  # Default to 0

                # Avoid division by zero if total_cpu or total_mem is 0
                cpu_utilization = alloc_cpu / total_cpu if total_cpu > 0 else 0
                mem_utilization = alloc_mem / total_mem if total_mem > 0 else 0

                high_constraint_state = cpu_utilization >= 0.9 or mem_utilization >= 0.9
                mid_constraint_state = (cpu_utilization >= 0.7 or mem_utilization >= 0.7) and not high_constraint_state
                available_state = not high_constraint_state and not mid_constraint_state

                # Ensure the total number of blocks matches total_gpus
                current_blocks = []
                current_blocks.extend(["stud_used"] * stud_used)
                current_blocks.extend(["prod_used"] * (used_gpus - stud_used))

                remaining_gpus = total_gpus - used_gpus
                if remaining_gpus > 0:
                    if available_state:
                        current_blocks.extend(["available"] * remaining_gpus)
                    elif mid_constraint_state:
                        current_blocks.extend(["mid-constraint"] * remaining_gpus)
                    elif high_constraint_state:
                        current_blocks.extend(["high-constraint"] * remaining_gpus)
                    else:
                        # Fallback if none of the above states apply to remaining GPUs
                        current_blocks.extend(["available"] * remaining_gpus)  # Assume available if no constraints

                block_states = current_blocks

            # Finally, assume idle if none of the above
            elif "IDLE" in state:
                block_states = ["available"] * total_gpus
            else:
                # Handle any other potential states
                print(f"Warning: Unhandled node state for {node_name}: {state}")
                block_states = ["unavailable"] * total_gpus  # Default to unavailable

            block_size = 16
            i = 0  # Counter for blocks in the current row
            col_start = 1  # Start adding blocks from the second column

            # Add block widgets starting from the second column (column 1)
            for block_index, block_state in enumerate(block_states):
                # Check if we need to move to the next row for blocks
                if i >= 8:
                    row_offset += 1
                    i = 0  # Reset column counter for the new row

                block_widget = QWidget()
                block_widget.setFixedSize(QSize(block_size, block_size))
                block_widget.setObjectName("coloredBlock")
                # Use dynamic property to apply specific styles based on state
                block_widget.setProperty("data-state", block_state)
                # Apply stylesheet using the stored theme
                if self.theme_stylesheet:
                    block_widget.setStyleSheet(self.theme_stylesheet)

                # Add block widget to the grid at the current row and column (col_start + i)
                self.node_status_grid_layout.addWidget(
                    block_widget, row_index + row_offset, col_start + i)
                i += 1  # Increment column counter

        # Adjust column stretches
        self.node_status_grid_layout.setColumnStretch(0, 0)  # Node name column

        # Stretch for block columns (up to max_gpu_count, assuming 8 blocks per row max)
        # We need enough columns for max_gpu_count blocks, potentially spread over multiple rows
        # A simpler approach is to set stretch for a reasonable number of columns after the name
        # Let's assume we might need up to 8 columns for blocks in a row
        for i in range(1, 1 + 8):  # Adjust range if you expect more blocks per row
            self.node_status_grid_layout.setColumnStretch(i, 0)

        # Set stretch for the column after the blocks to push everything to the left
        # The column index will depend on the maximum number of blocks in a single row (which is 8 in this layout)
        self.node_status_grid_layout.setColumnStretch(1 + 8, 1)

        if nodes_data:  # Only add stretch if there's data
            # The row stretch should be applied to the row *after* the last node's content,
            # considering the potential extra rows for blocks.
            # Calculate the maximum row index used by content
            max_row_used = len(nodes_data) + row_offset  # Simple approximation, might need refinement
            self.node_status_grid_layout.setRowStretch(max_row_used, 1)

    def set_theme(self, stylesheet):
        """Sets the theme for this tab."""
        self.theme_stylesheet = stylesheet
        self.setStyleSheet(stylesheet)
        # Re-create status key section to apply new theme colors to blocks
        # Clear existing status key layout items
        while self.status_key_layout.count():
            item = self.status_key_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():  # Handle nested layouts if any
                while item.layout().count():
                    nested_item = item.layout().takeAt(0)
                    if nested_item.widget():
                        nested_item.widget().deleteLater()

        # Create and add the new status key section
        new_status_key_layout = self.create_status_key_section()
        for i in range(new_status_key_layout.count()):
            self.status_key_layout.addLayout(new_status_key_layout.takeAt(0).layout())

        # Re-apply stylesheet to existing widgets in the grid layout
        for i in range(self.node_status_grid_layout.count()):
            item = self.node_status_grid_layout.itemAt(i)
            widget = item.widget()
            if widget and widget.objectName() == "coloredBlock":
                widget.setStyleSheet(self.theme_stylesheet)
            elif isinstance(widget, QLabel):  # Update label colors
                # Reapply the label stylesheet based on object name or type
                if widget.objectName() == "sectionTitle":
                    widget.setStyleSheet(
                        f"font-size: 14pt; font-weight: bold; margin-bottom: 8px; color: {COLOR_DARK_FG if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG};")
                else:  # Node name labels
                    widget.setStyleSheet(
                        f"color: {COLOR_DARK_FG if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG};")
            elif isinstance(widget, QWidget) and widget.layout() and isinstance(widget.layout(), QHBoxLayout):
                # Update separator line color
                for j in range(widget.layout().count()):
                    sub_item = widget.layout().itemAt(j)
                    if isinstance(sub_item.widget(), QFrame):
                        line_color = COLOR_DARK_BORDER if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_BORDER
                        separator_style = f"border: none; border-top: 1px dotted {line_color};"
                        sub_item.widget().setStyleSheet(separator_style)
                    elif isinstance(sub_item.widget(), QLabel):  # Partition label
                        label_color = COLOR_DARK_FG if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG
                        sub_item.widget().setStyleSheet(f"color: {label_color};")


class CpuUsageTab(QWidget):
    """Widget for displaying CPU usage visualization."""

    def __init__(self, parent=None, theme_stylesheet=None):
        super().__init__(parent)
        self.theme_stylesheet = theme_stylesheet
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

        # Add a vertical separator (optional, can be removed if not desired for this tab)
        # vertical_separator = QFrame()
        # vertical_separator.setObjectName("verticalSeparator")
        # vertical_separator.setFrameShape(QFrame.Shape.VLine)
        # vertical_separator.setFrameShadow(QFrame.Shadow.Sunken)
        # title_legend_layout.addWidget(vertical_separator)

        # Add legend for progress bar colors (optional)
        # self.legend_layout = self.create_legend()
        # title_legend_layout.addLayout(self.legend_layout)

        title_legend_layout.addStretch()

        self.main_layout.addLayout(title_legend_layout)
        self.main_layout.addLayout(self.usage_grid_layout)
        self.main_layout.addStretch()

        if self.theme_stylesheet:
            self.setStyleSheet(self.theme_stylesheet)
            section_title.setStyleSheet(
                f"color: {COLOR_DARK_FG if self.theme_stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG};")

    def update_content(self, nodes_data, jobs_data):
        """Updates the CPU usage visualization."""
        nodes_data = sort_nodes_data(nodes_data)

        # Clear existing grid layout content
        for i in reversed(range(self.usage_grid_layout.count())):
            item = self.usage_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        row_offset = 0
        prev_partition = ""
        for row_index, node_info in enumerate(nodes_data):
            if prev_partition != node_info["Partitions"]:
                prev_partition = node_info["Partitions"]
                separator_container = QWidget()
                separator_layout = QHBoxLayout(separator_container)
                separator_layout.setContentsMargins(0, 0, 0, 0)
                separator_layout.setSpacing(0)
                left_line = QFrame()
                left_line.setFrameShape(QFrame.Shape.HLine)
                left_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                line_color = COLOR_DARK_BORDER if self.theme_stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_BORDER
                separator_style = f"border: none; border-top: 1px dotted {line_color};"
                left_line.setStyleSheet(separator_style)
                partition_label_text = str(node_info['Partitions']).replace(" ", "_")
                partition_label = QLabel(partition_label_text)
                partition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label_color = COLOR_DARK_FG if self.theme_stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG
                partition_label.setStyleSheet(f"color: {label_color};")
                right_line = QFrame()
                right_line.setFrameShape(QFrame.Shape.HLine)
                right_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                right_line.setStyleSheet(separator_style)
                separator_layout.addWidget(left_line, 1)
                separator_layout.addWidget(partition_label, 0)
                separator_layout.addWidget(right_line, 1)
                self.usage_grid_layout.addWidget(separator_container, row_index + row_offset, 0, 1, 3)  # Span 3 columns
                row_offset += 1

            node_name = node_info.get("NodeName")
            if not node_name:
                continue

            name_label = QLabel(node_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_label.setMinimumWidth(120)  # Ensure node name column has enough space

            total_cpu = int(node_info.get("total_cpu", 1))
            alloc_cpu = int(node_info.get("alloc_cpu", 0))
            cpu_usage_percent = (alloc_cpu / total_cpu * 100) if total_cpu > 0 else 0

            progress_bar = QProgressBar()
            progress_bar.setObjectName("cpuUsageBar")
            progress_bar.setValue(int(cpu_usage_percent))
            progress_bar.setFormat(f"{alloc_cpu}/{total_cpu} ({cpu_usage_percent:.1f}%)")
            progress_bar.setFixedHeight(20)  # Consistent height for progress bars

            # Set dynamic properties for critical/warning colors based on usage
            if cpu_usage_percent >= 90:
                progress_bar.setProperty("crit", "true")
            elif cpu_usage_percent >= 70:
                progress_bar.setProperty("warn", "true")
            else:
                progress_bar.setProperty("crit", "false")  # Ensure properties are reset
                progress_bar.setProperty("warn", "false")

            if self.theme_stylesheet:
                progress_bar.setStyleSheet(self.theme_stylesheet)  # Apply theme

            self.usage_grid_layout.addWidget(name_label, row_index + row_offset, 0)
            self.usage_grid_layout.addWidget(progress_bar, row_index + row_offset, 1)
            # Optional: Add a label for the exact percentage or values if not in progress bar format
            # usage_label = QLabel(f"{alloc_cpu} / {total_cpu} ({cpu_usage_percent:.1f}%)")
            # self.usage_grid_layout.addWidget(usage_label, row_index + row_offset, 2)

        self.usage_grid_layout.setColumnStretch(0, 0)  # Node name
        self.usage_grid_layout.setColumnStretch(1, 1)  # Progress bar (take remaining space)
        # self.usage_grid_layout.setColumnStretch(2, 0) # Usage text if added

        if nodes_data:
            max_row_used = len(nodes_data) + row_offset
            self.usage_grid_layout.setRowStretch(max_row_used, 1)

    def set_theme(self, stylesheet):
        """Sets the theme for this tab."""
        self.theme_stylesheet = stylesheet
        self.setStyleSheet(stylesheet)
        # Update title color
        title_label = self.findChild(QLabel, "sectionTitle")
        if title_label:
            title_label.setStyleSheet(
                f"color: {COLOR_DARK_FG if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG};")

        # Re-apply stylesheet to existing progress bars and labels in the grid
        for i in range(self.usage_grid_layout.count()):
            item = self.usage_grid_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, QProgressBar):
                widget.setStyleSheet(self.theme_stylesheet)
            elif isinstance(widget, QLabel) and widget.objectName() != "sectionTitle":
                widget.setStyleSheet(
                    f"color: {COLOR_DARK_FG if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG};")
            elif isinstance(widget, QWidget) and widget.layout() and isinstance(widget.layout(), QHBoxLayout):  # Separator
                for j in range(widget.layout().count()):
                    sub_item = widget.layout().itemAt(j)
                    if isinstance(sub_item.widget(), QFrame):
                        line_color = COLOR_DARK_BORDER if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_BORDER
                        separator_style = f"border: none; border-top: 1px dotted {line_color};"
                        sub_item.widget().setStyleSheet(separator_style)
                    elif isinstance(sub_item.widget(), QLabel):  # Partition label
                        label_color = COLOR_DARK_FG if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG
                        sub_item.widget().setStyleSheet(f"color: {label_color};")


class RamUsageTab(QWidget):
    """Widget for displaying RAM usage visualization."""

    def __init__(self, parent=None, theme_stylesheet=None):
        super().__init__(parent)

        self.theme_stylesheet = theme_stylesheet
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
            section_title.setStyleSheet(
                f"color: {COLOR_DARK_FG if self.theme_stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG};")

    def update_content(self, nodes_data, jobs_data):
        """Updates the RAM usage visualization."""
        nodes_data = sort_nodes_data(nodes_data)

        for i in reversed(range(self.usage_grid_layout.count())):
            item = self.usage_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        row_offset = 0
        prev_partition = ""
        for row_index, node_info in enumerate(nodes_data):
            if prev_partition != node_info["Partitions"]:
                prev_partition = node_info["Partitions"]
                separator_container = QWidget()
                separator_layout = QHBoxLayout(separator_container)
                separator_layout.setContentsMargins(0, 0, 0, 0)
                separator_layout.setSpacing(0)
                left_line = QFrame()
                left_line.setFrameShape(QFrame.Shape.HLine)
                left_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                line_color = COLOR_DARK_BORDER if self.theme_stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_BORDER
                separator_style = f"border: none; border-top: 1px dotted {line_color};"
                left_line.setStyleSheet(separator_style)
                partition_label_text = str(node_info['Partitions']).replace(" ", "_")
                partition_label = QLabel(partition_label_text)
                partition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label_color = COLOR_DARK_FG if self.theme_stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG
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

            node_name = node_info.get("NodeName")
            if not node_name:
                continue

            name_label = QLabel(node_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_label.setMinimumWidth(120)

            try:
                # Already in MB from parse_memory_size
                total_mem_mb = parse_memory_size(node_info.get("total_mem", "1M"))
                alloc_mem_mb = parse_memory_size(node_info.get("alloc_mem", "0M"))  # Already in MB
            except (ValueError, IndexError) as e:
                print(f"Warning: Could not parse memory for node {node_name}: {e}")
                total_mem_mb = 1
                alloc_mem_mb = 0

            ram_usage_percent = (alloc_mem_mb / total_mem_mb * 100) if total_mem_mb > 0 else 0

            progress_bar = QProgressBar()
            progress_bar.setObjectName("ramUsageBar")
            progress_bar.setValue(int(ram_usage_percent))
            # Convert MB to GB for display if large enough, otherwise show MB
            total_mem_display = f"{total_mem_mb / 1024**3:.1f}G" if total_mem_mb >= 1024 else f"{total_mem_mb}M"
            alloc_mem_display = f"{alloc_mem_mb / 1024**3:.1f}G" if alloc_mem_mb >= 1024 else f"{alloc_mem_mb}M"
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

        if nodes_data:
            max_row_used = len(nodes_data) + row_offset
            self.usage_grid_layout.setRowStretch(max_row_used, 1)

    def set_theme(self, stylesheet):
        """Sets the theme for this tab."""
        self.theme_stylesheet = stylesheet
        self.setStyleSheet(stylesheet)
        title_label = self.findChild(QLabel, "sectionTitle")
        if title_label:
            title_label.setStyleSheet(
                f"color: {COLOR_DARK_FG if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG};")

        for i in range(self.usage_grid_layout.count()):
            item = self.usage_grid_layout.itemAt(i)
            widget = item.widget()
            if isinstance(widget, QProgressBar):
                widget.setStyleSheet(self.theme_stylesheet)
            elif isinstance(widget, QLabel) and widget.objectName() != "sectionTitle":
                widget.setStyleSheet(
                    f"color: {COLOR_DARK_FG if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG};")
            elif isinstance(widget, QWidget) and widget.layout() and isinstance(widget.layout(), QHBoxLayout):  # Separator
                for j in range(widget.layout().count()):
                    sub_item = widget.layout().itemAt(j)
                    if isinstance(sub_item.widget(), QFrame):
                        line_color = COLOR_DARK_BORDER if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_BORDER
                        separator_style = f"border: none; border-top: 1px dotted {line_color};"
                        sub_item.widget().setStyleSheet(separator_style)
                    elif isinstance(sub_item.widget(), QLabel):  # Partition label
                        label_color = COLOR_DARK_FG if stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG
                        sub_item.widget().setStyleSheet(f"color: {label_color};")


class ClusterStatusWidget(QWidget):
    def __init__(self, parent=None, slurm_connection=None):
        super().__init__(parent)

        self.setWindowTitle(APP_TITLE)
        # Set minimum size, allow resizing
        self.setMinimumSize(QSize(MIN_WIDTH, MIN_HEIGHT))
        # self.resize(MIN_WIDTH, MIN_HEIGHT)  # Start with minimum size

        self.themes = {
            THEME_DARK: get_dark_theme_stylesheet(),
            THEME_LIGHT: get_light_theme_stylesheet(),
        }
        self.current_theme = THEME_DARK
        self.setStyleSheet(self.themes[self.current_theme])

        self.main_layout = QVBoxLayout(self)  # Use self as parent for the main layout
        self.main_layout.setContentsMargins(0, 0, 0, 0)  # Set margins for the main layout
        self.main_layout.setSpacing(0)  # Set spacing for the main layout

        # Create the QTabWidget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(self.themes[self.current_theme])  # Apply theme to the tab widget

        # Create the individual tab widgets, passing the current theme stylesheet
        self.node_status_tab = NodeStatusTab(parent=self.tab_widget, theme_stylesheet=self.themes[self.current_theme])
        self.cpu_usage_tab = CpuUsageTab(parent=self.tab_widget, theme_stylesheet=self.themes[self.current_theme])
        self.ram_usage_tab = RamUsageTab(parent=self.tab_widget, theme_stylesheet=self.themes[self.current_theme])

        # Add the tab widgets to the QTabWidget
        self.tab_widget.addTab(self.node_status_tab, "Node Status")
        self.tab_widget.addTab(self.cpu_usage_tab, "CPU Usage")
        self.tab_widget.addTab(self.ram_usage_tab, "RAM Usage")

        # Add the tab widget to the main layout
        self.main_layout.addWidget(self.tab_widget)

        # Initial data fetch and update
        if slurm_connection is None:
            self.sc_ = SlurmConnection("./configs/slurm_config.yaml")
            self.sc_.connect()
        else:
            self.sc_ = slurm_connection

        # Setup timer for periodic updates
        # self.timer = QTimer(self)
        # self.timer.timeout.connect(self.fetch_and_update)
        # self.timer.start(REFRESH_INTERVAL_MS)

        # # Perform initial fetch and update
        # self.fetch_and_update()

    def update_status(self, nodes_data, jobs_data):
        """Fetches data from Slurm and updates all tabs."""

        # Update content of each tab

        self.node_status_tab.update_content(nodes_data, jobs_data)
        self.cpu_usage_tab.update_content(nodes_data, jobs_data)
        self.ram_usage_tab.update_content(nodes_data, jobs_data)

    def switch_theme(self, theme_key):
        """Switches the application theme."""
        if theme_key in self.themes:
            self.current_theme = theme_key
            stylesheet = self.themes[self.current_theme]
            self.setStyleSheet(stylesheet)
            self.tab_widget.setStyleSheet(stylesheet)  # Apply theme to the tab widget

            # Update theme in each tab widget
            self.node_status_tab.set_theme(stylesheet)
            self.cpu_usage_tab.set_theme(stylesheet)
            self.ram_usage_tab.set_theme(stylesheet)

            # Trigger a data update to re-render content with the new theme
            # This might be necessary if the visualization logic in the tabs
            # depends on the theme (e.g., for drawing charts).
            # self.fetch_and_update() # Uncomment if needed
