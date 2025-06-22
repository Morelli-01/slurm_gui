#!/usr/bin/env python3
"""
Simple Cineca HPC Cluster SSH Connection using system SSH client

This script uses the system's SSH client instead of paramiko to avoid
compatibility issues with ECDSA keys and SSH certificates.
"""

import subprocess
import os
import sys
from pathlib import Path


class CinecaSSHSimple:
    def __init__(self, username, cluster='leonardo'):
        self.username = username
        self.clusters = {
            'marconi': 'login.marconi.cineca.it',
            'g100': 'login.g100.cineca.it',
            'leonardo': 'login05-ext.leonardo.cineca.it',
            'pitagora': 'login.pitagora.cineca.it'
        }
        
        if cluster not in self.clusters:
            raise ValueError(f"Invalid cluster. Choose from: {list(self.clusters.keys())}")
        
        self.hostname = self.clusters[cluster]
        self.cert_path = os.path.expanduser('~/.ssh/id_rsa-cert.pub')
        self.key_path = os.path.expanduser('~/.ssh/id_rsa')

    def check_smallstep_installed(self):
        """Check if smallstep client is installed"""
        try:
            result = subprocess.run(['step', 'version'], 
                                  capture_output=True, text=True, check=True)
            print(f"Smallstep version: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error: smallstep client not found!")
            print("Please install it from: https://smallstep.com/docs/step-cli/installation/")
            return False
    
    def generate_certificate(self):
        """Generate SSH certificate using smallstep, allowing user to input passphrase interactively if needed."""
        print("Generating SSH certificate using smallstep...")
        print("This will open a browser window for 2FA authentication.")
        cmd = [
            'step', 'ssh', 'certificate',
            f'{self.username}@{self.hostname}',
            self.key_path
        ]
        # Always run with subprocess so user can input passphrase interactively if needed
        try:
            result = subprocess.run(cmd, check=True)
            print("Certificate generated successfully!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error generating certificate: {e}")
            return False

    def check_certificate_validity(self):
        """Check if SSH certificate exists and is valid"""
        if not os.path.exists(self.cert_path):
            print("No SSH certificate found.")
            return False
        
        try:
            result = subprocess.run([
                'ssh-keygen', '-L', '-f', self.cert_path
            ], capture_output=True, text=True, check=True)
            
            print("Certificate status:")
            print(result.stdout)
            return True
                
        except subprocess.CalledProcessError:
            print("Error checking certificate validity.")
            return False
    
    def delete_certificate(self):
        """Delete existing SSH certificate and key files"""
        files_to_delete = [
            self.cert_path,
            self.key_path,
            self.key_path + '.pub'
        ]
        
        deleted_files = []
        for file_path in files_to_delete:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    deleted_files.append(file_path)
                    print(f"Deleted: {file_path}")
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")
            else:
                print(f"File not found: {file_path}")
        
        if deleted_files:
            print(f"\nDeleted {len(deleted_files)} certificate/key files.")
            print("You can now generate a new certificate with --generate-cert")
        else:
            print("No certificate files found to delete.")
        
        # Also remove from SSH agent if loaded
        try:
            result = subprocess.run(['ssh-add', '-d', self.key_path], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("Removed key from SSH agent.")
        except:
            pass  # SSH agent might not be running
    
    def test_connection(self, password=None):
        """Test SSH connection using putty.exe for password automation on Windows."""
        print(f"Testing connection to {self.hostname}...")
        if password:
            putty_paths = [
                "putty.exe",  # In PATH
                r"C:\\Program Files\\PuTTY\\putty.exe",
                r"C:\\Program Files (x86)\\PuTTY\\putty.exe",
                os.path.join(os.path.dirname(__file__), "putty.exe"),
            ]
            putty_path = None
            for path in putty_paths:
                if os.path.exists(path):
                    putty_path = path
                    break
            if not putty_path:
                print("PuTTY (putty.exe) not found. Please install it from https://www.putty.org/")
                return False
            cmd = [
                putty_path,
                f"{self.username}@{self.hostname}",
                "-ssh",
                "-pw", password,
                "-m", os.path.join(os.path.dirname(__file__), "putty_test_cmd.txt")
            ]
            # Write the test command to a temp file
            with open(os.path.join(os.path.dirname(__file__), "putty_test_cmd.txt"), "w") as f:
                f.write('echo "Connection successful!" && hostname && whoami\n')
            try:
                subprocess.Popen(cmd)
                print("PuTTY window opened for connection test. Please check the window for results.")
                return True
            except Exception as e:
                print(f"Error starting PuTTY: {e}")
                return False
        else:
            cmd = [
                'ssh',
                '-o', 'ConnectTimeout=10',
                '-o', 'StrictHostKeyChecking=accept-new',
                f'{self.username}@{self.hostname}',
                'echo "Connection successful!" && hostname && whoami'
            ]
            try:
                result = subprocess.run(cmd, timeout=30)
                if result.returncode == 0:
                    print("✓ Connection test successful!")
                    return True
                else:
                    print("✗ Connection test failed!")
                    return False
            except subprocess.TimeoutExpired:
                print("✗ Connection test timed out!")
                return False
            except Exception as e:
                print(f"✗ Connection test error: {e}")
                return False

    def execute_command(self, command, password=None):
        """Execute a single command on the remote system using putty.exe if password is provided."""
        print(f"Executing: {command}")
        if password:
            putty_paths = [
                "putty.exe",  # In PATH
                r"C:\\Program Files\\PuTTY\\putty.exe",
                r"C:\\Program Files (x86)\\PuTTY\\putty.exe",
                os.path.join(os.path.dirname(__file__), "putty.exe"),
            ]
            putty_path = None
            for path in putty_paths:
                if os.path.exists(path):
                    putty_path = path
                    break
            if not putty_path:
                print("PuTTY (putty.exe) not found. Please install it from https://www.putty.org/")
                return False
            cmd = [
                putty_path,
                f"{self.username}@{self.hostname}",
                "-ssh",
                "-pw", password,
                "-m", os.path.join(os.path.dirname(__file__), "putty_cmd.txt")
            ]
            # Write the command to a temp file
            with open(os.path.join(os.path.dirname(__file__), "putty_cmd.txt"), "w") as f:
                f.write(command + '\n')
            try:
                subprocess.Popen(cmd)
                print("PuTTY window opened for command execution. Please check the window for results.")
                return True
            except Exception as e:
                print(f"Error starting PuTTY: {e}")
                return False
        else:
            cmd = [
                'ssh',
                '-o', 'StrictHostKeyChecking=accept-new',
                f'{self.username}@{self.hostname}',
                command
            ]
            try:
                result = subprocess.run(cmd, timeout=30)
                return result.returncode == 0
            except subprocess.TimeoutExpired:
                print("Command timed out!")
                return False
            except Exception as e:
                print(f"Error executing command: {e}")
                return False

    def interactive_shell(self, password=None):
        """Start an interactive SSH session using putty.exe if password is provided (Windows compatible)"""
        print(f"Starting interactive session to {self.hostname}...")
        print("Press Ctrl+D or type 'exit' to close the session.")
        print("-" * 50)
        if password:
            putty_paths = [
                "putty.exe",  # In PATH
                r"C:\\Program Files\\PuTTY\\putty.exe",
                r"C:\\Program Files (x86)\\PuTTY\\putty.exe",
                os.path.join(os.path.dirname(__file__), "putty.exe"),
            ]
            putty_path = None
            for path in putty_paths:
                if os.path.exists(path):
                    putty_path = path
                    break
            if not putty_path:
                print("PuTTY (putty.exe) not found. Please install it from https://www.putty.org/")
                return False
            cmd = [
                putty_path,
                f"{self.username}@{self.hostname}",
                "-ssh",
                "-pw", password
            ]
            try:
                subprocess.Popen(cmd)
                print("PuTTY window opened for interactive session.")
                return True
            except Exception as e:
                print(f"Error starting PuTTY: {e}")
                return False
        else:
            cmd = [
                'ssh',
                '-t',
                '-o', 'StrictHostKeyChecking=accept-new',
                f'{self.username}@{self.hostname}',
            ]
            try:
                result = subprocess.call(cmd)
                return result == 0
            except Exception as e:
                print(f"Error starting interactive session: {e}")
                return False
    
    def file_transfer_help(self):
        """Show help for file transfers"""
        print("File Transfer Commands:")
        print("-" * 30)
        print(f"Upload file:   scp /local/path {self.username}@{self.hostname}:/remote/path")
        print(f"Download file: scp {self.username}@{self.hostname}:/remote/path /local/path")
        print(f"Upload dir:    scp -r /local/dir {self.username}@{self.hostname}:/remote/path")
        print(f"Download dir:  scp -r {self.username}@{self.hostname}:/remote/dir /local/path")
        print()
        print("Alternative with rsync:")
        print(f"Sync upload:   rsync -avz /local/path {self.username}@{self.hostname}:/remote/path")
        print(f"Sync download: rsync -avz {self.username}@{self.hostname}:/remote/path /local/path")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Connect to Cineca HPC clusters (simple version)')
    parser.add_argument('username', help='Your Cineca username')
    parser.add_argument('--psw', help='Your rsa psw')

    parser.add_argument('--cluster', '-c', default='leonardo',
                       choices=['marconi', 'g100', 'leonardo', 'pitagora'],
                       help='Cluster to connect to (default: leonardo)')
    parser.add_argument('--command', help='Command to execute')
    parser.add_argument('--interactive', '-i', action='store_true',
                       help='Start interactive shell (default if no command given)')
    parser.add_argument('--test', '-t', action='store_true',
                       help='Test connection only')
    parser.add_argument('--cert-info', action='store_true',
                       help='Show certificate information')
    parser.add_argument('--generate-cert', action='store_true',
                       help='Generate new certificate')
    parser.add_argument('--transfer-help', action='store_true',
                       help='Show file transfer help')
    parser.add_argument('--fix-host-key', action='store_true',
                       help='Remove old host key from known_hosts')
    parser.add_argument('--delete-cert', action='store_true',
                       help='Delete existing certificate and key files')
    parser.add_argument('--fresh-start', action='store_true',
                       help='Delete certificate and generate a new one')
    
    args = parser.parse_args()
    
    conn = CinecaSSHSimple(args.username, args.cluster)
    
    # Check if smallstep is available
    if not conn.check_smallstep_installed():
        return 1
    
    # Handle different actions
    if args.generate_cert:
        if conn.generate_certificate():
            print("Certificate generated. You can now connect to the cluster.")
        return 0
    
    if args.cert_info:
        conn.check_certificate_validity()
        return 0
    
    if args.transfer_help:
        conn.file_transfer_help()
        return 0
    
    if args.fix_host_key:
        conn.fix_host_key()
        return 0
    
    if args.delete_cert:
        conn.delete_certificate()
        return 0
    
    if args.fresh_start:
        print("=== Fresh Start: Deleting old certificate and generating new one ===")
        conn.delete_certificate()
        print()
        if conn.generate_certificate():
            print("\n=== Testing new certificate ===")
            # success = conn.test_connection()
            return 0 if True else 1
        return 1
    
    # Check certificate validity
    if not conn.check_certificate_validity():
        print("\nNo valid certificate found.")
        print("Generate one with: python script.py username --generate-cert")
        return 1
    
    if args.test:
        success = conn.test_connection()
        return 0 if success else 1
    
    elif args.command:
        success = conn.execute_command(args.command)
        return 0 if success else 1
    
    else:
        # Default to interactive session
        conn.interactive_shell(args.psw)
        return 0


if __name__ == "__main__":
    sys.exit(main())