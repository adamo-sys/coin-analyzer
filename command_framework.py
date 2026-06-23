"""
Command Framework - Unified Command Execution System

This module provides the command framework for the Collector Platform,
allowing structured command execution with validation and history.
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CommandStatus(Enum):
    """Status of a command execution."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CommandResult:
    """Result of a command execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Command:
    """Represents a platform command."""
    name: str
    handler: Callable
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_validation: bool = True
    can_rollback: bool = False
    rollback_handler: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandHistoryEntry:
    """Entry in command history."""
    command_name: str
    parameters: Dict[str, Any]
    status: CommandStatus
    result: Optional[CommandResult] = None
    timestamp: datetime = field(default_factory=datetime.now)
    execution_time_ms: float = 0.0
    user: Optional[str] = None
    error: Optional[str] = None


class CommandBus:
    """Central command bus for executing and managing commands."""
    
    def __init__(self, platform):
        self.platform = platform
        self._commands: Dict[str, Command] = {}
        self._history: List[CommandHistoryEntry] = []
        self._max_history = 500
    
    def register(self, command: Command) -> bool:
        """Register a command."""
        if command.name in self._commands:
            return False
        
        self._commands[command.name] = command
        return True
    
    def unregister(self, name: str) -> bool:
        """Unregister a command."""
        if name not in self._commands:
            return False
        
        del self._commands[name]
        return True
    
    def get(self, name: str) -> Optional[Command]:
        """Get a registered command."""
        return self._commands.get(name)
    
    def get_all(self) -> List[Command]:
        """Get all registered commands."""
        return list(self._commands.values())
    
    def execute(self, name: str, parameters: Dict[str, Any] = None) -> CommandResult:
        """Execute a command."""
        command = self.get(name)
        if not command:
            return CommandResult(
                success=False,
                error=f"Command not found: {name}"
            )
        
        parameters = parameters or {}
        
        # Create history entry
        entry = CommandHistoryEntry(
            command_name=name,
            parameters=parameters,
            status=CommandStatus.EXECUTING
        )
        
        start_time = datetime.now()
        
        try:
            # Execute handler
            result_data = command.handler(**parameters)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            result = CommandResult(
                success=True,
                data=result_data,
                execution_time_ms=execution_time
            )
            
            entry.status = CommandStatus.COMPLETED
            entry.result = result
            entry.execution_time_ms = execution_time
            
            self.platform.state.total_commands_executed += 1
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            result = CommandResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time
            )
            
            entry.status = CommandStatus.FAILED
            entry.result = result
            entry.execution_time_ms = execution_time
            entry.error = str(e)
        
        # Add to history
        self._add_to_history(entry)
        
        return result
    
    def rollback(self, name: str, parameters: Dict[str, Any] = None) -> CommandResult:
        """Rollback a command if supported."""
        command = self.get(name)
        if not command:
            return CommandResult(
                success=False,
                error=f"Command not found: {name}"
            )
        
        if not command.can_rollback or not command.rollback_handler:
            return CommandResult(
                success=False,
                error=f"Command does not support rollback: {name}"
            )
        
        parameters = parameters or {}
        
        start_time = datetime.now()
        
        try:
            result_data = command.rollback_handler(**parameters)
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return CommandResult(
                success=True,
                data=result_data,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return CommandResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time
            )
    
    def validate(self, name: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate command parameters."""
        command = self.get(name)
        if not command:
            return {"valid": False, "error": f"Command not found: {name}"}
        
        if not command.requires_validation:
            return {"valid": True}
        
        # Basic validation - check required parameters
        issues = []
        
        if hasattr(command.handler, '__annotations__'):
            annotations = command.handler.__annotations__
            for param_name, param_type in annotations.items():
                if param_name == 'return':
                    continue
                if param_name not in parameters:
                    issues.append(f"Missing required parameter: {param_name}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    def get_history(self, limit: int = 100) -> List[CommandHistoryEntry]:
        """Get command history."""
        return self._history[-limit:]
    
    def get_command_history(self, command_name: str, limit: int = 50) -> List[CommandHistoryEntry]:
        """Get history for a specific command."""
        history = [e for e in self._history if e.command_name == command_name]
        return history[-limit:]
    
    def clear_history(self) -> bool:
        """Clear command history."""
        self._history.clear()
        return True
    
    def _add_to_history(self, entry: CommandHistoryEntry):
        """Add entry to history with size limit."""
        self._history.append(entry)
        
        # Enforce max history size
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get command execution statistics."""
        total = len(self._history)
        completed = len([e for e in self._history if e.status == CommandStatus.COMPLETED])
        failed = len([e for e in self._history if e.status == CommandStatus.FAILED])
        
        avg_time = 0.0
        if total > 0:
            total_time = sum(e.execution_time_ms for e in self._history)
            avg_time = total_time / total
        
        return {
            "total_commands": total,
            "completed": completed,
            "failed": failed,
            "success_rate": completed / total if total > 0 else 0.0,
            "average_execution_time_ms": avg_time,
            "max_history": self._max_history
        }


class CommandHandler:
    """Base class for command handlers."""
    
    def __init__(self, platform):
        self.platform = platform
    
    def execute(self, **kwargs) -> Any:
        """Execute the command. Override in subclasses."""
        raise NotImplementedError("Subclasses must implement execute")
    
    def validate(self, **kwargs) -> Dict[str, Any]:
        """Validate parameters. Override in subclasses."""
        return {"valid": True}
    
    def rollback(self, **kwargs) -> Any:
        """Rollback the command. Override in subclasses if rollback is supported."""
        raise NotImplementedError("Rollback not supported for this command")
