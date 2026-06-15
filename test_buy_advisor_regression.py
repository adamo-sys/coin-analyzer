"""
Buy Advisor Regression Tests
Comprehensive tests for Buy Advisor functionality including Tasks 11 and 12.
"""

from buy_advisor import BuyAdvisor
from coin_collection import CoinCollection


def run_regression_tests():
    """Run comprehensive regression tests for Buy Advisor."""
    collection = CoinCollection('data/collection.json')
    advisor = BuyAdvisor(collection)
    
    print("=" * 80)
    print("BUY ADVISOR REGRESSION TESTS")
    print("=" * 80)
    
    # Test 1: Duplicate with price
    print("\n" + "=" * 80)
    print("TEST 1: Duplicate with price")
    print("=" * 80)
    rec = advisor.advise("Argentina", "1.0", "1960", asking_price=2.00, shipping=1.00, tax_fees=0.20)
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Price Verdict: {rec.price_verdict}")
    print(f"Purchase Verdict: {rec.purchase_verdict}")
    print(f"Max Rational Bid: ${rec.max_rational_bid:.2f}")
    print(f"Landed Cost: ${rec.landed_cost:.2f}")
    print(f"Adam Priority Score: {rec.adam_priority_score}")
    print(f"Liquidity Score: {rec.liquidity_score}")
    print(f"Warnings: {rec.warnings}")
    print(f"Expected: PASS (duplicate)")
    
    # Test 2: Strong Buy under max bid
    print("\n" + "=" * 80)
    print("TEST 2: Strong Buy under max bid")
    print("=" * 80)
    rec = advisor.advise("Canada", "1 cent", "1967", asking_price=0.50, shipping=2.00, tax_fees=0.10)
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Price Verdict: {rec.price_verdict}")
    print(f"Purchase Verdict: {rec.purchase_verdict}")
    print(f"Max Rational Bid: ${rec.max_rational_bid:.2f}")
    print(f"Landed Cost: ${rec.landed_cost:.2f}")
    print(f"Adam Priority Score: {rec.adam_priority_score}")
    print(f"Liquidity Score: {rec.liquidity_score}")
    print(f"Warnings: {rec.warnings}")
    print(f"Expected: BUY NOW (Strong Buy + Good price)")
    
    # Test 3: Strong Buy overpriced
    print("\n" + "=" * 80)
    print("TEST 3: Strong Buy overpriced")
    print("=" * 80)
    rec = advisor.advise("Canada", "1 cent", "1967", asking_price=10.00, shipping=2.00, tax_fees=1.00)
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Price Verdict: {rec.price_verdict}")
    print(f"Purchase Verdict: {rec.purchase_verdict}")
    print(f"Max Rational Bid: ${rec.max_rational_bid:.2f}")
    print(f"Landed Cost: ${rec.landed_cost:.2f}")
    print(f"Adam Priority Score: {rec.adam_priority_score}")
    print(f"Liquidity Score: {rec.liquidity_score}")
    print(f"Warnings: {rec.warnings}")
    print(f"Expected: PASS (overpriced)")
    
    # Test 4: Neutral good price
    print("\n" + "=" * 80)
    print("TEST 4: Neutral good price")
    print("=" * 80)
    rec = advisor.advise("Argentina", "20 cents", "1975", asking_price=0.25, shipping=2.00, tax_fees=0.05)
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Price Verdict: {rec.price_verdict}")
    print(f"Purchase Verdict: {rec.purchase_verdict}")
    print(f"Max Rational Bid: ${rec.max_rational_bid:.2f}")
    print(f"Landed Cost: ${rec.landed_cost:.2f}")
    print(f"Adam Priority Score: {rec.adam_priority_score}")
    print(f"Liquidity Score: {rec.liquidity_score}")
    print(f"Warnings: {rec.warnings}")
    print(f"Expected: BID ONLY (Neutral + Good price)")
    
    # Test 5: Random world base metal
    print("\n" + "=" * 80)
    print("TEST 5: Random world base metal")
    print("=" * 80)
    rec = advisor.advise("Argentina", "20 cents", "1975", asking_price=0.50, shipping=2.00, tax_fees=0.10)
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Price Verdict: {rec.price_verdict}")
    print(f"Purchase Verdict: {rec.purchase_verdict}")
    print(f"Max Rational Bid: ${rec.max_rational_bid:.2f}")
    print(f"Landed Cost: ${rec.landed_cost:.2f}")
    print(f"Adam Priority Score: {rec.adam_priority_score}")
    print(f"Liquidity Score: {rec.liquidity_score}")
    print(f"Warnings: {rec.warnings}")
    print(f"Expected: PASS (Neutral + overpriced)")
    
    # Test 6: No asking price
    print("\n" + "=" * 80)
    print("TEST 6: No asking price")
    print("=" * 80)
    rec = advisor.advise("Canada", "1 cent", "1967")
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Price Verdict: {rec.price_verdict}")
    print(f"Purchase Verdict: {rec.purchase_verdict}")
    print(f"Max Rational Bid: ${rec.max_rational_bid:.2f}")
    print(f"Landed Cost: ${rec.landed_cost:.2f}")
    print(f"Adam Priority Score: {rec.adam_priority_score}")
    print(f"Liquidity Score: {rec.liquidity_score}")
    print(f"Warnings: {rec.warnings}")
    print(f"Expected: BID ONLY (Buy + no asking price)")
    
    # Test 7: No value data
    print("\n" + "=" * 80)
    print("TEST 7: No value data")
    print("=" * 80)
    rec = advisor.advise("Canada", "1 cent", "1967", asking_price=5.00, shipping=2.00, tax_fees=0.50)
    print(f"Final Recommendation: {rec.recommendation}")
    print(f"Price Verdict: {rec.price_verdict}")
    print(f"Purchase Verdict: {rec.purchase_verdict}")
    print(f"Max Rational Bid: ${rec.max_rational_bid:.2f}")
    print(f"Landed Cost: ${rec.landed_cost:.2f}")
    print(f"Adam Priority Score: {rec.adam_priority_score}")
    print(f"Liquidity Score: {rec.liquidity_score}")
    print(f"Warnings: {rec.warnings}")
    print(f"Expected: Cannot price-check (no value data)")
    
    print("\n" + "=" * 80)
    print("REGRESSION TESTS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    run_regression_tests()
