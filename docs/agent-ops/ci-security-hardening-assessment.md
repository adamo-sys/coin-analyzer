# CI security hardening assessment

## State and authority

- Repository: `adamo-sys/coin-analyzer` (public, verified through GitHub metadata).
- Worktree: `C:/Users/adamo/.codex/worktrees/ci-policy-security-hardening/coin-analyzer`.
- Branch: `fix/ci-policy-security-hardening`.
- Verified task base and unchanged HEAD: `f6ead4f740e225e7b2234626640becd9697f6cac` (current main at task start).
- PR #391: open, head `3e1d80bebd225b2a4fb370499b87659b2ac62722`; not modified.
- Primary checkout preserved at `fb03b892a295bff7fd7ff92cd1232710b5f57bca`, branch `fix/ci-privacy-hardening`, with unrelated tracked modifications to `benchmarks/bakeoff-v1/RUNBOOK.md` and `capture_import/desktop_import_pipeline_selection.py`.
- Exact proposed file set: `.github/workflows/tests.yml`, `.gitleaks.toml`, `tests/test_ci_security_boundaries.py`, `TESTING.md`, this assessment.
- Publication: uncommitted, unstaged; no push, PR, comment, merge, or workflow dispatch.
- Human clarification authorized full-history CI scanning despite possible protected-object transfer and enabling `[extend] useDefault = true`. Local protected-data access remains excluded.

## Contract and execution plan

GOAL: Correct confirmed blocking Tests policy violations and deliver evidence-backed boundary classifications and a prioritized backlog.

IN SCOPE: The five paths above; read-only inspection of six workflows, relevant governance, scanner/checkout upstream source, and historical grader boundaries; synthetic checks and one High-reasoning independent review.

OUT OF SCOPE: PR #391 implementation, production behavior, protected benchmark evidence, private material, historical grader/model execution, new dependencies, unrelated fixes, commits/publication.

PROTECTED BOUNDARIES: Preserve existing checkouts and local edits; preserve local-first behavior and blocking security checks. Do not treat scan success as data confidentiality. Transfer permission is limited to the CI full-history security scan.

ACCEPTANCE GATES: Structural workflow/privacy guards, synthetic Git selection, shell syntax/failure checks, focused Ruff and diff checks, independent review, then human acceptance. GitHub CI remains authoritative and is not run for this unpublished snapshot.

STOP CONDITIONS: Identity/base mismatch, policy contradiction, protected access outside clarified CI authority, weakening security, material credential exposure, scope expansion, unresolved validation/review blocker, or context/quota limits.

Plan: inspect policy and pinned dependencies; demonstrate recurrence with failing/static mutations; correct the CI recipe; validate synthetic boundaries; classify historical execution read-only; obtain one bounded review; stop for acceptance. No speculative backlog implementation.

## Confirmed changes and evidence

