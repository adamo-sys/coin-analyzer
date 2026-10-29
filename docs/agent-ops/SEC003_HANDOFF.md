# SEC-003 handoff packet — mainline reconciliation

Packet: SEC003-HANDOFF-v0.2.
Status: PROPOSED / NOT ADOPTED as a locator/preservation packet.
CA-OPS-EFF-001 efficiency amendment: PROPOSED / NOT ADOPTED.
Reconciliation date: 2026-10-29.
Authority: owner authorization "CA-OPS-EFF-001 — Mainline Governance
Reconciliation"; preparation and independent review only.
Predecessor: SEC003-HANDOFF-v0.1, retained verbatim below.

This current view reconciles the predecessor's governance/status claims against
one authenticated, pinned mainline revision. It neither changes governing
requirements nor supplies execution authority. Publication, commit, push, PR,
merge and governance adoption are not authorized by this reconciliation.
The historical packet below is evidence of earlier observations, not a second
current view. Its contrary present-tense statements are historical only.

## A. Authenticated reconciliation basis

Repository: adamo-sys/coin-analyzer.
Configured origin: https://github.com/adamo-sys/coin-analyzer.git.
Owner-designated mainline base:
`a6af8d1ebf4fd897f9fd5cb71f6d4a13e4eea2ef`.
GitHub authenticated that exact commit and its tree:
`51c61fa6012c2275b7665ddf9476605f6fd869d5`.
This authenticates the pinned revision; it is not a claim that main cannot
advance after observation. A later publication task must check mainline drift.

Applicable [CONTRACT](CONTRACT.md) at that base: complete Git blob, 59,246
bytes, SHA-256
`BBAB5413C5DFDA2B4767E34816FA7DB332FAAFB7BA0BBCDB459262B7BC4BFCF8`.
All of those bytes, including both Package 0 amendments, the adapted SEC-003
Assurance-Tier Amendment and the prospective Tier 1 adoption record, remain
an unchanged prefix. Only the reviewed CA-OPS-EFF-001 amendment is appended.
No governing line-ending normalization, replacement or deletion is proposed.

Previously reviewed source, at C:/Projects/coin-analyzer on branch
`docs/deferred-mass-research-candidate`, HEAD
`0a4a4bc8f9ae4eed0b3981d8fd1d25d4f83073e0`:

| File | Raw bytes | SHA-256 |
|---|---:|---|
| docs/agent-ops/CONTRACT.md | 35,816 | `84D196765C33F616D96EB2670DF9041302245E31C6C5B19D271E8DF7C32E52F2` |
| docs/agent-ops/SEC003_HANDOFF.md | 13,602 | `CD1D4B427C8323808CEE3936A5452ED0B90362461360548B7C7EA391F37159A8` |

Those source bytes matched at reconciliation entry. The 5,253-byte amendment
suffix [30,563,35,816) is appended verbatim, with no compatibility edits.
The source's original 30,563-byte CONTRACT prefix remains historical; it is
not substituted for newer mainline governance.

Preparation worktree:
C:/Projects/coin-analyzer/build/worktrees/ca-ops-eff-001-mainline-reconciliation.
Preparation branch: `docs/ca-ops-eff-001-mainline-reconciliation`.
HEAD/task-authorized base: the pinned mainline commit above.
Only docs/agent-ops/CONTRACT.md and docs/agent-ops/SEC003_HANDOFF.md are in scope.
This is an uncommitted reconciliation, not a publication or adoption record.

B0 in the historical packet remains exactly its pre-amendment source-checkout
baseline, including its four-modification expectation and raw index identity.
It is not the baseline of this isolated worktree or the current complete source
state. At reconciliation entry the original source still had those four
protected modifications plus the reviewed CONTRACT modification, the reviewed
untracked handoff, and no staged changes. Its raw index and four protected-file
fingerprints matched the historical values. No B0 refresh, successor assertion,
original-checkout edit or original-index staging is performed here. Any later
authorized transition needs its own applicable recorded baseline/receipt.

