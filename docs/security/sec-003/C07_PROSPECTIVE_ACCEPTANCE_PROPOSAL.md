# SEC-003 prospective C07 suppression-safety acceptance proposal

Status: PROPOSED / NOT ADOPTED. Verdict: PROPOSAL READY for owner consideration.
This is a new criterion, identifier C07-P1, not recovered historical C07.
SEC-003 OPEN; Stage 1B NO-GO; R2 UNCHANGED; PRs #451/#452 HOLD.

## Scope and authority

Owner authority: the C07 prospective-criterion task and subsequent baseline
clarification in this conversation. Only proposal and preservation documentation
are authorized. No criterion adoption, scanner-policy change, implementation,
qualification execution, corrective-patch edit, staging or publication is authorized.

Proposal worktree: C:/Users/adamo/.codex/worktrees/sec003-c07-prospective-criterion/coin-analyzer.
Branch: docs/sec003-c07-prospective-criterion.
HEAD and authorized base: 6c30daee23c2d8f9029f19e42dbabb69bac64034,
obtained by a successful fresh origin/main fetch in this task. The starting
tracked state was clean. Remote freshness is an observation, not a future guarantee.
The original checkout is governed by the separate task-specific preservation
receipt; its modified CONTRACT is neither adopted nor used as governing policy.

GOAL: Provide measurable prospective criteria and a decision-ready matrix.
IN SCOPE: This document and task-local C07_PRESERVATION_RECEIPT.json only;
read-only named source review and lightweight documentation/preservation checks.
OUT OF SCOPE: Engineering/provenance re-investigation, scans, installations,
policy or patch changes, execution admission, commits, pushes, PRs and merges.
PROTECTED BOUNDARIES: Original checkout/index, retained evidence and correction,
private material, scanner detection, full R2 and specialized security gates.
ACCEPTANCE GATES: Complete proposal, source correspondence, document checks,
preservation; independent review and owner adoption remain future acceptance gates.
STOP CONDITIONS: Unexplained drift, conflicting binding controls, protected access,
unsafe weakening, scope/authority expansion and governing context limits.

## Exact proposed criterion C07-P1

Once explicitly adopted prospectively, a suppression policy SHALL be eligible
for owner technical acceptance only when ALL the following are demonstrated:

1. Bind a reviewed immutable snapshot of the scanner, platform-specific binary
   digest, effective built-in/extended rules, config, workflow/harness, invocation,
   Git selection, fixture manifest and expected outcomes. Begin with Gitleaks
   8.24.3, the version used by the retained correction; any version change needs
   its own reviewed qualification. A version string alone is insufficient.
2. Define reference B as the SAME effective scanner/rules/invocation with only
   the candidate exception disabled in an isolated synthetic copy. Define C as
   the exact candidate policy. No other rules, inputs, history, options or
   environment may change between B and C for a case.
3. Before execution, enumerate E, the finite set of approved synthetic fixture
   findings eligible for suppression, with rule ID, exact repository-relative
   path, exact extracted inert value, fixture role/context and expected occurrence
   identities. Independently establish that the value is non-secret.
   For every case, require Findings(C) = Findings(B) minus E(case).
   Require each expected finding individually; aggregate counts alone cannot pass.
   B must actually detect every intended exception/control finding first.
   An empty or malformed B result cannot validate suppression.
4. Every unapproved secret-shaped synthetic control detected by B SHALL remain
   detected by C, including a distinct replacement at the same path, line and
   rule as an approved fixture. No path/line/commit fingerprint, cached baseline,
   inline directive, ignore file or wrapper may remove that distinct finding.
   Qualification reports must reconcile both missing and unexpected findings.
5. An exception SHALL be rule-specific and combine exact anchored path matching
   with exact anchored extracted-value matching using AND. No global file/path
   exclusion, OR widening, wildcard secret match, line-only/fingerprint-only
   suppression or baseline subtraction is acceptable. Approved scope requires
   explicit evidence and owner decision; this proposal grants no new exception.
   A candidate unable to meet these predicates is rejected, not broadened.
6. Preserve effective default detection and existing binding controls: no disabled
   default rules, reduced history coverage, unchecked/skipped scanner,
   continue-on-error, swallowed failure, unapproved report publication or weakened
   permissions/privacy boundary. Unrelated defects remain separately unresolved.
   Passing C07-P1 cannot waive or replace any other scan or gate.
