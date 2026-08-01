# Sprint 17 Progress

This closure update records the completed contract and leaf-evaluator scope of the Sprint 17 field-intelligence workstream. Aggregate orchestration and production integration are outside this closure and remain explicitly deferred.

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
| 1K | Certification-context evaluator for exact caller-supplied grading-company and certification evidence evaluation. | `c7148eb`, refined by `7740f8e` | Complete |

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
  - `assess_certification_context`

All five leaf evaluators are complete and present in repository history. Each
returns at most one transient `FieldIntelligenceFinding`, or `None` when its
relevant fields are wholly absent. No public aggregate evaluator currently
exists to invoke or combine these leaf results into
`ConfirmedObservationFieldIntelligenceAssessment`.

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

## 3. Sprint 17 Closure Scope

Sprint 17 closes only the field-intelligence contract and leaf-evaluator
scope. The completed scope consists of the immutable assessment and finding
contracts, the caller-owned rule-catalog contracts, the shared monarch-year
compatibility helper, and the five independent leaf evaluators listed above.

Aggregate orchestration is not part of the completed scope. No aggregate
orchestration function or public aggregate evaluator currently exists, and
none of the five leaf evaluators is wired into an aggregate production flow.
Production integration is therefore deferred, not complete.

## 4. Deferred Aggregate Orchestration

Aggregate orchestration requires a separately designed architectural unit and
explicit approval before implementation. That design and approval must cover:

1. ownership and module boundary;
2. the public callable and its signature;
3. catalog and context inputs;
4. deterministic evaluator ordering;
5. handling of `None` findings;
6. `ConfirmedObservationFieldIntelligenceAssessment` construction and validation;
7. backward compatibility; and
8. preservation of transient, advisory-only behaviour.

Until that unit is designed and approved, the leaf evaluators remain
independent, caller-invoked functions. No documentation in this closure should
be read as claiming aggregate evaluation, production wiring, persistence,
readiness authority, or collection-mutation authority.

## 5. Repository Status

### Current authoritative regression baseline

- Command: `python -m unittest discover -s . -p "test_*.py"`
- Result: `Ran 4241 tests in 128.602s`
- Status: `OK (skipped=22)`; zero failures and zero errors

### Current test count

- Tests run: 4,241
- Skipped: 22
- Failures: 0
- Errors: 0

### Current architecture baseline

- Current architecture baseline: a pure, immutable, caller-owned field-intelligence layer over `ConfirmedObservationSet`.
- Rule catalogs remain deterministic and caller-supplied.
- Evaluators remain advisory and non-authoritative.
- No persistence, readiness, or default-catalog behavior is wired into the layer.
- No aggregate orchestration or production integration is wired into the layer.

## Closure Decision

**PASS for the bounded contract and leaf-evaluator scope.**

Sprint 17 is closed only for its contracts and five leaf evaluators. Aggregate
orchestration and production integration remain deferred pending the separate
architecture design and approval described above.
