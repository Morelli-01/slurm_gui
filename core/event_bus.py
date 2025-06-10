"""
EventBus System for SlurmAIO - Centralized Event Management
"""

from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import weakref
import threading
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from modules.data_classes import Job, Project

# ============================================================================
# EVENT TYPES AND DATA CLASSES
# ============================================================================

@dataclass
class BaseEvent:
    """Base class for all events"""
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    
    def __post_init__(self):
        if self.source is None:
            self.source = self.__class__.__name__

# Connection Events
@dataclass
class ConnectionEstablishedEvent(BaseEvent):
    """Emitted when SLURM connection is established"""
    host: str = ""
    user: str = ""

@dataclass
class ConnectionLostEvent(BaseEvent):
    """Emitted when SLURM connection is lost"""
    error_message: str = ""

@dataclass
class ConnectionStatusChangedEvent(BaseEvent):
    """Emitted when connection status changes"""
    is_connected: bool = False
    host: Optional[str] = None

# Job Events
@dataclass
class JobStatusChangedEvent(BaseEvent):
    """Emitted when a job status changes"""
    project: Project
    job: Job
    old_status: str
    new_status: str

@dataclass
class JobUpdatedEvent(BaseEvent):
    """Emitted when job details are updated"""
    project: Project
    job: Job

@dataclass
class JobSubmittedEvent(BaseEvent):
    """Emitted when a job is submitted"""
    project: Project
    job: Job
    old_job_id: str
    new_job_id: str

@dataclass
class JobCreatedEvent(BaseEvent):
    """Emitted when a new job is created"""
    project: Project
    job: Job

@dataclass
class JobDeletedEvent(BaseEvent):
    """Emitted when a job is deleted"""
    project: Project
    job_id: str

# Project Events
@dataclass
class ProjectCreatedEvent(BaseEvent):
    """Emitted when a new project is created"""
    project_name: str

@dataclass
class ProjectSelectedEvent(BaseEvent):
    """Emitted when a project is selected"""
    project: Project

@dataclass
class ProjectStatsChangedEvent(BaseEvent):
    """Emitted when project statistics change"""
    project: Project
    stats: Dict[str, int]

# Data Events
@dataclass
class ClusterDataUpdatedEvent(BaseEvent):
    """Emitted when cluster data is updated"""
    nodes_data: List[Dict[str, Any]]
    jobs_data: List[Dict[str, Any]]

@dataclass
class JobQueueUpdatedEvent(BaseEvent):
    """Emitted when job queue is updated"""
    jobs_data: List[Dict[str, Any]]

# UI Events
@dataclass
class ToastNotificationEvent(BaseEvent):
    """Emitted to show toast notifications"""
    title: str
    message: str = ""
    toast_type: str = "info"  # info, success, warning, error
    duration: int = 4000

@dataclass
class NavigationEvent(BaseEvent):
    """Emitted for navigation changes"""
    destination: str
    data: Optional[Dict[str, Any]] = None

# Settings Events
@dataclass
class SettingsChangedEvent(BaseEvent):
    """Emitted when settings are changed"""
    setting_type: str  # connection, display, notification
    settings: Dict[str, Any]

# ============================================================================
# EVENT BUS IMPLEMENTATION
# ============================================================================

EventType = TypeVar('EventType', bound=BaseEvent)

