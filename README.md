# slurm_gui

A simple Python GUI for managing SLURM jobs.

## Features

- Submit and monitor SLURM jobs
- User-friendly interface

## Getting Started

1. Clone this repository:
   ```bash
   git clone https://github.com/Morelli-01/slurm_gui.git
   cd slurm_gui
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python main_application.py
   ```

## File/Folder Overview

- `main_application.py`: Main entry point. Starts the PyQt GUI, manages the core window and user interactions.
- `slurm_connection.py`: Logic for connecting to a SLURM cluster via SSH, running commands, fetching job/node info, and handling job submissions.
- `style.py`: Centralized Qt stylesheet and theme definitions used throughout the GUI.
- `utils.py`: Utility functions and common constants (e.g., paths, color codes), plus custom widgets for the UI.
- `requirements.txt`: Lists Python dependencies to run the application.
- `README.md`: This file.

### Folders

- `modules/`: Contains GUI panels, widgets, and supporting logic for jobs, settings, notifications, etc. See breakdown below.
- `src_static/`: Static resources like icons, images, default config files, and themes. (See [all static files](https://github.com/Morelli-01/slurm_gui/tree/main/src_static)).

_Note: Only the first 10 files per folder are listed here due to API limitations. For a full list, visit the links above._

---

### `modules/` Folder File Overview

- `cluster_status_widget.py`: Implements the Cluster Status panel with GPU/CPU/RAM visualizations, node status, and live updates from the cluster.
- `data_classes.py`: Defines the core data models for jobs and projects (Job, Project) and helper methods for SLURM job serialization, validation, and conversion.
- `defaults.py`: Central location for default constants, color definitions, status names, and style options used app-wide.
- `job_logs.py`: Dialog and logic for viewing job logs (stdout, stderr), live-updates logs via background threads, and provides job detail views.
- `job_panel.py`: Main panel for managing jobs, including job creation, submission, status display, and interaction with projects.
- `job_queue_widget.py`: Table widget for displaying, filtering, and sorting the global job queue from SLURM.
- `jobs_group.py`: Multi-project job table container; enables switching between projects and efficiently updating job tables for each project.
- `new_job_dp.py`: Dialog and logic for creating and editing new SLURM jobs, with form validation and advanced options.
- `project_store.py`: Manages project/job storage, synchronizes with remote SLURM cluster settings, and monitors job status in the background.
- `remote_directory_panel.py`: Dialog and logic for browsing, filtering, and selecting remote directories on the SLURM cluster (via SSH).

_Note: For the full up-to-date list, see the [modules directory on GitHub](https://github.com/Morelli-01/slurm_gui/tree/main/modules)._

## License

MIT License
