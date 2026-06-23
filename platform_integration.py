"""
Platform Integration - Service Integration Layer

This module integrates existing collector services as platform services.
"""

from typing import Dict, Any, Optional, List
from platform_core import Platform, PlatformService, ServiceRegistry
from plugin_system import PluginManager
from command_framework import CommandBus
from event_bus import EventBus
from unified_models import ModelRegistry
from ui_patterns import PlatformUI, UIStateManager
from platform_config import ConfigManager
from platform_state import PlatformStateManager


class PlatformIntegration:
    """Integration layer for connecting existing services to the platform."""
    
    def __init__(self, platform: Platform):
        self.platform = platform
        self.plugin_manager = PluginManager(platform)
        self.command_bus = CommandBus(platform)
        self.event_bus = EventBus(platform)
        self.model_registry = ModelRegistry()
        self.platform_ui = PlatformUI(platform)
        self.ui_state_manager = UIStateManager()
        self.config_manager = ConfigManager(platform.config)
        self.state_manager = PlatformStateManager(platform.config.data_directory)
    
    def initialize(self) -> bool:
        """Initialize all platform components."""
        # Initialize state manager
        if not self.state_manager.initialize():
            return False
        
        # Load configuration
        config_path = f"{self.platform.config.data_directory}/platform_config.json"
        self.config_manager.set_config_path(config_path)
        self.config_manager.load()
        
        # Register core services
        self._register_core_services()
        
        # Register existing collector services
        self._register_collector_services()
        
        return True
    
    def _register_core_services(self):
        """Register core platform services."""
        # Event Bus Service
        event_bus_service = PlatformService(
            name="event_bus",
            version="1.0",
            description="Platform-wide event bus for publish/subscribe communication",
            health_check=lambda: {"status": "healthy", "subscribers": len(self.event_bus.get_all_subscriptions())}
        )
        self.platform.register_service(event_bus_service)
        
        # Command Bus Service
        command_bus_service = PlatformService(
            name="command_bus",
            version="1.0",
            description="Platform command bus for structured command execution",
            health_check=lambda: {"status": "healthy", "commands": len(self.command_bus.get_all())}
        )
        self.platform.register_service(command_bus_service)
        
        # Plugin Manager Service
        plugin_manager_service = PlatformService(
            name="plugin_manager",
            version="1.0",
            description="Plugin system for extensible platform architecture",
            health_check=lambda: {"status": "healthy", "plugins": len(self.plugin_manager.get_all_plugins())}
        )
        self.platform.register_service(plugin_manager_service)
        
        # Model Registry Service
        model_registry_service = PlatformService(
            name="model_registry",
            version="1.0",
            description="Unified data model registry",
            health_check=lambda: {"status": "healthy", "models": len(self.model_registry.get_all())}
        )
        self.platform.register_service(model_registry_service)
    
    def _register_collector_services(self):
        """Register existing collector services as platform services."""
        # Collection Intelligence Service
        collection_intelligence_service = PlatformService(
            name="collection_intelligence",
            version="1.0",
            description="Collection Intelligence Engine for gap analysis, want lists, and duplicate detection",
            dependencies=[],
            health_check=self._collection_intelligence_health_check
        )
        self.platform.register_service(collection_intelligence_service)
        
        # Deal Hunter Service
        deal_hunter_service = PlatformService(
            name="deal_hunter",
            version="1.0",
            description="Deal Hunter for listing evaluation and scoring",
            dependencies=["collection_intelligence"],
            health_check=self._deal_hunter_health_check
        )
        self.platform.register_service(deal_hunter_service)
        
        # Market Intelligence Service
        market_intelligence_service = PlatformService(
            name="market_intelligence",
            version="1.0",
            description="Market Intelligence for fair-value estimation and deal quality",
            dependencies=["deal_hunter"],
            health_check=self._market_intelligence_health_check
        )
        self.platform.register_service(market_intelligence_service)
        
        # Portfolio Performance Service
        portfolio_performance_service = PlatformService(
            name="portfolio_performance",
            version="1.0",
            description="Portfolio Performance for growth analysis and health metrics",
            dependencies=["collection_intelligence", "market_intelligence"],
            health_check=self._portfolio_performance_health_check
        )
        self.platform.register_service(portfolio_performance_service)
        
        # Mobile Companion Service
        mobile_companion_service = PlatformService(
            name="mobile_companion",
            version="1.0",
            description="Mobile Companion for field workflows and mobile context",
            dependencies=["collection_intelligence"],
            health_check=self._mobile_companion_health_check
        )
        self.platform.register_service(mobile_companion_service)
        
        # Collector Cloud Service
        cloud_service = PlatformService(
            name="collector_cloud",
            version="1.0",
            description="Collector Cloud Foundation for cloud-ready architecture",
            dependencies=[],
            health_check=self._cloud_health_check
        )
        self.platform.register_service(cloud_service)
        
        # Sync & Backup Service
        sync_backup_service = PlatformService(
            name="sync_backup",
            version="1.0",
            description="Sync & Backup for disaster recovery and sync planning",
            dependencies=["collector_cloud"],
            health_check=self._sync_backup_health_check
        )
        self.platform.register_service(sync_backup_service)
        
        # Multi-Device Workspace Service
        workspace_service = PlatformService(
            name="multi_device_workspace",
            version="1.0",
            description="Multi-Device Workspace for device profiles and workspace management",
            dependencies=["collector_cloud", "sync_backup"],
            health_check=self._workspace_health_check
        )
        self.platform.register_service(workspace_service)
        
        # Device Linking Service
        device_linking_service = PlatformService(
            name="device_linking",
            version="1.0",
            description="Device Linking & Conflict Resolution for linked devices",
            dependencies=["multi_device_workspace"],
            health_check=self._device_linking_health_check
        )
        self.platform.register_service(device_linking_service)
    
    def _collection_intelligence_health_check(self) -> Dict[str, Any]:
        """Health check for Collection Intelligence service."""
        try:
            # Try to import the module
            import collection_intelligence
            return {"status": "healthy", "module_loaded": True}
        except ImportError:
            return {"status": "unavailable", "module_loaded": False}
    
    def _deal_hunter_health_check(self) -> Dict[str, Any]:
        """Health check for Deal Hunter service."""
        try:
            import deal_hunter
            return {"status": "healthy", "module_loaded": True}
        except ImportError:
            return {"status": "unavailable", "module_loaded": False}
    
    def _market_intelligence_health_check(self) -> Dict[str, Any]:
        """Health check for Market Intelligence service."""
        try:
            import market_intelligence
            return {"status": "healthy", "module_loaded": True}
        except ImportError:
            return {"status": "unavailable", "module_loaded": False}
    
    def _portfolio_performance_health_check(self) -> Dict[str, Any]:
        """Health check for Portfolio Performance service."""
        try:
            import portfolio_performance
            return {"status": "healthy", "module_loaded": True}
        except ImportError:
            return {"status": "unavailable", "module_loaded": False}
    
    def _mobile_companion_health_check(self) -> Dict[str, Any]:
        """Health check for Mobile Companion service."""
        try:
            import mobile_companion
            return {"status": "healthy", "module_loaded": True}
        except ImportError:
            return {"status": "unavailable", "module_loaded": False}
    
    def _cloud_health_check(self) -> Dict[str, Any]:
        """Health check for Collector Cloud service."""
        try:
            import collector_cloud
            return {"status": "healthy", "module_loaded": True}
        except ImportError:
            return {"status": "unavailable", "module_loaded": False}
    
    def _sync_backup_health_check(self) -> Dict[str, Any]:
        """Health check for Sync & Backup service."""
        try:
            import sync_backup
            return {"status": "healthy", "module_loaded": True}
        except ImportError:
            return {"status": "unavailable", "module_loaded": False}
    
    def _workspace_health_check(self) -> Dict[str, Any]:
        """Health check for Multi-Device Workspace service."""
        try:
            import multi_device_workspace
            return {"status": "healthy", "module_loaded": True}
        except ImportError:
            return {"status": "unavailable", "module_loaded": False}
    
    def _device_linking_health_check(self) -> Dict[str, Any]:
        """Health check for Device Linking service."""
        try:
            import device_linking
            return {"status": "healthy", "module_loaded": True}
        except ImportError:
            return {"status": "unavailable", "module_loaded": False}


def create_integrated_platform() -> Platform:
    """Create a fully integrated platform with all services."""
    from platform_core import create_default_platform
    
    platform = create_default_platform()
    integration = PlatformIntegration(platform)
    integration.initialize()
    
    return platform
