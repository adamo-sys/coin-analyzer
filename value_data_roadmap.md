# Value Data Roadmap

## Current Limitation

Many Numista rows have no Estimate CAD, so Max Bid becomes $0.00. This prevents price analysis from working correctly for coins without value data in the Numista export.

## Needed Future Value Sources

1. **Manual value override**
   - Allow user to manually input estimated market value
   - Override Numista estimate when available
   - Store in collection JSON for persistence

2. **Melt value for silver**
   - Calculate melt value based on silver content and current silver price
   - Apply to silver coins (Newfoundland, Canadian silver, etc.)
   - Provide floor value for price analysis

3. **Recent auction comps**
   - Scrape or import recent auction results
   - Use actual sale prices as value reference
   - Weight recent comps more heavily

4. **Dealer retail comps**
   - Import dealer price lists
   - Use retail prices as upper bound
   - Factor in dealer markups

5. **Numista estimate**
   - Already using Numista estimate when available
   - Continue to use as primary source
   - May need to parse alternative Numista fields

## Proposed Next Feature

Add manual "Estimated Market Value CAD" input in Buy Advisor so price analysis can work even when Numista estimate is missing.

### Implementation Plan

1. Add "Estimated Market Value CAD" field to Buy Advisor GUI
2. Pass manual value to advisor.advise() method
3. Use manual value as fallback when Numista estimate is missing
4. Store manual value in collection JSON for persistence
5. Update max bid calculation to use manual value when provided
6. Add confidence indicator for manual vs Numista values

### Benefits

- Enables price analysis for coins without Numista estimates
- Allows user to incorporate their own market knowledge
- Provides flexibility for rare coins with limited data
- Improves accuracy of purchase verdicts

### Considerations

- Manual values should be clearly marked as user-provided
- Confidence score should reflect source (Numista vs manual)
- Need validation to prevent unrealistic values
- Should allow editing/updating manual values over time
