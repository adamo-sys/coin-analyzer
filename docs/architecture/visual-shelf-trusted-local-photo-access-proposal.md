# Visual Shelf: Trusted Local Photo-Access Architecture Proposal

Status: **Non-frozen proposal; design direction accepted by the owner, subject
to qualification and final implementation approval.** Document readiness does
not mean API qualification, implementation readiness, or release acceptance.

Task baseline: `codex/visual-collection-shelf` at
`14686a03edf8656b98a850b2aab7df8ef1b34509`, worktree
`C:\Projects\coin-analyzer\build\visual-collection-shelf`.

## 1. Amendment boundary and frozen-spec protection

This proposal defines the shelf's future photo acquisition boundary. It neither
changes persistence schemas nor authorizes storage creation, migration, collection
writes, recovery changes, production code, or qualification execution.

The [frozen persistence specification](durable-persistence.md) remains authoritative
for import, managed-image publication, recovery, and durability. Its verified
committed SHA-256 is
`A77DAF73978A74A9869A4B9558ECC49A96B4AE4AD183F9D646A18CB1B7E362B4`.
The task baseline's working-file hash is
`22D881DBD666163961E5CDAC8F620FF40D6729A70CA47670875C25CC8E5C0997`;
normalizing CRLF to LF reproduces the committed bytes exactly. Neither that file,
AGENTS.md, frozen evidence, nor the seven existing shelf implementation files is
part of this amendment's edit boundary.

The frozen spec permits read-only preview to remain available in unsupported
durability environments; it does not require that availability. This proposal
narrows **shelf photo preview eligibility** without relaxing any persistence
guarantee or changing other workflows. Any implementation conflict with frozen
contracts must stop for an owner-approved amendment; this proposal is not a
general override.

## 2. Conditional guarantee and trust assumptions

The proposed guarantee is: **prevent application-directed remote photo acquisition
while browsing the shelf, under explicitly qualified trusted-storage assumptions.**
Shelf code, including background loaders and decoders, may acquire photo bytes
only from an admitted application-managed local NTFS root through retained,
verified handles. It must not resolve remote references, invoke hydration,
request provider downloads, upload photos, or delegate arbitrary photo paths to
shell thumbnail handlers, external viewers, codecs, or URL-capable libraries.

This is not a guarantee that arbitrary OS, driver, filter, antivirus, indexing,
backup, or provider network activity is eliminated. Admission and reads themselves
use OS services. Network observation can identify an application-directed failure,
but silence in one test cannot prove a universal absence of network activity.

The qualified environment must have a trusted OS and native API implementation,
a qualified local NTFS volume, an application-controlled storage lifecycle and
access policy, no synchronized/provider-managed root, no reparse traversal, and
no unaccounted writer or writable mapping. Hostile privileged software and arbitrary
kernel/filter behavior are outside this guarantee. A process running as the same
user may evade ordinary ACL separation; application-managed is a lifecycle and
qualification requirement, not proof of security isolation. If these assumptions
cannot be established, photo access is unavailable.

## 3. Root bootstrap and admission

Admission belongs to an explicit storage setup/qualification boundary, not to
shelf browsing. A string prefix, a drive letter, `resolve()`, `exists()`, a final
pathname, or an apparently local filename is not a storage trust decision.

The future admission procedure must:

1. Start from an owner-approved local volume anchor and application-owned root
   provisioned through the authorized storage lifecycle. Do not automatically
   adopt an arbitrary existing directory, user photo folder, or legacy reference.
2. Establish the anchor without traversing an untrusted drive mapping, namespace
   alias, redirector, or reparse point. Qualify the bootstrap sequence itself:
   checks performed after an unsafe root open cannot undo remote acquisition.
3. Bind directories component by component relative to retained parent handles,
   with qualified no-reparse semantics. Check every component and retain the
   ancestor chain needed to prevent namespace replacement during acquisition.
4. Verify filesystem/volume identity, directory type, reparse and cloud attributes,
   sync/provider classification, ownership/access policy, and lifecycle provenance
   from admitted objects and approved local evidence. Unknown results, unsupported
   APIs, ambiguous provider status, or concurrent changes reject admission.
5. Produce an in-memory admission token bound to root volume/file identity,
   platform/API profile, admission generation, and retained handles. Persisting a
   token or new manifest requires separate schema/write authorization. Cached
   qualification evidence alone is not authority to reopen a pathname.

Root setup must have no implicit effect during browsing. A missing root produces
unavailable previews, not creation, relocation, or repair. A fresh process must
re-establish admission; changes to volume, root identity, access policy, provider
classification, platform build, or API profile invalidate eligibility. Runtime
changes must invalidate affected work and require readmission. If continuous
provider exclusion cannot be made defensible, the environment remains unqualified.

