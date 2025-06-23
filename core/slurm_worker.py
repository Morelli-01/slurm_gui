from dataclasses import dataclass
from core.defaults import *
from core.slurm_api import ConnectionState, SlurmAPI
from models.project_model import Job, JobsModel


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
    "OT": "OTHER",
}


class SlurmWorker(QThread):
    """Worker thread for SLURM operations using Qt signals for thread-safety."""

    data_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, slurm_api: SlurmAPI, jobs_model: JobsModel, refresh_interval_seconds=5):
        super().__init__()
        self.slurm_api = slurm_api
        self.jobs_model = jobs_model
        self.refresh_interval = refresh_interval_seconds
        self._stop_requested = False

    def run(self):
        """Fetch data, pre-process it, and emit signals with the results."""
        try:
            if self.slurm_api.connection_status != ConnectionState.CONNECTED:
                return

            nodes_data = self.slurm_api.fetch_nodes_info()
            queue_jobs = self.slurm_api.fetch_job_queue() or []

            # --- MODIFICATION: Pre-sort the data in the worker thread ---
            # This reduces the workload on the main GUI thread.
            sorted_queue_jobs = sorted(
                queue_jobs,
                key=lambda job: (
                    job.get("Status", ""),
                    -ord(job.get("User", " ")[0]) - 0.01 * ord(job.get("User", "  ")[1]),
                ),
                reverse=True,
            )

            active_job_ids = self.jobs_model.get_active_job_ids()
            job_details_data = None
            if active_job_ids:
                job_details_data = self.slurm_api.fetch_job_details_sacct(
                    active_job_ids
                )

            self.data_ready.emit(
                {
                    "nodes": nodes_data or [],
                    "jobs": sorted_queue_jobs,  # Emit the pre-sorted list
                    "job_details": job_details_data or [],
                }
            )

        except Exception as e:
            error_message = f"Worker thread error: {e}"
            print(error_message)
            self.error_occurred.emit(error_message)

    def stop(self):
        """Stop the worker thread"""
        self._stop_requested = True
        self.quit()
        self.wait()

