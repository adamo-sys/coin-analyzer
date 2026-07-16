# ADR-001: Local-first architecture

- Status: Accepted
- Date: 2026-07-16

## Context

Coin Analyzer manages personal collection records, photographs, research, and reports. Core workflows must remain useful without accounts, network access, or third-party service availability. Personal records may include sensitive ownership details and local file paths.

## Decision

Core collection management, persistence, analysis, and reporting are local-first and user-triggered. The desktop application remains authoritative for local collection state. External services may enrich optional workflows, but core functionality must degrade safely when they are unavailable.

Personal runtime data is not committed to the repository. Export, backup, synchronization, and external-provider operations require deliberate user action and preserve source attribution where applicable.

## Consequences

- Collectors retain control of their data and can use core workflows offline.
- Tests can remain deterministic and independent from external services.
- Users are responsible for independently backing up local runtime data.
- Cross-device collaboration and live external data require explicit adapters and conflict policies rather than becoming hidden core dependencies.

## Reconsider When

Reconsider specific boundaries only when a user-validated workflow requires networked behavior and has an approved privacy, failure, ownership, and migration design. Local core operation remains the default.