class EventBus(QObject):
    """
    Central event bus for handling application-wide events.
    Thread-safe singleton implementation.
    """
    
    _instance: Optional['EventBus'] = None
    _lock = threading.Lock()
    
    # Qt signal for cross-thread event emission
    _event_emitted = pyqtSignal(object)
    
    def __new__(cls) -> 'EventBus':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not getattr(self, '_initialized', False):
            super().__init__()
            self._listeners: Dict[Type[BaseEvent], List[weakref.ref]] = {}
            self._event_queue: List[BaseEvent] = []
            self._processing = False
            self._initialized = True
            
            # Connect Qt signal for thread-safe emission
            self._event_emitted.connect(self._process_event_sync)
    
    @classmethod
    def instance(cls) -> 'EventBus':
        """Get the singleton instance"""
        return cls()
    
    def subscribe(self, event_type: Type[EventType], callback: Callable[[EventType], None]) -> None:
        """
        Subscribe to events of a specific type.
        
        Args:
            event_type: Type of event to listen for
            callback: Function to call when event is emitted
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        
        # Use weak references to prevent memory leaks
        if hasattr(callback, '__self__'):
            # Bound method - create weak reference to the object
            weak_callback = weakref.WeakMethod(callback)
        else:
            # Function - create weak reference directly
            weak_callback = weakref.ref(callback)
        
        self._listeners[event_type].append(weak_callback)
    
    def unsubscribe(self, event_type: Type[EventType], callback: Callable[[EventType], None]) -> None:
        """
        Unsubscribe from events of a specific type.
        
        Args:
            event_type: Type of event to stop listening for
            callback: Function to remove from listeners
        """
        if event_type not in self._listeners:
            return
        
        # Find and remove the callback
        to_remove = []
        for i, weak_callback in enumerate(self._listeners[event_type]):
            stored_callback = weak_callback()
            if stored_callback is None or stored_callback == callback:
                to_remove.append(i)
        
        # Remove in reverse order to maintain indices
        for i in reversed(to_remove):
            self._listeners[event_type].pop(i)
    
    def emit(self, event: BaseEvent) -> None:
        """
        Emit an event to all subscribers.
        Thread-safe - can be called from any thread.
        
        Args:
            event: Event instance to emit
        """
        # Use Qt signal for thread-safe emission
        self._event_emitted.emit(event)
    
    def _process_event_sync(self, event: BaseEvent) -> None:
        """
        Process event synchronously on the main thread.
        Called by Qt signal mechanism.
        """
        event_type = type(event)
        
        if event_type not in self._listeners:
            return
        
        # Clean up dead references and call active callbacks
        active_listeners = []
        for weak_callback in self._listeners[event_type]:
            callback = weak_callback()
            if callback is not None:
                active_listeners.append(weak_callback)
                try:
                    callback(event)
                except Exception as e:
                    print(f"Error in event callback for {event_type.__name__}: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Update listeners list with only active callbacks
        self._listeners[event_type] = active_listeners
    
    def emit_sync(self, event: BaseEvent) -> None:
        """
        Emit an event synchronously (only for main thread).
        
        Args:
            event: Event instance to emit
        """
        self._process_event_sync(event)
    
    def clear_listeners(self, event_type: Optional[Type[BaseEvent]] = None) -> None:
        """
        Clear listeners for a specific event type or all listeners.
        
        Args:
            event_type: Specific event type to clear, or None for all
        """
        if event_type is None:
            self._listeners.clear()
        elif event_type in self._listeners:
            self._listeners[event_type].clear()
    
    def get_listener_count(self, event_type: Type[BaseEvent]) -> int:
        """Get number of active listeners for an event type"""
        if event_type not in self._listeners:
            return 0
        
        # Count only active (non-dead) references
        active_count = 0
        for weak_callback in self._listeners[event_type]:
            if weak_callback() is not None:
                active_count += 1
        
        return active_count

# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def emit_event(event: BaseEvent) -> None:
    """Convenience function to emit events"""
    EventBus.instance().emit(event)

def subscribe_to_event(event_type: Type[EventType], callback: Callable[[EventType], None]) -> None:
    """Convenience function to subscribe to events"""
    EventBus.instance().subscribe(event_type, callback)

def unsubscribe_from_event(event_type: Type[EventType], callback: Callable[[EventType], None]) -> None:
    """Convenience function to unsubscribe from events"""
    EventBus.instance().unsubscribe(event_type, callback)

# ============================================================================
# DECORATORS FOR EASY INTEGRATION
# ============================================================================

def event_handler(event_type: Type[EventType]):
    """
    Decorator to automatically register event handlers.
    
    Usage:
        @event_handler(JobStatusChangedEvent)
        def handle_job_status_change(self, event):
            # Handle the event
            pass
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            return func(self, *args, **kwargs)
        
        # Mark function for auto-registration
        wrapper._event_type = event_type
        wrapper._original_func = func
        return wrapper
    
    return decorator

class EventMixin:
    """
    Mixin class that provides automatic event handler registration.
    Classes that inherit from this will automatically register methods
    decorated with @event_handler.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._auto_register_event_handlers()
    
    def _auto_register_event_handlers(self):
        """Automatically register decorated event handlers"""
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, '_event_type') and hasattr(attr, '_original_func'):
                EventBus.instance().subscribe(attr._event_type, attr)

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example usage
    bus = EventBus.instance()
    
    # Subscribe to events
    def handle_job_status_change(event: JobStatusChangedEvent):
        print(f"Job {event.job.id} status changed: {event.old_status} -> {event.new_status}")
    
    def handle_connection_change(event: ConnectionStatusChangedEvent):
        print(f"Connection status: {'Connected' if event.is_connected else 'Disconnected'}")
    
    bus.subscribe(JobStatusChangedEvent, handle_job_status_change)
    bus.subscribe(ConnectionStatusChangedEvent, handle_connection_change)
    
    # Create mock objects for demonstration
    from modules.data_classes import Job, Project
    
    # Emit events
    project = Project("test_project")
    job = Job(id="123", name="test_job")
    
    bus.emit(JobStatusChangedEvent(
        project=project,
        job=job,
        old_status="PENDING",
        new_status="RUNNING"
    ))
    
    bus.emit(ConnectionStatusChangedEvent(
        is_connected=True,
        host="cluster.example.com"
    ))