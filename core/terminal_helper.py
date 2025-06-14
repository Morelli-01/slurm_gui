"""
Terminal Helper - Cross-platform SSH Terminal Management
Handles opening SSH terminals across different operating systems with proper error handling.
"""

import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, List, Callable
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from widgets.toast_widget import (
    show_success_toast, show_error_toast, show_warning_toast
)


class PlatformType(Enum):
    """Supported platform types"""
    WINDOWS = auto()
    MACOS = auto() 
    LINUX = auto()
    UNSUPPORTED = auto()


@dataclass
class SSHConnectionDetails:
    """SSH connection configuration"""
    host: str
    username: str
    password: str
    port: int = 22
    
    def __post_init__(self):
        if not self.host or not self.username:
            raise ValueError("Host and username are required")


@dataclass
class TerminalConfig:
    """Terminal configuration options"""
    prefer_putty: bool = True  # Windows: prefer PuTTY over built-in terminal
    putty_paths: List[str] = None  # Custom PuTTY installation paths
    terminal_preferences: List[str] = None  # Preferred terminal emulators
    
    def __post_init__(self):
        if self.putty_paths is None:
            self.putty_paths = [
                "putty.exe",  # In PATH
                r"C:\Program Files\PuTTY\putty.exe",
                r"C:\Program Files (x86)\PuTTY\putty.exe",
            ]
        
        if self.terminal_preferences is None:
            # Default terminal preferences for each platform
            self.terminal_preferences = []


