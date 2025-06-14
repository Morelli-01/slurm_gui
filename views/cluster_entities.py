from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.defaults import STUDENTS_JOBS_KEYWORD
from core.slurm_api import SlurmAPI
from utils import parse_memory_size
import os

@dataclass
class Node:
    """Represents a single SLURM node with convenience metrics."""

    name: str
    info: Dict[str, Any] = field(default_factory=dict)
    jobs: List[Dict[str, Any]] = field(default_factory=list)

    # Derived values
    total_gpus: int = 0
    used_gpus: int = 0
    free_gpus: int = 0
    gpu_users: Dict[str, int] = field(default_factory=dict)
    stud_used: int = 0
    prod_used: int = 0
    cpu_usage_percent: float = 0.0
    ram_usage_percent: float = 0.0
    total_cpu: int = 0
    alloc_cpu: int = 0
    total_mem_mb: int = 0
    alloc_mem_mb: int = 0
    tooltips: List[str] = field(default_factory=list)
    state: str = ""
    reserved: bool = False
    block_states: List[str] = field(default_factory=list)

    def update(self, info: Dict[str, Any], jobs: List[Dict[str, Any]]) -> None:
        """Update node information and running jobs."""
        self.info = info
        self.jobs = [j for j in jobs if j.get("Nodelist") == self.name]

        # Basic state information
        self.state = str(info.get("State", "")).upper()
        self.reserved = str(info.get("RESERVED", "NO")).upper() == "YES"

        # GPU info
        self.total_gpus = int(info.get("total_gres/gpu", 0))
        self.used_gpus = int(info.get("alloc_gres/gpu", 0))
        self.free_gpus = max(self.total_gpus - self.used_gpus, 0)

        stud_used = 0
        prod_used = 0
        self.gpu_users = {}
        for job in self.jobs:
            gpus = int(job.get("GPUs", 0))
            user = job.get("User", "unknown")
            self.gpu_users[user] = self.gpu_users.get(user, 0) + gpus
            account = job.get("Account", "")
            if any(k in account for k in STUDENTS_JOBS_KEYWORD):
                stud_used += gpus
            else:
                prod_used += gpus

        self.stud_used = min(stud_used, self.used_gpus)
        self.prod_used = min(prod_used, max(self.used_gpus - self.stud_used, 0))

        # CPU / RAM info
        try:
            self.total_cpu = int(info.get("total_cpu", 0))
            self.alloc_cpu = int(info.get("alloc_cpu", 0))
            self.cpu_usage_percent = (
                self.alloc_cpu / self.total_cpu * 100
            ) if self.total_cpu > 0 else 0
        except (ValueError, TypeError):
            self.total_cpu = 0
            self.alloc_cpu = 0
            self.cpu_usage_percent = 0.0

        try:
            self.total_mem_mb = parse_memory_size(info.get("total_mem", "1M"))
            self.alloc_mem_mb = parse_memory_size(info.get("alloc_mem", "0M"))
            self.ram_usage_percent = (
                self.alloc_mem_mb / self.total_mem_mb * 100
            ) if self.total_mem_mb > 0 else 0
        except (ValueError, TypeError, IndexError):
            self.total_mem_mb = 0
            self.alloc_mem_mb = 0
            self.ram_usage_percent = 0.0

        self.tooltips = self.get_tooltips()
        self.block_states = self._compute_block_states()

    def get_tooltips(self) -> List[str]:
        """Generate tooltips showing which user occupies each GPU."""
        tooltips = [""] * self.total_gpus
        stud_jobs = []
        prod_jobs = []
        for job in self.jobs:
            account = job.get("Account", "")
            (stud_jobs if any(k in account for k in STUDENTS_JOBS_KEYWORD) else prod_jobs).append(job)

        idx = 0
        for job in stud_jobs + prod_jobs:
            num = int(job.get("GPUs", 0))
            user = job.get("User", "unknown")
            job_id = job.get("Job ID", None)
            for i in range(num):
                if idx + i < self.total_gpus:
                    tooltips[idx + i] = f"{user}{os.linesep}Job: {job_id}"
            idx += num

        return tooltips

    def _compute_block_states(self) -> List[str]:
        """Determine GPU block state representation for this node."""
        if self.reserved:
            return ["reserved"] * self.total_gpus

        if any(s in self.state for s in ["DRAIN", "DOWN", "UNKNOWN", "NOT_RESPONDING"]):
            return ["unavailable"] * self.total_gpus

        high_constraint_state = False
        mid_constraint_state = False
        if "ALLOCATED" in self.state or "MIXED" in self.state:
            try:
                cpu_util = self.alloc_cpu / self.total_cpu if self.total_cpu > 0 else 0
                mem_util = (
                    self.alloc_mem_mb / self.total_mem_mb
                    if self.total_mem_mb > 0
                    else 0
                )

                high_constraint_state = cpu_util >= 0.9 or mem_util >= 0.9
                mid_constraint_state = (cpu_util >= 0.7 or mem_util >= 0.7) and not high_constraint_state
            except (ValueError, IndexError):
                high_constraint_state = False
                mid_constraint_state = False

        blocks = ["stud_used"] * self.stud_used
        blocks.extend(["prod_used"] * self.prod_used)

        remaining = self.total_gpus - self.used_gpus
        if remaining > 0:
            if "ALLOCATED" in self.state or "MIXED" in self.state:
                if high_constraint_state:
                    blocks.extend(["high-constraint"] * remaining)
                elif mid_constraint_state:
                    blocks.extend(["mid-constraint"] * remaining)
                else:
                    blocks.extend(["available"] * remaining)
            else:
                blocks.extend(["available"] * remaining)

        return blocks

    def as_dict(self) -> Dict[str, Any]:
        """Return info dict enriched with computed metrics."""
        data = {"NodeName": self.name}
        data.update(self.info)
        data.update(
            {
                "total_gpus": self.total_gpus,
                "used_gpus": self.used_gpus,
                "free_gpus": self.free_gpus,
                "gpu_users": self.gpu_users,
                "stud_used": self.stud_used,
                "prod_used": self.prod_used,
                "cpu_usage_percent": self.cpu_usage_percent,
                "ram_usage_percent": self.ram_usage_percent,
                "total_cpu": self.total_cpu,
                "alloc_cpu": self.alloc_cpu,
                "total_mem_mb": self.total_mem_mb,
                "alloc_mem_mb": self.alloc_mem_mb,
                "jobs": self.jobs,
                "tooltips": self.tooltips,
                "state": self.state,
                "reserved": self.reserved,
                "block_states": self.block_states,
            }
        )
        return data

@dataclass
class Cluster:
    """Collection of SLURM nodes fetched from a connection."""
    nodes: Dict[str, Node] = field(default_factory=dict)
    jobs: List[Dict[str, Any]] = field(default_factory=list)

    def update_from_data(
        self, nodes_data: List[Dict[str, Any]], jobs_data: List[Dict[str, Any]]
    ) -> None:
        """Update cluster nodes from pre-fetched data."""
        self.jobs = jobs_data

        for node_info in nodes_data:
            name = node_info.get("NodeName")
            if not name:
                continue
            node = self.nodes.get(name)
            if not node:
                node = Node(name=name)
                self.nodes[name] = node
            node.update(node_info, jobs_data)

    def as_dicts(self) -> List[Dict[str, Any]]:
        """Return list of raw node dictionaries."""
        return [node.as_dict() for node in self.nodes.values()]