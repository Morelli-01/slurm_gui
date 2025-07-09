# Slurm AIO

A modern, cross-platform GUI for managing and monitoring SLURM clusters, designed for simplicity and efficiency.

## ✨ Features

* **Real-time Monitoring:** Visualize cluster status (Nodes, CPU, GPU, and RAM usage) and track the job queue as it happens.
* **Project-Based Organization:** Group your jobs into projects for better management and clarity.
* **Intuitive Job Management:** Easily create, submit, modify, duplicate, and cancel jobs through a user-friendly interface.
* **Integrated Tools:**

  * Browse remote directories on the cluster.
  * Open an SSH terminal directly to the cluster or a running job's node.
  * View job output and error logs in real-time.
* **Notifications:** Get Discord notifications for job status changes (start, completion, failure).
* **Modern UI:** A clean, dark-themed interface with helpful toast notifications.

## 📦 Installation Options

You can install **Slurm AIO** in two ways:

### 1. Install via pip (Recommended)

```sh
pip install slurm-aio-gui
```

After installation, run the app using:

```sh
slurm-aio-gui
```

### 2. Install from source

#### Prerequisites

* Python 3.8+
* Access to a SLURM cluster via SSH
* `sshpass` is required for password-based terminal authentication on Linux/macOS.

  * **Ubuntu/Debian:** `sudo apt-get install sshpass`
  * **macOS (Homebrew):** `brew install sshpass`

#### Steps

1. **Clone the repository:**

   ```sh
   git clone https://github.com/Morelli-01/slurm_gui.git
   cd slurm_gui
   ```

2. **Install the dependencies:**

   ```sh
   pip install -r requirements.txt
   ```

3. **Run the application:**

   ```sh
   python main_application.py
   ```

   The first time you run the application, you will be prompted to enter your cluster's SSH connection details.

## 📸 Screenshots

*Visualization of the cluster status and the jobs panel.*

![Cluster Status Panel](https://raw.githubusercontent.com/Morelli-01/slurm_gui/refs/heads/main/src_static/cluster_status.webp)

![Jobs Panel](https://raw.githubusercontent.com/Morelli-01/slurm_gui/refs/heads/main/src_static/job_panel.webp)


## 📄 License

This project is licensed under the MIT License.
