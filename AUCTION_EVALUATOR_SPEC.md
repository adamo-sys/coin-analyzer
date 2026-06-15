# Auction Evaluator Spec

## Purpose

The future Auction Evaluator will help decide whether an auction lot is worth bidding on. It must consume the Collection Intelligence Engine instead of duplicating collection analysis logic.

## Out Of Scope

- No auction evaluator implementation yet.
- No live auction scraping.
- No automated bidding.
- No external pricing integrations until value-source rules are defined.

## Inputs

The evaluator should accept:

- Country
- Denomination
- Year
- Reference or variety
- Grade
- Asking price or current bid
- Shipping
- Tax and fees
- Estimated market value
- Seller notes
- Lot URL
- Optional image paths

## Collection Intelligence Engine Inputs

The evaluator should instantiate `CollectionIntelligenceEngine` with the current collection items:

```python
engine = CollectionIntelligenceEngine(collection.get_all_items())
```

It should consume:

- `analyze_by_country()`
- `analyze_by_denomination()`
- `analyze_by_series()`
- `detect_missing_years()`
- `detect_duplicates()`
- `detect_upgrade_candidates()`
- `generate_acquisition_priorities()`
- `generate_want_list()`

## Decision Factors

The evaluator should use these factors:

1. Missing date or variety
2. Completion impact on date run
3. Adam-specific priority score
4. Duplicate risk
5. Upgrade potential
6. Estimated market value
7. Landed cost
8. Liquidity
9. Confidence in attribution
10. Budget fit

## Adam-Specific Priority Handling

High priority:

- Newfoundland coinage, especially 5 cent, 10 cent, 20 cent, and 50 cent date runs
- 1859 Canadian Large Cent varieties
- Canadian silver dimes, quarters, half dollars, and dollars
- Missing dates that improve date-run completion
- Quality upgrades over duplicate accumulation
- Underpriced lots with clear collection impact

Low priority:

- Low-impact duplicates
- Poorly attributed varieties
- Lots with no clear collection gap or upgrade value
- Overpriced common material

## Expected Outputs

The evaluator should return:

- Recommendation: `BUY`, `BID`, `WATCH`, or `PASS`
- Maximum rational bid
- Landed cost
- Collection impact summary
- Duplicate or upgrade status
- Priority reasons
- Warnings
- Confidence score

## Export Formats

Future exports should support:

- Markdown auction evaluation summary
- CSV batch evaluation report

## Testing Expectations

Tests should use isolated fixtures in `test_data/` and must not mutate `data/collection.json`.
