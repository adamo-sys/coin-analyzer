# Legacy backup security hardening, Phase 1

Status: PASS WITH NOTES after resumed final validation and bounded independent
review on 2026-10-22 UTC. No blocking defect identified in the reviewed snapshot.
This is not production security acceptance or filesystem qualification.

## Authority and reproducibility

- GitHub `gh api repos/adamo-sys/coin-analyzer/git/ref/heads/main --jq .object.sha`
  returned `9e9281fe528abe3861630183a7efa4660be58557` on 2026-10-21.
- Base and worktree HEAD initially equal that SHA; no fetch was needed.
- Branch: `security/sec-001-002-phase1`.
- Worktree: `C:/Projects/coin-analyzer/build/security-hardening-phase1` (ignored).
- Primary branch/HEAD: `docs/deferred-mass-research-candidate`,
  `cb54d10dd19b2c023c1f73344234358df5d802b7`.
- Primary protected modified paths: `ROADMAP.md`, `benchmarks/bakeoff-v1/RUNBOOK.md`,
  `capture_import/desktop_import_pipeline_selection.py`, `docs/AI_TOOL_EVALUATION.md`.
  No primary source or untracked/private material was edited or inspected.

Task contract:

- GOAL: Reproduce and remediate SEC-001/002 in legacy backup verification/restore.
- IN SCOPE: `backup_manager.py`, `test_backup_security.py`, this report;
  bounded implementation, synthetic testing, independent review, conditional local commit.
- OUT OF SCOPE: Dependency/CI/configuration changes, unrelated cleanup, publication,
  SEC-003 implementation, and frozen persistence changes.
- PROTECTED BOUNDARIES: Primary checkout, private/frozen evidence, local-first
  behavior, existing legitimate backup format and public API.
- ACCEPTANCE GATES: Reproductions, focused/affected checks, feasible broader
  regression, adversarial review, exact file-scope verification before local commit.
- STOP CONDITIONS: Task/user and repository governance stops, including unsafe
  testing, owner-dependent compatibility changes, and unresolved blocking review.

The audit's original retained artifact was not provided or inspected. SEC IDs
here refer to the user's descriptions; reproductions are independent synthetic
evidence rather than claims about the original audit's execution.

## Evidence and threat boundary

Attack prerequisite: a collector selects an attacker-controlled legacy backup
and confirms restore. Existing verification is not authenticity verification:
an attacker can recompute checksums. Filesystem substitutions additionally require
write access to the restore namespace. No real backups, photos, records, or
credentials are used.

Baseline command (configured interpreter, Windows 10, Python 3.14.6):

```text
C:/Projects/coin-analyzer/.venv/Scripts/python.exe -m unittest test_backup_manager
26 tests, OK
```

Synthetic baseline evidence before production edits:

```text
...python.exe -m unittest test_backup_security -v
9 tests, FAILED (29 failing subcases)
...python.exe -m unittest test_backup_security.BackupSecurityTests.test_traversal_restore_preserves_root_sentinel -v
FAILED: b'replacement' != b'sentinel'
```

The first run's subcase assertions often stop at acceptance by verification;
they do not individually prove a successful write exploit. The separate
traversal test does prove an unintended overwrite.

| Concern | Baseline evidence / coverage |
| --- | --- |
| `..` components | Confirmed unintended overwrite of a temporary root sentinel via `collection_data/app_state/../../sentinel.txt` |
| String prefix lookalikes/subtrees | Restore selection accepted paths outside the intended known-file set; synthetic restore test fails |
| Drive/UNC/separator/absolute/device/ADS names | Unsafe forms accepted by verifier; acceptance alone does not establish Windows write impact |
| ZIP symlink metadata | Verifier accepted it; legacy restore writes bytes rather than extracting a native symlink |
| Existing destination link | Synthetic directory-link test failed because restore followed it; fixture uses symlink or Windows junction fallback |
| Duplicates, aliases, file/directory conflicts | Verifier accepted synthetic conflicting entries |
| Resource budgets | Small fixtures with reduced test limits were accepted; no actual exhaustion payloads created |
| Corrupt archive/checksum failure | Existing behavior rejected; sentinel preservation retained |
| Substitution/race/rollback | New deterministic fault-injection coverage; continuous adversarial scheduling is not qualified |