## B. Current statuses and applicability

The current owner task and the pinned mainline CONTRACT control. Mainline
references below identify evidence and scope, not new authority from this packet.

| Subject | Status and limit | Mainline/owner source |
|---|---|---|
| CA-OPS-EFF-001; this packet; EFF-P1/P2/P3 | PROPOSED / NOT ADOPTED; no accounting or execution effect | Current owner task; appended amendment; historical section 5 |
| SEC003-T1-LINUX-PROVISIONING-DRAFT-01 | ADOPTED only as the prospective ordinary trusted Tier 1 Linux interpreter/tool provisioning contract, Sections 1–12 with the narrow Section 8 disposition | CONTRACT: SEC-003 Tier 1 Linux provisioning: prospective adoption record |
| Preserved Tier 1 draft/reports | Immutable earlier records; their PROPOSED / NOT ADOPTED labels are superseded only for prospective contract status by the mainline adoption record | CONTRACT: Preserved snapshot identity and provenance limitations |
| Section 8 interface condition | Narrow before-adoption flags/exit/schema condition satisfied; no artifact, bootstrap, closure or runtime toolchain qualification | CONTRACT: Section 8: narrow static-interface condition satisfied |
| Assurance-tier prerequisite changes | Only their exact conditional target applicability and sequencing; this packet does not infer adoption of other conditional provisions from the narrow Tier 1 adoption | CONTRACT: Authority, applicability and incorporated R2; Explicit prerequisite amendment and limits |
| Package 0 | BLOCKED; its two scoped amendments retain separate adoption, packet decision, applicability, independent verification and owner acceptance gates | CONTRACT: both Package 0 amendments, especially prospective-exception sections 4–7 |
| Package 0 phase/execution state | Phase 1 NO-GO; Phase 2 HOLD; execution allowlist EMPTY until their own separately authorized gates and decisions are satisfied | CONTRACT: prospective-exception section 7 |
| SEC-003 / Stage 1B | OPEN / NO-GO | CONTRACT: Outstanding gates and retained governing status; current owner task |
| R2 / Tier 3 | R2 UNCHANGED in full wherever originally applicable: C1–C12, all 30 C12 cases and native qualification; not qualified by Tier 1 adoption or this review | CONTRACT: Authority, applicability and incorporated R2; prospective adoption record |
| Tier 2 | Requires its own separately reviewed/adopted platform containment contract and native evidence; no containment qualification is credited here | CONTRACT: Assurance tiers; Trust assumptions, residual risks and outstanding Windows evidence |
| Pillow 12.3.0 / 13.0.0 | Both UNQUALIFIED; 12.3.0 pending independent security/advisory reassessment | CONTRACT and current owner task; appended efficiency amendment |
| Windows protected-runtime recovery / LPAC | BLOCKED/PARKED / UNVERIFIED/PARKED; no recovery or investigation authorized | CONTRACT: incorporated R2 and preserved status; historical locator, not a new LPAC observation |
| Tier 1 pilot / full-program execution | HOLD / NOT AUTHORIZED; full-program execution admission BLOCKED | CONTRACT: Tier 1 pilot specification and outstanding gates; current owner task |
| Implementation, provisioning, qualification | NOT AUTHORIZED; no interpreter/tool execution, installations or application solving follows from adoption | CONTRACT: prospective adoption record; current owner task |
| Resources and accounting | Existing ceilings, counters, failures and exhausted allowances unchanged; no current headroom or allocation certified | CONTRACT: outstanding gates and historical accounting limits; current owner task |

The preserved Package 0 text is not an acceptance decision or runtime allowlist.
Its permanent historical-evidence and governance-preservation disclosures,
independent packet qualification and finite-exit restrictions remain intact.
Tier labels or adoption of a prospective contract do not admit an operation.
An unresolved cross-tier applicability question must stop the dependent operation
for the exact owner decision required by CONTRACT; this packet does not decide it.

