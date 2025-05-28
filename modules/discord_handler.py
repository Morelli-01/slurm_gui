"""
Discord notification handler for SlurmAIO
Handles sending formatted Discord messages for job status updates
"""

import json
from pathlib import Path
import requests
from datetime import datetime
from typing import Optional, Dict, Any
from modules.defaults import *


def initialize_discord_integration(project_store):
    """
    Initialize Discord integration with the project store
    
    Args:
        project_store: ProjectStore instance
    """
    # Get Discord settings
    settings = QSettings(str(Path("./configs/settings.ini")), QSettings.Format.IniFormat)
    settings.beginGroup("NotificationSettings")
    
    discord_enabled = settings.value("discord_enabled", False, type=bool)
    webhook_url = settings.value("discord_webhook_url", "", type=str)
    
    settings.endGroup()
    
    if discord_enabled and webhook_url.strip():
        # Set up default webhook
        discord_manager.set_default_webhook(
            webhook_url=webhook_url.strip(),
            bot_name="SlurmAIO Bot",
            avatar_url=None  # You can add a custom avatar URL here
        )
        
        # Connect to project store signals
        project_store.signals.job_status_changed.connect(handle_job_status_change)
        print("Discord integration initialized")
    else:
        print("Discord integration disabled - no webhook configured")


def handle_job_status_change(project_name: str, job_id: str, old_status: str, new_status: str):
    """
    Handle job status changes and send Discord notifications if configured
    
    Args:
        project_name: Name of the project
        job_id: Job ID
        old_status: Previous job status
        new_status: New job status
    """
    # Only process significant status changes
    significant_changes = {
        'RUNNING': ['PENDING', 'SUSPENDED'],  # Job started
        'COMPLETED': ['RUNNING', 'COMPLETING'],  # Job completed successfully
        'FAILED': ['RUNNING', 'COMPLETING'],  # Job failed
        'CANCELLED': ['PENDING', 'RUNNING', 'SUSPENDED'],  # Job cancelled
        'TIMEOUT': ['RUNNING'],  # Job timed out
    }
    
    if new_status not in significant_changes:
        return
    
    if old_status not in significant_changes[new_status]:
        return
    
    # Check if this job has Discord notifications enabled
    if not discord_manager.is_job_registered(job_id):
        return
    
    try:
        # Get job details from project store
        project_store = get_project_store_instance()
        if not project_store:
            return
            
        project = project_store.get(project_name)
        if not project:
            return
            
        job = project.get_job(job_id)
        if not job:
            return
        
        # Get user from slurm connection
        user = getattr(project_store.slurm, 'remote_user', 'Unknown')
        
        if new_status == 'RUNNING':
            # Job started notification
            discord_manager.send_job_started_notification(
                job_id=job_id,
                project_name=project_name,
                job_name=job.name,
                user=user,
                partition=job.partition,
                nodes=job.nodes,
                cpus=job.cpus,
                gpus=job.gpus,
                memory=job.memory
            )
        
        elif new_status in ['COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT']:
            # Job completion notification
            runtime = job.get_runtime_str() if hasattr(job, 'get_runtime_str') else "N/A"
            exit_code = job.info.get('exit_code') if job.info else None
            
            discord_manager.send_job_completed_notification(
                job_id=job_id,
                project_name=project_name,
                job_name=job.name,
                user=user,
                status=new_status,
                runtime=runtime,
                exit_code=exit_code
            )
            
            # Unregister job after completion
            discord_manager.unregister_job(job_id)
    
    except Exception as e:
        print(f"Error sending Discord notification for job {job_id}: {e}")
        import traceback
        traceback.print_exc()


def register_job_for_discord_notifications(job_id: str, discord_settings: dict):
    """
    Register a job for Discord notifications based on its settings
    
    Args:
        job_id: Job ID to register
        discord_settings: Dictionary containing Discord notification settings
    """
    if not discord_settings.get("enabled", False):
        return
    
    # Register the job with the Discord manager
    discord_manager.register_job_for_notifications(job_id)
    
    print(f"Registered job {job_id} for Discord notifications")


def get_project_store_instance():
    """
    Get the ProjectStore singleton instance
    This is a helper function that you might need to adjust based on your implementation
    """
    try:
        from modules.project_store import ProjectStore
        # If ProjectStore is a singleton, you can access it directly
        # You might need to adjust this based on your actual implementation
        return ProjectStore._instance
    except Exception as e:
        print(f"Error getting ProjectStore instance: {e}")
        return None


