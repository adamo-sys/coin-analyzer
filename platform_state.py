"""
Platform State Management - Platform-Wide State Management

This module provides state management for the Collector Platform.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
import json
import os


@dataclass
class StateSnapshot:
    """Snapshot of platform state."""
    snapshot_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    platform_version: str = "7.0"
    state_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformStateManager:
    """Manager for platform-wide state."""
    
    def __init__(self, data_directory: str = "collection_data"):
        self.data_directory = data_directory
        self._state: Dict[str, Any] = {}
        self._snapshots: List[StateSnapshot] = []
        self._state_file = os.path.join(data_directory, "platform_state.json")
        self._snapshot_directory = os.path.join(data_directory, "state_snapshots")
        self._max_snapshots = 10
    
    def initialize(self) -> bool:
        """Initialize state manager."""
        try:
            os.makedirs(self.data_directory, exist_ok=True)
            os.makedirs(self._snapshot_directory, exist_ok=True)
            self.load_state()
            return True
        except Exception as e:
            print(f"Error initializing state manager: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        return self._state.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """Set a state value."""
        self._state[key] = value
        return self.save_state()
    
    def delete(self, key: str) -> bool:
        """Delete a state value."""
        if key in self._state:
            del self._state[key]
            return self.save_state()
        return False
    
    def get_all(self) -> Dict[str, Any]:
        """Get all state values."""
        return self._state.copy()
    
    def clear(self) -> bool:
        """Clear all state values."""
        self._state.clear()
        return self.save_state()
    
    def save_state(self) -> bool:
        """Save state to file."""
        try:
            with open(self._state_file, 'w') as f:
                json.dump(self._state, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving state: {e}")
            return False
    
    def load_state(self) -> bool:
        """Load state from file."""
        if not os.path.exists(self._state_file):
            return True
        
        try:
            with open(self._state_file, 'r') as f:
                self._state = json.load(f)
            return True
        except Exception as e:
            print(f"Error loading state: {e}")
            return False
    
    def create_snapshot(self, metadata: Dict[str, Any] = None) -> Optional[StateSnapshot]:
        """Create a snapshot of current state."""
        snapshot_id = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        snapshot = StateSnapshot(
            snapshot_id=snapshot_id,
            state_data=self._state.copy(),
            metadata=metadata or {}
        )
        
        self._snapshots.append(snapshot)
        
        # Save snapshot to file
        try:
            snapshot_file = os.path.join(self._snapshot_directory, f"{snapshot_id}.json")
            with open(snapshot_file, 'w') as f:
                json.dump({
                    "snapshot_id": snapshot.snapshot_id,
                    "timestamp": snapshot.timestamp.isoformat(),
                    "platform_version": snapshot.platform_version,
                    "state_data": snapshot.state_data,
                    "metadata": snapshot.metadata
                }, f, indent=2)
            
            # Clean old snapshots
            self._clean_old_snapshots()
            
            return snapshot
        except Exception as e:
            print(f"Error saving snapshot: {e}")
            return None
    
    def restore_snapshot(self, snapshot_id: str) -> bool:
        """Restore state from a snapshot."""
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return False
        
        self._state = snapshot.state_data.copy()
        return self.save_state()
    
    def get_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        """Get a snapshot by ID."""
        for snapshot in self._snapshots:
            if snapshot.snapshot_id == snapshot_id:
                return snapshot
        
        # Try loading from file
        snapshot_file = os.path.join(self._snapshot_directory, f"{snapshot_id}.json")
        if os.path.exists(snapshot_file):
            try:
                with open(snapshot_file, 'r') as f:
                    data = json.load(f)
                    snapshot = StateSnapshot(
                        snapshot_id=data["snapshot_id"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        platform_version=data["platform_version"],
                        state_data=data["state_data"],
                        metadata=data["metadata"]
                    )
                    self._snapshots.append(snapshot)
                    return snapshot
            except Exception as e:
                print(f"Error loading snapshot: {e}")
        
        return None
    
    def get_all_snapshots(self) -> List[StateSnapshot]:
        """Get all snapshots."""
        # Load snapshots from directory
        if not self._snapshots:
            self._load_snapshots_from_directory()
        return self._snapshots.copy()
    
    def _load_snapshots_from_directory(self):
        """Load all snapshots from directory."""
        if not os.path.exists(self._snapshot_directory):
            return
        
        for filename in os.listdir(self._snapshot_directory):
            if filename.startswith("snapshot_") and filename.endswith(".json"):
                snapshot_file = os.path.join(self._snapshot_directory, filename)
                try:
                    with open(snapshot_file, 'r') as f:
                        data = json.load(f)
                        snapshot = StateSnapshot(
                            snapshot_id=data["snapshot_id"],
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                            platform_version=data["platform_version"],
                            state_data=data["state_data"],
                            metadata=data["metadata"]
                        )
                        self._snapshots.append(snapshot)
                except Exception as e:
                    print(f"Error loading snapshot {filename}: {e}")
        
        # Sort by timestamp
        self._snapshots.sort(key=lambda s: s.timestamp)
    
    def _clean_old_snapshots(self):
        """Remove old snapshots."""
        while len(self._snapshots) > self._max_snapshots:
            oldest = self._snapshots.pop(0)
            snapshot_file = os.path.join(self._snapshot_directory, f"{oldest.snapshot_id}.json")
            try:
                os.remove(snapshot_file)
            except Exception as e:
                print(f"Error removing old snapshot: {e}")
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return False
        
        self._snapshots.remove(snapshot)
        
        snapshot_file = os.path.join(self._snapshot_directory, f"{snapshot_id}.json")
        try:
            os.remove(snapshot_file)
            return True
        except Exception as e:
            print(f"Error deleting snapshot: {e}")
            return False
    
    def validate_state(self) -> Dict[str, Any]:
        """Validate current state."""
        issues = []
        
        # Check for required keys
        required_keys = ["platform_version", "last_updated"]
        for key in required_keys:
            if key not in self._state:
                issues.append(f"Missing required state key: {key}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get information about current state."""
        return {
            "state_keys": list(self._state.keys()),
            "state_size": len(self._state),
            "snapshot_count": len(self._snapshots),
            "state_file": self._state_file,
            "snapshot_directory": self._snapshot_directory
        }


class StateMigration:
    """Migration handler for state versions."""
    
    @staticmethod
    def migrate_state(state: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """Migrate state from one version to another."""
        if from_version == to_version:
            return state
        
        # Handle version migrations
        if from_version == "7.0" and to_version == "7.0":
            return state
        
        # Add future migration logic here
        
        return state
    
    @staticmethod
    def validate_migration(state: Dict[str, Any], target_version: str) -> Dict[str, Any]:
        """Validate that state can be migrated to target version."""
        issues = []
        
        # Check for version compatibility
        current_version = state.get("platform_version", "unknown")
        
        # Add version-specific validation
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "current_version": current_version,
            "target_version": target_version
        }
