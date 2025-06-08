from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QProgressBar
from modules.defaults import *

# VIEW  
class SlurmConnectionView(QWidget):
    """View: Displays SLURM connection status and information"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout(self)
        
        # Connection status
        self.status_label = QLabel("Disconnected")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Progress indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Cluster info display
        self.info_label = QLabel("No cluster information available")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
    
    def show_connected_status(self):
        """Show connected status"""
        self.status_label.setText("Connected to SLURM")
        self.status_label.setStyleSheet(f"color: {COLOR_GREEN}; font-weight: bold;")
        self.progress_bar.setVisible(False)
    
    def show_disconnected_status(self):
        """Show disconnected status"""
        self.status_label.setText("Disconnected from SLURM")
        self.status_label.setStyleSheet(f"color: {COLOR_RED}; font-weight: bold;")
        self.progress_bar.setVisible(False)
    
    def show_connecting_status(self):
        """Show connecting status"""
        self.status_label.setText("Connecting to SLURM...")
        self.status_label.setStyleSheet(f"color: {COLOR_ORANGE}; font-weight: bold;")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
    
    def update_cluster_info(self, info: dict):
        """Update cluster information display"""
        info_text = f"""
        <b>Cluster Information:</b><br>
        Host: {info.get('hostname', 'Unknown')}<br>
        User: {info.get('remote_user', 'Unknown')}<br>
        SLURM Version: {info.get('slurm_version', 'Unknown')}<br>
        Total Nodes: {info.get('num_nodes', 'Unknown')}<br>
        Home Directory: {info.get('remote_home', 'Unknown')}
        """
        self.info_label.setText(info_text)
    
    def update_submission_options(self, options: dict):
        """Update submission options display"""
        partitions = options.get('partitions', [])
        accounts = options.get('accounts', [])
        
        options_text = f"""
        <b>Available Options:</b><br>
        Partitions: {', '.join(partitions[:5])}{'...' if len(partitions) > 5 else ''}<br>
        Accounts: {', '.join(accounts[:3])}{'...' if len(accounts) > 3 else ''}
        """
        
        # Append to existing info
        current_text = self.info_label.text()
        self.info_label.setText(current_text + "<br>" + options_text)

