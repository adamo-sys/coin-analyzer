# Collection Management V1 audit and disposition

## Contract and baseline

- GOAL: Audit the existing manual collection lifecycle and correct reproduced
  P0/P1 identity or selection failures in one reviewable slice.
- IN SCOPE: `coin_collection_gui.py`,
  `tests/test_collection_management_workflow.py`, and this report; synthetic
  tests, independent exact-commit review, commit, push, and one PR.
- OUT OF SCOPE: Autosave, migrations, storage backends, bulk deletion, unrelated
  features/refactors, filesystem qualification, environment repair, and merge.
- PROTECTED BOUNDARIES: Explicit Save, stable identity and provenance,
  local-first persistence, private records/photos, unrelated modifications,
  existing frozen contracts, and Phase 2 HOLD.
- ACCEPTANCE GATES: Reproduction before correction, focused/native workflow and
  integrity checks, Ruff, bounded Pyright, whitespace, one full regression capped
  at 30 minutes, independent exact-commit review, and hosted CI reporting.
- STOP CONDITIONS: Governance ambiguity, protected-state compromise, unauthorized
  destructive operations, architecture conflict, blocking validation/review
  findings, exceeded authority, and repository context limits.

Fetched `origin/main` and verified PR #425 as MERGED at base
`db55dba46d5fbb27595ba85660948cecadbff3e5` (2026-10-21T00:50:20Z).
Worktree: `C:\Users\adamo\.codex\worktrees\collection-management-hardening\coin-analyzer`.
Branch: `fix/collection-management-hardening`. The delivery commit is recorded in
Git/PR metadata; embedding its own SHA in this file would be self-referential.
No open collection-management PR overlapped this slice at baseline inspection.
Existing historical collection-search/edit/first-save worktrees were not reused.

The primary checkout remained on `docs/deferred-mass-research-candidate` at
`cb54d10dd19b2c023c1f73344234358df5d802b7`. Its four tracked modifications are
`ROADMAP.md`, `benchmarks/bakeoff-v1/RUNBOOK.md`,
`capture_import/desktop_import_pipeline_selection.py`, and
`docs/AI_TOOL_EVALUATION.md`. Their initial aggregate Git-diff fingerprint was
`6f8721266b58be2f085c72f535926b30a8f05763`. This is a comparison fingerprint,
not a raw-byte preservation receipt or historical qualification result.
No private records, backups, notes, exports, photos, or retained qualification
artifacts were inspected. No protected worktree was modified.

## Persistence authority and qualification

`CoinCollection` owns loaded exact-byte baselines, uses the package-import lock,
rejects stale storage without writing, publishes through `atomic_json`, and
advances its baseline from the publication receipt. CRUD rollback and
`CollectionItemReference` protect deferred editing. The ordinary baseline
contract and material saved-identity correction policy remain governing.
The frozen durable-persistence source has SHA-256
`A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`
when measured with repository LF bytes (the Windows checkout uses CRLF).
No architecture or persistence implementation was changed.

Current mainline governance records **Package 0 BLOCKED; Phase 1 NO-GO;
Phase 2 HOLD; execution allowlist EMPTY**. Option B first-save changes remain
PROPOSED, not adopted. Historical evidence gaps and the known governance
preservation discrepancy remain unresolved by this assignment. No new
qualification evidence or phase-advancement authority was supplied or inferred.
The protected first-save worktree and retained evidence were not requalified.

Ordinary synthetic save/reopen tests establish only the exercised application
behavior. In particular, the existing first-coin photo test references original
synthetic files; it does not qualify managed first-save media durability,
source disappearance, Windows NTFS exclusivity, crashes, power loss, source
coherence, orphan retention, or resource limits.

## Workflow audit

VERIFIED below means automated synthetic service/controller or native Tk
programmatic evidence for the stated behavior. Physical input, packaged startup,
and visual acceptance are separately UNVERIFIED.

