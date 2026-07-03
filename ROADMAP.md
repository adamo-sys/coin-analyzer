# Collector Companion Roadmap

A living document for ideas, experiments, bugs, UX improvements, and future releases. Not a commitment — a capture system.

---

## 🐞 Known Bugs

| # | Issue | Impact | Notes |
|---|-------|--------|-------|
| 1 | Direct multi-module `py -m unittest ...` commands can be flaky in this environment due to the Windows Python launcher | Low | Use `run_tests.bat` as the reliable suite command |
| 2 | GUI autocomplete currently prints suggestions to the console instead of showing a dropdown | Medium | Tkinter limitation; may require custom dropdown widget |
| 3 | Experimental detection and template matching are incomplete | Low | Should remain manual-verification-only |
| 4 | Numista API integration is not implemented and is blocked by API key, terms, pricing, and access review | Medium | External dependency; no timeline |
| 5 | JSON storage is simple and may not scale well for large collections | Low | Future: evaluate SQLite |
| 6 | Many collection rows have no `Estimate (CAD)`, limiting Buy Advisor max-bid accuracy | Low | Data quality issue, not code |
| 7 | No automated GUI tests currently cover Tkinter workflows | Medium | All GUI validation is manual smoke |

---

## 💡 Ideas

| # | Idea | Category | Notes |
|---|------|----------|-------|
| 1 | SQLite storage provider for larger collections | Architecture | Replace JSON with SQLite for collections > 10,000 items |
| 2 | Compact dealer-table candidate workflow | Mobile | Minimal entry for phone use at coin shows |
| 3 | Undo/redo system | UX | Transactional collection mutations |
| 4 | Batch editing (multi-select, bulk update) | UX | Select N items, edit one field across all |
| 5 | Image preview in collection list | UX | Thumbnail view alongside table |
| 6 | Autocomplete for country/denomination | UX | Reduce typing, reduce data entry errors |
| 7 | Expand normalization fixtures for country, denomination, variety edge cases | Data Quality | More robust fuzzy matching |
| 8 | Auction Evaluator implementation | Feature | From `AUCTION_EVALUATOR_SPEC.md` |
| 9 | Acquisition workflow guidance visible in Buy Advisor reports | Integration | Surface workflow reasoning directly |
| 10 | Storage-provider, file-picker, export-destination, and photo URI adapters | Architecture | Abstraction before mobile implementation |

---

## 🔬 Experiments

| # | Experiment | Status | Hypothesis |
|---|------------|--------|------------|
| 1 | OCR-assisted identification from phone photos | Partial | OCR text + deterministic suggestion = faster candidate entry |
| 2 | Batch photo processing workflow | Complete (v8.1) | Folder of photos → batch OCR → batch identification → batch review |
| 3 | AI Grading Assistant confidence scoring | Complete (v8.2) | Collection grade patterns + evidence = explainable guidance |
| 4 | Connected Data cross-referencing | Complete (v8.4) | Information entered once → reused everywhere |
| 5 | Collector Intelligence recommendation layer | Complete (v8.5) | Existing reports → deterministic "what should I do next?" |

---

## ✨ UX Improvements

| # | Improvement | Priority | Effort | Notes |
|---|-------------|----------|--------|-------|
| 1 | Improve Buy Advisor validation messages | Low | Small | |
| 2 | Add autocomplete for country/denomination | Medium | Medium | |
| 3 | Add image preview in collection list | Medium | Medium | |
| 4 | Add batch editing | Medium | Medium | |
| 5 | Add undo/redo | Medium | Large | |
| 6 | Better error messages when engines fail | Low | Small | |
| 7 | Keyboard shortcuts for common actions | Low | Small | |
| 8 | Dark mode support | Low | Large | |
| 9 | Collection list filtering (by country, year, denomination) | Medium | Medium | |
| 10 | Export directly to email/share | Low | Medium | |
| 11 | `RecommendationPriority` enum for presentation clarity | Low | Small | Typed enum lets GUI sort naturally without inventing weights.

---

## 🚀 Future Releases

### v8.5 — Collector Advisor *(Complete)*

