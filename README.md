# SLURM GUI

A modern Python application for managing SLURM jobs with a clean GUI, real-time monitoring, and project-based organization.

## Features

- Submit and monitor SLURM jobs in real time
- Visualize cluster status (CPU, GPU, RAM usage)
- Organize jobs by project
- Discord notifications for job events
- Browse remote directories
- Integrated SSH terminal
- Dark theme and toast notifications

## Getting Started

```bash
git clone https://github.com/Morelli-01/slurm_gui.git
cd slurm_gui
pip install -r requirements.txt
python main_application.py
```

## Project Structure

- `main_application.py` — Application entry point
- `core/` — Event bus, SLURM API, styling
- `controllers/` — Business logic
- `models/` — Data and SLURM operations
- `views/` — UI components
- `widgets/` — Reusable UI elements
- `src_static/` — Icons, images, configs

## Requirements

- Python 3.8+
- PyQt6
- See `requirements.txt` for all dependencies

## License

MIT