## Security design and compatibility

The existing manifest and `BackupResult` public interfaces remain. The writer
still emits DEFLATE ZIPs. Optional historical disclosure/coverage fields and
empty/missing checksums remain supported; checksums provide integrity only.
Supplied file lengths/checksums must be well-formed and agree with actual bytes.

Verification copies a bounded regular archive into an anonymous temporary file,
then validates and stages from that snapshot. Restore never reopens the input
pathname. An attacker changing the source during copying can only produce a
different snapshot which must itself pass verification. This is not signature
authentication. The original is also preflighted before copying, so an obviously
over-budget index is rejected before the snapshot copy.

Before `ZipFile` allocation, a bounded EOCD and central-directory walk checks
metadata size and actual entry count, including dishonest advertised counts.
ZIP64 locators are rejected at their absolute position before the classic EOCD,
even when hidden inside another entry's comment or before a maximum-length ZIP
comment. This prevents the reader from selecting an unchecked alternate index.
Before member reads, all names, types, declared sizes and ratios are checked.
Every member (including unlisted members) is streamed once for integrity;
actual stream bytes enforce both individual and total budgets. Only the bounded
JSON manifest is materialized in memory. Restore payloads stay in temporary files.

Names must use portable NFC path components, with no empty/dot/dot-dot components,
backslashes, drive/ADS colons, controls, Windows device names, trailing spaces/dots,
case aliases, duplicate names or file/directory conflicts. No percent-decoding or
path normalization is performed. ZIP symlinks/special entries are rejected.

Destination selection compares tuples against exactly:

- `data/collection.json`
- `collection_data/app_state/app_state.json`
- `collection_data/app_state/collection_snapshots.json`
- `collection_data/app_state/confirmed_observations.json`

Other safe archive members remain verifiable and are reported skipped on restore,
including workbooks/release documentation and unknown app-state subtrees.
The current writer produces only those four restore targets. It does not produce
arbitrary app-state descendants. Restricting accidental restoration of unknown
files is intentional; no sampled private archive compatibility claim is made.

Native held-directory primitives are reused without changing the importer or
frozen persistence contract. Existing destination links/reparse points, wrong
types and hard links are rejected. Windows ancestor handles deny delete sharing;
backup-specific handle-relative native renames disable replacement. POSIX uses
existing relative no-replace rename primitives. Random temporary names and
exclusive creation prevent collisions. A competing destination is never replaced.

All payloads stage before publication. A uniquely named, successful pre-restore
backup is required. Existing objects are held after that backup's readers close,
displaced into temporary names and preserved until all publications succeed.
Caught failures attempt reverse rollback using no-replace operations. Ambiguity
preserves artifacts and reports incomplete rollback. Cleanup never recursively
removes directories; empty directories created during planning may remain.

Microsoft's [sharing contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
and [native rename structure](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information)
explain why target-directory write sharing is needed and delete sharing can be
withheld. The native rename layout follows the repository primitive with
`FILE_RENAME_REPLACE_IF_EXISTS` disabled. This needs independent review and
platform testing, not trust based on a static match.

## Resource policy

| Budget | Default | Rationale |
| --- | --- | --- |
| ZIP entries | 4096 | Far above the writer's four state files plus workbook/release documentation; bounds metadata/object count |
| Central-directory bytes | 8 MiB | Bounds `ZipFile`'s metadata allocation, independently of dishonest entry count |
| JSON manifest | 4 MiB | Generous for thousands of bounded records; caps JSON allocation |
| JSON nesting | 64 containers | Checked on bounded raw bytes before the JSON parser allocates nested objects |
| Individual expanded file | 512 MiB | Allows large JSON/workbook copies while bounding one member |
| Total expanded bytes | 2 GiB | Bounds verification/decompression work and staged data |
| Compressed archive / actual copied bytes | 1 GiB | Bounds snapshot disk use and input consumption |
| Expanded/compressed member ratio | 2000:1 | Accommodates highly repetitive legitimate DEFLATE JSON; size budgets provide the primary amplification defense |
| I/O chunk | 64 KiB | Bounded member/input read requests and copying |

