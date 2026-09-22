# Post-RC1 consolidation and Pokémon-pile report

## Scope and evidence limits

This report records a non-destructive post-RC1 inventory and one bounded
foundation implementation. It is not authority to remove, merge, change, or
otherwise dispose of any worktree, branch, stash, artifact, or private data.
The inventory command is local-only and its remote freshness is unverified.

The RC1 evidence-extraction repair is preserved by open PR #288:
`codex/rc1-regression-repair-64bca35` at
`520d5d888b6b27d451abcf49db196ce7eb4b1308`, targeting
`release/v1.3.0-rc1-prep`. Its remote tracking ref matched locally when checked.
The PR was open and unmerged; its commit status was pending at the inspection
time. This task did not alter the branch or pull request.

## A. Repository consolidation map

Canonical checkout: `C:/Projects/coin-analyzer`, now on
`codex/post-rc1-consolidation-inventory`, based on `main`
`d388542fda7e034a2edc946cd1f9b5017c067d1e`. The inventory below compares HEAD
to that local base. `MERGED` means the HEAD is ancestry-contained by local main,
not that a directory may be removed. `PRESERVE` and `UNFINISHED` are proposed
human-review categories, not automated actions.

| Proposed category | Branch / HEAD | Worktree / observed state | Evidence and apparent purpose | Recommended disposition |
| --- | --- | --- | --- | --- |
| PRESERVE | `codex/post-rc1-consolidation-inventory` / `d388542` | canonical checkout; tracked-dirty | Active bounded task based on main. | Keep as the eventual canonical workspace. |
| MERGED | `feature/phone-intake` / `bf0e831` | `CA-phone-intake`; clean | Contained by main; Phone Intake. | Retain until owner confirms no active use. |
| MERGED | detached / `1857e337` | `CA-v120-smoke`; clean | Contained by main; v1.2 smoke snapshot. | Owner may later remove after confirming no acceptance use. |
| UNFINISHED | `codex/failure-report-validation-20260914` / `8db76f1` | task worktree; clean; 1 unique commit | Not contained by main; validation follow-up. | Review its one commit before integration/archive decision. |
| MERGED | `codex/foundation-slice1` / `447d574` | task worktree; clean | Contained by main; preflight foundation landed via #238. | Retain until owner confirms replacement by canonical workflow. |
| MERGED | `chore/agent-harness-v1` / `edb3d9d` | agent-harness worktree; clean | Contained by main; contract documentation. | Retain pending owner consolidation. |
| MERGED | `docs/agent-harness-context-budget` / `5ceabce` | nested task worktree; clean | Contained by main; context-budget documentation. | Retain pending parent-worktree decision. |
| MERGED | `feature/command-center-v0.1` / `3d80d1b` | Command Center worktree; clean | Contained by main; observation-only status projection. | Retain pending owner consolidation. |
| MERGED | `feature/command-center-repo-status` / `ce72d87` | Command Center status worktree; clean | Contained by main; detached-state handling. | Retain pending owner consolidation. |
| MERGED | `experiment/gemini-antigravity` / `f6fc6ed` | experiment worktree; clean | Contained by main; Serena/Superpowers pilot. | Retain pilot evidence pending owner decision. |
| PRESERVE | `experiment/gemini-pro-antigravity` / `f6fc6ed` | experiment worktree; tracked-dirty | HEAD contained but local tracked work exists. | Inspect only with explicit owner authority. |
| PRESERVE | `release/v1.3.0-rc1-prep` / `64bca354` | RC1 worktree; clean; 137 unique vs main | RC1 base and PR #288 target are not contained by local main. | Keep unchanged until RC1 disposition is authorized. |
| MERGED | `codex/operator-status-projection` / `56b96de` | operator-status worktree; clean | Contained by main; #236 basis. | Retain pending owner consolidation. |
| UNFINISHED | `chore/phone-photo-benchmark-v1` / `f8a4034` | benchmark worktree; clean; 1 unique commit | Not contained by main. | Review isolated commit before any decision. |
| PRESERVE | `experiment/phone-photo-historical-jurisdiction` / `c0dafb` | jurisdiction worktree; tracked-dirty | HEAD contained but local tracked work exists. | Inspect only with owner authority. |
| MERGED | `docs/phone-photo-v1-decision` / `9371926` | decision worktree; clean | Contained by main; documented decision. | Retain pending owner consolidation. |
| MERGED | detached / `aaf0b8b` | `coin-analyzer-pr199`; clean | Contained by main; runtime-readiness snapshot. | Owner may later remove after confirming no PR inspection use. |
| MERGED | `experiment/phone-photo-v1-results-closeout` / `0a2e53f` | results worktree; clean | Contained by main; results closeout. | Retain pending owner consolidation. |
| MERGED | `tooling/adopted-integrations` / `5aa39a0` | tooling worktree; clean | Contained by main; tooling/security review evidence. | Retain pending owner consolidation. |
| MERGED | `fix/type-design-persistence` / `122c0a4` | type-design worktree; clean | Contained by main. | Retain pending owner consolidation. |
| PRESERVE | detached / `64bca354` | Codex RC1 doctor baseline; clean; 137 unique vs main | RC1 baseline snapshot. | Keep until RC1 outcome is authorized. |
| PRESERVE | `codex/phone-photo-benchmark` / `ad60e98` | temporary publication worktree; tracked-dirty; 1 unique | Unintegrated/dirty benchmark work. | Inspect only with explicit owner authority. |
| PRESERVE | `benchmark/phone-photo-v1` / `b8250b3` | temporary recovery worktree; tracked-dirty | HEAD contained but local tracked work exists. | Inspect only with explicit owner authority. |
| MERGED | `feature/command-center-observation-snapshot` / `c915794` | bounded-state worktree; clean | Contained by main; Command Center snapshot. | Retain pending owner consolidation. |

