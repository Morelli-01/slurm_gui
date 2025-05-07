import sys
import re
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QGridLayout, QFrame, QSizePolicy)  # Import QSizePolicy
from PyQt6.QtCore import Qt, QSize, QTimer
from slurm_connection import SlurmConnection

# --- Constants ---
APP_TITLE = "Cluster Status Representation"
# Using a more flexible size, but keeping a minimum
MIN_WIDTH = 400
MIN_HEIGHT = 750
REFRESH_INTERVAL_MS = 10000  # Refresh every 10 seconds

# Theme Keys
THEME_DARK = "Dark"

# Colors (Inspired by a more vibrant dark theme)
COLOR_DARK_BG = "#1a1a2e"       # Deep background
COLOR_DARK_FG = "#e9e9f4"       # Light foreground text
COLOR_DARK_BG_ALT = "#2a2a4a"   # Slightly lighter background for contrast
COLOR_DARK_BORDER = "#5a5a8a"   # Border color
COLOR_DARK_BG_ALT = "#383a59"  # Alternate row background
COLOR_DARK_BG_HOVER = "#44475a"  # Hover color
COLOR_DARK_BORDER = "#6272a4"  # Border/Grid color
COLOR_BLUE = "#8be9fd"     # Completed/Stopped status (Dracula Cyan)

# More vibrant colors for blocks
COLOR_AVAILABLE = "#4CAF50"     # Green for Available
COLOR_USED = "#2196F3"          # Blue for Used
COLOR_UNAVAILABLE = "#F44336"   # Red for Unavailable (Drain/Down/Unknown)
COLOR_USED_BY_STUD = "#00AAAA"
COLOR_USED_PROD = "#AA00AA"

# Mapping internal states to colors
BLOCK_COLOR_MAP = {
    "available": COLOR_AVAILABLE,    # Available GPU on IDLE node
    "used": COLOR_USED,         # Used GPU on ALLOCATED/MIXED node
    "unavailable": COLOR_UNAVAILABLE,  # GPU on DRAIN/DOWN/UNKNOWN node
    "stud_used": COLOR_USED,
    "prod_used": COLOR_USED_PROD,
}

STUDENTS_JOBS_KEYWORD = [
    "tesi",
    "cvcs",
    "ai4bio"
]


# --- Helper Functions ---


def get_dark_theme_stylesheet():
    return f"""
        QWidget {{
            background-color: {COLOR_DARK_BG};
            color: {COLOR_DARK_FG};
            font-family: "Consolas", "Menlo", "DejaVu Sans Mono", "Courier New", monospace;
            font-size: 12pt;
        }}
        QLabel#sectionTitle {{
            font-size: 14pt;
            font-weight: bold;
            margin-bottom: 8px;
            color: {COLOR_DARK_FG};
        }}
        QFrame#sectionSeparator {{
            background-color: {COLOR_DARK_BORDER};
            min-height: 1px;
            max-height: 1px;
            margin-top: 8px;
            margin-bottom: 8px;
        }}
         QFrame#verticalSeparator {{
            background-color: {COLOR_DARK_BORDER};
            min-width: 1px;
            max-width: 1px;
            margin-left: 10px; /* Add some margin to the left */
            margin-right: 10px; /* Add some margin to the right */
        }}
        /* Common styles for the colored blocks */
        QWidget#coloredBlock {{
            border-radius: 2px;
        }}
        /* Specific style for 'available' blocks */
        QWidget#coloredBlock[data-state="available"] {{
            background-color: transparent;
            border: 1px solid {BLOCK_COLOR_MAP['available']};
        }}
        /* Specific style for 'used' blocks */
         QWidget#coloredBlock[data-state="used"] {{
            background-color: {BLOCK_COLOR_MAP['used']};
            border: 1px solid {BLOCK_COLOR_MAP['used']};
        }}
        /* Specific style for 'unavailable' blocks */
        QWidget#coloredBlock[data-state="unavailable"] {{
            background-color: {BLOCK_COLOR_MAP['unavailable']};
            border: 1px solid {BLOCK_COLOR_MAP['unavailable']};
        }}
        QWidget#coloredBlock[data-state="stud_used"] {{
            background-color: {BLOCK_COLOR_MAP['stud_used']};
            border: 1px solid {BLOCK_COLOR_MAP['stud_used']};
        }}
        QWidget#coloredBlock[data-state="prod_used"] {{
            background-color: {BLOCK_COLOR_MAP['prod_used']};
            border: 1px solid {BLOCK_COLOR_MAP['prod_used']};
        }}
        QGroupBox {{
                border: 2px solid {COLOR_DARK_BORDER};
                border-radius: 8px;
                margin-top: 10px; /* Space for title */
                font-size: 16px;
                font-weight: bold;
                color: {COLOR_DARK_FG};
            }}
            QTableWidget {{
                background-color: {COLOR_DARK_BG};
                color: {COLOR_DARK_FG};
                selection-background-color: {COLOR_DARK_BG_HOVER};
                selection-color: {COLOR_DARK_FG};
                border: 1px solid {COLOR_DARK_BORDER};
                border-radius: 5px;
                gridline-color: {COLOR_DARK_BORDER};
                font-size: 14px;
            }}
            QHeaderView::section {{
                background-color: {COLOR_DARK_BG_ALT};
                color: {COLOR_DARK_FG};
                padding: 5px;
                border: 1px solid {COLOR_DARK_BORDER};
                border-bottom: 2px solid {COLOR_BLUE}; /* Highlight bottom border */
                font-weight: bold;
            }}
            QTableWidget::item {{
                padding: 5px; /* Add some padding to items */
            }}
            QTableWidget::item:selected {{
                background-color: {COLOR_DARK_BG_HOVER};
                color: {COLOR_DARK_FG};
            }}
    """


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


