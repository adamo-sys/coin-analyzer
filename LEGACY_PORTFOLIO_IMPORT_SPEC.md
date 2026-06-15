# Legacy Portfolio Import Spec

## Purpose

Add future support for importing Adam's legacy Excel workbook as a portfolio source:

`C:\Users\<username>\Desktop\Adam_Collection_Portfolio_PRO_LEVEL.xlsx`

This is a design spec only. No importer is implemented yet.

The importer must never destroy, overwrite, or replace existing app data. It should import into a reviewable staging flow first, then merge selected records into the app collection only after explicit user confirmation.

## Workbook Inspection Summary

Inspected workbook sheets:

- `DASHBOARD`
- `UPGRADE_TARGETS`
- `SLABS`
- `CORE_RAW`
- `TRADE_SELL`
- `WATCHLIST`
- `TARGETS`
- `DENOMINATION_LOOKUP`
- `README`
- `LOOKUPS`
- `SILVER_PRICE_LOG`
- `ASW_REFERENCE`
- `SUBMISSION_TRACKER`
- `TOP_25_SHOWCASE`
- `WANT_LIST`
- `MARKET_WATCH`
- `REGRET_SALES`
- `INSURANCE_AUDIT`

Useful sheets requested for this import design:

- `CORE_RAW`
- `SLABS`
- `UPGRADE_TARGETS`
- `ASW_REFERENCE`
- `DASHBOARD`
- `WANT_LIST`
- `TARGETS`

## Useful Sheets

### CORE_RAW

Primary raw portfolio inventory. It has 819 data rows plus headers and appears to contain mostly raw coins imported from Numista plus manually enriched portfolio fields.

Columns:

- `Item`
- `Type`
- `Year`
- `Denomination`
- `Variety`
- `Grade`
- `Certifier`
- `Certification #`
- `Purchase Price`
- `Estimated Value`
- `Running Total`
- `Status`
- `Liquidity Score`
- `Notes`
- `Acquired From`
- `Date Acquired`
- `Source`
- `Numista #`
- `Bullion Value CAD`
- `Dealer Bid CAD`
- `Retail Value CAD`
- `Priority`
- `Silver?`
- `ASW oz`
- `Portfolio Category`
- `Disposition`
- `Eye Appeal`
- `Liquidity`
- `Attribution Confidence`
- `Rarity`
- `Acquisition Source`
- `Submission Candidate`
- `Expected Grade`
- `Upside Potential`
- `Collection Tier`

### SLABS

Certified/slabbed inventory. It has 43 data rows plus headers and shares the first 25 columns with `CORE_RAW`.

Columns:

- `Item`
- `Type`
- `Year`
- `Denomination`
- `Variety`
- `Grade`
- `Certifier`
- `Certification #`
- `Purchase Price`
- `Estimated Value`
- `Running Total`
- `Status`
- `Liquidity Score`
- `Notes`
- `Acquired From`
- `Date Acquired`
- `Source`
- `Numista #`
- `Bullion Value CAD`
- `Dealer Bid CAD`
- `Retail Value CAD`
- `Priority`
- `Silver?`
- `ASW oz`
- `Portfolio Category`

### UPGRADE_TARGETS

Curated upgrade-planning sheet. It should feed future Upgrade Advisor logic rather than direct `CoinItem` import.

Columns:

- `Tier`
- `Source Row`
- `Current Item`
- `Current Grade`
- `Current Est. CAD`
- `Target Grade/Format`
- `Target Budget CAD`
- `Priority`
- `Upgrade Thesis`
- `Action on Current Example`
- `Notes`

### ASW_REFERENCE

Silver reference table for melt-value calculations. It should feed a future Melt Value Engine.

Columns:

- `Country/Series`
- `Denomination`
- `Year Range`
- `ASW oz`
- `Notes`

### DASHBOARD

Workbook summary/dashboard sheet. It contains summary cells, counts, silver spot notes, and portfolio status values. It should not be imported directly.