7. A clean complete scan must exit 0. With --exit-code=2, a scan containing any
   unsuppressed expected finding must exit 2 AND contain matching valid finding
   metadata. Any other nonzero result is an operational failure, never a detection
   pass. Timeout, cancellation, crash, missing tool, version/hash mismatch,
   config/parser error, incomplete input, malformed/missing report, unexpected skip
   or failed required subcase prevents acceptance. A wrapper must propagate failure
   into the required check; a generic nonzero alone does not prove detection.
8. All required matrix cells, native lanes, evidence reconciliation and independent
   review must be complete for the stated scope. Partial, skipped or unavailable
   evidence is UNQUALIFIED; failures remain preserved. No automatic retry,
   correction or promotion is authorized. Owner acceptance is a separate explicit
   decision bound to the final reviewed snapshot.

Finding identity must include rule, normalized relative path, commit identity,
start/end line and a locally compared synthetic-value identity; include column
identity if provided. Normalize separators only for comparison, never to widen
the approved path. Retain multiplicity. Raw values are inert synthetic inputs;
retain only sanitized metadata in decision reports. No real credential is needed.

## Acceptance matrix

All cases are proposed requirements, NOT RUN in this task. Run both B and C
against identical fresh, local-only temporary Git repositories with no remote,
external hooks/templates/config/attributes, network access or protected objects.
No production checkout/history is a fixture. Predeclare outcomes before running.

| ID | Synthetic case | Required B / C outcome |
| --- | --- | --- |
| P01 | Clean repository without secret-shaped values | Both exit 0; no findings; proves the harness does not always fail |
| P02 | Each approved inert fixture, individually, in each authorized file/context | B reports the predeclared fixture occurrence; C removes only that occurrence; C exits 0 when nothing else is present |
| P03 | Approved fixture plus unrelated synthetic key in the SAME file, on a separate line and on the same line | B reports both; C retains the key exactly; C exits 2 |
| P04 | Independent A/B keys at the same path/line/rule in separate histories, including each approved path | Both keys detected individually by B and C, exit 2; no location-based credit or suppression |
| P05 | Commit approved fixture, then replace it with distinct key A and then key B at the same line | Full-history B includes expected historical occurrences; C removes only approved fixture, retaining both keys with correct commits, exit 2 |
| P06 | Approved value outside allowed paths, nested/lookalike names, suffix/prefix paths, and wrong rule | Wherever B detects the control, C retains it; synthetic rule-specific wrong-rule control must be B-detectable; no cross-rule suppression |
| P07 | One-character value changes, prefixes/suffixes and distinct high-entropy replacements in both approved paths | Prevalidated B-detectable controls remain in C; each exits 2; exact-value boundary demonstrated |
| P08 | Representative independent built-in rule controls, both inside approved paths and elsewhere | B and C finding multisets equal; no default rule disabled or overwritten; all expected controls exit 2 |
| P09 | Controls reachable only in root, deleted content, side/unmerged branch and merge-only change | B and C retain each unapproved occurrence under the frozen required history selection; no event-range substitution |
| P10 | LF/CRLF files, native path separators, path case/lookalikes supported by each filesystem | Exact approved scope only; all B-detectable unapproved controls retained; unsupported topology explicitly unqualified |
| P11 | Forbidden whole-file/global allowlist, AND-to-OR, broadened regex/path or fingerprint subtraction, in disposable candidate copies | Qualification rejects EACH weakened policy; include P03-P07 counterexamples rather than relying only on text checks |
| P12 | Scanner missing/wrong version/digest, invalid config, exit 1/3, timeout/crash, malformed/truncated/absent report | No qualified result; distinguish operational failure from detection; failure reaches the required check |
| P13 | Missing expected record with unchanged count, extra record, duplicate/lost record, wrong path/rule/commit and unexecuted/skipped case | Reconciliation rejects each independently; no count-only, stale or fabricated success |
| P14 | Swallowed exit, continue-on-error, early successful return, reduced history selection, empty rules or unapproved ignore source | Harness/control review and synthetic negative cases reject each; a clean exit alone cannot pass |

P02 is conditional on an evidenced non-secret fixture that B detects; if it
cannot be established, no suppression is qualified. Do not invent a false
positive. P06-P08 use inert inputs prevalidated against pinned B; absence of
detection invalidates that control, not the scanner. Case multiplicity includes
both allowed files, both A/B replacements and each named mutation separately.

## Evidence and platform scope