Registered stashes are both **PRESERVE pending human review**: `stash@{0}`
(`5d46127`, evaluator-v2 recovery before RC1 repair) and `stash@{1}`
(`34e1b97`, Sprint 20 local learning directories). Their contents were not
inspected.

### Proposed safe consolidation sequence

1. Keep `C:/Projects/coin-analyzer` as the sole long-lived checkout and begin
   normal work there on one named branch at a time.
2. Keep RC1-prep, RC1 doctor, stashes, every dirty worktree, and every
   non-contained HEAD untouched until an owner reviews their distinct evidence.
3. Review the two clean uncontained one-commit worktrees individually; decide
   integration, archival preservation, or later disposal only then.
4. For each clean ancestry-contained worktree, ask its owner whether an active
   task, PR inspection, or local artifact still depends on it; only after that
   explicit answer may a separate authorized cleanup task remove it.
5. Re-run the read-only inventory after each owner-approved change. Do not batch
   deletions, prune refs, or delete stashes.

## B. Pokémon master backlog

| Order / candidate family | Existing overlap and decision | Dependency / evidence needed |
| --- | --- | --- |
| 1. Foundation and execution discipline | **IMPLEMENTED:** this read-only inventory extends the merged preflight foundation; agent contract/runbook already provide the authority model. | Validate repeatable factual Git observation without mutation. |
| 2. Context and repository memory | **HARVEST/DEFER:** deterministic local metadata retrieval and RAG contracts already exist; no project evidence supports mandatory codebase-memory, Augment, Graft, or OpenViking adoption. | Demonstrate a specific retrieval gap using sanitized tasks and measurable navigation churn. |
| 3. Durable execution | **DEFER:** Stage 7-11 contracts provide bounded execution/review experiments; they deliberately exclude autonomous retries and broad orchestration. | Merge/green prerequisite stages and retained reliability evidence. |
| 4. Observability and provenance | **HARVEST:** Phoenix is an optional local, metadata-only bridge; provenance/evaluation contracts already exist. | Repeat local traces proving useful signal without package, prompt, or collection leakage. |
| 5. Routing/resource/token/cost governance | **BAKE-OFF:** existing task contracts and context budgets are policy foundations; Headroom, Context Mode, OmniRoute, and DeepSeek Harness have no retained project evaluation. | A bounded scorecard showing decision quality, cost, intervention burden, and reversibility. |
| 6. Security/credentials/policy | **IMPLEMENT queued bounded evaluations:** T10 diff-aware Semgrep, T11 SBOM/attestation, and T12 Harden-Runner audit are already dependency-ordered in the tooling roadmap. OPA is premature without a concrete enforceable policy gap. | Advisory pilot signal, false-positive rate, and no new credential/cloud dependency. |
| 7. Specialized agents | **DEFER:** Stage 11 strategy roles are architecture-frozen pending Stage 10 reliability; agency-agents, PraisonAI, AgentConnect, OpenWorker, and OpenClaw duplicate/expand authority prematurely. | Stage 10 gates and proof that the fixed two-candidate boundary is insufficient. |
| 8. Larger architecture/data platforms | **DROP/DEFER:** Temporal, MatrixOne, SurrealDB, Cloud in a Bottle, Kepler ADE, and similar platforms lack an evidenced local product requirement and add lock-in/operations. | Concrete local-first capability gap, exit strategy, threat model, and bounded evaluation. |
| Cross-cutting research patterns | **HARVEST:** Serena/Superpowers are OPTIONAL positive; GitHub Spec Kit and Karpathy-style guidelines remain patterns, not infrastructure. | Repeated measured task evidence beyond process ceremony. |
| Browser/research and security tooling | **HARVEST:** Playwright MCP is a bounded public, unauthenticated advisory pilot; existing Gitleaks, CodeQL, dependency audit, and action pinning remain authoritative/established. | Caller-supplied research question plus provenance; no trust-chain entry. |

