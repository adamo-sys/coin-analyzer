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
| --- | --- | --- | --- | --- |
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