The exact anchor bootstrap and reliable provider exclusion are unresolved
qualification questions. No Windows build is certified by this document.

## 4. Excluded storage and reference forms

Reject before photo acquisition:

| Storage/reference | Required treatment |
| --- | --- |
| UNC, SMB, WebDAV, URL and network device namespaces | No connection, existence check, metadata probe, download, or decode of the supplied reference |
| Mapped drives, including apparently local aliases | Excluded; do not infer trust from a drive letter |
| Reparse-backed paths | Reject links, junctions, mount points, and unknown reparse tags at any ancestor or leaf |
| Cloud placeholders and synchronized roots | Exclude dehydrated, hydrated, pinned, offline-available, and ordinary-looking files within such roots |
| Unsupported filesystems or devices | Exclude ReFS, FAT-family, remote/virtual redirectors, and any volume outside the qualified local NTFS profile |
| Unqualified platforms | Photo preview disabled on Linux, macOS, and unqualified Windows/API combinations |
| Paths outside admitted storage | Exclude even when the file is genuinely local and readable |

Strict relative references within admitted storage must reject absolute/device
forms, parent traversal, alternate data streams, malformed components, and
ambiguous normalization. Reject externally introduced hard-link aliases or unknown
link provenance; containment alone does not establish exclusive management of the
file object. An approved publication mechanism's use of links elsewhere does not
automatically admit them for shelf access.

Do not discover external references with filesystem calls. Classification uses
reference syntax and existing trusted admission/provenance information. A future
provider query must itself be qualified for safe use; blindly querying an external
path is not a permitted safety test.

## 5. Retained-handle acquisition and fail-closed behavior

The loader accepts an admission token and strict managed relative reference,
never a general filename to open. It binds each child relative to the retained
parent using qualified native primitives, rejects reparse/cloud/provider objects,
checks same-volume identity and regular-file type, and retains the object handles
through verification and bounded byte capture. Post-open checks complement the
safe open; they cannot substitute for preventing unsafe traversal.

Content access is read-only, without write/delete sharing where the qualified
profile requires that exclusion. Root/ancestor handle sharing must prevent
replacement across acquisition. Sharing violations fail closed; do not retry with
broader sharing, path reopening, standard-library fallback, or a remote decoder.
The precise sharing/access masks require native qualification.

Decode only a bounded immutable byte buffer captured from the verified handle.
No decoder may reopen by name, follow embedded external resources, or fetch
anything. Do not memory-map the source as a shortcut to an immutable snapshot.
Handle identity is checked against admitted volume/file IDs and verified evidence;
attribute/identity changes, truncation, missing evidence, hash mismatch, API failure,
timeout, or ambiguous classification discard the result and show a sanitized
unavailable status. Photo failure must not prevent metadata browsing.

## 6. Legacy photos and immutable browsing

Legacy/external photo references remain unchanged. The shelf shows the transient
status **"outside trusted photo storage"** when a reference is outside admitted
storage or lacks evidence of admission. The status is derived display state, not
a persisted collection field, evidence of corruption, or a declaration that the
photo is absent. Other failures within admitted storage use an unavailable/error
category appropriate to the failure.

Do not automatically migrate, copy, rewrite, hydrate, repair, replace, or substitute
a legacy photo, including substituting a different role, filename match, generated
image, or previously cached external thumbnail. An explicitly selected eligible
managed photo may be shown according to a separately approved role policy;
otherwise display a neutral placeholder. Any future migration requires an explicit
owner-approved workflow and separate privacy, provenance, persistence, and action
authority.

Opening, filtering, sorting, selecting, scrolling, decoding, cancellation, errors,
and closing the shelf must not change collection bytes, stored photo references,
managed photo bytes, provenance, journal/recovery state, or persistent thumbnail
caches. Transient verified buffers/caches may exist in memory within the limits
below. OS metadata effects such as access-time updates are outside the application
immutability claim; the application must request no content or persistence writes.

**Owner-accepted design tradeoff:** external photos have reduced preview
availability, including valid local legacy photos and fully hydrated synchronized
photos. The owner has accepted this direction subject to qualification. Final
manual acceptance of the unavailable-preview experience and final implementation
approval are required before release. This document does not record release
acceptance as completed.

## 7. Provenance, integrity, resource limits, and stale work

Expected length, SHA-256, media type, dimensions, photo role, and record association
must originate in verified managed-image/import evidence under the existing
persistence contract or a separately approved evidence mechanism. A file merely
located beneath the root is not provenance-backed. Missing evidence is reported
as unavailable; do not manufacture a digest expectation by hashing the candidate
and treating that new digest as prior provenance. SHA-256 establishes byte
agreement, not ownership, licensing, authenticity, or probability confidence.

