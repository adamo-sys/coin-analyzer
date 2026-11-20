# A. Proposed contract: SEC003-T1-LINUX-PROVISIONING-DRAFT-01

**Status: PROPOSED / NOT RUN / NOT ADOPTED.** The following is a conversation-derived transcription for source recovery, not a certified original-byte artifact. MUST/SHALL denote proposed future requirements, not present authority.

## 1. Bounded task contract

**GOAL**

Establish reproducible, independently reviewable installation and qualification of the selected Linux interpreter and approved bootstrap/resolver/scanner closures.

**IN SCOPE**

A distinct disposable Ubuntu 24.04 x86-64 environment; approved artifact acquisition or verified reuse; static archive validation; safe installation; separately authorized interpreter execution; complete tool qualification; retained evidence.

**OUT OF SCOPE**

Application solving, lock reconciliation, pilot execution, consumer migration, repository changes, Windows/WSL recovery, Tier 2/3 claims, provider calls, production deployment, or SEC-003 closure.

**PROTECTED BOUNDARIES**

Pinned governance; original failed extraction and evidence; local-first behavior; private material; unchanged version selections, budgets, native Windows requirements, and full R2 applicability.

**ACCEPTANCE GATES**

Completed admission schedule; reviewed implementation; qualified extraction; interpreter identity/behavior; complete tool closures, reproducibility and audits; finite negative controls; independently verified final evidence.

**STOP CONDITIONS**

First material authority, identity, provenance, privacy, topology, compatibility, coverage, preservation, budget, or review blocker.

**File boundary**

This draft authorizes no file changes. Any future implementation authorization must enumerate every new source, configuration, temporary, environment, and evidence path.

## 2. Applicability and authority

This procedure governs ordinary trusted development provisioning on a separately approved Linux platform. It does not contain deliberately hostile dependency execution.

It SHALL NOT reuse, repair, relocate, execute, or claim acceptance of the failed Windows-supervised WSL extraction.

Operations within R2's original applicability remain subject to complete R2 C1–C12, all 30 C12 cases, native qualification, and separate authority.

Unresolved applicability or suspicious artifact evidence blocks admission. No operator may assign Tier 1 merely to avoid stronger controls.

Contract review, owner adoption, implementation review, acquisition/install authority, interpreter execution authority, and pilot authority are separate gates. No gate follows automatically from another.

## 3. Mandatory admission schedule

Before execution, the owner-approved schedule MUST bind:

- Exact platform/provider, Ubuntu image revision or digest, kernel, architecture, filesystem/mount configuration, native libraries, and privileged platform services.
- Workflow/control/verifier revisions, full action SHAs where applicable, extraction implementation, trusted host interpreter/stdlib, and measurement utilities.
- Exact artifact origins and identities, permitted redirects, TLS/CA policy, network phases, and request/byte limits.
- Absolute storage roots, ownership/access rules, disposable environment inventory, evidence destinations, and allowed operations.
- Independent verifier identity and measurement/access boundary.
- Finite stage deadlines; memory, disk, process, output, and evidence limits; cumulative accounting; failure-handling reserve; authorized target-specific cancellation.
- Finite acceptance/negative-control manifest and retention policy.

Any missing, unverified, or changed entry means BLOCKED before admission.

A hosted runner label alone does not establish immutable image identity.

The proposed first execution package should end after interpreter/tool preflight. Application solving requires subsequent authority.

## 4. Artifact selection and authentication

Selected interpreter:

`cpython-3.12.15+20261021-x86_64-unknown-linux-gnu-install_only.tar.gz`

Expected size: 67,908,973 bytes.

Expected SHA-256:

`5FF9F0602CE964A529ED1E8555D3ABAB6341926D724402BA9A15E9E877191124`

Preserve the conventional-GIL, non-stripped, Linux GNU x86-64 selection.

No stripped, free-threaded, musl, different release, system-interpreter, or setup-python substitution is permitted.

