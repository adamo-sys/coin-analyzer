"""
Event Bus - Platform-Wide Event System

This module provides the event bus for the Collector Platform,
allowing publish/subscribe communication between components.
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading


class EventPriority(Enum):
    """Priority levels for events."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Event:
    """Represents a platform event."""
    name: str
    data: Dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    event_id: str = ""


@dataclass
class EventSubscription:
    """Represents a subscription to events."""
    event_name: str
    handler: Callable
    filter_func: Optional[Callable] = None
    priority: EventPriority = EventPriority.NORMAL
    active: bool = True
    subscription_id: str = ""


@dataclass
class EventHistoryEntry:
    """Entry in event history."""
    event: Event
    handler_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class EventBus:
    """Central event bus for platform-wide event communication."""
    
    def __init__(self, platform):
        self.platform = platform
        self._subscriptions: Dict[str, List[EventSubscription]] = {}
        self._history: List[EventHistoryEntry] = []
        self._max_history = 1000
        self._lock = threading.Lock()
        self._subscription_counter = 0
    
    def subscribe(self, event_name: str, handler: Callable, 
                  filter_func: Optional[Callable] = None,
                  priority: EventPriority = EventPriority.NORMAL) -> str:
        """Subscribe to an event."""
        with self._lock:
            self._subscription_counter += 1
            subscription_id = f"sub_{self._subscription_counter}"
            
            subscription = EventSubscription(
                event_name=event_name,
                handler=handler,
                filter_func=filter_func,
                priority=priority,
                active=True,
                subscription_id=subscription_id
            )
            
            if event_name not in self._subscriptions:
                self._subscriptions[event_name] = []
            
            self._subscriptions[event_name].append(subscription)
            
            # Sort by priority
            self._subscriptions[event_name].sort(
                key=lambda s: s.priority.value,
                reverse=True
            )
            
            return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from an event."""
        with self._lock:
            for event_name, subscriptions in self._subscriptions.items():
                for sub in subscriptions:
                    if sub.subscription_id == subscription_id:
                        subscriptions.remove(sub)
                        return True
            return False
    
    def unsubscribe_all(self, event_name: str) -> int:
        """Unsubscribe all handlers for an event."""
        with self._lock:
            if event_name in self._subscriptions:
                count = len(self._subscriptions[event_name])
                del self._subscriptions[event_name]
                return count
            return 0
    
    def publish(self, event: Event) -> int:
        """Publish an event to all subscribers."""
        handlers_called = 0
        
        with self._lock:
            subscriptions = self._subscriptions.get(event.name, [])
            
            # Add to history
            history_entry = EventHistoryEntry(
                event=event,
                handler_count=len(subscriptions)
            )
            self._add_to_history(history_entry)
        
        # Call handlers outside lock to prevent deadlocks
        for subscription in subscriptions:
            if not subscription.active:
                continue
            
            # Apply filter if present
            if subscription.filter_func and not subscription.filter_func(event):
                continue
            
            try:
                subscription.handler(event)
                handlers_called += 1
            except Exception as e:
                print(f"Error in event handler for {event.name}: {e}")
        
        self.platform.state.total_events_published += 1
        
        return handlers_called
    
    def publish_sync(self, event_name: str, data: Optional[Dict[str, Any]] = None,
                     source: Optional[str] = None,
                     priority: EventPriority = EventPriority.NORMAL) -> int:
        """Publish an event synchronously."""
        event = Event(
            name=event_name,
            data=data or {},
            source=source,
            priority=priority
        )
        return self.publish(event)
    
    def get_subscriptions(self, event_name: str) -> List[EventSubscription]:
        """Get all subscriptions for an event."""
        with self._lock:
            return self._subscriptions.get(event_name, []).copy()
    
    def get_all_subscriptions(self) -> Dict[str, List[EventSubscription]]:
        """Get all subscriptions."""
        with self._lock:
            return {k: v.copy() for k, v in self._subscriptions.items()}
    
    def get_history(self, limit: int = 100) -> List[EventHistoryEntry]:
        """Get event history."""
        with self._lock:
            return self._history[-limit:]
    
    def get_event_history(self, event_name: str, limit: int = 50) -> List[EventHistoryEntry]:
        """Get history for a specific event."""
        with self._lock:
            history = [e for e in self._history if e.event.name == event_name]
            return history[-limit:]
    
    def clear_history(self) -> bool:
        """Clear event history."""
        with self._lock:
            self._history.clear()
            return True
    
    def _add_to_history(self, entry: EventHistoryEntry):
        """Add entry to history with size limit."""
        self._history.append(entry)
        
        # Enforce max history size
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        with self._lock:
            total_subscriptions = sum(len(subs) for subs in self._subscriptions.values())
            total_events = len(self._history)
            
            event_counts = {}
            for entry in self._history:
                name = entry.event.name
                event_counts[name] = event_counts.get(name, 0) + 1
            
            return {
                "total_subscriptions": total_subscriptions,
                "total_events_published": total_events,
                "unique_event_types": len(self._subscriptions),
                "event_counts": event_counts,
                "max_history": self._max_history
            }


class EventHandler:
    """Base class for event handlers."""
    
    def __init__(self, platform):
        self.platform = platform
        self._subscription_ids: List[str] = []
    
    def handle(self, event: Event):
        """Handle an event. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement handle")
    
    def subscribe_to(self, event_bus: EventBus, event_name: str,
                     filter_func: Optional[Callable] = None,
                     priority: EventPriority = EventPriority.NORMAL):
        """Subscribe this handler to an event."""
        sub_id = event_bus.subscribe(
            event_name=event_name,
            handler=self.handle,
            filter_func=filter_func,
            priority=priority
        )
        self._subscription_ids.append(sub_id)
    
    def unsubscribe_all(self, event_bus: EventBus):
        """Unsubscribe this handler from all events."""
        for sub_id in self._subscription_ids:
            event_bus.unsubscribe(sub_id)
        self._subscription_ids.clear()
