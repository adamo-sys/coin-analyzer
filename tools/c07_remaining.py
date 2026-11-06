"""C07-P1 P09-P12/P14 scanner-free definitions and fail-closed adapters.

Mapping: P09/P10 map to their matrix rows and clauses 1,3,4,6;
P11 to row P11 and clauses 2-6; P12 to row P12 and clauses 1,7,8;
P14 to row P14 and clauses 6-8. Finding identity and evidence/platform
requirements apply throughout. Definitions are hypotheses, never observations.

Only inert in-memory objects and copied metadata are used. No scanner, process,
network, policy/workflow IO, retry or qualification occurs. Controls are a frozen
OFFLINE reference recipe, not an attestation about a real workflow or binary.
Synthetic failures demonstrate this adapter only. Native scanner detection,
merge traversal, config semantics, path case/topology, versions/digests, custody,
independent non-secret evidence, exact exception approval and native final review
remain unavailable. Ubuntu x86-64 and Windows 11 24H2 x64 require separately
authorized actual qualification; unsupported topology remains UNQUALIFIED.
"""

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, replace

from tools import c07_synthetic as prior
from tools.c07_findings import CRITERION_SHA256, ReconciliationError, reconcile

BASE = "25ebd93f02b58a588445c697cda410475ddbe30e"


@dataclass(frozen=True)
class Definition:
    case: prior.Case
    refs: tuple[tuple[str, str], ...]
    topology: str
    separator: str = "/"

    @property
    def snapshot_sha256(self):
        return hashlib.sha256(json.dumps({
            "base": BASE, "criterion": CRITERION_SHA256,
            "case": self.case.snapshot_sha256, "refs": self.refs,
            "topology": self.topology, "separator": self.separator,
            "history": prior.HISTORY_OPTIONS,
        }, sort_keys=True).encode()).hexdigest()


def _graph(case_id, path, topology):
    """Construct real Git objects, including empty trees and two-parent merges."""
    objects = {}

    def obj(kind, data):
        oid = hashlib.sha1(kind.encode() + b" " + str(len(data)).encode() + b"\0" + data).hexdigest()
        objects[oid] = prior.GitObject(oid, kind, data)
        return oid

    value = prior._marker(case_id)
    content = prior._source(prior._assignment(value))
    prototype = prior._case(case_id, path, (content,),
                            ((0, 41, value, prior.RULE, "control", topology),))
    objects.update((o.oid, o) for o in prototype.objects)
    full_tree = next(o.data.splitlines()[0][5:].decode() for o in prototype.objects
                     if o.kind == "commit")
    empty_tree = obj("tree", b"")

    def commit(tree, parents, label):
        data = (f"tree {tree}\n" + "".join(f"parent {p}\n" for p in parents) +
                "author C07 Synthetic <c07@example.invalid> 978307200 +0000\n"
                "committer C07 Synthetic <c07@example.invalid> 978307200 +0000\n\n" +
                case_id + " " + label + "\n").encode()
        return obj("commit", data)

    root = commit(full_tree if topology in {"root", "deleted"} else empty_tree, (), "root")
    target = root
    main = root
    refs = []
    if topology in {"root", "deleted"}:
        main = commit(empty_tree, (root,), "delete")
    elif topology == "unmerged":
        main = commit(empty_tree, (root,), "main")
        target = commit(full_tree, (root,), "side")
        refs.append(("refs/heads/side", target))
    else:
        left = commit(empty_tree, (root,), "left")
        right = commit(empty_tree, (root,), "right")
        target = main = commit(full_tree, (left, right), "merge-only")
    refs.append(("refs/heads/main", main))
    occurrence = replace(prototype.expected[0], commit=target)
    case = replace(prototype, revisions=(prior.Revision(target, None, path, content),),
                   objects=tuple(objects[k] for k in sorted(objects)), expected=(occurrence,))
    return Definition(case, tuple(refs), topology)


def build_definitions():
    """P09: each history control in both paths. P10: full finite cross-product.

    Git paths always use '/', independently of the report separator. P10's
    two case-distinct files must coexist for a native case-topology claim;
    the offline catalog does not assert any filesystem supports that topology.
    """
    result = []
    for index, path in enumerate(prior.AUTHORIZED_PATHS):
        for topology in ("root", "deleted", "unmerged", "merge-only"):
            result.append(_graph(f"P09/path-{index}/{topology}", path, topology))
        paths = (path, path.upper(), path.replace("test_", "Test_", 1),
                 path + ".bak", "nested/" + path, path.replace("e", "\u0435", 1))
        for pindex, other in enumerate(paths):
            for ending in ("LF", "CRLF"):
                for separator in ("/", "\\"):
                    cid = f"P10/path-{index}/variant-{pindex}/{ending}/sep-{ord(separator)}"
                    value = prior._marker(cid)
                    # Approved fixture AND independent same-location key, both predeclared.
                    text = prior._source(prior._assignment(prior.FIXTURE) + "\n" +
                                         prior._assignment(value))
                    if ending == "CRLF":
                        text = text.replace(b"\n", b"\r\n")
                    case = prior._case(cid, other, (text,), (
                        (0, 41, prior.FIXTURE, prior.RULE, "fixture", ending),
                        (0, 42, value, prior.RULE, "control", ending)),
                        (0,) if other == path else ())
                    if pindex in {1, 2}:
                        case = _coexisting(case, path)
                    result.append(Definition(case, (("refs/heads/main", case.revisions[0].commit),),
                                             "case-coexistence" if pindex in {1, 2} else ending,
                                             separator))
    return tuple(result)


