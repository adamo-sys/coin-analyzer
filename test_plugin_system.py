"""
Tests for Plugin System module
"""

import unittest
from plugin_system import Plugin, PluginManifest, PluginManager, PluginContext


class TestPluginManifest(unittest.TestCase):
    """Test cases for PluginManifest."""
    
    def test_manifest_creation(self):
        """Test creating a plugin manifest."""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0",
            description="Test plugin",
            author="Test Author"
        )
        self.assertEqual(manifest.name, "test_plugin")
        self.assertEqual(manifest.version, "1.0")
    
    def test_manifest_with_dependencies(self):
        """Test manifest with dependencies."""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0",
            description="Test plugin",
            author="Test Author",
            dependencies=["dep1", "dep2"]
        )
        self.assertEqual(len(manifest.dependencies), 2)


class TestPlugin(unittest.TestCase):
    """Test cases for Plugin."""
    
    def test_plugin_creation(self):
        """Test creating a plugin."""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0",
            description="Test plugin",
            author="Test Author"
        )
        plugin = Plugin(manifest=manifest)
        self.assertEqual(plugin.manifest.name, "test_plugin")
        self.assertEqual(plugin.status, "loaded")


class TestPluginManager(unittest.TestCase):
    """Test cases for PluginManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        from platform_core import Platform
        self.platform = Platform()
        self.manager = PluginManager(self.platform)
    
    def test_register_plugin(self):
        """Test registering a plugin."""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0",
            description="Test plugin",
            author="Test Author"
        )
        result = self.manager.register_plugin(manifest)
        self.assertTrue(result)
    
    def test_register_duplicate_plugin(self):
        """Test registering duplicate plugin."""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0",
            description="Test plugin",
            author="Test Author"
        )
        self.manager.register_plugin(manifest)
        result = self.manager.register_plugin(manifest)
        self.assertFalse(result)
    
    def test_get_plugin(self):
        """Test getting a plugin."""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0",
            description="Test plugin",
            author="Test Author"
        )
        self.manager.register_plugin(manifest)
        plugin = self.manager.get_plugin("test_plugin")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.manifest.name, "test_plugin")
    
    def test_get_all_plugins(self):
        """Test getting all plugins."""
        manifest1 = PluginManifest(name="p1", version="1.0", description="Plugin 1", author="A")
        manifest2 = PluginManifest(name="p2", version="1.0", description="Plugin 2", author="B")
        self.manager.register_plugin(manifest1)
        self.manager.register_plugin(manifest2)
        plugins = self.manager.get_all_plugins()
        self.assertEqual(len(plugins), 2)
    
    def test_unregister_plugin(self):
        """Test unregistering a plugin."""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0",
            description="Test plugin",
            author="Test Author"
        )
        self.manager.register_plugin(manifest)
        result = self.manager.unregister_plugin("test_plugin")
        self.assertTrue(result)
        self.assertIsNone(self.manager.get_plugin("test_plugin"))
    
    def test_validate_plugin(self):
        """Test validating a plugin."""
        manifest = PluginManifest(
            name="test_plugin",
            version="1.0",
            description="Test plugin",
            author="Test Author",
            platform_version="7.0"
        )
        self.manager.register_plugin(manifest)
        validation = self.manager.validate_plugin("test_plugin")
        self.assertTrue(validation["valid"])


if __name__ == '__main__':
    unittest.main()
