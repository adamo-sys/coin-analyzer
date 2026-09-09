# Accuracy research and evaluation backlog

Canonical tracking for the 2026-09-09 Coin Analyzer research delta. **Planning only:
no experiments executed, models installed, specimens selected, or production
dependencies introduced.** These are hypotheses, not verified model capabilities.
Promotion to execution requires a separate bounded task.

This queue complements the existing [evaluation harness contract](../architecture/EVALUATION_HARNESS.md)
and visual-identification evaluation work (#23); it does not duplicate the frozen
benchmark work (#21), engineering assurance #213/T10, tooling #137, or corpus
rights/reviewer work. Rights/readiness are prerequisites, not authorization to
inspect or process private material. No frozen benchmark is modified or used for
tuning. The ten local-only JPEGs are not implicitly eligible development data.

## RE-01 — Visual-evidence sensitivity audit

**Disposition: TEST NEXT — highest-priority new research item.**

- **Hypothesis:** a visual identifier relying on a genuinely decisive region
  should change its answer, abstain, or reduce its reported score when that
  evidence is obscured; unchanged unsupported claims may expose visual
  insensitivity. Prediction change alone is not proof of appropriate reasoning.
- **Prerequisites:** identify the exact black-box provider/model/revision and
  supported output fields; pin prompts, settings, image preprocessing and code
  SHA. Predeclare decisive regions and the claim each supports before model runs.
  Confirm that other views/context do not reveal the removed evidence. Include
  a non-decisive-region perturbation control to distinguish evidence sensitivity
  from generic image degradation. Set a small run/cost cap before execution.
- **Dataset/evidence:** exactly 10 non-frozen development specimens, each with
  certain reference identity, known decisive region(s), specimen ID, provenance
  and permitted processing. Keep intact, blurred and removed-region variants
  paired under the same specimen; retain transformation parameters, masks and
  hashes, outputs, score availability and human evidence adjudication. Variants
  inherit source restrictions. No provider upload without applicable permission.
- **Metrics:** prediction-change rate relative to intact, with abstention reported
  separately; paired confidence/score reduction where a comparable score exists;
  unsupported-evidence rate (unsupported factual claims / adjudicated factual
  claims, plus a specimen-level any-unsupported-claim rate); specimen-weighted
  error (average variant error within each specimen, then equal-weight average
  across specimens). Report exact counts/denominators, coverage/abstention and
  intact accuracy; do not count abstention as correct identification. Missing
  scores are unavailable, not zero. Provider scores remain uncalibrated.
- **Success/failure decision:** a successful diagnostic produces complete paired
  evidence and identifies whether response changes track decisive evidence more
  than control perturbations, without hiding intact errors. Persistent confident
  unsupported claims after removal are a negative model finding, not a failed
  experiment. Ten specimens support a directional diagnostic, not a population
  guarantee or adoption threshold. Freeze numeric decision rules before execution
  if needed; do not choose them after viewing results.
- **Stop conditions:** stop at the 10-specimen scope/run cap; pause for missing
  rights, uncertain labels/regions, residual decisive cues, unusable variants,
  provider/config drift or repeated infrastructure failure. Do not add specimens
  or tune prompts mid-audit to improve results.
- **Production dependency impact:** none. Evaluation diagnostic only; no runtime
  gate, automatic model switch, confidence reinterpretation or production tuning.

## RE-02 — NeoMME-260M shadow retrieval pilot

**Disposition: WATCH / SMALL PILOT — after RE-01 and the intervening priorities.**

- **Hypothesis:** this candidate may improve specimen-weighted retrieval recall
  within a practical local CPU/memory/storage budget. No capability, license or
  performance claim is accepted from its name alone.
- **Prerequisites:** verify exact upstream artifact/revision, license, integrity,
  modality/task suitability and safe loading requirements before any download;
  identify and freeze the current retriever, candidate gallery, query construction
  and ranking/tie rules. Predeclare absolute local latency/RAM/storage budgets and
  a bounded run cap on the target machine. Do not replace the current retriever.
- **Dataset/evidence:** use the same 10 development specimens as RE-01, with a
  separately specified retrieval relevance manifest and fixed gallery/distractors.
  Use intact queries as the primary comparison; report any perturbation analysis
  separately. Exclude same-specimen duplicates/derived query leakage from the
  gallery unless explicitly required by the declared task. If meaningful relevance
  labels/gallery cannot be established, defer rather than fabricate a benchmark.
  Both retrievers receive identical queries, gallery and relevance judgments.
- **Metrics:** specimen-weighted Top-1/Top-3 recall (aggregate query successes
  within each specimen, then weight specimens equally); paired per-specimen
  wins/losses; CPU latency median/p95 with cold loading/index construction separate
  from warm embedding/search; peak process RAM; embedding bytes total/per gallery
  item, with auxiliary index storage reported separately. Record hardware, threads,
  tool/model versions, failures and baseline measurements under matched conditions.
- **Success/failure decision:** continue only if recall benefit or a clear resource
  advantage appears under the predeclared budgets without concealing Top-1 losses.
  Report ties/inconclusive results honestly; this small set cannot justify a
  production replacement. Stop/defer for no useful signal or unsuitable resources.
- **Stop conditions:** terminate early if CPU latency or peak RAM clearly exceeds
  the declared local budget, or artifact/license/loading requirements are unsafe
  or unresolved. No GPU/infrastructure repair, unbounded optimization, dataset
  expansion or search for favorable configurations within this pilot.
- **Production dependency impact:** none. Isolated shadow evaluation; no retriever
  replacement, new runtime dependency, or production index migration.

## RE-03 — Conformal factuality / risk control

**Disposition: WATCH / FUTURE — methodology note only.**

- **Hypothesis:** with sufficient independent labelled evidence and defensible
  assumptions, a calibrated abstention/risk-control method may bound a defined
  factual-error event while retaining useful coverage. No guarantee is claimed.
- **Prerequisites:** a substantially larger independently labelled corpus; a
  clearly defined specimen-level loss, target risk and uncertainty level; a
  defensible sampling/exchangeability assessment; and disjoint calibration and
  evaluation specimens. Revisit sample-size feasibility from the chosen method
  and target risk, not from the current ten-specimen diagnostic.
- **Dataset/evidence:** independent specimen groups, reviewed factual labels,
  documented disagreement/uncertainty, provenance and permitted processing;
  no leakage through multiple photos or perturbations of one specimen. Preserve
  calibration/evaluation separation and document likely deployment shift.
- **Metrics for a future design:** specimen-level factual-error risk, coverage /
  abstention, selective error, uncertainty bounds and sample-size feasibility;
  distinguish empirical observations from any assumption-dependent guarantee.
- **Success/failure decision:** the note is useful if it defines the loss,
  assumptions, required labels/splits, and feasibility conditions. Defer if the
  corpus is too small or independence/assumptions cannot be defended. Formal
  guarantees must not be inferred from uncalibrated provider confidence.
- **Stop conditions:** stop at methodology tracking now. Revisit only when the
  independent labelled corpus is substantially larger and feasibility is reviewed.
  No implementation of model-internal hidden-state methods, instrumentation,
  calibration training, or model/provider changes.
- **Production dependency impact:** none, now or implicitly on later pilot success.

## Recommended execution order and reconciliation

Requested cross-track sequence: **RE-01 visual-evidence audit → #204 compatibility
checkpoint → T10 Semgrep → Hy3/Hy4 bake-off → RE-02 NeoMME shadow pilot**.

Inspection of current main `945240b0817edc939b3a5a5452de6558c0162fd4` confirmed
#204 is already merged (merge `28aab14ba14487d64ac24f33a6980dd9db5c48db`).
Do not reopen or repeat that work without a new compatibility gap. Therefore the
remaining order is **RE-01 → T10 → Hy3/Hy4 → RE-02**. Cross-track references express
priority only; this document does not change those tracks or start their work.
RE-03 stays deferred until its corpus/feasibility trigger, not a scheduled next run.

Among this delta alone: **RE-01 first; RE-02 later; RE-03 watch only**.
