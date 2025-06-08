from controllers.slurm_connection_controller import SlurmConnectionController
from PyQt6.QtWidgets import QWidget, QVBoxLayout

# MAIN WIDGET (Facade)
class SlurmConnectionWidget(QWidget):
    """Main SLURM Connection Widget - acts as a facade maintaining the original interface"""
    
    def __init__(self, config_path: str = None, parent=None):
        super().__init__(parent)
        
        # Create MVC controller
        self.controller = SlurmConnectionController(config_path)
        
        # Setup layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.controller.get_view())
        
        # Expose controller signals for external use
        self.connection_established = self.controller.connection_established
        self.data_fetched = self.controller.data_fetched
        self.job_submitted = self.controller.job_submitted
        self.error_occurred = self.controller.error_occurred
    
    # Maintain original interface methods
    def connect(self) -> bool:
        """Connect to SLURM cluster"""
        return self.controller.connect()
    
    def disconnect(self):
        """Disconnect from SLURM cluster"""
        self.controller.disconnect()
    
    def check_connection(self) -> bool:
        """Check connection status - legacy method name"""
        return self.controller.is_connected()
    
    def is_connected(self) -> bool:
        """Check connection status"""
        return self.controller.is_connected()
    
    def run_command(self, command: str):
        """Run command on remote server"""
        return self.controller.get_model().run_command(command)
    
    def fetch_data_async(self):
        """Fetch cluster data asynchronously"""
        self.controller.fetch_data_async()
    
    def submit_job(self, job, discord_settings=None):
        """Submit job to SLURM"""
        return self.controller.submit_job(job, discord_settings)
    
    def get_job_logs(self, job, preserve_progress_bars=False):
        """Get job logs"""
        return self.controller.get_job_logs(job, preserve_progress_bars)
    
    def update_credentials_and_reconnect(self):
        """Update credentials and reconnect - legacy method"""
        # Reload configuration and reconnect
        config_path = getattr(self, '_config_path', None)
        if config_path:
            self.controller.load_configuration(config_path)
        return self.controller.connect()
    
    def close(self):
        """Close connection - legacy method"""
        self.controller.disconnect()
    
    # Legacy methods for backward compatibility
    def _fetch_nodes_infos(self):
        """Legacy method for fetching node info"""
        return self.controller.get_model().fetch_nodes_info()
    
    def _fetch_squeue(self):
        """Legacy method for fetching job queue"""
        return self.controller.get_model().fetch_job_queue()    
    
    def _read_maintenances(self):
        """Legacy method for fetching job queue"""
        return self.controller.get_model().read_maintenances()
    
    def get_running_jobs(self):
        """Get running jobs for current user"""
        if not self.is_connected():
            return []
        
        all_jobs = self._fetch_squeue()
        remote_user = self.controller.get_cluster_info().get('remote_user')
        if not remote_user:
            return []
            
        return [job for job in all_jobs if job.get("User") == remote_user]
    
    def list_remote_directories(self, path: str):
        """List remote directories"""
        if not self.check_connection():
            return []
        try:
            command = f"ls -aF '{path}'"
            stdout, stderr = self.run_command(command)
            
            if stderr:
                if "Permission denied" in stderr or "No such file or directory" in stderr:
                    print(f"Error accessing remote path {path}: {stderr}")
                    return []
                print(f"Warning listing remote directories in {path}: {stderr}")
            
            directories = []
            for line in stdout.split('\n'):
                line = line.strip()
                if line and line.endswith('/') and line not in ('./', '../'):
                    directories.append(line.rstrip('/'))
            return sorted(directories, key=str.lower)
        except Exception as e:
            print(f"Failed to list remote directories: {e}")
            return []
    
    def remote_path_exists(self, path: str) -> bool:
        """Check if remote path exists"""
        if not self.check_connection():
            return False
        try:
            stdout, stderr = self.run_command(
                f"test -d '{path}' || test -e '{path}' && echo 'exists' || echo 'not_exists'")
            return stdout.strip() == 'exists'
        except Exception as e:
            print(f"Error checking remote path existence: {e}")
            return False
    
    # Property accessors for backward compatibility
    @property
    def host(self):
        return self.controller.get_model().get_connection_config()['host']
    
    @property
    def user(self):
        return self.controller.get_model().get_connection_config()['user']
    
    @property
    def password(self):
        return self.controller.get_model().get_connection_config()['password']
    
    @property
    def remote_home(self):
        return self.controller.get_cluster_info().get('remote_home')
    
    @property
    def remote_user(self):
        return self.controller.get_cluster_info().get('remote_user')
    
    @property
    def partitions(self):
        return self.controller.get_submission_options().get('partitions', [])
    
    @property
    def constraints(self):
        return self.controller.get_submission_options().get('constraints', [])
    
    @property
    def qos_list(self):
        return self.controller.get_submission_options().get('qos_list', [])
    
    @property
    def accounts(self):
        return self.controller.get_submission_options().get('accounts', [])
    
    @property
    def gres(self):
        return self.controller.get_submission_options().get('gres', [])

# Migration wrapper for backward compatibility
class SlurmConnection(SlurmConnectionWidget):
    """Backward compatibility wrapper for the original SlurmConnection class"""
    
    def __init__(self, config_path: str = "slurm_config.yaml"):
        super().__init__(config_path)
        self._config_path = config_path
        self.config_path = config_path
        
        # Maintain original attribute names
        self.client = None
        self.connected_status = False
        
        # Connect to model signals to update legacy attributes
        self.controller.connection_established.connect(self._update_legacy_attributes)
    
    def _update_legacy_attributes(self, connected: bool):
        """Update legacy attributes when connection status changes"""
        self.connected_status = connected
        if connected:
            self.client = self.controller.get_model()._client
        else:
            self.client = None
