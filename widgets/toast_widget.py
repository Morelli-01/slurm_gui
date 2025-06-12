"""
Toast Notification System - MVC Architecture Implementation
Separates data management, UI, and control logic for better maintainability.
"""

import os
from enum import Enum
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from PyQt6.QtCore import (
    QObject, QTimer, QPropertyAnimation, QEasingCurve, QRect, QPoint, QSize, 
    pyqtSignal, Qt
)
from PyQt6.QtGui import QFont, QPixmap, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, 
    QGraphicsDropShadowEffect, QSizePolicy, QApplication
)

from core.defaults import *
from utils import script_dir

# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class ToastType(Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

@dataclass
class ToastData:
    """Data structure representing a toast notification"""
    title: str
    message: str = ""
    toast_type: ToastType = ToastType.INFO
    duration: int = 4000  # milliseconds
    closable: bool = True
    id: Optional[str] = None
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    
    def __post_init__(self):
        if self.id is None:
            self.id = f"toast_{int(self.timestamp * 1000)}"

@dataclass 
class ToastConfiguration:
    """Configuration for toast system"""
    max_toasts: int = 5
    spacing: int = 15
    toast_width: int = 380
    margin: int = 20
    animation_duration: int = 400

# ============================================================================
# MODEL - Data and Business Logic
# ============================================================================

class ToastModel(QObject):
    """
    Model class managing toast data, queue, and configuration.
    Handles toast lifecycle and queue management.
    """
    
    # Data change signals
    toastAdded = pyqtSignal(object)      # ToastData
    toastRemoved = pyqtSignal(str)       # toast_id
    queueChanged = pyqtSignal(list)      # List of ToastData
    configurationChanged = pyqtSignal(object)  # ToastConfiguration
    
    def __init__(self, config: Optional[ToastConfiguration] = None):
        super().__init__()
        self._config = config or ToastConfiguration()
        self._toast_queue: List[ToastData] = []
        
    @property
    def configuration(self) -> ToastConfiguration:
        return self._config
    
    @property
    def toast_queue(self) -> List[ToastData]:
        return self._toast_queue.copy()
    
    def add_toast(self, toast_data: ToastData) -> str:
        """Add a toast to the queue"""
        # Remove oldest toast if queue is full
        while len(self._toast_queue) >= self._config.max_toasts:
            oldest = self._toast_queue.pop(0)
            self.toastRemoved.emit(oldest.id)
            
        self._toast_queue.append(toast_data)
        self.toastAdded.emit(toast_data)
        self.queueChanged.emit(self._toast_queue.copy())
        
        return toast_data.id
    
    def remove_toast(self, toast_id: str) -> bool:
        """Remove a toast from the queue"""
        for i, toast in enumerate(self._toast_queue):
            if toast.id == toast_id:
                self._toast_queue.pop(i)
                self.toastRemoved.emit(toast_id)
                self.queueChanged.emit(self._toast_queue.copy())
                return True
        return False
    
    def get_toast(self, toast_id: str) -> Optional[ToastData]:
        """Get toast data by ID"""
        for toast in self._toast_queue:
            if toast.id == toast_id:
                return toast
        return None
    
    def clear_all_toasts(self):
        """Clear all toasts from queue"""
        toast_ids = [toast.id for toast in self._toast_queue]
        self._toast_queue.clear()
        
        for toast_id in toast_ids:
            self.toastRemoved.emit(toast_id)
        
        self.queueChanged.emit([])
    
    def update_configuration(self, config: ToastConfiguration):
        """Update toast configuration"""
        self._config = config
        self.configurationChanged.emit(config)
        
        # Adjust queue if max_toasts changed
        while len(self._toast_queue) > config.max_toasts:
            oldest = self._toast_queue.pop(0)
            self.toastRemoved.emit(oldest.id)
        
        if self._toast_queue:
            self.queueChanged.emit(self._toast_queue.copy())

# ============================================================================
# VIEW - UI Components and Presentation
# ============================================================================

