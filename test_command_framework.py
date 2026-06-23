"""
Tests for Command Framework module
"""

import unittest
from command_framework import Command, CommandBus, CommandResult, CommandStatus, CommandHandler


class TestCommandResult(unittest.TestCase):
    """Test cases for CommandResult."""
    
    def test_success_result(self):
        """Test successful command result."""
        result = CommandResult(success=True, data="test_data")
        self.assertTrue(result.success)
        self.assertEqual(result.data, "test_data")
    
    def test_failure_result(self):
        """Test failed command result."""
        result = CommandResult(success=False, error="Test error")
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Test error")


class TestCommand(unittest.TestCase):
    """Test cases for Command."""
    
    def test_command_creation(self):
        """Test creating a command."""
        def handler(**kwargs):
            return "result"
        
        command = Command(
            name="test_command",
            handler=handler,
            description="Test command"
        )
        self.assertEqual(command.name, "test_command")
        self.assertIsNotNone(command.handler)
    
    def test_command_with_rollback(self):
        """Test command with rollback support."""
        def handler(**kwargs):
            return "result"
        
        def rollback(**kwargs):
            return "rolled_back"
        
        command = Command(
            name="test_command",
            handler=handler,
            description="Test command",
            can_rollback=True,
            rollback_handler=rollback
        )
        self.assertTrue(command.can_rollback)
        self.assertIsNotNone(command.rollback_handler)


class TestCommandBus(unittest.TestCase):
    """Test cases for CommandBus."""
    
    def setUp(self):
        """Set up test fixtures."""
        from platform_core import Platform
        self.platform = Platform()
        self.bus = CommandBus(self.platform)
    
    def test_register_command(self):
        """Test registering a command."""
        def handler(**kwargs):
            return "result"
        
        command = Command(
            name="test_command",
            handler=handler,
            description="Test command"
        )
        result = self.bus.register(command)
        self.assertTrue(result)
    
    def test_register_duplicate_command(self):
        """Test registering duplicate command."""
        def handler(**kwargs):
            return "result"
        
        command = Command(
            name="test_command",
            handler=handler,
            description="Test command"
        )
        self.bus.register(command)
        result = self.bus.register(command)
        self.assertFalse(result)
    
    def test_execute_command(self):
        """Test executing a command."""
        def handler(**kwargs):
            return "result"
        
        command = Command(
            name="test_command",
            handler=handler,
            description="Test command"
        )
        self.bus.register(command)
        result = self.bus.execute("test_command")
        self.assertTrue(result.success)
        self.assertEqual(result.data, "result")
    
    def test_execute_command_with_parameters(self):
        """Test executing command with parameters."""
        def handler(value):
            return f"result: {value}"
        
        command = Command(
            name="test_command",
            handler=handler,
            description="Test command"
        )
        self.bus.register(command)
        result = self.bus.execute("test_command", {"value": "test"})
        self.assertTrue(result.success)
        self.assertEqual(result.data, "result: test")
    
    def test_execute_nonexistent_command(self):
        """Test executing nonexistent command."""
        result = self.bus.execute("nonexistent")
        self.assertFalse(result.success)
        self.assertIn("not found", result.error)
    
    def test_validate_command(self):
        """Test validating command parameters."""
        def handler(value):
            return f"result: {value}"
        
        command = Command(
            name="test_command",
            handler=handler,
            description="Test command"
        )
        self.bus.register(command)
        validation = self.bus.validate("test_command", {"value": "test"})
        self.assertTrue(validation["valid"])
    
    def test_get_command_history(self):
        """Test getting command history."""
        def handler(**kwargs):
            return "result"
        
        command = Command(
            name="test_command",
            handler=handler,
            description="Test command"
        )
        self.bus.register(command)
        self.bus.execute("test_command")
        history = self.bus.get_history()
        self.assertEqual(len(history), 1)
    
    def test_get_statistics(self):
        """Test getting command statistics."""
        stats = self.bus.get_statistics()
        self.assertIn("total_commands", stats)
        self.assertIn("completed", stats)


class TestCommandHandler(unittest.TestCase):
    """Test cases for CommandHandler."""
    
    def test_handler_creation(self):
        """Test creating a command handler."""
        from platform_core import Platform
        platform = Platform()
        handler = CommandHandler(platform)
        self.assertIsNotNone(handler.platform)


if __name__ == '__main__':
    unittest.main()
