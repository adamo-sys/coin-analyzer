# Coin Analyzer Product Principles

This document is the product compass for Coin Analyzer. It should be short, stable, and rarely changed.

## Mission

Maximize time spent collecting and minimize time spent managing a collection.

## Guiding Principle

Not more capability, but less drag.

Every release should make collecting feel smoother.

## Collector Journey Audit

Observe. Do not fix.

During a Collector Journey Audit, gather evidence from real collecting use.

Do not fix.

Do not record implementation ideas during the session.

Only record observations.

## 30-Second Rule

If I pause for more than 30 seconds, write it down.

The pause is evidence that the software failed to stay out of the collector's way.

## Friction Categories

Every friction point belongs to exactly one category:

| Category | Meaning |
| --- | --- |
| Discovery | I could not find it. |
| Decision | I was not sure what to do. |
| Repetition | I had to do something twice. |

These categories describe the collector's experience. They do not dictate implementation.

## Roadmap Rule

If a friction point cannot be reproduced during a real collecting session, it does not become a roadmap item.

## Release Rule

Every significant workflow improvement must remove at least one user action.

Do not add capability unless it reduces collector friction.

Do not ask:

> What feature are we adding?

Ask:

> What step disappears?

## Explainability

Every recommendation answers:

- Why?
- Why now?
- What next?

## Human Control

Coin Analyzer advises.

The collector decides.

## v8.7 Guardrails

Collector Experience work is out of scope when it requires:

- new intelligence engines
- new recommendation categories
- cloud sync
- live pricing
- ML/CV enhancements
- major architectural changes
- a new workflow engine

## Phase 1 Rule

Do not recommend Phase 1 before the Collector Journey Audit.

After the audit:

1. Analyze the raw friction log.
2. Group observations by theme.
3. Identify the dominant friction pattern.
4. Select one primary success metric.
5. Lock the v8.7 roadmap.
6. Recommend a single Phase 1 candidate based entirely on evidence.

## North Star

A collector can buy a coin, process it from start to finish, and never once think about the software.

Software is successful when it disappears.

The collector should remember the coin, not the clicks.
