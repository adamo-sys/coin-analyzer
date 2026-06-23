"""
Tests for Platform Core module
"""

import unittest
from platform_core import Platform, PlatformService, ServiceRegistry, PlatformConfig, PlatformState


class TestPlatformService(unittest.TestCase):
    """Test cases for PlatformService."""
    
    def test_service_creation(self):
        """Test creating a platform service."""
        service = PlatformService(
            name="test_service",
            version="1.0",
            description="Test service"
        )
        self.assertEqual(service.name, "test_service")
        self.assertEqual(service.version, "1.0")
        self.assertEqual(service.status, "registered")
    
    def test_service_with_dependencies(self):
        """Test service with dependencies."""
        service = PlatformService(
            name="test_service",
            version="1.0",
            description="Test service",
            dependencies=["dep1", "dep2"]
        )
        self.assertEqual(len(service.dependencies), 2)


class TestServiceRegistry(unittest.TestCase):
    """Test cases for ServiceRegistry."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.registry = ServiceRegistry()
    
    def test_register_service(self):
        """Test registering a service."""
        service = PlatformService(
            name="test_service",
            version="1.0",
            description="Test service"
        )
        result = self.registry.register(service)
        self.assertTrue(result)
    
    def test_register_duplicate(self):
        """Test registering duplicate service."""
        service = PlatformService(
            name="test_service",
            version="1.0",
            description="Test service"
        )
        self.registry.register(service)
        result = self.registry.register(service)
        self.assertFalse(result)
    
    def test_get_service(self):
        """Test getting a service."""
        service = PlatformService(
            name="test_service",
            version="1.0",
            description="Test service"
        )
        self.registry.register(service)
        retrieved = self.registry.get("test_service")
        self.assertEqual(retrieved.name, "test_service")
    
    def test_get_all_services(self):
        """Test getting all services."""
        service1 = PlatformService(name="s1", version="1.0", description="Service 1")
        service2 = PlatformService(name="s2", version="1.0", description="Service 2")
        self.registry.register(service1)
        self.registry.register(service2)
        services = self.registry.get_all()
        self.assertEqual(len(services), 2)
    
    def test_unregister_service(self):
        """Test unregistering a service."""
        service = PlatformService(
            name="test_service",
            version="1.0",
            description="Test service"
        )
        self.registry.register(service)
        result = self.registry.unregister("test_service")
        self.assertTrue(result)
        self.assertIsNone(self.registry.get("test_service"))
    
    def test_get_dependencies(self):
        """Test getting service dependencies."""
        service1 = PlatformService(name="s1", version="1.0", description="Service 1")
        service2 = PlatformService(
            name="s2",
            version="1.0",
            description="Service 2",
            dependencies=["s1"]
        )
        self.registry.register(service1)
        self.registry.register(service2)
        deps = self.registry.get_dependencies("s2")
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0].name, "s1")


class TestPlatformConfig(unittest.TestCase):
    """Test cases for PlatformConfig."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = PlatformConfig()
        self.assertEqual(config.config_version, "1.0")
        self.assertFalse(config.debug_mode)
        self.assertEqual(config.log_level, "INFO")
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = PlatformConfig(
            debug_mode=True,
            log_level="DEBUG"
        )
        self.assertTrue(config.debug_mode)
        self.assertEqual(config.log_level, "DEBUG")


class TestPlatformState(unittest.TestCase):
    """Test cases for PlatformState."""
    
    def test_default_state(self):
        """Test default state."""
        state = PlatformState()
        self.assertEqual(state.platform_version, "7.0")
        self.assertIsNone(state.start_time)
        self.assertEqual(state.service_count, 0)


class TestPlatform(unittest.TestCase):
    """Test cases for Platform."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.platform = Platform()
    
    def test_platform_creation(self):
        """Test creating a platform."""
        self.assertIsNotNone(self.platform.config)
        self.assertIsNotNone(self.platform.state)
        self.assertIsNotNone(self.platform.service_registry)
    
    def test_register_service(self):
        """Test registering a service."""
        service = PlatformService(
            name="test_service",
            version="1.0",
            description="Test service"
        )
        result = self.platform.register_service(service)
        self.assertTrue(result)
    
    def test_get_service(self):
        """Test getting a service."""
        service = PlatformService(
            name="test_service",
            version="1.0",
            description="Test service"
        )
        self.platform.register_service(service)
        retrieved = self.platform.get_service("test_service")
        self.assertEqual(retrieved.name, "test_service")
    
    def test_get_all_services(self):
        """Test getting all services."""
        service1 = PlatformService(name="s1", version="1.0", description="Service 1")
        service2 = PlatformService(name="s2", version="1.0", description="Service 2")
        self.platform.register_service(service1)
        self.platform.register_service(service2)
        services = self.platform.get_all_services()
        self.assertEqual(len(services), 2)
    
    def test_health_check(self):
        """Test platform health check."""
        service = PlatformService(
            name="test_service",
            version="1.0",
            description="Test service",
            health_check=lambda: {"status": "healthy"}
        )
        self.platform.register_service(service)
        health = self.platform.health_check()
        self.assertIn("test_service", health)
    
    def test_get_platform_info(self):
        """Test getting platform info."""
        info = self.platform.get_platform_info()
        self.assertIn("platform_version", info)
        self.assertIn("initialized", info)


if __name__ == '__main__':
    unittest.main()
