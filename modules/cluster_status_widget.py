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

    return sorted(nodes_data, key=lambda x: (x['Partitions'], extract_mem_value(x)), reverse=True)

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
            # Add connection check
            self._show_connection_error()
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
            reserved = node_info.get("RESERVED", "NO").upper() == "YES"

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
                    if isinstance(job.get("Account"), str):
                        job_gpus = 0
                        try:
                            job_gpus = int(job.get("GPUs", 0))
                        except ValueError:
                            print(f"Warning: Could not convert job['GPUs'] to int for job {job.get('JobID')}")
                            continue
                            
                        # Check if it's a student job
                        is_student_job = any(k in job["Account"] for k in STUDENTS_JOBS_KEYWORD)
                        
                        if is_student_job:
                            stud_used += job_gpus
                        else:
                            prod_used += job_gpus

                # Ensure stud_used does not exceed used_gpus
                stud_used = min(stud_used, used_gpus)
                prod_used = used_gpus - stud_used
                # Ensure total used does not exceed total_gpus
                total_used = min(stud_used + prod_used, total_gpus)
                stud_used = min(stud_used, total_used)
                prod_used = min(prod_used, total_used - stud_used)

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
                current_blocks.extend(["prod_used"] * prod_used)

                # Calculate remaining GPUs based on actual SLURM allocation
                remaining_gpus = total_gpus - used_gpus
                if remaining_gpus > 0:
                    if available_state:
                        current_blocks.extend(["available"] * remaining_gpus)
                    elif mid_constraint_state:
                        current_blocks.extend(["mid-constraint"] * remaining_gpus)
                    elif high_constraint_state:
                        current_blocks.extend(["high-constraint"] * remaining_gpus)
                    else:
                        current_blocks.extend(["available"] * remaining_gpus)

                block_states = current_blocks

            # Handle state combinations
            if reserved:
                block_states = ["reserved"] * total_gpus
            elif "DOWN" in state or "NOT_RESPONDING" in state:
                block_states = ["unavailable"] * total_gpus
            else:
                current_blocks = []
                current_blocks.extend(["stud_used"] * stud_used)
                current_blocks.extend(["prod_used"] * (used_gpus - stud_used))
                remaining_gpus = total_gpus - used_gpus
                if remaining_gpus > 0:
                    current_blocks.extend(["available"] * remaining_gpus)
                block_states = current_blocks

            block_size = 16
            i = 0  # Counter for blocks in the current row
            col_start = 1  # Start adding blocks from the second column

            # Add block widgets starting from the second column (column 1)
            for block_index, block_state in enumerate(block_states):
                if i >= 8:
                    row_offset += 1
                    i = 0  # Reset column counter for the new row

                block_widget = QWidget()
                block_widget.setFixedSize(QSize(block_size, block_size))
                block_widget.setObjectName("coloredBlock")
                
                # Find the username for used GPUs
                tooltip_text = ""
                if block_state in ["prod_used", "stud_used"]:
                    # Find jobs running on this node
                    node_jobs = [job for job in jobs_data if node_info["NodeName"] == job.get("Nodelist", "")]
                    
                    # Separate student and production jobs
                    stud_jobs = []
                    prod_jobs = []
                    for job in node_jobs:
                        account = job.get("Account", "")
                        if any(k in account for k in STUDENTS_JOBS_KEYWORD):
                            stud_jobs.append(job)
                        else:
                            prod_jobs.append(job)
                    
                    # Count total GPUs for each type to determine offset
                    total_stud_gpus = sum(int(job.get("GPUs", 0)) for job in stud_jobs)
                    
                    if block_state == "stud_used":
                        current_gpu_index = 0
                        # Process student jobs
                        for job in stud_jobs:
                            num_gpus = int(job.get("GPUs", 0))
                            if block_index < total_stud_gpus and block_index >= current_gpu_index:
                                if block_index < current_gpu_index + num_gpus:
                                    tooltip_text = job.get("User", "unknown")
                                    break
                            current_gpu_index += num_gpus
                    
                    elif block_state == "prod_used":
                        current_gpu_index = total_stud_gpus
                        # Process production jobs
                        for job in prod_jobs:
                            num_gpus = int(job.get("GPUs", 0))
                            if block_index >= total_stud_gpus and block_index >= current_gpu_index:
                                if block_index < current_gpu_index + num_gpus:
                                    tooltip_text = job.get("User", "unknown")
                                    break
                            current_gpu_index += num_gpus

                if tooltip_text:
                    block_widget.setToolTip(tooltip_text)
                    
                block_widget.setProperty("data-state", block_state)
                if self.theme_stylesheet:
                    block_widget.setStyleSheet(self.theme_stylesheet)

                self.node_status_grid_layout.addWidget(
                    block_widget, row_index + row_offset, col_start + i)
                i += 1

        # Adjust column stretches
        self.node_status_grid_layout.setColumnStretch(0, 0)  # Node name column

        for i in range(1, 1 + 8):  # Adjust range if you expect more blocks per row
            self.node_status_grid_layout.setColumnStretch(i, 0)

        self.node_status_grid_layout.setColumnStretch(1 + 8, 1)

        if nodes_data:  # Only add stretch if there's data
            max_row_used = len(nodes_data) + row_offset  # Simple approximation, might need refinement
            self.node_status_grid_layout.setRowStretch(max_row_used, 1)

    def _show_connection_error(self):
        """Show connection error message"""
        # FIX: Pre-calculate complex expressions outside f-string
        text_color = COLOR_DARK_FG if self.theme_stylesheet == get_dark_theme_stylesheet() else COLOR_LIGHT_FG
        
        error_label = QLabel("⚠️ Unavailable Connection\n\nPlease check SLURM connection")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet(f"color: {text_color}; font-size: 16px; padding: 40px;")
        
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
        if not nodes_data:
            self._show_connection_error()
            return
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

        self.usage_grid_layout.setColumnStretch(0, 0)  # Node name
        self.usage_grid_layout.setColumnStretch(1, 1)  # Progress bar (take remaining space)

        if nodes_data:
            max_row_used = len(nodes_data) + row_offset
            self.usage_grid_layout.setRowStretch(max_row_used, 1)

    def _show_connection_error(self):
        """Show connection error message"""
        # Clear existing content
        for i in reversed(range(self.usage_grid_layout.count())):
            item = self.usage_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        # Add error message
        error_label = QLabel("⚠️ Unavailable Connection\n\nPlease check SLURM connection")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet(f"color: {COLOR_RED}; font-size: 16px; padding: 40px;")
        self.usage_grid_layout.addWidget(error_label, 0, 0)

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
        if not nodes_data:
            self._show_connection_error()
            return
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

    def _show_connection_error(self):
        """Show connection error message"""
        # Clear existing content
        for i in reversed(range(self.usage_grid_layout.count())):
            item = self.usage_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        # Add error message
        error_label = QLabel("⚠️ Unavailable Connection\n\nPlease check SLURM connection")
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_label.setStyleSheet(f"color: {COLOR_RED}; font-size: 16px; padding: 40px;")
        self.usage_grid_layout.addWidget(error_label, 0, 0)
    
