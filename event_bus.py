"""
EventBus System for SLURM GUI Application
Provides centralized event management for cross-component communication
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from PyQt6.QtCore import QObject, pyqtSignal
import uuid


class EventType(Enum):
    """Enumeration of all event types in the application"""
    
    # === CONNECTION EVENTS ===
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_LOST = "connection_lost"
    CONNECTION_ATTEMPTING = "connection_attempting"
    CONNECTION_ERROR = "connection_error"
    
    # === CLUSTER EVENTS ===
    CLUSTER_DATA_UPDATED = "cluster_data_updated"
    CLUSTER_STATUS_CHANGED = "cluster_status_changed"
    NODE_STATUS_CHANGED = "node_status_changed"
    
    # === JOB EVENTS ===
    JOB_SUBMITTED = "job_submitted"
    JOB_STATUS_CHANGED = "job_status_changed"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"
    JOB_UPDATED = "job_updated"
    JOB_DELETED = "job_deleted"
    
    # === PROJECT EVENTS ===
    PROJECT_CREATED = "project_created"
    PROJECT_SELECTED = "project_selected"
    PROJECT_DELETED = "project_deleted"
    PROJECT_STATS_CHANGED = "project_stats_changed"
    
    # === SETTINGS EVENTS ===
    SETTINGS_CHANGED = "settings_changed"
    DISPLAY_SETTINGS_CHANGED = "display_settings_changed"
    CONNECTION_SETTINGS_CHANGED = "connection_settings_changed"
    NOTIFICATION_SETTINGS_CHANGED = "notification_settings_changed"
    
    # === UI EVENTS ===
    TOAST_REQUESTED = "toast_requested"
    THEME_CHANGED = "theme_changed"
    REFRESH_REQUESTED = "refresh_requested"
    
    # === MONITORING EVENTS ===
    MONITORING_STARTED = "monitoring_started"
    MONITORING_STOPPED = "monitoring_stopped"
    DATA_REFRESH_CYCLE = "data_refresh_cycle"


@dataclass
class Event:
    """Event data structure containing all event information"""
    
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __str__(self) -> str:
        return f"Event({self.type.value}, source={self.source}, id={self.event_id[:8]})"


class EventSubscription:
    """Represents an event subscription with metadata"""
    
    def __init__(self, event_type: EventType, callback: Callable, subscriber_id: str):
        self.event_type = event_type
        self.callback = callback
        self.subscriber_id = subscriber_id
        self.subscription_id = str(uuid.uuid4())
        self.created_at = datetime.now()
    
    def matches(self, event: Event) -> bool:
        """Check if this subscription matches the given event"""
        return self.event_type == event.type
    
    def invoke(self, event: Event):
        """Invoke the callback with the event"""
        try:
            self.callback(event)
        except Exception as e:
            print(f"Error in event callback for {self.event_type}: {e}")


class EventBus(QObject):
    """
    Centralized event bus for cross-component communication.
    
    Features:
    - Type-safe event publishing and subscription
    - Qt integration with signals
    - Event filtering and routing
    - Subscription management
    - Event history for debugging
    """
    
    # Qt signal for event emission (allows Qt widgets to connect)
    event_emitted = pyqtSignal(object)  # Event object
    
    _instance: Optional['EventBus'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        super().__init__()
        self._subscriptions: List[EventSubscription] = []
        self._event_history: List[Event] = []
        self._max_history_size = 1000
        self._enabled = True
        self._initialized = True
        
        # Connect Qt signal to internal handler
        self.event_emitted.connect(self._handle_qt_event)
    
    @classmethod
    def instance(cls) -> 'EventBus':
        """Get the singleton instance"""
        return cls()
    
    def emit(self, event_type: EventType, data: Optional[Dict[str, Any]] = None, 
             source: str = "") -> Event:
        """
        Emit an event to all subscribers
        
        Args:
            event_type: Type of event to emit
            data: Event data dictionary
            source: Source identifier for the event
            
        Returns:
            The created Event object
        """
        if not self._enabled:
            return None
            
        event = Event(
            type=event_type,
            data=data or {},
            source=source
        )
        
        # Add to history
        self._add_to_history(event)
        
        # Emit Qt signal (this will trigger _handle_qt_event)
        self.event_emitted.emit(event)
        
        return event
    
    def subscribe(self, event_type: EventType, callback: Callable, 
                  subscriber_id: str = "") -> str:
        """
        Subscribe to an event type
        
        Args:
            event_type: Type of event to subscribe to
            callback: Function to call when event is emitted
            subscriber_id: Optional identifier for the subscriber
            
        Returns:
            Subscription ID that can be used to unsubscribe
        """
        subscription = EventSubscription(event_type, callback, subscriber_id)
        self._subscriptions.append(subscription)
        return subscription.subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from events using subscription ID
        
        Args:
            subscription_id: ID returned from subscribe()
            
        Returns:
            True if subscription was found and removed
        """
        for i, sub in enumerate(self._subscriptions):
            if sub.subscription_id == subscription_id:
                self._subscriptions.pop(i)
                return True
        return False
    
    def unsubscribe_all(self, subscriber_id: str) -> int:
        """
        Unsubscribe all subscriptions for a given subscriber
        
        Args:
            subscriber_id: Subscriber identifier
            
        Returns:
            Number of subscriptions removed
        """
        initial_count = len(self._subscriptions)
        self._subscriptions = [
            sub for sub in self._subscriptions 
            if sub.subscriber_id != subscriber_id
        ]
        return initial_count - len(self._subscriptions)
    
    def _handle_qt_event(self, event: Event):
        """Handle events emitted through Qt signals"""
        self._dispatch_event(event)
    
    def _dispatch_event(self, event: Event):
        """Dispatch event to all matching subscribers"""
        if not self._enabled:
            return
            
        for subscription in self._subscriptions[:]:  # Copy to avoid modification during iteration
            if subscription.matches(event):
                subscription.invoke(event)
    
    def _add_to_history(self, event: Event):
        """Add event to history with size limit"""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history_size:
            self._event_history.pop(0)
    
    # === Convenience Methods ===
    
    def emit_connection_established(self, connection_info: Dict[str, Any], source: str = ""):
        """Emit connection established event"""
        return self.emit(EventType.CONNECTION_ESTABLISHED, connection_info, source)
    
    def emit_connection_lost(self, reason: str = "", source: str = ""):
        """Emit connection lost event"""
        return self.emit(EventType.CONNECTION_LOST, {"reason": reason}, source)
    
    def emit_job_status_changed(self, job_id: str, old_status: str, new_status: str, 
                               project_name: str = "", source: str = ""):
        """Emit job status changed event"""
        return self.emit(EventType.JOB_STATUS_CHANGED, {
            "job_id": job_id,
            "old_status": old_status,
            "new_status": new_status,
            "project_name": project_name
        }, source)
    
    def emit_project_selected(self, project_name: str, source: str = ""):
        """Emit project selected event"""
        return self.emit(EventType.PROJECT_SELECTED, {"project_name": project_name}, source)
    
    def emit_settings_changed(self, settings_type: str, settings_data: Dict[str, Any], 
                             source: str = ""):
        """Emit settings changed event"""
        return self.emit(EventType.SETTINGS_CHANGED, {
            "settings_type": settings_type,
            "settings_data": settings_data
        }, source)
    
    def emit_toast_requested(self, title: str, message: str = "", toast_type: str = "info",
                            duration: int = 4000, source: str = ""):
        """Emit toast notification request"""
        return self.emit(EventType.TOAST_REQUESTED, {
            "title": title,
            "message": message,
            "toast_type": toast_type,
            "duration": duration
        }, source)
    
    def emit_cluster_data_updated(self, nodes_data: List, jobs_data: List, source: str = ""):
        """Emit cluster data updated event"""
        return self.emit(EventType.CLUSTER_DATA_UPDATED, {
            "nodes_data": nodes_data,
            "jobs_data": jobs_data
        }, source)
    
    # === Utility Methods ===
    
    def get_subscribers(self, event_type: EventType) -> List[EventSubscription]:
        """Get all subscribers for a specific event type"""
        return [sub for sub in self._subscriptions if sub.event_type == event_type]
    
    def get_event_history(self, event_type: Optional[EventType] = None, 
                         limit: int = 100) -> List[Event]:
        """Get event history, optionally filtered by type"""
        events = self._event_history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:] if limit else events
    
    def clear_history(self):
        """Clear event history"""
        self._event_history.clear()
    
    def enable(self):
        """Enable event processing"""
        self._enabled = True
    
    def disable(self):
        """Disable event processing"""
        self._enabled = False
    
    def is_enabled(self) -> bool:
        """Check if event processing is enabled"""
        return self._enabled
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the event bus"""
        event_counts = {}
        for event in self._event_history:
            event_type = event.type.value
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        subscription_counts = {}
        for sub in self._subscriptions:
            event_type = sub.event_type.value
            subscription_counts[event_type] = subscription_counts.get(event_type, 0) + 1
        
        return {
            "total_events_emitted": len(self._event_history),
            "total_subscriptions": len(self._subscriptions),
            "event_counts": event_counts,
            "subscription_counts": subscription_counts,
            "enabled": self._enabled
        }


# === Convenience Functions ===

def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    return EventBus.instance()


def emit_event(event_type: EventType, data: Optional[Dict[str, Any]] = None, 
               source: str = "") -> Event:
    """Convenience function to emit an event"""
    return get_event_bus().emit(event_type, data, source)


def subscribe_to_event(event_type: EventType, callback: Callable, 
                      subscriber_id: str = "") -> str:
    """Convenience function to subscribe to an event"""
    return get_event_bus().subscribe(event_type, callback, subscriber_id)


def unsubscribe_from_event(subscription_id: str) -> bool:
    """Convenience function to unsubscribe from an event"""
    return get_event_bus().unsubscribe(subscription_id)