## C. Source identities and historical/current distinctions

Governing source: the complete pinned CONTRACT identified in section A, with
[AGENTS.md](../../AGENTS.md), [RUNBOOK.md](RUNBOOK.md) and
[STANDARDS.md](STANDARDS.md) at the same base. Its Package 0 and prospective
Tier 1 adoption sections are additions relative to the predecessor's source.
The predecessor's statement that the Tier 1 contract "remains PROPOSED/NOT
ADOPTED" no longer describes the pinned mainline prospective-contract status.

Let P = docs/security/sec-003/t1-linux-provisioning-draft-01/ at the pinned
mainline base. Its eight exact Git blobs matched all eight identities in
CONTRACT's "Preserved snapshot identity and provenance limitations" table.
These are Git-blob identities, not hashes of line-ending-translated checkout
files, and establish correspondence rather than original-draft fidelity.
Primary locators:

| P file | Bytes | SHA-256 |
|---|---:|---|
| draft.md | 17,974 | `8FC0714B5A8C624861609CC9A7A6B707D264ED667733AF476199DA950D785ADD` |
| preservation-manifest.json | 5,583 | `9197F04A84F53B3E193738CDCF40C8E515A875D1D2E55DDDE256CBC02CCDC2AF` |
| owner-disposition-supplement.md | 821 | `BE97DF92DB57D2C02DDC59162EF8E56B4D8E677E17B8F7FAA636EC7D69971C3C` |

P/owner-disposition-supplement.md retains its earlier proposed-status wording
and accepts only the version-specific Section 8 interface evidence. The later
mainline CONTRACT adoption record supplies the prospective adoption disposition;
the supplement is not rewritten or treated as a recovered historical message.
The preserved EDR PASS concerns prospective design, not historical fidelity,
artifact authenticity, runtime qualification or this reconciled snapshot.

Retained local R and LPAC locators in historical section 2 remain rooted in
C:/Projects/coin-analyzer, not this isolated worktree. In particular R remains
C:/Projects/coin-analyzer/build/worktrees/sec-003-1-reconciliation, recorded
base `1e4150df50815ba2f501a8d12d15acf6dd9abee4`. No retained-worktree HEAD or
retained-source fingerprint was refreshed by this reconciliation.

Mainline incorporates complete R2 as 39,704 bytes, SHA-256
`4B0FF509AAA0AC511BA1905BAFAF38306AB7B5934E1FD8289E944AD069CF2778`.
Historical local observations of R2, its manifest, the dependency contract,
authorization summary, CI design, owner-record prefixes/full file and LPAC
remain attributed to v0.1. They are not new observations of retained bytes or
independent authentication of past approvals. No original 15-section owner
authorization or historical session was recovered. The owner-record drift and
its exact-prefix review limits remain unresolved as recorded in historical
section 6. Mainline adoption does not certify those later owner-record suffixes.

The original Tier 1 draft lacks an authenticated whole-packet original digest.
Mainline accepts the preserved representation with its recorded fidelity and
durability limitations; it does not invent historical original-file fidelity.
If another task needs proof beyond that accepted prospective representation,
its exact prerequisite and owner disposition remain necessary.

## D. Freshness, review coverage and action boundary

Fresh checks in this reconciliation cover the original source fingerprints,
pinned GitHub commit/tree identity, complete intervening mainline CONTRACT,
and the eight pinned P blob identities. Historical v0.1 observations and
"remote not contacted" / "no remote refresh" statements describe its earlier
task only. No advisory refresh, runtime verification, security scan, historical
session recovery, resource accounting reconciliation or CI execution is credited.
No unchanged hash establishes current advisory safety or execution admission.

