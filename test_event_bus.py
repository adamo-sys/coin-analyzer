"""
Tests for Event Bus module
"""

import unittest
from event_bus import Event, EventBus, EventSubscription, EventPriority, EventHandler


class TestEvent(unittest.TestCase):
    """Test cases for Event."""
    
    def test_event_creation(self):
        """Test creating an event."""
        event = Event(name="test_event")
        self.assertEqual(event.name, "test_event")
        self.assertEqual(event.priority, EventPriority.NORMAL)
    
    def test_event_with_data(self):
        """Test event with data."""
        event = Event(
            name="test_event",
            data={"key": "value"},
            source="test_source"
        )
        self.assertEqual(event.data["key"], "value")
        self.assertEqual(event.source, "test_source")
    
    def test_event_with_priority(self):
        """Test event with priority."""
        event = Event(
            name="test_event",
            priority=EventPriority.HIGH
        )
        self.assertEqual(event.priority, EventPriority.HIGH)


class TestEventSubscription(unittest.TestCase):
    """Test cases for EventSubscription."""
    
    def test_subscription_creation(self):
        """Test creating an event subscription."""
        def handler(event):
            pass
        
        subscription = EventSubscription(
            event_name="test_event",
            handler=handler
        )
        self.assertEqual(subscription.event_name, "test_event")
        self.assertTrue(subscription.active)


class TestEventBus(unittest.TestCase):
    """Test cases for EventBus."""
    
    def setUp(self):
        """Set up test fixtures."""
        from platform_core import Platform
        self.platform = Platform()
        self.bus = EventBus(self.platform)
    
    def test_subscribe(self):
        """Test subscribing to an event."""
        def handler(event):
            pass
        
        sub_id = self.bus.subscribe("test_event", handler)
        self.assertIsNotNone(sub_id)
        self.assertTrue(sub_id.startswith("sub_"))
    
    def test_unsubscribe(self):
        """Test unsubscribing from an event."""
        def handler(event):
            pass
        
        sub_id = self.bus.subscribe("test_event", handler)
        result = self.bus.unsubscribe(sub_id)
        self.assertTrue(result)
    
    def test_publish(self):
        """Test publishing an event."""
        call_count = [0]
        
        def handler(event):
            call_count[0] += 1
        
        self.bus.subscribe("test_event", handler)
        event = Event(name="test_event")
        handlers_called = self.bus.publish(event)
        self.assertEqual(handlers_called, 1)
        self.assertEqual(call_count[0], 1)
    
    def test_publish_sync(self):
        """Test publishing event synchronously."""
        call_count = [0]
        
        def handler(event):
            call_count[0] += 1
        
        self.bus.subscribe("test_event", handler)
        handlers_called = self.bus.publish_sync("test_event")
        self.assertEqual(handlers_called, 1)
        self.assertEqual(call_count[0], 1)
    
    def test_publish_with_filter(self):
        """Test publishing with filter function."""
        call_count = [0]
        
        def handler(event):
            call_count[0] += 1
        
        def filter_func(event):
            return event.data.get("allowed", False)
        
        self.bus.subscribe("test_event", handler, filter_func=filter_func)
        
        # Event that doesn't pass filter
        event1 = Event(name="test_event", data={"allowed": False})
        self.bus.publish(event1)
        self.assertEqual(call_count[0], 0)
        
        # Event that passes filter
        event2 = Event(name="test_event", data={"allowed": True})
        self.bus.publish(event2)
        self.assertEqual(call_count[0], 1)
    
    def test_get_subscriptions(self):
        """Test getting subscriptions for an event."""
        def handler(event):
            pass
        
        self.bus.subscribe("test_event", handler)
        subscriptions = self.bus.get_subscriptions("test_event")
        self.assertEqual(len(subscriptions), 1)
    
    def test_get_event_history(self):
        """Test getting event history."""
        event = Event(name="test_event")
        self.bus.publish(event)
        history = self.bus.get_history()
        self.assertEqual(len(history), 1)
    
    def test_get_statistics(self):
        """Test getting event bus statistics."""
        stats = self.bus.get_statistics()
        self.assertIn("total_subscriptions", stats)
        self.assertIn("total_events_published", stats)


class TestEventHandler(unittest.TestCase):
    """Test cases for EventHandler."""
    
    def test_handler_creation(self):
        """Test creating an event handler."""
        from platform_core import Platform
        platform = Platform()
        bus = EventBus(platform)
        handler = EventHandler(platform)
        self.assertIsNotNone(handler.platform)
    
    def test_subscribe_to(self):
        """Test subscribing handler to event."""
        from platform_core import Platform
        platform = Platform()
        bus = EventBus(platform)
        handler = EventHandler(platform)
        
        handler.subscribe_to(bus, "test_event")
        self.assertEqual(len(handler._subscription_ids), 1)


if __name__ == '__main__':
    unittest.main()
