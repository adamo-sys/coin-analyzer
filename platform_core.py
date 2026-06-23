"""
Platform Core - Collector Platform Foundation

This module provides the core platform infrastructure for the Collector Platform,
including the main Platform class, service registry, and platform configuration.
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
import json
import os


@dataclass
class PlatformService:
    """Represents a platform service with metadata and lifecycle."""
    name: str
    version: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    health_check: Optional[Callable] = None
    initialize: Optional[Callable] = None
    shutdown: Optional[Callable] = None
    status: str = "registered"
    last_health_check: Optional[datetime] = None


@dataclass
class PlatformConfig:
    """Platform configuration settings."""
    config_version: str = "1.0"
    debug_mode: bool = False
    log_level: str = "INFO"
    data_directory: str = "collection_data"
    backup_directory: str = "collection_data/backups"
    enable_plugins: bool = True
    enable_event_bus: bool = True
    enable_command_framework: bool = True
    max_event_history: int = 1000
    max_command_history: int = 500


@dataclass
class PlatformState:
    """Runtime platform state."""
    platform_version: str = "7.0"
    start_time: Optional[datetime] = None
    service_count: int = 0
    active_services: int = 0
    total_commands_executed: int = 0
    total_events_published: int = 0
    last_state_update: Optional[datetime] = None


class ServiceRegistry:
    """Central registry for platform services."""
    
    def __init__(self):
        self._services: Dict[str, PlatformService] = {}
        self._service_order: List[str] = []
    
    def register(self, service: PlatformService) -> bool:
        """Register a platform service."""
        if service.name in self._services:
            return False
        
        self._services[service.name] = service
        self._service_order.append(service.name)
        return True
    
    def get(self, name: str) -> Optional[PlatformService]:
        """Get a registered service by name."""
        return self._services.get(name)
    
    def get_all(self) -> List[PlatformService]:
        """Get all registered services in registration order."""
        return [self._services[name] for name in self._service_order]
    
    def get_active(self) -> List[PlatformService]:
        """Get all active services."""
        return [s for s in self._services.values() if s.status == "active"]
    
    def unregister(self, name: str) -> bool:
        """Unregister a service."""
        if name not in self._services:
            return False
        
        del self._services[name]
        self._service_order.remove(name)
        return True
    
    def get_dependencies(self, service_name: str) -> List[PlatformService]:
        """Get all dependencies for a service."""
        service = self.get(service_name)
        if not service:
            return []
        
        dependencies = []
        for dep_name in service.dependencies:
            dep = self.get(dep_name)
            if dep:
                dependencies.append(dep)
        
        return dependencies
    
    def get_dependents(self, service_name: str) -> List[PlatformService]:
        """Get all services that depend on this service."""
        dependents = []
        for service in self._services.values():
            if service_name in service.dependencies:
                dependents.append(service)
        return dependents


class Platform:
    """Main platform class that orchestrates all platform services."""
    
    def __init__(self, config: Optional[PlatformConfig] = None):
        self.config = config or PlatformConfig()
        self.state = PlatformState()
        self.service_registry = ServiceRegistry()
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize the platform and all registered services."""
        if self._initialized:
            return True
        
        self.state.start_time = datetime.now()
        self.state.last_state_update = datetime.now()
        
        # Initialize services in dependency order
        services = self._sort_services_by_dependencies()
        for service in services:
            if service.initialize:
                try:
                    service.initialize()
                    service.status = "active"
                except Exception as e:
                    service.status = f"error: {str(e)}"
        
        self.state.service_count = len(self.service_registry.get_all())
        self.state.active_services = len(self.service_registry.get_active())
        self._initialized = True
        
        return True
    
    def shutdown(self) -> bool:
        """Shutdown the platform and all services."""
        if not self._initialized:
            return True
        
        # Shutdown services in reverse dependency order
        services = self._sort_services_by_dependencies()
        for service in reversed(services):
            if service.shutdown:
                try:
                    service.shutdown()
                    service.status = "shutdown"
                except Exception as e:
                    service.status = f"shutdown_error: {str(e)}"
        
        self._initialized = False
        return True
    
    def register_service(self, service: PlatformService) -> bool:
        """Register a new platform service."""
        return self.service_registry.register(service)
    
    def get_service(self, name: str) -> Optional[PlatformService]:
        """Get a registered service."""
        return self.service_registry.get(name)
    
    def get_all_services(self) -> List[PlatformService]:
        """Get all registered services."""
        return self.service_registry.get_all()
    
    def get_active_services(self) -> List[PlatformService]:
        """Get all active services."""
        return self.service_registry.get_active()
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all services."""
        results = {}
        for service in self.service_registry.get_all():
            if service.health_check:
                try:
                    health = service.health_check()
                    service.last_health_check = datetime.now()
                    results[service.name] = {
                        "status": "healthy",
                        "check_result": health,
                        "timestamp": service.last_health_check.isoformat()
                    }
                except Exception as e:
                    results[service.name] = {
                        "status": "unhealthy",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
            else:
                results[service.name] = {
                    "status": "no_health_check",
                    "timestamp": datetime.now().isoformat()
                }
        
        return results
    
    def get_platform_info(self) -> Dict[str, Any]:
        """Get platform information and state."""
        return {
            "platform_version": self.state.platform_version,
            "config_version": self.config.config_version,
            "start_time": self.state.start_time.isoformat() if self.state.start_time else None,
            "initialized": self._initialized,
            "service_count": self.state.service_count,
            "active_services": self.state.active_services,
            "total_commands_executed": self.state.total_commands_executed,
            "total_events_published": self.state.total_events_published,
            "last_state_update": self.state.last_state_update.isoformat() if self.state.last_state_update else None
        }
    
    def _sort_services_by_dependencies(self) -> List[PlatformService]:
        """Topological sort of services by dependencies."""
        sorted_services = []
        visited = set()
        visiting = set()
        
        def visit(service: PlatformService):
            if service.name in visited:
                return
            if service.name in visiting:
                raise ValueError(f"Circular dependency detected involving {service.name}")
            
            visiting.add(service.name)
            
            for dep_name in service.dependencies:
                dep = self.service_registry.get(dep_name)
                if dep:
                    visit(dep)
            
            visiting.remove(service.name)
            visited.add(service.name)
            sorted_services.append(service)
        
        for service in self.service_registry.get_all():
            visit(service)
        
        return sorted_services
    
    def save_config(self, path: Optional[str] = None) -> bool:
        """Save platform configuration to file."""
        if path is None:
            path = os.path.join(self.config.data_directory, "platform_config.json")
        
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump({
                    "config_version": self.config.config_version,
                    "debug_mode": self.config.debug_mode,
                    "log_level": self.config.log_level,
                    "data_directory": self.config.data_directory,
                    "backup_directory": self.config.backup_directory,
                    "enable_plugins": self.config.enable_plugins,
                    "enable_event_bus": self.config.enable_event_bus,
                    "enable_command_framework": self.config.enable_command_framework,
                    "max_event_history": self.config.max_event_history,
                    "max_command_history": self.config.max_command_history
                }, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def load_config(self, path: Optional[str] = None) -> bool:
        """Load platform configuration from file."""
        if path is None:
            path = os.path.join(self.config.data_directory, "platform_config.json")
        
        if not os.path.exists(path):
            return True  # Use defaults
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                self.config.config_version = data.get("config_version", "1.0")
                self.config.debug_mode = data.get("debug_mode", False)
                self.config.log_level = data.get("log_level", "INFO")
                self.config.data_directory = data.get("data_directory", "collection_data")
                self.config.backup_directory = data.get("backup_directory", "collection_data/backups")
                self.config.enable_plugins = data.get("enable_plugins", True)
                self.config.enable_event_bus = data.get("enable_event_bus", True)
                self.config.enable_command_framework = data.get("enable_command_framework", True)
                self.config.max_event_history = data.get("max_event_history", 1000)
                self.config.max_command_history = data.get("max_command_history", 500)
            return True
        except Exception as e:
            print(f"Error loading config: {e}")
            return False


def create_default_platform() -> Platform:
    """Create a platform with default configuration."""
    config = PlatformConfig()
    return Platform(config)
