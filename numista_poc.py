"""
Proof-of-Concept Numista API Integration
Demonstrates coin search using Numista API
"""

import requests
import json
import os

class NumistaPOC:
    """Proof-of-concept Numista API integration."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('NUMISTA_API_KEY')
        self.base_url = "https://api.numista.com/api/v1"
        
        if not self.api_key:
            print("WARNING: No API key provided. Set NUMISTA_API_KEY environment variable or pass api_key parameter.")
            print("Get your API key from: https://en.numista.com/api/index.php")
    
    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated request to Numista API."""
        if not self.api_key:
            return {"error": "No API key configured"}
        
        headers = {
            "Numista-API-Key": self.api_key
        }
        
        try:
            url = f"{self.base_url}/{endpoint}"
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def search_coins(self, query: str, issuer: str = None) -> dict:
        """Search for coins by denomination and country."""
        params = {"q": query}
        if issuer:
            params["issuer"] = issuer
        
        result = self._make_request("types", params)
        return result
    
    def get_issuers(self) -> dict:
        """Get list of all countries/issuers."""
        return self._make_request("issuers")
    
    def get_coin_details(self, coin_id: int) -> dict:
        """Get detailed information about a specific coin."""
        return self._make_request(f"types/{coin_id}")
    
    def search_by_image_demo(self, image_path: str) -> dict:
        """
        Demonstrate image search (requires activated search-by-image feature).
        Note: This requires additional activation and billing setup.
        """
        if not self.api_key:
            return {"error": "Image search requires API key activation and billing setup"}
        
        # Image search endpoint (requires activation)
        # This is a placeholder - actual implementation depends on API documentation
        return {
            "message": "Image search requires activation of 'search by image' feature",
            "requirements": [
                "1. Activate search by image in API settings",
                "2. Set up billing (minimum €100/month)",
                "3. Use appropriate endpoint (documentation restricted)"
            ],
            "status": "Not implemented - requires API access"
        }
    
    def test_basic_search(self):
        """Test basic search functionality."""
        print("=" * 60)
        print("Numista API Proof-of-Concept Test")
        print("=" * 60)
        
        if not self.api_key:
            print("\nERROR: No API key configured")
            print("Get your API key from: https://en.numista.com/api/index.php")
            print("Then set environment variable: set NUMISTA_API_KEY=your_key")
            return
        
        print(f"\nAPI Key configured: {self.api_key[:10]}..." if len(self.api_key) > 10 else f"API Key configured: {self.api_key}")
        
        # Test 1: Get issuers
        print("\n[Test 1] Getting list of issuers...")
        issuers = self.get_issuers()
        if "error" in issuers:
            print(f"  ERROR: {issuers['error']}")
        else:
            print(f"  SUCCESS: Found {issuers.get('data', {}).get('count', 0)} issuers")
            if issuers.get('data', {}).get('issuers'):
                sample = issuers['data']['issuers'][:5]
                print(f"  Sample issuers: {[i['name'] for i in sample]}")
        
        # Test 2: Search for Canadian pennies
        print("\n[Test 2] Searching for Canadian pennies...")
        pennies = self.search_coins(query="penny", issuer="canada")
        if "error" in pennies:
            print(f"  ERROR: {pennies['error']}")
        else:
            count = pennies.get('data', {}).get('count', 0)
            print(f"  SUCCESS: Found {count} Canadian pennies")
            if pennies.get('data', {}).get('types'):
                sample = pennies['data']['types'][:3]
                for coin in sample:
                    print(f"    - {coin.get('title', 'Unknown')} (ID: {coin.get('id')})")
        
        # Test 3: Search for US dollars
        print("\n[Test 3] Searching for US dollars...")
        dollars = self.search_coins(query="dollar", issuer="etats-unis")
        if "error" in dollars:
            print(f"  ERROR: {dollars['error']}")
        else:
            count = dollars.get('data', {}).get('count', 0)
            print(f"  SUCCESS: Found {count} US dollars")
            if dollars.get('data', {}).get('types'):
                sample = dollars['data']['types'][:3]
                for coin in sample:
                    print(f"    - {coin.get('title', 'Unknown')} (ID: {coin.get('id')})")
        
        # Test 4: Image search demo
        print("\n[Test 4] Image search demonstration...")
        image_result = self.search_by_image_demo("test_coin.jpg")
        print(f"  STATUS: {image_result.get('status', 'Unknown')}")
        if 'requirements' in image_result:
            print("  Requirements:")
            for req in image_result['requirements']:
                print(f"    - {req}")
        
        print("\n" + "=" * 60)
        print("Proof-of-Concept Test Complete")
        print("=" * 60)


def main():
    """Run the proof-of-concept test."""
    # You can set your API key here or use environment variable
    poc = NumistaPOC()
    poc.test_basic_search()


if __name__ == "__main__":
    main()
