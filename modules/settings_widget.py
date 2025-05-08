from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QComboBox, QFrame, QSizePolicy, QStackedWidget, QFormLayout, QGroupBox,
    QTextEdit, QSpinBox, QFileDialog, QProgressBar, QMessageBox, QGridLayout, QScrollArea
)
from PyQt6.QtGui import QIcon, QColor, QPalette, QFont, QPixmap, QMovie
from PyQt6.QtCore import Qt, QSize, QTimer, QSettings
from modules.defaults import *
from utils import get_dark_theme_stylesheet, get_light_theme_stylesheet


class SettingsWidget(QWidget):
    def __init__(self, parent=..., flags=...):
        super().__init__()
        self.themes = {
            THEME_DARK: get_dark_theme_stylesheet(),
            THEME_LIGHT: get_light_theme_stylesheet(),
        }
        self.current_theme = THEME_DARK
        settings_layout = QVBoxLayout(self)
        settings_layout.setContentsMargins(25, 25, 25, 25)

        # Title
        settings_label = QLabel("Application Settings")
        settings_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        settings_layout.addWidget(settings_label)

        # Appearance section
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)
        appearance_layout.setSpacing(10)
        appearance_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        widgets_layout = QHBoxLayout()

        # Theme combo
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(self.themes.keys())
        self.theme_combo.setCurrentText(self.current_theme)

        self.theme_combo.setMaximumWidth(150)
        widgets_layout.addWidget(QLabel("UI Theme:"))
        widgets_layout.addWidget(self.theme_combo)
        widgets_layout.addStretch()  # Add stretch to push widgets to the left

        # Add the horizontal layout to the appearance layout
        appearance_layout.addRow("", widgets_layout)
        self.jobs_queue_options_group = QGroupBox("Jobs Queue Format")
        jobs_queue_layout = QGridLayout(self.jobs_queue_options_group)

        for i, label in enumerate(JOB_QUEUE_FIELDS):
            if label:
                checkbox = QCheckBox(label)
                checkbox.setObjectName(label)
                row = i // 3
                col = i % 3
                jobs_queue_layout.addWidget(checkbox, row, col)

        # Save Button
        self.save_appearance_btn = QPushButton("Save Appearence Settings")
        self.save_appearance_btn.setObjectName(BTN_GREEN)
        self.save_appearance_btn.setMaximumWidth(250)
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        jobs_queue_layout.addWidget(self.save_appearance_btn, row + 1, col + 1)
        appearance_layout.addRow(self.jobs_queue_options_group)

        settings_layout.addWidget(appearance_group)
        # --- SLURM Connection Settings ---
        connection_group = QGroupBox("SLURM Connection (Example)")
        connection_group.setMinimumHeight(150)
        connection_layout = QFormLayout(connection_group)
        self.cluster_address = QLineEdit()
        self.cluster_address.setClearButtonEnabled(True)
        connection_layout.addRow("Cluster Address:", self.cluster_address)
        self.username = QLineEdit()
        self.username.setClearButtonEnabled(True)
        connection_layout.addRow("Username:", self.username)

        # Replace SSH key with password field
        self.password = QLineEdit()
        self.password.setClearButtonEnabled(True)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)  # Correct way to set password mode
        connection_layout.addRow("Password:", self.password)

        self.connection_settings_btn = QPushButton("Save connection settings")
        self.connection_settings_btn.setObjectName(BTN_GREEN)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.connection_settings_btn)
        connection_layout.addRow(button_layout)
        settings_layout.addWidget(connection_group)

        # --- Notifications Section ---
        notifications_group = QGroupBox("Notifications")
        notifications_layout = QVBoxLayout(notifications_group)
        notifications_layout.setSpacing(10)
        self.desktop_notify_check = QCheckBox("Enable Desktop Notifications")
        self.desktop_notify_check.setChecked(True)
        self.email_notify_check = QCheckBox("Send Email Notifications (if email provided in job)")
        self.email_notify_check.setChecked(True)
        self.sound_notify_check = QCheckBox("Play Sound on Job Completion/Failure")
        notifications_layout.addWidget(self.desktop_notify_check)
        notifications_layout.addWidget(self.email_notify_check)
        notifications_layout.addWidget(self.sound_notify_check)
        settings_layout.addWidget(notifications_group)

        # --- Save Button ---
        self.save_button = QPushButton("Save Settings")
        self.save_button.setObjectName(BTN_GREEN)
        self.save_button.setIcon(QIcon())  # Placeholder icon

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        settings_layout.addLayout(button_layout)

        settings_layout.addStretch()  # Pushes settings to the top