class ClusterStatusWidget(QWidget):
    def __init__(self, parent=None, slurm_connection=None):
        super().__init__(parent)

        self.setWindowTitle(APP_TITLE)
        # Set minimum size, allow resizing
        self.setMinimumSize(QSize(MIN_WIDTH, MIN_HEIGHT))
        self.resize(MIN_WIDTH, MIN_HEIGHT)  # Start with minimum size

        self.themes = {
            THEME_DARK: get_dark_theme_stylesheet(),
        }
        self.current_theme = THEME_DARK
        self.setStyleSheet(self.themes[self.current_theme])

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)
        self.setLayout(self.main_layout)

        # Use QGridLayout for the user status content
        self.user_status_grid_layout = QGridLayout()
        self.user_status_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.user_status_grid_layout.setHorizontalSpacing(3)  # Increased spacing for clarity
        self.user_status_grid_layout.setVerticalSpacing(6)   # Increased spacing between rows

        # Create a horizontal layout for the title and legend
        title_legend_layout = QHBoxLayout()
        title_legend_layout.setContentsMargins(0, 0, 0, 0)
        title_legend_layout.setSpacing(0)  # Set spacing to 0 here, spacing is handled by the vertical separator margins

        # Add section title to the horizontal layout
        section_title = QLabel("Node Status")  # Changed title for clarity
        section_title.setObjectName("sectionTitle")
        title_legend_layout.addWidget(section_title)

        # Add a vertical separator
        vertical_separator = QFrame()
        vertical_separator.setObjectName("verticalSeparator")
        vertical_separator.setFrameShape(QFrame.Shape.VLine)
        vertical_separator.setFrameShadow(QFrame.Shadow.Sunken)
        title_legend_layout.addWidget(vertical_separator)

        # Create and add the status key section to the horizontal layout
        status_key_layout = self.create_status_key_section()
        title_legend_layout.addLayout(status_key_layout)

        # Add stretch to push the legend to the right
        title_legend_layout.addStretch()

        # Add the horizontal layout to the main layout
        self.main_layout.addLayout(title_legend_layout)

        # Add a separator line below the title and legend

        self.main_layout.addLayout(self.user_status_grid_layout)  # Add the grid layout to main layout

        self.main_layout.addStretch()  # Push content to the top

        # Initial data fetch and update
        if slurm_connection is None:
            self.sc_ = SlurmConnection("./configs/slurm_config.yaml")
            self.sc_.connect()
        else:
            self.sc_ = slurm_connection

    def add_separator(self):
        separator = QFrame()
        separator.setObjectName("sectionSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.main_layout.addWidget(separator)

    def create_status_key_section(self):
        status_key_layout = QVBoxLayout()
        status_key_layout.setContentsMargins(0, 0, 0, 0)
        status_key_layout.setSpacing(5)

        # section_title = QLabel("Status Legend") # Removed title from here
        # section_title.setObjectName("sectionTitle")
        # status_key_layout.addWidget(section_title)

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
            color_widget.setStyleSheet(self.themes[self.current_theme])

            key_row_layout.addWidget(color_widget)

            text_label = QLabel(text)
            key_row_layout.addWidget(text_label)
            key_row_layout.addStretch()

            status_key_layout.addLayout(key_row_layout)

        # self.main_layout.addLayout(status_key_layout) # Removed from here
        return status_key_layout  # Return the layout instead of adding directly

    def create_overall_stats_section(self):
        # This section will be updated dynamically
        overall_stats_layout = QVBoxLayout()
        overall_stats_layout.setContentsMargins(0, 0, 10, 0)
        overall_stats_layout.setSpacing(5)

        section_title = QLabel("Overall Statistics")
        section_title.setObjectName("sectionTitle")
        overall_stats_layout.addWidget(section_title)

        # Add placeholder labels that will be updated
        self.overall_stats_labels = {}
        stats_keys = ["gpu_stats", "users_stats"]  # Removed sgpu_stats for simplicity
        for key in stats_keys:
            label = QLabel("")
            self.overall_stats_labels[key] = label
            overall_stats_layout.addWidget(label)

        self.main_layout.addLayout(overall_stats_layout)

    def update_overall_stats(self, stats_data):
        """
        Updates the overall statistics labels.

        Args:
            stats_data (dict): A dictionary containing statistics like
                               total_gpus, used_gpus, user_gpu_counts, etc.
        """
        total_gpus = stats_data.get("total_gpus", 0)
        used_gpus = stats_data.get("used_gpus", 0)
        available_gpus = total_gpus - used_gpus
        user_gpu_counts = stats_data.get("user_gpu_counts", {})

        # self.overall_stats_labels["gpu_stats"].setText(
        #     f"Total GPUs: {total_gpus} \nUsed: {used_gpus} \nAvailable: {available_gpus}")

        # Sort users by GPU count descending for better readability
        sorted_users = sorted(user_gpu_counts.items(), key=lambda item: item[1], reverse=True)
        # users_text = "User GPU Usage:\n" + "\n".join([f"{user}: {count}" for user, count in sorted_users])
        # self.overall_stats_labels["users_stats"].setText(users_text)

    def calculate_overall_stats(self, nodes_data):
        """
        Calculates overall statistics from the nodes data.
        This is a simplified example. For accurate user stats, you'd typically
        need to parse squeue output or use a more detailed Slurm API call.
        """
        total_gpus = 0
        used_gpus = 0
        user_gpu_counts = {}  # Simplified: counts GPUs on allocated/mixed nodes

        for node_info in nodes_data:
            state = node_info.get("State", "").upper()
            gres = node_info.get("Gres", "")
            gres_used = node_info.get("GresUsed", "")

            node_total_gpus = 0
            node_used_gpus = 0

            if "total_gres/gpu" in node_info.keys():
                node_total_gpus = int(node_info.get("total_gres/gpu", ""))
                total_gpus += node_total_gpus
            if "alloc_gres/gpu" in node_info.keys():
                node_used_gpus = int(node_info.get("alloc_gres/gpu", ""))
                used_gpus += node_used_gpus

            # Simplified user stats based on node state - this is NOT accurate
            # You need to parse squeue output to get actual user-job-GPU mappings
            if "ALLOCATED" in state or "MIXED" in state:
                # Placeholder: In a real scenario, you'd associate used GPUs with users
                # based on squeue output. This just counts GPUs on allocated nodes.
                user = "allocated_node_user"  # This is a simplification
                user_gpu_counts[user] = user_gpu_counts.get(user, 0) + node_used_gpus

        # Note: The user_gpu_counts calculated here is a very rough estimate
        # based on node state. For accurate per-user usage, you MUST parse squeue.
        # If your slurm_connection has a method for this, use it in fetch_and_update_status

        return {
            "total_gpus": total_gpus,
            "used_gpus": used_gpus,
            "user_gpu_counts": user_gpu_counts  # This needs refinement with squeue data
        }

    def update_status(self, nodes_data, jobs_data):
        """
        Updates the visualization based on the provided scontrol show nodes data
        using a QGridLayout for better alignment.

        Args:
            nodes_data (list): A list of dictionaries, where each dictionary
                               represents a node entry from scontrol show nodes.
        """
        # Clear previous widgets from the grid layout
        # Iterate in reverse to safely remove items
        nodes_data = sort_nodes_data(nodes_data)
        self.total_gpu_used = 0
        self.total_gpu = 0
        for i in reversed(range(self.user_status_grid_layout.count())):
            item = self.user_status_grid_layout.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Determine the maximum number of blocks needed for layout purposes
        # This helps in setting column stretches correctly
        max_gpu_count = 0
        for node_info in nodes_data:
            max_gpu_count = max(int(node_info.get("total_gres/gpu", 0)), max_gpu_count)

        # Populate with new data
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
                left_line.setStyleSheet("border: none; border-top: 1px dotted #999;")

                # Label with partition name
                partition_label = str(node_info['Partitions']).replace(" ", "_")
                partition_label = QLabel(partition_label)
                partition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                partition_label.setStyleSheet("color: #666;")

                # Right dotted line
                right_line = QFrame()
                right_line.setFrameShape(QFrame.Shape.HLine)
                right_line.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
                right_line.setStyleSheet("border: none; border-top: 1px dotted #999;")

                # Add widgets to container layout with stretch
                separator_layout.addWidget(left_line, 1)  # Stretch factor 1
                separator_layout.addWidget(partition_label, 0)  # No stretch
                separator_layout.addWidget(right_line, 1)  # Stretch factor 1

                # Add the container to your grid
                self.user_status_grid_layout.addWidget(separator_container, row_index + row_offset, 0, 1, max(1, 35))
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
            # Corrected: Use name_label.sizePolicy() instead of QApplication.sizePolicy(name_label)
            name_label.setSizePolicy(
                name_label.sizePolicy().horizontalPolicy(),
                name_label.sizePolicy().verticalPolicy()
            )

            if "total_gres/gpu" in node_info.keys():
                total_gpus = int(node_info.get("total_gres/gpu", ""))
            else:
                total_gpus = 0
            if "alloc_gres/gpu" in node_info.keys():
                used_gpus = int(node_info.get("alloc_gres/gpu", ""))
            else:
                used_gpus = 0

            self.user_status_grid_layout.addWidget(name_label, row_index + row_offset, 0)
            if total_gpus > 8:
                for r in range(round(((total_gpus - 8) / 8) + 0.49)):
                    self.user_status_grid_layout.addWidget(QLabel(""), row_index + 1 + r + row_offset, 0)

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
                    for k in STUDENTS_JOBS_KEYWORD:
                        if k in job["Account"]:
                            stud_used += int(job["GPUs"])

                block_states = ["stud_used"] * stud_used + ["prod_used"] * \
                    (used_gpus - stud_used) + ["available"] * (total_gpus - used_gpus)
                # block_states = ["used"] * used_gpus + ["available"] * (total_gpus - used_gpus)
            # Finally, assume idle if none of the above
            elif "IDLE" in state:
                block_states = ["available"] * total_gpus
            else:
                # Handle any other potential states
                print(f"Warning: Unhandled node state for {node_name}: {state}")
                block_states = ["unavailable"] * total_gpus  # Default to unavailable

            block_size = 16
            col_offset = 0
            i = 0
            # Add block widgets starting from the second column (column 1)
            for col_offset, block_state in enumerate(block_states):
                if col_offset - i > 7:
                    row_offset += 1
                    i = 8

                block_widget = QWidget()
                block_widget.setFixedSize(QSize(block_size, block_size))
                block_widget.setObjectName("coloredBlock")
                # Use dynamic property to apply specific styles based on state
                block_widget.setProperty("data-state", block_state)
                # Apply stylesheet again to ensure dynamic property is considered
                block_widget.setStyleSheet(self.themes[self.current_theme])

                # Add block widget to the grid at the current row and column (1 + offset)
                self.user_status_grid_layout.addWidget(
                    block_widget, row_index + row_offset, 1 + col_offset - i)

        # --- Layout Stretching ---
        # Ensure the first column (node name) takes minimal space,
        # block columns take fixed space, and any extra space is at the end.
        # Set stretch for the name column (column 0) to 0
        self.user_status_grid_layout.setColumnStretch(0, 0)

        # Set stretch for the block columns (from 1 up to max_gpu_count) to 0
        # This prevents blocks from stretching and keeps them compact
        for i in range(1, max_gpu_count + 1):
            self.user_status_grid_layout.setColumnStretch(i, 0)

        # Add a stretch to the column *after* the last potential block column (max_gpu_count + 1)
        # This pushes the content to the left and fills remaining space
        self.user_status_grid_layout.setColumnStretch(max_gpu_count + 1, 1)

        # Ensure rows don't stretch unnecessarily
        # Add stretch to the row *after* the last data row
        if nodes_data:  # Only add stretch if there's data
            self.user_status_grid_layout.setRowStretch(len(nodes_data), 1)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    sc_ = SlurmConnection("./configs/slurm_config.yaml")
    sc_.connect()
    window = ClusterStatusWidget(slurm_connection=sc_)

    # The initial data fetch is now handled by the timer's first trigger
    # window.update_status(nodes_data) # No longer needed here

    window.show()
    sys.exit(app.exec())
