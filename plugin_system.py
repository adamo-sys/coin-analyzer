"""
Plugin System - Extensible Plugin Architecture

This module provides the plugin system for the Collector Platform,
allowing dynamic loading and management of platform plugins.
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
import os
import importlib.util
import sys


@dataclass
class PluginManifest:
    """Manifest describing a plugin."""
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str] = field(default_factory=list)
    platform_version: str = "7.0"
    entry_point: Optional[str] = None
    config_schema: Optional[Dict[str, Any]] = None


@dataclass
class Plugin:
    """Represents a loaded plugin."""
    manifest: PluginManifest
    module: Optional[Any] = None
    status: str = "loaded"
    load_time: Optional[datetime] = None
    error_message: Optional[str] = None
    context: Optional['PluginContext'] = None


@dataclass
class PluginContext:
    """Context provided to plugins during initialization."""
    platform: Any
    config: Dict[str, Any] = field(default_factory=dict)
    data_directory: str = ""


class PluginManager:
    """Manages plugin lifecycle and operations."""
    
    def __init__(self, platform):
        self.platform = platform
        self._plugins: Dict[str, Plugin] = {}
        self._plugin_directory = "plugins"
    
    def load_from_directory(self, directory: str) -> int:
        """Load all plugins from a directory."""
        if not os.path.exists(directory):
            return 0
        
        loaded_count = 0
        for filename in os.listdir(directory):
            if filename.endswith('.py') and not filename.startswith('_'):
                plugin_path = os.path.join(directory, filename)
                if self.load_from_file(plugin_path):
                    loaded_count += 1
        
        return loaded_count
    
    def load_from_file(self, file_path: str) -> bool:
        """Load a plugin from a Python file."""
        try:
            spec = importlib.util.spec_from_file_location("plugin", file_path)
            if spec is None or spec.loader is None:
                return False
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Look for manifest
            manifest = getattr(module, 'PLUGIN_MANIFEST', None)
            if not manifest:
                return False
            
            plugin = Plugin(
                manifest=manifest,
                module=module,
                status="loaded",
                load_time=datetime.now()
            )
            
            self._plugins[manifest.name] = plugin
            return True
            
        except Exception as e:
            print(f"Error loading plugin from {file_path}: {e}")
            return False
    
    def register_plugin(self, manifest: PluginManifest, module: Any = None) -> bool:
        """Register a plugin programmatically."""
        if manifest.name in self._plugins:
            return False
        
        plugin = Plugin(
            manifest=manifest,
            module=module,
            status="registered",
            load_time=datetime.now()
        )
        
        self._plugins[manifest.name] = plugin
        return True
    
    def initialize_plugin(self, name: str) -> bool:
        """Initialize a registered plugin."""
        plugin = self._plugins.get(name)
        if not plugin:
            return False
        
        if plugin.status != "registered":
            return False
        
        try:
            context = PluginContext(
                platform=self.platform,
                data_directory=self.platform.config.data_directory
            )
            plugin.context = context
            
            if plugin.module and hasattr(plugin.module, 'initialize'):
                plugin.module.initialize(context)
            
            plugin.status = "active"
            return True
            
        except Exception as e:
            plugin.status = f"error: {str(e)}"
            plugin.error_message = str(e)
            return False
    
    def shutdown_plugin(self, name: str) -> bool:
        """Shutdown an active plugin."""
        plugin = self._plugins.get(name)
        if not plugin:
            return False
        
        if plugin.status != "active":
            return False
        
        try:
            if plugin.module and hasattr(plugin.module, 'shutdown'):
                plugin.module.shutdown()
            
            plugin.status = "shutdown"
            return True
            
        except Exception as e:
            plugin.status = f"shutdown_error: {str(e)}"
            return False
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)
    
    def get_all_plugins(self) -> List[Plugin]:
        """Get all plugins."""
        return list(self._plugins.values())
    
    def get_active_plugins(self) -> List[Plugin]:
        """Get all active plugins."""
        return [p for p in self._plugins.values() if p.status == "active"]
    
    def unregister_plugin(self, name: str) -> bool:
        """Unregister a plugin."""
        if name not in self._plugins:
            return False
        
        plugin = self._plugins[name]
        if plugin.status == "active":
            self.shutdown_plugin(name)
        
        del self._plugins[name]
        return True
    
    def get_plugin_dependencies(self, name: str) -> List[Plugin]:
        """Get all dependencies for a plugin."""
        plugin = self.get_plugin(name)
        if not plugin:
            return []
        
        dependencies = []
        for dep_name in plugin.manifest.dependencies:
            dep = self.get_plugin(dep_name)
            if dep:
                dependencies.append(dep)
        
        return dependencies
    
    def get_dependent_plugins(self, name: str) -> List[Plugin]:
        """Get all plugins that depend on this plugin."""
        dependents = []
        for plugin in self._plugins.values():
            if name in plugin.manifest.dependencies:
                dependents.append(plugin)
        return dependents
    
    def validate_plugin(self, name: str) -> Dict[str, Any]:
        """Validate a plugin's dependencies and compatibility."""
        plugin = self.get_plugin(name)
        if not plugin:
            return {"valid": False, "reason": "Plugin not found"}
        
        issues = []
        
        # Check platform version compatibility
        if plugin.manifest.platform_version != self.platform.state.platform_version:
            issues.append(f"Platform version mismatch: plugin expects {plugin.manifest.platform_version}, platform is {self.platform.state.platform_version}")
        
        # Check dependencies
        for dep_name in plugin.manifest.dependencies:
            dep = self.get_plugin(dep_name)
            if not dep:
                issues.append(f"Missing dependency: {dep_name}")
            elif dep.status != "active":
                issues.append(f"Dependency not active: {dep_name}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "plugin_name": plugin.manifest.name,
            "plugin_version": plugin.manifest.version
        }
    
    def get_plugin_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a plugin."""
        plugin = self.get_plugin(name)
        if not plugin:
            return None
        
        return {
            "name": plugin.manifest.name,
            "version": plugin.manifest.version,
            "description": plugin.manifest.description,
            "author": plugin.manifest.author,
            "dependencies": plugin.manifest.dependencies,
            "platform_version": plugin.manifest.platform_version,
            "status": plugin.status,
            "load_time": plugin.load_time.isoformat() if plugin.load_time else None,
            "error_message": plugin.error_message,
            "has_module": plugin.module is not None
        }