Require a frozen manifest of source/base/blob/raw hashes; scanner binaries and
approved origin/integrity; exact effective config/default-rule identity; sanitized
synthetic fixture generator/content identities; Git graph/commit identities;
commands/options/environment; OS build/architecture, filesystem, Git/Python/tool
versions; expected versus observed complete finding multisets and exit codes;
case start/end and timeout/skip status; sanitized raw diagnostics, reconciliation,
negative controls, preservation and exact final independent verdict.

Candidate scope is initially native Ubuntu x86-64 (CI scanner lane) AND native
Windows x86-64 (retained local scanner/test behavior). Record exact Ubuntu
release/runner image and actual Windows build. For any SEC-003 native Windows
qualification claim, retain Windows 11 24H2 x64 and its applicable approved
interpreter/profile matrix; Windows 10, hosted Windows 2025, WSL or Ubuntu cannot
substitute. Do not infer scanner coverage of every Python profile: map which
harness/interpreter lanes actually affect the claim and retain all separately
binding full-matrix obligations. A narrow Linux-only result must remain labelled
Linux-only and cannot satisfy this two-platform proposed criterion or global
SEC-003 acceptance. Other architectures/OSes remain UNQUALIFIED until separately
authorized. Simulated shell/control failures prove adapters only; native actual
scanner runs are required for detection/configuration/path/exit semantics.

Do not run this matrix under old exhausted allowances. A later execution package
needs its own exact scope, resources, admission and privacy/retention authority.
No installation, provisioning, CI dispatch or protected-data transfer follows.

## Existing evidence and limitations

Reviewed source identities are recorded in the task-local receipt. Sources:

- Current base AGENTS, CONTRACT, RUNBOOK, general-governance adoption record,
  STANDARDS, SEC-003 dependency contract, .gitleaks.toml and Tests workflow.
- Original-checkout build/worktrees/sec003-c07-controlled-integration-01/docs/agent-ops/ci-security-hardening-assessment.md.
  This recovered assessment reports missing defaults, broad file exclusions,
  event-limited scanning and embedded SARIF publication at its historical snapshot;
  its review and validation apply only to that snapshot.
- Original-checkout build/sec003-c07-integration-review-20261106/INTEGRATION_REVIEW.md,
  VERIFICATION.json and C07_CORRECTIVE.patch. The retained 5,230-byte patch SHA-256
  is 8F396BD075CA13D31B585A0074F60D7207DAB53C8954E5B3B945137CF039E6CA.
  Its source base is 2f0ed985df3a466ca04402eff0ef366b7ac1cde2.
  The inspected unchanged test adds opt-in Gitleaks 8.24.3 checks for independent
  A/B histories at synthetic/c07_control.txt:41, using defaults-only configuration.
  Reported successful detection is engineering/default-detection evidence,
  not suppression qualification, replacement-history testing or historical acceptance.
  This task does not rerun those checks or import that test into main.
- Original-checkout build/sec003-gitleaks-linux-12/RUN01_EXECUTION_REPORT.md:
  FAIL/STOPPED at staged whitespace, before commit/publication/Linux runtime.
  No Linux qualification follows from it; this proposal neither retries nor repairs it.
- Exact retained SEC0031_R2_APPROVED.txt, complete C1-C12 including 30 C12 cases,
  verified against the incorporated 39,704-byte SHA-256 identity.

At this proposal base, .gitleaks.toml extends default rules and contains a
generic-api-key rule-level AND exception for exact extracted value
normalized-coin-1-front in tests/test_processed_artifact_snapshot.py and
tests/test_workflow_execution.py. This is an existing candidate scope for P02,
not a new authorization or a qualification claim. Independent non-secret evidence
and differential testing remain required. No .gitleaksignore exists at this base.

Current Tests still invokes pinned gitleaks-action, unlike the retained correction's
direct CLI recipe. No claim is made that the recovered assessment's workflow
findings have been remediated in current main. Do not copy that old workflow or
claim its checks apply to main. Any deployment remedy requires a separate bounded
decision and its own current evidence. This criterion supplies no exception for
wrapper publication, incomplete history or suppressed errors.

The owner reports targeted investigation did not authenticate the original C07
specification/adoption. That historical limitation is accepted as the task premise;
no historical sessions, confidential originals or provenance searches were reopened.
The recovered assessment is not authenticated proof of the unidentified C07 text.
Keep historical C07 UNRESOLVED/FAILING, F-01-F-04 and G-02 unresolved under their
existing dispositions. No synthetic PASS can retroactively satisfy that finding.

