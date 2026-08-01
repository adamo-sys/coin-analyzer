# Sprint 17 Progress

This maintenance update reflects the current repository state for the Sprint 17 field-intelligence workstream. The completed unit list below is taken from the repository history; the remaining unit list reflects the current working tree and the architecture sequence already established in the codebase.

## 1. Completed Units

The following Sprint 17 units are completed in the existing Git history, in chronological order.

| Unit identifier | Short description | Commit hash | Status |
| --- | --- | --- | --- |
| 1A | Field-intelligence assessment contracts for transient rule outcomes over `ConfirmedObservationSet`. | `346f8db` | Complete |
| 1B | Coin-year rule catalog contracts for caller-owned year rules and exact country/denomination scope matching. | `682fff6` | Complete |
| 1C | Coin-specific year evaluator for exact submitted-year membership checks against a caller-supplied catalog. | `2b39f87` | Complete |
| 1D | Denomination-country compatibility contracts for exact rule records across country and denomination. | `8598f5f` | Complete |
| 1E | Denomination-country compatibility evaluator for advisory `VALID`/`INVALID`/`NOT_EVALUATED` outcomes. | `57ce284` | Complete |
| 1F | Shared monarch-year compatibility helper extraction to keep year compatibility logic consistent across field-intelligence features. | `ddfcfe3` | Complete |
| 1G | Monarch-year compatibility evaluator for exact monarch/year compatibility assessment. | `eae4605` | Complete |
| 1H | Mintmark rule catalog contracts for deterministic mintmark rule scope and ordering. | `2a692b3` | Complete |
| 1I | Mintmark compatibility evaluator for exact caller-supplied mintmark evidence evaluation. | `2764942` | Complete |
| 1J | Certification context rule contracts for caller-supplied grading-company context and exact certification scope records. | `eb74314` | Complete |

## 2. Current Architecture

The Sprint 17 architecture is a pure field-intelligence layer that remains advisory and deterministic.

### Current field-intelligence architecture

- The layer reads exact submitted values from `ConfirmedObservationSet`.
- It never mutates the source observation set.
- It never persists findings, catalogs, or evaluator state.
- It never introduces built-in grading-company knowledge, historical numbering knowledge, or default catalogs.
- It emits at most one transient `FieldIntelligenceFinding` per evaluation call.
- It leaves readiness, persistence, OCR, and collection mutation fully outside the evaluator boundary.

### Immutable rule contracts

The immutable rule-contract modules currently present in the repository are:

- `capture_import/workflow_confirmed_observation_field_intelligence.py`
  - `FieldIntelligenceStatus`
  - `FieldIntelligenceFinding`
  - `ConfirmedObservationFieldIntelligenceAssessment`
- `capture_import/workflow_confirmed_observation_coin_year_rules.py`
  - `CoinYearRule`
  - `CoinYearRuleCatalog`
- `capture_import/workflow_confirmed_observation_denomination_country_rules.py`
  - `DenominationCountryRule`
  - `DenominationCountryRuleCatalog`
- `capture_import/workflow_confirmed_observation_mintmark_rules.py`
  - `MintmarkRule`
  - `MintmarkRuleCatalog`
- `capture_import/workflow_confirmed_observation_certification_context_rules.py`
  - `CertificationContextRule`
  - `CertificationContextRuleCatalog`
  - `CertificationEvaluationContext`

### Evaluators

The current evaluator surface is:

- `capture_import/workflow_confirmed_observation_coin_year_evaluator.py`
  - `assess_coin_specific_year`
- `capture_import/workflow_confirmed_observation_denomination_country_evaluator.py`
  - `assess_denomination_country_compatibility`
- `capture_import/workflow_confirmed_observation_monarch_year_evaluator.py`
  - `assess_monarch_year_compatibility`
- `capture_import/workflow_confirmed_observation_mintmark_evaluator.py`
  - `assess_mintmark`
- `capture_import/workflow_confirmed_observation_certification_context_evaluator.py`
  - `assess_certification_context` (current working-tree implementation; not yet part of repository history)

### Interaction with `ConfirmedObservationSet`

- `ConfirmedObservationSet` remains the authoritative evidence boundary.
- Field-intelligence evaluators receive a validated `ConfirmedObservationSet`.
- The evaluators validate the source first using the existing confirmed-observation validation boundary.
- Evaluators read exact submitted values only.
- Canonical values are ignored by the field-intelligence layer.
- `ConfirmedObservationSet` is not rewritten, enriched, or mutated.
- Findings are returned as transient field-intelligence artifacts only.

### Architectural boundaries

The current field-intelligence architecture intentionally keeps these boundaries fixed:

- No persistence
- No readiness integration
- No default catalogs
- No built-in grading-company knowledge
- No built-in historical numbering knowledge
- No normalization, inference, trimming, or rewrite of certification values
- No mutation of `ConfirmedObservationSet`
- Caller-owned rule catalogs only
- Advisory outcomes only; no readiness or collection-authority claims

## 3. Remaining Sprint 17 Units

The remaining planned work is tracked against the current architecture sequence.

| Unit identifier | Planned unit | Status |
| --- | --- | --- |
| 1F-B | Certification context evaluator implementation (`assess_certification_context`) | In Progress |
| Follow-on certification-context integration | End-to-end field-intelligence assessment wiring for certification-context evaluation | Not Started |
| Follow-on Sprint 17 closure documentation | Final documentation alignment and architecture closure | Deferred |

## 4. Deferred Architecture Decisions

The following design questions remain intentionally unresolved or explicitly deferred pending the next controlled implementation unit.

- Certification context evaluator design
  - Whether the evaluator should treat `grading_company` strictly as caller-supplied evaluation context, or whether future evidence-level observation of grading-company text should override or conflict with the caller context.
- Evaluation-context handling
  - Whether conflicting observed certification evidence and explicit caller-supplied evaluation context should remain advisory-only with a deterministic conflict diagnostic, or whether later layers need a more specific policy object.
- Rule-catalog ownership
  - The catalog remains caller-owned and deterministic; no default or built-in registration mechanism is defined.
- Historical numbering knowledge
  - The architecture explicitly excludes any built-in historical numbering or issuer-format knowledge from the field-intelligence layer.

## 5. Repository Status

### Current authoritative regression baseline

- Command: `python -m unittest discover -s . -p "test_*.py"`
- Result: `Ran 4241 tests in 128.602s`
- Status: `OK (skipped=22)`

### Current test count

- Current authoritative regression count: 4241 tests
- Current skipped count: 22

### Current architecture baseline

- Current architecture baseline: a pure, immutable, caller-owned field-intelligence layer over `ConfirmedObservationSet`.
- Rule catalogs remain deterministic and caller-supplied.
- Evaluators remain advisory and non-authoritative.
- No persistence, readiness, or default-catalog behavior is wired into the layer.

### Known technical debt

None.

## Next

The next planned unit is the certification-context evaluator completion and closure of the current working-tree implementation into the repository’s normal Sprint 17 sequence.