Limits are fixed module policy, not manifest-controlled or user-disableable.
No actual resource-exhaustion experiment was run. Tests lower limits over small
fixtures. Peak temporary disk use includes the archive snapshot, staged payloads,
destination staging, displaced originals and the existing pre-restore backup;
this is bounded per input but not a free-space reservation or process quota.

Intentional fail-closed restrictions: over-budget backups, multi-disk/end-record
ZIP64/SFX archives, encrypted or non-STORED/non-DEFLATE members, directory entries,
malformed manifests and nonportable/colliding names. These are not produced by the
current backup writer within the stated budgets. Small force-ZIP64 local headers
remain supported by the standard reader. Larger legitimate backups require a
separately reviewed policy change, without inspecting private material here.

## Validation ledger

All commands run from the isolated worktree. Native directory access requires
an elevated sandbox permission run; this is not Windows administrator elevation.

| Command | Result |
| --- | --- |
| `...python.exe -m unittest test_backup_manager` (base) | 26 tests, OK |
| `...python.exe -m unittest test_backup_security -v` (base) | Expected failures, described above |
| `...python.exe -m unittest test_backup_security test_backup_manager` (intermediate) | 42 tests, OK, 5.547 seconds |
| `...python.exe -m ruff check backup_manager.py test_backup_security.py --select E9,F63,F7,F82` | Passed, including after ZIP64 correction |
| `git diff --check` | Passed |

Here `...python.exe` is exactly
`C:/Projects/coin-analyzer/.venv/Scripts/python.exe`. Final combined command:

```powershell
C:/Projects/coin-analyzer/.venv/Scripts/python.exe -m unittest test_backup_security test_backup_manager test_collection_integrity test_collection_snapshot test_collector_companion_readiness test_collector_home_dashboard test_photo_assisted_entry test_confirmed_observations
```

Result: 121 tests, OK, 10.352 seconds. No skips in that Windows run. Includes
24 security tests, the 26 unchanged backup tests, and 71 affected-boundary tests.
The Windows ancestor-rename attempt was blocked during publication. Additional
tests cover hard links, destination substitution before mutation, default-ratio
compatibility, force-ZIP64 local headers, corrupt member data, deep JSON,
duplicate JSON keys and dishonest central-directory metadata.

The ZIP64 regression was first run against an incomplete tail-buffer-only fix:
the maximum-comment variant failed with `reader allocated`. Reading the locator
at its absolute offset fixed it; the direct regression then passed. It proves
rejection occurs before constructing `ZipFile`, not only after allocation.

Initial sandbox run failed while opening temporary-directory ancestry native
handles. Repeating outside the sandbox exposed real Windows sharing failures.
Those were resolved without weakening compatibility assertions: target directory
write sharing, handle-relative renames, and opening DELETE-capable original-file
handles only after the pre-backup reader closes. Initial failures are not passes.

The broader root regression has not run because it includes tests enumerating
protected local-only photograph fixtures. It was not filtered into a claimed
full pass. Affected-boundary regression has run as listed above. Independent
re-review completed on the unchanged production/test snapshot; see the resume
ledger below.
GitHub Actions was not triggered: no push/PR is authorized. CI remains unrun for
this change, and current blocking gates will be required before any future merge.

## Residual risks and qualification limits

- No crash/power-loss atomicity or durable recovery journal is added. A process
  crash between multiple publications can require manual recovery from retained
  originals and the pre-restore backup.
- A process with continuous same-user filesystem authority can interfere with
  data, reparse attributes or cleanup timing. POSIX identity checks plus unlink
  are not an atomic compare-and-delete. This boundary needs adversarial review;
  it is not claimed eliminated.
