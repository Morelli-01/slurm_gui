import configparser
import platform
import re
import sys
import functools
import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
from modules.data_classes import Job
from modules.new_job_dp import NewJobDialog
import paramiko
from PyQt6.QtCore import QObject, QSettings
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
from utils import settings_path, script_dir, determine_job_status, parse_duration
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
    "CA": "CANCELLED",
    "TO": "TIMEOUT",
    "NF": "NODE_FAIL",
    "RV": "REVOKED",
    "SE": "SPECIAL_EXIT",
    "OOM": "OUT_OF_MEMORY",
    "BF": "BOOT_FAIL",
    "DL": "DEADLINE",
    "OT": "OTHER"
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
                if not result:
                    # Emit empty data if connection failed
                    self.data_ready.emit([], [])
                    return

            nodes_data = self.slurm_connection._fetch_nodes_infos()
            queue_jobs = self.slurm_connection._fetch_squeue()
            self.data_ready.emit(nodes_data, queue_jobs)
        except Exception as e:
            print(f"Worker error: {e}")
            self.connected.emit(False)
            self.data_ready.emit([], [])  # Emit empty data on error


def require_connection(func):
    """Decorator to ensure SSH connection is established before executing a method."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.check_connection():
            raise ConnectionError(
                "SSH connection not established. Please connect first.")
        return func(self, *args, **kwargs)
    return wrapper



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
            self.client.connect(
                self.host, username=self.user, password=self.password)
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
        filtered_jobs = [
            job for job in all_jobs if job["User"] == self.remote_user]
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
            constraints_out, _ = self.run_command(
                "sinfo -o '%f' | sort | uniq")
            self.constraints = sorted(set(constraints_out.split()))

            # Fetch QoS options
            qos_out, _ = self.run_command(
                "sacctmgr show qos format=Name -n -P")
            self.qos_list = sorted(set(qos_out.splitlines()))

            # Fetch user accounts
            if self.remote_user:
                acc_out, _ = self.run_command(
                    f"sacctmgr show associations user={self.remote_user} format=Account -n -P")
                self.accounts = sorted(set(acc_out.splitlines()))
            else:
                print("[WARNING] remote_user is not set, cannot fetch accounts.")

            # Fetch GRES (Generic Resources)
            gres_out, _ = self.run_command("scontrol show gres")
            self.gres = [line.strip()
                         for line in gres_out.splitlines() if "Name=" in line]

        except Exception as e:
            print(f"Failed to fetch submission options: {e}")

    def _normalize_path(self, path: str) -> str:
        """
        Normalize a file path - if it's absolute, return as-is; if relative, prepend home directory.
        
        Args:
            path: File path (can be absolute or relative)
            
        Returns:
            str: Normalized absolute path
        """
        if not path:
            return ""
            
        # Check if path is absolute (starts with /)
        if path.startswith('/'):
            return path
        else:
            # Relative path - prepend home directory
            return f"{self.remote_home}/{path}"

    def _get_discord_webhook_url(self) -> Optional[str]:
        """Get Discord webhook URL from settings"""
        try:

            settings = QSettings(str(Path(settings_path)), QSettings.Format.IniFormat)
            settings.beginGroup("NotificationSettings")
            
            enabled = settings.value("discord_enabled", False, type=bool)
            webhook_url = settings.value("discord_webhook_url", "", type=str)
            
            settings.endGroup()
            
            if enabled and webhook_url:
                return webhook_url
            return None
        except Exception as e:
            print(f"Error getting Discord webhook URL: {e}")
            return None

    @require_connection
    def get_job_logs(self, job: 'Job', preserve_progress_bars: bool = False) -> Tuple[str, str]:
        """
        Get the output and error logs for a job with proper handling of progress bars.
        Enhanced to handle both relative and absolute log file paths.
        
        Args:
            job: Job object
            preserve_progress_bars: If True, keeps final progress bar state; if False, removes all progress bar lines
        Returns:
            Tuple[str, str]: (stdout, stderr) logs with proper formatting
        """
        
        def clean_progress_output(text: str, preserve_final_state: bool = False) -> str:
            """
            Clean text containing progress bars and ANSI sequences.
            Handles tqdm output by extracting the final state of each progress bar.
            """
            import re
            
            # Remove ANSI escape sequences but preserve structure
            ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
            clean_text = ansi_escape.sub('', text)
            
            if not preserve_final_state:
                # Just remove ANSI and carriage returns, convert to newlines
                return clean_text.replace('\r', '\n')
            
            # Split by newlines first to handle each logical line
            lines = clean_text.split('\n')
            cleaned_lines = []
            
            for line in lines:
                if '\r' in line:
                    # This line has carriage returns (likely progress bar updates)
                    # Split by \r and take the last non-empty part
                    parts = line.split('\r')
                    final_part = ''
                    
                    # Find the last non-empty, meaningful part
                    for part in reversed(parts):
                        if part.strip():
                            final_part = part.strip()
                            break
                    
                    # Only add if we found something meaningful
                    if final_part:
                        cleaned_lines.append(final_part)
                else:
                    # Regular line without carriage returns
                    if line.strip():  # Only add non-empty lines
                        cleaned_lines.append(line)
            
            return '\n'.join(cleaned_lines)

        if not self.is_connected():
            raise ConnectionError("SSH connection not established.")
        
        # Try multiple possible log file locations
        possible_stdout_files = [
            f"{self.remote_home}/.logs/out_{job.id}.log",  # Default relative path
            f"/tmp/out_{job.id}.log",  # Common temp location
            f"out_{job.id}.log",  # Current directory
        ]
        
        possible_stderr_files = [
            f"{self.remote_home}/.logs/err_{job.id}.log",  # Default relative path
            f"/tmp/err_{job.id}.log",  # Common temp location
            f"err_{job.id}.log",  # Current directory
        ]
        
        # Also check if job has custom output/error paths by querying SLURM
        try:
            # Get job details to find actual output/error file paths
            job_details_cmd = f"scontrol show job {job.id}"
            job_details_output, _ = self.run_command(job_details_cmd)
            
            # Parse output to find StdOut and StdErr paths
            for line in job_details_output.split('\n'):
                if 'StdOut=' in line:
                    stdout_match = re.search(r'StdOut=([^\s]+)', line)
                    if stdout_match:
                        custom_stdout = stdout_match.group(1)
                        if custom_stdout not in possible_stdout_files:
                            possible_stdout_files.insert(0, custom_stdout)  # Try custom path first
                            
                if 'StdErr=' in line:
                    stderr_match = re.search(r'StdErr=([^\s]+)', line)
                    if stderr_match:
                        custom_stderr = stderr_match.group(1)
                        if custom_stderr not in possible_stderr_files:
                            possible_stderr_files.insert(0, custom_stderr)  # Try custom path first
        except Exception as e:
            print(f"Warning: Could not query job details for {job.id}: {e}")
        
        stdout, stderr = "", ""

        try:
            sftp = self.client.open_sftp()
            
            # Try to find stdout file
            stdout_found = False
            for stdout_file in possible_stdout_files:
                try:
                    with sftp.open(stdout_file, 'rb') as f:
                        out_bytes = f.read()
                    out = out_bytes.decode(errors='replace')
                    stdout = clean_progress_output(out, preserve_progress_bars)
                    stdout_found = True
                    break
                except Exception:
                    continue
            
            if not stdout_found:
                stdout = f"[!] Output log for job {job.id} not found. Searched locations:\n" + \
                        "\n".join(f"  - {path}" for path in possible_stdout_files)
            
            # Try to find stderr file
            stderr_found = False
            for stderr_file in possible_stderr_files:
                try:
                    with sftp.open(stderr_file, 'rb') as f:
                        err_bytes = f.read()
                    err = err_bytes.decode(errors='replace')
                    stderr = clean_progress_output(err, preserve_progress_bars)
                    stderr_found = True
                    break
                except Exception:
                    continue
            
            if not stderr_found:
                stderr = f"[!] Error log for job {job.id} not found. Searched locations:\n" + \
                        "\n".join(f"  - {path}" for path in possible_stderr_files)
            
            sftp.close()
        except Exception as e:
            print(f"Error fetching logs for job {job.id}: {e}")
            stdout = f"[!] Error accessing log files for job {job.id}: {e}"
            stderr = f"[!] Error accessing log files for job {job.id}: {e}"
        
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
                    # Check if node is reserved
                    if key == "State":
                        node_dict["RESERVED"] = "YES" if "RESERVED" in value.upper() else "NO"

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
        Parse job fields from squeue output with better status handling.
        """
        raw_status_code = fields[9]
        status = JOB_CODES.get(raw_status_code, "UNKNOWN")

        job_dict = {
            "Job ID": fields[0],
            "Reason": fields[1],
            "Nodelist": fields[2],
            "User": fields[3],
            "Job Name": fields[7],
            "Partition": fields[8],
            "Status": status,
            "RawStatusCode": raw_status_code,  # Keep original for debugging
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
            command = f"ls -aF '{path}'"
            stdout, stderr = self.run_command(command)

            if stderr:
                # Handle permission denied or non-existent path gracefully
                if "Permission denied" in stderr or "No such file or directory" in stderr:
                    print(f"Error accessing remote path {path}: {stderr}")
                    return []
                # For other errors, print them but try to proceed if some output exists
                print(
                    f"Warning listing remote directories in {path}: {stderr}")

            directories = []
            # Include all directories, including hidden ones (but still exclude . and ..)
            for line in stdout.split('\n'):
                line = line.strip()
                if line and line.endswith('/') and line not in ('./', '../'):
                    directories.append(line.rstrip('/'))
            return sorted(directories, key=str.lower)  # Sort alphabetically
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
            stdout, stderr = self.run_command(
                f"test -d '{path}' || test -e '{path}' && echo 'exists' || echo 'not_exists'")
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
            raw_state = fields[2]
            exit_code = fields[3]

            # Determine refined job status
            refined_status = determine_job_status(raw_state, exit_code)

            job_info = {
                'JobID': job_id,
                'JobName': fields[1],
                'State': refined_status,  # Use refined status
                'RawState': raw_state,    # Keep original state for reference
                'ExitCode': exit_code,
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

    def _create_job_script(self, job_name: str, partition: str, time_limit: str, command: str, account: str,
                        constraint: Optional[str], qos: Optional[str], gres: Optional[str],
                        nodes: int, ntasks: int, output_file: str, error_file: str, memory: str, cpus: int,
                        discord_settings: Optional[Dict[str, Any]] = None,
                        array_spec: Optional[str] = None, array_max_jobs: Optional[int] = None) -> str:
        """
        Create the content of a SLURM job script with enhanced Discord notifications.
        """
        
        # Always use %a in output/error file for arrays
        if array_spec:
            if "%a" not in output_file:
                output_file = output_file.replace("%A", "%A_%a") if "%A" in output_file else output_file.replace(".log", "_%a.log")
            if "%a" not in error_file:
                error_file = error_file.replace("%A", "%A_%a") if "%A" in error_file else error_file.replace(".log", "_%a.log")

        normalized_output = self._normalize_path(output_file)
        normalized_error = self._normalize_path(error_file)

        script_lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name=\"{job_name}\"",
            f"#SBATCH --partition={partition.replace('*', '')}",
            f"#SBATCH --time={time_limit}",
            f"#SBATCH --nodes={nodes}",
            f"#SBATCH --ntasks={ntasks}",
            f"#SBATCH --output={normalized_output}",
            f"#SBATCH --error={normalized_error}",
            f"#SBATCH --mem={memory}",
            f"#SBATCH --cpus-per-task={cpus}",
        ]

        # Add job array directive if specified
        if array_spec:
            array_line = f"#SBATCH --array={array_spec}"
            if array_max_jobs:
                array_line += f"%{array_max_jobs}"
            script_lines.append(array_line)

        # Add optional parameters
        if "None" not in str(constraint):
            script_lines.append(f"#SBATCH --constraint={constraint}")
        if qos:
            script_lines.append(f"#SBATCH --qos={qos}")
        if account:
            script_lines.append(f"#SBATCH --account={account}")
        if gres:
            script_lines.append(f"#SBATCH --gres={gres}")

        # Add enhanced Discord webhook setup if enabled
        if discord_settings and discord_settings.get("enabled", False):
            webhook_url = self._get_discord_webhook_url()
            if webhook_url:
                script_lines.extend([
                    "",
                    "# =============================================================================",
                    "# Enhanced Discord Notification System for SLURM Jobs",
                    "# =============================================================================",
                    "",
                    f'export JOB_NAME="{job_name}"',
                    f'export PARTITION="{partition}"',
                    f'export TIME_LIMIT="{time_limit}"',
                    f'export REQUESTED_MEMORY="{memory}"',
                    f'export REQUESTED_CPUS="{cpus}"',
                    f'export REQUESTED_NODES="{nodes}"',
                    f'DISCORD_WEBHOOK_URL="{webhook_url}"',
                    "",
                    "# Get system info for richer notifications",
                    "export START_TIME=$(date '+%Y-%m-%d %H:%M:%S')",
                    "export HOSTNAME=$(hostname)",
                    "",
                    "# Enhanced Discord notification functions",
                    "function send_enhanced_discord_notification {",
                    "    local title=\"$1\"",
                    "    local description=\"$2\"",
                    "    local color=\"$3\"",
                    "    local thumbnail_url=\"$4\"",
                    "    local footer_text=\"$5\"",
                    "    ",
                    "    # Get current timestamp in ISO format",
                    "    local timestamp=$(date -u +\"%Y-%m-%dT%H:%M:%S.000Z\")",
                    "    ",
                    "    # Export parameters as environment variables for Python script",
                    "    export DISCORD_TITLE=\"$title\"",
                    "    export DISCORD_DESCRIPTION=\"$description\"",
                    "    export DISCORD_COLOR=\"$color\"",
                    "    export DISCORD_THUMBNAIL=\"$thumbnail_url\"",
                    "    export DISCORD_FOOTER=\"$footer_text\"",
                    "    export DISCORD_TIMESTAMP=\"$timestamp\"",
                    "    ",
                    "    # Build the enhanced embed payload",
                    "    local embed_payload=$(python3 <<'EOF'",
                    "import json, os",
                    "",
                    "# Get parameters from environment variables",
                    "title = os.environ.get(\"DISCORD_TITLE\", \"SLURM Job Update\")",
                    "description = os.environ.get(\"DISCORD_DESCRIPTION\", \"\")",
                    "color = int(os.environ.get(\"DISCORD_COLOR\", \"3447003\"))",
                    "thumbnail_url = os.environ.get(\"DISCORD_THUMBNAIL\", \"\")",
                    "footer_text = os.environ.get(\"DISCORD_FOOTER\", \"SlurmAIO Job Monitor\")",
                    "timestamp = os.environ.get(\"DISCORD_TIMESTAMP\", \"\")",
                    "",
                    "# Get environment variables",
                    "job_id = os.environ.get(\"SLURM_JOB_ID\", \"Unknown\")",
                    "job_name = os.environ.get(\"JOB_NAME\", \"Unknown\")",
                    "node = os.environ.get(\"SLURM_NODELIST\", \"Unknown\")",
                    "partition = os.environ.get(\"PARTITION\", \"Unknown\")",
                    "time_limit = os.environ.get(\"TIME_LIMIT\", \"Unknown\")",
                    "memory = os.environ.get(\"REQUESTED_MEMORY\", \"Unknown\")",
                    "cpus = os.environ.get(\"REQUESTED_CPUS\", \"Unknown\")",
                    "nodes = os.environ.get(\"REQUESTED_NODES\", \"Unknown\")",
                    "hostname = os.environ.get(\"HOSTNAME\", \"Unknown\")",
                    "start_time = os.environ.get(\"START_TIME\", \"Unknown\")",
                    "account = os.environ.get(\"SLURM_JOB_ACCOUNT\", \"Unknown\")",
                    "",
                    "# Build rich embed with base64 icon fallback",
                    "embed = {",
                    "    \"username\": \"SlurmAIO\",",
                    "    \"embeds\": [{",
                    "        \"title\": title,",
                    "        \"description\": description,",
                    "        \"color\": color,",
                    "        \"timestamp\": timestamp,",
                    "        \"fields\": [",
                    "            {",
                    "                \"name\": \"🎯 Job Details\",",
                    "                \"value\": f\"**ID:** `{job_id}`\\n**Name:** `{job_name}`\\n**Partition:** `{partition}`\",",
                    "                \"inline\": True",
                    "            },",
                    "            {",
                    "                \"name\": \"💻 Resources\",",
                    "                \"value\": f\"**CPUs:** {cpus}\\n**Memory:** {memory}\\n**Nodes:** {nodes}\",",
                    "                \"inline\": True",
                    "            },",
                    "            {",
                    "                \"name\": \"📍 Location\",",
                    "                \"value\": f\"**Cluster:** `{hostname}`\\n**Node(s):** `{node}`\\n**Account:** `{account}`\",",
                    "                \"inline\": True",
                    "            },",
                    "            {",
                    "                \"name\": \"⏱️ Timing\",",
                    "                \"value\": f\"**Time Limit:** {time_limit}\\n**Started:** {start_time}\",",
                    "                \"inline\": False",
                    "            }",
                    "        ],",
                    "        \"footer\": {",
                    "            \"text\": footer_text + \" • SlurmAIO\",",
                    "            \"icon_url\": \"https://cdn-icons-png.flaticon.com/512/2103/2103633.png\"",
                    "        },",
                    "        \"author\": {",
                    "            \"name\": \"SlurmAIO\",",
                    "            \"icon_url\": \"https://cdn-icons-png.flaticon.com/512/9131/9131529.png\"",
                    "        }",
                    "    }]",
                    "}",
                    "",
                    "# Add thumbnail if provided",
                    "if thumbnail_url:",
                    "    embed[\"embeds\"][0][\"thumbnail\"] = {\"url\": thumbnail_url}",
                    "",
                    "print(json.dumps(embed))",
                    "EOF",
                    "    )",
                    "    ",
                    "    # Send the notification with error checking",
                    "    local curl_response=$(curl -H \"Content-Type: application/json\" \\",
                    "         -X POST \\",
                    "         -d \"$embed_payload\" \\",
                    "         \"$DISCORD_WEBHOOK_URL\" \\",
                    "         -w \"%{http_code}\" \\",
                    "         --silent --show-error 2>&1)",
                    "    ",
                    "    if [[ \"$curl_response\" == *\"204\"* ]]; then",
                    "    else",
                    "    fi",
                    "}",
                    "",
                    "# Job start notification function",
                    "function send_job_start_notification {",
                    "    export DISCORD_TIMESTAMP=$(date -u +\"%Y-%m-%dT%H:%M:%S.000Z\")",
                    "    ",
                    "    local description=\"🚀 **Job Started Successfully!**\n\n\"",
                    "    ",
                    "    send_enhanced_discord_notification \\",
                    "        \"🏃‍♂️ JOB STARTED: $JOB_NAME\" \\",
                    "        \"$description\" \\",
                    "        \"3447003\" \\",
                    "        \"https://cdn-icons-png.flaticon.com/512/2103/2103591.png\" \\",
                    "        \"Started at $(date '+%H:%M:%S')\"",
                    "    ",
                    "}",
                    "",
                    "# Job completion notification function",
                    "function send_job_completion_notification {",
                    "    local exit_code=$1",
                    "    local end_time=$(date '+%Y-%m-%d %H:%M:%S')",
                    "    local duration=$((SECONDS))",
                    "    local duration_formatted=$(printf '%02d:%02d:%02d' $((duration/3600)) $(((duration%3600)/60)) $((duration%60)))",
                    "    ",
                    "    export DISCORD_TIMESTAMP=$(date -u +\"%Y-%m-%dT%H:%M:%S.000Z\")",
                    "    ",
                    "    if [ $exit_code -eq 0 ]; then",
                    "        # Success notification",
                    "        local description=\"✅ **Job Completed Successfully!**\n\n\"",
                    "        description+=\"🎉 Your SLURM job **$JOB_NAME** has finished execution without errors!\n\n\"",
                    "        description+=\"📊 **Final Status:** Completed Successfully\n\"",
                    "        description+=\"⏱️ **Total Runtime:** $duration_formatted\n\"",
                    "        description+=\"🏁 **Finished At:** $end_time\n\n\"",
                    "        description+=\"💡 **Next Step:** Check output logs for detailed results\"",
                    "        ",
                    "        send_enhanced_discord_notification \\",
                    "            \"✅ JOB COMPLETED: $JOB_NAME\" \\",
                    "            \"$description\" \\",
                    "            \"5763719\" \\",
                    "            \"https://cdn-icons-png.flaticon.com/512/190/190411.png\" \\",
                    "            \"SUCCESS: Completed in $duration_formatted\"",
                    "        ",
                    "    else",
                    "        # Failure notification",
                    "        local description=\"❌ **Job Failed!**\n\n\"",
                    "        description+=\"💥 Your SLURM job **$JOB_NAME** encountered an error during execution.\n\n\"",
                    "        description+=\"📊 **Final Status:** Failed\n\"",
                    "        description+=\"🚨 **Exit Code:** $exit_code\n\"",
                    "        description+=\"⏱️ **Runtime Before Failure:** $duration_formatted\n\"",
                    "        description+=\"💔 **Failed At:** $end_time\n\n\"",
                    "        description+=\"🔍 **Next Step:** Check error logs for troubleshooting\"",
                    "        ",
                    "        send_enhanced_discord_notification \\",
                    "            \"❌ JOB FAILED: $JOB_NAME\" \\",
                    "            \"$description\" \\",
                    "            \"15158332\" \\",
                    "            \"https://cdn-icons-png.flaticon.com/512/564/564619.png\" \\",
                    "            \"FAILED: Exit code $exit_code after $duration_formatted\"",
                    "        ",
                    "    fi",
                    "}",
                    "",
                    "# Job cancellation notification function",
                    "function send_job_cancelled_notification {",
                    "    local cancel_time=$(date '+%Y-%m-%d %H:%M:%S')",
                    "    local duration=$((SECONDS))",
                    "    local duration_formatted=$(printf '%02d:%02d:%02d' $((duration/3600)) $(((duration%3600)/60)) $((duration%60)))",
                    "    ",
                    "    export DISCORD_TIMESTAMP=$(date -u +\"%Y-%m-%dT%H:%M:%S.000Z\")",
                    "    ",
                    "    local description=\"🛑 **Job Cancelled**\\n\\n\"",
                    "    description+=\"⚠️ Your SLURM job **$JOB_NAME** was cancelled before completion.\\n\\n\"",
                    "    description+=\"📊 **Final Status:** Cancelled\\n\"",
                    "    description+=\"⏱️ **Runtime Before Cancellation:** $duration_formatted\\n\"",
                    "    description+=\"🛑 **Cancelled At:** $cancel_time\\n\\n\"",
                    "    description+=\"🤔 **Possible Reasons:** Time limits, resource constraints, or manual cancellation\"",
                    "    ",
                    "    send_enhanced_discord_notification \\",
                    "        \"🛑 JOB CANCELLED: $JOB_NAME\" \\",
                    "        \"$description\" \\",
                    "        \"16776960\" \\",
                    "        \"https://cdn-icons-png.flaticon.com/512/1828/1828843.png\" \\",
                    "        \"CANCELLED: After $duration_formatted\"",
                    "    ",
                    "}",
                    "",
                    "# Set up signal handlers for job cancellation",
                    "trap 'send_job_cancelled_notification; exit 130' INT TERM",
                    "",
                ])
                
                # Add notification settings based on user preferences
                notify_start = discord_settings.get("notify_start", True)
                notify_complete = discord_settings.get("notify_complete", True)

        script_lines.extend([
            "# =============================================================================",
            "# Job Execution",
            "# =============================================================================",
            "",
            "# Record start time for duration calculation",
            "SECONDS=0",
            "",
            "echo \"Starting job execution at $(date)\"",
            "echo \"Job ID: $SLURM_JOB_ID\"",
            "echo \"Job Name: $JOB_NAME\"",
            "echo \"Node(s): $SLURM_NODELIST\"",
            "echo \"Partition: $PARTITION\"",
            "echo \"\"",
            "",
        ])
        
        # Add job start notification if Discord is enabled and user wants it
        if discord_settings and discord_settings.get("enabled", False) and webhook_url:
            notify_start = discord_settings.get("notify_start", True)
            if notify_start:
                script_lines.extend([
                    "# Send job start notification",
                    "send_job_start_notification",
                    "",
                ])

        script_lines.extend([
            "# Your job command starts here",
            "echo \"Executing job command...\"",
            command,
            "",
            "# Capture the exit code immediately after job execution",
            "JOB_EXIT_CODE=$?",
            "",
            "echo \"\"",
            "echo \"Job finished at $(date)\"",
            "echo \"Exit code: $JOB_EXIT_CODE\"",
        ])
        
        # Add job completion notification if Discord is enabled
        if discord_settings and discord_settings.get("enabled", False) and webhook_url:
            notify_complete = discord_settings.get("notify_complete", True)
            if notify_complete:
                script_lines.extend([
                    "",
                    "# Send completion notification based on exit code",
                    "if [ $JOB_EXIT_CODE -eq 0 ]; then",
                    "    echo \"Job completed successfully, sending success notification...\"",
                    "else",
                    "    echo \"Job failed with exit code $JOB_EXIT_CODE, sending failure notification...\"",
                    "fi",
                    "send_job_completion_notification $JOB_EXIT_CODE",
                    "",
                ])

        script_lines.extend([
            "# Exit with the original job exit code",
            "exit $JOB_EXIT_CODE"
        ])

        script_content = "\n".join(script_lines)
        
        # Ensure Unix line endings for cross-platform compatibility
        if platform.system().lower() == "windows":
            script_content = script_content.replace('\r\n', '\n').replace('\r', '\n')
        
        return script_content

    def submit_job_from_object(self, job: 'Job', discord_settings: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Submit a job using the enhanced Job object.
        
        Args:
            job: Enhanced Job object with all parameters
            discord_settings: Optional Discord notification settings
            
        Returns:
            str: Job ID if submission successful, None otherwise
        """
        if not self.check_connection():
            raise ConnectionError("SSH connection not established.")
        
        try:
            # Validate job parameters
            validation_issues = job.validate_parameters()
            if validation_issues:
                raise ValueError(f"Job validation failed: {'; '.join(validation_issues)}")
            
            # Save script to temporary file
            script_path = job.save_sbatch_script(
                include_discord=bool(discord_settings and discord_settings.get("enabled", False)),
                discord_settings=discord_settings
            )
            
            try:
                # Upload and submit the script
                remote_script_path = f"/tmp/{os.path.basename(script_path)}"
                
                # Upload via SFTP
                sftp = self.client.open_sftp()
                sftp.put(script_path, remote_script_path)
                sftp.close()
                
                # Submit via sbatch
                stdout, stderr = self.run_command(f"sbatch {remote_script_path}")
                
                if stderr and "INFO" not in stderr:
                    raise RuntimeError(f"SLURM error: {stderr}")
                
                # Parse job ID
                job_id = None
                if "Submitted batch job" in stdout:
                    job_id = stdout.strip().split()[-1]
                    
                    # Update the job object with the new ID and submission info
                    job.id = job_id
                    job.status = "PENDING"
                    job.submission_time = datetime.now()
                
                return job_id
                
            finally:
                # Clean up local script file
                try:
                    os.unlink(script_path)
                except:
                    pass
                    
        except Exception as e:
            raise RuntimeError(f"Job submission failed: {e}")

    # Update the existing submit_job method to use the new Job-based approach
    def submit_job(self, job_name: str, partition: str, time_limit: str, command: str, account: str,
                constraint: Optional[str] = None, qos: Optional[str] = None,
                gres: Optional[str] = None, nodes: int = 1, ntasks: int = 1,
                output_file: str = ".logs/out_%A.log", error_file: str = ".logs/err_%A.log", 
                memory: str = "1G", cpus: int = 1, discord_settings: Optional[Dict[str, Any]] = None,
                array_spec: Optional[str] = None, array_max_jobs: Optional[int] = None,
                **additional_params) -> Optional[str]:
        """
        Submit a job to the SLURM scheduler using the enhanced Job class.
        
        This method now creates a Job object internally and uses the new submission system.
        Maintains backward compatibility with existing code.
        """
        
        # Create job details dictionary
        job_details = {
            'job_name': job_name,
            'partition': partition,
            'time_limit': time_limit,
            'command': command,
            'account': account,
            'constraint': constraint,
            'qos': qos,
            'gres': gres,
            'nodes': nodes,
            'ntasks': ntasks,
            'output_file': output_file,
            'error_file': error_file,
            'memory': memory,
            'cpus_per_task': cpus,
            'array': array_spec,
            'array_max_jobs': array_max_jobs,
            **additional_params  # Include any additional parameters
        }
        
        # Create Job object
        job = Job.create_job_from_details(job_details)
        
        # Submit using the new method
        return self.submit_job_from_object(job, discord_settings)

    def preview_job_script(self, job_details: Dict[str, Any], 
                        include_discord: bool = False,
                        discord_settings: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a preview of the sbatch script without submitting.
        
        Args:
            job_details: Dictionary containing job parameters
            include_discord: Whether to include Discord notifications
            discord_settings: Discord notification settings
            
        Returns:
            str: Generated sbatch script content
        """
        job = Job.create_job_from_details(job_details)
        return job.generate_sbatch_script(
            include_discord=include_discord,
            discord_settings=discord_settings
        )

    
class JobStatusMonitor(QThread):
    """Background thread to monitor job status updates"""

    # Signals for different types of updates
    # project_name, job_id, new_status
    job_status_updated = pyqtSignal(str, str, str)
    # project_name, job_id, job_details
    job_details_updated = pyqtSignal(str, str, dict)
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
        """Check job statuses and update as needed with proper status determination"""
        if not self.project_store:
            return

        # Get all active jobs that need monitoring
        active_jobs = self._get_active_jobs()

        if not active_jobs:
            return

        # Get job details from SLURM using sacct with exit codes
        job_details = self._fetch_job_details(
            [job['id'] for job in active_jobs])

        # Process updates
        updated_projects = {}

        for job in active_jobs:
            job_id = str(job['id'])
            project_name = job['project']

            if job_id in job_details:
                slurm_job = job_details[job_id]
                old_status = job['status']

                # Use the refined status from sacct parsing
                new_status = slurm_job.get('State', old_status)

                # Check if status changed
                if old_status != new_status:
                    print(
                        f"Job {job_id} status changed: {old_status} -> {new_status} (exit code: {slurm_job.get('ExitCode', 'N/A')})")

                    # Update in project store
                    self.project_store.update_job_status(
                        project_name, job_id, new_status)

                    # Emit individual status update signal
                    self.job_status_updated.emit(
                        project_name, job_id, new_status)

                # Update other job details regardless of status change
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
                if new_status in ['RUNNING', 'COMPLETING']:
                    self.job_details_updated.emit(project_name, job_id, slurm_job)
            else:
            # Job not found in SLURM data - set status to COMPLETED
                if job['status'] in ['RUNNING', 'PENDING', 'COMPLETING']:
                    print(f"Job {job_id} not found in squeue, setting status to COMPLETED")
                    
                    # Update in project store
                    self.project_store.update_job_status(project_name, job_id, 'COMPLETED')
                    
                    # Emit status update signal
                    self.job_status_updated.emit(project_name, job_id, 'COMPLETED')
                    
                    # Track for batch UI update
                    if project_name not in updated_projects:
                        updated_projects[project_name] = []
                    updated_projects[project_name].append({
                        'job_id': job_id,
                        'old_status': job['status'],
                        'new_status': 'COMPLETED',
                        'details': {}
                    })
        # Emit batch update signal if there were changes
        if updated_projects:
            self.jobs_batch_updated.emit(updated_projects)

    def _get_active_jobs(self):
        """Get all jobs that need status monitoring"""
        active_jobs = []
        active_statuses = {'PENDING', 'RUNNING',
                           'COMPLETING', 'SUSPENDED', 'PREEMPTED'}

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
        """Fetch job details using sacct command with exit codes"""
        
        if not job_ids:
            return {}

        # Create comma-separated list of job IDs
        job_ids_str = ','.join(str(jid) for jid in job_ids)

        # Enhanced sacct command that includes exit codes and more details
        cmd = f"sacct -j {job_ids_str} --format=JobID,JobName,State,ExitCode,Start,End,Elapsed,AllocCPUS,ReqMem,MaxRSS,NodeList,Reason,DerivedExitCode --parsable2 --noheader"

        try:
            stdout, stderr = self.slurm_connection.run_command(cmd)

            if stderr:
                raise Exception(f"{stderr}")

            return self._parse_sacct_output(stdout)

        except Exception as e:
            print(f"Error fetching job details with sacct: {e}")
            print("proceeding with squeue")
            return self._fetch_job_details_backup(job_ids)
    
    def _parse_sacct_output(self, output):
        """Parse sacct command output"""
        job_details = {}
        
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
            if ".batch" in line or ".extern" in line: continue
            fields = line.split('|')
            if len(fields) < 12:
                continue

            job_id = fields[0].split('.')[0]  # Remove array/step suffixes

            job_info = {
                'JobID': job_id,
                'JobName': fields[1],
                'State': fields[2].split(" ")[0],
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

    def _fetch_job_details_backup(self, job_ids):
        """
        Backup method to fetch job details using squeue command when sacct fails.
        Returns job details in the same format as _fetch_job_details for compatibility.
        """
        if not job_ids:
            return {}

        # Create comma-separated list of job IDs
        job_ids_str = ','.join(str(jid) for jid in job_ids)

        # Use squeue command as backup - format similar to _fetch_squeue but with specific job IDs
        cmd = f"squeue -j {job_ids_str} -o '%i|%j|%T|%M|%N|%u|%a|%r' --noheader"

        try:
            stdout, stderr = self.slurm_connection.run_command(cmd)

            if stderr:
                print(f"Warning in backup squeue command: {stderr}")

            return self._parse_squeue_backup_output(stdout)

        except Exception as e:
            print(f"Error in backup job details fetch with squeue: {e}")
            return {}
    
    def _parse_squeue_backup_output(self, output):
        """
        Parse squeue backup output and convert to format compatible with sacct output.
        Maps squeue fields to sacct-like structure for consistency.
        """
        job_details = {}
        
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
                
            fields = line.split('|')
            if len(fields) < 8:
                continue

            job_id = fields[0].split('.')[0]  # Remove array/step suffixes
            
            # Map squeue status codes to full status names
            status_code = fields[2]
            status_map = {
                'R': 'RUNNING',
                'PD': 'PENDING', 
                'CG': 'COMPLETING',
                'CD': 'COMPLETED',
                'CA': 'CANCELLED',
                'F': 'FAILED',
                'TO': 'TIMEOUT',
                'S': 'SUSPENDED'
            }
            
            mapped_status = status_map.get(status_code, status_code)

            # Create job info in format compatible with sacct parsing
            job_info = {
                'JobID': job_id,
                'JobName': fields[1],
                'State': mapped_status,
                'ExitCode': '',  # Not available in squeue
                'Start': '',     # Not available in squeue  
                'End': '',       # Not available in squeue
                'Elapsed': fields[3],  # Time used
                'AllocCPUS': '',       # Not directly available
                'ReqMem': '',          # Not directly available
                'MaxRSS': '',          # Not available in squeue
                'NodeList': fields[4] if fields[4] != '(None assigned)' else '',
                'Reason': fields[7] if mapped_status == 'PENDING' else ''
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
                job.start_time = datetime.strptime(
                    slurm_job['Start'], '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                pass

        if slurm_job.get('End') and slurm_job['End'] != 'Unknown':
            try:
                job.end_time = datetime.strptime(
                    slurm_job['End'], '%Y-%m-%dT%H:%M:%S')
            except ValueError:
                pass

        # Update elapsed time
        if job.status == 'RUNNING' and job.start_time and not job.time_used:
            job.time_used = datetime.now() - job.start_time

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