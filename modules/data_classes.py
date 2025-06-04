from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import json

from utils import determine_job_status



@dataclass

class Job:

    # Core identification
    id: Union[int, str]  # SLURM job ID
    name: str  # Job name
    status: str = "PENDING"  # SLURM job status
    command: str = ""  # The job command/script

    # === RESOURCE ALLOCATION PARAMETERS ===
    # Basic resources
    partition: str = ""  # SLURM partition
    account: str = ""  # SLURM account
    time_limit: str = ""  # Time limit in HH:MM:SS format
    nodes: int = 1  # Number of nodes
    cpus: int = 1  # CPUs per task
    ntasks: int = 1  # Number of tasks
    ntasks_per_node: Optional[int] = None  # Tasks per node
    ntasks_per_core: Optional[int] = None  # Tasks per core
    ntasks_per_socket: Optional[int] = None  # Tasks per socket

    # Memory
    memory: str = ""  # Memory requirement (e.g., "8G")
    memory_per_cpu: Optional[str] = None  # Memory per CPU
    memory_per_gpu: Optional[str] = None  # Memory per GPU
    memory_per_node: Optional[str] = None  # Memory per node

    # GPUs and other resources
    gpus: int = 0  # Number of GPUs
    gres: Optional[str] = None  # Generic Resources string

    # === CONSTRAINTS AND QOS ===
    constraints: Optional[str] = None  # Node constraints
    qos: Optional[str] = None  # Quality of Service
    reservation: Optional[str] = None  # Reservation name

    # === JOB PLACEMENT ===
    nodelist: str = ""  # Specific nodes to use/avoid
    exclude: Optional[str] = None  # Nodes to exclude

    # === JOB TIMING AND DEPENDENCIES ===
    time_used: Optional[timedelta] = None  # Time used so far
    begin_time: Optional[str] = None  # When job should begin
    deadline: Optional[str] = None  # Job deadline
    dependency: Optional[str] = None  # Job dependency specification

    # === JOB ARRAYS ===
    array_spec: Optional[str] = None  # Job array specification
    array_max_jobs: Optional[int] = None  # Maximum concurrent array jobs

    # === INPUT/OUTPUT FILES ===
    output_file: str = ""  # Path for job output
    error_file: str = ""  # Path for job errors
    input_file: Optional[str] = None  # Input file
    working_dir: str = ""  # Working directory

    # === JOB CONTROL ===
    priority: int = 0  # Job priority
    nice: Optional[int] = None  # Nice value
    requeue: Optional[bool] = None  # Allow requeue
    no_requeue: Optional[bool] = None  # Prevent requeue
    reboot: Optional[bool] = None  # Reboot nodes before job

    # === NOTIFICATIONS ===
    mail_type: Optional[str] = None  # Email notification types
    mail_user: Optional[str] = None  # Email address

    # === ENVIRONMENT ===
    export_env: Optional[str] = None  # Environment export settings
    get_user_env: Optional[bool] = None  # Load user environment

    # === ADVANCED FEATURES ===
    exclusive: Optional[bool] = None  # Exclusive node access
    overcommit: Optional[bool] = None  # Allow overcommit
    oversubscribe: Optional[bool] = None  # Allow oversubscribe
    threads_per_core: Optional[int] = None  # Threads per core
    sockets_per_node: Optional[int] = None  # Sockets per node
    cores_per_socket: Optional[int] = None  # Cores per socket

    # Job control flags
    wait: Optional[bool] = None  # Wait for job completion
    wrap: Optional[str] = None  # Wrap command

    # === STATUS AND TIMING ===
    submission_time: Optional[datetime] = None  # When job was submitted
    start_time: Optional[datetime] = None  # When job started running
    end_time: Optional[datetime] = None  # When job completed/failed
    reason: str = ""  # Status reason


    # === VIRTUAL ENVIRONMENT ===
    virtual_env: Optional[str] = None  # Path to Python virtual environment (venv)

    # === EXTENSIBLE INFO ===
    info: Dict[str, Any] = field(
        default_factory=dict)  # Additional information

    # .................................................................

    def generate_sbatch_script(self,
                               include_shebang: bool = True,
                               include_discord: bool = False,
                               discord_settings: Optional[Dict[str, Any]] = None) -> str:
        """
        Dynamically generate a complete SLURM sbatch script from job parameters.

        Args:
            include_shebang: Whether to include #!/bin/bash shebang
            include_discord: Whether to include Discord notification system
            discord_settings: Discord configuration if include_discord is True

        Returns:
            str: Complete sbatch script content
        """
        script_lines = []

        # Shebang
        if include_shebang:
            script_lines.append("#!/bin/bash")
            script_lines.append("")

        # Header comment
        script_lines.extend([
            "# ============================================",
            f"# SLURM Job Script: {self.name}",
            f"# Generated automatically by SlurmAIO",
            f"# Job ID: {self.id}",
            f"# Creation Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "# ============================================",
            ""
        ])

        # === CORE JOB PARAMETERS ===
        script_lines.append("# === Core Job Configuration ===")
        script_lines.append(f'#SBATCH --job-name="{self.name}"')

        if self.partition:
            script_lines.append(
                f"#SBATCH --partition={self.partition.replace('*', '')}")

        if self.account:
            script_lines.append(f"#SBATCH --account={self.account}")

        if self.time_limit:
            script_lines.append(f"#SBATCH --time={self.time_limit}")

        # === RESOURCE ALLOCATION ===
        script_lines.append("")
        script_lines.append("# === Resource Allocation ===")

        if self.nodes > 1:
            script_lines.append(f"#SBATCH --nodes={self.nodes}")

        if self.ntasks > 1:
            script_lines.append(f"#SBATCH --ntasks={self.ntasks}")

        if self.cpus > 1:
            script_lines.append(f"#SBATCH --cpus-per-task={self.cpus}")

        if self.ntasks_per_node:
            script_lines.append(
                f"#SBATCH --ntasks-per-node={self.ntasks_per_node}")

        if self.ntasks_per_core:
            script_lines.append(
                f"#SBATCH --ntasks-per-core={self.ntasks_per_core}")

        if self.ntasks_per_socket:
            script_lines.append(
                f"#SBATCH --ntasks-per-socket={self.ntasks_per_socket}")

        # Memory allocation
        if self.memory:
            script_lines.append(f"#SBATCH --mem={self.memory}")
        elif self.memory_per_cpu:
            script_lines.append(f"#SBATCH --mem-per-cpu={self.memory_per_cpu}")
        elif self.memory_per_gpu:
            script_lines.append(f"#SBATCH --mem-per-gpu={self.memory_per_gpu}")
        elif self.memory_per_node:
            script_lines.append(
                f"#SBATCH --mem-per-node={self.memory_per_node}")

        # === ADVANCED RESOURCES ===
        if self.gres:
            script_lines.append(f"#SBATCH --gres={self.gres}")

        if self.constraints and "None" not in str(self.constraints):
            script_lines.append(f"#SBATCH --constraint={self.constraints}")

        if self.qos:
            script_lines.append(f"#SBATCH --qos={self.qos}")

        if self.reservation:
            script_lines.append(f"#SBATCH --reservation={self.reservation}")

        # === JOB PLACEMENT ===
        if self.nodelist and self.nodelist not in ["", "None"]:
            script_lines.append(f"#SBATCH --nodelist={self.nodelist}")

        if self.exclude:
            script_lines.append(f"#SBATCH --exclude={self.exclude}")

        # === TIMING AND DEPENDENCIES ===
        if self.begin_time:
            script_lines.append(f"#SBATCH --begin={self.begin_time}")

        if self.deadline:
            script_lines.append(f"#SBATCH --deadline={self.deadline}")

        if self.dependency:
            script_lines.append(f"#SBATCH --dependency={self.dependency}")

        # === JOB ARRAYS ===
        if self.array_spec:
            array_line = f"#SBATCH --array={self.array_spec}"
            if self.array_max_jobs:
                array_line += f"%{self.array_max_jobs}"
            script_lines.append(array_line)

        # === INPUT/OUTPUT ===
        script_lines.append("")
        script_lines.append("# === Input/Output Configuration ===")

        if self.output_file:
            script_lines.append(
                f"#SBATCH --output={self._normalize_path(self.output_file)}")
        else:
            script_lines.append("#SBATCH --output=slurm-%j.out")

        if self.error_file:
            script_lines.append(
                f"#SBATCH --error={self._normalize_path(self.error_file)}")
        else:
            script_lines.append("#SBATCH --error=slurm-%j.err")

        if self.input_file:
            script_lines.append(
                f"#SBATCH --input={self._normalize_path(self.input_file)}")

        # === JOB CONTROL ===
        if self.nice is not None:
            script_lines.append(f"#SBATCH --nice={self.nice}")

        if self.requeue is True:
            script_lines.append("#SBATCH --requeue")
        elif self.no_requeue is True:
            script_lines.append("#SBATCH --no-requeue")

        if self.reboot is True:
            script_lines.append("#SBATCH --reboot")

        if self.exclusive is True:
            script_lines.append("#SBATCH --exclusive")

        if self.overcommit is True:
            script_lines.append("#SBATCH --overcommit")

        if self.oversubscribe is True:
            script_lines.append("#SBATCH --oversubscribe")

        # === ADVANCED HARDWARE ===
        if self.threads_per_core:
            script_lines.append(
                f"#SBATCH --threads-per-core={self.threads_per_core}")

        if self.sockets_per_node:
            script_lines.append(
                f"#SBATCH --sockets-per-node={self.sockets_per_node}")

        if self.cores_per_socket:
            script_lines.append(
                f"#SBATCH --cores-per-socket={self.cores_per_socket}")

        # === NOTIFICATIONS ===
        if self.mail_type:
            script_lines.append(f"#SBATCH --mail-type={self.mail_type}")

        if self.mail_user:
            script_lines.append(f"#SBATCH --mail-user={self.mail_user}")

        # === ENVIRONMENT ===
        if self.export_env:
            script_lines.append(f"#SBATCH --export={self.export_env}")

        if self.get_user_env is True:
            script_lines.append("#SBATCH --get-user-env")

        # === JOB CONTROL FLAGS ===
        if self.wait is True:
            script_lines.append("#SBATCH --wait")

        if self.wrap:
            script_lines.append(f"#SBATCH --wrap='{self.wrap}'")
            return "\n".join(script_lines)  # Return early for wrapped commands

        # === DISCORD NOTIFICATION SYSTEM ===
        if include_discord and discord_settings and discord_settings.get("enabled", False):
            script_lines.extend(
                self._get_discord_notification_script(discord_settings))

        # === JOB EXECUTION SECTION ===
        script_lines.extend([
            "",
            "# ============================================",
            "# Job Execution",
            "# ============================================",
            "",
            "# Record start time for duration calculation",
            "SECONDS=0",
            "",
            f"echo \"Starting job '{self.name}' at $(date)\"",
            "echo \"Job ID: $SLURM_JOB_ID\"",
            "echo \"Node(s): $SLURM_NODELIST\"",
            "echo \"Working Directory: $(pwd)\"",
            "echo \"\"",
            ""
        ])


        # Change working directory if specified
        if self.working_dir:
            script_lines.extend([
                "# Change to working directory",
                f"cd '{self.working_dir}' || {{ echo \"Failed to change to directory: {self.working_dir}\"; exit 1; }}",
                "echo \"Changed to working directory: $(pwd)\"",
                ""
            ])

        # Activate virtual environment if specified
        if self.virtual_env:
            script_lines.extend([
                f"# Activate Python virtual environment",
                f"if [ -f '{self.virtual_env}/bin/activate' ]; then",
                f"    source '{self.virtual_env}/bin/activate'",
                f"    echo 'Activated virtual environment: {self.virtual_env}'",
                f"else",
                f"    echo 'Warning: Virtual environment not found at {self.virtual_env}/bin/activate'",
                f"fi",
                ""
            ])

        # Array job information
        if self.array_spec:
            script_lines.extend([
                "# Job array information",
                "if [ ! -z \"$SLURM_ARRAY_TASK_ID\" ]; then",
                "    echo \"Job Array ID: $SLURM_ARRAY_JOB_ID\"",
                "    echo \"Array Task ID: $SLURM_ARRAY_TASK_ID\"",
                "    echo \"Array Task Count: $SLURM_ARRAY_TASK_COUNT\"",
                "fi",
                ""
            ])

        # Discord start notification
        if include_discord and discord_settings and discord_settings.get("notify_start", True):
            script_lines.extend([
                "# Send job start notification",
                "send_job_start_notification",
                ""
            ])

        # Main command execution
        script_lines.extend([
            "# Your job command starts here",
            "echo \"Executing main job command...\"",
            "echo \"Command: " + self.command.replace('"', '\\"') + "\"",
            "echo \"\"",
            "",
            self.command if self.command else "echo \"No command specified\"",
            "",
            "# Capture the exit code immediately after job execution",
            "JOB_EXIT_CODE=$?",
            "",
            "echo \"\"",
            "echo \"Job finished at $(date)\"",
            "echo \"Exit code: $JOB_EXIT_CODE\"",
            "echo \"Runtime: $(printf '%02d:%02d:%02d' $((SECONDS/3600)) $(((SECONDS%3600)/60)) $((SECONDS%60)))\""
        ])

        # Discord completion notification
        if include_discord and discord_settings and discord_settings.get("notify_complete", True):
            script_lines.extend([
                "",
                "# Send completion notification based on exit code",
                "send_job_completion_notification $JOB_EXIT_CODE"
            ])

        # Final exit
        script_lines.extend([
            "",
            "# Exit with the original job exit code",
            "exit $JOB_EXIT_CODE"
        ])

        return "\n".join(script_lines)

    def _normalize_path(self, path: str, home_dir: str = "") -> str:
        """Normalize file paths - if relative, prepend home directory"""
        if not path or path.startswith('/'):
            return path

        if home_dir:
            return f"{home_dir}/{path}"
        else:
            return f"$HOME/{path}"

    def _get_discord_notification_script(self, discord_settings: Dict[str, Any]) -> List[str]:
        """Generate Discord notification script section"""
        # This would contain the Discord webhook notification system
        # Implementation details from the original _create_job_script method
        webhook_url = discord_settings.get('discord_webhook_url') or discord_settings.get('webhook_url', '')
        if not webhook_url:
            return [] 
        return [
            "",
            "# =============================================================================",
            "# Enhanced Discord Notification System",
            "# =============================================================================",
            "",
            "# Discord webhook configuration",
            f"DISCORD_WEBHOOK_URL=\"{webhook_url}\"",
            "",
            "# Job information variables",
            f'export JOB_NAME="{self.name}"',
            f'export PARTITION="{self.partition}"',
            f'export TIME_LIMIT="{self.time_limit}"',
            f'export REQUESTED_MEMORY="{self.memory}"',
            f'export REQUESTED_CPUS="{self.cpus}"',
            f'export REQUESTED_NODES="{self.nodes}"',
            "",
            "# Enhanced Discord notification functions",
            self._get_discord_functions(),
            "",
            "# Set up signal handlers for job cancellation",
            "trap 'send_job_cancelled_notification; exit 130' INT TERM",
            ""
        ]
    
    def _get_discord_functions(self) -> str:
        """Get Discord notification functions"""
        # Return the bash functions as a properly unindented string for sbatch script
        return '''
function send_enhanced_discord_notification {
    local title="$1"
    local description="$2"
    local color="$3"
    local thumbnail_url="$4"
    local footer_text="$5"
    
    # Get current timestamp in ISO format
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
    
    # Export parameters as environment variables for Python script
    export DISCORD_TITLE="$title"
    export DISCORD_DESCRIPTION="$description"
    export DISCORD_COLOR="$color"
    export DISCORD_THUMBNAIL="$thumbnail_url"
    export DISCORD_FOOTER="$footer_text"
    export DISCORD_TIMESTAMP="$timestamp"
    
    # Build the enhanced embed payload
    local embed_payload=$(python3 <<'EOF'
import json, os

# Get parameters from environment variables
title = os.environ.get("DISCORD_TITLE", "SLURM Job Update")
description = os.environ.get("DISCORD_DESCRIPTION", "")
color = int(os.environ.get("DISCORD_COLOR", "3447003"))
thumbnail_url = os.environ.get("DISCORD_THUMBNAIL", "")
footer_text = os.environ.get("DISCORD_FOOTER", "SlurmAIO Job Monitor")
timestamp = os.environ.get("DISCORD_TIMESTAMP", "")

# Get environment variables
job_id = os.environ.get("SLURM_JOB_ID", "Unknown")
job_name = os.environ.get("JOB_NAME", "Unknown")
node = os.environ.get("SLURM_NODELIST", "Unknown")
partition = os.environ.get("PARTITION", "Unknown")
time_limit = os.environ.get("TIME_LIMIT", "Unknown")
memory = os.environ.get("REQUESTED_MEMORY", "Unknown")
cpus = os.environ.get("REQUESTED_CPUS", "Unknown")
nodes = os.environ.get("REQUESTED_NODES", "Unknown")
hostname = os.environ.get("HOSTNAME", "Unknown")
start_time = os.environ.get("START_TIME", "Unknown")
account = os.environ.get("SLURM_JOB_ACCOUNT", "Unknown")

# Build rich embed
embed = {
    "username": "SlurmAIO",
    "embeds": [{
        "title": title,
        "description": description,
        "color": color,
        "timestamp": timestamp,
        "fields": [
            {
                "name": "🎯 Job Details",
                "value": "**ID:** `" + job_id + "`\\n**Name:** `" + job_name + "`\\n**Partition:** `" + partition + "`",
                "inline": True
            },
            {
                "name": "💻 Resources", 
                "value": "**CPUs:** " + cpus + "\\n**Memory:** " + memory + "\\n**Nodes:** " + nodes,
                "inline": True
            },
            {
                "name": "📍 Location",
                "value": "**Cluster:** `" + hostname + "`\\n**Node(s):** `" + node + "`\\n**Account:** `" + account + "`",
                "inline": True
            },
            {
                "name": "⏱️ Timing",
                "value": "**Time Limit:** " + time_limit + "\\n**Started:** " + start_time,
                "inline": False
            }
        ],
        "footer": {
            "text": footer_text + " • SlurmAIO",
            "icon_url": "https://cdn-icons-png.flaticon.com/512/2103/2103633.png"
        },
        "author": {
            "name": "SlurmAIO", 
            "icon_url": "https://cdn-icons-png.flaticon.com/512/9131/9131529.png"
        }
    }]
}

if thumbnail_url:
    embed["embeds"][0]["thumbnail"] = {"url": thumbnail_url}

print(json.dumps(embed))
EOF
    )
    
    local curl_response=$(curl -H "Content-Type: application/json" \
        -X POST \
        -d "$embed_payload" \
        "$DISCORD_WEBHOOK_URL" \
        -w "%{http_code}" \
        --silent --show-error 2>&1)
    
    if [[ "$curl_response" == *"204"* ]]; then
        echo "Discord notification sent successfully"
    else
        echo "Failed to send Discord notification: $curl_response"
    fi
}

function send_job_start_notification {
    export DISCORD_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
    
    local description=""
    
    send_enhanced_discord_notification \
        "🏃‍♂️ JOB STARTED: $JOB_NAME" \
        "$description" \
        "3447003" \
        "https://cdn-icons-png.flaticon.com/512/2103/2103591.png" \
        "Started at $(date '+%H:%M:%S')"
}

function send_job_completion_notification {
    local exit_code=$1
    local end_time=$(date '+%Y-%m-%d %H:%M:%S')
    local duration=$((SECONDS))
    local duration_formatted=$(printf '%02d:%02d:%02d' $((duration/3600)) $(((duration%3600)/60)) $((duration%60)))
    
    export DISCORD_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
    
    if [ $exit_code -eq 0 ]; then
        local description ="**Final Status:** Completed Successfully\n"
        description+="⏱️ **Total Runtime:** $duration_formatted\n" 
        description+="🏁 **Finished At:** $end_time\n\n"
        
        send_enhanced_discord_notification \
            "✅ JOB COMPLETED: $JOB_NAME" \
            "$description" \
            "5763719" \
            "https://cdn-icons-png.flaticon.com/512/190/190411.png" \
            "SUCCESS: Completed in $duration_formatted"
    else
        description+="💥 Your SLURM job **$JOB_NAME** encountered an error during execution.\n\n"
        description+="📊 **Final Status:** Failed\n"
        description+="🚨 **Exit Code:** $exit_code\n"
        
        send_enhanced_discord_notification \
            "❌ JOB FAILED: $JOB_NAME" \
            "$description" \
            "15158332" \
            "https://cdn-icons-png.flaticon.com/512/564/564619.png" \
            "FAILED: Exit code $exit_code after $duration_formatted"
    fi
}

function send_job_cancelled_notification {
    local cancel_time=$(date '+%Y-%m-%d %H:%M:%S')
    local duration=$((SECONDS))
    local duration_formatted=$(printf '%02d:%02d:%02d' $((duration/3600)) $(((duration%3600)/60)) $((duration%60)))
    
    export DISCORD_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
    
    description+="⚠️ Your SLURM job **$JOB_NAME** was cancelled before completion.\n\n"
    description+="📊 **Final Status:** Cancelled\n"
    description+="🛑 **Cancelled At:** $cancel_time\n\n"
    description+="🤔 **Possible Reasons:** Time limits, resource constraints, or manual cancellation"
    
    send_enhanced_discord_notification \
        "🛑 JOB CANCELLED: $JOB_NAME" \
        "$description" \
        "16776960" \
        "https://cdn-icons-png.flaticon.com/512/1828/1828843.png" \
        "CANCELLED: After $duration_formatted"
}
'''
    
    def save_sbatch_script(self,
                           filepath: Optional[str] = None,
                           include_discord: bool = False,
                           discord_settings: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate and save the sbatch script to a file.

        Args:
            filepath: Path to save the script (if None, creates a temp file)
            include_discord: Whether to include Discord notifications
            discord_settings: Discord configuration

        Returns:
            str: Path to the saved script file
        """
        script_content = self.generate_sbatch_script(
            include_discord=include_discord,
            discord_settings=discord_settings
        )

        if filepath is None:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix=f'_{self.name}.sh',
                prefix='slurm_job_',
                delete=False
            ) as f:
                f.write(script_content)
                filepath = f.name
        else:
            with open(filepath, 'w') as f:
                f.write(script_content)

        # Make script executable
        os.chmod(filepath, 0o755)
        return filepath

    def get_resource_summary(self) -> Dict[str, Any]:
        """Get a summary of requested resources"""
        return {
            "nodes": self.nodes,
            "cpus": self.cpus,
            "gpus": self.gpus,
            "memory": self.memory,
            "time_limit": self.time_limit,
            "partition": self.partition,
            "qos": self.qos,
            "array_tasks": len(self.array_spec.split(',')) if self.array_spec and ',' in self.array_spec else 1 if self.array_spec else 1
        }

    def validate_parameters(self) -> List[str]:
        """
        Validate job parameters and return list of issues found.

        Returns:
            List[str]: List of validation errors/warnings
        """
        issues = []

        # Required parameters
        if not self.name.strip():
            issues.append("Job name is required")

        if not self.command.strip() and not self.wrap:
            issues.append("Job command is required")

        # Resource validation
        if self.nodes < 1:
            issues.append("Number of nodes must be at least 1")

        if self.cpus < 1:
            issues.append("Number of CPUs must be at least 1")

        if self.ntasks < 1:
            issues.append("Number of tasks must be at least 1")

        # Memory validation
        if self.memory and not any(unit in self.memory.upper() for unit in ['K', 'M', 'G', 'T']):
            issues.append(
                "Memory specification should include unit (K, M, G, T)")

        # Time limit validation
        if self.time_limit:
            try:
                # Basic validation of time format
                parts = self.time_limit.split(':')
                if len(parts) not in [2, 3]:
                    issues.append(
                        "Time limit should be in format HH:MM:SS or MM:SS")
            except:
                issues.append("Invalid time limit format")

        # Array validation
        if self.array_spec:
            if self.array_max_jobs and self.array_max_jobs < 1:
                issues.append("Array max jobs must be at least 1")

        return issues

    def to_json(self) -> Dict[str, Any]:
        """Convert Job to JSON-serializable dictionary with proper datetime/timedelta handling"""
        d = {}

        # Handle each field explicitly to ensure JSON compatibility
        for field_name, field_value in self.__dict__.items():
            if field_value is None:
                continue  # Skip None values to keep JSON compact

            # Handle datetime objects
            if isinstance(field_value, datetime):
                d[field_name] = field_value.isoformat()
            # Handle timedelta objects
            elif isinstance(field_value, timedelta):
                d[field_name] = str(field_value)
            # Handle dictionary (info field)
            elif isinstance(field_value, dict):
                cleaned_dict = self._clean_dict_for_json(field_value)
                if cleaned_dict:
                    d[field_name] = cleaned_dict
            # Handle all other types
            else:
                try:
                    json.dumps(field_value)
                    d[field_name] = field_value
                except (TypeError, ValueError):
                    d[field_name] = str(field_value)

        return d

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "Job":
        # Make a copy to avoid modifying the input
        data_copy = data.copy()

        # Handle special types
        if "time_used" in data_copy and data_copy["time_used"]:
            try:
                parts = data_copy["time_used"].split(":")
                if len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                    data_copy["time_used"] = timedelta(
                        hours=hours, minutes=minutes, seconds=seconds)
                else:
                    data_copy["time_used"] = None
            except (ValueError, TypeError):
                data_copy["time_used"] = None

        # Handle date fields
        for date_field in ["submission_time", "start_time", "end_time"]:
            if date_field in data_copy and data_copy[date_field]:
                try:
                    data_copy[date_field] = datetime.fromisoformat(
                        data_copy[date_field])
                except (ValueError, TypeError):
                    data_copy[date_field] = None

        # Handle info dictionary
        info = data_copy.pop("info", {}) or {}

        # Create job with known fields
        known_fields = {k: v for k, v in data_copy.items()
                        if k in cls.__annotations__}
        job = cls(**known_fields)

        # Set info separately
        job.info = info

        return job

    @classmethod
    def from_slurm_dict(cls, slurm_dict: Dict[str, Any]) -> "Job":
        """Create a Job instance from a dictionary returned by SlurmConnection with proper status handling"""

        # Get the raw status and any exit code information
        raw_status = slurm_dict.get("Status", "PENDING")
        exit_code = slurm_dict.get("ExitCode")
        raw_state = slurm_dict.get("RawState", raw_status)

        # Determine refined status if we have exit code information
        if exit_code and raw_status == "COMPLETED":
            refined_status = determine_job_status(raw_state, exit_code)
        else:
            refined_status = raw_status

        job = cls(
            id=slurm_dict.get("Job ID", ""),
            name=slurm_dict.get("Job Name", ""),
            status=refined_status,  # Use refined status
            partition=slurm_dict.get("Partition", ""),
            account=slurm_dict.get("Account", ""),
            priority=slurm_dict.get("Priority", 0),
            nodelist=slurm_dict.get("Nodelist", ""),
            reason=slurm_dict.get("Reason", ""),
        )

        # Handle time fields
        if "Time Limit" in slurm_dict:
            job.time_limit = slurm_dict["Time Limit"]

        if "Time Used" in slurm_dict and isinstance(slurm_dict["Time Used"], list) and len(slurm_dict["Time Used"]) > 1:
            # Use the timedelta value
            job.time_used = slurm_dict["Time Used"][1]

        # Handle resource fields
        if "CPUs" in slurm_dict:
            job.cpus = slurm_dict["CPUs"]

        if "GPUs" in slurm_dict:
            job.gpus = slurm_dict["GPUs"]

        if "RAM" in slurm_dict:
            job.memory = slurm_dict["RAM"]

        # Store exit code and raw state for debugging
        job.info["exit_code"] = exit_code
        job.info["raw_state"] = raw_state
        job.info["raw_status"] = raw_status

        # Store the rest in info dictionary
        for k, v in slurm_dict.items():
            if k not in asdict(job):
                job.info[k] = v

        return job

    def get_runtime_str(self) -> str:
        """Return a formatted string of the job's runtime"""
        if not self.time_used:
            return "—"

        total_seconds = int(self.time_used.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def to_table_row(self) -> List[Any]:
        """
        Return a list of values for display in a table row.
        Format: [id, name, status, runtime, cpus, gpus, memory]
        """
        # Format runtime string (or use placeholder for NOT_SUBMITTED jobs)
        runtime_str = "—" if self.status == "NOT_SUBMITTED" else self.get_runtime_str()

        # Return formatted row data
        return [
            self.id,
            self.name,
            self.status,
            runtime_str,
            self.cpus,
            self.gpus,
            self.memory,
        ]

    def _clean_dict_for_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively clean a dictionary to make it JSON serializable"""
        cleaned = {}

        for key, value in data.items():
            if value is None:
                continue

            if isinstance(value, datetime):
                cleaned[key] = value.isoformat()
            elif isinstance(value, timedelta):
                cleaned[key] = str(value)
            elif isinstance(value, dict):
                nested_clean = self._clean_dict_for_json(value)
                if nested_clean:
                    cleaned[key] = nested_clean
            elif isinstance(value, (list, tuple)):
                # Handle lists/tuples that might contain non-serializable objects
                cleaned_list = []
                for item in value:
                    if isinstance(item, datetime):
                        cleaned_list.append(item.isoformat())
                    elif isinstance(item, timedelta):
                        cleaned_list.append(str(item))
                    else:
                        try:
                            json.dumps(item)
                            cleaned_list.append(item)
                        except (TypeError, ValueError):
                            cleaned_list.append(str(item))
                if cleaned_list:
                    cleaned[key] = cleaned_list
            else:
                try:
                    # Test if the value is JSON serializable
                    json.dumps(value)
                    cleaned[key] = value
                except (TypeError, ValueError):
                    # If not serializable, convert to string
                    cleaned[key] = str(value)

        return cleaned

    @staticmethod
    def create_job_from_details(job_details: Dict[str, Any]) -> 'Job':
        """
        Create an enhanced Job object from job details dictionary.
        
        Args:
            job_details: Dictionary containing job parameters
            
        Returns:
            Job: Enhanced Job object
        """
        from modules.project_store import Job  # Import here to avoid circular imports
        
        # Generate temporary ID for new jobs
        import random
        temp_id = f"NEW-{random.randint(1000, 9999)}"
        
        # Map common job details to Job class parameters
        job_params = {
            'id': temp_id,
            'name': job_details.get('job_name', ''),
            'status': 'NOT_SUBMITTED',
            'command': job_details.get('command', ''),
            'partition': job_details.get('partition', ''),
            'account': job_details.get('account', ''),
            'time_limit': job_details.get('time_limit', ''),
            'nodes': job_details.get('nodes', 1),
            'cpus': job_details.get('cpus_per_task', 1),
            'ntasks': job_details.get('ntasks', 1),
            'ntasks_per_node': job_details.get('ntasks_per_node'),
            'memory': job_details.get('memory', ''),
            'memory_per_cpu': job_details.get('memory_per_cpu'),
            'memory_per_node': job_details.get('memory_per_node'),
            'gpus': 0,  # Will be calculated from gres
            'gres': job_details.get('gres'),
            'constraints': job_details.get('constraint'),
            'qos': job_details.get('qos'),
            'reservation': job_details.get('reservation'),
            'nodelist': ','.join(job_details.get('nodelist', [])) if isinstance(job_details.get('nodelist'), list) else job_details.get('nodelist', ''),
            'exclude': job_details.get('exclude'),
            'begin_time': job_details.get('begin_time'),
            'deadline': job_details.get('deadline'),
            'dependency': job_details.get('dependency'),
            'array_spec': job_details.get('array'),
            'array_max_jobs': job_details.get('array_max_jobs'),
            'output_file': job_details.get('output_file', ''),
            'error_file': job_details.get('error_file', ''),
            'input_file': job_details.get('input_file'),
            'working_dir': job_details.get('working_dir', ''),
            'priority': job_details.get('priority', 0),
            'nice': job_details.get('nice'),
            'requeue': job_details.get('requeue'),
            'no_requeue': job_details.get('no_requeue'),
            'reboot': job_details.get('reboot'),
            'mail_type': job_details.get('mail_type'),
            'mail_user': job_details.get('mail_user'),
            'export_env': job_details.get('export_env'),
            'get_user_env': job_details.get('get_user_env'),
            'exclusive': job_details.get('exclusive'),
            'overcommit': job_details.get('overcommit'),
            'oversubscribe': job_details.get('oversubscribe'),
            'threads_per_core': job_details.get('threads_per_core'),
            'sockets_per_node': job_details.get('sockets_per_node'),
            'cores_per_socket': job_details.get('cores_per_socket'),
            'wait': job_details.get('wait'),
            'wrap': job_details.get('wrap'),
            'virtual_env': job_details.get('virtual_env'),
        }
        
        # Parse GPU count from gres if available
        if job_params['gres'] and "gpu:" in job_params['gres']:
            try:
                gpu_parts = job_params['gres'].split(":")
                if len(gpu_parts) == 2:  # Format: gpu:N
                    job_params['gpus'] = int(gpu_parts[1])
                elif len(gpu_parts) == 3:  # Format: gpu:type:N
                    job_params['gpus'] = int(gpu_parts[2])
            except (ValueError, IndexError):
                pass
        
        # Handle memory unit conversion if needed
        if 'memory_spin' in job_details and 'memory_unit' in job_details:
            memory_value = job_details.get('memory_spin', 1)
            memory_unit = job_details.get('memory_unit', 'GB')
            job_params['memory'] = f"{memory_value}{memory_unit.replace('B', '')}"
        
        # Clean None values
        job_params = {k: v for k, v in job_params.items() if v is not None}
        
        # Create Job object
        job = Job(**job_params)
        
        # Store additional info
        job.info['submission_details'] = job_details
        if 'discord_notifications' in job_details:
            job.info['discord_notifications'] = job_details['discord_notifications']
        
        return job

@dataclass
class Project:
    name: str
    jobs: List[Job] = field(default_factory=list)

    # .................................................................
    def add_job(self, job: Job) -> None:
        """Add a job to the project"""
        # Check if job already exists (by ID)
        for i, existing_job in enumerate(self.jobs):
            if existing_job.id == job.id:
                # Update existing job
                self.jobs[i] = job
                return

        # Add new job
        self.jobs.append(job)

    def get_job(self, job_id: Union[int, str]) -> Optional[Job]:
        """Get a job by ID"""
        for job in self.jobs:
            if job.id == job_id:
                return job
        return None

    def remove_job(self, job_id: Union[int, str]) -> None:
        """Remove a job by ID"""
        self.jobs = [j for j in self.jobs if j.id != job_id]

    def get_job_stats(self) -> Dict[str, int]:
        """Get counts of jobs by status with proper failed job detection"""
        stats = {
            "RUNNING": 0,
            "PENDING": 0,
            "COMPLETED": 0,
            "FAILED": 0,
            "CANCELLED": 0,
            "SUSPENDED": 0,
            "NOT_SUBMITTED": 0,
            "TOTAL": len(self.jobs)
        }

        for job in self.jobs:
            status = job.status.upper()
            if status in stats:
                stats[status] += 1
            else:
                # Handle other statuses by categorizing them
                if status in ["COMPLETING"]:
                    stats["RUNNING"] += 1
                elif status in ["PREEMPTED", "STOPPED"]:
                    stats["SUSPENDED"] += 1
                elif status in ["TIMEOUT", "NODE_FAIL", "OUT_OF_MEMORY", "BOOT_FAIL"]:
                    stats["FAILED"] += 1
                elif status in ["REVOKED", "DEADLINE"]:
                    stats["CANCELLED"] += 1
                else:
                    # Unknown status, log it for debugging
                    print(f"Unknown job status encountered: {status}")

        return stats
    # .................................................................

    def to_json(self) -> Dict[str, Any]:
        """Serialize project to JSON-compatible dictionary"""
        return {
            "name": self.name,
            "jobs": [j.to_json() for j in self.jobs],
        }

    @classmethod
    def from_json(cls, name: str, data: Dict[str, Any]) -> "Project":
        """Create Project from JSON data"""
        jobs = [Job.from_json(j) for j in data.get("jobs", [])]
        return cls(name=name, jobs=jobs)

