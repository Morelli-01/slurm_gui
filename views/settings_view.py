from pathlib import Path
from functools import partial

from core.event_bus import Events, get_event_bus
from core.defaults import *
from core.style import AppStyles
from utils import settings_path


class SettingsView(QWidget):
    """View: Handles UI presentation."""

    discord_test_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.event_bus = get_event_bus()
        self._job_queue_checkboxes = []
        self._is_loading_settings = False
        self._setup_ui()
        self._connect_signals()
        self.load_settings()

    def _setup_ui(self):
        self.setObjectName("settingsView")
        style = AppStyles.get_complete_stylesheet(THEME_DARK)
        style += f"""
        QWidget#settingsContent {{
            background-color: transparent;
        }}
        QLabel#settingsPageTitle {{
            font-size: 22px;
            font-weight: 700;
            color: {COLOR_DARK_FG};
        }}
        QLabel#settingsPageSubtitle {{
            font-size: 13px;
            color: {COLOR_GRAY};
            margin-bottom: 4px;
        }}
        QLabel#settingsSectionHint {{
            color: {COLOR_GRAY};
            font-size: 12px;
        }}
        QLabel#settingsCounter {{
            color: {COLOR_GRAY};
            font-size: 12px;
            font-weight: 600;
        }}
        QLineEdit#settingsColumnFilter {{
            min-height: 34px;
        }}
        """
        self.setStyleSheet(style)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        main_layout.addWidget(scroll)

        content = QWidget()
        content.setObjectName("settingsContent")
        content.setMinimumWidth(700)
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("settingsPageTitle")
        subtitle = QLabel("Manage connection, queue display, and notification behavior.")
        subtitle.setObjectName("settingsPageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self._setup_connection_section(layout)
        self._setup_display_section(layout)
        self._setup_notifications_section(layout)

        layout.addStretch(1)

    def _setup_connection_section(self, layout):
        conn_group = QGroupBox("SLURM Connection")
        conn_layout = QFormLayout(conn_group)
        conn_layout.setSpacing(10)
        conn_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        conn_hint = QLabel("Credentials are saved locally and synced to remote settings when connected.")
        conn_hint.setObjectName("settingsSectionHint")
        conn_hint.setWordWrap(True)
        conn_layout.addRow(conn_hint)

        self.cluster_address = QLineEdit()
        self.cluster_address.setFixedHeight(34)
        self.cluster_address.setPlaceholderText("cluster.example.com")
        conn_layout.addRow("Address:", self.cluster_address)

        self.username = QLineEdit()
        self.username.setFixedHeight(34)
        self.username.setPlaceholderText("username")
        conn_layout.addRow("Username:", self.username)

        password_row = QWidget()
        password_layout = QHBoxLayout(password_row)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(6)

        self.password = QLineEdit()
        self.password.setFixedHeight(34)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("password")
        password_layout.addWidget(self.password, 1)

        self.show_password_btn = QPushButton("Show")
        self.show_password_btn.setObjectName(BTN_BLUE)
        self.show_password_btn.setCheckable(True)
        self.show_password_btn.setFixedSize(80, 34)
        password_layout.addWidget(self.show_password_btn)
        conn_layout.addRow("Password:", password_row)

        actions_row = QWidget()
        actions_layout = QHBoxLayout(actions_row)
        actions_layout.setContentsMargins(0, 4, 0, 0)
        actions_layout.setSpacing(8)

        self.connection_settings_btn = QPushButton("Save Connection")
        self.connection_settings_btn.setObjectName(BTN_GREEN)
        self.connection_settings_btn.setFixedWidth(180)
        actions_layout.addWidget(self.connection_settings_btn)

        self.reload_settings_btn = QPushButton("Reload")
        self.reload_settings_btn.setObjectName(BTN_BLUE)
        self.reload_settings_btn.setFixedWidth(120)
        actions_layout.addWidget(self.reload_settings_btn)
        actions_layout.addStretch(1)
        conn_layout.addRow("", actions_row)

        layout.addWidget(conn_group)

    def _setup_display_section(self, layout):
        display_group = QGroupBox("Display Options")
        display_layout = QVBoxLayout(display_group)
        display_layout.setSpacing(10)

        hint = QLabel("Choose which columns are visible in the Job Queue table.")
        hint.setObjectName("settingsSectionHint")
        display_layout.addWidget(hint)

        controls_row = QWidget()
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self.column_filter_input = QLineEdit()
        self.column_filter_input.setObjectName("settingsColumnFilter")
        self.column_filter_input.setPlaceholderText("Filter columns...")
        self.column_filter_input.setClearButtonEnabled(True)
        controls_layout.addWidget(self.column_filter_input, 1)

        self.columns_select_all_btn = QPushButton("Select All")
        self.columns_select_all_btn.setObjectName(BTN_BLUE)
        controls_layout.addWidget(self.columns_select_all_btn)

        self.columns_clear_all_btn = QPushButton("Clear All")
        self.columns_clear_all_btn.setObjectName(BTN_RED)
        controls_layout.addWidget(self.columns_clear_all_btn)

        self.column_counter_label = QLabel("0/0 selected")
        self.column_counter_label.setObjectName("settingsCounter")
        controls_layout.addWidget(self.column_counter_label)
        display_layout.addWidget(controls_row)

        self.jobs_queue_options_group = QGroupBox("Job Queue Columns")
        queue_layout = QGridLayout(self.jobs_queue_options_group)
        queue_layout.setContentsMargins(10, 10, 10, 10)
        queue_layout.setSpacing(6)

        for i, label in enumerate(JOB_QUEUE_FIELDS):
            checkbox = QCheckBox(label)
            checkbox.setObjectName(label)
            row, col = divmod(i, 2)
            queue_layout.addWidget(checkbox, row, col)
            self._job_queue_checkboxes.append(checkbox)

        display_layout.addWidget(self.jobs_queue_options_group)

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch(1)

        self.save_appearance_btn = QPushButton("Save Display Settings")
        self.save_appearance_btn.setObjectName(BTN_GREEN)
        self.save_appearance_btn.setFixedWidth(250)
        button_layout.addWidget(self.save_appearance_btn)
        display_layout.addWidget(button_row)

        layout.addWidget(display_group)

    def _setup_notifications_section(self, layout):
        notif_group = QGroupBox("Notifications")
        notif_layout = QVBoxLayout(notif_group)
        notif_layout.setSpacing(10)

        hint = QLabel("Configure Discord webhook notifications for job status updates.")
        hint.setObjectName("settingsSectionHint")
        notif_layout.addWidget(hint)

        self.discord_webhook_check = QCheckBox("Enable Discord Notifications")
        notif_layout.addWidget(self.discord_webhook_check)

        self.discord_webhook_url = QLineEdit()
        self.discord_webhook_url.setFixedHeight(34)
        self.discord_webhook_url.setPlaceholderText("https://discord.com/api/webhooks/...")
        notif_layout.addWidget(self.discord_webhook_url)

        notif_buttons = QWidget()
        notif_buttons_layout = QHBoxLayout(notif_buttons)
        notif_buttons_layout.setContentsMargins(0, 0, 0, 0)
        notif_buttons_layout.setSpacing(8)

        self.save_notifications_btn = QPushButton("Save Notifications")
        self.save_notifications_btn.setObjectName(BTN_GREEN)
        self.save_notifications_btn.setFixedWidth(220)
        notif_buttons_layout.addWidget(self.save_notifications_btn)

        self.test_discord_btn = QPushButton("Test Discord Webhook")
        self.test_discord_btn.setObjectName(BTN_BLUE)
        self.test_discord_btn.setFixedWidth(220)
        notif_buttons_layout.addWidget(self.test_discord_btn)
        notif_buttons_layout.addStretch(1)
        notif_layout.addWidget(notif_buttons)

        self.notification_hint_label = QLabel("")
        self.notification_hint_label.setObjectName("settingsSectionHint")
        notif_layout.addWidget(self.notification_hint_label)

        layout.addWidget(notif_group)

    def _connect_signals(self):
        self.connection_settings_btn.clicked.connect(self._emit_connection_save)
        self.reload_settings_btn.clicked.connect(self.load_settings)
        self.show_password_btn.toggled.connect(self._toggle_password_visibility)

        self.save_appearance_btn.clicked.connect(self._emit_display_opt_save)
        self.column_filter_input.textChanged.connect(self._filter_display_options)
        self.columns_select_all_btn.clicked.connect(partial(self._set_all_column_checks, True))
        self.columns_clear_all_btn.clicked.connect(partial(self._set_all_column_checks, False))
        for checkbox in self._job_queue_checkboxes:
            checkbox.stateChanged.connect(self._update_column_selection_status)

        self.save_notifications_btn.clicked.connect(self._emit_noti_opt_save)
        self.test_discord_btn.clicked.connect(self._emit_discord_test)
        self.discord_webhook_check.stateChanged.connect(self._update_notification_controls)
        self.discord_webhook_url.textChanged.connect(self._update_notification_controls)

    def _toggle_password_visibility(self, show: bool):
        self.password.setEchoMode(QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password)
        self.show_password_btn.setText("Hide" if show else "Show")

    def _set_all_column_checks(self, enabled: bool):
        for checkbox in self._job_queue_checkboxes:
            if checkbox.isVisible():
                checkbox.setChecked(enabled)
        self._update_column_selection_status()

    def _filter_display_options(self, text: str):
        needle = text.strip().lower()
        for checkbox in self._job_queue_checkboxes:
            checkbox.setVisible((not needle) or (needle in checkbox.text().lower()))
        self._update_column_selection_status()

    def _update_column_selection_status(self):
        visible = [cb for cb in self._job_queue_checkboxes if cb.isVisible()]
        selected_visible = sum(1 for cb in visible if cb.isChecked())
        total_visible = len(visible)
        total_all = len(self._job_queue_checkboxes)

        if total_visible != total_all:
            self.column_counter_label.setText(f"{selected_visible}/{total_visible} visible")
        else:
            self.column_counter_label.setText(f"{selected_visible}/{total_all} selected")

    def _update_notification_controls(self):
        enabled = self.discord_webhook_check.isChecked()
        self.discord_webhook_url.setEnabled(enabled)
        self.save_notifications_btn.setEnabled(True)

        webhook_url = self.discord_webhook_url.text().strip()
        can_test = enabled and webhook_url.startswith("http")
        self.test_discord_btn.setEnabled(can_test)

        if not enabled:
            self.notification_hint_label.setText("Discord notifications are disabled.")
        elif can_test:
            self.notification_hint_label.setText("Webhook configured. Save to persist changes.")
        else:
            self.notification_hint_label.setText("Enter a valid webhook URL to enable testing.")

    def _emit_connection_save(self):
        settings = {
            "cluster_address": self.cluster_address.text().strip(),
            "username": self.username.text().strip(),
            "password": self.password.text().strip(),
        }
        self.event_bus.emit(
            Events.CONNECTION_SAVE_REQ,
            {"settings": settings},
            source="settings.view",
        )

    def _emit_display_opt_save(self):
        display_settings = {}
        for checkbox in self._job_queue_checkboxes:
            display_settings[checkbox.objectName()] = bool(checkbox.checkState().value)
        self.event_bus.emit(
            Events.DISPLAY_SAVE_REQ,
            data={"display_settings": display_settings},
            source="settings.view",
        )

    def _emit_discord_test(self):
        self.discord_test_requested.emit(self.discord_webhook_url.text().strip())

    def _emit_noti_opt_save(self):
        notification_settings = {
            "discord_enabled": bool(self.discord_webhook_check.checkState().value),
            "discord_webhook_url": self.discord_webhook_url.text().strip(),
        }
        self.event_bus.emit(Events.NOTIF_SAVE_REQ, notification_settings, source="settings.view")

    def load_settings(self):
        self._is_loading_settings = True
        self.settings = QSettings(str(Path(settings_path)), QSettings.Format.IniFormat)

        self.settings.beginGroup("GeneralSettings")
        self.cluster_address.setText(self.settings.value("clusterAddress", ""))
        self.username.setText(self.settings.value("username", ""))
        self.password.setText(self.settings.value("psw", ""))
        self.settings.endGroup()

        for checkbox in self._job_queue_checkboxes:
            checkbox.blockSignals(True)
        self.settings.beginGroup("AppearenceSettings")
        for checkbox in self._job_queue_checkboxes:
            value = self.settings.value(checkbox.objectName(), False, type=bool)
            checkbox.setCheckState(
                Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
            )
        self.settings.endGroup()
        for checkbox in self._job_queue_checkboxes:
            checkbox.blockSignals(False)

        self.discord_webhook_check.blockSignals(True)
        self.discord_webhook_url.blockSignals(True)
        self.settings.beginGroup("NotificationSettings")
        self.discord_webhook_check.setChecked(
            self.settings.value("discord_enabled", False, type=bool)
        )
        self.discord_webhook_url.setText(
            self.settings.value("discord_webhook_url", "", type=str)
        )
        self.settings.endGroup()
        self.discord_webhook_check.blockSignals(False)
        self.discord_webhook_url.blockSignals(False)

        self._update_column_selection_status()
        self._update_notification_controls()
        self._is_loading_settings = False
