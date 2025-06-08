import configparser
import os
import tempfile
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
from pathlib import Path
import paramiko
from PyQt6.QtCore import QObject, pyqtSignal, QSettings

from modules.data_classes import Job
from utils import determine_job_status, parse_duration, settings_path

# Job status code mappings
JOB_CODES = {
    "CD": "COMPLETED", "CG": "COMPLETING", "F": "FAILED", "PD": "PENDING",
    "PR": "PREEMPTED", "R": "RUNNING", "S": "SUSPENDED", "ST": "STOPPED",
    "CA": "CANCELLED", "TO": "TIMEOUT", "NF": "NODE_FAIL", "RV": "REVOKED",
    "SE": "SPECIAL_EXIT", "OOM": "OUT_OF_MEMORY", "BF": "BOOT_FAIL",
    "DL": "DEADLINE", "OT": "OTHER"
}

# MODEL
class SlurmConnectionModel(QObject):
    """Model: Manages SLURM connection state and data operations"""
    
    # Signals for state changes
    connection_status_changed = pyqtSignal(bool)  # connected/disconnected
    cluster_info_updated = pyqtSignal(dict)  # cluster information
    submission_options_updated = pyqtSignal(dict)  # partitions, QoS, etc.
    
    def __init__(self):
        super().__init__()
        
        # Connection state
        self._connected = False
        self._client = None
        
        # Connection configuration
        self._host = ""
        self._user = ""
        self._password = ""
        
        # Cluster information
        self._cluster_info = {
            'remote_user': None,
            'user_groups': None,
            'num_nodes': None,
            'hostname': None,
            'slurm_version': None,
            'remote_home': None
        }
        
        # Submission options
        self._submission_options = {
            'partitions': [],
            'constraints': [],
            'qos_list': [],
            'accounts': [],
            'gres': []
        }
    
    # Connection management
    def load_configuration(self, config_path: str) -> bool:
        """Load connection configuration from file"""
        try:
            config = configparser.ConfigParser()
            config.read(config_path)
            
            self._host = config['GeneralSettings']['clusterAddress']
            self._password = config['GeneralSettings']['psw']
            self._user = config['GeneralSettings']['username']
            return True
        except (KeyError, ValueError) as e:
            print(f"Invalid configuration file: {e}")
            return False
    
    def connect(self) -> bool:
        """Establish SSH connection to SLURM cluster"""
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            self._client.connect(
                self._host,
                username=self._user,
                password=self._password,
                allow_agent=False,
                look_for_keys=False,
                timeout=30
            )
            
            self._connected = True
            self.connection_status_changed.emit(True)
            
            # Initialize cluster data
            self._fetch_basic_info()
            self._fetch_submission_options()
            
            return True
            
        except Exception as e:
            print(f"Connection failed: {e}")
            self._connected = False
            self.connection_status_changed.emit(False)
            return False
    
    def disconnect(self):
        """Close SSH connection"""
        if self._client:
            self._client.close()
            self._connected = False
            self.connection_status_changed.emit(False)
    
    def is_connected(self) -> bool:
        """Check if connection is active"""
        if not self._client:
            return False
            
        try:
            transport = self._client.get_transport()
            if transport and transport.is_active():
                # Test channel
                channel = transport.open_session(timeout=1)
                if channel:
                    channel.close()
                    return True
            return False
        except Exception:
            self._connected = False
            self.connection_status_changed.emit(False)
            return False
    
    def run_command(self, command: str) -> Tuple[str, str]:
        """Execute command on remote server"""
        if not self.is_connected():
            raise ConnectionError("SSH connection not established")
            
        stdin, stdout, stderr = self._client.exec_command(command)
        return stdout.read().decode().strip(), stderr.read().decode().strip()
    
    # Data fetching methods
    def _fetch_basic_info(self):
        """Fetch basic cluster information"""
        try:
            commands = {
                "remote_user": "whoami",
                "user_groups": "groups", 
                "num_nodes": "sinfo -h -o '%D' | awk '{s+=$1} END {print s}'",
                "hostname": "hostname",
                "slurm_version": "scontrol --version"
            }
            
            for attr, cmd in commands.items():
                result, _ = self.run_command(cmd)
                self._cluster_info[attr] = result.strip()
            
            # Set up home directory
            self._cluster_info['remote_home'], _ = self.run_command("echo $HOME")
            self._cluster_info['remote_home'] = self._cluster_info['remote_home'].strip()
            
            # Create log directory
            self.run_command(f"mkdir -p {self._cluster_info['remote_home']}/.logs")
            
            self.cluster_info_updated.emit(self._cluster_info.copy())
            
        except Exception as e:
            print(f"Failed to fetch cluster info: {e}")
    
    def _fetch_submission_options(self):
        """Fetch SLURM submission options"""
        try:
            # Fetch partitions
            partitions_out, _ = self.run_command("sinfo -h -o '%P'")
            self._submission_options['partitions'] = sorted(set(partitions_out.splitlines()))
            
            # Fetch constraints
            constraints_out, _ = self.run_command("sinfo -o '%f' | sort | uniq")
            self._submission_options['constraints'] = sorted(set(constraints_out.split()))
            
            # Fetch QoS options
            qos_out, _ = self.run_command("sacctmgr show qos format=Name -n -P")
            self._submission_options['qos_list'] = sorted(set(qos_out.splitlines()))
            
            # Fetch user accounts
            if self._cluster_info['remote_user']:
                acc_out, _ = self.run_command(
                    f"sacctmgr show associations user={self._cluster_info['remote_user']} format=Account -n -P")
                self._submission_options['accounts'] = sorted(set(acc_out.splitlines()))
            
            # Fetch GRES
            gres_out, _ = self.run_command("scontrol show gres")
            self._submission_options['gres'] = [
                line.strip() for line in gres_out.splitlines() if "Name=" in line
            ]
            
            self.submission_options_updated.emit(self._submission_options.copy())
            
        except Exception as e:
            print(f"Failed to fetch submission options: {e}")
    
    def fetch_nodes_info(self) -> List[Dict[str, Any]]:
        """Fetch detailed node information"""
        if not self.is_connected():
            raise ConnectionError("Not connected to SLURM")
            
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
                        
                    if key == "State":
                        node_dict["RESERVED"] = "YES" if "RESERVED" in value.upper() else "NO"
            
            nodes_arr.append(node_dict)
        
        return nodes_arr
    
    def fetch_job_queue(self) -> List[Dict[str, Any]]:
        """Fetch job queue information"""
        if not self.is_connected():
            raise ConnectionError("Not connected to SLURM")
            
        cmd = "squeue -O jobarrayid:\\;,Reason:\\;,NodeList:\\;,Username:\\;,tres-per-job:\\;," + \
              "tres-per-task:\\;,tres-per-node:\\;,Name:\\;,Partition:\\;,StateCompact:\\;," + \
              "Timelimit:\\;,TimeUsed:\\;,NumNodes:\\;,NumTasks:\\;,Reason:\\;,MinMemory:\\;," + \
              "MinCpus:\\;,Account:\\;,PriorityLong:\\;,jobid:\\;,tres:\\;,nice:"
        
        out, _ = self.run_command(cmd)
        job_queue = []
        
        for i, line in enumerate(out.splitlines()):
            if i == 0:  # Skip header
                continue
                
            fields = line.split(";")
            if len(fields) < 21:
                continue
                
            try:
                job_dict = self._parse_job_fields(fields)
                job_queue.append(job_dict)
            except (IndexError, ValueError) as e:
                print(f"Error parsing job data: {e}")
        
        return job_queue
    
    def submit_job(self, job: Job, discord_settings: Optional[Dict] = None) -> Optional[str]:
        """Submit a job to SLURM"""
        if not self.is_connected():
            raise ConnectionError("Not connected to SLURM")
            
        # Validate job
        validation_issues = job.validate_parameters()
        if validation_issues:
            raise ValueError(f"Job validation failed: {'; '.join(validation_issues)}")
        
        # Generate script
        script_path = job.save_sbatch_script(
            include_discord=bool(discord_settings and discord_settings.get("enabled", False)),
            discord_settings=discord_settings
        )
        
        try:
            # Upload script
            remote_script_path = f"/tmp/{os.path.basename(script_path)}"
            sftp = self._client.open_sftp()
            sftp.put(script_path, remote_script_path)
            sftp.close()
            
            # Submit job
            stdout, stderr = self.run_command(f"sbatch {remote_script_path}")
            
            if stderr and "INFO" not in stderr:
                raise RuntimeError(f"SLURM error: {stderr}")
            
            # Parse job ID
            if "Submitted batch job" in stdout:
                job_id = stdout.strip().split()[-1]
                return job_id
                
            return None
            
        finally:
            # Clean up
            try:
                os.unlink(script_path)
            except:
                pass
    
    def get_job_logs(self, job: Job, preserve_progress_bars: bool = False) -> Tuple[str, str]:
        """Get job output and error logs with proper handling of progress bars"""
        if not self.is_connected():
            raise ConnectionError("SSH connection not established.")
        
        def clean_progress_output(text: str, preserve_final_state: bool = False) -> str:
            """Clean text containing progress bars and ANSI sequences"""
            import re
            
            # Remove ANSI escape sequences but preserve structure
            ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
            clean_text = ansi_escape.sub('', text)
            
            if not preserve_final_state:
                return clean_text.replace('\r', '\n')
            
            # Split by newlines first to handle each logical line
            lines = clean_text.split('\n')
            cleaned_lines = []
            
            for line in lines:
                if '\r' in line:
                    parts = line.split('\r')
                    final_part = ''
                    
                    for part in reversed(parts):
                        if part.strip():
                            final_part = part.strip()
                            break
                    
                    if final_part:
                        cleaned_lines.append(final_part)
                else:
                    if line.strip():
                        cleaned_lines.append(line)
            
            return '\n'.join(cleaned_lines)
        
        # Try multiple possible log file locations
        possible_stdout_files = [
            f"{self._cluster_info['remote_home']}/.logs/out_{job.id}.log",
            f"/tmp/out_{job.id}.log",
            f"out_{job.id}.log",
        ]
        
        possible_stderr_files = [
            f"{self._cluster_info['remote_home']}/.logs/err_{job.id}.log",
            f"/tmp/err_{job.id}.log", 
            f"err_{job.id}.log",
        ]
        
        # Check job details for custom paths
        try:
            job_details_cmd = f"scontrol show job {job.id}"
            job_details_output, _ = self.run_command(job_details_cmd)
            
            for line in job_details_output.split('\n'):
                if 'StdOut=' in line:
                    stdout_match = re.search(r'StdOut=([^\s]+)', line)
                    if stdout_match:
                        custom_stdout = stdout_match.group(1)
                        if custom_stdout not in possible_stdout_files:
                            possible_stdout_files.insert(0, custom_stdout)
                            
                if 'StdErr=' in line:
                    stderr_match = re.search(r'StdErr=([^\s]+)', line)
                    if stderr_match:
                        custom_stderr = stderr_match.group(1)
                        if custom_stderr not in possible_stderr_files:
                            possible_stderr_files.insert(0, custom_stderr)
        except Exception as e:
            print(f"Warning: Could not query job details for {job.id}: {e}")
        
        stdout, stderr = "", ""
        
        try:
            sftp = self._client.open_sftp()
            
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
    
    def read_maintenances(self) -> Optional[str]:
        """Read SLURM maintenance reservations"""
        if not self.is_connected():
            return None
            
        msg_out, _ = self.run_command("scontrol show reservation 2>/dev/null")
        return None if "No reservations in the system" in msg_out else msg_out
    
    # Utility methods
    def _parse_tres(self, tres_string: str, prefix: str, node_dict: Dict[str, Any]):
        """Parse TRES strings"""
        parts = tres_string.split("=", 1)[1].split(",")
        for part in parts:
            if not part:
                continue
            try:
                key, value = part.split("=")
                node_dict[f"{prefix}{key}"] = value
            except ValueError:
                pass
    
    def _parse_job_fields(self, fields: List[str]) -> Dict[str, Any]:
        """Parse job fields from squeue output"""
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
            "RawStatusCode": raw_status_code,
            "Time Limit": fields[10],
            "Time Used": [fields[11], parse_duration(fields[11]) if fields[11] else timedelta()],
            "Account": fields[17],
            "Priority": int(fields[18]) if fields[18].isdigit() else 0,
            "GPUs": 0
        }
        
        # Parse resources
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
        
        # Handle pending jobs
        if job_dict["Status"] == "PENDING":
            job_dict["Nodelist"] = job_dict["Reason"]
        
        return job_dict
    
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
    
    # Getters for current state
    def get_cluster_info(self) -> Dict[str, Any]:
        """Get cluster information"""
        return self._cluster_info.copy()
    
    def get_submission_options(self) -> Dict[str, Any]:
        """Get submission options"""
        return self._submission_options.copy()
    
    def get_connection_config(self) -> Dict[str, str]:
        """Get connection configuration"""
        return {
            'host': self._host,
            'user': self._user,
            'password': self._password
        }
    
    def read_maintenances(self) -> Optional[str]:
        """Read SLURM maintenance reservations"""
        if not self.is_connected():
            return None
            
        msg_out, _ = self.run_command("scontrol show reservation 2>/dev/null")
        return None if "No reservations in the system" in msg_out else msg_out