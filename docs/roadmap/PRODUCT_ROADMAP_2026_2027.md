# Coin Analyzer — Product Roadmap 2026–2027

**Status: ADOPTED — OWNER-APPROVED STRATEGIC ROADMAP**

Prepared: 2026-10-13. Planning horizon: October 2026 through 2027.

This is the proposed canonical strategic roadmap, not an implementation contract
or release approval. The owner has accepted the October strategic portfolio
assessment as provisional direction; adoption of this document remains pending.
Each implementation, experiment, data operation, and publication needs its own
bounded authorization. No Phase 1A work is authorized by this roadmap.

## 1. Vision and collector experience

Help a collector turn a newly acquired coin into a useful, trustworthy collection
record: capture or import photographs, understand what the evidence supports,
correct or complete the identity, explicitly confirm and save, then find and
reopen the coin with its photographs and provenance. The software should reduce
collector effort without pretending that uncertain attribution is certain.

The first audience is a Canadian common-coin collector using Windows with an
optional phone capture companion. Manual completion and explicitly unidentified
records are useful product outcomes; neither should be presented as independently
verified identification. Assistance earns its place field by field. Advanced
variety, condition, valuation, and broader world-coin support follow evidence of
need and qualification, rather than delaying the first understandable release.

Retain the [collector-first principles](../../PRODUCT_PRINCIPLES.md) and
[intelligence constitution](../../COLLECTOR_INTELLIGENCE_VISION.md): Coin Analyzer
advises; the collector decides. Record reproducible Discovery, Decision, and
Repetition friction before choosing UX changes. Removing unnecessary actions must
preserve the distinct human verification and save approvals.

## 2. Evidence basis and current project state

### Documentation baseline and evidence classes

Authoring baseline: repository `https://github.com/adamo-sys/coin-analyzer.git`,
worktree `C:\Projects\coin-analyzer`, branch `fix/ci-privacy-hardening`, exact HEAD
`fb03b892a295bff7fd7ff92cd1232710b5f57bca`. This is an authorized documentation
baseline, not a declaration that the branch has the newest product features.

Strategic input: retained **Review Coin Analyzer roadmap**, October 2026,
chat ID `01a1376e-2b0b-7522-8b29-6978be6e3cfc`, sections A–P. That read-only
assessment used source, local Git history, documentation, and retained handoffs;
it executed no tests or benchmarks. This roadmap retains its recommendations
while qualifying them against the repository documents linked below.

Use these classes when maintaining claims:

| Class | Meaning |
| --- | --- |
| Source-verified at authoring HEAD | Named functionality exists in inspected source/contracts; no fresh runtime or usability pass is implied. |
| Historical result | A retained report records a bounded result at its own revision/population; it is not current product performance. |
| Cached-history observation | Locally retained newer Git evidence; absent from or not qualified at the authoring baseline, and not freshly verified remotely. |
| Owner-approved direction | Provisional strategic preference, distinct from execution authority and roadmap adoption. |
| Proposed / unknown | Future work, or a claim lacking adequate evidence. Queue membership is not installation, approval, or completion. |

### Reusable assets and qualification gaps

| Area | Evidence-grounded state | Remaining qualification |
| --- | --- | --- |
| Collection management and intelligence | [PROJECT_STATE](../../PROJECT_STATE.md) and the assessment document local CRUD, acquisition accounting, photographs, import/export, deterministic gaps/want lists, and portfolio analysis. These are reusable assets, not new roadmap builds. | No application run, current market coverage, or novice acceptance was performed for this roadmap. |
| Persistence and reviewed save | [Ordinary baseline contract](../architecture/ORDINARY_COLLECTION_BASELINE.md), [reviewed phone save](../architecture/PHONE_ENTRY_REVIEWED_SAVE_SERVICE.md), and [visual save acceptance](../VISUAL_REVIEW_SAVE_ACCEPTANCE.md) establish guarded, explicit workflows and retained synthetic acceptance evidence. | Native rendering, live-provider quality, real-device journeys, crash/restore and release qualification are separate. |
| Phone capture and assistance seam | At HEAD, [PhoneEntryService](../../phone_entry_service.py) accepts an optional proposal producer, retains proposal/treatment evidence, and requires separate VERIFY/SAVE approvals. [Demo composition](../../phone_entry_demo.py) supplies no producer. | A qualified local producer and actual enabled phone suggestions are unfinished. The [first-demo guide](../PHONE_ENTRY_FIRST_DEMO.md) describes manual entry and must not be treated as proof of assisted accuracy. |
| Recognition | [Grounded pipeline](../../capture_import/grounded_recognition_pipeline.py), literal field extraction, candidate verification, conflict handling and conservative final gating exist. | Useful direct evidence, representative accuracy, production catalogue coverage and probability calibration remain unqualified. |
| Collector Work Queue | [Queue contract](../COLLECTOR_WORK_QUEUE.md) records read-only projections and native automated acceptance. | Its retained evidence explicitly leaves visual layout and manual usability unverified. It is distinct from the research queue. |
| Newer product work | The retained assessment reports search, identity correction, photo preview, visual shelf, Canadian benchmark/metadata contracts, evidence summaries and recapture handoff in newer cached history. | Reuse only after verifying the chosen implementation revision; these are not claimed as functionality at this HEAD. |
| CI and release health | [TESTING](../../TESTING.md) and repository governance define the gates. | Current exact-head CI, current release readiness and external operational state are **UNKNOWN** here. |