Mainline's separate design, original-final-diff and integrated-diff review
statements retain their exact recorded coverage and unresolved evidence gaps.
Draft-time "uncommitted/unpublished" and "NOT PERFORMED / NOT AUTHORIZED in this
package" statements remain verbatim records of those named packages; neither
this packet nor committed presence supplies a missing historical review receipt.
This reconciliation does not determine a new adoption/acceptance disposition for
those packages or erase their review prerequisites.

The owner reports PASS for previous source snapshot CA-OPS-EFF-001-FINAL-01.
That attribution covers the previously reviewed source pair only. It does not
cover the different mainline integration or this handoff revision. The complete
reconciled two-file snapshot requires its own independent Expert Depth Review,
with applicability, adversarial checklist, exact file lengths/SHA-256, evidence,
verdict and limitations in the separate review/receipt. Its verdict is not
preclaimed or embedded by the packet's author. Such review assesses this
reconciliation against the pinned governance; it does not qualify unchanged
runtime designs or supply missing historical final-diff reviews.

This task ends with an uncommitted reconciliation receipt. No commit, push,
PR, merge, adoption or autonomous follow-on work is authorized. A later owner
may separately authorize one bounded publication after checking exact reviewed
bytes, mainline drift, preservation and applicable gates. No publication step
begins automatically, and no runtime admission or accounting change follows.

## E. Verbatim historical predecessor — not current governance/status

The following fenced block preserves all 13,602 raw bytes of v0.1, SHA-256
`CD1D4B427C8323808CEE3936A5452ED0B90362461360548B7C7EA391F37159A8`,
without editing its B0, observations, hashes, failures or earlier dispositions.
Its present-tense claims must be read as historical. Sections A–D above are
the current reconciliation view; governing originals retain precedence.
No historical baseline is silently replaced, and the original source pair
remains unmodified in its source checkout. Final reconciled file identities
belong in the separate authorized review/receipt to avoid self-reference.

