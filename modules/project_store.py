import json
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QSettings

# Forward import for type checking – real instance is passed at runtime
from slurm_connection import SlurmConnection

__all__ = [
    "Job",
    "Project",
    "ProjectStore",
]

# ---------------------------------------------------------------------------
# Model layer
# ---------------------------------------------------------------------------


def _clean_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Drop None values so the JSON stays compact."""
    return {k: v for k, v in d.items() if v is not None}


@dataclass
class Job:
    id: int | str
    name: str
    status: str = "pending"  # arbitrary free‑form string, e.g. "queued", "running"
    info: Dict[str, Any] = field(default_factory=dict)

    # .................................................................
    def to_json(self) -> Dict[str, Any]:
        d = asdict(self)
        d["info"] = self.info or None  # empty dict → null
        return _clean_dict(d)

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Job":
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            status=data.get("status", "pending"),
            info=data.get("info", {}) or {},
        )


@dataclass
class Project:
    name: str
    jobs: List[Job] = field(default_factory=list)

    # .................................................................
    def add_job(self, job: Job) -> None:
        self.jobs.append(job)

    def remove_job(self, job_id: int | str) -> None:
        self.jobs = [j for j in self.jobs if j.id != job_id]

    # .................................................................
    def to_json(self) -> Dict[str, Any]:
        return {
            "jobs": [j.to_json() for j in self.jobs],
        }

    @classmethod
    def from_json(cls, name: str, data: Dict[str, Any]) -> "Project":
        jobs = [Job.from_json(j) for j in data.get("jobs", [])]
        return cls(name=name, jobs=jobs)


# ---------------------------------------------------------------------------
# Persistence façade (singleton)
# ---------------------------------------------------------------------------

class ProjectStore:
    """Thread‑safe singleton that mirrors a remote *settings.ini* file."""

    _instance: "ProjectStore | None" = None
    _lock = RLock()

    def __new__(cls, slurm: SlurmConnection, remote_path: Optional[str] = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init(slurm, remote_path)
            return cls._instance

    # ------------------------------------------------------------------
    # initialisation & helpers
    # ------------------------------------------------------------------
    def _init(self, slurm: SlurmConnection, remote_path: Optional[str]):
        if not slurm.check_connection():
            raise RuntimeError("SlurmConnection must be *connected* before using ProjectStore")

        self.slurm = slurm

        # Where to put the INI on the cluster
        if remote_path is None:
            home = (
                self.slurm.remote_home
                or self.slurm.run_command("echo $HOME")[0].strip()
            )
            remote_path = f"{home}/.slurm_gui/project_settings.ini"
        self.remote_path = remote_path

        # Local temporary copy (lives for the whole session)
        self._tmp_local = Path(tempfile.mkdtemp()) / "project_settings.ini"

        self._download_remote()
        self.settings = QSettings(str(self._tmp_local), QSettings.Format.IniFormat)
        self.settings.setFallbacksEnabled(False)

        self._projects: Dict[str, Project] = self._read_from_settings()

    # .................................................................
    def _download_remote(self) -> None:
        """Fetch the INI from the cluster (create it if missing)."""
        try:
            sftp = self.slurm.client.open_sftp()
            remote_dir = Path(self.remote_path).parent.as_posix()
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                sftp.mkdir(remote_dir)

            try:
                sftp.get(self.remote_path, str(self._tmp_local))
            except FileNotFoundError:
                # First run → create an empty file and upload it
                self._tmp_local.touch()
                sftp.put(str(self._tmp_local), self.remote_path)
        finally:
            sftp.close()

    def _upload_remote(self) -> None:
        """Push the local INI back to the cluster."""
        self.settings.sync()
        try:
            sftp = self.slurm.client.open_sftp()
            sftp.put(str(self._tmp_local), self.remote_path)
        finally:
            sftp.close()

    def _read_from_settings(self) -> Dict[str, Project]:
        raw = self.settings.value("projects/data", "")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return {
                name: Project.from_json(name, pj_data) for name, pj_data in data.items()
            }
        except Exception:
            # corrupted → reset
            return {}

    def _write_to_settings(self) -> None:
        data = {name: pj.to_json() for name, pj in self._projects.items()}
        self.settings.setValue("projects/data", json.dumps(data))
        self._upload_remote()

    # ------------------------------------------------------------------
    # Public API (project level)
    # ------------------------------------------------------------------
    def all_projects(self) -> List[str]:
        return list(self._projects.keys())

    def add_project(self, name: str, *, jobs: List[Job] | None = None) -> None:
        if name in self._projects:
            return
        self._projects[name] = Project(name, jobs or [])
        self._write_to_settings()

    def remove_project(self, name: str) -> None:
        if name not in self._projects:
            return
        self._projects.pop(name)
        self._write_to_settings()

    def rename_project(self, old: str, new: str) -> None:
        if old not in self._projects or new in self._projects:
            return
        self._projects[new] = self._projects.pop(old)
        self._projects[new].name = new
        self._write_to_settings()

    def get(self, name: str) -> Optional[Project]:
        return self._projects.get(name)

    # ------------------------------------------------------------------
    # Public API (job level)
    # ------------------------------------------------------------------
    def add_job(self, project: str, job: Job) -> None:
        self._projects.setdefault(project, Project(project)).add_job(job)
        self._write_to_settings()

    def remove_job(self, project: str, job_id: int | str) -> None:
        pj = self._projects.get(project)
        if not pj:
            return
        pj.remove_job(job_id)
        self._write_to_settings()

    # ------------------------------------------------------------------
    # Convenience / debugging helpers
    # ------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover – convenience only
        return f"<ProjectStore {self._projects}>"

