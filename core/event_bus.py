"""
EventBus - Centralized Event Handling System
Simple, thread-safe event bus for decoupled communication between components.
"""

import weakref
from typing import Dict, List, Callable, Any, Optional
from threading import RLock  
from dataclasses import dataclass
from enum import Enum, auto
from PyQt6.QtCore import QObject, pyqtSignal, QMetaObject, Qt


class EventPriority(Enum):
    """Event priority levels"""
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass
class Event:
    """Base event data structure"""
    type: str
    data: Any = None
    source: Optional[str] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            import time
            self.timestamp = time.time()


@dataclass 
class EventListener:
    """Event listener data structure"""
    callback: Callable
    priority: EventPriority = EventPriority.NORMAL
    once: bool = False  # Remove after first call
    weak_ref: bool = True  # Use weak reference to prevent memory leaks


class EventBus(QObject):
    """
    Simple, thread-safe EventBus for centralized event handling.
    Integrates with PyQt signals while providing additional flexibility.
    """
    
    # Qt signal for integration with existing PyQt signal/slot system
    eventEmitted = pyqtSignal(object)  # Emits Event object
    
    def __init__(self):
        super().__init__()
        self._listeners: Dict[str, List[EventListener]] = {}
        self._lock = RLock()
        self._enabled = True
        
    def subscribe(self, event_type: str, callback: Callable, 
                  priority: EventPriority = EventPriority.NORMAL,
                  once: bool = False, weak_ref: bool = False) -> str:
        """
        Subscribe to an event type.
        
        Args:
            event_type: The type of event to listen for
            callback: Function to call when event occurs
            priority: Priority level for this listener
            once: If True, remove listener after first call
            weak_ref: If True, use weak reference (recommended for object methods)
            
        Returns:
            Subscription ID for later unsubscription
        """
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            
            # Create weak reference if requested and callback is a bound method
            actual_callback = callback
            if weak_ref and hasattr(callback, '__self__'):
                obj_ref = weakref.ref(callback.__self__)
                method_name = callback.__name__
                
                def weak_callback(*args, **kwargs):
                    obj = obj_ref()
                    if obj is not None:
                        return getattr(obj, method_name)(*args, **kwargs)
                    # Object was garbage collected, remove this listener
                    return None
                    
                actual_callback = weak_callback
            
            listener = EventListener(
                callback=actual_callback,
                priority=priority,
                once=once,
                weak_ref=weak_ref
            )
            
            # Insert based on priority (higher priority first)
            priority_order = [EventPriority.CRITICAL, EventPriority.HIGH, 
                            EventPriority.NORMAL, EventPriority.LOW]
            
            inserted = False
            for i, existing_listener in enumerate(self._listeners[event_type]):
                if priority_order.index(listener.priority) < priority_order.index(existing_listener.priority):
                    self._listeners[event_type].insert(i, listener)
                    inserted = True
                    break
            
            if not inserted:
                self._listeners[event_type].append(listener)
            
            # Generate subscription ID
            sub_id = f"{event_type}_{id(listener)}"
            return sub_id
    
    def unsubscribe(self, event_type: str, callback: Callable = None, sub_id: str = None):
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: The event type to unsubscribe from
            callback: Specific callback to remove (optional)
            sub_id: Subscription ID to remove (optional)
        """
        with self._lock:
            if event_type not in self._listeners:
                return
            
            if sub_id:
                # Remove by subscription ID
                listener_id = sub_id.split('_')[-1]
                self._listeners[event_type] = [
                    l for l in self._listeners[event_type] 
                    if str(id(l)) != listener_id
                ]
            elif callback:
                # Remove by callback
                self._listeners[event_type] = [
                    l for l in self._listeners[event_type] 
                    if l.callback != callback
                ]
            else:
                # Remove all listeners for this event type
                self._listeners[event_type] = []
    
    def emit(self, event_type: str, data: Any = None, source: str = None) -> bool:
        """
        Emit an event to all subscribers.
        
        Args:
            event_type: Type of event to emit
            data: Event data
            source: Source identifier (optional)
            
        Returns:
            True if event was processed by at least one listener
        """
        if not self._enabled:
            return False
        
        event = Event(type=event_type, data=data, source=source)
        
        # Emit Qt signal for integration with existing signal/slot system
        self.eventEmitted.emit(event)
        
        with self._lock:
            if event_type not in self._listeners:
                return False
            
            listeners = self._listeners[event_type].copy()
            listeners_to_remove = []
            processed = False
            
            for listener in listeners:
                try:
                    # Call the listener
                    result = listener.callback(event)
                    
                    # If callback returned None and it's a weak reference,
                    # the object was garbage collected
                    if result is None and listener.weak_ref:
                        listeners_to_remove.append(listener)
                        continue
                    
                    processed = True
                    
                    # Remove one-time listeners
                    if listener.once:
                        listeners_to_remove.append(listener)
                        
                except Exception as e:
                    print(f"EventBus: Error in listener for {event_type}: {e}")
                    # Remove problematic listeners
                    listeners_to_remove.append(listener)
            
            # Clean up listeners that need to be removed
            for listener in listeners_to_remove:
                if listener in self._listeners[event_type]:
                    self._listeners[event_type].remove(listener)
        
        return processed
    
    def emit_qt_safe(self, event_type: str, data: Any = None, source: str = None):
        """
        Emit an event safely from any thread using Qt's event system.
        """
        QMetaObject.invokeMethod(
            self, "emit", 
            Qt.ConnectionType.QueuedConnection,
            event_type, data, source
        )
    
    def clear(self, event_type: str = None):
        """Clear all listeners for a specific event type or all listeners."""
        with self._lock:
            if event_type:
                if event_type in self._listeners:
                    del self._listeners[event_type]
            else:
                self._listeners.clear()
    
    def get_listeners_count(self, event_type: str = None) -> int:
        """Get count of listeners for an event type or total listeners."""
        with self._lock:
            if event_type:
                return len(self._listeners.get(event_type, []))
            return sum(len(listeners) for listeners in self._listeners.values())
    
    def enable(self):
        """Enable event processing."""
        self._enabled = True
    
    def disable(self):
        """Disable event processing."""
        self._enabled = False
    
    def enabled(self) -> bool:
        """Check if event bus is enabled."""
        return self._enabled


# Singleton instance
_event_bus_instance = None


def get_event_bus() -> EventBus:
    """Get the global EventBus instance."""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance


# Convenience functions for common event patterns
def emit_event(event_type: str, data: Any = None, source: str = None) -> bool:
    """Emit an event using the global event bus."""
    return get_event_bus().emit(event_type, data, source)


def subscribe_event(event_type: str, callback: Callable, 
                   priority: EventPriority = EventPriority.NORMAL,
                   once: bool = False) -> str:
    """Subscribe to an event using the global event bus."""
    return get_event_bus().subscribe(event_type, callback, priority, once)


def unsubscribe_event(event_type: str, callback: Callable = None):
    """Unsubscribe from an event using the global event bus."""
    get_event_bus().unsubscribe(event_type, callback)


# Common event types used throughout the application
class Events:
    """Common event type constants"""
    
    # Connection events
    CONNECTION_STATE_CHANGED =  "connection_status.changed"
    
    # Job events  
    JOB_SUBMITTED = "job.submitted"
    JOB_STATUS_CHANGED = "job.status_changed"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    ADD_JOB = "job.add"
    MODIFY_JOB = "job.modify"
    DEL_JOB = "job.del_job"
    DUPLICATE_JOB = "job.duplicate"
    STOP_JOB = "job.stop"

    # Data events
    DATA_READY = "cluster_job.data_ready"
    # UI events
    PROJECT_SELECTED = "project.selected"
    PROJECT_LIST_CHANGED = "project.list_changed"   
    ADD_PROJECT = "project.add_project"   
    DEL_PROJECT = "project.del_project"   
    
    # System events
    APP_STARTUP = "app.startup"
    APP_SHUTDOWN = "app.shutdown"
    ERROR_OCCURRED = "error.occurred"
    
    # Internal settings events
    CONNECTION_SAVE_REQ = "settings.view.connection_save_btn"
    DISPLAY_SAVE_REQ = "settings.view.display_save_btn"
    NOTIF_SAVE_REQ = "settings.view.notification_changed"
    DISCORD_TEST_REQ = "settings.view.discord_test_btn"
    
     