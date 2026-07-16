# ADR-004: Derive acquisition totals from components

- Status: Accepted
- Date: 2026-07-16

## Context

An acquisition total is the sum of purchase price, shipping cost, buyer's premium, and tax. Persisting an independently editable total would allow it to disagree with its components. Reporting must also distinguish “no acquisition cost recorded” from an explicitly recorded zero-dollar acquisition.

## Decision

`total_cost` is a read-only derived value:

```text
purchase_price + shipping_cost + buyers_premium + tax
```

Missing components count as zero only when at least one component is present. When all four components are absent, `total_cost` is `None`. An explicitly entered zero therefore produces `Decimal("0")`.

The total is not persisted and is never accepted as authoritative during import. CSV export may include it as a calculated reporting column; CSV import ignores any supplied total and recalculates from components.

## Consequences

- Totals cannot become stale or conflict with component values.
- Legacy records with no acquisition components remain distinguishable in reporting.
- All consumers must calculate through the model rather than reading stored total data.
- Changing a component immediately changes the displayed and exported total.

## Reconsider When

If a future domain requires an authoritative invoiced total that differs from the component sum, model that as a separately named concept with explicit reconciliation rules rather than changing `total_cost` semantics.
