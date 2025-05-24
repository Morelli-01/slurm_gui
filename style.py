"""
Centralized styling system for SlurmAIO application.
All styles are defined here for better maintainability and organization.
"""

import os
from modules.defaults import *
from utils import script_dir
# Get script directory for icon paths

class AppStyles:
    """Central class containing all application styles"""
    
    # Base colors and theme definitions
    THEMES = {
        THEME_DARK: {
            'bg': COLOR_DARK_BG,
            'fg': COLOR_DARK_FG,
            'bg_alt': COLOR_DARK_BG_ALT,
            'bg_hover': COLOR_DARK_BG_HOVER,
            'border': COLOR_DARK_BORDER,
        },
        THEME_LIGHT: {
            'bg': COLOR_LIGHT_BG,
            'fg': COLOR_LIGHT_FG,
            'bg_alt': COLOR_LIGHT_BG_ALT,
            'bg_hover': COLOR_LIGHT_BG_HOVER,
            'border': COLOR_LIGHT_BORDER,
        }
    }
    
    @classmethod
    def get_main_window_style(cls, theme=THEME_DARK):
        """Main window and base widget styles"""
        colors = cls.THEMES[theme]
        
        return f"""
        QMainWindow, QWidget {{
            background-color: {colors['bg']};
            color: {colors['fg']};
            font-family: Inter, sans-serif;
        }}
        """
    
    @classmethod
    def get_button_styles(cls, theme=THEME_DARK):
        """All button styles including navigation and action buttons"""
        colors = cls.THEMES[theme]
        
        return f"""
        /* Base button style */
        QPushButton {{
            background-color: {colors['bg_alt']};
            color: {colors['fg']};
            border-radius: 5px;
            padding: 8px 16px;
            border: none;
            font-weight: 500;
        }}
        QPushButton:hover {{
            background-color: {colors['bg_hover']};
        }}
        
        /* Navigation buttons */
        QPushButton#navButton {{
            background-color: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            padding: 8px 5px;
            margin-right: 10px;
            font-weight: 600;
        }}
        QPushButton#navButton:hover {{
            color: {COLOR_GREEN};
        }}
        QPushButton#navButtonActive {{
            background-color: transparent;
            border: none;
            border-bottom: 2px solid {COLOR_GREEN};
            padding: 8px 5px;
            margin-right: 10px;
            font-weight: 600;
            color: {COLOR_GREEN};
        }}
        
        /* Colored action buttons */
        QPushButton#{BTN_GREEN} {{
            background-color: {COLOR_GREEN};
            color: #000000;
            font-weight: bold;
        }}
        QPushButton#{BTN_GREEN}:hover {{
            background-color: #8affce;
            color: #000000;
        }}
        
        QPushButton#{BTN_RED} {{
            background-color: {COLOR_RED};
            color: #000000;
            font-weight: bold;
        }}
        QPushButton#{BTN_RED}:hover {{
            background-color: #ff9e9e;
            color: #000000;
        }}
        
        QPushButton#{BTN_BLUE} {{
            background-color: {COLOR_BLUE};
            color: #000000;
            font-weight: bold;
        }}
        QPushButton#{BTN_BLUE}:hover {{
            background-color: #c4f5ff;
            color: #000000;
        }}
        
        /* Small action buttons for job tables */
        QPushButton#submitBtn {{
            background-color: {COLOR_GREEN};
            border: none;
            border-radius: 14px;
            min-width: 30px;
            min-height: 30px;
            max-width: 30px;
            max-height: 30px;
            padding: 0px;
        }}
        
        QPushButton#stopBtn {{
            background-color: {COLOR_PURPLE};
            border: none;
            border-radius: 14px;
            min-width: 30px;
            min-height: 30px;
            max-width: 30px;
            max-height: 30px;
            padding: 0px;
        }}
        
        QPushButton#cancelBtn {{
            background-color: {COLOR_RED};
            border: none;
            border-radius: 14px;
            min-width: 30px;
            min-height: 30px;
            max-width: 30px;
            max-height: 30px;
            padding: 0px;
        }}
        
        QPushButton#logsBtn {{
            background-color: #6DB8E8;
            border: none;
            border-radius: 14px;
            min-width: 30px;
            min-height: 30px;
            max-width: 30px;
            max-height: 30px;
            padding: 0px;
        }}
        
        QPushButton#duplicateBtn {{
            background-color: {COLOR_ORANGE};
            border: none;
            border-radius: 14px;
            min-width: 30px;
            min-height: 30px;
            max-width: 30px;
            max-height: 30px;
            padding: 0px;
        }}
        
        QPushButton#modifyBtn {{
            background-color: #6272a4;
            border: none;
            border-radius: 14px;
            min-width: 30px;
            min-height: 30px;
            max-width: 30px;
            max-height: 30px;
            padding: 0px;
        }}
        """
    
    @classmethod
    def get_input_styles(cls, theme=THEME_DARK):
        """Input fields and form controls"""
        colors = cls.THEMES[theme]
        
        return f"""
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QTimeEdit {{
            background-color: {colors['bg_alt']};
            color: {colors['fg']};
            border-radius: 5px;
            padding: 8px;
            border: 1px solid {colors['border']};
            font-size: 14px;
            selection-background-color: {COLOR_BLUE};
        }}
        QLineEdit:hover, QTextEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QTimeEdit:hover {{
            border: 1px solid {COLOR_BLUE};
        }}
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus {{
            border: 1px solid {COLOR_BLUE};
            background-color: {colors['bg']};
        }}
        
        /* Spin box arrows */
        QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button, QTimeEdit::up-button, QTimeEdit::down-button {{
            background-color: {colors['border']};
            border-radius: 2px;
        }}
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QTimeEdit::up-arrow {{
            background-color: transparent;
            image: url({os.path.join(script_dir, "src_static", "up_arrow.svg").replace('\\', '/')});
            width: 10px;
            height: 10px;
        }}
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QTimeEdit::down-arrow {{
            background-color: transparent;
            image: url({os.path.join(script_dir, "src_static", "down_arrow.svg").replace('\\', '/')});
            width: 10px;
            height: 10px;
        }}
        """
    
    @classmethod
    def get_table_styles(cls, theme=THEME_DARK):
        """Table and list styles"""
        colors = cls.THEMES[theme]
        
        return f"""
        QTableWidget {{
            background-color: {colors['bg']};
            color: {colors['fg']};
            selection-background-color: {colors['bg']};
            selection-color: {colors['fg']};
            gridline-color: {colors['bg']};
            border: 1px solid {colors['border']};
            border-radius: 14px;
            font-size: 14px;
            show-decoration-selected: 1;
            padding-top: 5px;
        }}
        
        QTableWidget::item {{
            background-color: {colors['bg_alt']};
            border: 0px solid {colors['border']};
            border-radius: 14px;
            margin-top: 2px;
            margin-bottom: 2px;
            padding: 5px;
        }}
        
        QTableWidget::item:hover {{
            background-color: {colors['bg_hover']};
        }}
        
        QHeaderView::section {{
            background-color: {colors['bg_alt']};
            color: {colors['fg']};
            padding: 6px;
            border: 0px solid {colors['border']};
            border-bottom: 2px solid {COLOR_BLUE};
            font-weight: bold;
            border-radius: 14px;
        }}
        
        /* List views */
        QListView {{
            background-color: {colors['bg_alt']};
            color: {colors['fg']};
            border: 1px solid {colors['border']};
            border-radius: 4px;
            padding: 4px;
            selection-background-color: {COLOR_BLUE};
        }}
        QListView::item {{
            padding: 6px 8px;
        }}
        QListView::item:hover {{
            background-color: {colors['bg_hover']};
        }}
        QListView::item:selected {{
            background-color: {COLOR_BLUE};
            color: #000000;
        }}
        """
    
    @classmethod
    def get_combobox_styles(cls, theme=THEME_DARK):
        """Combobox and dropdown styles"""
        colors = cls.THEMES[theme]
        
        return f"""
        QComboBox {{
            background-color: {colors['bg_alt']};
            color: {colors['fg']};
            border-radius: 5px;
            padding: 8px;
            border: 1px solid {colors['border']};
            min-width: 6em;
            font-size: 14px;
        }}
        QComboBox:hover {{
            border: 1px solid {COLOR_BLUE};
        }}
        QComboBox::drop-down {{
            border: 0px;
            background-color: {colors['border']};
            width: 24px;
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
        }}
        QComboBox::down-arrow {{
            width: 14px;
            height: 14px;
            image: url({os.path.join(script_dir, "src_static", "down_arrow.svg").replace('\\', '/')});
        }}
        QComboBox QAbstractItemView {{
            background-color: {colors['bg_alt']};
            color: {colors['fg']};
            selection-background-color: {colors['bg_hover']};
            border: 1px solid {colors['border']};
            border-radius: 5px;
            padding: 5px;
        }}
        """
    
    @classmethod
    def get_checkbox_styles(cls, theme=THEME_DARK):
        """Checkbox styles"""
        colors = cls.THEMES[theme]
        
        return f"""
        QCheckBox {{
            color: {colors['fg']};
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 2px;
            border: 1px solid {colors['border']};
            background-color: {colors['bg_alt']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {COLOR_GREEN};
            border: 1px solid {COLOR_GREEN};
            image: url({os.path.join(script_dir, "src_static", "check.svg").replace('\\', '/')});
        }}
        """
    
    @classmethod
    def get_groupbox_styles(cls, theme=THEME_DARK):
        """Group box styles"""
        colors = cls.THEMES[theme]
        
        return f"""
        QGroupBox {{
            border: 2px solid {colors['border']};
            border-radius: 8px;
            margin-top: 10px;
            font-size: 16px;
            font-weight: bold;
            color: {colors['fg']};
            padding: 1em 0em 0.5em 0em;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
            background-color: {colors['bg']};
            color: {colors['fg']};
            margin-left: 5px;
        }}
        
        /* Checkable group boxes */
        QGroupBox::indicator {{
            width: 16px;
            height: 16px;
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 15px;
        }}
        QGroupBox::indicator:unchecked {{
            background-color: {COLOR_RED};
            border: 2px solid {COLOR_RED};
            border-radius: 3px;
            image: url({os.path.join(script_dir, "src_static", "err.svg").replace('\\', '/')});
        }}
        QGroupBox::indicator:checked {{
            background-color: #0ab836;
            border: 2px solid #0ab836;
            border-radius: 3px;
            image: url({os.path.join(script_dir, "src_static", "checkmark.svg").replace('\\', '/')});
        }}
        """
    
    @classmethod
    def get_tab_styles(cls, theme=THEME_DARK):
        """Tab widget styles"""
        colors = cls.THEMES[theme]
        
        return f"""
        QTabWidget::pane {{
            border: 1px solid {colors['border']};
            background-color: {colors['bg']};
            border-radius: 4px;
        }}
        QTabWidget::tab-bar {{
            left: 5px;
        }}
        QTabBar::tab {{
            background-color: {colors['bg_alt']};
            color: {colors['fg']};
            padding: 8px 16px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
            border: 1px solid {colors['border']};
            border-bottom-color: {colors['border']};
        }}
        QTabBar::tab:selected {{
            background-color: {COLOR_BLUE};
            color: #000000;
            font-weight: bold;
            border-color: {COLOR_BLUE};
            border-bottom-color: {colors['bg']};
        }}
        QTabBar::tab:hover:!selected {{
            background-color: {colors['bg_hover']};
        }}
        QTabBar::tab:!selected {{
            margin-top: 2px;
        }}
        """
    
    @classmethod
    def get_progressbar_styles(cls, theme=THEME_DARK):
        """Progress bar styles"""
        colors = cls.THEMES[theme]
        
        return f"""
        QProgressBar {{
            border: 1px solid {colors['border']};
            border-radius: 3px;
            background-color: {colors['bg_alt']};
            text-align: center;
            color: {colors['fg']};
            font-size: 10pt;
        }}
        QProgressBar::chunk {{
            background-color: {COLOR_BLUE};
            border-radius: 2px;
        }}
        
        /* Special progress bars for CPU/RAM usage */
        QProgressBar#cpuUsageBar::chunk[crit="true"] {{
            background-color: {BLOCK_COLOR_MAP['high-constraint-ram_cpu']};
        }}
        QProgressBar#cpuUsageBar::chunk[warn="true"] {{
            background-color: {BLOCK_COLOR_MAP['mid-constraint-ram_cpu']};
        }}
        QProgressBar#ramUsageBar::chunk[crit="true"] {{
            background-color: {BLOCK_COLOR_MAP['high-constraint-ram_cpu']};
        }}
        QProgressBar#ramUsageBar::chunk[warn="true"] {{
            background-color: {BLOCK_COLOR_MAP['mid-constraint-ram_cpu']};
        }}
        """
    
    @classmethod
    def get_scrollbar_styles(cls, theme=THEME_DARK):
        """Scrollbar styles"""
        colors = cls.THEMES[theme]
        
        return f"""
        QScrollBar:vertical {{
            border: none;
            background: {colors['bg_alt']};
            width: 10px;
            margin: 0px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background: {colors['border']};
            min-height: 20px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {COLOR_BLUE};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        
        QScrollBar:horizontal {{
            border: none;
            background: {colors['bg_alt']};
            height: 10px;
            margin: 0px;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal {{
            background: {colors['border']};
            min-width: 20px;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {COLOR_BLUE};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
        """
    
    @classmethod
    def get_cluster_status_styles(cls, theme=THEME_DARK):
        """Cluster status widget specific styles"""
        colors = cls.THEMES[theme]
        
        return f"""
        /* Section titles */
        QLabel#sectionTitle {{
            font-size: 14pt;
            font-weight: bold;
            margin-bottom: 8px;
            color: {colors['fg']};
        }}
        
        /* Separators */
        QFrame#sectionSeparator {{
            background-color: {colors['border']};
            min-height: 1px;
            max-height: 1px;
            margin-top: 8px;
            margin-bottom: 8px;
        }}
        QFrame#verticalSeparator {{
            background-color: {colors['border']};
            min-width: 1px;
            max-width: 1px;
            margin-left: 10px;
            margin-right: 10px;
        }}
        
        /* Colored blocks for node status */
        QWidget#coloredBlock {{
            border-radius: 2px;
        }}
        QWidget#coloredBlock[data-state="available"] {{
            background-color: transparent;
            border: 1px solid {BLOCK_COLOR_MAP['available']};
        }}
        QWidget#coloredBlock[data-state="mid-constraint"] {{
            background-color: transparent;
            border: 1px solid {BLOCK_COLOR_MAP['mid-constraint']};
        }}
        QWidget#coloredBlock[data-state="high-constraint"] {{
            background-color: transparent;
            border: 1px solid {BLOCK_COLOR_MAP['high-constraint']};
        }}
        QWidget#coloredBlock[data-state="used"] {{
            background-color: {BLOCK_COLOR_MAP['used']};
            border: 1px solid {BLOCK_COLOR_MAP['used']};
        }}
        QWidget#coloredBlock[data-state="unavailable"] {{
            background-color: {BLOCK_COLOR_MAP['unavailable']};
            border: 1px solid {BLOCK_COLOR_MAP['unavailable']};
        }}
        QWidget#coloredBlock[data-state="stud_used"] {{
            background-color: {BLOCK_COLOR_MAP['stud_used']};
            border: 1px solid {BLOCK_COLOR_MAP['stud_used']};
        }}
        QWidget#coloredBlock[data-state="prod_used"] {{
            background-color: {BLOCK_COLOR_MAP['prod_used']};
            border: 1px solid {BLOCK_COLOR_MAP['prod_used']};
        }}
        """
    
    @classmethod
    def get_dialog_styles(cls, theme=THEME_DARK):
        """Dialog specific styles"""
        colors = cls.THEMES[theme]
        
        return f"""
        QDialog {{
            background-color: {colors['bg']};
            color: {colors['fg']};
        }}
        """
    
    @classmethod
    def get_job_action_container_styles(cls):
        """Styles for job action button containers"""
        return """
        QWidget#actionContainer {
            background: transparent;
        }
        """
    
    @classmethod
    def get_complete_stylesheet(cls, theme=THEME_DARK):
        """Get complete stylesheet for the application"""
        stylesheet = ""
        stylesheet += cls.get_main_window_style(theme)
        stylesheet += cls.get_button_styles(theme)
        stylesheet += cls.get_input_styles(theme)
        stylesheet += cls.get_table_styles(theme)
        stylesheet += cls.get_combobox_styles(theme)
        stylesheet += cls.get_checkbox_styles(theme)
        stylesheet += cls.get_groupbox_styles(theme)
        stylesheet += cls.get_tab_styles(theme)
        stylesheet += cls.get_progressbar_styles(theme)
        stylesheet += cls.get_scrollbar_styles(theme)
        stylesheet += cls.get_cluster_status_styles(theme)
        stylesheet += cls.get_dialog_styles(theme)
        stylesheet += cls.get_job_action_container_styles()
        
        return stylesheet

def get_dark_theme_stylesheet():
    """Get dark theme stylesheet - for backward compatibility"""
    return AppStyles.get_complete_stylesheet(THEME_DARK)

def get_light_theme_stylesheet():
    """Get light theme stylesheet - for backward compatibility"""
    return AppStyles.get_complete_stylesheet(THEME_LIGHT)