def _coexisting(case, approved_path):
    """Encode case-distinct files together, without touching a filesystem."""
    objects = {o.oid: o for o in case.objects}

    def obj(kind, data):
        oid = hashlib.sha1(kind.encode() + b" " + str(len(data)).encode() + b"\0" + data).hexdigest()
        objects[oid] = prior.GitObject(oid, kind, data)
        return oid

    trie = {}
    approved_content = prior._source(prior._assignment(prior.FIXTURE))
    for path, content in ((case.revisions[0].path, case.revisions[0].content),
                          (approved_path, approved_content)):
        node = trie
        parts = path.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = obj("blob", content)

    def tree(node):
        data = b""
        for name in sorted(node, key=lambda n: (n + "/" if isinstance(node[n], dict) else n).encode()):
            entry = node[name]
            mode, oid = ("40000", tree(entry)) if isinstance(entry, dict) else ("100644", entry)
            data += mode.encode() + b" " + name.encode() + b"\0" + bytes.fromhex(oid)
        return obj("tree", data)

    old_commit = objects[case.revisions[0].commit].data
    commit = obj("commit", b"tree " + tree(trie).encode() + b"\n" + old_commit.split(b"\n", 1)[1])
    expected = tuple(replace(f, commit=commit) for f in case.expected)
    approved = replace(expected[0], path=approved_path, context="case-coexistence")
    return replace(case, objects=tuple(objects[k] for k in sorted(objects)),
                   revisions=(replace(case.revisions[0], commit=commit),
                              prior.Revision(commit, None, approved_path, approved_content)),
                   expected=expected + (approved,), exceptions=(approved,))


def definition_plan(definition):
    plan = prior.make_plan((definition.case,))
    row = plan["cases"][0]
    binding = hashlib.sha256((row["snapshot_sha256"] + definition.snapshot_sha256).encode()).hexdigest()
    row.update(snapshot_sha256=binding,
               baseline_execution_id=definition.case.case_id + "/B/" + binding,
               candidate_execution_id=definition.case.case_id + "/C/" + binding)
    return plan


def check_definition(definition, reports, *, supported):
    if supported is not True:
        raise ReconciliationError("topology: UNQUALIFIED")
    # Bind graph/refs/separator as well as the original occurrence definition.
    # P13 still owns occurrence, exit, status and multiplicity reconciliation.
    return prior.EngineeringResult(reconcile(definition_plan(definition), reports))


@dataclass(frozen=True)
class Controls:
    config: bytes = prior._CANDIDATE
    history: str = prior.HISTORY_OPTIONS
    version: str = prior.SCANNER_VERSION
    binary_digest: str = hashlib.sha256(b"OFFLINE synthetic binary identity only").hexdigest()
    tool_present: bool = True
    defaults: bool = True
    continue_on_error: bool = False
    early_success: bool = False
    swallow_exit: bool = False
    harness_enabled: bool = True
    tests_enabled: bool = True
    ignore_sources: tuple = ()
    publish_reports: bool = False
    permissions: str = "read-only"
    complete_input: bool = True
    required_check: bool = True


def check_controls(controls):
    reference = Controls()
    if type(controls) is not Controls or any(
        type(getattr(controls, k)) is not type(v) or getattr(controls, k) != v
        for k, v in asdict(reference).items()
    ):
        raise ReconciliationError("controls: reference recipe mismatch")


def required_check(cases, reports, controls):
    """Raise every failure through the required-check boundary; never catch it."""
    check_controls(controls)
    return prior.reconcile_synthetic(cases, reports)


@dataclass(frozen=True)
class PolicyMutation:
    name: str
    config: bytes
    controls: tuple[prior.Case, ...]


