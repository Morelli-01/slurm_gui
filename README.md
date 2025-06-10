# slurm_gui

A modern Python GUI for managing SLURM jobs with MVC architecture, real-time monitoring, and advanced project organization.

## Features

- Submit and monitor SLURM jobs with real-time updates
- Project-based job organization and management
- Comprehensive cluster status visualization (GPU, CPU, RAM usage)
- Job arrays and dependency management
- Discord webhook notifications for job status changes
- Remote directory browsing and terminal access
- Advanced job queue filtering and sorting
- Live job log viewing with auto-refresh
- Modern dark theme with toast notifications

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

- `main_application.py`: Main entry point. Starts the PyQt GUI and manages the core window and user interactions.
- `style.py`: Centralized styling system with theme management and component-specific styles.
- `utils.py`: Utility functions, helper classes, and common constants used throughout the application.
- `requirements.txt`: Lists Python dependencies required to run the application.
- `README.md`: This file.

### Folders

- `controllers/`: MVC controllers that coordinate between models and views, handling business logic and user interactions.
- `models/`: Data models managing SLURM connections, job data, settings, and business logic with signal emission for real-time updates.
- `views/`: Pure UI presentation components that handle user interface rendering and emit signals for user interactions.
- `widgets/`: Composite UI components that combine MVC patterns into reusable widgets, maintaining backward compatibility.
- `modules/`: Core application modules including job management, project storage, data classes, and configuration defaults.
- `src_static/`: Static resources like icons, images, default config files, and themes.

_Note: Only the first 10 files per folder are listed here due to API limitations. For a full list, visit the links above._

---

### Key MVC Components

#### Controllers (`controllers/`)
- `cluster_status_controller.py`: Coordinates cluster status data between model and view components.
- `job_queue_controller.py`: Manages job queue display logic and filtering operations.
- `settings_controller.py`: Handles application settings and configuration management.
- `slurm_connection_controller.py`: Controls SLURM connection lifecycle and data fetching operations.

#### Models (`models/`)
- `cluster_status_model.py`: Manages cluster node data processing and caching.
- `job_queue_model.py`: Handles job queue data management and filtering state.
- `settings_model.py`: Manages application settings persistence and validation.
- `slurm_connection_model.py`: Core SLURM connection logic, command execution, and job submission.

#### Views (`views/`)
- `cluster_status_view.py`: UI components for cluster status visualization with multiple tabs.
- `job_queue_view.py`: Table display components for job queue presentation.
- `settings_view.py`: Settings interface with connection, display, and notification options.
- `slurm_connection_view.py`: Connection status and cluster information display.

#### Widgets (`widgets/`)
- `cluster_status_widget.py`: Complete cluster status widget combining MVC components.
- `job_queue_widget.py`: Job queue table widget with filtering and sorting capabilities.
- `settings_widget.py`: Settings management widget with tabbed interface.
- `slurm_connection_widget.py`: SLURM connection facade maintaining backward compatibility.
- `toast_widget.py`: Modern notification system with multiple toast types.
- `remote_directory_widget.py`: Remote directory browser with SSH file system access.

#### Core Modules (`modules/`)
- `data_classes.py`: Job and Project data structures with validation and serialization.
- `job_panel.py`: Main job management interface with project organization.
- `jobs_group.py`: Job table container with efficient updates and action buttons.
- `new_job_dp.py`: Job creation and modification dialogs with advanced options.
- `project_store.py`: Project and job persistence with real-time monitoring.
- `job_logs.py`: Job log viewing with live updates and progress tracking.
- `defaults.py`: Application constants, enums, and default configurations.

_Note: For the full up-to-date list, see the [project directory on GitHub](https://github.com/Morelli-01/slurm_gui)._

## License

MIT License