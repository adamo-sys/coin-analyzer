# ADR-002: JSON over SQLite for collection persistence

- Status: Accepted for the current collection scale
- Date: 2026-07-16

## Context

The collection manager persists a single user-owned collection with optional fields and backward-compatible records. The current application benefits from transparent files, simple backups, direct export, and low operational complexity. It does not currently require concurrent writers or relational queries for core CRUD operations.

## Decision

Continue using local JSON for the primary collection rather than introducing SQLite. `CoinCollection` tolerates a missing file, loads legacy records with absent optional fields, and writes complete documents atomically. The live `data/collection.json` file is local runtime data and is excluded from Git.

Tests use temporary JSON files and sanitized fixtures, never the live collection.

## Consequences

- Persistence remains inspectable, portable, and easy to back up.
- Existing collections require no database migration.
- Atomic whole-file replacement protects against partial writes but does not provide database transactions or concurrent-write coordination.
- Query and write performance may become limiting as collections or relationships grow substantially.

## Reconsider When

Evaluate SQLite or another provider when measured collection size, query complexity, concurrency, integrity constraints, or migration needs exceed the JSON model. Any replacement requires a reversible migration plan, backup safeguards, and backward-compatibility tests.
