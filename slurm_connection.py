import configparser, sys
import functools
import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
from modules.new_job_dp import NewJobDialog
import paramiko
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal
# Constants
JOB_CODES = {
    "CD": "COMPLETED",
    "CG": "COMPLETING",
    "F": "FAILED",
    "PD": "PENDING",
    "PR": "PREEMPTED",
    "R": "RUNNING",
    "S": "SUSPENDED",
    "ST": "STOPPED",
}

# Use QThread for SLURM operations

class SlurmWorker(QThread):
    connected = pyqtSignal(bool)
    data_ready = pyqtSignal(list, list)  # For nodes_data and queue_jobs
    
    def __init__(self, slurm_connection):
        super().__init__()
        self.slurm_connection = slurm_connection
        
    def run(self):
        try:
            if not self.slurm_connection.is_connected():
                result = self.slurm_connection.connect()
                self.connected.emit(result)
                
            nodes_data = self.slurm_connection._fetch_nodes_infos()
            queue_jobs = self.slurm_connection._fetch_squeue()
            self.data_ready.emit(nodes_data, queue_jobs)
        except Exception as e:
            print(f"Worker error: {e}")
            self.connected.emit(False)

def require_connection(func):
    """Decorator to ensure SSH connection is established before executing a method."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.check_connection():
            raise ConnectionError("SSH connection not established. Please connect first.")
        return func(self, *args, **kwargs)
    return wrapper


def parse_duration(s: str) -> timedelta:
    """Parse a duration string in SLURM format to a timedelta object."""
    days = 0
    if '-' in s:
        # Format: D-HH:MM:SS
        day_part, time_part = s.split('-')
        days = int(day_part)
    else:
        time_part = s
    
    parts = [int(p) for p in time_part.split(':')]
    
    if len(parts) == 2:        # MM:SS
        h, m, s = 0, parts[0], parts[1]
    elif len(parts) == 3:      # HH:MM:SS
        h, m, s = parts
    else:
        raise ValueError(f"Invalid time format: {s}")
        
    return timedelta(days=days, hours=h, minutes=m, seconds=s)


class SlurmConnection:
    """
    Class to manage SSH connections to a SLURM cluster and perform SLURM operations.
    """
    
    def __init__(self, config_path: str = "slurm_config.yaml"):
        """
        Initialize the SLURM connection.
        
        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path
        self._load_configuration(self.config_path)
        self.connected_status = False
        self.client = None

        # Cluster information
        self.remote_user = None
        self.user_groups = None
        self.num_nodes = None
        self.hostname = None
        self.slurm_version = None

        # Submission options
        self.partitions = []
        self.constraints = []
        self.qos_list = []
        self.accounts = []
        self.gres = []
        self.remote_home = None

    def _load_configuration(self, config_path: str) -> None:
        """
        Load configuration from file.
        
        Args:
            config_path: Path to the configuration file
        """
        config = configparser.ConfigParser()
        config.read(config_path)

        # Access configuration values
        try:
            self.host = config['GeneralSettings']['clusterAddress']
            self.password = config['GeneralSettings']['psw']
            self.user = config['GeneralSettings']['username']
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid configuration file: {e}")

    def check_connection(self) -> bool:
        """Check if the connection is established."""
        return self.connected_status

    def connect(self) -> bool:
        """
        Establish an SSH connection to the SLURM cluster.
        
        Returns:
            bool: True if connection succeeded, False otherwise
        """
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            self.client.connect(self.host, username=self.user, password=self.password)
            self.connected_status = True
            print(f"Connected to {self.host}")
            
            # Initialize cluster information
            self._fetch_basic_info()
            self._fetch_submission_options()
            
            # Create log directory
            self.remote_home, _ = self.run_command("echo $HOME")
            self.remote_home = self.remote_home.strip()
            self.run_command(f"mkdir -p {self.remote_home}/.logs")
            
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self.connected_status = False
            return False

    def is_connected(self) -> bool:
        """
        Check if the SSH connection is active.
        
        Returns:
            bool: True if connection is active, False otherwise
        """
        try:
            transport = self.client.get_transport() if self.client else None
            
            if transport and transport.is_active():
                # Try sending a simple command with a short timeout to check if the channel is still working
                channel = transport.open_session(timeout=1)
                if channel:
                    channel.close()
                    self.connected_status = True
                    return True
            
            self.connected_status = False
            return False
        except paramiko.SSHException as e:
            print(f"SSH error: {e}")
            self.connected_status = False
            return False
        except Exception as e:
            print(f"Connection error: {e}")
            self.connected_status = False
            return False

    @require_connection
    def get_running_jobs(self):
        all_jobs = self._fetch_squeue()
        filtered_jobs = [job for job in all_jobs if job["User"] == self.remote_user]
        return filtered_jobs

    @require_connection
    def run_command(self, command: str) -> Tuple[str, str]:
        """
        Run a command on the remote server.
        
        Args:
            command: Command to execute
            
        Returns:
            Tuple[str, str]: (stdout, stderr) output of the command
        """
            
        stdin, stdout, stderr = self.client.exec_command(command)
        return stdout.read().decode().strip(), stderr.read().decode().strip()

    @require_connection
    def _fetch_basic_info(self) -> None:
        """Fetch basic cluster information."""
        try:
            # Execute commands to fetch cluster information
            commands = {
                "remote_user": "whoami",
                "user_groups": "groups",
                "num_nodes": "sinfo -h -o '%D' | awk '{s+=$1} END {print s}'",
                "hostname": "hostname",
                "slurm_version": "scontrol --version"
            }
            
            for attr, cmd in commands.items():
                result, _ = self.run_command(cmd)
                setattr(self, attr, result.strip())
                
        except Exception as e:
            print(f"Failed to fetch system info: {e}")

    @require_connection
    def _fetch_submission_options(self) -> None:
        """Fetch SLURM submission options."""
        try:
            # Fetch partitions
            partitions_out, _ = self.run_command("sinfo -h -o '%P'")
            self.partitions = sorted(set(partitions_out.splitlines()))

            # Fetch constraints
            constraints_out, _ = self.run_command("sinfo -o '%f' | sort | uniq")
            self.constraints = sorted(set(constraints_out.split()))

            # Fetch QoS options
            qos_out, _ = self.run_command("sacctmgr show qos format=Name -n -P")
            self.qos_list = sorted(set(qos_out.splitlines()))

            # Fetch user accounts
            if self.remote_user:
                acc_out, _ = self.run_command(
                    f"sacctmgr show associations user={self.remote_user} format=Account -n -P")
                self.accounts = sorted(set(acc_out.splitlines()))

            # Fetch GRES (Generic Resources)
            gres_out, _ = self.run_command("scontrol show gres")
            self.gres = [line.strip() for line in gres_out.splitlines() if "Name=" in line]

        except Exception as e:
            print(f"Failed to fetch submission options: {e}")

    @require_connection
    def submit_job(self, job_name: str, partition: str, time_limit: str, command: str, account: str,
                   constraint: Optional[str] = None, qos: Optional[str] = None,
                   gres: Optional[str] = None, nodes: int = 1, ntasks: int = 1,
                   output_file: str = ".logs/out_%A.log", error_file: str = ".logs/err_%A.log", memory: str="1G", cpus:int = 1) -> Optional[str]:
        """
        Submit a job to the SLURM scheduler.
        
        Args:
            job_name: Job name
            partition: SLURM partition
            time_limit: Time limit in format HH:MM:SS
            command: Command to execute
            account: SLURM account
            constraint: Node constraints
            qos: Quality of Service
            gres: Generic Resources
            nodes: Number of nodes
            ntasks: Number of tasks
            output_file: Path for job output file
            error_file: Path for job error file
            
        Returns:
            str: Job ID if submission was successful, None otherwise
        """

        # Create SLURM script content
        script_content = self._create_job_script(
            job_name, partition, time_limit, command, account,
            constraint, qos, gres, nodes, ntasks, output_file, error_file, memory, cpus
        )

        # Save script locally
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sh") as f:
            f.write(script_content)
            local_script_path = f.name

        # Remote path (temporary directory)
        remote_script_path = f"/tmp/{os.path.basename(local_script_path)}"

        try:
            # Upload script via SFTP
            sftp = self.client.open_sftp()
            sftp.put(local_script_path, remote_script_path)
            sftp.close()

            # Submit via sbatch
            stdout, stderr = self.run_command(f"sbatch {remote_script_path}")
            if stderr:
                os.remove(local_script_path)
                raise RuntimeError(f"SLURM error: {stderr}")
            else:
                os.remove(local_script_path)

            # Cleanup local file

            

            # Parse job ID
            job_id = None
            if "Submitted batch job" in stdout:
                job_id = stdout.strip().split()[-1]

            return job_id

        except Exception as e:
            raise RuntimeError(f"Job submission failed: {e}")

    def _create_job_script(self, job_name: str, partition: str, time_limit: str, command: str, account: str,
                          constraint: Optional[str], qos: Optional[str], gres: Optional[str], 
                          nodes: int, ntasks: int, output_file: str, error_file: str, memory:str, cpus:int) -> str:
        """
        Create the content of a SLURM job script.
        
        Args:
            Same as submit_job method
            
        Returns:
            str: Content of SLURM job script
        """
        script_lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name=\"{job_name}\"",
            f"#SBATCH --partition={partition.replace("*", "")}",
            f"#SBATCH --time={time_limit}",
            f"#SBATCH --nodes={nodes}",
            f"#SBATCH --ntasks={ntasks}",
            f"#SBATCH --output={self.remote_home}/{output_file}",
            f"#SBATCH --error={self.remote_home}/{error_file}",
            f"#SBATCH --mem={memory}",
            f"#SBATCH --cpus-per-task={cpus}",

        ]
        
        # Add optional parameters
        if "None" not in constraint:
            script_lines.append(f"#SBATCH --constraint={constraint}")
        if qos:
            script_lines.append(f"#SBATCH --qos={qos}")
        if account:
            script_lines.append(f"#SBATCH --account={account}")
        if gres:
            script_lines.append(f"#SBATCH --gres={gres}")

        script_lines.append("")  # Blank line
        script_lines.append(command)

        return "\n".join(script_lines)

    @require_connection
    def get_job_logs(self, job_id: str) -> Tuple[str, str]:
        """
        Get the output and error logs for a job.
        
        Args:
            job_id: Job ID
            
        Returns:
            Tuple[str, str]: (stdout, stderr) logs
        """
        if not self.is_connected():
            raise ConnectionError("SSH connection not established.")

        remote_log_dir = f"{self.remote_home}/.logs"
        stdout_file = f"{remote_log_dir}/out_{job_id}.log"
        stderr_file = f"{remote_log_dir}/err_{job_id}.log"

        stdout, stderr = "", ""
        
        # Get stdout log
        try:
            out, _ = self.run_command(f"cat {stdout_file}")
            stdout = out.strip()
        except Exception:
            stdout = f"[!] Output log {stdout_file} not found or unreadable."

        # Get stderr log
        try:
            err, _ = self.run_command(f"cat {stderr_file}")
            stderr = err.strip()
        except Exception:
            stderr = f"[!] Error log {stderr_file} not found or unreadable."

        return stdout, stderr

    def update_credentials_and_reconnect(self) -> None:
        """Update credentials from config file and reconnect."""
        self.__init__(self.config_path)
        self.connect()

    @require_connection
    def _read_maintenances(self) -> Optional[str]:
        """
        Read SLURM maintenance reservations.
        
        Returns:
            Optional[str]: Maintenance reservation information, None if none exist
        """
        msg_out, _ = self.run_command("scontrol show reservation 2>/dev/null")
        return None if "No reservations in the system" in msg_out else msg_out

    @require_connection
    def _fetch_nodes_infos(self) -> List[Dict[str, Any]]:
        """
        Fetch detailed information about all nodes.
        
        Returns:
            List[Dict[str, Any]]: List of node information dictionaries
        """
        msg_out, _ = self.run_command("scontrol show nodes")
        nodes = msg_out.split("\n\n")
        nodes_arr = []
        
        for node in nodes:
            if not node.strip():
                continue
                
            node_dict = {}
            for line in node.split("\n"):
                for feature in line.split():
                    if "=" not in feature:
                        continue
                        
                    if "AllocTRES" in feature:
                        self._parse_tres(feature, "alloc_", node_dict)
                    elif "CfgTRES" in feature:
                        self._parse_tres(feature, "total_", node_dict)
                    else:
                        key, value = feature.strip().split("=", 1)
                        node_dict[key] = value
                        
            nodes_arr.append(node_dict)

        return nodes_arr
    
    def _parse_tres(self, tres_string: str, prefix: str, node_dict: Dict[str, Any]) -> None:
        """
        Parse TRES (Trackable RESources) strings.
        
        Args:
            tres_string: String containing TRES information
            prefix: Prefix to add to keys in node_dict
            node_dict: Dictionary to add parsed values to
        """
        parts = tres_string.split("=", 1)[1].split(",")
        for part in parts:
            if not part:
                continue
            try:
                key, value = part.split("=")
                node_dict[f"{prefix}{key}"] = value
            except ValueError:
                pass

    @require_connection
    def _fetch_squeue(self) -> List[Dict[str, Any]]:
        """
        Fetch information about jobs in the queue.
        
        Returns:
            List[Dict[str, Any]]: List of job information dictionaries
        """
        # Use a more flexible job command with clear field separators
        cmd = "squeue -O jobarrayid:\\;,Reason:\\;,NodeList:\\;,Username:\\;,tres-per-job:\\;," + \
              "tres-per-task:\\;,tres-per-node:\\;,Name:\\;,Partition:\\;,StateCompact:\\;," + \
              "Timelimit:\\;,TimeUsed:\\;,NumNodes:\\;,NumTasks:\\;,Reason:\\;,MinMemory:\\;," + \
              "MinCpus:\\;,Account:\\;,PriorityLong:\\;,jobid:\\;,tres:\\;,nice:"
            
        out, _ = self.run_command(cmd)
        job_queue = []
        
        # Skip header row
        for i, line in enumerate(out.splitlines()):
            if i == 0:
                continue
                
            fields = line.split(";")
            if len(fields) < 21:
                print(f"Warning: incomplete job data: {line}")
                continue
                
            try:
                job_dict = self._parse_job_fields(fields)
                job_queue.append(job_dict)
            except (IndexError, ValueError) as e:
                print(f"Error parsing job data: {e} - {line}")
                
        return job_queue
    
    def _parse_job_fields(self, fields: List[str]) -> Dict[str, Any]:
        """
        Parse job fields from squeue output.
        
        Args:
            fields: List of field values from squeue
            
        Returns:
            Dict[str, Any]: Dictionary of job information
        """
        job_dict = {
            "Job ID": fields[0],
            "Reason": fields[1],
            "Nodelist": fields[2],
            "User": fields[3],
            "Job Name": fields[7],
            "Partition": fields[8],
            "Status": JOB_CODES.get(fields[9], "UNKNOWN"),
            "Time Limit": fields[10],
            "Time Used": [fields[11], parse_duration(fields[11]) if fields[11] else timedelta()],
            "Account": fields[17],
            "Priority": int(fields[18]) if fields[18].isdigit() else 0,
            "GPUs": 0  # Default value
        }
        
        # Parse allocated resources
        alloc_gres = fields[20].split(",")
        for resource in alloc_gres:
            if "=" not in resource:
                continue
                
            key, value = resource.split("=")
            if key == "cpu":
                job_dict["CPUs"] = int(value)
            elif key == "mem":
                job_dict["RAM"] = value
            elif key == "gres/gpu":
                job_dict["GPUs"] = int(value)
            elif key == "billing":
                job_dict["Billing"] = int(value)
        
        # For pending jobs, use reason as nodelist
        if job_dict["Status"] == "PENDING":
            job_dict["Nodelist"] = job_dict["Reason"]
            
        return job_dict

    @require_connection
    def list_remote_directories(self, path: str) -> List[str]:
        """
        Lists directories in the given remote path.
        Returns a list of directory names.
        Handles SSH connection and command execution.
        """
        if not self.check_connection():
            print("Not connected to SLURM.")
            return []
        try:
            # Use 'ls -F' to list files and directories, then filter for directories only.
            # -F appends / to directories, * to executables, etc.
            # We then filter for lines ending with / and remove the slash.
            command = f"ls -F '{path}'"
            stdout, stderr = self.run_command(command)
            
            if stderr:
                # Handle permission denied or non-existent path gracefully
                if "Permission denied" in stderr or "No such file or directory" in stderr:
                    print(f"Error accessing remote path {path}: {stderr}")
                    return []
                # For other errors, print them but try to proceed if some output exists
                print(f"Warning listing remote directories in {path}: {stderr}")

            directories = []
            # Filter out hidden files and current/parent directory entries from ls output
            # Also ensure we only add directories.
            for line in stdout.split('\n'):
                line = line.strip()
                if line and line.endswith('/') and not line.startswith('.'):
                    directories.append(line.rstrip('/'))
            return sorted(directories, key=str.lower) # Sort alphabetically
        except Exception as e:
            print(f"Failed to list remote directories: {e}")
            return []

    @require_connection
    def remote_path_exists(self, path: str) -> bool:
        """
        Checks if a remote path exists and is a directory.
        """
        if not self.check_connection():
            return False
        try:
            # Use 'test -d' to check if it's a directory
            stdout, stderr = self.run_command(f"test -d '{path}' && echo 'exists' || echo 'not_exists'")
            return stdout.strip() == 'exists'
        except Exception as e:
            print(f"Error checking remote path existence: {e}")
            return False
        
    @require_connection
    def close(self) -> None:
        """Close the SSH connection."""
        if self.client:
            self.client.close()
            self.connected_status = False
            print("SSH connection closed.")


    @require_connection  
    def get_job_details_sacct(self, job_ids: List[Union[str, int]]) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed job information using sacct command
        
        Args:
            job_ids: List of job IDs to query
            
        Returns:
            Dict mapping job_id to job details dictionary
        """
        if not job_ids:
            return {}
            
        job_ids_str = ','.join(str(jid) for jid in job_ids)
        
        cmd = f"sacct -j {job_ids_str} --format=JobID,JobName,State,ExitCode,Start,End,Elapsed,AllocCPUS,ReqMem,MaxRSS,NodeList,Reason --parsable2 --noheader"
        
        try:
            stdout, stderr = self.run_command(cmd)
            
            if stderr:
                print(f"Warning in sacct command: {stderr}")
                
            return self._parse_sacct_output(stdout)
            
        except Exception as e:
            print(f"Error fetching job details with sacct: {e}")
            return {}

    def _parse_sacct_output(self, output: str) -> Dict[str, Dict[str, Any]]:
        """Parse sacct command output into job details dictionary"""
        job_details = {}
        
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
                
            fields = line.split('|')
            if len(fields) < 12:
                continue
                
            job_id = fields[0].split('.')[0]  # Remove array/step suffixes
            
            job_info = {
                'JobID': job_id,
                'JobName': fields[1],
                'State': fields[2],
                'ExitCode': fields[3],
                'Start': fields[4],
                'End': fields[5], 
                'Elapsed': fields[6],
                'AllocCPUS': fields[7],
                'ReqMem': fields[8],
                'MaxRSS': fields[9],
                'NodeList': fields[10],
                'Reason': fields[11]
            }
            
            job_details[job_id] = job_info
            
        return job_details

# Add this to slurm_connection.py

class JobStatusMonitor(QThread):
    """Background thread to monitor job status updates"""
    
    # Signals for different types of updates
    job_status_updated = pyqtSignal(str, str, str)  # project_name, job_id, new_status
    job_details_updated = pyqtSignal(str, str, dict)  # project_name, job_id, job_details
    jobs_batch_updated = pyqtSignal(dict)  # {project_name: [updated_jobs]}
    
    def __init__(self, slurm_connection, project_store, update_interval=30):
        """
        Initialize the job status monitor
        
        Args:
            slurm_connection: SlurmConnection instance
            project_store: ProjectStore instance  
            update_interval: Update interval in seconds (default: 30)
        """
        super().__init__()
        self.slurm_connection = slurm_connection
        self.project_store = project_store
        self.update_interval = update_interval
        self.running = False
        self._stop_requested = False
        
    def run(self):
        """Main thread loop"""
        self.running = True
        self._stop_requested = False
        
        while not self._stop_requested:
            try:
                if self.slurm_connection.check_connection():
                    print("updating jobs status...")
                    self._check_and_update_jobs()
                else:
                    print("SLURM connection lost, attempting to reconnect...")
                    if not self.slurm_connection.connect():
                        print("Failed to reconnect to SLURM")
                        
            except Exception as e:
                print(f"Error in job status monitor: {e}")
                import traceback
                traceback.print_exc()
            
            # Wait for the specified interval, but check for stop request frequently
            for _ in range(self.update_interval * 10):  # Check every 0.1 seconds
                if self._stop_requested:
                    break
                self.msleep(100)  # Sleep for 100ms
                
        self.running = False
        
    def stop(self):
        """Stop the monitoring thread"""
        self._stop_requested = True
        
    def _check_and_update_jobs(self):
        """Check job statuses and update as needed"""
        if not self.project_store:
            return
            
        # Get all active jobs that need monitoring
        active_jobs = self._get_active_jobs()
        
        if not active_jobs:
            return
            
        # Get job details from SLURM using sacct
        job_details = self._fetch_job_details([job['id'] for job in active_jobs])
        
        # Process updates
        updated_projects = {}
        
        for job in active_jobs:
            job_id = str(job['id'])
            project_name = job['project']
            
            if job_id in job_details:
                slurm_job = job_details[job_id]
                old_status = job['status']
                new_status = slurm_job.get('State', old_status)
                
                # Check if status changed
                # if old_status != new_status:
                    # Update in project store
                self.project_store.update_job_status(project_name, job_id, new_status)
                
                # Update other job details
                self._update_job_details(project_name, job_id, slurm_job)
                
                # Track for batch UI update
                if project_name not in updated_projects:
                    updated_projects[project_name] = []
                updated_projects[project_name].append({
                    'job_id': job_id,
                    'old_status': old_status,
                    'new_status': new_status,
                    'details': slurm_job
                })
                
                # Emit individual status update signal
                self.job_status_updated.emit(project_name, job_id, new_status)
                
                # print(f"Job {job_id} status updated: {old_status} -> {new_status}")
        
        # Emit batch update signal if there were changes
        if updated_projects:
            self.jobs_batch_updated.emit(updated_projects)
            
    def _get_active_jobs(self):
        """Get all jobs that need status monitoring"""
        active_jobs = []
        active_statuses = {'PENDING', 'RUNNING', 'COMPLETING', 'SUSPENDED', 'PREEMPTED'}
        
        for project_name in self.project_store.all_projects():
            project = self.project_store.get(project_name)
            if not project:
                continue
                
            for job in project.jobs:
                if job.status in active_statuses and job.status != 'NOT_SUBMITTED':
                    active_jobs.append({
                        'id': job.id,
                        'project': project_name,
                        'status': job.status
                    })
                    
        return active_jobs
        
    def _fetch_job_details(self, job_ids):
        """Fetch job details using sacct command"""
        if not job_ids:
            return {}
            
        # Create comma-separated list of job IDs
        job_ids_str = ','.join(str(jid) for jid in job_ids)
        
        # Use sacct to get detailed job information
        cmd = f"sacct -j {job_ids_str} --format=JobID,JobName,State,ExitCode,Start,End,Elapsed,AllocCPUS,ReqMem,MaxRSS,NodeList,Reason --parsable2 --noheader"
        
        try:
            stdout, stderr = self.slurm_connection.run_command(cmd)
            
            if stderr:
                print(f"Warning in sacct command: {stderr}")
                
            return self._parse_sacct_output(stdout)
            
        except Exception as e:
            print(f"Error fetching job details with sacct: {e}")
            return {}
            
    def _parse_sacct_output(self, output):
        """Parse sacct command output"""
        job_details = {}
        
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
                
            fields = line.split('|')
            if len(fields) < 12:
                continue
                
            job_id = fields[0].split('.')[0]  # Remove array/step suffixes
            
            job_info = {
                'JobID': job_id,
                'JobName': fields[1],
                'State': fields[2],
                'ExitCode': fields[3],
                'Start': fields[4],
                'End': fields[5], 
                'Elapsed': fields[6],
                'AllocCPUS': fields[7],
                'ReqMem': fields[8],
                'MaxRSS': fields[9],
                'NodeList': fields[10],
                'Reason': fields[11]
            }
            
            job_details[job_id] = job_info
            
        return job_details
        
    def _update_job_details(self, project_name, job_id, slurm_job):
        """Update additional job details from SLURM data"""
        job = self.project_store.get_job(project_name, job_id)
        if not job:
            return
            
        # Update timing information
        if slurm_job.get('Start') and slurm_job['Start'] != 'Unknown':
            try:
                job.start_time = datetime.strptime(slurm_job['Start'], '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                pass
                
        if slurm_job.get('End') and slurm_job['End'] != 'Unknown':
            try:
                job.end_time = datetime.strptime(slurm_job['End'], '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                pass
                
        # Update elapsed time
        if slurm_job.get('Elapsed'):
            try:
                job.time_used = parse_duration(slurm_job['Elapsed'])
            except ValueError:
                pass
                
        # Update node information
        if slurm_job.get('NodeList'):
            job.nodelist = slurm_job['NodeList']
            
        # Update reason
        if slurm_job.get('Reason'):
            job.reason = slurm_job['Reason']
            
        # Update resource usage
        if slurm_job.get('AllocCPUS'):
            try:
                job.cpus = int(slurm_job['AllocCPUS'])
            except ValueError:
                pass
                
        # Store additional info
        job.info.update({
            'exit_code': slurm_job.get('ExitCode'),
            'max_rss': slurm_job.get('MaxRSS'),
            'last_updated': datetime.now().isoformat()
        })


# Add these methods to the SlurmConnection class

if __name__ == "__main__":
    sc = SlurmConnection("/home/nicola/Desktop/slurm_gui/configs/settings.ini")
    sc.connect()
    app = QApplication(sys.argv)
    

    window = NewJobDialog("Debug", slurm_connection=sc)
    window.show()
    app.exec()
    print(window.get_job_details())
    sys.exit()