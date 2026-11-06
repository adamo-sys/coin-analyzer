# General-governance adoption and session rotation

## Prospective general-governance adoption

**Owner approval supplied; effectiveness pending required review, passing CI and
normal repository change control.** The owner's governance-adoption and
session-rotation task expressly approves prospective adoption of the general
engineering framework introduced by [PR #453](https://github.com/adamo-sys/coin-analyzer/pull/453).
That PR was squash-merged at `8ebc03e67edc0584ff673aec692c5af73777a6b9`.
Read-only remote main verification for this package returned that exact SHA on
2026-11-06 UTC; it is the authorized editing base, not an assertion of future
remote freshness. PR #453 published a proposal; its merge did not itself adopt
every proposal it contained.

This approval covers the general entry/scope rules, action authority, engineering
risk tiers, validation/review, evidence reuse, finite blocker handling, scheduled
agents and bounded workflow in AGENTS, CONTRACT and RUNBOOK, with the prospective
rotation amendment below. It adds no specialized acceptance or security exception.
The general framework becomes **ADOPTED for future work** only after review of
the exact final diff and security-equivalence assessment, independent confirmation
of any blocking-finding resolutions, passing applicable CI on the exact final PR
head, and completion of normal repository change control including a separately
authorized merge into main. The owner approval is recorded here; those remaining
conditions are not claimed complete by this working copy. Until effective, the
previous governing policy, including mandatory work-package rotation, still applies.
After effectiveness, this record supersedes general-framework proposal labels in
the historical section below; it does not supersede specialized status labels.

The adoption boundary preserves four distinct classes:

- **General governance:** owner-approved prospectively, effective only on the
  conditions above; this package prepares the exact uncommitted four-file diff.
- **Historical decisions/evidence:** original scope, provenance limits and gaps
  remain unchanged. No historical procedure, finding or review is newly validated.
- **Specialized adopted requirements:** retain their existing exact scope and all
  independent verification, custody, native qualification, budget and release gates.
- **Specialized proposals:** Package 0 amendments, SEC-003 proposed amendments,
  CA-OPS-EFF-001 and conditional owner clarifications keep their separate adoption
  conditions. This general approval supplies none of their missing decisions.

**SEC-003 OPEN; Stage 1B NO-GO; R2 UNCHANGED; PR #451 HOLD; PR #452 HOLD.**
No SEC-003 acceptance, historical-evidence or release-gate change is authorized.
The complete CONTRACT tail from the first Package 0 amendment remains unchanged.

## Session-rotation amendment and security equivalence

Binding source for the replaced general rule: AGENTS context-budget paragraph and
RUNBOOK checkpoint procedure at the editing base above. This is a prospective
policy-control change, treated as engineering Tier 3 despite documentation-only
implementation. The failure modes are stale assumptions, lost decision history,
overloaded context and erosion of specialized or independent assurance.

**Old:** checkpoint at every bounded work-package boundary and rotate before
another substantive package. **New, once effective:** checkpoint meaningful
boundaries and record whether continuing is safe; continue only with sufficient
context, authorized scope, understood state and valid evidence. Rotate on context,
state, evidence, separation or binding security grounds. No new numeric allowance
is introduced: 50K warning, 65K checkpoint/no new substantive steps, 75K hard
rotation and 100K emergency ceiling retain their exact actions and finish exception.
Compaction never resets accumulated context/work.

Automatic boundary rotation was considered and retains a simple trigger, but
does not itself establish evidence freshness or independent assurance. Removing
rotation controls entirely would lose protection against overload and stale state.
The selected bounded amendment retains mandatory limits and specialized triggers,
and makes the general boundary decision explicit and reviewable.

| Changed requirement / original objective | Replacement control | Verification method | Residual risk |
| --- | --- | --- | --- |
| R1 Automatic rotation before another substantive package: avoid overloaded context, forgotten constraints and stale assumptions | Meaningful-boundary checkpoint plus reasoned continuation decision; require sufficient context, authorized scope, understood state and valid evidence; rotate on capacity, uncertainty, integrity, separation or binding security trigger | Compare AGENTS/RUNBOOK against the base; independently challenge continuation with stale evidence, unknown state, exhausted capacity and unauthorized next scope; confirm all fail closed or require rotation as applicable | Capacity/freshness judgments can be mistaken; conservative checkpointing, affected-fact revalidation, mismatch stops and unchanged hard limits bound this risk |
| R2 Repeated boundary checkpoint production: preserve decisions and resumability | Retain one sufficient record with all existing handoff fields; reference it and record decisions/material deltas when substantive state is unchanged; preserve original evidence and all mandatory complete receipts | Check unchanged handoff template, authorized-storage limits and locator paragraph; review unchanged-state and changed-state cases; confirm specialized receipts cannot be skipped | An incomplete record or missed delta can impair reconstruction; required fields, original sources, delta recording and receiver verification remain mandatory |
| R3 Generic boundary handoff: obtain a reliable fresh start | Mandatory handoff for triggered rotation; receiving session verifies state, authority and next prerequisites; explicit specialized security handoffs and independent reviewer separation override continuation | Compare retained receiver verification, exact-file/protected-evidence boundaries and reviewer requirements; inspect the untouched specialized CONTRACT tail and exact final diff | Fresh sessions can inherit an incorrect summary; actual-source review and specialized custody/independence predicates remain necessary; rotation alone certifies nothing |

These are documentary equivalence criteria for the general procedure, not runtime
confidentiality, historical authentication or measured efficiency claims. Numeric
thresholds, finish-exception text, mandatory security handoffs, exact-file authority,
protected evidence and independent blocking-finding confirmation are retained.
The historical E12 row describes PR #453's unchanged-budget design; only its
blanket boundary-rotation retention is superseded prospectively by R1-R3.

## Adoption-package validation and limits

Acceptance requires exact four-file scope, whitespace/newline/conflict-marker and
relevant local-link/anchor checks, exact specialized-tail preservation, unchanged
numeric budget table and finish exception, unchanged conditional locator and
handoff fields, original-checkout preservation, and independent technical review
of the actual fixed diff. Review/check results and snapshot identities accompany
delivery; the historical receipts below do not cover this amendment.

No commit, staging, push, PR, merge or manual CI dispatch is authorized in this
package. CI for these uncommitted changes is unrun; PR #453's results support only
its own snapshot. Owner review of the final changes is the next action. Later
publication and adoption gates need their own authority and fresh applicable
evidence. No further SEC-003 investigation is needed or authorized here.

## Historical PR #453 proposal and reconciliation record

Everything below is the retained historical proposal record. Its dates, draft
labels, source observations, task-local prohibitions and review receipts describe
the original snapshots, not current general-framework effectiveness or a fresh
verification. Specialized proposals and their conditions remain independently
controlling; the prospective record above cannot adopt them by implication.

**PROPOSED / NOT ADOPTED - documentation only, 2026-11-05.**
Review target: READY TO ADOPT after final independent confirmation, not adopted policy, verified operational
security, runtime acceptance or merge readiness. Actual validation/review results
are recorded in the completion receipt. No commits or publication are authorized.

## Operating model and scope

AGENTS is the concise entry point and retains context thresholds/protected boundaries.
CONTRACT owns engineering authority, risk, evidence, review and conflict rules.
RUNBOOK supplies one workflow scaled to actual impact. Specialized architecture,
security, dependency, evidence and testing contracts retain their own predicates.
Use authoritative links and one sufficient decision/closure/checkpoint record.

Only four files may change: `AGENTS.md`, `docs/agent-ops/CONTRACT.md`,
`docs/agent-ops/RUNBOOK.md` and this proposal. No code, dependencies, tests, CI,
findings, evidence records, collection data or credentials may change. No Stage A
feasibility work, installation, scans, regression, remote mutation or publication.
Preparing these proposed replacements does not adopt them for this task.

## Baseline and authority register

| Source | Observed identity / applicability | Treatment |
| --- | --- | --- |
| Owner task and worktree authorization | Exact authorized baseline `0a4a4bc8f9ae4eed0b3981d8fd1d25d4f83073e0`; branch `codex/governance-simplification`; isolated worktree `C:/Users/adamo/.codex/worktrees/governance-simplification/coin-analyzer` | Binding task scope; permits draft preparation, not adoption or publication |
| Historical/local baseline | [Exact baseline](https://github.com/adamo-sys/coin-analyzer/tree/0a4a4bc8f9ae4eed0b3981d8fd1d25d4f83073e0); root harness, CONTRACT, RUNBOOK, STANDARDS, CODEX_WORKFLOW, SECURITY and TESTING read at that revision | Operative baseline for this bounded task, not asserted to be current main |
| Original dirty checkout | `docs/deferred-mass-research-candidate` at the same commit, five tracked modifications | Preserved separately; none copied. The 92 added CA-OPS-EFF-001 lines explicitly say PROPOSED / NOT ADOPTED and supply no policy authority |
| Live remote observation | GitHub read-only branch API on 2026-11-05 returned main `31a0b19e0bd714fc498a84783670951550d853dd`, matching the cached ref | Distinct pinned observation, not a fetch or a new authorized editing base; later movement not excluded |
| Remote governing delta | [Pinned main](https://github.com/adamo-sys/coin-analyzer/tree/31a0b19e0bd714fc498a84783670951550d853dd) differs in AGENTS, CONTRACT, RUNBOOK, CODEX_WORKFLOW, TESTING and the two SEC-003 documents below; STANDARDS/SECURITY match | Fresh review completed; specialized CONTRACT tail and conditional RUNBOOK locator retained exactly; current target freshness remains required |
| SEC-003 dependency contract | Absent at authorized baseline; inspected [pinned remote document](https://github.com/adamo-sys/coin-analyzer/blob/31a0b19e0bd714fc498a84783670951550d853dd/docs/security/SEC-003_DEPENDENCY_CONTRACT.md), especially authority, profiles, closure/audits, acceptance and owner decisions | Specialized requirements retained; no acceptance criteria altered or execution authorized |
| SEC-003 handoff | Absent at authorized baseline; inspected [pinned remote handoff](https://github.com/adamo-sys/coin-analyzer/blob/31a0b19e0bd714fc498a84783670951550d853dd/docs/security/sec-003/EVIDENCE_HANDOFF.md), especially source/adoption limits, verification procedure and status | Contains its own proposed-procedure labels and historical claims; publication alone does not adopt every clause. No linked confidential original/session/PDF was opened or reauthenticated |
| Remote adoption records | Remote CONTRACT records prospective Tier 1 Linux provisioning ADOPTED and retains qualification, native, budget and execution holds; baseline lacks that record | Exact remote record retained, including adoption scope, provenance limits, independent-review gaps and all outstanding gates |
| Other remote additions | Package 0 amendments retain explicit adoption conditions/historical disclosures; context-pack clauses deny policy authority; RUNBOOK adds current-state locator details; TESTING adds offline-PWA browser CI | Package 0 text and conditional locator preserved; TESTING and executable workflows remain controlling, with no branch-protection inference |
| Baseline SEC-003 assurance amendment | Historical source retained at immutable baseline; proposal now carries the exact remote specialized tail, including adapted assurance attribution | No historical decision rewritten; remote original-final-diff EDR gap and all separate adoption conditions retained |

No broad search, original-source recovery or independent historical authentication
was performed. The recorded specialized source claims are not newly proved facts.
The fresh review reconciles the named remote governance differences within these
four authorized paths. The checkout base is unchanged. Future application must use
a then-verified target and retain all intervening governance changes; this verdict
does not authorize rebasing, publication, adoption or a wholesale historical transplant.

## Binding versus proposed control register

| Control / assertion | Demonstrated authority | Result |
| --- | --- | --- |
| Exact-file confidential access; no unauthorized transfer; local-only images; no invented provenance | Owner task, baseline AGENTS and SECURITY; specialized sources preserve further limits | RETAIN; confidentiality exceptions are not supplied by efficiency |
| Full R2 within original applicability; specialized independent verification, native qualification and mandatory gates | Preserved remote amendment and specialized references | RETAIN; this proposal does not verify original R2 bytes, alter incorporation or credit missing evidence |
| Three engineering risk tiers and finite workflow | Proposed here under owner drafting authority | Pending explicit prospective adoption; not a reclassification of SEC-003 assurance tiers |
| Independent AI technical review | Baseline already permits a separate verifier without mandating a human for every claim; proposed text specifies eligibility/limits | Clarification for suitable technical claims only; specialized human/custody/independence predicates remain controlling |
| Permanent physical isolation as a universal Stage A requirement | Owner reports a bounded review did not establish binding adoption; original review/adoption sources not authenticated in this task | Not demonstrated as a universal requirement. This does not prove no specific requirement exists; retain any applicable specific control and defer adjudication |
| Dedicated offline equipment; verified temporary isolation with controlled release | Candidate methods reported by owner; neither verified compliant | DEFER selection/qualification. No hardware mandate inferred from recommendation; no reconnection or access authorized |
| Raw-index/all-protected-file fingerprints on every routine operation | Not a general baseline requirement; specific historical/evidence tasks may mandate them | No new universal mandate. RETAIN every applicable specialized fingerprint, preservation and custody predicate |
| Repeated full discovery, duplicate contracts/packets, repeated equivalent reviews, blanket full regression | General baseline requires bounded relevant sources, one six-field format and lightweight docs checks, not universal duplication | Simplify general mechanics only; retain any specific full-source, refresh, receipt or regression requirement |
| CA-OPS-EFF-001 detailed preservation baseline and model-effort routing | Remote section retained explicitly PROPOSED / NOT ADOPTED; navigation guidance disclaims unqualified routing/savings | Neither silently adopted nor disproved. Existing specific requirements remain |

Do not infer that an implementation method became historically mandatory merely
because this task asks to identify that risk. The register distinguishes observed
proposals and owner-reported ambiguity from proven adoption history.

## Old-to-new crosswalk and security-equivalence assessment

Baseline references below mean the exact authorized commit, not current main.
Rows cover every material removal, merger or replacement in the three drafts.
SIMPLIFY means structural/design equivalence for the general rule; it does not
certify operational effectiveness. Where that argument cannot establish equivalence,
the original specific control is retained and the broader proposal is DEFERRED.
All general policy changes require explicit owner adoption; no SEC-003 exception is
requested. RETAIN rows need no new waiver or historical disposition.

| ID / original requirement and objective | Proposed replacement / reason | Evidence supporting equivalence or retention | Security impact / residual risk | Decision / owner action |
| --- | --- | --- | --- | --- |
| E1 AGENTS, CONTRACT Git Rules and RUNBOOK step 1 repeat branch/HEAD/base gate: prevent wrong-base work | One recorded entry check, linked procedure, affected-fact refresh on state change and current action gates | Exact base comparison/mismatch stop retained in all entry routes; exit scope and publication/merge freshness retained | Undetected concurrent mutation remains possible; current-state claims need current evidence; specialized hash checkpoints unchanged | SIMPLIFY repeated collection; owner adoption |
| E2 AGENTS/CONTRACT/standards six-field task format: prevent scope/authority drift | Reuse complete owner contract once; update only material changes | Same six fields and named file boundary retained; prerequisite expansion still stops | Contract can become stale if changes not surfaced; material-change update remains mandatory | SIMPLIFY; owner adoption |
| E3 RUNBOOK checkpoint plus closure and CONTRACT durable state: preserve resumability/audit trail | One authorized durable decision/closure record reused for handoff | All original handoff facts retained, including publication, evidence, next action, boundaries and budget; full specialized originals retained | Concise records can omit detail; required material fields and original evidence cannot be omitted | SIMPLIFY duplication; owner adoption |
| E4 Significant review and final blocking-finding confirmation: challenge implementation independently | Explicit suitable LLM reviewer eligibility; same-risk separated authorship, actual source/diff, verdict and limitations | Baseline RUNBOOK already says separate reviewer, read-only evidence review, findings and independent final confirmation; all retained | Shared-harness/provider/custody limits remain; AI cannot verify inaccessible evidence or replace required humans | SIMPLIFY generic ambiguity only; owner adoption; RETAIN specialized assurance |
| E5 Re-review blocking findings on updated snapshot: prevent stale acceptance | Recheck changed predicates/dependencies and independently confirm resolution; retain full review when required | Original independent confirmation and final-snapshot condition retained, not replaced by implementer assertion | Missed dependencies could invalidate reused coverage; changed risk or binding refresh requires broader review | SIMPLIFY redundant unchanged coverage; owner adoption; DEFER relaxing any specialized whole-snapshot review |
| E6 Focused tests then affected checks; docs-only lightweight validation: catch relevant regressions | One tier-scaled validation rule linked from entry point and runbook | Same root regression command, authoritative CI roles and TESTING contract retained; docs exception already existed | Tier misclassification could under-test; actual impact/highest applicable tier and more-specific rules control | SIMPLIFY repeated text; owner adoption; RETAIN every mandatory gate |
| E7 Default authority and explicit restricted actions: prevent unauthorized mutations/disclosure | Action-based summary, reuse unchanged valid authorizations, no inference across operations | Branch/commit/push/PR/comment/CI/publication, merge, credential, destructive, privacy and architecture restrictions expressly retained | Overbroad interpretation of authorization remains a risk; exact action/material/destination and task prohibitions control | SIMPLIFY repeated requests only; owner adoption |
| E8 General significant closure review versus routine self-review: proportionate assurance | Three engineering risk tiers based on effects, with stricter binding predicates overriding | Baseline makes significant review practical, not universally mandatory for routine docs; proposed Tier 3 requires appropriate independent verification | A security-policy draft is Tier 3 despite being docs-only; AI-only assurance insufficient where claim/policy requires human | SIMPLIFY defaults; owner adoption; no specialized review reduction |
| E9 Bounded discovery/current evidence and strict stops: prevent unsupported claims and uncontrolled inquiry | Defined objective, threshold and exit; one blocker-to-action record; reuse valid evidence | Source identity/scope/environment/freshness and material-change triggers retained; UNKNOWN/FAIL/BLOCKED separated | Unknown mandatory predicates cannot pass; time limits/owner preference do not prove compliance | SIMPLIFY redundant inquiry; owner adoption; RETAIN mandatory unresolved blockers |
| E10 Broad stop wording: protect security boundaries | Explicit dependency mapping; stop dependent activity, permit independent authorized work only without broader binding stop | Original scoped-task and protected-boundary rules retained; no SEC-003 qualification/merge/release progress credited | Incorrect isolation could bypass a blocker; must establish separation and honor global/specialized stops | SIMPLIFY propagation only; owner adoption; DEFER any unsupported dependency claim |
| E11 Repeated architecture/privacy/evidence references: protect local-first state and confidentiality | Concise root controls plus authoritative contract/source links | All exact-material restrictions, ten JPEG limits, synthetic fixtures, ground-truth/confidence limits and frozen-spec digest retained | Broken/stale links can hide requirements; link checks and source applicability remain required | SIMPLIFY location/text; owner adoption |
| E12 Context budget, exceptional finish and checkpoint storage: avoid uncontrolled session growth | Existing root budget block retained verbatim; runbook references it | Byte-comparison check of complete budget block; thresholds and work-package rotation unchanged | Accounting remains estimated when telemetry unavailable; no new waiver or reset | RETAIN; no relaxation proposed |
| E13 Scheduled-agent explicit instructions, durable state, safe stops and outcome records | One concise retained section under same authority limits | Completed/skipped/failed states, per-run persistence and material-change stops expressly retained | Automation can still misuse stale authority; scope and mandatory source rules continue | SIMPLIFY prose; owner adoption |
| E14 Package 0 and SEC-003 source, adoption, independence, native, budget and unresolved-status clauses | Retain complete verified remote specialized tail unchanged, with original scope/adoption limits | Exact source-text comparison to pinned remote; historical baseline remains immutable and linked; no specialized source file changed | Historical review gaps remain gaps; proposed sections remain proposed; current target freshness still required | RETAIN all specialized controls and decisions; no new exception or disposition |
| E15 Isolation recommendation versus confidentiality outcome | No new hardware mandate; consider only demonstrably compliant methods under governing source | Owner's reported ambiguity is labelled, not authenticated as an adopted rule; no containment claim made | Delayed transmission, residual state and unknown handling remain unresolved; exact-file access, no unauthorized transmission and defensible release remain mandatory | DEFER implementation/equivalence judgment; retain existing applicable controls; separate owner process |

Equivalence evidence here is document comparison, explicit predicate preservation
and bounded technical review. It supports the proposed general procedure design,
not empirically measured time savings, confidentiality engineering or retrospective
compliance. No operational control is removed on an unproved equivalence claim.

## Review-tier matrix

| Engineering case | Self-review | Independent AI technical review | Qualified human / specialist | Remaining gates |
| --- | --- | --- | --- | --- |
| Tier 1 routine | Required | Optional unless specifically binding | Only if applicable requirement/claim demands it | Focused checks, scope/authority, concise closure |
| Tier 2 significant | Required | Appropriate when practical and adequate separation/evidence exist | Required where AI-only assurance is insufficient under governing requirements | Tests, blocker resolution, applicable CI and explicit merge authority |
| Tier 3 security-critical | Required; explicit risk assessment | Appropriate independent verification where suitable; missing required review blocks acceptance | Required by policy/law/contract/claim, including evidence or assurance AI cannot establish | Security controls, uncertainty, owner decisions and mandatory security/CI gates |
| Historical evidence/custody claim | No self-authentication | Only accessible evidence within actual review competence | Required when governing claim demands independent custody/authentication or human judgment | Exact-file authority; never invent missing history or promote UNKNOWN to PASS |

Reviewer records model/identity, separation, exact snapshot, actual requirements/
source/diff inspected, challenge/findings, PASS/PASS WITH NOTES/FAIL/BLOCKED, missing
evidence and limits. No reviewer label implies human/external/platform isolation.
Confidential transfers need separate exact-material authorization/privacy assessment.

## Practical workflow examples

1. **Documentation correction (Tier 1).** Confirm base/state once; reuse six-field
   contract, change named text, check whitespace/relevant links, self-review and
   report result. No full regression, extra evidence packet or fresh approval for
   actions already authorized. Publication still needs its own authority.
2. **Small UI feature (classify by impact).** A non-sensitive label/layout feature
   can be Tier 1: bounded acceptance, focused UI validation and self-review. Data
   flow, persistence or security effects raise it to Tier 2/3. Never qualify the
   feature by its size or wording alone. CI and merge authority remain applicable.
3. **Significant persistence change (Tier 2 or 3).** Verify frozen architecture and
   invariant applicability; stop for contradictions, define acceptance, use
   synthetic temporary fixtures, run focused persistence/recovery and affected
   regression/static checks, and obtain practical independent technical review.
   Resolve blockers on the final snapshot; real records/backups require separate
   exact-material authority. No write decision is delegated to recognition.
4. **Security-control change (Tier 3).** State objective, binding source, threat,
   candidate methods, verification criteria and residual risk. Obtain required
   owner authority, implement only authorized controls, independently verify their
   actual claims, use qualified human review where necessary and retain mandatory
   gates. This governance reform is such a policy proposal; lightweight docs checks
   support its text, not containment or historical evidence claims.
5. **Unresolved historical evidence.** Identify the exact claim and missing source;
   use authorized named sources once. Record UNKNOWN or a failed criterion without
   inventing history. Keep only dependent acceptance blocked unless a broader rule
   applies. Escalate one finite decision record. An authorized prospective change
   may alter future criteria through adoption, never manufacture past compliance.

## Controls retained unchanged

- Confidentiality, exact-file access/transfer authorization, credential boundaries,
  local-only image restrictions and synthetic-fixture requirements.
- Local-first architecture, optional network/AI behavior, collector intent for
  persistence and provenance-backed evidence without invented confidence.
- Mandatory technical verification, meaningful independent review, independent
  confirmation of blocking-finding resolution and human review where required.
- Applicable tests/security gates, current blocking CI and explicit human merge
  authority; no acceptance of stale, failed, cancelled or incomplete gates.
- Specialized SEC-003 acceptance criteria, complete R2 applicability, native
  qualification, evidence authenticity/custody and all unresolved dispositions.
- The complete pinned remote specialized CONTRACT tail, preserved text-for-text,
  and the original root context-budget block, preserved byte-for-byte; no resource
  allowance, historical verdict or approval is reset or extended.

These are retained protections, not claims that their operational predicates have
been newly verified. The crosswalk identifies the general procedures simplified
around them and the controls whose replacement remains deferred.

## SEC-003 boundaries and adoption checklist

**SEC-003: OPEN. Stage 1B: NO-GO. R2: UNCHANGED. PR #451: HOLD. PR #452: HOLD.**
**F-01-F-04: unresolved pending qualified disposition. G-02: conflicting historical
decisions unresolved. C07: unresolved failing control.** These are preserved owner
constraints, not newly authenticated/closed finding records. No old FAIL is PASS.

- Confidential original files remain inaccessible without separate exact-file
  authorization; do not open them to complete this proposal.
- Dedicated offline hardware and temporary verified isolation remain unqualified
  candidate approaches. Do not reopen Stage A feasibility.
- No unauthorized confidential transmission, including delayed transmission after
  reconnection. Local-persistence risk acceptance does not permit transfer.
- Reconnection where confidential state could remain requires a defensible release
  process and is prohibited while confidential state remains uncontrolled.
  Owner preference cannot resolve unknown handling risks.
- Before adoption: review this four-file diff and equivalence register, reconcile
  then-current remote amendments and their adoption conditions, resolve blocking
  technical review findings, and obtain explicit prospective owner adoption under
  applicable review/change control. This is the smallest next policy action;
  implementation, qualification and publication are separate.
- Do not adopt a deferred control replacement without independent supporting
  evidence and its separately required owner decision. No specialized SEC-003
  acceptance-criterion amendment is included or implied.

## Validation and review boundary

Required lightweight checks: four-file scope and clean index; `git diff --check`
plus whitespace check for the new file; relative links/anchors without opening
protected targets; exact pinned remote specialized-tail text and original context-budget
block; original five-file/index preservation; self-review and a separate read-only
technical review of the draft requirements/diff. Exact results, reviewer/snapshot
and limitations accompany the delivered patch. These are proposal checks, not
security qualification or a new SEC-003 historical final-diff EDR.

Full regression, application tests, scanners, dependency operations and CI runs
are not performed for this documentation task. No current passing CI or merge
readiness is claimed. Efficiency is a design objective; no timing/quota savings
are measured or promised.

Historical preparation receipt, 2026-11-05 (prior snapshot, not rerun here): **PASS** for `git diff --check`; standard-library
whitespace/conflict-marker checks across all four files; 40 local links and 14
Markdown anchors; exact four-file scope, requested branch/base and empty staged
diff; byte-identical baseline SEC-003 suffix and context-budget block; and SHA-256
preservation of the original checkout's five modified files and raw index.
The original checkout's HEAD branch selector is also unchanged. These observations
do not authenticate historical evidence or establish remote CI success. The final
patch identity, patch verification and independent-review verdict accompany delivery.

## Fresh remote reconciliation review — 2026-11-06 UTC

The live GitHub repository/branch APIs identified default branch main and SHA
31a0b19e0bd714fc498a84783670951550d853dd in this newly rotated review session.
The same SHA as the prior observation was independently obtained; cached
origin/main was not used, and no fetch or checkout mutation occurred.
The task branch and HEAD/base remain exactly as recorded above.

Actual conflicts corrected:

1. The historical replacement omitted both remote Package 0 amendments. Their
   exact scopes, permanent evidence-gap/discrepancy disclosures, separate packet
   decision, independent verification, protected-checkout non-mutation and finite
   exit are now retained without textual change.
2. The old assurance representation differed from remote target-main attribution,
   adoption conditions, static-finding scope and original-final-diff EDR status.
   The complete remote tail now retains those distinctions, the prospective T1
   ADOPTED record, proposed CA-OPS-EFF-001, single-VM amendment and conditional
   owner clarification. This review supplies no missing historical EDR or adoption.
3. The conditional current-state handoff locator had lost mandatory UTC observation,
   source locators, verified claims, freshness/invalidation and decision fields.
   The remote RUNBOOK paragraph is restored verbatim; no universal locator is added.

4. The shortened root ground-truth wording could admit an unsupported supplied
   label. The original provenance-backed-or-unavailable predicate is now explicit.

Workflow reconciliation: remote context packs remain nonbinding navigation aids.
Task/Outcome Packets grant no autonomous authority. TESTING and executable CI
remain controlling, including the independent Offline PWA browser job, existing
AI smoke and other required jobs, privacy checkout exclusions and artifact limits.
The original named Python gates are not an exhaustive replacement list. No new
branch-protection setting is inferred or requested; advisory classifications stay
unchanged. No workflow or testing source file changes.

Security-equivalence conclusion: the general procedure design preserves exact
confidential-material/access/transfer boundaries, original evidence and truthful
unknowns, specialized custody/native/final-snapshot requirements, independent
confirmation of blockers, all applicable CI and explicit human authorization for
each merge. Reuse requires valid identity/scope/environment/freshness; dependent
stops cannot bypass broader binding holds. No runtime confidentiality, isolation,
historical authenticity or SEC-003 qualification is certified.

SEC-003 OPEN; Stage 1B NO-GO; R2 UNCHANGED; PR #451 HOLD; PR #452 HOLD.
Package 0 and all retained adoption, execution, budget and qualification holds keep
their exact scope. No confidential original or protected checkout was accessed.
No commit, staging, push, PR, merge, CI trigger or publication is authorized.

The final independent verdict and fresh documentation-check results must identify
the corrected snapshot. The prior PASS WITH NOTES and preparation receipt do not
by themselves cover this delta. The next policy action, after those checks, is
explicit owner prospective adoption through applicable repository review/change
control on a then-verified target; operational and publication actions stay separate.