```markdown
# SEC-003 handoff packet

Packet: SEC003-HANDOFF-v0.1.
Status: PROPOSED / NOT ADOPTED.
Observation date: 2026-10-29.
Source task: owner authorization CA-OPS-EFF-001.

This is a reusable evidence locator and preservation proposal. It neither
replaces originals nor supplies execution authority. No rule adoption is
recorded here.

## 1. Repository and preservation baseline

Baseline CA-OPS-EFF-001-B0; owner supplied, current local bytes matched at
task entry.

Repository: adamo-sys/coin-analyzer.
Configured origin: https://github.com/adamo-sys/coin-analyzer.git
(configuration observed, remote not contacted).
Worktree: C:/Projects/coin-analyzer.
Branch: docs/deferred-mass-research-candidate.
HEAD and task-authorized base:
0a4a4bc8f9ae4eed0b3981d8fd1d25d4f83073e0.

Raw index: .git/index.
Bytes: 142716.
SHA-256:
9349D001EE662D1F9DE5E4918CB3C6861A738CAF04004EC55890F0DCE87E77C7.

Tracked state: exactly four unstaged modifications, no staged changes:
- ROADMAP.md
- benchmarks/bakeoff-v1/RUNBOOK.md
- capture_import/desktop_import_pipeline_selection.py
- docs/AI_TOOL_EVALUATION.md

Protected raw working-tree fingerprints:

| Path | Bytes | SHA-256 |
|---|---:|---|
| ROADMAP.md | 4817 | AB3B8FDC22C8780C97B402DAE938FD914D03CBC7AF718AF35C79BF5676F59E34 |
| benchmarks/bakeoff-v1/RUNBOOK.md | 12033 | 21BC140C24D1964F0275261F4BB99CFD34CD5C3A91825476BAC3DDF4BEE448F4 |
| capture_import/desktop_import_pipeline_selection.py | 4029 | A20B379F6F5E1935AF8BFA7E1D7CEE5DF2FBD176E7322367A3927CE27B506349 |
| docs/AI_TOOL_EVALUATION.md | 26053 | 4925A32B6AAA3360D825B894FC26FCC49274CE2A0683E6BB43FD1460ECD4A1AE |

Lengths/hashes concern raw bytes: do not normalize line endings.

This B0 describes the pre-adoption state, not the future checkout containing
this new file/amendment. It must remain historical; a future task must select
an explicitly authorized applicable successor. Untracked/private material
was not inventoried.

## 2. Governing sources and exact locations

Authority/scope:
- Current explicit bounded owner authorization plus AGENTS.md.
- docs/agent-ops/CONTRACT.md: Default Authority, Conflict Rule,
  SEC-003 Assurance-Tier Amendment.
- docs/agent-ops/RUNBOOK.md: checkpoint and independent review.
- docs/agent-ops/STANDARDS.md: Sources of Truth, Validation Truth,
  Security Review Standard.

Task restrictions prevail; unresolved contradictions stop reliance, not
trigger implied waivers. Actual state comes from current observations;
permitted behavior comes from applicable governing contracts; exact-head CI
controls merge readiness when authorized. This packet has no governing
precedence.

CONTRACT observed during the CA-OPS-EFF-001 task on 2026-10-29 at B0:
30563 raw bytes, SHA-256
C85398EB41E7BD2E626EA12DA058485277C6B4EB1EADB8A19F16531833A8C107.
Treat this as historical once an authorized amendment changes it.

Let R =
C:/Projects/coin-analyzer/build/worktrees/sec-003-1-reconciliation.

Recorded retained base:
1e4150df50815ba2f501a8d12d15acf6dd9abee4
(current worktree HEAD not reverified in this task).

Exact retained originals/records:
- R/docs/security/SEC-003_DEPENDENCY_CONTRACT.md, especially §§1–11.
- R/.sec003-1-local/authorization.txt
  (explicitly a summary, not the complete 15-section owner authorization).
- R/.sec003-1-local/ci-qualification-design-01.md,
  especially §§4–10 and appendices.
- R/.sec003-1-local/owner-decision-record-01.md,
  especially §§1–10, D1–D10, reviewed-prefix/closure limits and D11.
- R/.sec003-1-local/contracts/SEC0031_R2_APPROVED.txt and
  SEC0031_R2_APPROVED.manifest.json.

R2 is 39704 bytes, SHA-256
4B0FF509AAA0AC511BA1905BAFAF38306AB7B5934E1FD8289E944AD069CF2778;
bytes observed during the CA-OPS-EFF-001 task on 2026-10-29 match the
incorporated identity. Complete C1–C12 prose and all
30 C12 cases control wherever applicable; read the full original when the
task requires it. This packet is no substitute.

Manifest: 7939 bytes, SHA-256
2BFCD9FF5BB7DD9551BC39889312687C52F35B4A1D77C4568C0617EDD03546D6.
Its provenance assertions are retained attribution, not a new historical
authentication. Do not open referenced historical sessions under this packet.

Let P = docs/security/sec-003/t1-linux-provisioning-draft-01/.

Exact files:
README.md, draft.md, evidence-matrix.md, edr-report.md,
section-8-static-verification.md, manifest.json,
preservation-manifest.json and owner-disposition-supplement.md.

P/preservation-manifest.json is 5583 bytes, SHA-256
9197F04A84F53B3E193738CDCF40C8E515A875D1D2E55DDDE256CBC02CCDC2AF.
Its seven content-file fingerprints matched local bytes observed during the
CA-OPS-EFF-001 task on 2026-10-29. It records
preservation correspondence, not original-draft fidelity.

LPAC disposition:
C:/Projects/coin-analyzer/build/worktrees/sec-003-lpac-feasibility/docs/security/SEC-003_LPAC_PARKED.md

4288 bytes, SHA-256
57357EF34BC895E3679441C1411550440BD13DC9743691560D7CF7E3E82CCE46.

## 3. Current restrictions

SEC-003 OPEN.
Stage 1B NO-GO.
R2 UNCHANGED.
Pillow 12.3.0 UNQUALIFIED pending independent security/advisory reassessment.
Pillow 13.0.0 UNQUALIFIED.
Full-program execution admission BLOCKED.

Windows protected-runtime recovery BLOCKED/PARKED.
LPAC UNVERIFIED/PARKED.
Tier 1 pilot HOLD/NOT AUTHORIZED.
Native Windows 11 24H2 x64 qualification remains mandatory and outstanding.

Tier labels, documentation review, hash matches and static interface
verification provide no runtime qualification, security closure or admission.
Applicable independent final-snapshot review and exact owner approvals remain
required. No acquisition, installation, execution, retry or follow-on authority
follows from recorded historical authorizations.

## 4. Accepted findings and feasibility limits

The P/owner-disposition-supplement.md accepts only the read-only
version-specific §8 verification of flags, exit semantics and machine-readable
schemas for selected uv 0.13.5, pip 26.2.2 and pip-audit 2.10.1.

This does not qualify tool artifacts, complete closures, bootstrap or runtime
behavior. The preserved EDR PASS concerns prospective design;
SEC003-T1-LINUX-PROVISIONING-DRAFT-01 remains PROPOSED/NOT ADOPTED.

LPAC parking records successful profile APIs and Job Object
configuration/readback, but failed worker launch, no observed effective LPAC
token and no demonstrated enforcement. Accepted disposition is
UNVERIFIED/PARKED, not successful containment or proof of impossibility.
No further investigation is admitted.

Current CONTRACT records a limited three-tier architecture/prerequisite
amendment. Its exact applicability limits remain controlling: lower-tier
evidence does not satisfy global acceptance or R2 by implication.
No affirmative full-program feasibility finding is established by this packet.

## 5. Scope-and-counting proposals — NOT ADOPTED

EFF-P1: For future owner consideration, describe provisioning,
interpreter/bootstrap/tool qualification and application-profile evidence
separately. A scope label gives no exemption, new allocation or narrower
support promise. Retain complete recursive closures and all applicable
native/profile outputs.

EFF-P2: For future owner consideration, give evidence a stable identity
linking platform, interpreter, profile, input/tool revisions, attempt and
artifact/audit snapshot. Reference an unchanged result once across summaries
while preserving each required lane/outcome.

Deduplication of reporting is not deduplication of environments, attempts,
generations, machine-time or required evidence. Any execution
reuse/deduplication requires existing governing equality rules and separate
owner authority; mere version/set similarity is insufficient.

EFF-P3: Carry historical counters, failures, ceilings, uncertainty and review
coverage forward unchanged. No arithmetic reconciliation, counter correction,
refund, reset, headroom certification or resource admission is performed here.

These proposals do not adopt earlier unspecified proposals; no authenticated
earlier scope-and-counting proposal was identified in the bounded source reads.

## 6. Unresolved source dependencies and smallest resolutions

Complete original 15-section owner authorization:
authorization.txt calls itself a summary. Do not treat it as the original or
revived authority. A future task needing original terms must receive an
owner-designated authenticated complete source or new complete bounded
authorization. No session recovery is authorized.

Original Tier 1 draft fidelity:
P describes conversation-derived transcriptions, not authenticated original
Codex bytes; no whole-packet historical digest. If original fidelity is
required, owner must separately designate/provide the authenticated original
or explicitly disposition that fidelity requirement. Preserve the existing
copy and caveats.

Owner-decision record drift:
Older P/edr-report.md inventories 47517 bytes, SHA-256
32CC8943307B5DC41C90F3FEC42281781D24193DEF5C162AD171C3F399FF98D6.

The file observed during the CA-OPS-EFF-001 task on 2026-10-29 is
49411 bytes, SHA-256
A6CB66F93BAD8F000E14D37679D4E8E33EE8B070DD5F095F6EDD03B424F49DD4.

The first 47517 bytes observed during the CA-OPS-EFF-001 task on
2026-10-29 match that older identity; suffix includes D11.
The earlier independently reviewed prefix is only [0,36456), SHA-256
39FD521DC3E32B4A73A54887F534920C903A7CF1DEFE9D10102F1610CA90D9F4,
also matched.

These matches prove correspondence, not independent review or authorization
of later suffixes. Use committed P/owner-disposition-supplement.md for its
narrow recorded disposition; obtain exact-snapshot independent review/owner
disposition if reliance on later record bytes requires it.

Root docs/security/SEC-003_DEPENDENCY_CONTRACT.md is unavailable at that root
location; the governing CONTRACT explicitly locates the retained copy under R.
Use the named retained copy within authorization; do not ask for a baseline
already present or invent a replacement.

Artifact/upstream authenticity, tool closure/audits, Pillow reassessment,
native/R2 evidence, complete current resource reconciliation and execution
admission remain unestablished. This packet does not resolve them or request
their investigation.

## 7. Provenance and freshness

B0 comes from the current owner's prompt and matched local observations
made during the CA-OPS-EFF-001 task on 2026-10-29;
no signature or independent historical authentication is claimed.

As observed during the CA-OPS-EFF-001 task on 2026-10-29, retained dependency
contract, authorization summary, CI design, R2 and R2 manifest matched
identities in the preserved EDR inventory; the owner-record
prefix/full-file distinction is above.

This task read relevant governance/record portions and fingerprinted R2;
it did not repeat a complete R2/source/implementation review or authenticate
historical approvals. Prior EDRs retain exact reviewed-snapshot coverage and
never transfer to new prose or suffixes.

Local bytes, remote repository identity, artifact origin, advisory freshness,
review, adoption and execution authority are separate claims. No remote/CI/
advisory refresh or runtime verification was performed. An unchanged hash
cannot establish current advisory safety.

No independent verdict is embedded into this packet by its author; reference
the separately returned current proposal EDR by snapshot ID if authorized to
preserve it later.

## 8. Updating without erasing evidence

Update only under separate exact-file owner authorization. Preserve existing
sources/manifests and original byte identities; do not rewrite old
dispositions, failures or fingerprints.

Append dated revisions naming predecessor, authority, changed claims, new
source identities, freshness and exact review coverage. If a current-view
section changes, retain its predecessor verbatim in version history or an
explicitly authorized immutable snapshot; Git history alone cannot preserve
never-committed bytes.

Record baseline successors separately; never silently make observed drift
the expected state. Keep the packet/manifest's own digest in a separate
authorized review/publication record, avoiding self-reference.

Review the final exact snapshot; design EDR is not final-diff EDR.
Updating is not adoption, publication or runtime admission.

## 9. Compact new-thread procedure

1. Read the new bounded owner task, applicable packet revision and controlling
   governance. Select its applicable owner-designated baseline; do not assume
   B0 remains current.

2. Verify repository/worktree identity, branch, HEAD/base, raw index, tracked
   staged/unstaged state and exact protected fingerprints at entry. Avoid
   untracked/private traversal; use read-only Git/no optional locks where
   available. Stop on mismatch without repair, fetch or baseline replacement.

3. Read only originals and relevant sections needed for the next authorized
   action. Authenticate applicable identities/provenance; separate available
   evidence from insufficient evidence. Reuse prior results only for unchanged
   applicable predicates; refresh required fresh evidence.

4. Report baseline ID, checks performed, match/delta, unchanged restrictions,
   exact blocker and smallest resolution. Preserve any contract-required full
   evidence. Do not recursively investigate or turn the packet into authority.

5. Verify preservation again at exit and required checkpoints; leave a concise
   authorized handoff with objective, worktree/branch/HEAD/base, exact modified
   paths, evidence/checks, blockers, next authorized action, publication and
   stop conditions. If no further action is authorized, state NONE and stop.
```
