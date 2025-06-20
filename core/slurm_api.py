import configparser
import threading
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum, auto
import functools
from typing import Any, Callable, Dict, List, Optional, Tuple
import paramiko
from core.defaults import *
from core.event_bus import Events, get_event_bus
from utils import settings_path, parse_duration


JOB_CODES = {
    "CD": "COMPLETED", "CG": "COMPLETING", "F": "FAILED", "PD": "PENDING",
    "PR": "PREEMPTED", "R": "RUNNING", "S": "SUSPENDED", "ST": "STOPPED",
    "CA": "CANCELLED", "TO": "TIMEOUT", "NF": "NODE_FAIL", "RV": "REVOKED",
    "SE": "SPECIAL_EXIT", "OOM": "OUT_OF_MEMORY", "BF": "BOOT_FAIL",
    "DL": "DEADLINE", "OT": "OTHER"
}


class SlurmWorker(QThread):  # Changed from threading.Thread to QThread
    """Worker thread for SLURM operations using event bus - continuous loop"""

    def __init__(self, slurm_api, refresh_interval_seconds=5):
        super().__init__()  # QThread doesn't need daemon=True
        self.slurm_api = slurm_api
        self.event_bus = get_event_bus()
        self.refresh_interval = refresh_interval_seconds
        self._stop_requested = False  # Changed from threading.Event to simple boolean

    def run(self):
        """Continuous loop until stop is requested"""
        try:
            if self.slurm_api.connection_status != ConnectionState.CONNECTED:
                return
            nodes_data = self.slurm_api.fetch_nodes_info()
            queue_jobs = self.slurm_api.fetch_job_queue()
            self.event_bus.emit(Events.DATA_READY,
                                {"nodes": nodes_data or [],
                                    "jobs": queue_jobs or []},
                                source="slurmworker")

        except Exception as e:
            print(f"Worker error: {e}")
            self.event_bus.emit(Events.ERROR_OCCURRED,
                                {"error": str(e)}, source="worker")

    def stop(self):
        """Stop the worker thread"""
        self._stop_requested = True
        self.quit()  # QThread method to quit the event loop
        # self.wait()  # QThread method to wait for thread to finish


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
        if not hasattr(self, 'connection_status') or self.connection_status != ConnectionState.CONNECTED:
            print("SlurmAPI is not connected!")
            return None
        return func(self, *args, **kwargs)
    return wrapper


class SlurmAPI():
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
        if hasattr(self, '_initialized'):
            return

        self.event_bus = get_event_bus()
        self.connection_status = ConnectionState.DISCONNECTED
        self._config = ConnectionConfig()
        self._client: Optional[paramiko.SSHClient]
        self._load_connection_config()
        self._initialized = True
        self.accounts = None
        self.partitions = None


    def _load_connection_config(self):
        try:
            config = configparser.ConfigParser()
            config.read(settings_path)

            self._config.host = config['GeneralSettings']['clusterAddress']
            self._config.password = config['GeneralSettings']['psw']
            self._config.username = config['GeneralSettings']['username']
            return True
        except (KeyError, ValueError) as e:
            print(f"Invalid configuration file: {e}")
            return False

    def _set_connection_status(self, new_state: ConnectionState):
        old_state = self.connection_status
        self.connection_status = new_state
        self.event_bus.emit(
            Events.CONNECTION_STATE_CHANGED,
            data={"old_state": old_state,
                  "new_state": self.connection_status},
            source="slurmapi"
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
                look_for_keys=False
            )
            self._set_connection_status(ConnectionState.CONNECTED)

            # --- fetch some basic info ---
            self.fetch_accounts()
            self.fetch_partitions()
            # -----------------------------

            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self._set_connection_status(ConnectionState.DISCONNECTED)

            self.disconnect()
            return False

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
                        node_dict["RESERVED"] = "YES" if "RESERVED" in value.upper(
                        ) else "NO"

            nodes_arr.append(node_dict)

        return nodes_arr

    @requires_connection
    def fetch_job_queue(self) -> List[Dict[str, Any]]:
        """Fetch job queue information"""

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
            msg_out, err_out = self.run_command("sacctmgr show associations format=Account -n -P")
            if err_out:
                print(f"Error fetching accounts: {err_out}")
                return []
            
            self.accounts  = sorted(list(set(msg_out.splitlines())))
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


def _refresh(slurm_api: SlurmAPI):
    try:
        if slurm_api.connection_status != ConnectionState.CONNECTED:
            return

        nodes_data = slurm_api.fetch_nodes_info()
        queue_jobs = slurm_api.fetch_job_queue()

        get_event_bus().emit(Events.DATA_READY,
                             {"nodes": nodes_data or [],
                              "jobs": queue_jobs or []},
                             source="slurmworker")

    except Exception as e:
        print(f"Worker error: {e}")
        get_event_bus().emit(Events.ERROR_OCCURRED,
                             {"error": str(e)}, source="worker")


def refresh_func(slurm_api: SlurmAPI):
    t = threading.Thread(target=functools.partial(
        _refresh, slurm_api), daemon=True)
    t.start()


if __name__ == '__main__':
    settings_path = "/home/nicola/Desktop/slurm_gui/configs/settings.ini"
    api = SlurmAPI()
    print(api._config)
    api.connect()
    print(api.fetch_job_queue())
