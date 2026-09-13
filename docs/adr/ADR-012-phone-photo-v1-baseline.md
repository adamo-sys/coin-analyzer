# ADR-012: Phone-photo v1 baseline decision

- Status: Proposed (decision only; Phase 2 not implemented or authorized by this ADR)
- Date: 2026-09-13

## Context

The merged [public results](../../benchmarks/phone-photo-v1/RESULTS.md)
(aggregate baseline and cohort tables) establish a frozen, descriptive baseline.
The [protocol](../../benchmarks/phone-photo-v1/README.md) and
[scorer](../../capture_import/phone_photo_benchmark.py) define its interpretation.
Only sanitized public evidence informs this decision; root causes are not exposed
by the aggregate tables. This small benchmark is not a general recognition gate.

### Baseline

| Execution outcome | Specimens |
|---|---:|
| Attempted | 10 |
| Validated predictions | 8 |
| Validated whole-specimen abstentions | 0 |
| Validation rejections | 2 |
| Provider/runtime failures | 0 |
| Not attempted | 0 |

Execution and baseline completeness are true; postflight source integrity was
verified. Rejections are excluded from ordinary scoring, not counted as incorrect
predictions or abstentions.

| Field | Correct | Incorrect | Abstained | Accuracy |
|---|---:|---:|---:|---:|
| Jurisdiction | 5 | 3 | 0 | 5/8 (62.5%) |
| Denomination | 5 | 2 | 1 | 5/8 (62.5%) |
| Year | 4 | 2 | 2 | 4/8 (50.0%) |
| Type/design | 0 | 0 | 0 | Unavailable: no scored denominator |

Exact identity across verified fields is **2/8 (25%)**; overall field abstention
is **3/24 (12.5%)**. These are strict NFKC-normalized, trimmed, case-folded text
matches, not semantic adjudication. Type/design ground truth is unscorable;
exact identity does not establish complete numismatic identification.

### Failure taxonomy

- **Jurisdiction mismatch:** three incorrect fields overall. The
  historical-jurisdiction cohort has jurisdiction correct on 0/3 scored specimens
  and one rejection among four attempts. Thus all scored jurisdiction errors
  fall in this cohort; neither a naming mismatch nor a visual misidentification
  is established as the cause.
- **Other field mismatch:** denomination and year each have two incorrect fields.
  Public evidence does not distinguish reading errors from representation errors.
- **Partial prediction abstention:** denomination abstains once and year twice.
  This is unavailable field output, not evidence of a calibrated low-confidence score.
- **Validation rejection:** two attempted outcomes fail the existing validator.
  Reasons are not public; no particular validator defect is established.

These are outcome classes, not disjoint specimen groups. Crop, rotation, glare,
blur, perspective, background, side confusion, and import/preprocessing failures
cannot be attributed from the published evidence.

## Decision

Preserve this baseline and its scoring rules. Prioritize jurisdiction mismatch
and select only the prompt clarification hypothesis below for the next experiment.

### Prioritization

Ranking is engineering judgment, not measured prevalence in real phone-photo use.
Risk estimates concern a possible intervention; they are not benchmark results.

| Rank / class | Impact and frequency evidence | Implementation / regression risk | Measurement |
|---|---|---|---|
| First: jurisdiction mismatch | Wrong issuing identity undermines identification; three errors concentrated in the historical cohort | A narrow prompt edit is simple; historical interpretation may regress other identities | Frozen jurisdiction field and historical cohort scores |
| Second: other field mismatch | Denomination and year affect identification; two errors each | Cause unknown; broad recognition changes risk unrelated fields | Existing field and exact-identity scores |
| Third: validation rejection | Removes usable output; two attempts rejected | Reason-specific intervention cannot be chosen publicly; relaxing validation risks accepting malformed output | Separate rejection count, never accuracy reclassification |
| Fourth: partial abstention | Leaves identity incomplete; three field opportunities | Forcing output risks replacing honest abstention with wrong answers | Abstention and incorrect counts together |

The historical-jurisdiction concentration provides the most targeted measurable
first experiment. Year has lower accuracy, but the public evidence offers less
specific direction for an intervention. No ranking implies causal certainty.

### Phase-2 hypothesis

Change only the jurisdiction instruction in the recognition prompt: explicitly
request the historical issuing jurisdiction at the coin's date, rather than its
present-day geographic successor. Do not prescribe benchmark labels or aliases.
The hypothesis is that clarifying this temporal interpretation reduces historical
jurisdiction mismatches. Modern-versus-historical confusion is a proposed mechanism,
not an observed diagnosis; strict representation differences may remain.

Hold all other prompt content, provider/model settings, image bytes and order,
preprocessing, thresholds, validator, scorer, labels, and cohorts fixed. Run the
candidate through the same frozen benchmark contract in a separately authorized
experiment. No per-specimen exceptions, repair, retries, or fallback are added.

### Success criteria

The following are proposed acceptance thresholds, not additional measurements.
For a complete candidate run with verified source integrity:

- Historical-cohort jurisdiction correctness must improve from 0/3 to at least
  1/3, preserving that scored denominator and the same scored specimens.
- Overall jurisdiction correctness must exceed 5/8 with the same scored set.
  Denomination and year correctness must not fall below 5/8 and 4/8 respectively;
  exact identity must not fall below 2/8. No previously correct verified field
  may become incorrect or abstained.
- Rejections must not exceed two; provider/runtime failures and unattempted
  specimens must remain zero. No additional specimen may be rejected, and field
  abstentions must not exceed three. Report any coverage change separately;
  it cannot substitute for improvement on the baseline scored set.

A future operator can measure these with the frozen scorer and an authorized
local comparison of retained outcomes; this task does not access those outcomes.
Passing is a screening signal only. Stochastic reruns and the small corpus do not
establish causation or generalization; repeat-run policy requires a separate
predeclared decision before promotion. Failure or an invalid comparison rejects
the candidate: restore the unchanged baseline prompt and preserve the baseline
record. No production rollout follows automatically from a pass.

### Explicit non-goals

No production changes, Phase-2 implementation or execution, provider calls,
private-data inspection/publication, validator relaxation, scoring aliases,
ground-truth invention, corpus edits, confidence calibration, or persistence
changes. Recognition remains advisory; collector acceptance retains authority.

### Deferred experiments

Defer crop/framing, rotation, lighting, blur, perspective and background changes
until public evidence supports their relevance. Also defer year/denomination
prompt changes, OCR, provider/model substitution, validator interventions,
semantic scoring, and type/design evaluation with provenance-backed truth.
Each needs its own bounded decision; none accompanies the jurisdiction edit.

## Consequences

A single prompt variable is easy to revert and measured by an existing cohort,
but may have no benefit if the errors have another cause. Strict scoring preserves
comparability while potentially counting equivalent wording as incorrect. The
selected thresholds deliberately guard against moving errors into other fields;
this corpus cannot establish real-world performance or broad regression safety.

## Reconsider When

Reconsider if the bounded candidate fails, a separately authorized repeat-run
assessment contradicts it, or new sanitized evidence changes the failure ranking.
Do not reinterpret this baseline or broaden the experiment silently.

### Next action

Obtain owner review of this proposed ADR. After acceptance, define and separately
authorize the prompt-only experiment, its execution/privacy scope and repeat-run
policy. This ADR authorizes neither paid execution nor production promotion.
