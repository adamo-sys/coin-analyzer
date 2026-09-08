# Backlog reconciliation — 2026-09-08

Initial audited main: `b9e976a1c0941936555ea57ea00bf45cd7d991ff`. This dated record
supersedes older current-status labels, not architecture contracts or historical
evidence. The pre-change reconciliation and raw audit snapshots are retained in
the local audit workspace. No private corpus, notes, backup or photographs were
used to decide completion.

Concurrent update: #217 was merged by `adamo-sys` at 2026-09-08 21:57:08 UTC
as `5af6bba389bb3afa0e98cf6cca49ef2d3cb6de94` before the audit's closure request.
This audit did not merge it. PR #219 incorporates that main and removes the
case-colliding uppercase template while preserving the lowercase template and
useful review wording. #215 was closed with verified completion evidence.

## Finish now / bookkeeping

| Item | Evidence and disposition |
| --- | --- |
| Misleading mutation evidence | PR #218 completes the existing uncommitted local repair. Main suppressed capture failures and could print “No surviving mutants.” The repair retains exit codes/output, distinguishes COMPLETE/INCOMPLETE/UNAVAILABLE, and leaves mutation policy advisory. Ten focused capture tests passed; no mutation execution is inferred from mocks. |
| #215 immutable action SHAs | Already implemented by #216: five files, 23 reference replacements. All six distinct action/tag mappings verified from upstream Git refs. actionlint 1.7.12 and offline zizmor 1.30.0 pass; authoritative main workflows are green. Acceptance is satisfied independently of OpenCode. |
| #217 duplicate template | Superseded addition, but concurrently merged before closure. Remove `.github/PULL_REQUEST_TEMPLATE.md` in #219 and retain one lowercase template with the useful exact-head review/advisory wording. Do not claim this audit closed #217 without merge. |
| #52 checklist drift | Security policy and PR template exist; dependency-audit CI and canonical developer-version inventory exist; atomic_json.py joined bounded Pyright in #212. Update completed bookkeeping while keeping the umbrella open. |
| T6/T8/Stage 11 stale status | T6's completed evidence is in MUTMUT_PILOT.md; #213 records T8; #114 merged Stage 11 runtime/tests. Correct status labels, preserving reusable run checklists. Reviewer/Stage 11 pytest suites: 24 passed. |
| Sprint/product status drift | Sprint 8 completed in 94495f3/a356810; Sprint 20 merged in ad2e861. Later desktop load/save/cancellation acceptance is in #192–#198; runtime readiness/Doctor in #199/#200; AI audit seam in #205/#206/#208. Old planning headers and historical pending hashes must not drive duplicate work. No new native Tk or release claim. |
| Benchmark v2 pre-run wording | The README's “no visual provider has been run” was stale. VISUAL_IDENTIFICATION.md already records the prospective result and failed fusion evaluation. Correct the README without broadening those claims. |
| #216 OpenCode local loop | Actual OpenCode 1.18.29 run completed using opencode/nemotron-3.5-lightning-free, with tools denied and exact public Git-object contents supplied. Returned MERGE WITH NONBLOCKING FINDINGS. Record two inaccurate observations and nonliteral verdict formatting; this is retrospective advisory evidence, not a protocol-perfect gate. See OPENCODE_REVIEW_LOG.md. |

## Blocked / incomplete evidence

