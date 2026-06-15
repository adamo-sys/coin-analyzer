"""
Coin Identification Interface
Abstract interface for coin identification methods to allow swapping between implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import numpy as np

class CoinIdentifier(ABC):
    """Abstract interface for coin identification methods."""
    
    @abstractmethod
    def identify_coin(self, image_path: str) -> Dict:
        """
        Identify a coin from an image.
        
        Args:
            image_path: Path to the coin image
            
        Returns:
            Dictionary containing identification results:
            - success: bool - Whether identification succeeded
            - confidence: float - Confidence score (0-1)
            - country: str - Detected country
            - denomination: str - Detected denomination
            - year: str - Detected year
            - composition: str - Coin composition
            - mintage: int - Mintage quantity
            - error: str - Error message if failed
            - method: str - Identification method used
            - debug_info: dict - Debug information
        """
        pass
    
    @abstractmethod
    def search_by_image(self, image_path: str) -> List[Dict]:
        """
        Search for coins by image similarity.
        
        Args:
            image_path: Path to the coin image
            
        Returns:
            List of matching coins with similarity scores
        """
        pass
    
    @abstractmethod
    def get_coin_details(self, coin_id: str) -> Dict:
        """
        Get detailed information about a specific coin.
        
        Args:
            coin_id: Coin identifier
            
        Returns:
            Dictionary with detailed coin information
        """
        pass


class TemplateMatchingIdentifier(CoinIdentifier):
    """Template matching based coin identification (local, experimental)."""
    
    def __init__(self):
        self.method = "template_matching"
        self.debug_folder = "debug_outputs/template_matching"
        import os
        os.makedirs(self.debug_folder, exist_ok=True)
    
    def identify_coin(self, image_path: str) -> Dict:
        """Identify coin using template matching (experimental)."""
        # Placeholder implementation
        return {
            'success': False,
            'confidence': 0.0,
            'country': 'unknown',
            'denomination': 'unknown',
            'year': 'unknown',
            'composition': 'unknown',
            'mintage': 0,
            'error': 'Not implemented',
            'method': self.method,
            'debug_info': {}
        }
    
    def search_by_image(self, image_path: str) -> List[Dict]:
        """Search by image using template matching."""
        return []
    
    def get_coin_details(self, coin_id: str) -> Dict:
        """Get coin details (not applicable for template matching)."""
        return {}


class NumistaIdentifier(CoinIdentifier):
    """Numista API based coin identification (future implementation)."""
    
    def __init__(self, api_key: str = None):
        self.method = "numista_api"
        self.api_key = api_key
        self.available = False  # Will be set to True when API is accessible
    
    def identify_coin(self, image_path: str) -> Dict:
        """Identify coin using Numista API."""
        if not self.available:
            return {
                'success': False,
                'confidence': 0.0,
                'country': 'unknown',
                'denomination': 'unknown',
                'year': 'unknown',
                'composition': 'unknown',
                'mintage': 0,
                'error': 'Numista API not available',
                'method': self.method,
                'debug_info': {}
            }
        # Placeholder for actual Numista implementation
        return {
            'success': False,
            'confidence': 0.0,
            'country': 'unknown',
            'denomination': 'unknown',
            'year': 'unknown',
            'composition': 'unknown',
            'mintage': 0,
            'error': 'Not implemented',
            'method': self.method,
            'debug_info': {}
        }
    
    def search_by_image(self, image_path: str) -> List[Dict]:
        """Search by image using Numista API."""
        if not self.available:
            return []
        return []
    
    def get_coin_details(self, coin_id: str) -> Dict:
        """Get coin details from Numista API."""
        if not self.available:
            return {}
        return {}


class CoinIdentifierFactory:
    """Factory for creating coin identifier instances."""
    
    @staticmethod
    def create_identifier(method: str = "template_matching", **kwargs) -> CoinIdentifier:
        """
        Create a coin identifier instance.
        
        Args:
            method: Identification method ("template_matching" or "numista")
            **kwargs: Additional arguments for the identifier
            
        Returns:
            CoinIdentifier instance
        """
        if method == "template_matching":
            return TemplateMatchingIdentifier()
        elif method == "numista":
            api_key = kwargs.get('api_key')
            return NumistaIdentifier(api_key=api_key)
        else:
            raise ValueError(f"Unknown identification method: {method}")
