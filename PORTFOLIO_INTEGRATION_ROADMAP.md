# Portfolio Integration Roadmap

## Purpose

This roadmap breaks the legacy portfolio workbook migration into safe, incremental phases. The workbook source is:

`C:\Users\<username>\Desktop\Adam_Collection_Portfolio_PRO_LEVEL.xlsx`

No phase should overwrite or replace `data/collection.json`. All portfolio imports should begin as reviewable staged records and merge into app data only after explicit user approval.

## Phase 1: Portfolio Inventory Foundation

Scope:

- Import `CORE_RAW`
- Import `SLABS`
- Preserve existing `collection.json`
- Detect duplicates

Deliverables:

- Read-only workbook parser for `CORE_RAW` and `SLABS`
- Header validation
- Staging model for legacy portfolio rows
- Mapping from inventory rows to current `CoinItem` fields plus future metadata
- Duplicate detection against existing collection records
- Import preview showing new rows, likely duplicates, and ambiguous rows
- Timestamped backup before any confirmed merge

Complexity: High

Risks:

- Country is not an explicit workbook column and must be inferred from `Item`
- Workbook-only fields do not fit the current `CoinItem` model
- Duplicate detection may be fuzzy across Numista rows, manual rows, and slabbed rows
- Certification numbers must not be confused with Numista numbers
- Existing app data must not be overwritten

Estimated development effort: 3-5 focused development sessions

Dependencies:

- `LEGACY_PORTFOLIO_IMPORT_SPEC.md`
- Existing `CoinCollection` persistence layer
- Existing test fixture patterns in `test_data/`
- A staging/preview design before any write path is enabled

## Phase 2: Acquisition Intent Integration

Scope:

- Import `WANT_LIST`
- Import `TARGETS`
- Connect to Buy Advisor

Deliverables:

- Parser for `WANT_LIST` target rows
- Parser for `TARGETS` acquisition rows
- Staged want-list records separate from owned holdings
- Buy Advisor support for workbook intent signals such as target grade, budget, priority, and why-wanted notes
- Rules for boosting or suppressing Buy Advisor recommendations based on explicit want-list intent

Complexity: Medium

Risks:

- `WANT_LIST` currently contains headers only, so behavior must tolerate empty sheets
- `TARGETS` may contain planned acquisitions, not holdings
- Target records could be accidentally treated as owned coins if data boundaries are unclear
- Buy Advisor logic may become opaque if workbook priorities are mixed with collection-completion priorities without explanation

Estimated development effort: 2-4 focused development sessions

Dependencies:

- Phase 1 staging model
- Collection Intelligence Engine acquisition target model
- Buy Advisor validation/message improvements
- Clear distinction between owned inventory and desired targets

## Phase 3: Upgrade Planning

Scope:

- Import `UPGRADE_TARGETS`
- Create Upgrade Advisor

Deliverables:

- Parser for `UPGRADE_TARGETS`
- Upgrade target model with current item, current grade, target grade, target budget, thesis, and action on current example
- Upgrade Advisor report ranking upgrade opportunities
- Links between upgrade targets and existing holdings where possible
- Recommendations for keep/sell/trade after upgrade

Complexity: Medium-High

Risks:

- `Source Row` values may refer to workbook row numbers that do not directly match app IDs
- Current item text may need fuzzy matching against collection records
- Upgrade decisions are subjective and should preserve the user's thesis text
- The app should not automatically mark current coins for sale

Estimated development effort: 3-4 focused development sessions

Dependencies:

- Phase 1 imported/staged holdings
- Collection Intelligence Engine duplicate and upgrade-candidate detection
- Adam-specific priority rules
- A stable way to reference imported legacy rows

## Phase 4: Melt Value Foundation

Scope:

- Import `ASW_REFERENCE`
- Add melt value calculations

Deliverables:

- Parser for `ASW_REFERENCE`
- ASW lookup by country/series, denomination, and year range
- Melt value calculation model
- Support for workbook fields: `Silver?`, `ASW oz`, `Bullion Value CAD`
- Spot price input/update mechanism
- Melt floor display for Buy Advisor and future Auction Evaluator

Complexity: Medium

Risks:

- Year-range matching can be subtle across composition changes
- Spot price source and update cadence must be explicit
- Workbook bullion values may become stale
- Melt value should be a floor, not a full market valuation

Estimated development effort: 2-3 focused development sessions

Dependencies:

- `ASW_REFERENCE` schema
- Phase 1 inventory import or staging fields for silver/ASW data
- A current silver spot price input or log model
- Buy Advisor value-source messaging

## Phase 5: In-App Portfolio Dashboard

Scope:

- Recreate `DASHBOARD` metrics inside the application

Deliverables:

- In-app dashboard view
- Inventory counts by source and category
- Estimated value totals
- Slab/raw counts
- Melt-value summary
- Review-needed counts
- High-priority target counts
- Exportable dashboard summary

Complexity: Medium-High

Risks:

- Workbook dashboard values may rely on formulas or assumptions not visible in imported records
- Dashboard totals can become misleading if staging data and committed holdings are mixed
- Value totals need clear source labels and confidence levels
- Performance may degrade if JSON storage grows substantially

Estimated development effort: 3-5 focused development sessions

Dependencies:

- Phase 1 inventory import
- Phase 2 acquisition intent model
- Phase 3 upgrade model
- Phase 4 melt value model
- Clear value-source conventions

## Recommended Sequence

1. Build safe staging import for `CORE_RAW` and `SLABS`.
2. Add tests around duplicate detection and no-overwrite behavior.
3. Add target/want-list staging and Buy Advisor integration.
4. Add Upgrade Advisor from `UPGRADE_TARGETS`.
5. Add ASW/melt calculations.
6. Rebuild dashboard metrics from app-owned data and staged/imported metadata.

## Non-Negotiable Safety Rules

- Never overwrite `data/collection.json`.
- Always create a timestamped backup before confirmed imports.
- Keep workbook target sheets separate from owned holdings.
- Preserve legacy fields even when they do not yet map to current app fields.
- Make every inferred field visible in an import preview.
