# ADR-005: Portfolio financial comparability

- Status: Accepted
- Date: 2026-07-16

## Context

Portfolio Analytics combines exact acquisition components with an older valuation
field. `CoinItem.total_cost` is a derived `Decimal` with an explicit or missing
purchase currency, while `estimate_cad` is a legacy float-backed approximate CAD
estimate whose `0.0` default cannot distinguish missing data from explicit zero.
Market Awareness also has separate purchase records for local market activity.

Summing unlike currencies, assuming a missing currency is CAD, multiplying a
record-level transaction cost by quantity, or presenting every record as
financially comparable would produce misleading totals.

## Decision

- `CoinItem.total_cost` is the complete acquisition cost associated with that
  collection record or lot. Analytics do not multiply it by `quantity`.
- `None` means no acquisition cost was recorded. Explicit zero remains recorded
  acquisition data.
- Costs are grouped by normalized `purchase_currency`. Missing currency is
  reported as `Unspecified`, never inferred as CAD.
- Analytics do not combine currencies or perform exchange-rate conversion.
- `estimate_cad` remains an approximate legacy value. Analytics convert it with
  `Decimal(str(value))` at the reporting boundary and accept only finite values
  greater than zero as usable valuation evidence.
- A record enters the comparable CAD subset only when it has a recorded
  `total_cost`, `purchase_currency == "CAD"`, and a usable positive
  `estimate_cad`.
- Comparable estimated value is `estimate_cad * quantity`; comparable acquisition
  cost is the record-level `total_cost`. Estimated ROI is reported only when the
  aggregate comparable cost is greater than zero.
- Exclusion counts and coverage accompany gain/loss and ROI so the comparable
  subset is visible.
- Market Awareness `PurchaseRecord` data remains a separate activity record and
  is not merged with item-owned acquisition fields.

## Consequences

- Portfolio totals remain exact for recorded acquisition costs and honest about
  currency and valuation gaps.
- Multi-currency collections have separate totals rather than a false combined
  value.
- Gain/loss and ROI describe only an explicitly eligible CAD subset, not the whole
  collection.
- A record with quantity greater than one treats acquisition cost as a lot total
  and its approximate estimate as a per-unit value.
- No collection migration, portfolio persistence, currency registry, or exchange
  rate is introduced.

## Reconsider When

Reconsider these boundaries only after the product has explicit per-unit versus
lot pricing, a valuation model that distinguishes missing from zero, or an
approved exchange-rate policy with sources, effective dates, and failure rules.
Realized gains, sales, tax accounting, and historical financial snapshots require
separate decisions.
