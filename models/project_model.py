import copy
from dataclasses import dataclass, field
import uuid
from core.event_bus import get_event_bus, Events
from widgets.toast_widget import show_error_toast, show_success_toast, show_warning_toast
from typing import Dict, List, Any, Optional, Set
import json
import dataclasses

# In a new file: models/job.py
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    """
    A comprehensive data structure for a single SLURM job, designed to
    closely mirror sbatch command-line options.
    """

    # --- sbatch Options ---
    name: str = "new_job"
    account: Optional[str] = None
    array: Optional[str] = None
    working_directory: Optional[str] = None
    constraint: Optional[List[str]] = None
    cpus_per_task: Optional[int] = 1
    dependency: Optional[str] = None
    error_file: Optional[str] = None
    gpus: Optional[str] = None
    gpus_per_task: Optional[str] = None
    mem: Optional[str] = "1G"  # Default to 1GB
    nice: Optional[int] = None
    nodes: Optional[str] = 1
    ntasks: Optional[int] = 1
    output_file: Optional[str] = None
    oversubscribe: bool = False
    partition: Optional[str] = None
    qos: Optional[str] = None
    nodelist: Optional[List[str]] = None
    time_limit: Optional[str] = None
    # --- Custom Fields ---
    venv: Optional[str] = None
    project_name: Optional[str] = None  # To link the job to a project in the GUI
    optional_sbatch: Optional[str] = None
    script_commands: str = "echo 'Hello from SLURM!'"
    discord_notifications: bool = False

    # --- Internal State ---
    id: Optional[str] = None
    status: str = "NOT_SUBMITTED"
    elapsed: str = "00:00:00"
    
    def __post_init__(self):
        if self.error_file is None or self.output_file is None:
            # Import here to avoid circular import at module level
            from core.slurm_api import SlurmAPI
            remote_home = SlurmAPI().remote_home or "~/"
            if self.error_file is None:
                self.error_file = f"{remote_home}/.slurm_logs/err_%A.log"
            if self.output_file is None:
                self.output_file = f"{remote_home}/.slurm_logs/out_%A.log"

    def to_dict(self):
        """Converts the Job object to a dictionary for JSON serialization."""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        """Creates a Job instance from a dictionary."""
        return cls(**data)
    
    def create_sbatch_script(self) -> str:
        """
        Generates the content for an sbatch submission script based on the
        job's attributes. Uses os.linesep for cross-platform compatibility.
        """
        lines = ["#!/bin/bash"]

        # --- Standard SBATCH Options ---
        if self.name:
            lines.append(f"#SBATCH --job-name={self.name}")
        if self.account:
            lines.append(f"#SBATCH --account={self.account}")
        if self.array:
            lines.append(f"#SBATCH --array={self.array}")
        if self.working_directory:
            lines.append(f"#SBATCH --chdir={self.working_directory}")
        if self.constraint:
            value = self.constraint[0]
            if len(self.constraint) >= 1:
                for c in self.constraint[1:]:
                    value += f"|{c}"
            lines.append(f"#SBATCH --constraint='{value }'")
        if self.cpus_per_task:
            lines.append(f"#SBATCH --cpus-per-task={self.cpus_per_task}")
        if self.dependency:
            lines.append(f"#SBATCH --dependency={self.dependency}")
        if self.error_file:
            lines.append(f"#SBATCH --error={self.error_file}")
        if self.gpus:
            lines.append(f"#SBATCH --gpus={self.gpus}")
        if self.gpus_per_task:
            lines.append(f"#SBATCH --gpus-per-task={self.gpus_per_task}")
        if self.mem:
            lines.append(f"#SBATCH --mem={self.mem}")
        if self.nice is not None:
            lines.append(f"#SBATCH --nice={self.nice}")
        if self.nodes:
            lines.append(f"#SBATCH --nodes={self.nodes}")
        if self.ntasks:
            lines.append(f"#SBATCH --ntasks={self.ntasks}")
        if self.output_file:
            lines.append(f"#SBATCH --output={self.output_file}")
        if self.oversubscribe:
            lines.append("#SBATCH --oversubscribe")
        if self.partition:
            lines.append(f"#SBATCH --partition={self.partition}")
        if self.qos:
            lines.append(f"#SBATCH --qos={self.qos}")
        if self.nodelist:
            lines.append(f"#SBATCH --nodelist={self.nodelist}")
        if self.time_limit:
            lines.append(f"#SBATCH --time={self.time_limit}") 
        
        # --- Custom Options ---
        if self.optional_sbatch:
            lines.append(self.optional_sbatch)

        lines.append("")  # Blank line before commands

        if self.discord_notifications:
            from models.settings_model import SettingsModel
            settings = SettingsModel()
            webhook_url = settings._notification_settings.get('discord_webhook_url')
            if settings._notification_settings.get('discord_enabled') and webhook_url:
                lines.append("# --- Discord Notifications (Improved) ---")
                lines.append(f'DISCORD_WEBHOOK_URL="{webhook_url}"')
                
                # Improved Discord notification script
                discord_script = '''
# Global variables for better state tracking
CANCELLED=0
NOTIFICATION_SENT=0
NOTIFICATION_LOG="/tmp/slurm_notification_${SLURM_JOB_ID}.log"

# Improved notification function with better error handling
send_discord_notification() {
    local status_message="$1"
    local color_code="$2"
    local exit_code_info="$3"
    
    # Prevent duplicate notifications
    if [ "$NOTIFICATION_SENT" -eq 1 ] && [ "$status_message" != "🚀 STARTED" ]; then
        return 0
    fi
    
    local job_name="${SLURM_JOB_NAME:-unknown}"
    local job_id="${SLURM_JOB_ID:-unknown}"
    local timestamp=$(date --iso-8601=seconds 2>/dev/null || date)
    local exit_field=""
    
    if [ ! -z "$exit_code_info" ]; then
        exit_field=",{\"name\": \"Exit Code\", \"value\": \"$exit_code_info\", \"inline\": true}"
    fi

    # Create JSON payload with better escaping
    local json_payload
    json_payload=$(cat <<EOF
{
    "embeds": [{
        "title": "Job Status: $status_message",
        "color": $color_code,
        "fields": [
            {"name": "Job Name", "value": "$job_name", "inline": true},
            {"name": "Job ID", "value": "$job_id", "inline": true}$exit_field
        ],
        "timestamp": "$timestamp",
        "footer": {"text": "SlurmAIO"}
    }]
}
EOF
)

    # Send notification with better error handling and timeout
    local curl_output
    curl_output=$(curl -H "Content-Type: application/json" \
                      -X POST \
                      -d "$json_payload" \
                      "$DISCORD_WEBHOOK_URL" \
                      --max-time 30 \
                      --retry 3 \
                      --retry-delay 5 \
                      --silent \
                      --show-error 2>&1)
    
    local curl_exit_code=$?
    
    # Log the notification attempt
    echo "[$(date)] Status: $status_message, Curl exit: $curl_exit_code" >> "$NOTIFICATION_LOG"
    
    if [ $curl_exit_code -eq 0 ]; then
        echo "[$(date)] Discord notification sent successfully: $status_message" >> "$NOTIFICATION_LOG"
        if [ "$status_message" != "🚀 STARTED" ]; then
            NOTIFICATION_SENT=1
        fi
    else
        echo "[$(date)] Failed to send Discord notification: $curl_output" >> "$NOTIFICATION_LOG"
    fi
    
    return $curl_exit_code
}

# Improved signal handlers
handle_cancel() {
    echo "[$(date)] Received SIGTERM - job being cancelled/timed out" >> "$NOTIFICATION_LOG"
    CANCELLED=1
    
    # Send cancellation notification immediately (foreground)
    send_discord_notification "🛑 CANCELLED / TIMEOUT" "8421504"
    
    # Wait briefly to ensure notification is sent
    sleep 2
    
    # Exit with appropriate code
    exit 143  # 128 + 15 (SIGTERM)
}

handle_exit() {
    local exit_code=$?
    echo "[$(date)] Script exiting with code: $exit_code, CANCELLED: $CANCELLED" >> "$NOTIFICATION_LOG"
    
    # Don't send completion notification if already cancelled
    if [ "$CANCELLED" -eq 1 ]; then
        echo "[$(date)] Skipping completion notification - job was cancelled" >> "$NOTIFICATION_LOG"
        exit $exit_code
    fi
    
    # Send appropriate completion notification
    if [ $exit_code -eq 0 ]; then
        send_discord_notification "✅ COMPLETED" "65280"
    else
        send_discord_notification "❌ FAILED" "16711680" "$exit_code"
    fi
    
    # Brief wait to ensure notification is sent
    sleep 2
    
    exit $exit_code
}

# Set up signal traps - improved order and handling
trap handle_cancel SIGTERM SIGINT
trap handle_exit EXIT

# Send start notification
send_discord_notification "🚀 STARTED" "3447003"

# Add a small delay to ensure start notification is sent
sleep 1
'''
                lines.append(discord_script)

        lines.append("# --- Your commands start here ---")

        # Add setup for virtual environment if specified
        if self.venv:
            lines.append(f"source {self.venv}/bin/activate")
            lines.append("")

        # Wrap user commands with better signal handling if discord notifications are enabled
        if self.discord_notifications:
            lines.append("# Execute user commands with proper signal propagation")
            lines.append("(")
            lines.append("  # User commands in subshell for better signal handling")
            lines.append(f"  {self.script_commands}")
            lines.append(") &")
            lines.append("USER_CMD_PID=$!")
            lines.append("")
            lines.append("# Wait for user commands to complete")
            lines.append("wait $USER_CMD_PID")
            lines.append("USER_EXIT_CODE=$?")
            lines.append("")
            lines.append("# Exit with the same code as user commands")
            lines.append("exit $USER_EXIT_CODE")
        else:
            lines.append(self.script_commands)

        # Join lines with the appropriate separator for the OS
        return "\n".join(lines)

    def to_table_row(self):
        return [ self.id, self.name, self.status, self.elapsed, self.cpus_per_task,self.mem, self.gpus if self.gpus != None else "0"]

