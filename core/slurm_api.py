import configparser
import re
import threading
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum, auto
import functools
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid
import paramiko
from core.defaults import *
from core.event_bus import Events, get_event_bus
from models.project_model import Job
from utils import settings_path, parse_duration





class ConnectionState(Enum):
    """Clear connection states"""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()


@dataclass
class ConnectionConfig:
    """Immutable connection configuration"""

    host: str = None
    username: str = None
    password: str = None
    timeout: int = 30
    retry_attempts: int = 1
    retry_delay: int = 5


def requires_connection(func: Callable) -> Callable:
    """Returns None if not connected, no error"""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.connection_status != ConnectionState.CONNECTED:
            print("SlurmAPI is not connected!")
            return None
        return func(self, *args, **kwargs)

    return wrapper


class SlurmAPI:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Reset the singleton instance to create a fresh SlurmAPI"""
        if cls._instance is not None:
            # Disconnect and cleanup the old instance
            cls._instance.disconnect()
            cls._instance = None
        return cls()

    def __init__(self):
        # Only initialize once
        if hasattr(self, "_initialized"):
            return

        self.event_bus = get_event_bus()
        self.connection_status = ConnectionState.DISCONNECTED
        self._config = ConnectionConfig()
        self._client: Optional[paramiko.SSHClient]
        self._load_connection_config()
        self._initialized = True
        self.accounts = None
        self.partitions = None
        self.qos = None
        self.constraint = None
        self.nodelist = None
        self.remote_home: Optional[str] = None

    def _load_connection_config(self):
        try:
            config = configparser.ConfigParser()
            config.read(settings_path)

            self._config.host = config["GeneralSettings"]["clusterAddress"]
            self._config.password = config["GeneralSettings"]["psw"]
            self._config.username = config["GeneralSettings"]["username"]
            return True
        except (KeyError, ValueError) as e:
            print(f"Invalid configuration file: {e}")
            return False

    def _set_connection_status(self, new_state: ConnectionState):
        old_state = self.connection_status
        self.connection_status = new_state
        self.event_bus.emit(
            Events.CONNECTION_STATE_CHANGED,
            data={"old_state": old_state, "new_state": self.connection_status},
            source="slurmapi",
        )
        print(f"Connection State changed: {old_state} -> {new_state}")

    @requires_connection
    def run_command(self, command: str) -> Tuple[str, str]:
        """Execute command on remote server"""

        stdin, stdout, stderr = self._client.exec_command(command)
        return stdout.read().decode().strip(), stderr.read().decode().strip()

    def connect(self, *args):
        """Establish SSH connection"""
        self._set_connection_status(ConnectionState.CONNECTING)
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._client.connect(
                self._config.host,
                username=self._config.username,
                password=self._config.password,
                timeout=self._config.timeout,
                allow_agent=False,
                look_for_keys=False,
            )
            self._set_connection_status(ConnectionState.CONNECTED)
            self._load_basic_info()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self._set_connection_status(ConnectionState.DISCONNECTED)

            self.disconnect()
            return False
    
    @requires_connection
    def _load_basic_info(self):
        self.fetch_accounts()
        self.fetch_partitions()
        self.remote_home = self.get_home_directory()
        self.qos = self.fetch_qos()
        self.constraint = self.fetch_constraint()
        self.nodelist = self.fetch_nodelist()

    def disconnect(self):
        """Close connection"""
        if self._client:
            self._client.close()
            self._client = None

    @requires_connection
    def fetch_nodes_info(self) -> List[Dict[str, Any]]:
        """Fetch detailed node information"""

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
                        node_dict["RESERVED"] = (
                            "YES" if "RESERVED" in value.upper() else "NO"
                        )

            nodes_arr.append(node_dict)

        return nodes_arr

    @requires_connection
    def fetch_job_queue(self) -> List[Dict[str, Any]]:
        """Fetch job queue information"""

        cmd = (
            "squeue -O jobarrayid:\\;,Reason:\\;,NodeList:\\;,Username:\\;,tres-per-job:\\;,"
            + "tres-per-task:\\;,tres-per-node:\\;,Name:\\;,Partition:\\;,StateCompact:\\;,"
            + "Timelimit:\\;,TimeUsed:\\;,NumNodes:\\;,NumTasks:\\;,Reason:\\;,MinMemory:\\;,"
            + "MinCpus:\\;,Account:\\;,PriorityLong:\\;,jobid:\\;,tres:\\;,nice:"
        )

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

    @requires_connection
    def read_maintenances(self) -> Optional[str]:
        """Read SLURM maintenance reservations"""

        msg_out, _ = self.run_command("scontrol show reservation 2>/dev/null")
        return None if "No reservations in the system" in msg_out else msg_out

    @requires_connection
    def fetch_accounts(self) -> List[str]:
        """Fetch available accounts."""
        if self.accounts:
            return self.accounts
        try:
            # The command gives unique accounts already
            msg_out, err_out = self.run_command(
                "sacctmgr show associations format=Account -n -P"
            )
            if err_out:
                print(f"Error fetching accounts: {err_out}")
                return []

            self.accounts = sorted(list(set(msg_out.splitlines())))
            return self.accounts
        except Exception as e:
            print(f"Exception fetching accounts: {e}")
            return []

    @requires_connection
    def fetch_partitions(self) -> List[str]:
        """Fetch available partitions."""
        if self.partitions:
            return self.partitions
        try:
            msg_out, err_out = self.run_command("sinfo -h -o '%P'")
            if err_out:
                print(f"Error fetching partitions: {err_out}")
                return []
            msg_out = str(msg_out).replace("*", "")
            self.partitions = sorted(list(set(msg_out.splitlines())))
            return self.partitions
        except Exception as e:
            print(f"Exception fetching partitions: {e}")
            return []
        
    @requires_connection
    def fetch_qos(self) -> List[str]:
        """Fetch available partitions."""
        if self.qos:
            return self.qos
        try:
            msg_out, err_out = self.run_command("sacctmgr show qos --parsable2 format=Name --noheader")
            if err_out:
                print(f"Error fetching partitions: {err_out}")
                return []
            msg_out = str(msg_out).replace("*", "")
            self.qos = sorted(list(set(msg_out.splitlines())))
            return self.qos
        except Exception as e:
            print(f"Exception fetching partitions: {e}")
            return []    
        
    @requires_connection
    def fetch_constraint(self) -> List[str]:
        """Fetch available partitions."""
        if self.constraint:
            return self.constraint
        try:
            msg_out, err_out = self.run_command("sinfo -o '%f' --noheader  | sort | uniq")
            if err_out:
                print(f"Error fetching partitions: {err_out}")
                return []
            msg_out = str(msg_out).replace("*", "")
            self.constraint = sorted(list(set(msg_out.splitlines())))
            return self.constraint
        except Exception as e:
            print(f"Exception fetching partitions: {e}")
            return []
    
    @requires_connection
    def fetch_nodelist(self) -> List[str]:
        """Fetch available partitions."""
        if self.nodelist:
            return self.nodelist
        try:
            msg_out, err_out = self.run_command("sinfo -N -h -o \"%N\"")
            if err_out:
                print(f"Error fetching partitions: {err_out}")
                return []
            msg_out = str(msg_out).replace("*", "")
            self.nodelist = sorted(list(set(msg_out.splitlines())))
            return self.nodelist
        except Exception as e:
            print(f"Exception fetching partitions: {e}")
            return []
        
    @requires_connection
    def remote_path_exists(self, path: str) -> bool:
        """Check if a remote path exists and is a directory."""
        command = f'if [ -d "{path}" ]; then echo "exists"; fi'
        stdout, stderr = self.run_command(command)
        return stdout.strip() == "exists"

    @requires_connection
    def remote_file_exists(self, path: str) -> bool:
        """Check if a remote file exists."""
        command = f'if [ -f "{path}" ]; then echo "exists"; fi'
        stdout, stderr = self.run_command(command)
        return stdout.strip() == "exists"

    @requires_connection
    def list_remote_directories(self, path: str) -> List[str]:
        """List directories in a given remote path."""
        # The command finds all directories in the given path, at a max depth of 1, and prints their names.
        command = (
            f"find '{path}' -maxdepth 1 -mindepth 1 -type d -exec basename {{}} \\;"
        )
        stdout, stderr = self.run_command(command)
        if stderr:
            print(f"Error listing directories in '{path}': {stderr}")
            return []

        directories = stdout.strip().split("\n")
        # Filter out empty strings that might result from splitting
        return [d for d in directories if d]

    @requires_connection
    def get_home_directory(self) -> Optional[str]:
        """Get the user's home directory on the remote server."""
        stdout, stderr = self.run_command("echo $HOME")
        if stderr or not stdout.strip():
            print(f"Error fetching home directory: {stderr}")
            return None
        return stdout.strip()
   
    @requires_connection
    def cancel_job(self, job_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Cancels a job using scancel."""
        if not job_id or not str(job_id).isdigit():
            return None, f"Invalid Job ID: {job_id}"

        command = f"scancel {job_id}"
        stdout, stderr = self.run_command(command)

        if stderr:
            return None, stderr

        return stdout, None
    


    @requires_connection
    def submit_job(self, job: Job) -> Tuple[Optional[str], Optional[str]]:
        """Creates a temporary script, sbaches it, and returns the job ID or an error."""
        script_content = job.create_sbatch_script()
        
        sftp = None
        local_path = None
        remote_path = f"/tmp/slurm_gui_job_{uuid.uuid4().hex[:8]}.sh"

        try:
            # 1. Create a local temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".sh", encoding='utf-8', newline='') as tmp:
                tmp.write(script_content)
                local_path = tmp.name

            # 2. Define remote path and upload
            sftp = self._client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            sftp = None

            # 3. Sbatch the remote file
            sbatch_output, sbatch_error = self.run_command(f"sbatch {remote_path}")

            # 4. Parse output
            if sbatch_error:
                return None, sbatch_error
            
            match = re.search(r"Submitted batch job (\d+)", sbatch_output)
            if match:
                new_job_id = match.group(1)
                return new_job_id, None
            else:
                return None, sbatch_output or "sbatch command did not return a job ID."

        except Exception as e:
            return None, str(e)
        finally:
            # 5. Cleanup
            if local_path and os.path.exists(local_path):
                os.unlink(local_path)
            if self.connection_status == ConnectionState.CONNECTED:
                try:
                    self.run_command(f"rm {remote_path}")
                except Exception:
                    pass # Ignore cleanup errors if connection is lost
            if sftp:
                try: 
                    sftp.close()
                except Exception:
                    pass
    
    @requires_connection
    def fetch_job_details_sacct(self, job_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch detailed job information using sacct for a list of job IDs."""
        if not job_ids:
            return []

        job_id_str = ",".join(job_ids)
        format_str = "JobID,JobName,State,ExitCode,Start,End,Elapsed,AllocCPUS,ReqMem,MaxRSS,NodeList,Reason,DerivedExitCode"
        cmd = f"sacct -j {job_id_str} --format={format_str} --parsable2 --noheader"

        out, err = self.run_command(cmd)
        if err:
            print(f"Error running sacct: {err}")
            return []

        job_details = []
        lines = out.strip().splitlines()

        for line in lines:
            if '.' in line.split('|')[0]:
                continue
            
            parts = line.strip().split('|')
            if len(parts) < 13:
                continue

            try:
                details = {
                    "JobID": parts[0],
                    "JobName": parts[1],
                    "State": parts[2].strip().split(" ")[0],
                    "ExitCode": parts[3],
                    "Start": parts[4],
                    "End": parts[5],
                    "Elapsed": parts[6],
                    "AllocCPUS": parts[7],
                    "ReqMem": parts[8],
                    "MaxRSS": parts[9],
                    "NodeList": parts[10],
                    "Reason": parts[11],
                    "DerivedExitCode": parts[12],
                }
                job_details.append(details)
            except IndexError as e:
                print(f"Error parsing sacct line: '{line}'. Error: {e}")
                continue
        
        return job_details
    
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
            "Time Used": [
                fields[11],
                parse_duration(fields[11]) if fields[11] else timedelta(),
            ],
            "Account": fields[17],
            "Priority": int(fields[18]) if fields[18].isdigit() else 0,
            "GPUs": 0,
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


if __name__ == "__main__":
    settings_path = "/home/nicola/Desktop/slurm_gui/configs/settings.ini"
    api = SlurmAPI()
    print(api._config)
    api.connect()
    print(api.fetch_job_queue())