The locally cached `origin/main` is
`de7525909c4ac46a5c1df7c4e919f45b9f7ee1fc` (PR #400 merge), and is not an ancestor
of the authoring HEAD. No fetch or remote freshness check was performed. This
cached SHA is evidence context, not an authorized implementation base.

### Historical recognition evidence: keep populations separate

| Retained evidence | Result | Interpretation boundary |
| --- | --- | --- |
| [Recognition30 v2 canonical closeout](../recognition30-v2-baseline-closeout.md) | 1/30 identified, 29 abstained, zero reported unsafe wrong identities; correct candidate Recall@10 11/30. | Oracle-catalogue benchmark; neither production retrieval nor Canadian-phone accuracy. One accepted case cannot establish population safety. |
| Later replay mentioned in the portfolio assessment | Top-1 0/30, Recall@10 14/30, 30 abstentions, zero reported unsafe acceptances. | Retained assessment context only; underlying artifacts were not independently verified. Does not replace the canonical closeout. |
| [Separate visual-provider experiment](../architecture/VISUAL_IDENTIFICATION.md) | Country 75%, denomination 85%, year 65%, full required identity 50%. | Historical prospective result for its own frozen population, not autonomous collector-photo performance. |
| Same document, deterministic OCR/visual fusion | Identity 50% → 45%; denomination 85% → 80%; OCR corrected no visual error. | Formal **FAIL**. Automatic production fusion promotion remains rejected/unapproved. |
| [RE-01 development diagnostic](RESEARCH_EVALUATION_BACKLOG.md) | Evidence degradation changed responses in a ten-specimen diagnostic. | Sensitivity is not correctness or calibrated probability. |

Preserve immutable benchmark identities, truth, hashes, raw outputs, settings,
acceptance records and failed runs. New product metrics and derived experiments
use separate versioned evidence; do not rewrite old results or pool unlike cases.

## 3. Product-first strategic principles

1. **Deliver collector value first.** One dependable entry/reopen journey precedes
   general recognition, framework expansion or hardware procurement.
2. **Reuse before rebuilding.** Verify newer assets at an authorized implementation
   base; stale planning labels are not instructions to repeat completed work.
3. **Evidence before inference.** Keep source, side, conflict and uncertainty
   visible. A type/year range cannot supply an observed date; heuristics and
   provider scores are not probability confidence.
4. **Local-first and optional services.** Normal collection authority remains
   local. Network/AI features require explicit disclosure and optional use.
5. **Confirmation owns persistence.** Recognition, routing, research, and Command
   Center cannot approve collection writes. OCR review approval and collection
   change approval remain separate; grade stays outside OCR-derived updates.
6. **Qualify narrowly, then expand.** Enable only passed fields; preserve manual
   fallback, abstention, and conflict evidence. Do not relax gates to raise coverage.
7. **Control work in progress.** Proposed limit: one primary product implementation
   and one supporting experiment. Blocked lab work need not block independent
   collector work.

The [frozen persistence specification](../architecture/durable-persistence.md)
remains authoritative, with verified SHA-256
`A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`.
Preserve existing import/recovery authority, exact-byte freshness checks, managed
photo ownership, atomic publication and fail-closed behavior. Architectural
contradictions require an owner-reviewed amendment before production work.

## 4. Proposed milestones and dependency gates

Horizons express sequence and ambition, not promised delivery dates. Every row is
proposed future work and requires separate authorization.

| Milestone / horizon | Product outcome | Exit criteria and dependencies |
| --- | --- | --- |
| M0 — Consolidate, October 2026 | Adopt strategic direction and select one bounded entry slice. | Owner reviews this roadmap, selects exact implementation base and scope, verifies reusable newer assets and names qualification material. No broad repeat audit. |
| M1 — Assisted entry, October 2026 onward | Useful common-coin proposals inside human-controlled entry. | Phase 1A adapter and Phase 1B evidence qualify each enabled field; failure/absence preserves manual use; confirmation, save and reopen pass. |
| M2 — Show Mom, 2026–2027 after workflow qualification | A novice completes the actual collector journey. | Phase 1C native/device acceptance, onboarding, truthful failures, search/reopen and backup/recovery acceptance at one exact release candidate. A manual release may proceed while assistance stays disabled. |
| M3 — Recognition coverage, during 2027 when warranted | Fewer corrections across a wider declared population. | Independent truth, stratified holdout, measured gain and unsafe-acceptance accounting. Reference admission/retrieval only if diagnosed failures require it. |
| M4 — Collection and numismatic intelligence | Explainable next acquisitions and bounded research/condition/valuation support. | Reliable records first; one domain with explicit sources, diagnostic limits and acceptance gates. No automatic grade, authenticity or market guarantee. |
| M5 — Scale/commercial assessment, conditional 2027 or later | Maintainable deployment and optional broader services. | Sustained user demand, qualified quality, operational/privacy readiness and measured economics justify each expansion. No pricing or launch commitment. |

Critical path: authorized source revision → paired intake → manual or qualified
review → explicit confirmation/save → find/reopen → novice acceptance.
Assistance adds a qualified producer and independent proving evidence. Retrieval
adds an admitted independent gallery only when necessary. P1-B software-task
grading, a new harness, GPU infrastructure and cloud sync are not collector-release
prerequisites.

## 5. Phase 1A / 1B / 1C objectives

These names designate the portfolio assessment's three proposed work packages.
The [September Canadian plan](../superpowers/plans/2026-09-28-canadian-assisted-common-coin-identification.md)
uses “Phase 1A” for modern Canadian corpus coverage and “Phase 1B” for George VI/V
extension. Those historical coverage labels remain intact; task contracts must
identify which naming scheme they mean. The modern corpus is a proving scope,
not proof that all its families are supported today.

### Phase 1A — Local proposal composition

Implement a bounded offline producer behind the existing phone proposal seam,
reusing generic observations, literal country/denomination/year evidence, proposal
contracts and side-aware audit machinery. Do not build a Canada-only recognizer,
new verifier, second collection model or new persistence path.

Exit: synthetic integration proves proposal binding, side/provenance retention,
no supported value from malformed/conflicting evidence, no catalogue-derived
year, and safe producer absence/failure. Suggestions cannot verify or save;
manual fields remain usable. Real-phone enablement stays disabled until Phase
1B passes. Any needed dependency/provider or architecture expansion stops for a
new decision. At present this is proposed implementation, not completed work.

### Phase 1B — Proving population and field qualification

Choose one narrow common-coin population, authorize exact query captures and
truth records, and reuse applicable Canadian metadata/benchmark contracts after
base verification. Freeze case identity, source rights, capture roles, expected
field states, holdout separation, baseline, one treatment, resource budget and
decision thresholds before execution. Synthetic tests prove contracts, not photo
recognition. Capture evidence is distinct from a reference gallery.

Exit: retain counts for correctness, coverage, false-supported fields, conflicts,
abstentions, manual corrections, latency and failures; explain the first material
bottleneck and record enable/keep-disabled decisions per field. Preserve the
Canadian plan's minimum gates: zero false supported years, zero false standard
reverse assertions over documented alternate designs, and zero loss of conflict
evidence. Owner must set other thresholds, holdout size and useful coverage floor
prospectively. Zero observed errors is not proof of zero underlying risk.

No unresolved truth or uncertain material is admitted merely to finish the phase.
George VI/V coverage extension remains later work under the same generic contract.
Varieties/errors, broad world coins, grading and automatic persistence are excluded.

### Phase 1C — First novice release candidate

Compose one supported capture/import route, understandable uncertainty and manual
completion, explicit confirmation, existing search/photo/correction surfaces and
concise setup guidance. Measure the native journey with a novice observer.

Exit: normal, abstaining and corrected cases save/reopen accurately; rejection and
cancellation create no unintended entry; persistence failure never announces
success; photographs remain attached; setup and backup/recovery expectations are
understood. Record exact candidate revision, environment and remaining limitations.
This milestone does not authorize a general UI redesign or release publication.

## 6. Minimum viable Show Mom release

The novice should be able to:

- Launch without repository expertise and identify the active collection.
- Capture/import one coin with explicit obverse/reverse roles through a supported
  route; phone use retains the approved private-LAN posture.
- Understand suggestions, missing evidence and conflicts; edit manually or record
  an incomplete identity where the selected workflow explicitly supports it.
- Perform human verification and separate save confirmation, with truthful outcomes.
- Find the saved coin and reopen human-final values and photographs.
- Understand cancellation, safe retry/reload, backup and bounded restore guidance.

Release acceptance requires owner-observed native desktop and intended-device
journeys, not just component tests. Include unfamiliar-user task completion,
failure/recovery cases, privacy disclosure, exact-revision blocking CI and a
separately authorized backup/restore trial using sanitized temporary collections.
No private production backup is implicitly authorized. A useful manual release
does not require an embedding model or general recognition breakthrough; an
assisted release additionally requires Phase 1B field qualification.

## 7. Recognition improvement and evidence policy

Diagnose failures in order: capture/readability, direct observation/OCR, metadata
coverage, candidate recall, verification, then review presentation. Test existing
OCR/crop controls first. Run one baseline and one treatment on the same eligible
population with a predeclared stopping rule; a failed treatment stays failed.

Retain the [selective-recognition direction](../recognition30-selective-recognition-direction.md).
`AUTO_ACCEPT / REVIEW / ABSTAIN` is proposed operational routing; the existing
whole-identity gate uses `IDENTIFY / ABSTAIN`. Field-level `SUPPORTED` is an
advisory assertion, never whole-coin truth or save permission. Automatic OCR/visual
fusion remains unapproved following its failed historical promotion evaluation.
Any reconsideration needs a new bounded experiment and an explicit decision.

[E7 is CLOSED — E7 PARKED](../recognition30-e7-v2-metadata-preflight-closeout.md):
27/30 metadata resolutions and three review-required cases establish no acquired
gallery or embedding performance. Keep E7/Coin-CLIP parked. Reactivate only if
qualified direct evidence leaves material recall/design failures and an independent,
licensed, leakage-audited gallery can be specified and separately authorized.
NeoMME and calibration methodology remain conditional research, not dependencies.

Ground truth requires provenance; human confirmation alone is insufficient. Keep
training/development, holdout queries and reference galleries distinct. Unavailable
truth/confidence stays unavailable. The ten `test_coins/` JPEGs remain UNCERTAIN /
LOCAL-ONLY, excluded from external providers, CI artifacts and public manifests.
No collection records, private photos, notes, exports, credentials or backups may
be inspected or processed without exact material/operation authorization.

## 8. Collection intelligence and longer-term ambition

Harvest existing deterministic collection analysis, gap reports, want lists,
acquisition accounting and portfolio views. First make their results discoverable
and explainable in real collecting sessions. Reliable identity and acquisition
records precede stronger recommendations; missing prices or uncertain attribution
must not become manufactured estimates.

Later, qualify one useful domain at a time: evidence-backed type/variety research,
condition observations, source-attributed valuation, broader coin populations,
bulk workflows or optional services. Condition-assessment source modules do not
prove numismatic accuracy or certification equivalence. Authentication, mint-error
recognition, live market coverage, synchronization and commercial/dealer offerings
require dedicated evidence and owner scope. Preserve the intelligence constitution;
neither recommendations nor future learning systems own collection decisions.

## 9. Command Center and research queue boundaries

Command Center supports bounded delivery: exact task/base/scope, blockers, evidence
references, compact handoffs, next authorized action and review packaging. Its
[status projection](../../command_center.py) includes observation-only authority.
Existing bounded orchestration is reusable; dynamic swarms, autonomous promotion,
repository-memory platforms and hardware expansion are not product prerequisites.
Status visibility is not permission to execute, merge or persist collector data.

Use existing queues rather than copying their contender lists:

| Record | Role |
| --- | --- |
| [Research/evaluation backlog](RESEARCH_EVALUATION_BACKLOG.md) | RE-01 retained diagnostic, RE-02 shadow retrieval and RE-03 methodology dispositions. |
| [AI tool evaluation](../AI_TOOL_EVALUATION.md) | Tool evidence, scorecards and empirical adoption decisions. |
| [Engineering tooling roadmap](../ENGINEERING_TOOLING_ROADMAP.md) | Assurance/tooling sequence and later pilot closeouts; older pending labels must be reconciled. |
| [Self-improvement roadmap](../SELF_IMPROVEMENT_ROADMAP.md) | Bounded agent machinery and separate future scope. |
| [Task queue](../../TASK_QUEUE.md) | Historical and bounded engineering execution records; not strategic permission. |
| [Bake-off runbook](../../benchmarks/bakeoff-v1/RUNBOOK.md) | Software-task evaluation protocol; its existing local modification is outside this roadmap change. |

Proposed consolidated intake policy: every research item names the existing product
decision it could change, its current evidence class, queue owner/record, one
baseline, eligible data, cost cap, stop rule and adoption gate. Deduplicate by
problem, not model/tool name. Use TEST NEXT / WATCH / NO ACTION within the existing
records when separately authorized; this file does not edit their statuses.
No challenger gets an independent permanent workstream solely through novelty.
Unknown external queue items remain unknown; no installation or adoption is inferred.

## 10. Priorities: retained versus proposed

| Priority | Retained direction/assets | Proposed action, separately authorized |
| --- | --- | --- |
| NOW | Collector-first, local-first, manual fallback, explicit confirmation, existing persistence/review and provisional narrow-assisted-entry direction. | Owner adoption/base decision; Phase 1A producer composition and Phase 1B proving contract. Enable nothing before evidence gates. |
| NEXT | Existing capture/review/save, newer cached collector surfaces to verify/reuse, Canadian planning safety rules. | Qualify passed fields; finish Phase 1C Show Mom acceptance, onboarding and backup/recovery evidence. |
| LATER | Explainable collection intelligence and selective-recognition direction. | Wider Canadian coverage including George VI/V, conditional retrieval, one evidence-backed research/valuation domain, then scaling. |
| PARKED | E7/Coin-CLIP parking, failed fusion promotion, P1-B blockers and immutable benchmark/acceptance evidence. | Keep broad harness tournaments, memory frameworks, calibration/fine-tuning and homelab/GPU expansion off the critical path until a measured decision warrants reopening. |

Retained means preserving a decision, boundary, asset or historical result—not
asserting fresh acceptance. Proposed means prioritization only. Previously rejected
automatic fusion promotion remains rejected; parking does not erase that verdict.

## 11. Product KPIs and measurement contract

**North star: verified collection-ready identifications per 100 real submitted
coin-photo cases.** One case is one physical coin submission; additional photos
and retries remain linked to it. Predeclare population and required identity scope.
Keep failures, unresolved cases and abstentions in the denominator. Report supported
and unsupported strata and an overall intake view; do not drop difficult cases.

A qualifying numerator requires independently supported identity at that scope,
human review, retained evidence, successful save and successful reopen. Report
manual and assisted contributions separately. An unidentified record may count
as workflow success, never as verified identification. No current value or
population target is established by this documentation task.

| KPI | Definition / reporting obligation |
| --- | --- |
| Unsafe acceptance | Wrong machine-supported identity/field treated as accepted at its declared scope. Report count per submitted case, error among accepted cases, and false-supported proposals even when the collector catches them. Separate year/design and catastrophic cases; human save confirmation does not excuse machine error. |
| Field precision and coverage | Correct supported values / adjudicated supported values; supported values / eligible field opportunities. Show country, denomination, date and enabled design separately; missing truth is unavailable, not correct. |
| Routing and retrieval | Review/abstain proportions with denominators; conflict preservation; Recall@K only for a declared gallery/relevance endpoint. No mixing oracle and production retrieval. |
| Collection integrity | Successful save-and-reopen / attempted saves; false success, stale overwrite, media loss and recovery failures as separate counts. |
| Collector effort | Novice completion rate, actions/corrections, repeated steps, intervention count and reproducible friction observations against a manual baseline. |
| Latency and cost | End-to-end median/p95 including retries/review/recovery; provider/compute spend per verified case, with owner review time separately recorded. |
| Evidence completeness | Provenance/role/rights/expected-state coverage by population stratum and enabled field. |

Freeze thresholds and budgets prospectively with the owner. Do not substitute
historical accuracy for these product-use KPIs or interpret zero observed unsafe
cases as a population guarantee.

## 12. Outstanding decisions and blocked work

Owner decisions at the applicable execution gate:

1. Adopt/revise this roadmap and choose the exact newer implementation base.
2. Select the first coin population and authorize exact proving captures, truth,
   rights/privacy classification and evaluation operations.
3. Set field thresholds, holdout size, coverage floor, latency/cost caps and the
   novice acceptance observer; decide manual versus assisted first release scope.
4. Confirm how incomplete/unidentified records fit the selected entry route,
   retaining its existing required-field and confirmation contracts.
5. Define release candidate packaging, backup/restore acceptance and separately
   authorized publication; preserve optional disclosed cloud image processing.
6. Confirm the proposed WIP limit and keep lab/hardware work outside the critical path.

Before Phase 1A, approve the exact implementation revision and bounded producer scope, first proving population and prospective field thresholds, and WIP limit. Retain the Canadian plan’s requirement to approve holdout size and coverage floor before implementation. Exact capture-processing authorization is required before evaluation; novice observer, incomplete-record handling, packaging and backup/restore acceptance are required before the corresponding Phase 1C work. Publication requires separate authorization when a qualified release candidate exists.

Preserved blockers from the owner mandate and retained assessment:

- **P1-B5 DESIGN CLOSE WITH NOTES.**
- **P1-B contract REVISE.**
- **P1-B implementation BLOCK.**
- **P1-B operational grading BLOCKED.**

P1-B is software-task grading, distinct from coin condition grading. Original
Revision 2 contract and P/Q/R ledgers were not verified for this roadmap; reconstructed
inventories do not replace them. Scored harness comparison remains blocked on the
retained seal/custody, settings, authorization, enforcement, isolation/delivery
and runtime grading gates. This roadmap neither reopens nor resolves them.

Real-phone assistance is blocked pending producer composition and independent
field qualification. Broad reference readiness and Museums Victoria NU 28226
production admission remain unestablished here. E7 stays parked, and fusion
promotion stays failed. Current CI/native acceptance and external installations
are unknown; hardware capacity is not assumed. These limitations do not create
dependencies on independent collector work.

## 13. Maintenance, adoption and PROJECT_STATE relationship

After explicit owner adoption, this file should own strategic product priorities,
milestone dependencies and KPI definitions. [PROJECT_STATE](../../PROJECT_STATE.md)
continues to own dated implementation/evidence snapshots, exact revisions,
validation and active stop points. Neither file grants implementation authority.

Retain [historical product roadmap](PRODUCT_ROADMAP.md),
[locked sprint sequence](COIN_ANALYZER_ROADMAP_LOCKED.txt),
[root roadmap](../../ROADMAP.md), and
[dated reconciliation](../BACKLOG_RECONCILIATION_2026_09_08.md).
Adoption does not erase their architectural decisions, historical checkpoints or
acceptance evidence. Conflicting status labels require evidence reconciliation;
frozen contracts prevail over strategic aspirations. This authoring change updates
no index, queue or PROJECT_STATE entry.

Review at each milestone exit, owner scope/base change, blocking acceptance result,
corpus/provider/schema change, material KPI regression, or research result that
changes a product decision. Recheck before enabling a field or preparing a release.
Every proposed update records date, reason, exact evidence revision, retained versus
changed decision, owner adoption status and remaining gates. Archive comparisons
by reference; never overwrite immutable historical evidence. Stop on unsupported
claims, privacy/provenance ambiguity or architecture contradiction.

Authoring validation is documentation-only. No tests, benchmark/provider calls,
native acceptance, current CI verification, release or Phase 1A implementation
are implied. The next action is owner review of this proposed roadmap.