| Scenario | Baseline disposition | Final disposition and evidence |
| --- | --- | --- |
| Add manually | VERIFIED | `test_first_coin_workflow`: explicit entry/Save, generated photos, distinct stable IDs, no recognition/network requirement. |
| Search/filter entries | VERIFIED | `test_collection_search`: literal case-insensitive substrings, order, total/matching counts, empty/no-match states, and native Clear/focus behavior. No new filter semantics. |
| Select and inspect details | DEFECTIVE | VERIFIED after correction: exact retained reference required; native numeric-looking ID `001` opens its own details. Stale/unmapped rows open nothing. |
| Open selected editor | DEFECTIVE | VERIFIED after correction: selection cannot silently retarget a replacement object, collection instance, ambiguous ID, or failed-load collection. |
| Edit country/denomination/year/grade/notes/type-design | VERIFIED for current ordinary IDs | VERIFIED: native draft/save/reopen checks, identity-correction history, dependent metadata invalidation, and independent second-record preservation. Numeric-looking selection is corrected. |
| Edit other supported acquisition fields | VERIFIED | Existing acquisition tracking/parser and type/design suites check exact round trips, currency/date/money rules, and invalid-update rejection. New native invalid-price case retains draft and writes nothing. |
| Change selection with unsaved edits | VERIFIED in audited programmatic transition | Native test switches list selection while the original editor stays open; draft and bytes remain unchanged, then Save affects the original record only. Normal editor uses a Tk grab. |
| Clear search while editing | VERIFIED | Native test filters to no matches then clears; editor values and bytes remain unchanged until explicit Save. |
| Save edited record | VERIFIED | New native journey plus existing first-coin/material-correction suites exercise Save, reload, field values, history, identity and other-record preservation. |
| Invalid/incomplete inputs | VERIFIED for tested policy | Invalid acquisition input retains editor and storage; existing tests reject invalid dates/money/enums/ID changes. Incomplete identity is allowed and remains partial/unidentified; custom identity strings remain permitted. |
| Stale selection | DEFECTIVE | VERIFIED after correction across reload, replacement, collection switch, duplicate ID, failed load, missing row authority, and post-confirmation reload. |
| Stale writes | VERIFIED | Existing stale-baseline suite rejects an independent writer; editor keeps draft. New native case rejects Save after reload invalidates its reference. No retry, merge, or implicit reload added. |
| Reopen/reload state | VERIFIED for ordinary synthetic storage | Existing first-coin and new editor journeys reload through `CoinCollection`; published records and stable IDs survive. |
| Filesystem first-save qualification / Phase 2 | BLOCKED | BLOCKED / HOLD unchanged; unit tests and temporary file I/O do not supply qualification. |
| Physical-input and visual acceptance | UNVERIFIED | UNVERIFIED; no physical mouse/keyboard session, visual inspection, or packaged startup was performed. |

## Confirmed defects and corrections

1. **P0, wrong-record deletion after stale selection.** Details, Edit, and Delete
   read the displayed ID and called current `get_item`/`delete_item` instead of
   honoring the display-time reference. A synthetic reload during delete
   confirmation demonstrated actual deletion through the stale action; replacement
   and duplicate-ID cases exposed the same lost authority. Delete now requires
   the retained reference before confirmation and resolves it again afterward.
   A changed reference writes nothing and requests current selection.
2. **P1, stale edit retargeting.** Old rows could open an editor for a newly loaded
   or replaced object with the same ID, manufacturing fresh edit authority from
   stale selection. Details had the same retargeting defect. Both now use the
   shared guarded selection helper and refuse stale/unmapped references.
3. **P1, numeric-looking IDs inaccessible through native list actions.** Native
   Treeview value conversion can yield an integer for a string ID such as `001`;
   lookup by the display value fails. Runtime references preserve the original
   exact ID. A real Tk details/editor test covers this behavior.

These are one cohesive selection-authority correction. The existing single-item
Delete control retains its explicit confirmation and ordinary persistence guard;
no bulk-delete behavior is added. No service, schema, storage, identity policy,
photo ingestion, or provenance policy was changed.

## Validation and review