These are retained selections, not independently authenticated publisher evidence.

Before consumption, a separately authorized verification step MUST establish the approved upstream repository/release, asset identity, size, digest, release status, and approved source relationship.

Retained reports name release `20261021` and target commit:

`0c5e581b54a4736cdbbe68bdd6d7e571a1dca11e`

These upstream claims were not independently reauthenticated during drafting.

Retained-byte reuse requires approved access and custody verification. Reacquisition requires explicit download authority. Neither route is currently authorized.

Independently measure consumed bytes and bind verification through use to the same finalized object or verified immutable copy.

Matching publisher-controlled API and checksum endpoints are corroboration within one publisher's trust domain, not independent publisher diversity.

## 5. Filesystem and permission boundary

Use a fresh, exclusively allocated, root-controlled, non-casefolded ext4 destination on the approved Linux platform.

Exclude repository checkouts, Windows-mounted paths, the historical partial tree, shared caches, and existing user environments.

Separate namespaces as follows:

| Namespace | Required access |
|---|---|
| Policy, verifier, trusted tools | Provisioning/package workload cannot modify |
| Artifact staging | Acquisition writer only until finalized; read-only consumers afterward |
| Extraction destination | Trusted extraction writer only |
| Accepted interpreter tree | Read/execute access for approved workloads; no workload write access |
| Tool environments/temp files | Explicit per-environment writers; no shared ambient state |
| Evidence | Controlled capture, independent finalization and verification |

Create private working directories with restrictive permissions.

Apply only reviewed final modes and minimum traversal/read access.

Do not restore archive ownership blindly or permit setuid/setgid, capabilities, unexpected ACLs, or group/other write access.

Validate ancestor and object identities; use descriptor-relative, exclusive, no-follow writes. Do not validate one pathname and later consume an unrelated reopen.

These are provisioning integrity controls, not proof of containment against hostile code or privileged platform compromise.

## 6. Archive validation and extraction

Before creating payload files, validate the complete archive and link graph with the pinned trusted extraction stack.

Never use the extracted interpreter to extract or validate itself.

Retain the identified worker's exact archive policy:

| Property | Required value |
|---|---|
| Archive members | 4,536 |
| Regular-file members | 3,487 |
| Symlink members | 1,049 |
| Implied directories | 197 |
| Final filesystem nodes | 4,733 |
| Aggregate regular payload | 222,572,989 bytes |
| Largest regular payload | 119,091,144 bytes |
| Expanded tar bound | 260,000,000 bytes |
| Approved case-collision groups | Exact retained 25 groups |
| Metadata-manifest SHA-256 | `00DD2BA5AF763374C6F2954E39D32F2B084D720B0077B79BB9248F8E5338ABA8` |

The 197 directories are implied directories, not additional directory members.

Retained worker SHA-256:

`CD180665FA86898A2532352DE36B2D568EAA33CEA7C191705EEC7263A7F81E42`

Previous inspection reported matching worker bytes and inspected relevant constants/policy. No implementation or runtime qualification is claimed.

The reviewed Linux implementation SHALL preserve:

- Exact ordered metadata-manifest serialization and digest.
- Canonical ASCII paths rooted under `python/`; reject absolute, empty, dot, parent, backslash, duplicate, and ambiguous member paths.
- Exact retained metadata, permitted types/modes, payload lengths, trailer checks, directory set, and collision groups.
- Rejection of hardlinks, devices, FIFOs, sparse/PAX variants, unexpected types, and namespace conflicts.
- Exact permitted relative symlinks; no escaping, dangling, cyclic, or overlong chains. Do not replace the approved link policy with blanket link removal or dereferencing.
- Explicit `data_filter` validation at required stages, rejecting skipped members and unexpected transformations.
- Exclusive descriptor-relative creation, pinned ancestor/mount identities, complete content/link reconciliation, and a bounded member ledger.
- No execution during extraction and no continuation after filter or reconciliation failure.