Capture bytes through the retained handle, compute their exact length/hash, and
compare with prior trusted evidence before display. Decode that same captured
buffer and verify allowed format and dimension constraints. Do not verify one
open and decode another. Pre/post identity checks and equal metadata do not prove
absence of in-place modification; a matching prior digest plus qualified writer
exclusion is required. Pre-existing writable mappings remain a qualification risk.

Proposed finite ceilings for qualification (new browsing limits, not changes to
frozen import limits):

| Resource | Proposed ceiling and enforcement |
| --- | --- |
| Encoded photo | 41,943,040 bytes; reject oversize before allocation and enforce a cumulative read cap |
| Decoded input | JPEG/PNG only, one frame; each axis at most 12,000 and total at most 16,000,000 pixels; reject oversized headers before full decode |
| Decoder output/intermediates | Account for every allocation; at most 64 MiB per decoded image, within the total budget; no unbounded animation/metadata expansion |
| Active work | At most 2 workers and 8 queued requests; deduplicate and evict obsolete requests rather than grow a queue |
| Total photo memory | At most 256 MiB across encoded buffers, decode intermediates, results, and in-memory cache; reserve budget before starting work |
| Visible thumbnail/cache | At most 512 pixels per thumbnail axis and 64 entries, additionally constrained by total memory |
| Request lifetime | 5-second wall-clock deadline including acquisition, verification, and decode; timeout means unavailable |

Qualification must show enforceable allocation and cancellation bounds with the
chosen codec/API. If an operation cannot be safely interrupted in-process, a
qualified isolated worker with bounded memory and termination is required before
enabling it. A deadline alone does not prove native I/O has stopped. Never reuse
handles or buffers while native work still references them; an unreaped operation
occupies its slot, and repeated failures disable photo loading instead of spawning
unbounded replacements. Final values and containment policy require owner approval.

Each request carries view/selection generation, root admission generation,
record/role association, and expected identity/hash. Selection changes, refresh,
root invalidation, and closure cancel obsolete work. Late results must be discarded
before UI publication even if cancellation could not interrupt I/O. Clear obsolete
images promptly; a stale success must not replace a current placeholder or error.
Cache keys include admitted identity, digest, role/association, and admission
generation; never key trust only by pathname. Closing releases resources after
native work is quiescent. Diagnostics omit raw paths and photo contents.

## 8. Windows/API qualification requirements

The candidate target is a specifically tested Windows desktop build/architecture
on application-managed local NTFS. Minimum OS version, build range, native ABI,
library packaging, and accepted filesystem/provider configuration must be recorded
from qualification evidence before support is advertised. API presence alone is
insufficient; unknown profiles fail closed without a less-safe fallback.

Candidate primitives require qualification, not assumption:

