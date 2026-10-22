# AI Tool Evaluation Log

Purpose: evaluate developer tooling empirically before adopting it into the normal Coin Analyzer workflow.

## Evaluation rules

- A tool must solve a specific workflow problem; novelty alone is not sufficient.
- Experiments use bounded branches and existing acceptance criteria.
- The primary implementation agent and independent reviewer should be separated where practical.
- Existing CI, regression, privacy, provenance, and scope boundaries remain authoritative.
- Tool cost includes subscription/API spend, setup time, intervention time, and review burden.
- A tool is not adopted until it demonstrates measurable value across repeated real tasks.

## Standard scorecard

For each tool or configuration, record:

- role/purpose;
- software cost and model/API cost;
- tasks evaluated;
- task completion rate;
- defects or scope violations found;
- false-positive review comments;
- tests selected and outcomes;
- files changed and unnecessary churn;
- human interventions required;
- approximate completion time;
- decision: adopt, optional, retry later, or reject.

## Developer-tool version record

Current status correction (2026-09-08): `atomic_json.py` joined the blocking
boundary in PR #212; the candidate note below is historical. PR #216 pinned
action references, and #218 tracks truthful mutation-evidence capture. See
[closeout](BACKLOG_RECONCILIATION_2026_09_08.md) and
[OpenCode review log](OPENCODE_REVIEW_LOG.md) for the actual retrospective #216
execution and its limitations. T9's partial Windows run is not a successful
coverage/overhead baseline.

This is the canonical inventory of development/quality tool version sources,
verified against main `5d8688e6085524e4c1966c11c30b471c06c59d22` for Issue #52.
The linked executable declarations remain authoritative: this record does not
install tools, change pins, or freeze floating CI resolutions. Update the matching
row when changing its declaration; keep historical pilot results below intact.

| Tool | Declared version / resolution | Authoritative declaration and scope |
| --- | --- | --- |
| Python | 3.12 in CI; patch selected by setup-python | [Tests](../.github/workflows/tests.yml) and the other workflow setup steps; not an exact interpreter build pin |
| Ruff | 0.16.5 | [Tests](../.github/workflows/tests.yml), required syntax-only E9 gate |
| Pyright | 1.1.411 | [Tests](../.github/workflows/tests.yml) and [Quality Advisory](../.github/workflows/quality-advisory.yml); keep both declarations aligned |
| Gitleaks | action v3; binary version not explicitly pinned here | [Tests](../.github/workflows/tests.yml), required history scan |
| Hypothesis | lock snapshot 6.167.1; CI resolves an unpinned requirement | [requirements-dev.lock](../requirements-dev.lock), [requirements-dev.txt](../requirements-dev.txt), and [Quality Advisory](../.github/workflows/quality-advisory.yml) |
| coverage | lock snapshot 7.16.0; declared unpinned, no CI measurement yet | [requirements-dev.lock](../requirements-dev.lock) and [requirements-dev.txt](../requirements-dev.txt) |
| pytest | lock snapshot 9.1.1; declared unpinned | [requirements-dev.lock](../requirements-dev.lock) and [requirements-dev.txt](../requirements-dev.txt); used by the mutation pilot |
| mutmut | 3.7.0 | [Mutmut Advisory](../.github/workflows/mutmut-advisory.yml), manually dispatched non-blocking pilot |
| pip-audit | 2.10.1 | [Dependency Audit](../.github/workflows/dependency-audit.yml), audits the three lockfiles |
| CodeQL | action v4; analysis bundle managed by the action | [CodeQL Advisory](../.github/workflows/codeql.yml); not a fixed analyzer binary version |
| uv | generator version not recorded | Lockfile headers record `uv pip compile` commands, not the generator version; no new version is inferred |

Runtime requirements are intentionally unchanged. A lock snapshot is evidence of
one resolution, not proof that workflows installing `.txt` files use those exact
versions. Consolidating executable tool constraints or adopting lockfile installs
requires a separate compatibility change; do not turn this inventory into a
second dependency mechanism.

### Issue #52 bounded maintenance findings

- **PR template / security policy:** both already existed. The maintenance slice
  fills explicit CI/stop-condition/collection-authority reporting and credential
  exposure/private-collection guidance rather than creating duplicate documents.
  GitHub private vulnerability reporting was disabled when checked; SECURITY.md
  retains its existing conditional channel and minimal public contact-request
  fallback. No contact address or service commitment is invented.