1. **Embedded artifact publication:** Before, the pinned Gitleaks wrapper defaulted to SARIF upload despite no explicit upload step. GitHub metadata for PR head confirms `gitleaks-results.sarif` in runs [38189195291](https://github.com/adamo-sys/coin-analyzer/actions/runs/38189195291) and [38189259053](https://github.com/adamo-sys/coin-analyzer/actions/runs/38189259053). Contents were not read. After, direct CLI invocation has no report path or publishing wrapper. Failure remains visible through job status and aggregate logs. This corrects the implementation; deployed behavior remains unverified.
2. **Event-limited scan:** Pinned wrapper chooses an event commit interval, excluding merges/other parents, despite full-depth checkout. After, the scanner explicitly selects `--full-history --all --root -m --no-ext-diff --no-textconv`, independent of event type. Scope is fetched refs plus event commit and their reachable history, not dangling/deleted refs, other forks, or all server objects.
3. **Detection configuration:** Existing `.gitleaks.toml` defined an allowlist only. Pinned Gitleaks loads that file as the configuration, without implicit default extension; translating it supplies zero configured rules. After, built-in rules are explicitly extended. Existing fixture allowlists remain unchanged. Detection was not proven by running a scanner locally.
4. **Objects and credentials:** Checkout remains sparse and does not persist credentials. Because the pinned checkout uses `blob:none` for sparse checkout, a separate read-token fetch uses `--refetch --no-filter` for all branches/tags and the event SHA. Shallow/missing object checks fail closed before scanning. The auth header is masked, process-local, and unset; scanner step receives no credential environment. Object inventory is temporary and removed on successful preparation. It is never published.
5. **Scanner provenance:** Same version as the previous wrapper default, 8.24.3. CI downloads the existing security tool and verifies SHA-256 `9991e0b2903da4c8f6122b5c3186448b927a5da4deef1fe45271c3793f4ee29c` before extraction. Checksum came from the published release checksum text; no binary/dependency was installed locally. Pinning integrity does not authenticate a compromised original release.
6. **Guards:** New guard module is explicitly included in the pre-discovery boundary check and remains discoverable by unittest. The previous wrapper fixture failed the new policy requirement before correction. Mutation fixtures demonstrate rejection of uploads, wrapper replacement, limited scan options, permission expansion, skips, suppressed scan errors, and direct/indexed/aggregate secret expressions. Adding secret fixtures initially exposed a generator escaping defect (8 failing subtests); correcting it restored the 17-test pass. A later aggregate-secret case produced 4 failures before the regex was widened, then all 17 tests passed again. These failures were resolved before the reviewed final snapshot.

Upstream evidence (exact inspected revisions): [wrapper scan and embedded uploads](https://github.com/gitleaks/gitleaks-action/blob/e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e/src/gitleaks.js), [wrapper event/default-version handling](https://github.com/gitleaks/gitleaks-action/blob/e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e/src/index.js), [scanner config loading](https://github.com/gitleaks/gitleaks/blob/v8.24.3/cmd/root.go), [rule extension](https://github.com/gitleaks/gitleaks/blob/v8.24.3/config/config.go), [Git selection](https://github.com/gitleaks/gitleaks/blob/v8.24.3/sources/git.go), [checkout filtering](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/src/git-source-provider.ts), [release checksums](https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_checksums.txt).

## Boundary assessment

Classifications apply only to inspected configuration/source. A corrected recipe is not deployed evidence. Mixed classes retain the unresolved classification rather than declaring overall safety.

| Failure class | Classification | Evidence and limits |
| --- | --- | --- |
| 1. Unintended uploads | CONFIRMED FINDING, corrected in snapshot | Embedded SARIF upload confirmed by pinned source and artifact metadata. Six workflows' explicit upload paths satisfy existing privacy guards; advisory report contents and arbitrary shell publication remain unverified. |
| 2. Sensitive logs | UNVERIFIED / INSUFFICIENT EVIDENCE | Scanner now non-verbose, fully redacted, aggregate logs only. No sensitive logs were inspected. Other test/tool diagnostics, paths, exception output, and upstream logging are not proven confidential. |
| 3. Token permissions | VERIFIED SAFE within inspected Tests scope | Tests declares only `contents: read`, no job overrides. Other workflows are read-only except CodeQL's existing `security-events: write`, expressly retained by policy; reachability/adequacy is not comprehensively proven. |
| 4. Untrusted PR credentials | VERIFIED SAFE within inspected Tests configuration | `pull_request`, no `pull_request_target`/`workflow_run`, no inherited secrets or write permission. Scanner receives no token; fetch receives only read token, executes no candidate Python. Actions can access the generated read token implicitly; this is not token absence or sandbox proof. |
| 5. Mutable dependencies | CONFIRMED FINDING | E7 workflow uses `actions/checkout@v7` and `actions/setup-python@v5`. Other inspected action uses are SHA pinned. Pip `.txt` installs and upgrades still resolve mutable transitive versions. Existing scanner binary now checksum pinned and its wrapper/cache removed. |
| 6. Secret detection completeness | CONFIRMED FINDING, partly corrected | Missing default rules corrected. Existing global allowlist excludes all contents of two test files, not merely the stated fixture identifier; remains a blind spot. Heuristic detection cannot prove absence of credentials. |
| 7. Git history coverage | CONFIRMED FINDING, corrected recipe; live result unverified | Old wrapper limits event interval/parents. New command covers fetched refs and event SHA, including root/merge patches; static and synthetic selection evidence only. Unreachable objects, deleted server refs, and other forks remain outside scope. |
| 8. Object hydration | CONFIRMED FINDING; exact past transfers UNVERIFIED / INSUFFICIENT EVIDENCE | Pinned checkout selects blob filtering; Git patch scans and grader object reads can request missing blobs. New security preparation deliberately fetches complete objects under explicit human authorization. No protected object contents or past transfer logs examined. |
| 9. Cache poisoning | UNVERIFIED / INSUFFICIENT EVIDENCE | setup-python pip caching in five workflows; cache service/ref scoping, restored contents, and package integrity not independently audited. Old wrapper's binary cache removed. No demonstrated cross-trust cache exploit. |
| 10. Network/provider execution | UNVERIFIED / INSUFFICIENT EVIDENCE | CI intentionally contacts package registries/GitHub/audit endpoints and has no egress deny policy. OpenAI smoke creates a dummy-key client and checks methods; no direct model call in inspected recipe. Whole-suite transitive/historical code not proven offline. |
| 11. Historical grading outside authority | UNVERIFIED / INSUFFICIENT EVIDENCE for a policy violation | Root discovery includes all 24 grader methods. Policies permit full suite and runbook lists grader unit tests; no express repository-wide ban found. This task's local no-run restriction obeyed. See classification below. |
| 12. False confidentiality claim | VERIFIED SAFE for revised documentation; actual confidentiality UNVERIFIED | TESTING already distinguishes sparse materialization/object transfer/report publication. This assessment and updated docs explicitly retain that distinction. Passing CI has never been used here to establish protected-data confidentiality. |

## Historical grader classification (read-only)

Inspected `tests/test_bakeoff_v1_grader.py`, `tools/bakeoff_v1_grader.py`, candidate-state validation, public task declarations, `bakeoff-v1-spec.md`, operator runbook, TESTING, AGENTS, and SECURITY. Historical Git test blobs were not opened or executed. No benchmark records, images, collection files, or contestant outputs were accessed.

All 24 methods share `setUpClass`, which creates a temporary historical candidate. Thus even provenance-only methods depend on object materialization; they are not wholly synthetic test runs. The helper copies bounded commit/tree metadata and selected source blobs from two frozen task histories, forbids an explicitly excluded image blob and `test_coins/` path blobs, sets skip-worktree bits, and uses no candidate remote/alternates. This bounds the candidate object store; it does not prove the CI source clone never received protected objects. Git object reads in a partial source clone may hydrate implicitly. Missing historical commit availability on shallow CI remains a runner-dependent question.

Several methods call real `grade_run`, `collect_grading_evidence`, or immutable reference acceptance against temporary candidates. They are existing regression tests that perform historical grading internally; they are not model contestant trials or grading of retained private benchmark runs. They read public tracked benchmark controls; protected-control mutation tests write a synthetic `{}` only inside temporary candidates. Inspected grader commands execute frozen local checks and historical test bytes, with output digests and five-second timeouts. The task packets forbid network/provider access, but the grader subprocess recipe is not a network sandbox. Current expected test sources show no direct provider call; uninspected historical bytes/transitive imports cannot be declared offline by inference.

Authority: TESTING mandates full CI discovery; the bake-off runbook explicitly lists the grader unit suite. AGENTS excludes uncertain/private inputs from CI and forbids unauthorized protected access. No inspected policy expressly prohibits all these existing unit methods. The temporary GOV-01C task restriction is not inferred to be repository-wide. Actual protected-object transfer and historical/transitive egress remain UNVERIFIED, with separate authorization needed for deeper validation. Do not disable the tests as an assumed policy correction.

Exact method inventory (source names, not execution evidence):

- `test_grade_run_rejects_missing_external_corpus_seal`
- `test_historical_candidate_is_object_bounded_and_excludes_local_only_images`
- `test_independent_execution_controls_false_pass_claim`
- `test_v11_grade_run_accepts_frozen_dirty_candidate_without_an_ending_commit`
- `test_v11_grade_run_rejects_forged_recorded_candidate_state`
- `test_claimed_pass_cannot_override_unavailable_frozen_check`
- `test_nonexistent_end_and_unrelated_end_are_invalid`
- `test_raw_evidence_has_no_authoritative_public_grading_entry_point`
- `test_private_evaluator_rejects_incomplete_or_substituted_evidence`
- `test_private_evaluator_rejects_wrong_run_or_candidate_identity`
- `test_ledger_rejects_abbreviated_ending_sha`
- `test_timed_out_check_is_never_success`
- `test_reference_oracle_identity_is_git_blob_bound_for_both_tasks`
- `test_synthetic_test_provenance_cannot_satisfy_expected_implementation`
- `test_outside_candidate_implementation_cannot_satisfy_expected_provenance`
- `test_immutable_oracle_rejects_an_expected_module_resolved_only_from_outside_candidate`
- `test_weakened_candidate_test_cannot_turn_broken_implementation_into_success`
- `test_deleted_candidate_test_cannot_turn_broken_implementation_into_success`
- `test_renamed_candidate_test_cannot_turn_broken_implementation_into_success`
- `test_trivial_candidate_test_cannot_substitute_for_immutable_oracle`
- `test_reference_candidate_test_change_is_permitted_and_non_reference_equivalent_implementation_can_pass`
- `test_protected_benchmark_control_mutation_is_invalid`
- `test_z_broken_candidate_fails_immutable_task_packet_oracle`
- `test_provenance_changes_canonical_evidence_identity`

## Validation evidence and limitations

- Existing configured Windows interpreter: `C:/Projects/coin-analyzer/.venv/Scripts/python.exe`; existing PyYAML 6.0.3. No dependencies installed.
- `python -B -m unittest tests.test_ci_security_boundaries tests.test_repository_privacy_boundaries -v`: **17 passed** (8 new security, 9 existing privacy checks). These include a harmless temporary Git repository; no historical grading.
- `python -m ruff check tests/test_ci_security_boundaries.py --select E9,F`: **passed**.
- `git diff --check`: **passed** at validation snapshot. Separate trailing-whitespace/final-newline checks cover all five tracked and new paths. Final Ruff rerun initially hit a sandbox cache-write denial; authorized rerun passed.
- YAML: existing strict structural loader checks all six workflows, rejects duplicates/aliases/ambiguous mappings; new Tests assertions cover triggers, job permission overrides, scan sequence, checkout, reporting, and error handling.
- Bash 5.3.9 via existing Ubuntu WSL: **3 syntax checks passed**, **9 synthetic shell cases passed** using temporary stub commands: object preparation success, fetch exit 7, shallow history, missing object; scanner exits 0/2/3; download exit 6; checksum exit 9. No fetch, curl, actual scanner, secrets, or protected objects were used by those cases. First temporary harness attempt produced CRLF and failed Bash parsing; rerun with LF passed. That was a harness defect, not a workflow failure.
- Real Git history selection test includes root, deleted text, side branch, unmerged branch, and conflict-resolution merge text; limited `HEAD^..HEAD` misses the unmerged marker.
- Guard limits: exact inspected scanner recipe; object/download scripts have required-control assertions rather than a general shell analyzer. This is not adversarial tamper resistance against arbitrary rewritten scripts or changed tests.
- Not run: real Gitleaks binary, full repository history scan, actual authenticated GitHub fetch, actionlint (unavailable), whole regression suite, bounded production Pyright, CI on this uncommitted snapshot, historical tests, model contestants, protected-data processing. Full suite would violate this task's historical no-run boundary; production code was unchanged.
- PR #391 metadata: current inspected Tests run 38189259053 shows all seven relevant check names successful (Ruff, Gitleaks, Pyright, SDK smoke, Windows/Ubuntu tests), with CodeQL/quality successes separately. This proves status for that PR head only. Earlier check metadata contains a status/conclusion inconsistency; no merge decision uses it. Success does not resolve policy violations or validate this patch.

## Independent review

**PASS WITH NOTES** from independent High-reasoning agent `/root/ci_security_review` for the bounded uncommitted snapshot. No blocking finding in the inspected workflow/configuration. Reviewer verified branch/base/HEAD, reviewed the five authorized paths, existing privacy guards, and contract/runbook. The same reviewer was asked to conclude from retained evidence after prolonged exploration; no second independent review was launched.

Reviewed core SHA-256 fingerprints:

- `.github/workflows/tests.yml`: `9A7AD255BD59DC71F29D722CA3D45237E7571CE068B4D805AC93D74DABCBC3B1`
- `.gitleaks.toml`: `11D30F325AB83F1D36D961D3A85901E017CFBB0BC5A1A9656FB637B687C6A34A`
- `tests/test_ci_security_boundaries.py`: `D46E5B50577E091309E5F40E125804729B5E0A101743B0D8626EEA35641ECE59`
- `TESTING.md`: `13FBAB4FCAF71E2E3B30E7DF1E86A26C6919FE39615331FF89C8445523B98734`

Nonblocking notes and disposition:

1. **Medium, tests/test_ci_security_boundaries.py:78:** preparation scripts use required-substring checks. Reviewer demonstrated an in-memory mutation adding `exit 0` after `set -euo pipefail` passes that guard, bypassing preparation. Current workflow has no such bypass. Disclosed limit, not an unsafe current recipe; defer a small normalized-recipe comparison plus early-exit/failure-suppression mutations. This guard follow-up requires separate authorization after acceptance; it is not an exhaustive shell analyzer.
2. **Medium, .gitleaks.toml:11:** two existing whole-file exemptions remain a detection blind spot. Already in backlog item 2; no exception policy changed silently.

Independent evidence: seven static tests passed. The synthetic-history test encountered sandbox temporary-directory permission errors; an escalated rerun was cancelled. Reviewer therefore claims no independent eight-test pass. Implementer final 17-test, Ruff, whitespace, and shell-stub results remain separately attributed. No actual scanner/authenticated fetch/current CI/historical grading/protected-data inspection occurred in review. Wider historical inventory was not independently re-audited. Acceptance concerns the bounded correction, not deployment or protected-data confidentiality.

This assessment was updated after review only to record the verdict, evidence attribution, and deferred guard finding; reviewed workflow/config/test/TESTING content remains frozen.

## Dependency-ordered hardening backlog

| Order / finding and evidence | Severity / practical exploitability | Boundary | Minimal next correction / risk reduction | Cost | Blocks #391? | Separate authorization? |
| --- | --- | --- | --- | --- | --- | --- |
| 1. Deploy this correction; old wrapper publishes SARIF, limits history, and has zero configured rules | High security-control failure; exploitation requires an actual secret and publication contents are unknown | Source/history to CI and reporting | Human accept snapshot, authorize publication, run current Windows/Ubuntu/static/security gates; establishes an effective blocking scan and removes artifact publisher | Small publication/check work; history scanning may add runtime | Yes: confirmed policy HOLD until corrected deployed evidence | Yes, commit/push/PR and any merge each outside present grant |
| 2. Narrow existing `.gitleaks.toml` global path exemptions for `test_processed_artifact_snapshot.py` and `test_workflow_execution.py` | Medium blind spot; a secret in either file is ignored under current global allowlist | Scanner input to findings | Replace whole-file exclusions with evidence-backed exact fixture exception, validate harmless canaries and known fixture behavior; avoids silently masking unrelated credentials | Small; requires actual scanner synthetic tests | Recommend before claiming comprehensive scan; owner determines whether additional HOLD | Yes: exception-policy change; not implemented |
| 3. Resolve protected history disposition; SECURITY forbids uncertain corpora while Git transfer remains unproven | High privacy impact if protected blobs are reachable/transferred; reachability and exact transfers not verified here | Git server/source clone to runner | Separate authorized metadata/transport investigation and owner decision on historical exposure; do not read blobs or rewrite history without exact authorization. Document intended retained-history boundary | Medium investigation; remediation cost unknown | Human decision; current transfer authorization does not establish confidentiality | Yes: protected evidence/history operations require exact grant |
| 3a. Strengthen preparation-script regression guard; reviewer early-exit mutation bypasses substring assertions | Medium validation blind spot; requires a future script change, no current bypass | CI recipe to local validation claim | Compare normalized preparation recipe and add early-exit/failure-suppression fixtures; makes ordinary recurrence fail deterministically | Small; after current correction, before claiming stronger guard coverage | No current workflow blocker per review | Yes, new bounded follow-up after acceptance |
| 4. Pin E7 action tags | Medium supply-chain risk; mutable tags are confirmed, compromise is not | Third-party action to runner/read token | Pin approved checkout/setup-python SHAs and synthetic pin guard; reduces tag-movement exposure | Small, high ROI after blocking fixes | No known #391 blocker | Yes, separate workflow scope |
| 5. Establish historical regression egress/object boundary | Medium uncertainty; historical subprocess code is real execution, no isolation proof | Frozen code/Git source to candidate/runner/network | Authorized synthetic-only transfer and egress characterization, then smallest explicit policy or isolated job if evidence warrants. Preserve tests until authority is resolved | Medium; stop if metadata suffices or protected access is required | No express ban found; conditional on new evidence | Yes; no historical grading permitted in current task |
| 6. Validate advisory report provenance/log minimization | Medium possible disclosure; allowed paths do not prove report contents | Tool output to public logs/reports | Inspect generators using synthetic diagnostics; assert approved fields/paths, minimize raw text where required by policy; do not download existing possibly sensitive outputs by default | Small to medium | No demonstrated content breach; SARIF publication addressed by item 1 | Yes, reports/generators outside bounded change |
| 7. Evaluate pip cache and dependency integrity | Medium supply-chain uncertainty; mutable transitive installs and shared cache tooling exist, exploit unproven | Package/cache service to trusted job | First read-only documented cache scoping/integrity check; use existing lockfiles in one separate compatibility slice only if evidence warrants. No blanket cache removal | Medium; lower ROI until earlier confirmed fixes close | No confirmed #391 blocker | Yes, install strategy/cache changes outside scope |

Early stopping: close confirmed violations first, then high-ROI pin/exception corrections. For uncertain items gather the smallest non-sensitive evidence before implementation. Stop when the next step needs protected access, wider policy decisions, dependencies, or a separate architectural scope. No new architecture workstream is proposed.

## Human acceptance and checkpoint

Next decision: accept the uncommitted bounded correction, decide which backlog items must precede lifting PR #391's HOLD, and separately authorize publication/CI. No merge authorization requested or implied. Independent review and final local verification are complete. Next action is human acceptance and a separately authorized publication/CI phase; no merge authorization is implied.

Base/HEAD and all five modified paths are recorded above. Local synthetic validation and bounded review are complete; real CI/security execution remains unrun. Full-history refetch/runtime and new rule findings may cause legitimate CI failures; do not suppress them to obtain a pass. Protected-object confidentiality remains unproven, and full-history CI object transfer is explicitly permitted for this correction. The temporary prior A2 stop was resolved by the human reply. No remaining quota/context blocker observed at this checkpoint; exact session-wide context accounting unavailable as disclosed at start.