Duplicates are intentionally collapsed: command/agent policy belongs in the
existing task contract and preflight foundation; repo-memory candidates remain
one retrieval problem; orchestration frameworks remain one durable-execution
problem; and external security platforms remain evaluation candidates rather
than additive systems.

## C. Tonight's implementation

**Selected improvement:** `tools/task-state.py inventory`.

It outranked alternatives because it builds on merged local preflight work,
solves the immediate repeated-worktree evidence gap, adds no dependency or
authority, is reversible, and provides a safe input to future consolidation
decisions. A document-only map is less reusable; Command Center integration
would couple a read-only Git fact source to a wider interface prematurely.

**Bounded files:** `tools/task-state.py`, `tests/test_task_state.py`,
`docs/CODEX_WORKFLOW.md`, this report, and the approved design/plan artifacts.
The command is deterministic, local-only, and observation-only. It reports
path/branch-or-detached/HEAD/tracked-dirty/base relationship facts, does not
print changed paths, and uses a process-local `safe.directory` setting only when
the sandbox needs to inspect another registered worktree. It never persists
that setting or mutates Git state.

**Validation:** focused synthetic tests passed; a canonical `inventory --base
main` smoke passed; Ruff E9 passed; targeted Pyright reported 0 errors, 0
warnings, and 0 informations; and `git diff --check` passed. Full root unittest
discovery also completed successfully with `TEMP`, `TMP`, and `TMPDIR` set to an
ignored workspace-local directory. Independent read-only review returned **PASS
WITH NOTES**: two Important findings were corrected in the same bounded pass
(locked/prunable worktree metadata support, and `safe.directory` only after a
dubious-ownership failure); one Minor malformed-porcelain hardening suggestion
was deferred without changing the approved scope.

## D. Next action

Run exactly one bounded **T10 diff-aware Semgrep advisory evaluation** against
changed production Python, using the existing engineering-tooling roadmap's
advisory-first, evidence-recording contract. Do not begin it in this task.