Observed labels include:

- `Latest Silver Spot CAD/oz`
- `Latest Spot Date`
- `CORE_RAW Entries`
- `SLABS Entries`
- `CORE_RAW Estimated Total`

### WANT_LIST

Manual want-list sheet. Currently only headers were observed. It should feed or seed the app's Want List Generator once supported.

Columns:

- `Target Coin`
- `Priority`
- `Target Grade`
- `Budget`
- `Why Wanted`
- `Status`

### TARGETS

Acquisition target staging sheet. It has the same basic inventory-style columns as `CORE_RAW`, but currently only headers were observed.

Columns:

- `Item`
- `Type`
- `Year`
- `Denomination`
- `Variety`
- `Grade`
- `Certifier`
- `Certification #`
- `Purchase Price`
- `Estimated Value`
- `Running Total`
- `Status`
- `Liquidity Score`
- `Notes`
- `Acquired From`
- `Date Acquired`
- `Source`
- `Numista #`

## CoinItem Field Mapping

The future importer should map inventory rows from `CORE_RAW` and `SLABS` into `CoinItem` fields as follows.

| Workbook column | CoinItem field | Notes |
| --- | --- | --- |
| `Item` | `title` | Preserve full display name. May also help infer country. |
| `Year` | `year` | Convert numeric years to strings without decimals. |
| `Denomination` | `denomination` | Normalize casing later; preserve original text at import. |
| `Variety` | `reference` and/or `comments` | Useful for KM references, Narrow 9/Wide 9, 8 over 9, and attribution notes. |
| `Grade` | `grade` | Preserve as entered. Future validation should normalize grade scale. |
| `Certifier` | future field | Current app has no certifier field. For now append to `comments` or hold in staging metadata. |
| `Certification #` | future field | Current app has no certification-number field. Do not squeeze into `numista_n`. |
| `Purchase Price` | future field | Cost basis. Do not map to `estimate_cad`. |
| `Estimated Value` | `estimate_cad` | Map to current app estimate when numeric. |
| `Status` | future field | KEEP/SELL/etc. Should become portfolio status. |
| `Liquidity Score` | future field | Should feed Buy Advisor/Auction Evaluator, not current `detection_confidence`. |
| `Notes` | `notes` and/or `comments` | Preserve all user notes. |
| `Acquired From` | future field | Provenance/dealer source. |
| `Date Acquired` | `date_added` or future field | Prefer future `date_acquired`; use `date_added` only if no better field exists. |
| `Source` | `comments` or future field | Preserve source metadata. |
| `Numista #` | `numista_n` | Strip `N#` prefix consistently if existing app expects number only. |
| `Bullion Value CAD` | future field | Feed Melt Value Engine. |
| `Dealer Bid CAD` | future field | Feed Buy Advisor/Auction Evaluator. |
| `Retail Value CAD` | future field | Feed value model. |
| `Priority` | future field | Feed acquisition priority ranking. |
| `Silver?` | future field | Feed Melt Value Engine. |
| `ASW oz` | future field | Feed Melt Value Engine. |
| `Portfolio Category` | future field | Feed collection segmentation. |

Fields not present in workbook:

- `id`: generate stable IDs such as `legacy_core_raw_<row_number>` or a hash of sheet, row, item, year, denomination, and certification number.
- `image_path`: leave blank.
- `country`: infer from `Item` where reliable, but stage for review when ambiguous.
- `quantity`: default to 1 unless future workbook versions include quantity.
- `auto_detected`: set false.
- `detection_confidence`: set 0.0.
- `from_numista`: set true only when `Source` or `Numista #` clearly indicates Numista; otherwise false or a future `source_type`.

## Future App Features From Workbook Fields

The workbook contains data that should become first-class app features later:

