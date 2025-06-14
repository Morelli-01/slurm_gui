# slurm_gui

Modern Python GUI for managing SLURM jobs with MVC architecture and real-time monitoring.

## Features

- Real-time SLURM job submission and monitoring
- Cluster status visualization (GPU/CPU/RAM usage)
- Project-based job organization
- Discord notifications
- Remote directory browsing
- SSH terminal integration
- Dark theme with toast notifications

## Quick Start

```bash
git clone https://github.com/Morelli-01/slurm_gui.git
cd slurm_gui
pip install -r requirements.txt
python main_application.py
```

## Architecture

### Core Files
- `main_application.py` - Application entry point
- `core/` - Event bus, SLURM API, styling system
- `utils.py` - Helper functions and constants

### MVC Structure
- `controllers/` - Business logic coordination
- `models/` - Data management and SLURM operations  
- `views/` - UI components and presentation
- `widgets/` - Reusable composite UI elements
- `modules/` - Job management and project storage

### Resources
- `src_static/` - Icons, images, and default configs

## Requirements

- Python 3.8+
- PyQt6
- See `requirements.txt` for full dependencies

## License

MIT