def policy_mutations():
    """P11/clauses 4-6. Disposable bytes only; never write candidate policies.

    Each mutation is paired with ALL P03-P07 cases, both paths and A/B values.
    These are independent retained-finding challenges, not claims that a native
    scanner interprets any given weakened config in a particular way.
    """
    source = prior._CANDIDATE
    variants = (
        ("whole-file", source + b"\n[allowlist]\npaths = ['tests/']\n"),
        ("global", source + b"\n[allowlist]\nregexes = ['.*']\n"),
        ("AND-to-OR", source.replace(b'condition = "AND"', b'condition = "OR"')),
        ("wildcard-value", source.replace(b"^normalized-coin-1-front$", b".*")),
        ("unanchored-value", source.replace(b"^normalized-coin-1-front$", b"normalized-coin-1-front")),
        ("broad-path", source.replace(b"^tests", b".*tests")),
        ("line-only", source + b"\n# synthetic wrapper suppression: line=41\n"),
        ("fingerprint", source + b"\n# synthetic wrapper subtraction: fingerprint\n"),
        ("baseline-subtraction", source + b"\n# synthetic wrapper subtraction: baseline\n"),
        ("cross-rule", source + b"\n# synthetic wrapper suppression: all-rules\n"),
    )
    controls = tuple(c for c in prior.build_cases() if c.requirement in
                     {"P03", "P04", "P05", "P06", "P07"})
    return tuple(PolicyMutation(name, config, controls) for name, config in variants)


def weakened_reports(mutation, reports):
    """Explicit hypothetical suppression semantics, never a scanner emulator.

    Comment-marked wrapper mutations are interpreted HERE, not by TOML/scanner.
    Counterexamples prove the reconciler rejects the stated behavior, not that
    a native scanner executes these recipes. B remains unchanged.
    """
    if mutation.name not in {m.name for m in policy_mutations()}:
        raise ReconciliationError("mutation: unknown")

    def remove(f):
        path = f["path"].replace("\\", "/")
        allowed = path in prior.AUTHORIZED_PATHS
        value = f["value"] == prior.FIXTURE
        rule = f["rule"] == prior.RULE
        name = mutation.name
        if name == "whole-file":
            return allowed
        if name == "global":
            return True
        if name == "AND-to-OR":
            return rule and (allowed or value)
        if name == "wildcard-value":
            return rule and allowed
        if name == "unanchored-value":
            return rule and allowed and prior.FIXTURE in f["value"]
        if name == "broad-path":
            return rule and value and any(p in path for p in prior.AUTHORIZED_PATHS)
        if name in {"line-only", "fingerprint", "baseline-subtraction"}:
            return rule and allowed and f["start_line"] == 41
        return allowed and value  # cross-rule exception

    result = deepcopy(reports)
    for row in result:
        execution = row["candidate"]
        execution["findings"] = [f for f in execution["findings"] if not remove(f)]
        execution["exit_code"] = 2 if execution["findings"] else 0
    return result


OPERATIONAL_FAILURES = (
    "missing-tool", "wrong-version", "wrong-digest", "invalid-config", "exit-1", "exit-3",
    "timeout", "crash", "cancelled", "incomplete-input", "parser-error", "malformed",
    "truncated", "absent-report", "missing-metadata", "snapshot-digest", "skipped",
)


def operational_failure(name, reports, controls, lane):
    """P12/clauses 1,7,8; explicitly simulated failures in either B or C."""
    if name not in OPERATIONAL_FAILURES or lane not in {"baseline", "candidate"}:
        raise ReconciliationError("failure definition: unknown")
    result = deepcopy(reports)
    changes = {
        "missing-tool": {"tool_present": False}, "wrong-version": {"version": "wrong"},
        "wrong-digest": {"binary_digest": "0" * 64}, "invalid-config": {"config": b"["},
        "incomplete-input": {"complete_input": False},
    }
    if name in changes:
        controls = replace(controls, **changes[name])
    elif name.startswith("exit-"):
        result[0][lane]["exit_code"] = int(name[-1])
    elif name in {"timeout", "crash", "cancelled", "parser-error", "skipped"}:
        result[0][lane]["status"] = name
    elif name == "malformed":
        result = {"invalid": "report"}
    elif name == "truncated":
        result = '[{"case_id":'
    elif name == "absent-report":
        result = None
    elif name == "missing-metadata":
        del result[0][lane]["findings"]
    else:
        result[0]["snapshot_sha256"] = "0" * 64
    return result, controls


def workflow_mutations():
    """P14/clauses 6-8 plus preserved publication/permissions boundaries."""
    changes = (
        ("swallowed-exit", "swallow_exit", True),
        ("continue-on-error", "continue_on_error", True),
        ("early-success", "early_success", True),
        ("event-range", "history", "HEAD~1..HEAD"),
        ("empty-rules", "defaults", False),
        ("ignore-file", "ignore_sources", (".gitleaksignore",)),
        ("inline-directive", "ignore_sources", ("inline",)),
        ("cached-baseline", "ignore_sources", ("baseline",)),
        ("harness-bypass", "harness_enabled", False),
        ("skipped-tests", "tests_enabled", False),
        ("optional-check", "required_check", False),
        ("report-publication", "publish_reports", True),
        ("permissions-widened", "permissions", "write"),
    )
    return tuple((name, replace(Controls(), **{field: value})) for name, field, value in changes)