- Microsoft documents handle-relative names using `OBJECT_ATTRIBUTES.RootDirectory`
  and rejection on reparse traversal using `OBJ_DONT_REPARSE`.
  [OBJECT_ATTRIBUTES](https://learn.microsoft.com/en-us/windows/win32/api/ntdef/ns-ntdef-_object_attributes)
- `NtCreateFile` is documented as a user-mode native open/create interface. Its
  binding, rights, options, status handling, directory-relative traversal, and
  rejection behavior require tests on each supported profile.
  [NtCreateFile](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile)
- Win32 `CreateFileW` flags and sharing rules are relevant to root handles and
  writer exclusion. `FILE_FLAG_OPEN_REPARSE_POINT` alone is not an ancestor
  traversal policy or proof that a pathname open was safe.
  [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
- The Cloud Files API exposes a path-based registered sync-root query. It is a
  candidate signal, not evidence of all third-party synchronizers or race-free
  provider absence. Do not call it on arbitrary legacy paths.
  [CfGetSyncRootInfoByPath](https://learn.microsoft.com/en-us/windows/win32/api/cfapi/nf-cfapi-cfgetsyncrootinfobypath)

Qualify volume/filesystem and remote-device checks from held objects, file IDs,
reparse/cloud attribute queries, provider admission/invalidation, sharing masks,
handle lifetime, bounded reads, cancellation, codec containment, and error mapping.
The exact safe provider-detection API sequence is an open decision. The shelf's
read qualification is distinct from the frozen persistence mutation capability
probe and cannot weaken or replace it. No import/durability qualification is
inferred from a successful photo read test.

## 9. Native synthetic acceptance matrix

All rows below are **required but unrun**. A separately authorized probe must
use exclusively generated JPEG/PNG fixtures, temporary application-owned NTFS
directories, controlled synthetic actors, and sanitized evidence. No collection,
private photos, backups, exports, credentials, or the uncertain `test_coins/` JPEGs
may be used. No real provider account or remote share is implicitly authorized.

Mocks establish control flow only. Native races/sharing require actual Windows
API execution; controlled provider/redirector fixtures require their own authorization
and isolation. An unavailable fixture yields INCONCLUSIVE for that row, never PASS.

| ID | Synthetic native scenario | Required outcome/evidence |
| --- | --- | --- |
| Q01 | Approved local NTFS root, generated image, prior fixture digest/association | Exact verified buffer displayed; identities, bounded resource use, and unchanged source/collection fixture digests |
| Q02 | Root absent, replaced, remapped, or ancestor changed during bootstrap | No implicit creation/adoption; unavailable; instrument every bootstrap open to establish no untrusted traversal |
| Q03 | UNC/SMB/WebDAV/URL, mapped-drive, device-alias and malformed reference inputs | Reject before supplied-reference I/O; sanitized call trace; native controlled redirector cases only with separate fixture authority |
| Q04 | Reparse root/ancestor/leaf, junction/mount, hard-link alias, traversal and stream names | Reject; no target-byte read; include swap races between checks and opens |
| Q05 | Placeholder variants, hydrated/pinned files, ordinary file in sync root, unknown provider result, provider registration race | No hydration/read when excluded or ambiguous; invalidate admission; provider traffic separately attributed |
| Q06 | Unsupported volume/platform/API, missing export, failed identity/attribute query | Photo unavailable with no alternate open strategy; metadata browsing usable |
| Q07 | Concurrent rename/delete/replacement, write opens before/after acquisition | Safe retained-object result only if all commitments hold; otherwise fail closed; demonstrate sharing/lifetime policy |
| Q08 | Writable mapping established before acquisition, external same-user writer, in-place mutation during copy | Establish enforceable exclusion or reject/unqualify profile; no false claim that handle sharing freezes bytes |
| Q09 | Missing/incorrect provenance, length/hash mismatch, corrupt/mismatched media/dimensions | No display and no evidence manufacture or collection repair |
| Q10 | Oversized encoded data, decompression/metadata expansion, queue flood, codec stall and I/O stall | Enforced byte/pixel/memory/work/deadline bounds; safe cancellation/quiescence; no unbounded worker replacement |
| Q11 | Rapid selection/scroll/refresh/closure and root invalidation, forced out-of-order completion | Cancel obsolete work; no stale image/cache result or use-after-close; bounded handle cleanup |
| Q12 | External legacy photo with old thumbnail, repeated browsing/errors, eligible managed comparison | Transient outside-storage status; no external access, substitution, automatic migration, persistent cache, or fixture mutation |

Retain probe revision/hash, exact OS/build/architecture, filesystem and native/API
profile, fixture provenance/digests, schedules and repetitions for races, resource
measurements, sanitized call outcomes, and PASS/FAIL/INCONCLUSIVE per row. Separate
application calls, provider callbacks, and background OS traffic when recording
network observations. Observed no traffic is supporting evidence only. Sanitized
evidence publication requires separate authority; raw environment paths and photos
are not probe artifacts for upload. A synthetic PASS bounds that tested profile;
it does not prove arbitrary filter/provider safety.

## 10. Unresolved decisions, risks, and progression gates

| Decision/risk | Required resolution before enabling photo access |
| --- | --- |
| Root bootstrap | Owner-approved anchor/provisioning policy and native evidence that initial acquisition cannot traverse an untrusted mapping/provider |
| Provider detection | Defensible exclusion of registered and non-registered synchronized roots, safe query sequence, and change invalidation; unknown means unavailable |
| Concurrency | Qualified ancestor/root sharing, publisher coordination, hard-link policy, races, and admission-generation lifecycle without changing frozen persistence semantics |
| Pre-existing writable mappings | Prove lifecycle/access exclusion or keep affected environments unsupported; sharing and hash checks alone are not a universal immutability proof |
| Cross-platform support | Linux/macOS and untested Windows remain unqualified for this photo contract; no generic path-based fallback |
| Provenance availability | Choose an existing verified evidence source or separately authorize an evidence mechanism; no fabricated expectations or schema change here |
| Resource/worker policy | Approve ceilings, codecs, memory accounting and safe containment; demonstrate native cancellation and quiescence |
| Preview availability | Final owner acceptance of external-photo placeholder experience and affected legacy cases before release |

The document may be DOCUMENT_READY while these qualification and approval gates
remain open. A separately authorized synthetic qualification probe **can proceed
as an investigation**, with this matrix and exact fixture/API scope in its task
contract. It must treat unresolved bootstrap/provider/mapping questions as subjects
to test, not as assumptions already proven. This task grants no probe execution
authority. Failure or inconclusive safety evidence blocks enabling the affected
profile and must be reported to the owner without relaxing the guarantee.

After qualification, the owner must review the evidence and resolve open decisions,
approve the final amendment/implementation contract, and separately authorize
implementation. Release requires final manual tradeoff acceptance and applicable
current CI/review gates. DOCUMENT_READY, probe PASS, or accepted design direction
does not authorize implementation, commits, publication, or release.
