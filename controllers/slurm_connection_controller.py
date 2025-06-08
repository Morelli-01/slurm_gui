from threading import Thread
from typing import Optional
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from models.slurm_connection_model import SlurmConnectionModel
from views.slurm_connection_view import SlurmConnectionView

class SlurmWorker(QThread):
    """Worker thread for SLURM operations"""
    connected = pyqtSignal(bool)
    data_ready = pyqtSignal(list, list)  # nodes_data, queue_jobs
    error_occurred = pyqtSignal(str)
    
    def __init__(self, model):
        super().__init__()
        self.model = model
    
    def run(self):
        try:
            if not self.model.is_connected():
                result = self.model.connect()
                self.connected.emit(result)
                if not result:
                    self.data_ready.emit([], [])
                    return
            
            nodes_data = self.model.fetch_nodes_info()
            queue_jobs = self.model.fetch_job_queue()
            self.data_ready.emit(nodes_data, queue_jobs)
            
        except Exception as e:
            print(f"Worker error: {e}")
            self.error_occurred.emit(str(e))
            self.connected.emit(False)
            self.data_ready.emit([], [])

# CONTROLLER
class SlurmConnectionController(QObject):
    """Controller: Manages SLURM operations and coordinates model/view"""
    
    # Signals for external communication
    connection_established = pyqtSignal(bool)
    data_fetched = pyqtSignal(list, list)  # nodes, jobs
    job_submitted = pyqtSignal(str)  # job_id
    error_occurred = pyqtSignal(str)
    
    def __init__(self, config_path: str = None):
        super().__init__()
        
        # Create model and view
        self.model = SlurmConnectionModel()
        self.view = SlurmConnectionView()
        self.worker = SlurmWorker(self.model)
        self.worker.connected.connect(self.connection_established.emit)
        self.worker.data_ready.connect(self.data_fetched.emit)
        self.worker.error_occurred.connect(self.error_occurred.emit)
        # self.worker.finished.connect(self.worker.deleteLater)
        # Connect model signals
        self._connect_model_signals()
        
        # Load configuration if provided
        if config_path:
            self.load_configuration(config_path)
    
    def _connect_model_signals(self):
        """Connect model signals to controller actions"""
        self.model.connection_status_changed.connect(self._on_connection_changed)
        self.model.cluster_info_updated.connect(self._on_cluster_info_updated)
        self.model.submission_options_updated.connect(self._on_submission_options_updated)
    
    def _on_connection_changed(self, connected: bool):
        """Handle connection status changes"""
        self.connection_established.emit(connected)
        if connected:
            self.view.show_connected_status()
        else:
            self.view.show_disconnected_status()
    
    def _on_cluster_info_updated(self, info: dict):
        """Handle cluster info updates"""
        self.view.update_cluster_info(info)
    
    def _on_submission_options_updated(self, options: dict):
        """Handle submission options updates"""
        self.view.update_submission_options(options)
    
    # Public interface methods
    def load_configuration(self, config_path: str) -> bool:
        """Load connection configuration"""
        return self.model.load_configuration(config_path)
    
    def connect(self) -> bool:
        """Establish connection to SLURM cluster"""
        return self.model.connect()
    
    def disconnect(self):
        """Disconnect from SLURM cluster"""
        self.model.disconnect()
    
    def is_connected(self) -> bool:
        """Check if connected to SLURM"""
        return self.model.is_connected()
    
    def fetch_data_async(self):
        """Fetch cluster data asynchronously"""
        # self.worker.start()
        t = Thread(target=self.worker.start)
        t.start()
    
    def submit_job(self, job, discord_settings=None) -> Optional[str]:
        """Submit a job to SLURM"""
        try:
            job_id = self.model.submit_job(job, discord_settings)
            if job_id:
                self.job_submitted.emit(job_id)
            return job_id
        except Exception as e:
            self.error_occurred.emit(f"Job submission failed: {str(e)}")
            return None
    
    def get_job_logs(self, job, preserve_progress_bars=False):
        """Get job logs"""
        try:
            return self.model.get_job_logs(job, preserve_progress_bars)
        except Exception as e:
            self.error_occurred.emit(f"Failed to get logs: {str(e)}")
            return "", ""
    
    # Getters for external access
    def get_cluster_info(self):
        """Get current cluster information"""
        return self.model.get_cluster_info()
    
    def get_submission_options(self):
        """Get current submission options"""
        return self.model.get_submission_options()
    
    def get_view(self):
        """Get the view widget"""
        return self.view
    
    def get_model(self):
        """Get the model"""
        return self.model

