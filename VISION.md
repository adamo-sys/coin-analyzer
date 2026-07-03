# Coin Analyzer Vision

## Purpose

Coin Analyzer is becoming a comprehensive collection intelligence platform for coin and banknote collectors. Its job is not only to store records or give isolated advice, but to help the collector move through the real work of collecting: deciding what to buy, reviewing what was bought, improving the collection, finding risks, preserving evidence, and learning from past decisions.

The long-term direction is a local-first collection assistant that turns collection data, photos, market observations, want lists, prior recommendations, and review history into deterministic, explainable guidance.

## Two-to-Three-Year Direction

Coin Analyzer should evolve from a feature-rich desktop application into a coherent collector operating system:

1. Unified workflows replace scattered tool entry points.
2. The portfolio dashboard becomes the daily home screen.
3. Every recommendation explains why it exists, what evidence supports it, and what uncertainty remains.
4. Batch photo and OCR workflows reduce repetitive cataloguing work while preserving manual review.
5. Collection health checks identify duplicates, weak examples, missing key dates, imbalance, and risk.
6. Recommendation memory lets the software compare current opportunities with past passes, purchases, sellers, and prices.
7. Long-term platform work remains local-first, deterministic, auditable, and collector-controlled.

## Guiding Principles

### Local First

The collection file, app state, photos, market notes, and workflow history remain local unless a future release explicitly designs and reviews sync behavior. No hidden cloud dependency should be required for core collecting work.

### Deterministic Before Clever

The application should favor reproducible rules, stable scoring, transparent data transformations, and tests over black-box behavior. If the same inputs are provided twice, the same recommendation and evidence should result.

### Explain Every Decision

Advice without evidence is not enough. Recommendations should answer:

- What is being recommended?
- Why does it matter?
- Which data supports it?
- What risks or missing evidence remain?
- What should the collector do next?

### Assistant, Not Autopilot

Coin Analyzer may organize, prioritize, explain, and prepare review steps. It must not automatically buy, bid, sell, grade, submit, delete, mutate collection records, or resolve conflicts without explicit collector action.

### Reuse Before Building

New features should first ask which existing engines already know the answer. Thin orchestration, workspace aggregation, and workflow coordination are preferred over duplicating business logic.

### Evidence Has Ownership

Each subsystem owns the facts it produces. Workflow and dashboard layers may cite, summarize, and route those facts, but should not silently fork logic into another module.

### Feature Growth Needs Shape

New capabilities should fit one of these durable platform goals:

- Better acquisition decisions
- Faster collection processing
- Stronger collection health
- Better portfolio understanding
- Better evidence and explainability
- Safer persistence, backup, and review
- Better continuity across sessions and devices

## Product North Star

The collector opens Coin Analyzer and sees a calm, actionable picture of the collection:

- What needs attention today
- What recent acquisitions need processing
- Which opportunities are worth acting on
- Which duplicates, upgrades, and gaps matter most
- How the portfolio is changing
- Why each recommendation is being made
- What decisions were made before and what changed since

The software should feel like an organized assistant at the table with the collector: structured, skeptical, evidence-driven, and never pushy.

## Relationship to ROADMAP.md

`VISION.md` is stable direction. It describes what Coin Analyzer is trying to become.

`ROADMAP.md` is the tactical backlog. It captures concrete versions, ideas, experiments, known bugs, and release planning.

When planning a release, use this file to decide whether the work strengthens the platform or merely adds another disconnected feature.