- Baseline focused suite: 61 tests run, 59 passed, 2 opt-in Tk skips.
- Red reproduction after fixture isolation correction: 6 tests, 17 expected
  assertion failures against unchanged production; no test errors. Initial
  fixture isolation errors were corrected before implementation.
- Green selection suite: 6 passed; expanded suite: 9 passed, including 3 real
  Tk tests. Final focused and boundary results are recorded below.
- Root Ruff syntax scan passed. New test file passed configured Ruff after import
  ordering correction. CI's 11-file Pyright boundary passed with zero errors;
  the new test file passed Pyright after test-double typing/optional-value fixes.
- Final focused run: **205 tests passed, no failures or skips**, in 37.152s,
  with `RUN_WORK_QUEUE_NATIVE=1`. Modules: the new workflow, first-coin,
  collection search/resume/native, edit suggestions, saved identity correction,
  type/design persistence, stale baseline, acquisition GUI/tracking, multi-photo
  GUI, collection integrity, persistence manager, durable persistence
  contracts/services, CSV identity/staleness, privacy, evaluation, and Work Queue
  foundations. Four native Tk cases are in the new ten-test module.
- An in-memory probe of the exact base Details callback reproduced the native
  numeric-ID failure. No production file was changed by that probe.
- One capped full regression completed successfully: process exit 0, 1043.001s
  wall time; unittest reported `Ran 6357 tests in 1027.907s` and
  `OK (skipped=30)`. This is the observed local run, not a repository-wide test
  inventory or hosted CI result. The runner emitted an aggregate skip count;
  individual skip reasons were not retained by its default output.
  The production fix was unchanged throughout. This run began before the final
  invalid-acquisition test and test-only typing/assertion cleanup; the final
  test module was separately rerun afterward: **10 passed**, no skips, in
  1.810s, with Ruff and Pyright passing. The unchanged full command was not rerun.
- Whitespace checks passed. Local Gitleaks scan of the implementation commit
  (`base..57c65e80a05b169ae65a97c546fb033a2204d1e8`) found no leaks; hosted
  full-history Gitleaks remains a separate CI gate.
- Independent reviewer `/root/collection_exact_review`: **PASS WITH NOTES**, no
  blocking findings, for base `db55dba46d5fbb27595ba85660948cecadbff3e5` to
  implementation commit `57c65e80a05b169ae65a97c546fb033a2204d1e8`.
  Coverage: the complete three-file diff, retained reference construction and
  resolution, editor Save authority, ordinary deletion/rollback, and report
  claims. Its own test execution had 6 passes and 4 native skips because Tcl
  initialization was unavailable in the sandbox; an escalated retry awaited
  approval and was aborted. It did not independently rerun the parent's native,
  focused, static, Gitleaks, full-regression, or historical reproduction evidence.
  No severity/file-line corrective findings were returned. This documentation-only
  evidence successor requires final exact-head confirmation in the PR/task record
  before publication; no review/merge authority is inferred from a pending request.
- The primary checkout's tracked paths and aggregate diff fingerprint still
  matched the initial observation after validation. No protected worktree was
  mutated or requalified.

## Remaining acceptance and prioritized backlog

- **P1 acceptance:** Physical mouse/keyboard journeys for selection, modal editor,
  Cancel, Save, invalid acquisition, and visible error handling remain unverified.
  No production-ready disposition is made without that evidence.
- **P1 qualification dependency:** Resolve separately authorized first-save
  governance/feasibility/resource/source-coherence prerequisites before any phase
  advancement. This PR carries no authority to perform that work.
- **P2 usability follow-up:** Visual layout, actual focus ergonomics, native file
  picker, and packaged process restart require owner/manual acceptance. Native
  programmatic checks do not replace those observations.
- No additional confirmed P0/P1 defect is deferred within the audited slice.
  This is bounded coverage, not an exhaustive proof against all concurrency or
  arbitrary external-writer races.

Publication, exact reviewed head, reviewer verdict, and hosted CI status belong
in the final task/PR record. No merge is authorized. Phase 2 HOLD and protected
modifications must remain unchanged at closure.