A deterministic recommendation layer. No ML. No LLM. No black box. Just explainable recommendations built on everything already built.

**Mission:** Collector Advisor helps the collector decide what to do next using deterministic, explainable recommendations built entirely from existing engines.

**Module:** `collector_advisor.py` → `CollectorAdvisor`

**Naming rationale:** "Advisor" signals recommendations rather than analysis. Distinct from `CollectionIntelligenceEngine` (analysis) and `ConnectedDataEngine` (cross-referencing).

**Stable recommendation categories (frozen):**
- `BUY_NOW`
- `BUY_IF_PRICE_RIGHT`
- `WATCH`
- `NEGOTIATE`
- `PASS`
- `REVIEW`

> No new categories without explicit justification and a breaking-change review. Future work improves evidence quality, prioritization, confidence, and explanation — not recommendation quantity.

**Architectural rules:**
1. Reuse first. Compute second. The Advisor orchestrates existing intelligence rather than reimplementing it.
2. Every recommendation must be explainable. Every recommendation DTO includes `evidence: List[RecommendationReason]` with human-readable, source-labeled reasons.
3. Public APIs are stable after Phase 1 unless a later phase explicitly documents and justifies a breaking change.
4. The six `AdvisorCategory` enum values are treated as stable public API. New categories require explicit justification.

**Completed release scope:** Collector Advisor core engine, workspace integration, GUI Advisor tab, frozen categories, deterministic ordering, upstream signal-quality fixes, dependency management, CI workflow, and release metadata. Final regression: 1261 tests passing.

**Next step:** Complete v8.5 tag and remote verification before any v8.6 planning.

**Status:** Complete. Key commits: `9e65158` (Phase 0), `894785b` (Phase 1), `c101015` (Phase 2), `a7bfb46` (Phase 3), `7c34837` (Phase 4), `22cfbe0` (Phase 5), `b5ba9ec` (CI fixes).

---

### v9.0 — Collector Ecosystem *(Long-term)*

Vision: A fully integrated collector ecosystem where the app not only organizes and recommends, but also helps execute — from discovery to acquisition to cataloguing to portfolio management — all deterministic, all explainable, all local.

---

## 🏛️ Permanent Architectural Rules

1. **CollectorWorkspace remains a ViewModel only.** Connection methods cross-reference existing panel outputs; they do not compute new business logic.
2. **No new intelligence engine unless explicitly justified.** All analysis, scoring, and recommendations remain in existing engines or thin facades.
3. **No new persistence layer.** Connected data holds references, not copies. Source engines remain the owners.
4. **No duplicated business logic.** If an engine already computes it, the connection layer references it.
5. **Keyword-only context propagation.** All new context parameters are keyword-only, preserving existing API signatures.
6. **Lazy connection.** Cross-references are computed on demand, not eagerly.
7. **Graceful degradation.** If related data is missing, the tool works normally without it.
8. **Public API stability after Phase 1.** Public APIs are stable after Phase 1 unless a later phase explicitly documents and justifies a breaking change. This prevents later phases from subtly reshaping DTOs or method signatures without deliberate review.
9. **Deterministic recommendation ordering.** Given identical inputs and configuration, the CollectorAdvisor must always produce identical recommendation ordering and evidence. This protects against subtle regressions and makes testing deterministic.
10. **Recommendation category freeze.** The six `RecommendationCategory` enum values are treated as stable public API after Phase 3. New categories require explicit justification and a breaking-change review. Future work improves evidence quality, prioritization, and confidence rather than multiplying recommendation types.

---

## How to Use This Document

1. **When inspiration strikes:** Add an idea to the appropriate section.
2. **When a bug is found:** Add it to Known Bugs. If it blocks a release, escalate immediately.
3. **When a release is planned:** Move the relevant idea to an implementation plan (e.g., `v8.5_implementation_plan.md`).
4. **When an experiment completes:** Update its status. If successful, promote to a feature. If not, archive with notes.
5. **When an item is implemented:** Remove it from this file and reference it in release notes.

This document is not a commitment. It is a capture system. Repository contents remain the sole source of truth for active work.
