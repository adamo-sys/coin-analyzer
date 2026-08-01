# Sprint 17 Status

## Overall Progress

| Unit | Description | Status | Commit |
| --- | --- | --- | --- |
| 1A – Foundation | Field-intelligence assessment contracts for transient rule outcomes over `ConfirmedObservationSet`. | Complete | `346f8db` |
| 1B-A – Coin-Year Rules | Coin-year rule catalog contracts for caller-owned year rules and exact country/denomination scope matching. | Complete | `682fff6` |
| 1B-B – Coin-Year Evaluator | Coin-specific year evaluator for exact submitted-year membership checks. | Complete | `2b39f87` |
| 1C-A – Denomination-Country Rules | Denomination-country compatibility contracts for exact country and denomination records. | Complete | `8598f5f` |
| 1C-B – Denomination-Country Evaluator | Advisory denomination-country compatibility evaluator. | Complete | `57ce284` |
| 1D-A – Shared Monarch-Year Helper | Shared monarch-year compatibility helper extraction to centralize year-compatibility logic. | Complete | `ddfcfe3` |
| 1D-B – Monarch-Year Evaluator | Monarch-year compatibility evaluator for exact monarch/year compatibility assessment. | Complete | `eae4605` |
| 1E-A – Mintmark Rules | Mintmark rule catalog contracts for deterministic mintmark rule scope and ordering. | Complete | `2a692b3` |
| 1E-B – Mintmark Evaluator | Mintmark compatibility evaluator for exact caller-supplied mintmark evidence evaluation. | Complete | `2764942` |
| 1F-A – Certification Context Contracts | Certification-context rule contracts for caller-supplied grading-company context and exact certification scope records. | Complete | `eb74314` |
| 1F-B – Certification Context Evaluator | Certification-context evaluator for exact caller-supplied grading-company and certification evidence. | Complete | `c7148eb`, refined by `7740f8e` |

## Progress Snapshot

Completed

- ✓ Coin-year contracts
- ✓ Coin-year evaluator
- ✓ Denomination-country contracts
- ✓ Denomination-country evaluator
- ✓ Monarch-year shared helper refactor
- ✓ Monarch-year evaluator
- ✓ Mintmark contracts
- ✓ Mintmark evaluator
- ✓ Certification-context contracts
- ✓ Certification-context evaluator

Sprint 17 closes only this contract and five-leaf-evaluator scope. It does not
close aggregate orchestration or production integration.

Quality gates

- ✓ Full regression passing
- ✓ Architecture review completed for each bounded unit
- ✓ Committed
- ✓ Pushed to GitHub

## Architecture Decisions

Sprint 17 continues the field-intelligence architecture with the following decisions now reflected in the repository history:

- Single source of truth for monarch/year compatibility is the shared helper extracted in `ddfcfe3`, keeping monarch-year logic consistent across the evaluator surface.
- Field-intelligence evaluators are pure and deterministic: they consume validated `ConfirmedObservationSet` evidence, return transient advisory findings, and do not rewrite source observations.
- Rule catalogs are immutable and caller-supplied, so the evaluation layer remains deterministic and does not register or synthesize built-in catalogs.
- No persistence is performed by the field-intelligence layer; findings remain transient and advisory.
- No default catalogs are introduced; callers own the rule catalog boundaries.
- No built-in grading-company knowledge is embedded in the evaluation layer.
- No readiness integration is wired into the field-intelligence boundary unless explicitly approved by the owning architecture decision.
- `ConfirmedObservationFieldIntelligenceAssessment` is the immutable aggregate result contract, but no aggregate orchestration function or public aggregate evaluator currently constructs it from the five leaf evaluators.
- None of the leaf evaluators is wired into an aggregate production flow.

## Deferred Aggregate Orchestration

Aggregate orchestration and production integration are deferred, not
complete. A future orchestration unit requires separate architecture design
and explicit approval covering:

1. ownership and module boundary;
2. the public callable and its signature;
3. catalog and context inputs;
4. deterministic evaluator ordering;
5. handling of `None` findings;
6. `ConfirmedObservationFieldIntelligenceAssessment` construction and validation;
7. backward compatibility; and
8. preservation of transient, advisory-only behaviour.

## Regression Status

Latest authoritative regression currently reflected in the repository:

- Command: `python -m unittest discover -s . -p "test_*.py"`
- Total tests run: `4,241`
- Failures: `0`
- Errors: `0`
- Skipped: `22`
- Overall: `PASS`

## Notes

- All completed units are committed in the repository history.
- The repository is pushed to GitHub on `origin/main`.
- This closure records only the completed contract and leaf-evaluator scope; aggregate orchestration and production wiring remain deferred.