class TerminalHelper(QObject):
    """
    Cross-platform terminal helper for SSH connections.
    Handles platform detection, terminal selection, and SSH command execution.
    """
    
    # Signals for feedback
    terminal_opened = pyqtSignal(str, str)  # host, username
    terminal_failed = pyqtSignal(str)       # error_message
    
    def __init__(self, config: Optional[TerminalConfig] = None, parent=None):
        super().__init__(parent)
        self.config = config or TerminalConfig()
        self.platform = self._detect_platform()
        self._temp_files: List[str] = []
        
    def _detect_platform(self) -> PlatformType:
        """Detect the current platform"""
        system = platform.system().lower()
        if system == "windows":
            return PlatformType.WINDOWS
        elif system == "darwin":
            return PlatformType.MACOS
        elif system == "linux":
            return PlatformType.LINUX
        else:
            return PlatformType.UNSUPPORTED
    
    def open_ssh_terminal(self, connection: SSHConnectionDetails, 
                         parent_widget=None) -> bool:
        """
        Open SSH terminal for the given connection details.
        
        Args:
            connection: SSH connection configuration
            parent_widget: Parent widget for toast notifications
            
        Returns:
            bool: True if terminal was successfully opened, False otherwise
        """
        try:
            if self.platform == PlatformType.UNSUPPORTED:
                self._show_error(parent_widget, 
                    "Unsupported Platform",
                    f"Terminal opening not supported on {platform.system()}")
                return False
            
            # Select appropriate method based on platform
            method_map = {
                PlatformType.WINDOWS: self._open_windows_terminal,
                PlatformType.MACOS: self._open_macos_terminal,
                PlatformType.LINUX: self._open_linux_terminal,
            }
            
            success = method_map[self.platform](connection, parent_widget)
            
            if success:
                self.terminal_opened.emit(connection.host, connection.username)
                self._show_success(parent_widget,
                    "Terminal Opened",
                    f"SSH session opened for {connection.username}@{connection.host}")
            
            return success
            
        except Exception as e:
            error_msg = f"Failed to open terminal: {str(e)}"
            self.terminal_failed.emit(error_msg)
            self._show_error(parent_widget, "Terminal Error", error_msg)
            return False
    
    def _open_windows_terminal(self, connection: SSHConnectionDetails, 
                              parent_widget=None) -> bool:
        """Open terminal on Windows using PuTTY for SSH connection"""
        try:
            if self.config.prefer_putty:
                # Try PuTTY first
                putty_path = self._find_putty()
                if putty_path:
                    putty_cmd = [
                        putty_path,
                        f"{connection.username}@{connection.host}",
                        "-ssh",
                        "-pw", connection.password
                    ]
                    
                    if connection.port != 22:
                        putty_cmd.extend(["-P", str(connection.port)])
                    
                    subprocess.Popen(putty_cmd)
                    return True
                else:
                    self._show_error(parent_widget,
                        "PuTTY Not Found",
                        "PuTTY is required for SSH connections on Windows.\n"
                        "Please install PuTTY from https://www.putty.org/")
                    return False
            
            # Fallback to Windows Terminal or PowerShell SSH (if available)
            return self._try_windows_native_ssh(connection, parent_widget)
            
        except Exception as e:
            self._show_error(parent_widget,
                "Windows Terminal Error", 
                f"Failed to open Windows terminal: {str(e)}")
            return False
    
    def _open_macos_terminal(self, connection: SSHConnectionDetails,
                            parent_widget=None) -> bool:
        """Open terminal on macOS using sshpass for automatic SSH login"""
        try:
            # Check if sshpass is available
            sshpass_path = shutil.which("sshpass")
            if not sshpass_path:
                self._show_error(parent_widget,
                    "sshpass Not Found",
                    "sshpass is required for automatic password entry. "
                    "Please install sshpass (e.g., 'brew install sshpass').")
                return False
            
            # Build the sshpass command
            ssh_cmd = self._build_ssh_command(connection, sshpass_path)
            
            # List of terminal emulators to try for macOS
            terminals = [
                # Default Terminal.app
                ["open", "-a", "Terminal", f"{ssh_cmd}"],
                ["open", "-a", "iTerm", f"{ssh_cmd}"],  # iTerm2
                # AppleScript fallback
                ["osascript", "-e", 
                 f'tell application "Terminal" to do script "{ssh_cmd}"'],
            ]
            
            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd)
                    return True
                except FileNotFoundError:
                    continue
            
            # If no terminal emulator found, try AppleScript approach
            try:
                applescript = f"""
                tell application "Terminal"
                    activate
                    do script "{ssh_cmd}"
                end tell
                """
                subprocess.Popen(["osascript", "-e", applescript])
                return True
            except Exception as e:
                self._show_error(parent_widget,
                    "No Terminal Found",
                    f"No supported terminal emulator found: {str(e)}")
                return False
                
        except Exception as e:
            self._show_error(parent_widget,
                "macOS Terminal Error",
                f"Failed to open macOS terminal: {str(e)}")
            return False
    
    def _open_linux_terminal(self, connection: SSHConnectionDetails,
                            parent_widget=None) -> bool:
        """Open terminal on Linux using sshpass for automatic SSH login"""
        try:
            # Check if sshpass is available
            sshpass_path = shutil.which("sshpass")
            if not sshpass_path:
                self._show_error(parent_widget,
                    "sshpass Not Found",
                    "sshpass is required for automatic password entry. "
                    "Please install sshpass (e.g., 'sudo apt install sshpass').")
                return False
            
            # Build the sshpass command
            ssh_cmd = self._build_ssh_command(connection, sshpass_path)
            
            # List of terminal emulators to try
            terminals = [
                ["gnome-terminal", "--", "bash", "-c", f"{ssh_cmd}"],
                ["konsole", "-e", "bash", "-c", f"{ssh_cmd}"],
                ["xfce4-terminal", "-e", f"bash -c {ssh_cmd}"],
                ["lxterminal", "-e", f"bash -c {ssh_cmd}"],
                ["mate-terminal", "-e", f"bash -c {ssh_cmd}"],
                ["terminator", "-e", f"bash -c {ssh_cmd}"],
                ["alacritty", "-e", "bash", "-c", f"{ssh_cmd}"],
                ["kitty", "bash", "-c", f"{ssh_cmd}"],
                ["xterm", "-e", f"bash -c {ssh_cmd}"],
            ]
            
            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd)
                    return True
                except FileNotFoundError:
                    continue
            
            self._show_error(parent_widget,
                "No Terminal Found",
                "No supported terminal emulator found on this system.")
            return False
            
        except Exception as e:
            self._show_error(parent_widget,
                "Linux Terminal Error",
                f"Failed to open Linux terminal: {str(e)}")
            return False
    
    def _find_putty(self) -> Optional[str]:
        """Find PuTTY executable on Windows"""
        for path in self.config.putty_paths:
            if shutil.which(path) or os.path.exists(path):
                return path
        return None
    
    def _build_ssh_command(self, connection: SSHConnectionDetails,
                          sshpass_path: str) -> str:
        """Build SSH command with sshpass"""
        ssh_cmd = (f"{sshpass_path} -p '{connection.password}' "
                  f"ssh {connection.username}@{connection.host}")
        
        if connection.port != 22:
            ssh_cmd += f" -p {connection.port}"
            
        return ssh_cmd
    
    def _try_windows_native_ssh(self, connection: SSHConnectionDetails,
                               parent_widget=None) -> bool:
        """Try to use Windows built-in SSH (Windows 10+)"""
        try:
            # Check if SSH is available
            if not shutil.which("ssh.exe"):
                return False
            
            # Create a batch file for the SSH connection
            batch_content = f"""@echo off
echo Connecting to {connection.host}...
ssh {connection.username}@{connection.host}
pause
"""
            
            # Create temporary batch file
            temp_file = tempfile.NamedTemporaryFile(
                mode='w', suffix='.bat', delete=False
            )
            temp_file.write(batch_content)
            temp_file.close()
            self._temp_files.append(temp_file.name)
            
            # Run the batch file
            subprocess.Popen(['cmd', '/c', 'start', 'cmd', '/k', temp_file.name])
            
            # Schedule cleanup
            self._schedule_cleanup(temp_file.name)
            return True
            
        except Exception:
            return False
    
    def _schedule_cleanup(self, file_path: str, delay_ms: int = 10000):
        """Schedule temporary file cleanup"""
        from PyQt6.QtCore import QTimer
        
        def cleanup():
            self._cleanup_temp_file(file_path)
            
        QTimer.singleShot(delay_ms, cleanup)
    
    def _cleanup_temp_file(self, file_path: str):
        """Clean up temporary script files"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
                if file_path in self._temp_files:
                    self._temp_files.remove(file_path)
        except Exception as e:
            print(f"Warning: Could not clean up temporary file {file_path}: {e}")
    
    def _show_success(self, parent_widget, title: str, message: str):
        """Show success toast notification"""
        if parent_widget:
            show_success_toast(parent_widget, title, message)
    
    def _show_error(self, parent_widget, title: str, message: str):
        """Show error toast notification"""
        if parent_widget:
            show_error_toast(parent_widget, title, message)
    
    def _show_warning(self, parent_widget, title: str, message: str):
        """Show warning toast notification"""
        if parent_widget:
            show_warning_toast(parent_widget, title, message)
    
    def cleanup(self):
        """Clean up all temporary files"""
        for file_path in self._temp_files[:]:  # Copy list to avoid modification during iteration
            self._cleanup_temp_file(file_path)
    
    def __del__(self):
        """Cleanup on destruction"""
        self.cleanup()