class ClusterStatusWidget(QWidget):
    def __init__(self, parent=None, slurm_connection=None):
        super().__init__(parent)
        self._setup_ui()
        self.setWindowTitle(APP_TITLE)
        # Set minimum size, allow resizing
        self.setMinimumSize(QSize(MIN_WIDTH, MIN_HEIGHT))
        # self.resize(MIN_WIDTH, MIN_HEIGHT)  # Start with minimum size

        self.themes = {
            THEME_DARK: get_dark_theme_stylesheet(),
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
        
    # In cluster_status_widget.py
    def _setup_ui(self):
        
        # Use the application's default font consistently
        app_font = QApplication.instance().font()
        
        # For section titles, scale appropriately
        title_font = QFont(app_font)
        title_font.setPointSize(app_font.pointSize() + 8)  # Slightly larger
        title_font.setWeight(QFont.Weight.Bold)
        
        section_title = QLabel("Node Status")
        section_title.setFont(title_font)
        section_title.setObjectName("sectionTitle")

    def update_status(self, nodes_data, jobs_data):
        """Fetches data from Slurm and updates all tabs."""

        # Update content of each tab

        self.node_status_tab.update_content(nodes_data, jobs_data)
        self.cpu_usage_tab.update_content(nodes_data, jobs_data)
        self.ram_usage_tab.update_content(nodes_data, jobs_data)