## Independent assurance and owner adoption

Before adopting C07-P1, a reviewer separate from the author must assess this exact
final proposal and security-equivalence argument against binding governance,
actual config/workflow, full applicable R2 and the retained evidence limits.
Record reviewer/model/role, separation, snapshot digest, coverage, findings,
limits and PASS / PASS WITH NOTES (nonblocking only) / FAIL / BLOCKED.
Self-review is not independent. Resolve blocking findings only under authority;
obtain independent confirmation on the changed final snapshot before acceptance.

Before accepting technical qualification, an independent verifier must inspect
the exact implemented policy/harness and native evidence, independently challenge
suppression specificity and failure propagation, and verify evidence identity,
completeness and applicability. Reuse prior review only for unchanged predicates;
historical engineering PASS WITH NOTES cannot cover this new policy.
Any separately binding human, custody or platform-separated evidence requirement
remains mandatory; a different LLM/session alone does not establish it.

Owner approval must separately identify (a) prospective criterion adoption,
(b) each exact exception, if any, after non-secret evidence, and (c) acceptance
of the qualified final snapshot after all required independent/native gates.
Normal change control/current CI and publication authority remain required.
No approval in one category supplies execution or approval in another.
This document has author self-review only; independent final-proposal review,
matrix execution and owner acceptance are NOT PERFORMED.

## Security equivalence and conflicts

| Binding control/objective | C07-P1 treatment | Conflict assessment |
| --- | --- | --- |
| Default secret detection and narrow exceptions | Differential multiset equality, exact path AND value within one rule, same-location replacements, independent rule controls | Preserves detection; adds prospective measurable assurance; no new exception granted |
| Fail-closed outcomes and truthful evidence | Explicit clean/detection/error outcomes, native results, mutation rejection, missing evidence unqualified | Compatible; actual future equivalence remains to be demonstrated |
| R2 C1-C12 and 30 cases within original applicability | No replacement, reclassification, timing/resource reset, helper/custody shortcut or runtime credit | No textual/control conflict identified; scanner synthetic evidence cannot qualify R2 |
| SEC-003 native/full matrix, provenance, custody, budgets and independent gates | Retained in full; narrow scanner result never promotes global status | Compatible only with exact scoped labels and separate authority |
| Historical C07 failing disposition and F/R/G-02 reconciliation | Preserved without waiver; new criterion has distinct identity/effective scope | Adoption is prospective; treating it as historical satisfaction WOULD conflict |
| Governance authority/change control | Separate final-snapshot review, explicit adoption, future implementation/execution and publication gates | Compatible; owner preference or document presence alone cannot adopt it |

No existing binding requirement was identified that prohibits proposing or later
adopting this additive prospective criterion through required change control.
This is a documentary assessment, not proof of operational security equivalence.
Original C07 requirements remain unidentified; equivalence to that unknown text
cannot be assessed or asserted. A request to substitute this criterion for
historical authentication, close C07 retroactively, narrow original R2/native
scope or weaken detection would require rejection/conflict disposition.

Pillow 12.3.0 remains UNQUALIFIED pending independent security/advisory reassessment.
Pillow 13.0.0 remains UNQUALIFIED. Full-program admission remains BLOCKED and the
Tier 1 pilot remains HOLD / NOT AUTHORIZED. Historical failed/exhausted allowances
remain unchanged. No qualifying run, independent acceptance or publication occurred.

## Decision and checkpoint

Requested owner decision: consider C07-P1 solely as an additive prospective
acceptance standard, with historical C07 left unresolved; authorize one bounded
independent review of this exact proposal before any adoption decision.
That review authorization must name snapshot, scope/resources and finite exit.
No implementation or qualification execution is requested now.

One concrete next action: owner authorize the independent final-proposal review.

Preservation is documented in C07_PRESERVATION_RECEIPT.json; this receipt is a
task-specific observed baseline, not a successor that erases historical B0.
Only these two new documentation files exist as task outputs, unstaged/uncommitted.
No code/config/workflow or corrective patch was modified. Engineering tests,
scanners, native qualification and CI were not run; existing evidence is attributed
above. Required independent review and manual owner acceptance remain outstanding.

SEC-003 OPEN; Stage 1B NO-GO; R2 UNCHANGED; PRs #451/#452 HOLD.