# Rest of your classes remain the same...
@dataclass
class Project:
    """Data structure for a project, containing a name and a list of jobs."""

    name: str
    jobs: List[Job] = field(default_factory=list)
    cached_job: Optional[Job] = None

    def to_dict(self):
        """Converts the Project object to a dictionary for JSON serialization."""
        return {
            "name": self.name,
            "jobs": [job.to_dict() for job in self.jobs],
            "cached_job": self.cached_job.to_dict() if self.cached_job else None
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Creates a Project instance from a dictionary."""
        jobs = [Job.from_dict(job_data) for job_data in data.get("jobs", [])]
        cached_job_data = data.get("cached_job")
        cached_job = Job.from_dict(cached_job_data) if cached_job_data else None
        return cls(name=data["name"], jobs=jobs, cached_job=cached_job)

    def get_job_stats(self) -> dict:
        """Counts the number of jobs in each status category."""
        stats = {
            "COMPLETED": 0,
            "FAILED": 0,
            "PENDING": 0,
            "RUNNING": 0,
            "CANCELLED": 0,
            "NOT_SUBMITTED": 0,
        }
        for job in self.jobs:
            if job.status in stats:
                stats[job.status] += 1
        return stats

class ProjectStorer:
    """Handles saving and loading of projects to/from a remote JSON file."""
    REMOTE_PROJECTS_DIR = ".slurm_gui"
    REMOTE_PROJECTS_FILENAME = "projects.json"

    def __init__(self):
        self.remote_file_path = None

    def _get_remote_path(self):
        from core.slurm_api import SlurmAPI
        slurm_api = SlurmAPI()
        if not self.remote_file_path:
            if not slurm_api.remote_home:
                slurm_api.remote_home = slurm_api.get_home_directory()
            if slurm_api.remote_home:
                remote_dir = f"{slurm_api.remote_home}/{self.REMOTE_PROJECTS_DIR}"
                self.remote_file_path = f"{remote_dir}/{self.REMOTE_PROJECTS_FILENAME}"
        return self.remote_file_path

    def save(self, projects: List[Project]):
        from core.slurm_api import ConnectionState, SlurmAPI
        slurm_api = SlurmAPI()
        if slurm_api.connection_status != ConnectionState.CONNECTED:
            return

        remote_path = self._get_remote_path()
        if not remote_path:
            return

        try:
            projects_data = [p.to_dict() for p in projects]
            json_data = json.dumps(projects_data, indent=4)
            
            remote_dir = os.path.dirname(remote_path)
            slurm_api.create_remote_directory(remote_dir)
            slurm_api.write_remote_file(remote_path, json_data)
        except Exception as e:
            show_error_toast(None, "Save Failed", f"Could not save projects: {e}")

    def load(self) -> List[Project]:
        from core.slurm_api import ConnectionState, SlurmAPI
        slurm_api = SlurmAPI()
        if slurm_api.connection_status != ConnectionState.CONNECTED:
            return []

        remote_path = self._get_remote_path()
        if not remote_path:
            return []
            
        content, err = slurm_api.read_remote_file(remote_path)
        if err or not content:
            return []

        try:
            projects_data = json.loads(content)
            return [Project.from_dict(p_data) for p_data in projects_data]
        except (json.JSONDecodeError, TypeError):
            return []

class JobsModel:
    """Model to manage projects and jobs."""

    def __init__(self):
        self.projects: List[Project] = []
        self.active_project: Optional[Project] = None
        self.event_bus = get_event_bus()
        self._is_loading = False
        self.project_storer = ProjectStorer()
        self._event_bus_subscription()

    def _event_bus_subscription(self):
        self.event_bus.subscribe(Events.ADD_JOB, self.add_job_to_active_project)
        # The controller will now handle triggering the load on connection.

    def save_to_remote(self):
        """Saves the current project list to the remote server."""
        if not self._is_loading:
            self.project_storer.save(self.projects)

    def load_from_remote(self):
        """Loads projects from the remote server and updates the model."""
        self._is_loading = True
        self.projects = self.project_storer.load()
        self.event_bus.emit(Events.PROJECT_LIST_CHANGED, data={"projects": self.projects})
        self._is_loading = False
        show_success_toast(None, "Projects Loaded", "Loaded projects from remote.", duration=2000)

    def add_project(self, event: Dict):
        """Adds a new project and emits an event."""
        name = event.data["project_name"]
        if name and not any(p.name == name for p in self.projects):
            new_project = Project(name=name)
            self.projects.append(new_project)
            self.event_bus.emit(
                Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
            )
            self.save_to_remote()
        else:
            show_error_toast(None, "Error", "Project already exist")

    def remove_project(self, name: str):
        """Removes a project and emits an event."""
        project_to_remove = next((p for p in self.projects if p.name == name), None)
        if project_to_remove:
            self.projects.remove(project_to_remove)
            self.event_bus.emit(
                Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
            )
            self.save_to_remote()

    def set_active_project(self, name: str):
        """Sets the currently active project and emits an event."""
        self.active_project = next((p for p in self.projects if p.name == name), None)

    def add_job_to_active_project(self, event: Dict):  # New method to add a job
        """Adds a new job to the active project and emits an event."""
        project_name = event.data["project_name"]
        job_to_add = event.data["job_data"]

        project = next((p for p in self.projects if p.name == project_name), None)
        if project:
            job_to_add.project_name = project.name
            project.jobs.append(job_to_add)
            project.cached_job = copy.deepcopy(job_to_add)
            project.cached_job.id = None
            project.cached_job.status = "NOT_SUBMITTED"
            project.cached_job.dependency = None
            self.event_bus.emit(
                Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
            )
            self.save_to_remote()
        else:
            show_error_toast(None, "Error", f"Project '{project_name}' not found.")
    
    def get_job_by_id(self, project_name: str, job_id: str) -> Optional[Job]:
        """Retrieves a job by its ID from a specific project."""
        project = next((p for p in self.projects if p.name == project_name), None)
        if project:
            for job in project.jobs:
                if job.id == job_id:
                    return job
        return None

    def update_job_in_project(self, project_name: str, job_id: str, modified_job_data: Job):
        """Updates a job in the specified project."""
        project = next((p for p in self.projects if p.name == project_name), None)
        if project:
            for i, job in enumerate(project.jobs):
                if job.id == job_id:
                    project.jobs[i] = modified_job_data
                    project.cached_job = copy.deepcopy(modified_job_data)
                    project.cached_job.id = None
                    project.cached_job.status = "NOT_SUBMITTED"
                    project.cached_job.dependency = None
                    self.event_bus.emit(
                        Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
                    )
                    self.save_to_remote()
                    break
    
    def duplicate_job(self, project_name: str, job_id: str):
        """Finds a job, creates a duplicate, and adds it to the project."""
        original_job = self.get_job_by_id(project_name, job_id)
        project = next((p for p in self.projects if p.name == project_name), None)

        if original_job and project:
            # Create a deep copy to avoid shared references
            new_job = copy.deepcopy(original_job)

            # Modify the new job
            new_job.id = uuid.uuid4().hex[:8].upper()
            new_job.name = f"{original_job.name}_copy"
            new_job.status = "NOT_SUBMITTED"
            new_job.dependency = None  # Clear dependencies

            # Add the duplicated job to the project
            project.jobs.append(new_job)

            # Emit event to update the UI
            self.event_bus.emit(
                Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
            )
            self.save_to_remote()
            show_success_toast(None, "Job Duplicated", f"Created a copy of '{original_job.name}'.", duration=1000)
        else:
            show_error_toast(None, "Error", "Could not find the job or project to duplicate.")
    
    def update_job_after_submission(self, project_name: str, temp_job_id: str, new_slurm_id: str):
        """Updates a job's ID and status after successful submission."""
        project = next((p for p in self.projects if p.name == project_name), None)
        if project:
            job_to_update = self.get_job_by_id(project_name, temp_job_id)
            if job_to_update:
                job_to_update.id = new_slurm_id
                job_to_update.status = "PENDING"
                self.event_bus.emit(
                    Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
                )
                self.save_to_remote()
              
    def remove_job_from_project(self, project_name: str, job_id: str):
        """Removes a job from a specific project."""
        project = next((p for p in self.projects if p.name == project_name), None)
        if project:
            job_to_remove = next((j for j in project.jobs if j.id == job_id), None)
            if job_to_remove:
                project.jobs.remove(job_to_remove)
                self.event_bus.emit(
                    Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
                )
                self.save_to_remote()

    def get_active_job_ids(self) -> List[str]:
        """Scans all projects and returns a list of job IDs that are in an active state."""
        active_ids = []
        inactive_states = {"NOT_SUBMITTED", "COMPLETED", "FAILED", "CANCELLED", "STOPPED", "TIMEOUT"}
        for project in self.projects:
            for job in project.jobs:
                if job.id and job.id.isdigit() and job.status.upper() not in inactive_states:
                    active_ids.append(job.id)
        return list(set(active_ids))

    def update_jobs_from_sacct(self, job_updates: List[Dict[str, Any]]):
        """Updates job statuses and details from a list of sacct query results."""
        updated = False
        for update in job_updates:
            job_id = update.get("JobID")
            if not job_id:
                continue
            
            found_job = None
            for project in self.projects:
                job = self.get_job_by_id(project.name, job_id)
                if job:
                    found_job = job
                    break
            
            if found_job:
                new_status = update.get("State", found_job.status).upper()
                new_elapsed = update.get("Elapsed", found_job.elapsed)

                if found_job.status != new_status or found_job.elapsed != new_elapsed:
                    found_job.status = new_status
                    found_job.elapsed = new_elapsed
                    updated = True

        if updated:
            self.event_bus.emit(
                Events.PROJECT_LIST_CHANGED, data={"projects": self.projects}
            )
            self.save_to_remote()