def test_discord_webhook():
    """
    Test the configured Discord webhook
    
    Returns:
        bool: True if test was successful
    """
    if discord_manager.default_handler:
        return discord_manager.default_handler.test_webhook()
    return False


class DiscordNotificationHandler:
    """
    Handles Discord webhook notifications for job status updates
    """
    
    def __init__(self, webhook_url: str, bot_name: str = "SlurmAIO Bot", avatar_url: Optional[str] = None):
        """
        Initialize Discord notification handler
        
        Args:
            webhook_url: Discord webhook URL
            bot_name: Name to display for the bot
            avatar_url: Avatar image URL for the bot (optional)
        """
        self.webhook_url = webhook_url
        self.bot_name = bot_name
        self.avatar_url = avatar_url
        
        # Status color mapping for Discord embeds
        self.status_colors = {
            "RUNNING": 0x00ff00,      # Green
            "COMPLETED": 0x00aaff,    # Blue  
            "FAILED": 0xff0000,       # Red
            "CANCELLED": 0xff6600,    # Orange
            "TIMEOUT": 0x990000,      # Dark red
            "PENDING": 0xffff00,      # Yellow
            "SUSPENDED": 0x9900ff,    # Purple
            "STOPPED": 0x666666       # Gray
        }
        
        # Status icons/emojis
        self.status_icons = {
            "RUNNING": "🏃",
            "COMPLETED": "✅", 
            "FAILED": "❌",
            "CANCELLED": "🛑",
            "TIMEOUT": "⏰",
            "PENDING": "⏳",
            "SUSPENDED": "⏸️",
            "STOPPED": "⏹️"
        }
    
    def send_job_started_notification(self, project_name: str, job_id: str, job_name: str, 
                                    user: str, partition: str, nodes: int = 1, 
                                    cpus: int = 1, gpus: int = 0, memory: str = "N/A") -> bool:
        """
        Send notification when a job starts running
        
        Args:
            project_name: Name of the project
            job_id: SLURM job ID
            job_name: Human-readable job name
            user: Username who submitted the job
            partition: SLURM partition
            nodes: Number of nodes
            cpus: Number of CPUs
            gpus: Number of GPUs
            memory: Memory allocation
            
        Returns:
            bool: True if notification was sent successfully
        """
        embed = {
            "title": f"{self.status_icons['RUNNING']} Job Started",
            "description": f"**{job_name}** is now running",
            "color": self.status_colors["RUNNING"],
            "fields": [
                {"name": "Job ID", "value": str(job_id), "inline": True},
                {"name": "Project", "value": project_name, "inline": True},
                {"name": "User", "value": user, "inline": True},
                {"name": "Partition", "value": partition, "inline": True},
                {"name": "Resources", "value": f"{nodes} node(s), {cpus} CPU(s)", "inline": True},
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": self.bot_name}
        }
        
        # Add GPU info if available
        if gpus > 0:
            embed["fields"].append({"name": "GPUs", "value": str(gpus), "inline": True})
        
        # Add memory info if available  
        if memory and memory != "N/A":
            embed["fields"].append({"name": "Memory", "value": memory, "inline": True})
        
        return self._send_webhook_message(embeds=[embed])
    
    def send_job_completed_notification(self, project_name: str, job_id: str, job_name: str,
                                      user: str, status: str, runtime: str = "N/A",
                                      exit_code: str = None) -> bool:
        """
        Send notification when a job completes (success, failure, etc.)
        
        Args:
            project_name: Name of the project
            job_id: SLURM job ID
            job_name: Human-readable job name
            user: Username who submitted the job
            status: Final job status
            runtime: Job runtime duration
            exit_code: Job exit code (if available)
            
        Returns:
            bool: True if notification was sent successfully
        """
        status_upper = status.upper()
        icon = self.status_icons.get(status_upper, "❓")
        color = self.status_colors.get(status_upper, 0x666666)
        
        # Determine description based on status
        if status_upper == "COMPLETED":
            description = f"**{job_name}** completed successfully! 🎉"
        elif status_upper == "FAILED":
            description = f"**{job_name}** failed to complete ❌"
        elif status_upper == "CANCELLED":
            description = f"**{job_name}** was cancelled 🛑"
        elif status_upper == "TIMEOUT":
            description = f"**{job_name}** timed out ⏰"
        else:
            description = f"**{job_name}** finished with status: {status}"
        
        embed = {
            "title": f"{icon} Job {status.title()}",
            "description": description,
            "color": color,
            "fields": [
                {"name": "Job ID", "value": str(job_id), "inline": True},
                {"name": "Project", "value": project_name, "inline": True},
                {"name": "User", "value": user, "inline": True},
                {"name": "Status", "value": status.upper(), "inline": True},
            ],
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": self.bot_name}
        }
        
        # Add runtime if available
        if runtime and runtime != "N/A":
            embed["fields"].append({"name": "Runtime", "value": runtime, "inline": True})
        
        # Add exit code if available
        if exit_code:
            embed["fields"].append({"name": "Exit Code", "value": exit_code, "inline": True})
        
        return self._send_webhook_message(embeds=[embed])
    
    def send_custom_notification(self, title: str, message: str, color: int = 0x0099ff) -> bool:
        """
        Send a custom notification
        
        Args:
            title: Notification title
            message: Notification message
            color: Embed color (hex value)
            
        Returns:
            bool: True if notification was sent successfully
        """
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": self.bot_name}
        }
        
        return self._send_webhook_message(embeds=[embed])
    
    def test_webhook(self) -> bool:
        """
        Test the webhook connection by sending a test message
        
        Returns:
            bool: True if test was successful
        """
        embed = {
            "title": "🔔 Test Notification",
            "description": "This is a test message from SlurmAIO to verify Discord webhook configuration.",
            "color": 0x00ff00,
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": self.bot_name}
        }
        
        return self._send_webhook_message(embeds=[embed])
    
    def _send_webhook_message(self, content: str = None, embeds: list = None) -> bool:
        """
        Send a message to Discord via webhook
        
        Args:
            content: Text content (optional)
            embeds: List of embed objects (optional)
            
        Returns:
            bool: True if message was sent successfully
        """
        if not self.webhook_url:
            print("Discord webhook URL not configured")
            return False
        
        payload = {
            "username": self.bot_name,
        }
        
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
        
        if content:
            payload["content"] = content
        
        if embeds:
            payload["embeds"] = embeds
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                self.webhook_url, 
                data=json.dumps(payload), 
                headers=headers, 
                timeout=10
            )
            
            if response.status_code == 204:
                print("Discord notification sent successfully")
                return True
            else:
                print(f"Failed to send Discord notification. Status code: {response.status_code}")
                if response.text:
                    print(f"Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"Error sending Discord notification: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error sending Discord notification: {e}")
            return False


class DiscordNotificationManager:
    """
    Manager class to handle Discord notifications for multiple jobs
    """
    
    def __init__(self):
        self.handlers = {}  # job_id -> DiscordNotificationHandler
        self.default_handler = None
    
    def set_default_webhook(self, webhook_url: str, bot_name: str = "SlurmAIO Bot", 
                          avatar_url: Optional[str] = None):
        """Set the default webhook for notifications"""
        if webhook_url:
            self.default_handler = DiscordNotificationHandler(webhook_url, bot_name, avatar_url)
    
    def register_job_for_notifications(self, job_id: str, webhook_url: str = None):
        """
        Register a job for Discord notifications
        
        Args:
            job_id: Job ID to register
            webhook_url: Specific webhook URL for this job (optional, uses default if not provided)
        """
        if webhook_url:
            self.handlers[job_id] = DiscordNotificationHandler(webhook_url)
        elif self.default_handler:
            self.handlers[job_id] = self.default_handler
        else:
            print(f"No webhook configured for job {job_id}")
    
    def unregister_job(self, job_id: str):
        """Unregister a job from notifications"""
        if job_id in self.handlers:
            del self.handlers[job_id]
    
    def send_job_started_notification(self, job_id: str, **kwargs) -> bool:
        """Send job started notification if job is registered"""
        if job_id in self.handlers:
            return self.handlers[job_id].send_job_started_notification(**kwargs)
        return False
    
    def send_job_completed_notification(self, job_id: str, **kwargs) -> bool:
        """Send job completed notification if job is registered"""
        if job_id in self.handlers:
            return self.handlers[job_id].send_job_completed_notification(**kwargs)
        return False
    
    def is_job_registered(self, job_id: str) -> bool:
        """Check if a job is registered for notifications"""
        return job_id in self.handlers


# Global instance
discord_manager = DiscordNotificationManager()