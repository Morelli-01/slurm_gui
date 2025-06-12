import configparser
import os
import tempfile
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
from pathlib import Path
import paramiko
from PyQt6.QtCore import QObject, pyqtSignal, QSettings

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