- Windows delete-denying ancestor pins are held briefly and may conflict with
  other applications. Filesystems lacking native identity/rename support fail
  closed. Windows network shares, ReFS, macOS and Linux are not qualified here.
- Disk-full, hardware failure and inability to roll back are reported failures;
  uncertain artifacts are preserved rather than recursively cleaned.
- Missing legacy hashes remain permitted for compatibility. An adversary may
  supply arbitrary allowlisted JSON bytes; this phase does not validate domain
  semantics, restore provenance or authenticity.
- Root regression is pending privacy-safe execution: some tests use the local-only
  `test_coins` photographs. No such photographs may be read under this task.

## SEC-003: separate read-only recommendation

Inspected `requirements.txt`, `requirements.lock`, dev/AI requirement declarations,
and relevant install commands in `.github/workflows/tests.yml` without changes.
The runtime manifest pins pandas `3.0.6`, while the runtime lock records `3.0.5`.
The manifest includes Flask and qrcode, which are absent from that lock. CI runtime
installs use `requirements.txt`, so the lock is not the executed dependency set.
This is confirmed declaration drift, not evidence that a specific dependency is
exploitable. No package advisory assessment or dependency upgrade was performed.

Recommend a separately authorized remediation: choose supported Python/platform
targets; regenerate runtime/dev/optional-AI locks from their authoritative inputs
using a recorded resolver version; review transitive changes and optional-feature
boundaries; decide on hashes/platform-specific lock strategy; verify clean installs
and offline synthetic smoke tests on Windows/Ubuntu; then deliberately align CI's
installation policy. Preserve a compatibility-floor job where intended. Do not
silently substitute package versions or treat lock generation alone as remediation.

## Independent review and publication

Reviewer: separate read-only agent `/root/security_review`.
Initial reviewed production SHA-256:
`0CB9CE3DCACCEA79551B819115762AB443FB2AAAD12E11F48C157F80846F09B0`.
Verdict: FAIL, one High blocker. A synthetic ZIP64 locator hidden in a decoy
central-entry comment redirected Python to a different directory after preflight.
Reviewer reproduced 4097 accepted entries against the default 4096 limit in
350319 bytes, and 114 actual directory bytes accepted under a reduced 100-byte
limit. No exhaustion attempted. Correction: reject the absolute-position ZIP64
locator before reader allocation; retain local force-ZIP64 compatibility.
Regression covers empty and maximum-length ZIP comments. The resumed independent
review confirmed resolution on the exact production/test hashes below.

Canonical Git bytes of the frozen persistence spec hash to
`A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`;
Windows checkout CRLF bytes naturally hash differently. The file is unmodified.

At the original checkpoint there was no local commit and re-review was pending.
The resumed final validation below supersedes that pending status. No push, PR,
merge, release, deployment or production configuration change is authorized.

## Original work-package checkpoint (historical)

Objective/contract: SEC-001/002 and the six fields above. Worktree branch/base
remain as recorded. Exact proposed file set: `backup_manager.py`,
`test_backup_security.py`, `docs/security/SEC-001-002-phase1.md`; no staged or
committed implementation yet. Completed evidence: baseline reproductions,
121-test Windows run, narrow Ruff, whitespace check, canonical frozen-spec hash.
Outstanding: independent confirmation of the corrected snapshot; optional existing
WSL synthetic checks; final exact scope and primary-state checks. Root/full CI
remains unrun. Next authorized action: re-review, then conditional local commit
only if no blocker remains. No publication authority. Context estimate near the
50K warning threshold; no new scope, and repository 65K/75K stops still apply.

## Resumed final verification, 2026-10-22 UTC

The existing branch, worktree and exact HEAD/base above were reverified without
fetching, switching, or creating a branch/worktree. All three worktree-byte hashes
matched the previous session's last recorded snapshot before any edit:

| File | SHA-256 at resume |
| --- | --- |
| `backup_manager.py` | `D887EFAEAFB82CEF43C89B5DC26B8858ABF1158A5606C89138701EC4970B737E` |
| `test_backup_security.py` | `42DDAD37702C49D9FC19E1529BB9FA32197E1C25FAAFA5869B47F50571FF112D` |
| This report, before this verification update | `8C54A70F894BF2844CCDDE529A28F879EDE4759A1D33C4DAC6D0F4AE7EF8020B` |

Production and tests were not edited during final verification. Only this report
was updated. Fresh commands ran from the existing worktree with the configured
interpreter `C:/Projects/coin-analyzer/.venv/Scripts/python.exe`:

```powershell
C:/Projects/coin-analyzer/.venv/Scripts/python.exe -m unittest test_backup_security test_backup_manager -v
C:/Projects/coin-analyzer/.venv/Scripts/python.exe -m unittest test_collection_integrity test_collection_snapshot test_collector_companion_readiness test_collector_home_dashboard test_photo_assisted_entry test_confirmed_observations
C:/Projects/coin-analyzer/.venv/Scripts/python.exe -m ruff check backup_manager.py test_backup_security.py --select E9,F63,F7,F82
git diff --check
```

Results: focused 50 tests OK in 7.776 seconds; affected-boundary 71 tests OK in
7.719 seconds; both exit 0 with no skips. Narrow Ruff and whitespace checks
passed. Native Windows tests used approved outside-sandbox execution, not Windows
administrator elevation. No full root regression, Linux run or GitHub CI pass is
claimed. Root discovery remains excluded because it can access protected photos;
the previous WSL dependency check failed for missing `cv2`. No dependencies were
changed.

Independent verifier: separate read-only agent `/root/final_security_review`.
Verdict: **PASS WITH NOTES**, no blocking finding identified in bounded coverage.
The verifier checked the production/test hashes above and independently passed
the ZIP64 empty/maximum-comment regression with reader construction trapped, plus
the dishonest-central-directory regression. The original High ZIP64 parsing
finding is confirmed resolved on this snapshot before reader allocation.

Review covered exact destination allowlisting, archive snapshotting, declared and
streamed budgets, member type/name rejection, link/reparse checks, Windows ancestor
pins, native no-replace publication, original retention, reverse rollback and
cleanup. Unknown safe members are verified and skipped. Existing plain, singly
linked targets are skipped with `overwrite=False`; unsafe targets fail closed.
Existing synthetic tests were examined for security and compatibility gaps.

The verifier's additional compatibility attempt failed inside the sandbox; its
requested escalation rerun awaited approval and was interrupted. It is not a
passing result. The coordinator's complete outside-sandbox focused run includes
that compatibility test and passed on the unchanged snapshot. Review was concluded
with explicit coverage and limitations after status requests and interruption;
no unfinished tool attempt is counted as evidence.

Nonblocking limitations: incomplete-rollback and retained-original cleanup
branches were inspected but not independently fault-injected. Continuous same-user
interference, POSIX compare/delete gaps, crash recovery, disk-full behavior and
additional platforms/filesystems remain unqualified. No resource-exhaustion or
exhaustive scheduling experiment was performed. Authenticity, restored JSON domain
validity, private-archive compatibility and broad production acceptance were not
judged. The residual-risk register above continues to apply.

The final allowed commit set is exactly `backup_manager.py`,
`test_backup_security.py`, and this report. Governance, frozen persistence,
dependency and PWA files have no diff. Final comparison confirmed the primary
checkout's branch/HEAD and all four protected-file hashes unchanged from the start
of this resume. The frozen specification's canonical Git hash also matches the
governed value. No private backups, photos, records or credentials were accessed.
No unrelated files may be staged.

Scope, protected-state and whitespace checks passed. Next authorized action:
create the conditional local-only commit and record its exact SHA in the final
delivery. Its SHA cannot be embedded in its own committed report; Git commit
metadata is the durable identity. No publication is authorized. The next owner
decision is whether to authorize publication with these documented limitations;
current passing blocking GitHub gates and explicit owner approval remain required
for any later merge.
