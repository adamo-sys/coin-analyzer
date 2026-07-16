# ADR-003: Decimal representation for acquisition money

- Status: Accepted
- Date: 2026-07-16

## Context

Acquisition tracking adds purchase price, shipping, buyer's premium, and tax. Binary floating-point arithmetic can introduce representation errors in entered monetary values, and forced two-decimal rounding would discard valid precision.

The repository also contains older estimate-oriented fields that predate this decision.

## Decision

Acquisition monetary components use Python `Decimal`. Inputs must be finite, non-negative decimal values; booleans, malformed text, `NaN`, and infinity are rejected. Entered precision is preserved rather than quantized to two decimal places.

Persist acquisition money as deterministic non-exponent JSON strings. Blank optional fields remain `None`, distinct from an explicitly entered zero.

This decision governs acquisition money and new exact-money work. It does not silently migrate legacy float-based estimate fields.

## Consequences

- Component arithmetic avoids binary floating-point errors.
- Persistence and CSV reporting are deterministic and preserve precision.
- Boundaries must normalize strings, numbers, and `Decimal` values consistently.
- Code must not mix acquisition `Decimal` values with floats without an explicit conversion policy.

## Reconsider When

Reconsider serialization only as part of a versioned, backward-compatible money model. Currency conversion, exchange rates, and forced display precision require separate decisions.