| Item | Exact remaining work |
| --- | --- |
| #204 OpenAI SDK floor | Head 49c111a7c6687f806d8813dcb6dce08debd8363f has green CI, but moving >=1.73.0 to >=3.8.0 lacks dedicated minimum-version compatibility evidence. Test actual SDK 3.8.0 collection-assistant and visual-provider request/response/error contracts without provider calls, examine supported Python and lockfile consistency, document the reason for dropping the old floor, then obtain merge authorization. Callable-surface smoke and mocks alone do not prove this. Remains open. |
| T9 partial local coverage experiment (#213) | At b9e976a, retained Windows baseline venv log: 5,407 tests, 26 skipped, passed. Instrumented run: 5,407 tests, 26 skipped, one Hypothesis slow-input health-check error. Earlier non-venv runs lacked Hypothesis. No successful coverage report, changed-line report or defensible overhead comparison exists. Resume the planned controlled Ubuntu pilot, preserving failed logs. No health-check weakening or coverage gate in this closeout. |
| Real-world acceptance corpus | No frozen real manifest/corpus. Independent identity/action review, rights/provider eligibility and real second-capture metadata for cases 028–030 remain prerequisites. Local completed-review filenames are not proof of accepted corpus readiness. Preserve protected assets. |
| Local Collector Work Queue | Reviewer-A checkout has unpushed dbf6de6 (projection) and c98dffc (GUI), plus uncommitted architecture/Sprint20 changes. Do not silently promote mixed alternate-history work or pending architecture amendments. It needs a separate contract/diff/acceptance reconciliation. Original files remain intact. |

## Intentional future work

- #137: Serena and Superpowers individual versioned trials, scorecards and conditional
  combined trial remain unexecuted in the recorded evidence. Setup is not completion.
- #213: T9 controlled Ubuntu measurement, T10 diff-aware Semgrep, T11 release
  attestations/SBOM, T12 runner audit, Pacify-X and pxpipe remain scoped research.
- #52: evidence-led type/lint ratchets, coverage policy, auto-merge decision,
  recurring allowlist/privacy review, measured caching/CI improvements and release
  automation remain future work or standing rules. Do not turn policy checkboxes
  into invented cleanup tasks.
- #93's foundation completion remains bounded: vector/graph infrastructure and
  composite confirmed-observation identity adapters retain explicit architecture
  gates. Later specialist seams do not authorize a general agent system.
- Product/backlog ideas (grading, dealer, mobile/cloud, reference content, Soup,
  additional model/OCR experiments) retain their evidence and approval gates.
  The visual benchmark's bounded 50% identity result and failed 45% fusion result
  do not establish representative collector-photo performance or production fusion.
- The earlier local ROI audit's load failure, visual responsiveness and launcher
  findings are addressed by #192/#193/#199. Its corpus, packaging, reference-data,
  navigation and valuation proposals remain separate future scope, not new
  implementation authority from an old report.

## Branch and marker audit

At baseline the clone had 202 remote refs including origin/HEAD: 163 were
ancestors of main; 28 additional refs mapped to merged PRs, including squash
history. They are completed branch residue, not 191 new engineering tasks.
Seven refs mapped to closed unmerged PRs (#28, #61, #78, #83, #105, #138, #145);
retain their historical disposition rather than reopening automatically. Two
open PR refs (#204/#217) and two unassociated refs remained.

The unassociated `feat/self-improvement-foundation-v1-copy` is an old foundation
copy, superseded in purpose by merged #90; retain until patch-equivalence review
before deletion. `review/batch-02-reviewer-a` contains mixed historical/review
work and the dirty local work described above. No branch or worktree was deleted.
The original uncommitted mutation repair is preserved after being completed in
an isolated branch. Repository-wide TODO/FIXME search on main returned no matches.

## Main health and next step

Main Tests run [34213093279](https://github.com/adamo-sys/coin-analyzer/actions/runs/34213093279)
passed all required jobs and optional OpenAI smoke. Root discovery ran 5,407
tests on each platform: Ubuntu 8 skipped, Windows 17 skipped, no failures/errors.
Quality Advisory [34213093202](https://github.com/adamo-sys/coin-analyzer/actions/runs/34213093202),
CodeQL 34213093260 and Dependency Audit 34213093189 succeeded. Whole-repo
Pyright remains 3,189 errors / 1 warning over 691 files; only 11 cleaned modules
are blocking. The active Protect main ruleset retains five required checks,
PRs, resolved review threads, no force pushes and no bypass actors.

Two observed main job-runtime samples (34175279374 and 34213093279): Ubuntu
65/67 seconds, Windows 186/184 seconds. These are small-sample total job times,
not test-only duration or a stable performance baseline. No speculative CI
optimization follows from them.

Recommended next engineering task: finish T9's controlled Ubuntu coverage/diff
pilot with matched test selection and explicit overhead/failure evidence. The
larger product evidence priority remains owner-authorized corpus completion.
Merge readiness for this closeout and #218 remains subject to their exact-head
CI and explicit PR merge authorization under AGENTS.md.

The actual advisory mutation workflow on #218 completed successfully:
[34283698240](https://github.com/adamo-sys/coin-analyzer/actions/runs/34283698240),
exact head `e03c603d6771ae46775e9173c9a6dd322a6c894e`. This execution is separate
from the mocked capture tests; the retained artifact/report is its integration
evidence. It changes no mutation or promotion authority.

Local validation caveat for #218: root discovery ran 5,417 tests. The sandbox
run had nine Doctor directory-handle failures (26 skips); the host rerun cleared
those but hit a Hypothesis slow-input health check and a temporary launcher
executable cleanup access error (two errors, 26 skips). The affected Doctor
suite passed separately on the host; the property/runtime suites also passed
on focused host recheck without source or test changes. Do not describe either
full local run as green. Exact-head GitHub Windows/Ubuntu regression, Ruff,
Gitleaks and bounded Pyright passed on #218, providing authoritative validation.
