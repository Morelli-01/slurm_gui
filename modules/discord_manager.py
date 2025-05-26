
import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from PyQt6.QtCore import QSettings
from modules.defaults import *


class DiscordNotificationManager:
    """Centralized Discord notification manager"""

    def __init__(self):
        self.webhook_url = None
        self.enabled = False
        self._load_settings()

    def _load_settings(self) -> bool:
        """Load Discord settings from configuration"""
        try:
            settings = QSettings(
                str(Path("./configs/settings.ini")), QSettings.Format.IniFormat)
            settings.beginGroup("NotificationSettings")

            self.enabled = settings.value("discord_enabled", False, type=bool)
            self.webhook_url = settings.value(
                "discord_webhook_url", "", type=str)

            settings.endGroup()

            print(
                f"[DISCORD] Settings loaded: enabled={self.enabled}, webhook_configured={bool(self.webhook_url)}")
            return self.enabled and bool(self.webhook_url)

        except Exception as e:
            print(f"[DISCORD] Error loading settings: {e}")
            return False

    def is_configured(self) -> bool:
        """Check if Discord notifications are properly configured"""
        return self.enabled and bool(self.webhook_url)

    def send_notification(self, project_name: str, job,
                          old_status: str, new_status: str, job_settings: Dict[str, Any] = None) -> bool:
        """
        Send Discord notification for job status change

        Args:
            project_name: Name of the project
            job_id: Job ID
            job_name: Job name
            old_status: Previous job status
            new_status: New job status
            job_settings: Job-specific notification settings

        Returns:
            bool: True if notification was sent successfully
        """
        if not self.is_configured():
            print(
                f"[DISCORD] Not configured, skipping notification for job {job.id}")
            return False

        # Check if job has notifications enabled
        if job_settings and not job_settings.get("enabled", False):
            print(f"[DISCORD] Job {job.id} has notifications disabled")
            return False

        # Check if we should notify for this status change
        if not self._should_notify(old_status, new_status, job_settings):
            print(
                f"[DISCORD] Notification filtered out for {old_status} -> {new_status}")
            return False

        try:
            # payload = self._create_payload(project_name, job.id, job.name, old_status, new_status, job_settings)
            payload = self._create_discord_payload(
                project_name, job, old_status, new_status, job_settings)
            return self._send_webhook(payload)

        except Exception as e:
            print(f"[DISCORD] Error sending notification: {e}")
            return False

    def _should_notify(self, old_status: str, new_status: str, job_settings: Dict[str, Any] = None) -> bool:
        """Determine if notification should be sent based on status change"""
        # Default notification rules (simplified and reliable)
        default_notifications = {
            "PENDING": True,      # Job entered queue
            "RUNNING": True,      # Job started
            "COMPLETED": True,    # Job completed successfully
            "FAILED": True,       # Job failed
            "CANCELLED": True,    # Job was cancelled
            "TIMEOUT": True,      # Job timed out
        }

        # Use job-specific settings if available, otherwise use defaults
        if job_settings:
            notify_rules = {
                "PENDING": job_settings.get("notify_queued", True),
                "RUNNING": job_settings.get("notify_start", True),
                "COMPLETED": job_settings.get("notify_complete", True),
                "FAILED": job_settings.get("notify_failed", True),
                "CANCELLED": job_settings.get("notify_failed", True),
                "TIMEOUT": job_settings.get("notify_failed", True),
            }
        else:
            notify_rules = default_notifications

        return notify_rules.get(new_status, False)

    def _create_payload(self, project_name: str, job_id: str, job_name: str, old_status: str, new_status: str, job_settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create Discord webhook payload"""

        # Get message prefix from job settings or use default
        prefix = ""
        if job_settings:
            prefix = job_settings.get("message_prefix", f"[{project_name}]")
        else:
            prefix = f"[{project_name}]"

        # Status colors and emojis
        status_info = {
            "PENDING": {"color": 0x9b59b6, "emoji": "⏳", "title": "Job Queued"},
            "RUNNING": {"color": 0x3498db, "emoji": "🏃", "title": "Job Started"},
            "COMPLETED": {"color": 0x2ecc71, "emoji": "✅", "title": "Job Completed"},
            "FAILED": {"color": 0xe74c3c, "emoji": "❌", "title": "Job Failed"},
            "CANCELLED": {"color": 0xf39c12, "emoji": "🛑", "title": "Job Cancelled"},
            "TIMEOUT": {"color": 0xe67e22, "emoji": "⏰", "title": "Job Timed Out"},
        }

        info = status_info.get(
            new_status, {"color": 0x95a5a6, "emoji": "📋", "title": "Job Updated"})

        # Create embed
        embed = {
            "title": f"Job {job_id}: {job_name}",
            "color": info["color"],
            "timestamp": datetime.now().isoformat(),
            "fields": [
                {"name": "Project", "value": project_name, "inline": True},
                {"name": "Status", "value": new_status, "inline": True},
                {"name": "Job ID", "value": str(job_id), "inline": True},
            ],
            "footer": {"text": "SlurmAIO"}
        }

        # Add status change if it's different
        if old_status and old_status != new_status:
            embed["fields"].insert(1, {
                "name": "Status Change",
                "value": f"{old_status} → {new_status}",
                "inline": True
            })

        content = f"{info['emoji']} **{prefix} {info['title']}**"

        return {
            "content": content,
            "embeds": [embed]
        }

    def _create_discord_payload(self, project_name: str, job, old_status: str, new_status: str, discord_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Create Discord webhook payload"""
        prefix = discord_settings.get("message_prefix", "")
        title = f"{prefix} Job Status Update" if prefix else "Job Status Update"

        status_colors = {
            "RUNNING": 0x3498db, "COMPLETED": 0x2ecc71, "FAILED": 0xe74c3c,
            "CANCELLED": 0xf39c12, "TIMEOUT": 0xe67e22, "PENDING": 0x9b59b6,
        }
        color = status_colors.get(new_status, 0x95a5a6)

        status_emojis = {
            "RUNNING": "🏃", "COMPLETED": "✅", "FAILED": "❌",
            "CANCELLED": "🛑", "TIMEOUT": "⏰", "PENDING": "⏳",
        }
        emoji = status_emojis.get(new_status, "📋")

        status_desc = f"{old_status} → **{new_status}**" if old_status != new_status else f"**{new_status}**"
        runtime_str = job.get_runtime_str() if hasattr(job, 'get_runtime_str') else "—"

        embed_fields = [
            {"name": "Job Name", "value": job.name, "inline": True},
            {"name": "Project", "value": project_name, "inline": True},
            {"name": "Status", "value": status_desc, "inline": True},
            {"name": "Runtime", "value": runtime_str, "inline": True},
        ]

        if job.nodelist and job.nodelist.strip():
            embed_fields.append(
                {"name": "Node(s)", "value": job.nodelist, "inline": True})

        resources = []
        if job.cpus and job.cpus > 0:
            resources.append(f"CPUs: {job.cpus}")
        if job.gpus and job.gpus > 0:
            resources.append(f"GPUs: {job.gpus}")
        if job.memory:
            resources.append(f"Memory: {job.memory}")

        if resources:
            embed_fields.append(
                {"name": "Resources", "value": " | ".join(resources), "inline": False})

        return {
            "content": f"{emoji} **{title}**",
            "embeds": [{
                "title": f"Job {job.id}",
                "color": color,
                "fields": embed_fields,
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": "SlurmAIO Job Monitor"}
            }]
        }

    def _send_webhook(self, payload: Dict[str, Any]) -> bool:
        """Send webhook payload to Discord"""
        try:
            headers = {"Content-Type": "application/json"}

            print(f"[DISCORD] Sending notification...")
            response = requests.post(
                self.webhook_url,
                data=json.dumps(payload),
                headers=headers,
                timeout=10
            )

            if response.status_code == 204:
                print(f"[DISCORD] Notification sent successfully!")
                return True
            else:
                print(
                    f"[DISCORD] Failed with status {response.status_code}: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"[DISCORD] Network error: {e}")
            return False
        except Exception as e:
            print(f"[DISCORD] Unexpected error: {e}")
            return False


# Create singleton instance
discord_manager = DiscordNotificationManager()
