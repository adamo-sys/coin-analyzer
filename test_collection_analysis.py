"""
Test collection analysis functionality.
"""

from coin_collection import CoinCollection

def test_collection_analysis():
    """Test collection analysis."""
    collection = CoinCollection('data/collection.json')
    
    print(f"Total coins: {len(collection.items)}")
    
    # Test autocomplete
    print("\n=== Autocomplete Test ===")
    suggestions = collection.get_autocomplete_suggestions('country', 'can')
    print(f"Country suggestions for 'can': {suggestions[:5]}")
    
    suggestions = collection.get_autocomplete_suggestions('denomination', '1')
    print(f"Denomination suggestions for '1': {suggestions[:5]}")
    
    # Test find matching coins
    print("\n=== Find Matching Coins Test ===")
    matches = collection.find_matching_coins('Canada', 'Nickel', '2000')
    print(f"Matches for Canada/Nickel/2000: {len(matches)}")
    
    # Test collection analysis
    print("\n=== Collection Analysis Test ===")
    analysis = collection.analyze_collection_gaps()
    print(f"Total coins: {analysis['total_coins']}")
    print(f"Numista coverage: {analysis['numista_coverage']:.1f}%")
    print(f"Number of countries: {len(analysis['countries'])}")
    print(f"Number of years: {len(analysis['years'])}")
    print(f"Number of denominations: {len(analysis['denominations'])}")
    
    print("\n=== Top 5 Countries ===")
    for country, count in sorted(analysis['countries'].items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {country}: {count}")
    
    print("\n=== Top 5 Denominations ===")
    for denom, count in sorted(analysis['denominations'].items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {denom}: {count}")

if __name__ == "__main__":
    test_collection_analysis()