- Certified holder metadata: `Certifier`, `Certification #`
- Cost basis: `Purchase Price`
- Portfolio status: `Status`, `Disposition`
- Liquidity model: `Liquidity Score`, `Liquidity`
- Melt model: `Silver?`, `ASW oz`, `Bullion Value CAD`
- Dealer/retail value model: `Dealer Bid CAD`, `Retail Value CAD`
- Acquisition ranking: `Priority`, `Upside Potential`, `Collection Tier`
- Attribution confidence: `Attribution Confidence`
- Eye appeal and rarity: `Eye Appeal`, `Rarity`
- Provenance: `Acquired From`, `Acquisition Source`, `Date Acquired`
- Submission workflow: `Submission Candidate`, `Expected Grade`
- Upgrade workflow: `UPGRADE_TARGETS`
- Want-list workflow: `WANT_LIST` and `TARGETS`

## Data That Should Not Be Imported Directly

Do not directly import:

- `DASHBOARD`: summary and formula-style status data, not item-level records.
- `Running Total`: workbook-derived calculation.
- `CORE_RAW` / `SLABS` formula outputs without preserving their source fields.
- `UPGRADE_TARGETS` as collection holdings.
- `ASW_REFERENCE` as coin holdings.
- Empty `WANT_LIST` / `TARGETS` rows.
- Market/watch/regret/insurance sheets until separate workflows are designed.
- Any data that would overwrite existing `data/collection.json`.

## Importer Design

Future module name: `legacy_portfolio_importer.py`

Proposed design:

1. Open workbook read-only with `openpyxl`.
2. Validate required sheets and headers.
3. Parse `CORE_RAW` and `SLABS` into staging records.
4. Normalize year, denomination, Numista number, and estimate values.
5. Generate stable legacy IDs.
6. Detect duplicates against existing `CoinCollection` using:
   - Numista number
   - Certification number
   - Country/title + denomination + year + variety
7. Present an import preview:
   - New records
   - Probable duplicates
   - Ambiguous country/title rows
   - Rows requiring manual review
8. Import only selected rows after explicit user confirmation.
9. Write a timestamped backup of `data/collection.json` before any confirmed merge.
10. Preserve workbook-only fields in a future metadata structure or append them to `comments` until first-class fields exist.

Do not implement direct overwrite import behavior.

## How Workbook Data Should Feed Existing/Future Systems

### Collection Gap Report

Use `CORE_RAW` and `SLABS` as richer inventory sources. They improve date-run detection, variety tracking, and completion percentages, especially for Newfoundland, 1859 Large Cents, and Canadian silver.

### Want List Generator

Use `WANT_LIST`, `TARGETS`, and `UPGRADE_TARGETS` as curated human intent. These should boost generated acquisition targets rather than replace engine-generated want-list logic.

### Buy Advisor

Feed these fields into recommendation quality:

- `Estimated Value`
- `Dealer Bid CAD`
- `Retail Value CAD`
- `Liquidity Score`
- `Priority`
- `Status`
- `Collection Tier`
- `Upside Potential`

### Melt Value Engine

Use:

- `ASW_REFERENCE`
- `Silver?`
- `ASW oz`
- `Bullion Value CAD`
- workbook silver spot notes from `DASHBOARD` / `SILVER_PRICE_LOG`

The melt engine should compute melt values from ASW and current spot, while preserving workbook bullion values as imported references.

### Upgrade Advisor

Use `UPGRADE_TARGETS` as the initial upgrade-planning source. It contains current item, current grade, target grade, budget, priority, upgrade thesis, and recommended action on the current example.

## Open Questions Before Implementation

- Should country be inferred from `Item`, or should the workbook gain an explicit `Country` column first?
- Should legacy-only fields be stored in a generic metadata object, added to `CoinItem`, or normalized into separate portfolio tables?
- Should `CORE_RAW` rows with `Status` other than `KEEP` be imported as active holdings?
- Should Numista numbers preserve the `N#` prefix or match the existing numeric-only importer convention?
- Should `Purchase Price` be private/local-only data excluded from general exports?
