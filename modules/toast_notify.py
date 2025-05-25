"""
Improved Toast Notification System for SlurmAIO
A modern, properly styled toast notification implementation
"""

from enum import Enum
import os
from modules.defaults import *
from utils import script_dir


class ToastType(Enum):
    """Types of toast notifications"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class ToastManager:
    """Singleton manager for toast notifications"""
    _instance = None
    _toasts = []
    _max_toasts = 5
    _spacing = 15
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
    
    @classmethod
    def show_toast(cls, parent, title, message, toast_type=ToastType.INFO, duration=4000, closable=True):
        """Show a toast notification"""
        manager = cls()
        toast = ToastWidget(parent, title, message, toast_type, duration, closable)
        manager._add_toast(toast)
        return toast
    
    def _add_toast(self, toast):
        """Add a toast to the manager and position it"""
        if len(self._toasts) >= self._max_toasts:
            # Remove oldest toast
            old_toast = self._toasts.pop(0)
            old_toast.hide_toast()
        
        self._toasts.append(toast)
        toast.closed.connect(lambda: self._remove_toast(toast))
        self._position_toasts()
        toast.show_toast()
    
    def _remove_toast(self, toast):
        """Remove a toast from the manager"""
        if toast in self._toasts:
            self._toasts.remove(toast)
            self._position_toasts()
    
    def _position_toasts(self):
        """Position all toasts in bottom-right corner"""
        if not self._toasts:
            return
        
        # Get the main window to position relative to it
        parent = self._toasts[0].parent()
        while parent and not hasattr(parent, 'geometry'):
            parent = parent.parent()
        
        if not parent:
            return
        
        # Get parent geometry
        parent_geometry = parent.geometry()
        toast_width = 380
        margin = 20
        
        # Start from bottom-right corner
        x = parent_geometry.width() - toast_width - margin
        y = parent_geometry.height() - margin
        
        # Position each toast, stacking upwards
        for toast in reversed(self._toasts):
            toast_height = toast.sizeHint().height()
            y -= toast_height
            
            # Convert to global coordinates
            global_pos = parent.mapToGlobal(QPoint(x, y))
            toast.move(global_pos)
            
            # Add spacing for next toast
            y -= self._spacing


class ToastWidget(QWidget):
    """Individual toast notification widget with modern styling"""
    
    closed = pyqtSignal()
    
    def __init__(self, parent, title, message, toast_type=ToastType.INFO, duration=4000, closable=True):
        super().__init__(parent)
        self.toast_type = toast_type
        self.duration = duration
        self.closable = closable
        self.is_visible = False
        
        # Set window properties for proper overlay behavior
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
        self._setup_ui(title, message)
        self._apply_modern_styles()
        self._setup_animations()
        self._add_shadow_effect()
        
        # Auto-hide timer
        if duration > 0:
            QTimer.singleShot(duration, self.hide_toast)
    
    def _setup_ui(self, title, message):
        """Setup the UI components with modern layout"""
        # Main container with proper margins
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Content container
        self.content_frame = QFrame()
        self.content_frame.setObjectName("toastContent")
        
        # Main content layout
        content_layout = QHBoxLayout(self.content_frame)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(15)
        
        # Icon container
        icon_container = QWidget()
        icon_container.setFixedSize(32, 32)
        icon_layout = QHBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_icon()
        icon_layout.addWidget(self.icon_label)
        
        content_layout.addWidget(icon_container)
        
        # Text content container
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)
        
        # Title
        self.title_label = QLabel(title)
        self.title_label.setObjectName("toastTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        text_layout.addWidget(self.title_label)
        
        # Message
        if message.strip():  # Only add message if it's not empty
            self.message_label = QLabel(message)
            self.message_label.setObjectName("toastMessage")
            self.message_label.setWordWrap(True)
            self.message_label.setFont(QFont("Inter", 11))
            text_layout.addWidget(self.message_label)
        
        content_layout.addWidget(text_container, 1)
        
        # Close button
        if self.closable:
            close_container = QWidget()
            close_container.setFixedSize(32, 32)
            close_layout = QHBoxLayout(close_container)
            close_layout.setContentsMargins(0, 0, 0, 0)
            
            self.close_button = QPushButton("×")
            self.close_button.setObjectName("toastCloseBtn")
            self.close_button.setFixedSize(24, 24)
            self.close_button.clicked.connect(self.hide_toast)
            close_layout.addWidget(self.close_button)
            
            content_layout.addWidget(close_container)
        
        main_layout.addWidget(self.content_frame)
        
        # Progress indicator
        if self.duration > 0:
            self.progress_frame = QFrame()
            self.progress_frame.setObjectName("toastProgress")
            self.progress_frame.setFixedHeight(4)
            main_layout.addWidget(self.progress_frame)
    
    def _set_icon(self):
        """Set the appropriate icon with proper styling"""
        # Icon configuration for each type
        icon_config = {
            ToastType.INFO: {"char": "ℹ", "color": "#2196F3"},
            ToastType.SUCCESS: {"char": "✓", "color": COLOR_GREEN},
            ToastType.WARNING: {"char": "⚠", "color": COLOR_ORANGE},
            ToastType.ERROR: {"char": "✗", "color": COLOR_RED}
        }
        
        config = icon_config.get(self.toast_type, icon_config[ToastType.INFO])
        
        # Try to load SVG icon first
        icon_files = {
            ToastType.INFO: "info.svg",
            ToastType.SUCCESS: "ok.svg",
            ToastType.WARNING: "warning.svg",
            ToastType.ERROR: "err.svg"
        }
        
        icon_file = icon_files.get(self.toast_type, "info.svg")
        icon_path = os.path.join(script_dir, "src_static", icon_file)
        
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            scaled_pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.icon_label.setPixmap(scaled_pixmap)
        else:
            # Fallback to Unicode character
            self.icon_label.setText(config["char"])
            self.icon_label.setStyleSheet(f"""
                color: {config["color"]};
                font-size: 18px;
                font-weight: bold;
                background: transparent;
            """)
    
    def _apply_modern_styles(self):
        """Apply modern, clean styles based on SlurmAIO theme"""
        # Color schemes that match your existing dark theme
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
        
        scheme = schemes[self.toast_type]
        
        # Main toast styling
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
    
    def _add_shadow_effect(self):
        """Add subtle shadow effect"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.content_frame.setGraphicsEffect(shadow)
    
    def _setup_animations(self):
        """Setup smooth show/hide animations"""
        # Slide animation
        self.slide_animation = QPropertyAnimation(self, b"pos")
        self.slide_animation.setDuration(400)
        self.slide_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Opacity animation
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(400)
        self.opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Progress bar animation
        if hasattr(self, 'progress_frame') and self.duration > 0:
            self.progress_animation = QPropertyAnimation(self.progress_frame, b"geometry")
            self.progress_animation.setDuration(self.duration)
            self.progress_animation.setEasingCurve(QEasingCurve.Type.Linear)
            
            # Set up progress bar geometry animation
            progress_rect = self.progress_frame.geometry()
            start_rect = QRect(progress_rect.x(), progress_rect.y(), progress_rect.width(), progress_rect.height())
            end_rect = QRect(progress_rect.x(), progress_rect.y(), 0, progress_rect.height())
            
            self.progress_animation.setStartValue(start_rect)
            self.progress_animation.setEndValue(end_rect)
    
    def show_toast(self):
        """Show the toast with smooth animation"""
        if self.is_visible:
            return
            
        self.is_visible = True
        super().show()
        
        # Get current position for animation
        current_pos = self.pos()
        
        # Start from right edge (slide in from right)
        start_pos = QPoint(current_pos.x() + 400, current_pos.y())
        end_pos = current_pos
        
        # Set initial state
        self.move(start_pos)
        self.setWindowOpacity(0.0)
        
        # Setup and start slide animation
        self.slide_animation.setStartValue(start_pos)
        self.slide_animation.setEndValue(end_pos)
        self.slide_animation.start()
        
        # Setup and start opacity animation
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.start()
        
        # Start progress animation if available
        if hasattr(self, 'progress_animation'):
            QTimer.singleShot(500, self.progress_animation.start)  # Delay progress start slightly
    
    def hide_toast(self):
        """Hide the toast with smooth animation"""
        if not self.is_visible:
            return
            
        self.is_visible = False
        
        # Get current position
        current_pos = self.pos()
        end_pos = QPoint(current_pos.x() + 400, current_pos.y())
        
        # Setup slide out animation
        self.slide_animation.setStartValue(current_pos)
        self.slide_animation.setEndValue(end_pos)
        self.slide_animation.finished.connect(self._on_hide_finished)
        self.slide_animation.start()
        
        # Setup opacity animation
        self.opacity_animation.setStartValue(1.0)
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.start()
    
    def _on_hide_finished(self):
        """Called when hide animation finishes"""
        self.hide()
        self.closed.emit()
        self.deleteLater()
    
    def mousePressEvent(self, event):
        """Handle mouse clicks - click anywhere to dismiss"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.hide_toast()
        super().mousePressEvent(event)


# Convenience functions to replace QMessageBox calls
def show_info_toast(parent, title, message="", duration=4000):
    """Show an info toast notification"""
    return ToastManager.show_toast(parent, title, message, ToastType.INFO, duration)

def show_success_toast(parent, title, message="", duration=4000):
    """Show a success toast notification"""
    return ToastManager.show_toast(parent, title, message, ToastType.SUCCESS, duration)

def show_warning_toast(parent, title, message="", duration=5000):
    """Show a warning toast notification"""
    return ToastManager.show_toast(parent, title, message, ToastType.WARNING, duration)

def show_error_toast(parent, title, message="", duration=6000):
    """Show an error toast notification"""
    return ToastManager.show_toast(parent, title, message, ToastType.ERROR, duration)

def show_critical_toast(parent, title, message="", duration=8000):
    """Show a critical error toast notification"""
    return ToastManager.show_toast(parent, title, message, ToastType.ERROR, duration)