class ToastView(QWidget):
    """
    View class handling the visual representation of a single toast.
    Manages styling, animations, and visual state.
    """
    
    # UI interaction signals
    closeRequested = pyqtSignal(str)  # toast_id
    clicked = pyqtSignal(str)         # toast_id
    
    def __init__(self, toast_data: ToastData, parent=None):
        super().__init__(parent)
        self.toast_data = toast_data
        self.is_visible = False
        self._setup_window_properties()
        self._setup_ui()
        self._apply_styling()
        self._setup_animations()
        self._add_shadow_effect()
        
    def _setup_window_properties(self):
        """Configure window properties for overlay behavior"""
        self.setWindowFlags(
            Qt.WindowType.Tool |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedWidth(380)

    def _setup_ui(self):
        """Setup the user interface components"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Content frame
        self.content_frame = QFrame()
        self.content_frame.setObjectName("toastContent")
        self.content_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, 
            QSizePolicy.Policy.MinimumExpanding
        )
        
        content_layout = QHBoxLayout(self.content_frame)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(15)
        
        # Icon
        self.icon_container = self._create_icon_container()
        content_layout.addWidget(self.icon_container, 0, Qt.AlignmentFlag.AlignTop)
        
        # Text content
        self.text_container = self._create_text_container()
        content_layout.addWidget(self.text_container, 1)
        
        # Close button
        if self.toast_data.closable:
            self.close_container = self._create_close_container()
            content_layout.addWidget(self.close_container, 0, Qt.AlignmentFlag.AlignTop)
        
        main_layout.addWidget(self.content_frame)
        
        # Progress bar for timed toasts
        if self.toast_data.duration > 0:
            self.progress_frame = QFrame()
            self.progress_frame.setObjectName("toastProgress")
            self.progress_frame.setFixedHeight(4)
            main_layout.addWidget(self.progress_frame)
        
        self.adjustSize()

    def _create_icon_container(self) -> QWidget:
        """Create icon container"""
        container = QWidget()
        container.setFixedSize(32, 32)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_icon()
        
        layout.addWidget(self.icon_label)
        return container

    def _create_text_container(self) -> QWidget:
        """Create text container"""
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # Title
        self.title_label = QLabel(self.toast_data.title)
        self.title_label.setObjectName("toastTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.title_label.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        layout.addWidget(self.title_label, 0, Qt.AlignmentFlag.AlignTop)
        
        # Message
        if self.toast_data.message.strip():
            self.message_label = QLabel(self.toast_data.message)
            self.message_label.setObjectName("toastMessage")
            self.message_label.setWordWrap(True)
            self.message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.message_label.setFont(QFont("Inter", 11))
            self.message_label.setTextFormat(Qt.TextFormat.RichText)
            self.message_label.setOpenExternalLinks(True)
            self.message_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse | 
                Qt.TextInteractionFlag.LinksAccessibleByMouse
            )
            layout.addWidget(self.message_label, 0, Qt.AlignmentFlag.AlignTop)
        
        return container

    def _create_close_container(self) -> QWidget:
        """Create close button container"""
        container = QWidget()
        container.setFixedSize(32, 32)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.close_button = QPushButton("×")
        self.close_button.setObjectName("toastCloseBtn")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(lambda: self.closeRequested.emit(self.toast_data.id))
        
        layout.addWidget(self.close_button)
        return container

    def _set_icon(self):
        """Set appropriate icon based on toast type"""
        icon_config = {
            ToastType.INFO: {"char": "ℹ", "color": "#2196F3"},
            ToastType.SUCCESS: {"char": "✓", "color": COLOR_GREEN},
            ToastType.WARNING: {"char": "⚠", "color": COLOR_ORANGE},
            ToastType.ERROR: {"char": "✗", "color": COLOR_RED}
        }
        
        config = icon_config.get(self.toast_data.toast_type, icon_config[ToastType.INFO])
        
        # Try to load icon from file
        icon_files = {
            ToastType.INFO: "info.svg",
            ToastType.SUCCESS: "ok.svg", 
            ToastType.WARNING: "warning.svg",
            ToastType.ERROR: "err.svg"
        }
        
        icon_file = icon_files.get(self.toast_data.toast_type, "info.svg")
        icon_path = os.path.join(script_dir, "src_static", icon_file)
        
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            scaled_pixmap = pixmap.scaled(
                24, 24, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.icon_label.setPixmap(scaled_pixmap)
        else:
            # Fallback to text icon
            self.icon_label.setText(config["char"])
            self.icon_label.setStyleSheet(f"""
                color: {config["color"]};
                font-size: 18px;
                font-weight: bold;
                background: transparent;
            """)

    def _apply_styling(self):
        """Apply styling based on toast type"""
        schemes = {
            ToastType.INFO: {
                'bg': COLOR_DARK_BG_ALT,
                'border': "#2196F3",
                'title': COLOR_DARK_FG,
                'message': "#CCCCCC",
                'progress': "#2196F3",
                'shadow': "rgba(33, 150, 243, 0.3)"
            },
            ToastType.SUCCESS: {
                'bg': COLOR_DARK_BG_ALT,
                'border': COLOR_GREEN,
                'title': COLOR_DARK_FG,
                'message': "#CCCCCC",
                'progress': COLOR_GREEN,
                'shadow': f"rgba(11, 184, 54, 0.3)"
            },
            ToastType.WARNING: {
                'bg': COLOR_DARK_BG_ALT,
                'border': COLOR_ORANGE,
                'title': COLOR_DARK_FG,
                'message': "#CCCCCC",
                'progress': COLOR_ORANGE,
                'shadow': "rgba(255, 184, 108, 0.3)"
            },
            ToastType.ERROR: {
                'bg': COLOR_DARK_BG_ALT,
                'border': COLOR_RED,
                'title': COLOR_DARK_FG,
                'message': "#CCCCCC",
                'progress': COLOR_RED,
                'shadow': "rgba(241, 50, 50, 0.3)"
            }
        }
        
        scheme = schemes[self.toast_data.toast_type]
        
        self.setStyleSheet(f"""
            QWidget {{
                background: transparent;
            }}
            #toastContent {{
                background-color: {scheme['bg']};
                border: 2px solid {scheme['border']};
                border-radius: 12px;
                margin: 4px;
            }}
            #toastTitle {{
                color: {scheme['title']};
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            }}
            #toastMessage {{
                color: {scheme['message']};
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                line-height: 1.4;
            }}
            #toastCloseBtn {{
                background: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 12px;
                color: {scheme['title']};
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
                margin: 0px;
            }}
            #toastCloseBtn:hover {{
                background: rgba(255, 255, 255, 0.2);
            }}
            #toastCloseBtn:pressed {{
                background: rgba(255, 255, 255, 0.3);
            }}
            #toastProgress {{
                background-color: {scheme['progress']};
                border-radius: 2px;
                margin: 0px 4px 4px 4px;
            }}
        """)

    def _setup_animations(self):
        """Setup animation objects"""
        self.slide_animation = QPropertyAnimation(self, b"pos")
        self.slide_animation.setDuration(400)
        self.slide_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(400)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        if hasattr(self, 'progress_frame') and self.toast_data.duration > 0:
            self.progress_animation = QPropertyAnimation(self.progress_frame, b"geometry")
            self.progress_animation.setDuration(self.toast_data.duration)
            self.progress_animation.setEasingCurve(QEasingCurve.Type.Linear)

    def _add_shadow_effect(self):
        """Add drop shadow effect"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.content_frame.setGraphicsEffect(shadow)

    def sizeHint(self) -> QSize:
        """Calculate preferred size"""
        width = 380
        height = self.content_frame.sizeHint().height() + (8 if hasattr(self, 'progress_frame') else 0)
        return QSize(width, min(height, 400))

    def show_toast(self, target_position: QPoint):
        """Animate toast appearance"""
        if self.is_visible:
            return
            
        self.is_visible = True
        super().show()
        
        # Setup slide animation
        start_pos = QPoint(target_position.x(), target_position.y())
        self.move(start_pos)
        self.setWindowOpacity(0.0)
        
        self.slide_animation.setStartValue(start_pos)
        self.slide_animation.setEndValue(target_position)
        self.slide_animation.start()
        
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.start()
        
        # Start progress animation if applicable
        if hasattr(self, 'progress_animation'):
            QTimer.singleShot(500, self._start_progress_animation)

    def _start_progress_animation(self):
        """Start progress bar animation"""
        if hasattr(self, 'progress_animation'):
            progress_rect = self.progress_frame.geometry()
            start_rect = QRect(progress_rect.x(), progress_rect.y(), 
                             progress_rect.width(), progress_rect.height())
            end_rect = QRect(progress_rect.x(), progress_rect.y(), 
                           0, progress_rect.height())
            
            self.progress_animation.setStartValue(start_rect)
            self.progress_animation.setEndValue(end_rect)
            self.progress_animation.start()

    def hide_toast(self):
        """Animate toast disappearance"""
        if not self.is_visible:
            return
            
        self.is_visible = False
        current_pos = self.pos()
        end_pos = QPoint(current_pos.x() + 400, current_pos.y())
        
        self.slide_animation.setStartValue(current_pos)
        self.slide_animation.setEndValue(end_pos)
        self.slide_animation.finished.connect(self._on_hide_finished)
        self.slide_animation.start()
        
        self.opacity_animation.setStartValue(1.0)
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.start()

    def _on_hide_finished(self):
        """Handle animation completion"""
        self.hide()
        self.deleteLater()

    def mousePressEvent(self, event):
        """Handle mouse clicks"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.toast_data.id)
        super().mousePressEvent(event)

# ============================================================================
# CONTROLLER - Coordination and Business Logic
# ============================================================================

class ToastController(QObject):
    """
    Controller class coordinating between model and views.
    Manages toast lifecycle, positioning, and user interactions.
    """
    
    def __init__(self, model: ToastModel):
        super().__init__()
        self.model = model
        self.active_views: Dict[str, ToastView] = {}
        self.auto_hide_timers: Dict[str, QTimer] = {}
        self._setup_connections()
        
    def _setup_connections(self):
        """Setup signal-slot connections"""
        self.model.toastAdded.connect(self._create_toast_view)
        self.model.toastRemoved.connect(self._remove_toast_view)
        self.model.queueChanged.connect(self._reposition_toasts)
        self.model.configurationChanged.connect(self._handle_config_change)
        
    def _create_toast_view(self, toast_data: ToastData):
        """Create and show a new toast view"""
        view = ToastView(toast_data)
        self.active_views[toast_data.id] = view
        
        # Connect view signals
        view.closeRequested.connect(self._handle_close_request)
        view.clicked.connect(self._handle_toast_click)
        
        # Position and show toast
        position = self._calculate_toast_position(toast_data.id)
        view.show_toast(position)
        
        # Setup auto-hide timer if duration is set
        if toast_data.duration > 0:
            timer = QTimer()
            timer.timeout.connect(lambda: self._auto_hide_toast(toast_data.id))
            timer.setSingleShot(True)
            timer.start(toast_data.duration)
            self.auto_hide_timers[toast_data.id] = timer
            
    def _remove_toast_view(self, toast_id: str):
        """Remove a toast view"""
        if toast_id in self.active_views:
            view = self.active_views[toast_id]
            view.hide_toast()
            del self.active_views[toast_id]
            
        if toast_id in self.auto_hide_timers:
            self.auto_hide_timers[toast_id].stop()
            del self.auto_hide_timers[toast_id]
            
    def _reposition_toasts(self, toast_queue: List[ToastData]):
        """Reposition all active toasts"""
        self._position_all_toasts()
                
    def _position_all_toasts(self):
        """Position all active toasts properly"""
        if not self.active_views:
            return
            
        config = self.model.configuration
        queue = self.model.toast_queue
        
        # Get positioning context
        main_window = self._find_main_window()
        is_window_visible = (
            main_window and main_window.isVisible() and 
            not main_window.isMinimized() and
            main_window.windowState() != Qt.WindowState.WindowMinimized
        )
        
        if is_window_visible and main_window:
            # Position relative to main window
            parent_geometry = main_window.geometry()
            x = parent_geometry.width() - config.toast_width - config.margin
            y = parent_geometry.height() - config.margin
            
            # Position toasts starting from the bottom-right of the window
            for toast_data in reversed(queue):
                if toast_data.id in self.active_views:
                    view = self.active_views[toast_data.id]
                    toast_height = view.sizeHint().height()
                    y -= toast_height
                    global_pos = main_window.mapToGlobal(QPoint(x, y))
                    
                    # Animate to new position if already visible
                    if view.is_visible:
                        view.slide_animation.setStartValue(view.pos())
                        view.slide_animation.setEndValue(global_pos)
                        view.slide_animation.start()
                    else:
                        view.move(global_pos)
                    
                    y -= config.spacing
        else:
            # Position on desktop
            desktop = QApplication.primaryScreen().availableGeometry()
            x = desktop.width() - config.toast_width - config.margin
            y = desktop.height() - config.margin
            
            # Position toasts starting from the bottom-right of the desktop
            for toast_data in reversed(queue):
                if toast_data.id in self.active_views:
                    view = self.active_views[toast_data.id]
                    toast_height = view.sizeHint().height()
                    y -= toast_height
                    
                    # Animate to new position if already visible
                    if view.is_visible:
                        view.slide_animation.setStartValue(view.pos())
                        view.slide_animation.setEndValue(QPoint(x, y))
                        view.slide_animation.start()
                    else:
                        view.move(x, y)
                    
                    y -= config.spacing
                    
    def _calculate_toast_position(self, toast_id: str, index: Optional[int] = None) -> QPoint:
        """Calculate initial position for a new toast"""
        config = self.model.configuration
        
        # Get positioning context
        main_window = self._find_main_window()
        is_window_visible = (
            main_window and main_window.isVisible() and 
            not main_window.isMinimized() and
            main_window.windowState() != Qt.WindowState.WindowMinimized
        )
        
        if is_window_visible and main_window:
            # Position relative to main window
            parent_geometry = main_window.geometry()
            x = parent_geometry.width() - config.toast_width - config.margin
            y = parent_geometry.height() - config.margin
            
            # Calculate Y position based on existing toasts
            queue = self.model.toast_queue
            for toast_data in reversed(queue):
                if toast_data.id == toast_id:
                    break
                if toast_data.id in self.active_views:
                    existing_view = self.active_views[toast_data.id]
                    y -= existing_view.sizeHint().height() + config.spacing
            
            # Subtract this toast's height
            if toast_id in self.active_views:
                view = self.active_views[toast_id]
                y -= view.sizeHint().height()
            
            return main_window.mapToGlobal(QPoint(x, y))
        else:
            # Position on desktop
            desktop = QApplication.primaryScreen().availableGeometry()
            x = desktop.width() - config.toast_width - config.margin
            y = desktop.height() - config.margin
            
            # Calculate Y position based on existing toasts
            queue = self.model.toast_queue
            for toast_data in reversed(queue):
                if toast_data.id == toast_id:
                    break
                if toast_data.id in self.active_views:
                    existing_view = self.active_views[toast_data.id]
                    y -= existing_view.sizeHint().height() + config.spacing
            
            # Subtract this toast's height
            if toast_id in self.active_views:
                view = self.active_views[toast_id]
                y -= view.sizeHint().height()
            
            return QPoint(x, y)
            
    def _find_main_window(self) -> Optional[QWidget]:
        """Find the main application window"""
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, 'geometry') and widget.isVisible():
                return widget
        return None
        
    def _get_average_toast_height(self) -> int:
        """Get average height of active toasts"""
        if not self.active_views:
            return 100  # Default height
            
        total_height = sum(view.sizeHint().height() for view in self.active_views.values())
        return total_height // len(self.active_views)
        
    def _handle_close_request(self, toast_id: str):
        """Handle toast close request"""
        self.model.remove_toast(toast_id)
        
    def _handle_toast_click(self, toast_id: str):
        """Handle toast click"""
        # Close toast on click
        self.model.remove_toast(toast_id)
        
    def _auto_hide_toast(self, toast_id: str):
        """Auto-hide toast after duration"""
        self.model.remove_toast(toast_id)
        
    def _handle_config_change(self, config: ToastConfiguration):
        """Handle configuration changes"""
        # Reposition existing toasts with new configuration
        self._reposition_toasts(self.model.toast_queue)
        
    def show_toast(self, title: str, message: str = "", toast_type: ToastType = ToastType.INFO, 
                   duration: int = 4000, closable: bool = True) -> str:
        """Show a new toast (convenience method)"""
        toast_data = ToastData(
            title=title,
            message=message,
            toast_type=toast_type,
            duration=duration,
            closable=closable
        )
        return self.model.add_toast(toast_data)

# ============================================================================
# MANAGER FACADE - Simplified Interface
# ============================================================================

class ToastManager:
    """
    Singleton manager providing the same interface as the original system.
    Encapsulates the MVC architecture.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.model = ToastModel()
            self.controller = ToastController(self.model)
            self._initialized = True
    
    @classmethod
    def show_toast(cls, parent, title, message="", toast_type=ToastType.INFO, duration=4000, closable=True):
        """Show a toast notification"""
        manager = cls()
        return manager.controller.show_toast(title, message, toast_type, duration, closable)
    
    def clear_all(self):
        """Clear all toasts"""
        self.model.clear_all_toasts()
    
    def update_configuration(self, **kwargs):
        """Update toast configuration"""
        current_config = self.model.configuration
        new_config = ToastConfiguration(
            max_toasts=kwargs.get('max_toasts', current_config.max_toasts),
            spacing=kwargs.get('spacing', current_config.spacing),
            toast_width=kwargs.get('toast_width', current_config.toast_width),
            margin=kwargs.get('margin', current_config.margin),
            animation_duration=kwargs.get('animation_duration', current_config.animation_duration)
        )
        self.model.update_configuration(new_config)

# ============================================================================
# CONVENIENCE FUNCTIONS - Maintaining Original API
# ============================================================================

def show_info_toast(parent, title, message="", duration=4000):
    return ToastManager.show_toast(parent, title, message, ToastType.INFO, duration)

def show_success_toast(parent, title, message="", duration=4000):
    return ToastManager.show_toast(parent, title, message, ToastType.SUCCESS, duration)

def show_warning_toast(parent, title, message="", duration=5000):
    return ToastManager.show_toast(parent, title, message, ToastType.WARNING, duration)

def show_error_toast(parent, title, message="", duration=6000):
    return ToastManager.show_toast(parent, title, message, ToastType.ERROR, duration)

def show_critical_toast(parent, title, message="", duration=8000):
    return ToastManager.show_toast(parent, title, message, ToastType.ERROR, duration)