Filter availability and behavior MUST be qualified for the exact trusted extraction runtime.

Python's extraction documentation warns that filters do not prevent every dangerous feature, denial of service, or concurrent namespace modification.

Reference: https://docs.python.org/3/library/tarfile.html#hints-for-further-verification

The distinct Linux implementation requires fresh source identity, independent review, and authorized qualification.

Existing source-only review does not establish execution readiness.

## 7. Interpreter execution gate

Extraction produces only a sealed installation candidate.

Before first invocation, independently confirm artifact/tree correspondence, ownership/modes, executable identities, ELF architecture, expected native dependencies, and approved invocation paths.

Static inspection must use trusted tools without invoking the candidate loader.

Interpreter execution requires separate authority.

Finite qualification must cover:

- Exact CPython 3.12.15 build, conventional GIL, ABI/SOABI, non-stripped status, and native linking.
- Required stdlib/native imports, TLS verification, certificate configuration, venv behavior, and bundled bootstrap identity.
- Rejection of ambient user-site, PYTHONPATH, current-directory, loader-path, and package-configuration injection.
- No bytecode or other writes into retained sources or the sealed interpreter tree.
- No fallback interpreter, automatic runtime download, OS-package installation, or compatibility repair.

Do not require `PYTHON.json` inside this `install_only` archive; upstream documents that install-only archives omit it.

Build evidence must use approved external records and measured contents.

Reference: https://docs.astral.sh/python-build-standalone/distributions/#install-only-archive

## 8. Bootstrap, resolver, and scanner qualification

Preserve these selections:

- uv 0.13.5
- pip 26.2.2
- pip-audit 2.10.1
- Candidate cutoff: 2026-10-23T00:00:00Z

Authenticate exact artifacts and complete bootstrap/tool closures before application solving.

Account for bundled bootstrap wheels, vendored components, transitives, native executables/libraries, and relevant managed runtimes.

Top-level version pins are insufficient.

Use separate tool environments. The scanner SHALL NOT be installed into or mutate a later application environment.

The bootstrap plan MUST identify an independently trusted initial inspection/install path.

An unqualified scanner's zero report cannot serve as its sole qualification evidence.

For each tool closure, require reviewed complete inputs, deterministic first/second generation and accepted-output replay, fresh installation from approved staged wheels without dependency fetching, inventories, metadata consistency, and strict complete audit coverage.

Source policy remains public PyPI over verified HTTPS and approved artifact hosts, with the specific interpreter-release exception.

Reject alternate indexes, unreviewed caches, VCS/editable/local/direct-URL packages, prereleases, sdists/builds, and automatic upgrades/downloads.

Enforce reviewed local artifact hashes and wheel-only installation.

Hash mode must cover the complete selected set. No unreviewed transitive fetching may repair incomplete closure.

Reference: https://pip.pypa.io/en/stable/topics/secure-installs/

Selected-version flags, exit semantics, and report schemas require verification before adoption.

This draft supplies no untested executable recipe.

**Pillow 12.3.0 remains UNQUALIFIED pending independent security/advisory reassessment.**

Historical retention preferences and this draft cannot qualify it.

Application resolving/installing remains outside the proposed first package.

## 9. Configuration, credentials, and network

Start from sanctioned sterile configuration and explicit environment-variable allowlists.

Use a fresh home, temporary directories, and empty caches.

Do not discover or dump a real user's configuration or credentials.

No provider, collection, private-index, cloud, SSH-agent, Git-store, or OIDC credentials may be accessible to package workloads.

Any unavoidable platform/control credential is an explicit owner-reviewed trusted-computing-base dependency.

Acquisition and advisory phases require separate allowlists and permissions.

Installation and interpreter/tool checks use authenticated staged artifacts with egress denied.

No TLS bypass, wildcard Internet access, unexpected redirect, fallback source, or repair fetch.

No shared/restored cache is trusted by default.

No provider call is permitted.

Verify controls with separately authorized synthetic canaries, never real secrets.

