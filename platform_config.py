"""
Platform Configuration - Centralized Configuration Management

This module provides centralized configuration management for the Collector Platform.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import json
import os


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
    plugin_directory: str = "plugins"
    auto_save_config: bool = True
    config_backup_count: int = 5


class ConfigManager:
    """Manager for platform configuration."""
    
    def __init__(self, config: Optional[PlatformConfig] = None):
        self.config = config or PlatformConfig()
        self._config_path: Optional[str] = None
        self._backup_directory: Optional[str] = None
    
    def set_config_path(self, path: str):
        """Set the configuration file path."""
        self._config_path = path
        self._backup_directory = os.path.join(os.path.dirname(path), "config_backups")
    
    def load(self, path: Optional[str] = None) -> bool:
        """Load configuration from file."""
        config_path = path or self._config_path
        if not config_path:
            config_path = os.path.join(self.config.data_directory, "platform_config.json")
        
        if not os.path.exists(config_path):
            return True  # Use defaults
        
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                self._apply_config_data(data)
            return True
        except Exception as e:
            print(f"Error loading config: {e}")
            return False
    
    def save(self, path: Optional[str] = None, backup: bool = True) -> bool:
        """Save configuration to file."""
        config_path = path or self._config_path
        if not config_path:
            config_path = os.path.join(self.config.data_directory, "platform_config.json")
        
        try:
            # Create backup if enabled
            if backup and os.path.exists(config_path):
                self._create_backup(config_path)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(self._to_dict(), f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def _apply_config_data(self, data: Dict[str, Any]):
        """Apply configuration data from dictionary."""
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
        self.config.plugin_directory = data.get("plugin_directory", "plugins")
        self.config.auto_save_config = data.get("auto_save_config", True)
        self.config.config_backup_count = data.get("config_backup_count", 5)
    
    def _to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "config_version": self.config.config_version,
            "debug_mode": self.config.debug_mode,
            "log_level": self.config.log_level,
            "data_directory": self.config.data_directory,
            "backup_directory": self.config.backup_directory,
            "enable_plugins": self.config.enable_plugins,
            "enable_event_bus": self.config.enable_event_bus,
            "enable_command_framework": self.config.enable_command_framework,
            "max_event_history": self.config.max_event_history,
            "max_command_history": self.config.max_command_history,
            "plugin_directory": self.config.plugin_directory,
            "auto_save_config": self.config.auto_save_config,
            "config_backup_count": self.config.config_backup_count
        }
    
    def _create_backup(self, config_path: str):
        """Create a backup of the current configuration."""
        if not self._backup_directory:
            self._backup_directory = os.path.join(os.path.dirname(config_path), "config_backups")
        
        os.makedirs(self._backup_directory, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self._backup_directory, f"platform_config_{timestamp}.json")
        
        try:
            import shutil
            shutil.copy2(config_path, backup_path)
            
            # Clean old backups
            self._clean_old_backups()
        except Exception as e:
            print(f"Error creating config backup: {e}")
    
    def _clean_old_backups(self):
        """Remove old configuration backups."""
        if not self._backup_directory or not os.path.exists(self._backup_directory):
            return
        
        backups = []
        for filename in os.listdir(self._backup_directory):
            if filename.startswith("platform_config_") and filename.endswith(".json"):
                backup_path = os.path.join(self._backup_directory, filename)
                backups.append((backup_path, os.path.getmtime(backup_path)))
        
        # Sort by modification time (oldest first)
        backups.sort(key=lambda x: x[1])
        
        # Remove excess backups
        while len(backups) > self.config.config_backup_count:
            backup_path, _ = backups.pop(0)
            try:
                os.remove(backup_path)
            except Exception as e:
                print(f"Error removing old backup {backup_path}: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return getattr(self.config, key, default)
    
    def set(self, key: str, value: Any, auto_save: bool = True) -> bool:
        """Set a configuration value."""
        if not hasattr(self.config, key):
            return False
        
        setattr(self.config, key, value)
        
        if auto_save and self.config.auto_save_config:
            return self.save()
        
        return True
    
    def reset_to_defaults(self) -> bool:
        """Reset configuration to defaults."""
        self.config = PlatformConfig()
        if self.config.auto_save_config:
            return self.save()
        return True
    
    def validate(self) -> Dict[str, Any]:
        """Validate configuration settings."""
        issues = []
        
        if not self.config.data_directory:
            issues.append("data_directory cannot be empty")
        
        if not self.config.backup_directory:
            issues.append("backup_directory cannot be empty")
        
        if self.config.max_event_history < 0:
            issues.append("max_event_history cannot be negative")
        
        if self.config.max_command_history < 0:
            issues.append("max_command_history cannot be negative")
        
        if self.config.config_backup_count < 0:
            issues.append("config_backup_count cannot be negative")
        
        if self.config.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            issues.append(f"Invalid log_level: {self.config.log_level}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all configuration settings."""
        return self._to_dict()


class ConfigValidator:
    """Validator for configuration values."""
    
    @staticmethod
    def validate_log_level(log_level: str) -> bool:
        """Validate log level."""
        return log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    
    @staticmethod
    def validate_directory_path(path: str) -> bool:
        """Validate directory path."""
        if not path:
            return False
        # Check if path is valid (doesn't contain invalid characters)
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        return not any(char in path for char in invalid_chars)
    
    @staticmethod
    def validate_positive_integer(value: int) -> bool:
        """Validate positive integer."""
        return isinstance(value, int) and value >= 0
    
    @staticmethod
    def validate_boolean(value: Any) -> bool:
        """Validate boolean value."""
        return isinstance(value, bool)


class ConfigMigration:
    """Migration handler for configuration versions."""
    
    @staticmethod
    def migrate(data: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """Migrate configuration from one version to another."""
        if from_version == to_version:
            return data
        
        # Handle version migrations
        if from_version == "1.0" and to_version == "1.0":
            return data
        
        # Add future migration logic here
        
        return data
