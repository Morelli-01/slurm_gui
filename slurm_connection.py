import yaml, sys
import os
from time import sleep
import paramiko
import yaml
import os
import tempfile
from PyQt6.QtCore import QObject


class SlurmConnection:
    def __init__(self, config_path="slurm_config.yaml"):
        self.config_path = config_path
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        ssh_config = self.config.get('ssh', {})
        self.host = ssh_config.get('host')
        self.user = ssh_config.get('user')
        self.password = ssh_config.get('password')
        self.identity_file = ssh_config.get('identity_file')

        self.client = None

        # Info raccolte
        self.remote_user = None
        self.user_groups = None
        self.num_nodes = None
        self.hostname = None
        self.slurm_version = None

        # Per la GUI
        self.partitions = []
        self.constraints = []
        self.qos_list = []
        self.accounts = []
        self.gres = []
        self.remote_home = None

    def connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            if self.identity_file and os.path.exists(self.identity_file):
                self.client.connect(self.host, username=self.user, key_filename=self.identity_file)
            elif self.password:
                self.client.connect(self.host, username=self.user, password=self.password)
            else:
                raise ValueError("No valid authentication method provided.")
            print(f"Connected to {self.host}")
            self._fetch_basic_info()
            self._fetch_submission_options()
            self.remote_home, _ = self.run_command("echo $HOME")
            self.remote_home = self.remote_home.strip()
            self.run_command(f"mkdir -p {self.remote_home}/.logs")

        except Exception as e:
            print(f"Connection failed: {e}")

    def is_connected(self):
        try:
            transport = self.client.get_transport()
            if transport and transport.is_active():
                # Try sending a simple command with a short timeout to check if the channel is still working
                channel = transport.open_session(timeout=1)
                if channel:
                    channel.close()
                    return True
                else:
                    return False
            else:
                return False
        except paramiko.SSHException as e:
            print(f"SSH error: {e}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return False

    def run_command(self, command):
        if not self.is_connected():
            raise ConnectionError("SSH connection not established.")
        stdin, stdout, stderr = self.client.exec_command(command)
        return stdout.read().decode().strip(), stderr.read().decode().strip()

    def _fetch_basic_info(self):
        try:
            self.remote_user, _ = self.run_command("whoami")
            self.user_groups, _ = self.run_command("groups")
            self.num_nodes, _ = self.run_command("sinfo -h -o '%D' | awk '{s+=$1} END {print s}'")
            self.hostname, _ = self.run_command("hostname")
            self.slurm_version, _ = self.run_command("scontrol --version")
        except Exception as e:
            print(f"Failed to fetch system info: {e}")

    def _fetch_submission_options(self):
        try:
            partitions_out, _ = self.run_command("sinfo -h -o '%P'")
            self.partitions = sorted(set(partitions_out.splitlines()))

            constraints_out, _ = self.run_command("sinfo -o '%f' | sort | uniq")
            self.constraints = sorted(set(constraints_out.split()))

            qos_out, _ = self.run_command("sacctmgr show qos format=Name -n -P")
            self.qos_list = sorted(set(qos_out.splitlines()))

            if self.remote_user:
                acc_out, _ = self.run_command(
                    f"sacctmgr show associations user={self.remote_user} format=Account -n -P")
                self.accounts = sorted(set(acc_out.splitlines()))

            gres_out, _ = self.run_command("scontrol show gres")
            self.gres = [line.strip() for line in gres_out.splitlines() if "Name=" in line]

        except Exception as e:
            print(f"Failed to fetch submission options: {e}")

    def submit_job(self, job_name, partition, time_limit, command, account,
                   constraint=None, qos=None,
                   gres=None, nodes=1, ntasks=1,
                   output_file=".logs/out_%A.log", error_file=".logs/err_%A.log"):
        if not self.is_connected():
            raise ConnectionError("SSH connection not established.")

        # Crea contenuto script SLURM
        script_lines = [
            f"#!/bin/bash",
            f"#SBATCH --job-name={job_name}",
            f"#SBATCH --partition={partition}",
            f"#SBATCH --time={time_limit}",
            f"#SBATCH --nodes={nodes}",
            f"#SBATCH --ntasks={ntasks}",
            f"#SBATCH --output={self.remote_home}/{output_file}",
            f"#SBATCH --error={self.remote_home}/{error_file}",
        ]
        if constraint:
            script_lines.append(f"#SBATCH --constraint={constraint}")
        if qos:
            script_lines.append(f"#SBATCH --qos={qos}")
        if account:
            script_lines.append(f"#SBATCH --account={account}")
        if gres:
            script_lines.append(f"#SBATCH --gres={gres}")

        script_lines.append("")  # Riga vuota
        script_lines.append(command)

        script_content = "\n".join(script_lines)

        # Salva script localmente
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sh") as f:
            f.write(script_content)
            local_script_path = f.name

        # Path remoto (home directory temporanea)
        remote_script_path = f"/tmp/{os.path.basename(local_script_path)}"

        try:
            # Upload dello script via SFTP
            sftp = self.client.open_sftp()
            sftp.put(local_script_path, remote_script_path)
            sftp.close()

            # Sottomissione via sbatch
            stdout, stderr = self.run_command(f"sbatch {remote_script_path}")

            # Pulizia file locale
            os.remove(local_script_path)

            if stderr:
                raise RuntimeError(f"SLURM error: {stderr}")

            # Parsing dell'ID del job
            job_id = None
            if "Submitted batch job" in stdout:
                job_id = stdout.strip().split()[-1]

            return job_id

        except Exception as e:
            raise RuntimeError(f"Job submission failed: {e}")

    def get_job_logs(self, job_id):
        if not self.is_connected():
            raise ConnectionError("SSH connection not established.")

        remote_log_dir = f"{self.remote_home}/.logs"
        stdout_file = f"{remote_log_dir}/out_{job_id}.log"
        stderr_file = f"{remote_log_dir}/err_{job_id}.log"

        stdout, stderr = "", ""
        try:
            out, _ = self.run_command(f"cat {stdout_file}")
            stdout = out.strip()
        except Exception:
            stdout = f"[!] Output log {stdout_file} not found or unreadable."

        try:
            err, _ = self.run_command(f"cat {stderr_file}")
            stderr = err.strip()
        except Exception:
            stderr = f"[!] Error log {stderr_file} not found or unreadable."

        return stdout, stderr

    def update_credentials_and_reconnect(self, new_user, new_host, new_psw=None, new_identity_file=None):
        self.config['ssh'] = {
            'user': new_user,
            'host': new_host,
            'password': new_psw,
            'identity_file': new_identity_file
        }
        try:
            with open(self.config_path, "w") as f:
                yaml.dump(self.config, f)
            if self.is_connected():
                self.client.close()
            self.__init__(self.config_path)
            self.connect()
        except Exception as e:
            raise IOError(f"Failed to update YAML configuration file: {e}")

    def _read_maintenances(self):
        msg_out, MSG_ERRQUEUE = self.run_command("scontrol show reservation 2>/dev/null")
        if "No reservations in the system" in msg_out:
            return None
        else:
            return msg_out

    def _fetch_nodes_infos(self):
        msg_out, msg_err = self.run_command("scontrol show nodes")
        nodes = msg_out.split("\n\n")
        nodes_arr = []
        for node in nodes:
            node_dict = {}
            for feats in node.split("\n"):
                for f in feats.split(" "):
                    if "=" in f:
                        if "AllocTRES" in f:
                            for f1 in f.removeprefix("AllocTRES=").split(","):
                                if f1 != '':
                                    k, v = f1.split("=")
                                    node_dict[f"alloc_{k}"] = v
                        elif "CfgTRES" in f:
                            for f1 in f.removeprefix("CfgTRES=").split(","):
                                if f1 != '':
                                    k, v = f1.split("=")
                                    node_dict[f"total_{k}"] = v
                        else:
                            f = f.strip().split("=")
                            node_dict[f[0]] = f[1]
            nodes_arr.append(node_dict)

        return nodes_arr

    def close(self):
        if self.client:
            self.client.close()
            print("SSH connection closed.")


if __name__ == "__main__":
    sc_ = SlurmConnection("./configs/slurm_config.yaml")
    sc_.connect()
    out = sc_._fetch_nodes_infos()
    print(out[5])
    sys.exit(0)
    out, err = sc_.run_command("squeue")

    print(out, err)
    print(sc_.remote_user)
    print(sc_.user_groups)
    print(sc_.num_nodes)
    print(sc_.hostname)
    print(sc_.slurm_version)
    print(sc_.partitions)   # ["main", "gpu", "long"]
    print(sc_.constraints)  # ["intel", "amd", "highmem"]
    print(sc_.qos_list)     # ["normal", "debug", "high"]
    print(sc_.accounts)     # ["project1", "project2"]
    print(sc_.gres)         # ["Name=gpu Type=rtx5000 Count=2 ..."]

    try:
        job_id = sc_.submit_job(job_name="test_", partition="all_serial", time_limit="00:10:00",
                                command="nvidia-smi", account="tesi_nmorelli", gres="gpu:1")
        print(job_id)
        sleep(5)
        out, err = sc_.get_job_logs(job_id)
        print(out, err)
    except RuntimeError as e:
        print(e)