No application source export is needed for this preflight.

Any later export requires its own exact sanitized allowlist and transfer approval.

## 10. Accounting and failure handling

Before admission, reconcile cumulative historical consumption and approve finite available headroom.

Preserve the 36,000-machine-second ceiling and existing counters.

Historical preflight/recovery allowances are not reusable.

Charge approved preparation, acquisition, verification, extraction, execution, concurrency, evidence work, and failure handling according to the adopted accounting method.

Unknown consumption is not zero.

Stop substantive work at the first material failure.

Preserve primary errors, secondary cleanup errors, partial outputs, diagnostics, process/IO uncertainty, and original attempt identity.

Cancellation is limited to separately authorized, creation-bound targets.

No global shutdown, unrelated process killing, distro reset, automatic retry, alternate platform, relocation, or repair-in-place.

Rejected attempts cannot be upgraded by cleanup or a later successful attempt.

Another attempt requires new authority, identity, and remaining-budget evidence.

If no safe cancellation or retention mechanism exists, fail admission.

Timeouts do not establish hard cessation or descendant termination.

## 11. Evidence, completion, and retention

Retain an attempt-bound evidence envelope containing:

- Authority, policy/snapshot, platform, workflow/action/control/verifier identities.
- Exact artifact origins, sizes, hashes, custody, and verification observations.
- Extraction policy, member ledger, tree inventories, permissions, links, and preservation comparisons.
- Interpreter/bootstrap/tool identities, complete closures, commands, exits, timing, inventories, replay, and audit coverage.
- Expected versus observed controls, incomplete states, failures, and accounting.
- Final capture, flush, close, readback, namespace, and independent-review results.

Bound schemas, record sizes, nesting, filenames, totals, and retention periods before execution.

Reject duplicate, malformed, oversized, truncated, stale, or wrong-attempt evidence.

Preserve raw bytes; do not repair evidence or omit invalid tails.

Complete capture lifecycle before final reread/hash.

Record unavailable observations explicitly.

Flush/readback or upload acknowledgment does not prove physical durability.

The independent verifier obtains policy and expected inputs outside producer control and checks the complete retained namespace and measurements.

A second process under the producer's control is insufficient.

Same-platform privileged compromise remains outside the assurance claim.

Retention requires approved local paths, access, capacity, duration, and disposal authority.

Publication is separate.

No evidence-tree, environment, cache, interpreter-archive, protected-data, or raw application-log upload is authorized.

## 12. Finite controls and acceptance

The future qualification manifest MUST include one clean control and independently observable rejection cases for:

- Wrong artifact name, size, digest, origin, or changed identity between verification and use.
- Unsafe ancestry, filesystem mismatch, extra node, altered payload, invalid metadata, link escape/cycle, collision mismatch, or exhausted resource bound.
- Wrong interpreter/ABI/native prerequisite or ambient configuration injection.
- Missing/extra tool dependency, unapproved artifact, source build, drift, or replay mismatch.
- Partial/unsupported/skipped audit coverage, malformed response, advisory outage, or unapproved finding.
- Producer-modified expectations, forged/stale evidence, incomplete captures, cancellation, deadline, budget, or cleanup uncertainty.

Use synthetic fixtures and bookkeeping faults. Do not install malicious samples.

Before execution, enumerate exact cases, expected failed predicates, bounds, and evidence.

Missing cases block admission.

Report acquisition, extraction, interpreter, bootstrap, resolver, scanner, audits, controls, preservation, and evidence verification separately.

Unavailable prerequisites mean BLOCKED.

Violations after admission mean REJECTED.

A scoped Tier 1 result may become **T1 — ACCEPTABLE FOR OWNER REVIEW** only after every declared predicate passes and independent final-snapshot review has no blockers.

It credits only the explicitly qualified provisioning/tool scope.

No result qualifies application closures, a pilot, other Python/OS lanes, Windows, GUI/OCR, Tier 2/3, or global SEC-003 acceptance.
