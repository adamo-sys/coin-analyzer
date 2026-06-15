# WANT_LIST Integration Plan

## Scope

Plan v0.4 Phase 2 support for workbook `WANT_LIST` rows only. Do not treat want-list rows as owned collection items, and do not write to `data/collection.json`.

## Proposed Approach

1. Extend `legacy_portfolio_importer.py` with a read-only parser for the `WANT_LIST` sheet.
2. Stage each row as acquisition intent with fields for target coin, priority, target grade, budget, why wanted, and status.
3. Validate headers and tolerate an empty `WANT_LIST` sheet without error.
4. Add preview summary counts for want-list rows found, staged, skipped, and warnings.
5. Keep staged want-list records separate from `CoinItem` holdings.
6. Feed staged intent into the Want List Generator as priority boosts, not replacements for engine-generated targets.
7. Expose clear Buy Advisor context when a candidate matches a staged want-list target.

## Data Mapping

| Workbook column | Planned app usage |
| --- | --- |
| `Target Coin` | Display label and matching input for acquisition intent |
| `Priority` | Ranking boost for Want List Generator and Buy Advisor |
| `Target Grade` | Desired grade context |
| `Budget` | Maximum target spend context |
| `Why Wanted` | Human-readable recommendation reason |
| `Status` | Workflow state such as active, acquired, deferred, or ignored |

## Testing Plan

- Add isolated workbook fixtures with populated and empty `WANT_LIST` sheets.
- Verify parsing does not modify collection JSON.
- Verify invalid or incomplete rows are skipped with warnings.
- Verify staged want-list records remain distinct from owned inventory.
- Verify Want List Generator priority boosts are explainable and deterministic.

## Open Decisions

- Define accepted `Status` values before implementation.
- Decide whether `TARGETS` should share the same staged-intent model or remain separate until its own implementation step.
- Decide how strict matching should be between `Target Coin` text and collection/Buy Advisor fields.
