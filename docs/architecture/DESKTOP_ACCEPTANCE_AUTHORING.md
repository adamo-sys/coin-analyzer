# Desktop Acceptance Pre-Freeze Authoring

The desktop acceptance authoring workflow exists to assemble and review a candidate real-world corpus before the strict frozen v1 manifest is created.

It is deliberately separate from the frozen desktop acceptance contract. An authoring plan may contain unresolved state; a frozen manifest may not. The strict frozen loader is not relaxed to accept authoring objects.

## Workflow boundary

The intended sequence is:

1. Author candidate cases/specimens and cohort intent.
2. Complete independent ground-truth and expected-action reviews, including adjudication when reviewers disagree.
3. Establish provenance, privacy approval, licensing approval, and provider authorization.
4. Capture the planned obverse/reverse photographs and complete capture-condition metadata.
5. Complete near-duplicate review.
6. Run the authoring readiness validator.
7. If and only if readiness has no blockers, generate the deterministic freeze-preparation handoff.
8. Freeze the exact image bytes, compute SHA-256 digests and the frozen ledgers/digests, then construct and validate the existing strict v1 manifest.
9. Only after a valid frozen manifest exists may benchmark execution be considered separately.

`ready_for_freeze` therefore means **ready to begin the byte-freeze/frozen-manifest construction step**. It does not mean recognition is authorized, it does not mean the benchmark has been executed, and it does not approve threshold tuning or production changes.

## Fail-closed authoring state

The authoring plan uses explicit unresolved states for privacy, licensing, provider authorization, reviews, capture, and near-duplicate work. Required unresolved or non-approved state is a readiness blocker. The workflow never converts unknown authorization into approval and never fabricates provenance, reviewer evidence, reviewer decisions, image hashes, or frozen digests.

The validator also checks progress toward the fixed v1 corpus constraints: 30 cases, 24 identify and 6 abstain, at least 24 specimens, no more than two cases per specimen, 10 stability cases using distinct specimens, both actions in the stability subset, declared stability-cohort coverage, and materially different capture conditions when a specimen is used twice.

Complete known identity remains required for abstain cases. Ground-truth and expected-action review are separate authoring processes, and disagreement requires a distinct adjudicator plus evidence and rationale.

## Freeze preparation

`capture_import.desktop_acceptance_authoring.prepare_for_freeze` emits an intermediate handoff only when the authoring plan is ready. The handoff carries resolved review results and operational metadata but intentionally omits frozen image and manifest digests.

The handoff explicitly lists the remaining byte-freeze steps. The strict frozen loader remains the authority for the final frozen contract.

## CLI

A narrow readiness CLI is available through the module:

```text
python -m capture_import.desktop_acceptance_authoring path/to/authoring.json
python -m capture_import.desktop_acceptance_authoring path/to/authoring.json --json
```

The human-readable form exits 0 when ready and 2 when blockers remain. `--json` emits deterministic JSON suitable for tooling.

## Before real photography

Do not treat an authoring worksheet as an invitation to start recognition. First finalize the candidate specimen roster, intended case composition, cohort coverage, reviewer assignments, provenance/authorization evidence, and stability-subset intent. Photography should then be performed deliberately under the planned capture conditions. Recognition should not be run on candidate benchmark captures before the exact accepted bytes have been frozen and validated under the strict manifest contract.