- **Coverage:** the dependency already exists, but there is no measurement job or
  defensible percentage baseline. Defer instrumentation: another full test run
  would duplicate costly regression work, while adding tracing to a required job
  needs an overhead comparison. A separate advisory-only pilot should measure
  the same synthetic test selection with/without coverage, establish source and
  fixture exclusions, and publish text/JSON evidence only. No percentage gate,
  badge, benchmark claim, or test replacement is authorized by this record.
- **CI runtime:** every inspected job already has a timeout; most Python jobs
  use setup-python pip caching. Per-job dependency installs serve isolated
  environments and are not removable as duplicate shell steps. Push and PR runs,
  the standalone Hypothesis pilot versus discovery, and pre-discovery boundary
  tests overlap intentionally or potentially; measure their diagnostic value and
  cache hit rates before changing trigger/gate behavior. The manual mutation job
  has no pip cache; frequency/cost evidence is needed before optimizing it.
  One [main test run](https://github.com/adamo-sys/coin-analyzer/actions/runs/34175279374)
  at the same recorded SHA took 65 seconds for Ubuntu and 186 seconds for Windows
  (job elapsed time, not a typical-runtime baseline or isolated test duration).
- **Next Pyright candidate:** `atomic_json.py`, a small stdlib-only module. The
  [current advisory artifact](https://github.com/adamo-sys/coin-analyzer/actions/runs/34175279339)
  reports 691 files, 3,189 errors, and 1 warning overall, with zero diagnostics for
  that module. This nominates a separate focused `pyright atomic_json.py` check
  under 1.1.411 plus its existing persistence tests before any blocking expansion;
  it does not claim that standalone check was run. Do not change atomic-write,
  receipt, or collection authority semantics for typing. High-debt GUI/provider
  modules remain inappropriate for this maintenance slice.

No CI workflow, required check, production module, runtime dependency, or Issue #52
checkbox is changed by this documentation-only slice. Existing dependency auditing,
CodeQL, property tests, and type gates are retained even where older issue text
still describes them as future work.

## Current stack

### Codex

- Role: primary implementation agent for bounded vertical slices.
- Status: adopted.
- Guardrails: explicit scope/invariants, focused tests, full regression, changed-file/test/risk reporting, stop conditions on failed gates, and user merge authority.

### GitHub Actions

- Role: authoritative automated verification on pushes and pull requests.
- Status: adopted.
- Current gates: Windows and Ubuntu tests, Gitleaks history scanning, syntax-level Ruff checks, and a bounded blocking Pyright boundary for cleaned modules.

### Gitleaks

- Role: secret scanning.
- Status: adopted.
- Baseline: full working tree and 470-commit history scanned clean after a narrow allowlist for known non-secret processed-artifact fixture identifiers.

### Ruff

- Role: static lint/syntax checking.
- Status: adopted at syntax-only baseline.
- Current gate: E9 only.
- Ratchet plan: expand rule coverage only after existing lint debt is measured and cleaned in bounded work.

### Pyright

- Role: static type analysis.
- Status: adopted in mixed advisory/blocking mode.
- Whole-repository mode remains advisory so existing type debt is visible without blocking unrelated work.
- Cleaned modules are promoted into a blocking CI boundary incrementally. The current bounded gate covers `event_bus.py`, `image_analyzer.py`, `denomination_label_audit.py`, `market_intelligence_automation.py`, `photo_inbox.py`, `confirmed_observation_evaluator.py`, `diagnostic_agent.py`, `improvement_agent.py`, `retrieval_contracts.py`, and `local_retrieval.py`; this scope is read directly from `.github/workflows/tests.yml`. The whole-repo advisory workflow remains pinned to Pyright 1.1.411 for comparable debt measurements.

### Hypothesis

- Role: property-based testing for edge cases and invariants.
- Status: adopted for bounded deterministic invariants; expansion remains evidence-driven.
- Initial pilot: deterministic case-insensitive deduplication in `market_intelligence_automation._dedupe`.
- Mutation cross-check: the same property test killed all 11 generated `_dedupe` mutants in the first bounded mutmut pilot, providing evidence that the property test detects meaningful behavioral regressions rather than only exercising the function.

### Mutmut / mutation testing

- Role: measure test sensitivity by injecting bounded code mutations into deterministic logic.
- Status: adopted for targeted local quality diagnostics; not a repository-wide CI gate.
- Environment: mutmut 3.7.0 requires WSL on Windows. Running from the `/mnt/c/...` NTFS mount failed when mutmut copied metadata into `mutants/`, so successful pilots use a disposable Linux-native copy under the WSL home directory.
- Pilot 1 target: `market_intelligence_automation._dedupe`, with test selection limited to `tests/test_property_based_quality_pilot.py`.
- Pilot 1 result: 11 `_dedupe` mutants executed, 11 killed, 0 survived, 0 timeouts, and no suspicious results; bounded mutation score 100% for that function. This confirmed that the existing Hypothesis test strongly pins case-insensitive uniqueness, trimming, blank filtering, and order preservation.
- Pilot 2 target: `deal_hunter_ranking.DealHunterRankingEngine._budget_points`, a deterministic boundary-scoring function with thresholds at 0, 50, 100, 250, and 500.
- Pilot 2 baseline: all 17 generated `_budget_points` mutants survived the existing `test_deal_hunter_ranking.py` suite. Inspected survivors included `<= 0` to `< 0`, `<= 50` to `<= 51`, `<= 250` to `< 250`, and final return `-8` to `-9`, demonstrating a concrete missing boundary contract rather than equivalent-mutant noise.
- Pilot 2 remediation: added one focused table-driven boundary test covering negative/zero input, each exact threshold, values immediately above each threshold, and the above-$500 result.
- Pilot 2 result after remediation: 17/17 mutants killed, 0 survived, 0 timeouts, and no suspicious results; bounded mutation score improved from 0% to 100% for `_budget_points`.
- Interpretation: the two pilots demonstrate both useful outcomes: mutation testing can confirm strong existing tests and can expose a specific green-suite coverage weakness that a narrow regression test then closes.
- Decision: keep mutation testing as an explicit bounded/advisory diagnostic and use it selectively for deterministic functions with clear contracts. Do not add a whole-repository mutation gate until runtime, dependency setup, and signal-to-noise justify stronger integration.

### AgentDiff

- Role: deterministic/heuristic agent-oriented diff analysis for change grouping, relationship mapping, change-type classification, and reviewer navigation; not an AI semantic-review authority.
- Status: retain for advisory evaluation.
- Controlled benchmark: evaluated the exact PR #199 (runtime readiness) diff, base `ec8b4a7169445802a57fd937f9ca9cf9bb45a161`, head `aaf0b8bff95b75464d6964360380f48c67d3399c`; 7 changed files, +462/-64.
- Result: classified 2 files high risk, 4 medium, and 1 low. Correctly identified relationships among runtime readiness, startup integration, GUI integration, and tests, and produced a useful reviewer-oriented change map and review order.
- Risk-label weaknesses: classified a synthetic secret sentinel in a test as secret exposure and architecture documentation discussing auth/API-key boundaries as high risk. Assigned `Launch_Coin_Analyzer.bat` low risk despite meaningful startup/interpreter-selection and exit-code behavior.
- Operational notes: Windows/PowerShell input handling rejected UTF-16 and UTF-8 BOM JSON; no-BOM UTF-8 was required. Plan schema/discovery was not obvious from CLI help.
- Comparison scope: Ruff 0.16.6 and Semgrep 1.176.1 ran against the exact PR #199 head, limited to the five changed Python files: `coin_analyzer_startup.py`, `coin_collection_gui.py`, `runtime_readiness.py`, `tests/test_coin_collection_gui_entrypoint.py`, and `tests/test_runtime_readiness.py`.
- Comparison results: Ruff produced concrete deterministic findings including BLE001 broad `Exception` catches, import ordering, and unused imports. Semgrep produced one `exec()` audit finding in `tests/test_coin_collection_gui_entrypoint.py`; two rules timed out against `coin_collection_gui.py`, which dominated core scan time (approximately 48 of 49 seconds).
- Evidence boundary: this head-only comparison does not establish which Ruff/Semgrep findings PR #199 introduced; that claim requires a base-vs-head differential scan.
- Decision: retain/evaluate as advisory tooling. AgentDiff provides change grouping, relationship mapping, change-type classification, and reviewer navigation that Ruff/Semgrep do not, but does not replace deterministic linting, static/security analysis, tests, or CI. Do not use its risk labels as a merge gate or security authority.
- Suggested role: agent change -> AgentDiff review map -> deterministic/static analysis + tests -> CI authority.

### OpenCode

- Role: independent read-only reviewer/second opinion, not primary implementer.
- Status: provisionally adopted as the preferred independent reviewer, pending repetition across more real PRs.
- First controlled benchmark: reviewed historical PR #60 (`87c0097e1fbca2260957081a93d2eb96b3107888..90073eaf765ea9d69e34532ed05bd4811f2c291c`) using Qwen3-Coder-Next through OpenCode.
- Result: correct merge recommendation; one useful non-blocking observation that `Dict[str, Any]` is broader than an eventual precise result type; one low-value/false-positive workflow-label nit; no fabricated blockers or severity inflation.
- Operational notes: browser/model setup was straightforward after authentication; a Unix-style `head` command failed under PowerShell, but the review recovered. OpenAI quota exhaustion did not block the pilot because an alternate Qwen/Hugging Face model was available.
- Decision: adopt as an optional independent reviewer now; do not make it an authoritative merge gate until several additional bounded PRs reproduce the signal-to-noise result.

### Goose

- Role: optional second-opinion reviewer and candidate MCP/orchestration layer.
- Status: keep installed; useful but not the preferred routine reviewer yet.
- Controlled benchmark: reviewed the same historical PR #60 through Goose/OpenRouter using Qwen3-Coder after an initial Claude Sonnet configuration encountered provider/credit friction.
- Result: correct merge recommendation and clean recognition that the annotation change fixes an existing static contract mismatch without changing runtime behavior; little review noise in the completed run.
- Operational notes: Windows setup had substantially more friction than OpenCode. The first review attempted Unix-style `sed`; OpenRouter OAuth/key setup required extra intervention; model/provider selection and spend controls added setup burden. A small OpenRouter credit purchase was made for the experiment.
- Decision: optional/keep. Re-evaluate for orchestration/MCP workflows or occasional second opinions rather than making Goose a required reviewer.

### Ollama/local models

- Role: zero-API-cost local assistance where hardware permits.
- Status: adopted for low-stakes auxiliary work; rejected as an authoritative merge reviewer on the current laptop/model sizes.
- Controlled benchmark: reviewed the same PR #60 using local `qwen2.5-coder:3b` and `qwen2.5-coder:7b`.
- 3B result: overall merge verdict was directionally correct, but the model claimed test/coverage adequacy without evidence and blurred static annotation changes with runtime behavior. Review discipline was insufficient for merge gating.
- 7B result: materially better instruction following and evidence discipline than 3B, but still overstated regression risk from an annotation-only change and from expanding Pyright coverage. Heavy prompts also triggered a CUDA `shared object initialization failed` error, while trivial prompts succeeded, showing hardware/runtime instability at this size on the current machine.
- Decision: use local models for summarization, code explanation, preliminary review, test-idea generation, documentation cleanup, and other low-risk tasks. Do not use the current 3B/7B local setup as an authoritative independent reviewer.

### OpenHands

- Role: autonomous issue-to-solution experiment.
- Status: deferred.
- Entry condition: mature CI gates, isolated environment, bounded issue, and explicit comparison against the existing Codex workflow.

## Controlled reviewer benchmark: PR #60

Historical change under review:

- base: `87c0097e1fbca2260957081a93d2eb96b3107888`;
- head: `90073eaf765ea9d69e34532ed05bd4811f2c291c`;
- production change: widen `CoinAnalyzer.analyze_coin()` from `Dict[str, str]` to `Dict[str, Any]`, matching an existing mixed-value result payload;
- CI change: expand the blocking Pyright boundary from `event_bus.py` to `event_bus.py image_analyzer.py`;
- known validation evidence from the original PR: `pyright event_bus.py image_analyzer.py` passed with zero errors/warnings/informations and the authoritative local full regression passed with 4,847 tests run, 24 skipped, and no failures.
- CI-control follow-up: PR #62 repaired the focused Pyright job's missing runtime-dependency installation after GitHub Actions exposed the configuration gap; this reinforces that reviewer verdicts are advisory and CI remains authoritative.

### Comparative result

| Reviewer configuration | Review quality | Noise / false positives | Operational friction | Cost profile | Decision |
| --- | --- | --- | --- | --- | --- |
| OpenCode + Qwen3-Coder-Next | Strong | One useful minor observation; one low-value nit | Low to moderate | Free/alternate-provider route available | Adopt as preferred optional reviewer |
| Goose + Qwen3-Coder via OpenRouter | Strong | Very little in completed run | High on Windows/provider setup | Small paid OpenRouter usage | Keep for optional second opinion/orchestration |
| Ollama + Qwen2.5-Coder 7B | Moderate | Overstated runtime/regression risk | Low after install, but hardware instability on heavier prompts | No API cost | Auxiliary use only |
| Ollama + Qwen2.5-Coder 3B | Weak to moderate | Unsupported claims about tests/coverage; muddled typing/runtime reasoning | Low | No API cost | Do not use for merge review |

## Current workflow recommendation

For bounded Coin Analyzer changes, prefer:

1. Codex or another approved implementation agent performs the scoped change.
2. Focused tests and the authoritative GitHub Actions gates verify behavior and repository boundaries.
3. OpenCode performs an independent read-only review on selected real PRs.
4. Goose may be used for a second opinion or future MCP/orchestration experiments when the extra setup/cost is justified.
5. Ollama/local models may assist with low-risk preparation and explanation, but do not replace CI or the independent reviewer.
6. Use Hypothesis and targeted mutation testing where deterministic invariants justify the extra diagnostic cost; mutation results remain advisory unless a future bounded gate is explicitly approved.
7. Merge only when the reviewed head is unchanged, blocking CI is green, and no substantive review blocker remains.

## Planned experiments

1. Continue the Pyright module-by-module blocking ratchet while leaving whole-repo Pyright advisory.
2. Add one additional Hypothesis property test only where invariants are clear and deterministic.
3. Repeat OpenCode read-only review on several additional real PRs and track useful findings, false positives, intervention time, and cost before making it a routine gate.
4. Continue mutation testing only on selected deterministic targets where a clear contract makes survivor interpretation useful; the first two pilots are complete and mutation testing remains advisory.
5. Revisit Goose specifically for controlled MCP/tool orchestration rather than duplicating OpenCode's reviewer role.
6. Defer larger local-model reviewer experiments until hardware changes or a smaller, demonstrably stronger model becomes available.
7. Later benchmark autonomous agents on a small set of historical bounded tasks using task success, test pass rate, scope compliance, human intervention, time, and cost.

### Deferred candidate — Sakana AI MASS

**Disposition: DEFERRED, BOUNDED RESEARCH CANDIDATE — Coin Analyzer / Command Center workflow evaluation only.**

- **Source and scope:** [Sakana AI MASS: Recursive Self-Improvement through
  Multi-Agent Self-Supervision](https://pub.sakana.ai/mass/) and its
  [reference repository](https://github.com/SakanaAI/mass). MASS combines
  multi-agent workflow optimization with model training. This candidate considers
  only a MASS-inspired workflow comparison with fixed model weights; it is not
  a reproduction of the training loop or evidence of benefit in this repository.
- **Hypothesis:** a bounded multi-agent workflow may improve completed-task
  correctness over the current single-agent Codex baseline enough to justify
  its additional cost, time, resources and operator burden, without increasing
  unsafe acceptance or weakening provenance and evidence custody.
- **Dependencies / entry trigger:** retain existing experiment priorities and
  authorized filesystem work without interruption or reprioritization. Before
  designing a run, verify completion of the applicable existing dependencies,
  including the T10 and Hy3/Hy4 prerequisites tracked in the
  [research backlog's execution order](roadmap/RESEARCH_EVALUATION_BACKLOG.md#recommended-execution-order-and-reconciliation).
  Do not infer their completion from historical plans. Once satisfied, a
  separately authorized bounded design task must freeze the protocol, budgets
  and independent deterministic acceptance gates before execution is considered.
- **Controlled comparison to design later:** select 10–20 representative,
  provenance-backed tasks spanning Coin Analyzer / Command Center correctness,
  filesystem boundaries, recovery, and evidence handling. Freeze task IDs,
  exact starting revisions, sanitized fixtures, expected results and executable
  acceptance criteria before either arm runs. Use the same tasks and starting
  state in isolated disposable environments for the current single-agent Codex
  baseline and a fixed MASS-inspired multi-agent workflow. Pin model/version,
  prompts, permissions, tools and environment; predeclare agent count, rounds,
  retries, run order/repetitions and total resource caps. Keep any workflow
  development on separate tasks; no tuning on this frozen evaluation set.
- **Measurements:** report per-task results and paired aggregate counts with
  denominators for completed-task correctness; false ACCEPT (an arm declares
  acceptance but independent gates reject it) and unsafe outcomes; provenance
  and evidence-custody violations; total input/output tokens and tool calls
  across every agent, retry and review; wall time and compute/resource use
  (CPU/GPU time where observable, peak RAM and storage); and operator
  interventions by count, reason and time. Include failures, timeouts,
  abstentions and setup/orchestration overhead. Unobservable provider compute
  is unavailable, not zero; distinguish it from measured local resources.
- **Independent acceptance / explicit threats:** an evaluator outside both
  arms runs frozen deterministic correctness, safety, provenance and custody
  checks against retained outputs and immutable input/output manifests/hashes.
  Participating agents must not edit gates, expected results or the evidence
  ledger. Agent votes, self-scores and shared-model reviewers cannot grant
  ACCEPT. Treat correlated agent errors and self-evaluation bias as explicit
  threats: inspect paired/shared failure patterns and retain disagreements and
  unsupported claims rather than treating consensus as independent evidence.
  Missing or tampered evidence cannot pass; tasks without defensible ground
  truth or deterministic acceptance remain ineligible pending protocol review.
- **Decision / stop conditions:** preregister correctness and resource decision
  rules before execution. Any false ACCEPT, unsafe outcome, provenance or
  evidence-custody violation blocks promotion and requires review. Stop for
  budget overruns, configuration drift, task leakage, protected-data exposure
  or unresolved acceptance evidence. Report ties and inconclusive results;
  10–20 tasks do not establish general safety or authorize adoption.
- **Authority / production dependency impact:** queue record only; research
  and evaluation remain deferred. No new workstream, dependency installation,
  model-weight modification, training/distillation, production change or
  interruption of authorized filesystem work. This entry authorizes neither
  implementation nor experiment execution, commit, publication or adoption.

### Deferred candidate — Microsoft AI Engineering Coach

**Status: DEFERRED — UNAPPROVED evaluation candidate.**

- **Source / classification:** [Microsoft AI Engineering Coach](https://github.com/microsoft/ai-engineering-coach);
  developer productivity / agentic engineering / workflow diagnostics.
  Upstream feature claims remain unverified until independently confirmed.
- **Queue / dependency:** append to the existing post-foundation developer-tool /
  agent-workflow evaluation queue, preserving existing candidates and priorities,
  including Anti Slop, ColGrep-Agent, jgrep, and other approved experiments.
  Phase 1 filesystem/provenance work and applicable governance gates must be
  resolved before separately authorized evaluation execution. This entry creates
  no new workstream and does not interrupt or reprioritize authorized Phase 1 work.
- **Questions:** can it detect inefficient agent workflows, repeated investigations,
  prompt/context-management problems, and actionable session-level feedback?
  Can it identify reusable skills and automation opportunities, and reduce
  unnecessary tool calls, tokens, and engineering time?
- **Frozen comparison:** use 10–20 representative tasks at a fixed repository
  revision, with identical sanitized inputs, success criteria, budgets, and stop
  conditions. Control: existing Codex workflow without the Coach. Treatment: the
  same workflow with permitted, isolated Coach analysis or recommendations.
  Freeze configurations and run order/repetitions before either arm runs; use
  reproducible isolated environments and provenance-backed expected results.
- **Measurements:** completed-task correctness; actionable diagnostic findings;
  false positives and misleading recommendations; token consumption and tool-call
  counts; wall-clock completion time; repeated or unnecessary investigations;
  setup and maintenance overhead; and security, privacy, and governance
  compatibility. Include analysis overhead, failures, and timeouts; report
  unavailable measurements explicitly.
- **Evidence / acceptance:** assess diagnostic quality separately from demonstrated
  workflow improvement. Use independent checks of frozen task success criteria.
  Claim savings only from controlled evidence including overhead, without degraded
  correctness or governance compatibility. Inconclusive results do not authorize
  adoption; tasks without defensible acceptance evidence remain ineligible.
- **Pre-execution gates:** verify upstream source, license, dependencies, and release
  provenance; test compatibility with the actual Codex session format; review
  session-log collection, sensitive-data exposure, and external transmission;
  confirm analysis cannot modify protected workspaces; obtain explicit approval
  for network access, executable installation, and agent permissions; and establish
  reproducible isolated testing before any installation or execution.
- **Privacy / authority / stops:** no telemetry, credentials, session logs, repository
  content, or other sensitive information may be transmitted externally without
  authorization. Stop for unresolved gates, protected-data exposure, protected
  workspace mutation, configuration drift, budget overruns, or unreliable
  acceptance evidence. This queue entry authorizes no installation, execution,
  integration, publication, adoption, or Phase 1 changes.

### Deferred candidate — Matt Pocock's Skills

**Status: DEFERRED / NOT APPROVED FOR EXECUTION.**

- **Source / pin / research date:** [Matt Pocock's Skills](https://github.com/mattpocock/skills);
  `5beb35b040e3de97e54fa9e386d7e42d15c295c2`; 2026-10-21.
- **Hypothesis / baseline:** selective manual adaptation of TDD guidance and review
  rubrics might improve bounded task quality. Compare against existing AGENTS.md
  authority and Superpowers TDD/review practices, including their current overhead.
  No wholesale skill import; automatic commit/publish instructions are unacceptable.
- **Evidence limitations:** previously researched candidate, recorded from the owner
  handoff; upstream contents and licensing were not independently revalidated in
  this documentation task. Coin Analyzer incremental benefits: **NOT MEASURED**.
- **Concerns (needs_validation):** executable instructions can conflict with local
  authority or induce unauthorized actions; examples/prompts could expose private
  material. Verify the pinned license and adaptation/attribution rights, upstream
  maintenance and revision drift, and ongoing manual-review cost. No confirmed
  vulnerability or license compatibility is asserted.
- **Smallest future bounded comparison:** after separate approval, manually compare
  one selected TDD/review excerpt with the existing rubric on one sanitized fixed
  historical diff and its existing acceptance criteria. Record useful findings,
  false positives, missed known defects, review time and adaptation overhead;
  no imported skills, automatic commands, commits or publication.
- **Owner authorization gates:** approve the exact excerpt, license review, task,
  sanitized inputs, reviewer, time cap and preregistered decision thresholds before
  comparison. Any later adaptation needs separate owner approval; AGENTS.md retains
  authority. This record grants no installation, execution, integration or adoption.
- **Success / rejection:** consider a later manual adaptation only for at least one
  independently confirmed useful finding missed by baseline, no missed baseline
  acceptance requirement, zero authority violations, and total time within the
  approved cap. Reject conflicting or automatic commit/publish directions; defer
  ties, duplicated guidance or inconclusive benefit. One comparison cannot establish
  repeated-task adoption value.
- **Reconsideration trigger:** an owner-identified gap in current TDD/review practice
  and explicit authorization for the bounded comparison; no active queue promotion.

### Deferred candidate — context-mode

**Status: DEFERRED / NOT APPROVED FOR EXECUTION.**

- **Source / pin / research date:** [context-mode](https://github.com/mksglu/context-mode);
  `a92cf6a77ac02971fb5fafe2155e5ee229491884`; 2026-10-21.
- **Hypothesis / baseline:** possible tool-output reduction versus current bounded
  commands, targeted reads/searches and manual output limits, while retaining exact
  evidence needed for decisions. Upstream reduction claims do not establish local
  savings. Coin Analyzer incremental benefits: **NOT MEASURED**.
- **Evidence limitations:** owner-supplied prior research disposition and pin only;
  no independent upstream, security, license or performance verification in this
  task. Summaries may omit decisive output; token savings alone are insufficient.
- **Concerns (needs_validation):** review hooks, MCP trust boundaries, routing,
  process execution and environment exposure; retained/indexed output, SQLite
  storage, deletion and teardown; prompt injection and sensitive-data leakage.
  Verify pinned license/dependency rights, maintenance/update provenance and drift,
  and compatibility with evidence custody and AGENTS.md. These are review questions,
  not confirmed vulnerabilities.
- **Smallest future bounded comparison:** only after separate execution approval,
  use an isolated disposable environment and one fixed synthetic tool-output packet;
  compare current output handling with candidate reduction under identical evidence
  questions. Measure retained required facts/exact references, unsupported claims,
  output tokens, latency and setup/teardown overhead; no real repository/session data.
- **Owner authorization gates:** first approve source/license and dependency review,
  isolation design, retention/deletion and teardown review, sanitized inputs, resource
  caps and numeric decision thresholds. Hooks, MCP, SQLite installation, routing
  overrides, process execution and environment exposure are each unauthorized now;
  no such permission is implied by a future comparison proposal. Obtain explicit
  permission for any required capability before execution; integration is separate.
- **Success / rejection:** require 100% recovery of preregistered required facts and
  references, zero unsupported evidence claims or unauthorized exposure, verified
  teardown, and net token reduction after overhead within approved latency/storage
  caps. Reject evidence loss, leakage, routing/authority violations or failed teardown;
  defer no net savings or inconclusive results. Success grants no adoption authority.
- **Reconsideration trigger:** measured output-volume pressure under the existing
  workflow plus owner-approved isolation and retention/teardown plan; remains deferred.

### Deferred candidate — diagram-design

**Status: DEFERRED / NOT APPROVED FOR EXECUTION.**

- **Source / pin / research date:** [diagram-design](https://github.com/cathrynlavery/diagram-design);
  `7a12007b5a4246894f342a2e52e78facbc62eca3`; 2026-10-21.
- **Hypothesis / baseline:** publication-specific static diagrams might communicate
  a reviewed flow more clearly than the existing Mermaid baseline. Mermaid remains
  baseline; no application feature, diagram runtime or publishing workflow is adopted.
  Coin Analyzer incremental benefits: **NOT MEASURED**.
- **Evidence limitations:** owner-supplied prior research disposition and pin;
  upstream behavior, license and local benefit were not independently revalidated
  in this documentation task. A polished diagram is not implementation evidence.
- **Concerns (needs_validation):** verify pinned license, asset/font redistribution
  rights, dependencies, maintenance/update drift and export reproducibility. Review
  rendering inputs and external requests for privacy or script execution. No external
  fonts or scripts without authorization. Require source-backed labels distinguishing
  implemented PWA flows from proposed HTTPS/authentication and recovery; preserve
  offline PWA gates and the historical [4 PASS / 2 FAIL / 18 UNVERIFIED
  assessment](OFFLINE_PWA_POST_MERGE_ACCEPTANCE_2026-10-21.md#5-acceptance-matrix-and-physical-device-checklist).
- **Smallest future bounded comparison:** after separate approval, compare one
  sanitized static publication figure with the equivalent Mermaid figure using the
  same reviewed flow and a fixed set of reader questions. Record factual errors,
  correct reader answers, accessibility/readability, authoring time and export cost.
- **Owner authorization gates:** approve the publication need, exact source/labels,
  licensing/assets, rendering method, offline inputs, reviewer, time cap and success
  thresholds first. Any tool execution, external assets, publication or integration
  requires separate explicit authority. No physical-device acceptance, real-data
  readiness or coin-show readiness may be inferred from the figure.
- **Success / rejection:** require zero incorrect implementation/acceptance labels,
  no omitted safety boundary, all preregistered reader questions answered correctly,
  and a recorded readability benefit within the approved effort cap. Reject misleading
  proposed-as-implemented flows, unauthorized external assets or licensing blockers;
  retain Mermaid for ties or inconclusive benefit. Comparison success is advisory.
- **Reconsideration trigger:** a concrete owner-approved static publication need that
  Mermaid demonstrably cannot meet adequately; no active queue promotion now.

### Deferred candidate — billion-context

**Status: DEFERRED / NOT APPROVED FOR EXECUTION — lowest priority of these four.**

- **Source / pin / research date:** [billion-context](https://github.com/ranxianglei/billion-context);
  `c87185a05a44ecccc225f96f92089e8f309fb1d9`; 2026-10-21.
- **Hypothesis / baseline:** possible long-session context reduction versus existing
  bounded tasks, targeted reads, checkpoints and thread rotation. The researched
  TLS-intercepting Codex launcher design requires independent review; its advertised
  capacity is not evidence of fidelity, safety or Coin Analyzer value.
- **Evidence limitations:** owner-supplied prior research disposition and pin only;
  no independent source/security/license audit or local experiment in this task.
  Coin Analyzer incremental benefits: **NOT MEASURED**.
- **Concerns (needs_validation):** independently review TLS interception, certificate
  trust, credential handling, traffic/log retention and deletion, compression fidelity,
  update provenance/supply chain, pinned licensing and redistribution rights, and
  maintenance burden. Check authority/evidence preservation under compression.
  No confirmed exploit or license compatibility is asserted.
- **Smallest future bounded comparison:** source/design and license review first;
  only under a separately approved protocol, compare compression of one synthetic
  offline transcript with current manual checkpointing on fixed evidence questions.
  Measure exact constraint/reference retention, unsupported claims, size reduction,
  time and review overhead. If offline evaluation requires interception or real
  traffic, stop and redesign or retain deferral; do not expand permission implicitly.
- **Owner authorization gates:** independent security/privacy/license and maintenance
  review must precede any execution decision. Owner must separately approve exact
  inputs, isolation, retention/teardown, resource caps, fidelity thresholds and any
  executable capability. No proxy, certificate, interception or real Codex traffic
  is authorized. Credentials, live sessions and private records are excluded;
  integration/adoption would require a further explicit decision.
- **Success / rejection:** require 100% retention of preregistered constraints and
  exact evidence references, zero unsupported claims or sensitive-data exposure,
  verified deletion, and net reduction after review overhead within approved caps.
  Reject fidelity loss, unresolved trust/license/credential risks or dependence on
  unauthorized interception; defer ties and unmeasured benefit. No result bypasses
  AGENTS.md context thresholds or grants adoption authority.
- **Reconsideration trigger:** a documented unmet need after existing checkpoint/
  rotation practices and lower-risk candidates, plus completed independent review
  and explicit owner approval; keep lowest priority and outside the active queue.
