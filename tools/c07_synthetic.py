"""C07-P1 P01-P08 offline definitions, NOT scanner evidence or qualification.

No scanner, subprocess, network, repository IO, exception approval or native
execution occurs here. Histories are real Git object encodings held in memory;
future authorized runners must materialize fresh temporary repositories with no
remotes, hooks, templates, attributes or inherited config. Never use production
history. B and C consume the SAME objects and history selection, with only the
candidate exception disabled in B. The wrong-rule case adds the SAME synthetic
rule to both configurations, solely as a disposable qualification control.

Catalog mapping: each case's requirement names the exact P01-P08 matrix row in
the frozen criterion. P02 enumerates every current occurrence/context at the
authorized base, individually. P03-P08 explicitly cross both approved paths;
P07 substitutes each character position independently. All values are generated
from public fixed labels, have no issuer/account or service, and are inert.
That construction is not independent non-secret evidence or owner approval.

Expected B records are hypotheses to prevalidate with pinned B, NOT observations.
An undetectable control blocks that subcase; never silently drop it or infer
detection from another case. P02 source-context snippets deliberately preserve
the relevant original line, even where B detectability remains unknown. Native
column semantics must be independently established and predeclared via `columns`;
no columns, commits, paths, values or missing reports are guessed from observations.
P13 retains every supplied column and occurrence. Canonical P13 input is required:
there is deliberately no ambiguous/redacted raw-scanner-field translation here.

All return labels describe synthetic engineering only. Native Ubuntu/Windows,
binary/default-rule digests, actual B prevalidation, independent non-secret
evidence, exact exception approvals and final snapshot acceptance remain BLOCKED.
P09-P14 definitions, CI/policy deployment and SEC-003 gate changes are excluded.
"""

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from typing import Mapping

from tools.c07_findings import CRITERION_SHA256, ReconciliationError, Summary, reconcile

BASE = "c2833648c1aed392e05f816e7beeb25391c7807f"
WORKFLOW_SHA256 = "6b0c259cb3d6f773d8134f0db07614a15ccb983533187803c46289ba42af0d0b"
CONFIG_SHA256 = "0238323f4229e48dfa5f19d273b558e07fa51bad8f49656d53a415e45ddcad51"
SCANNER_VERSION = "8.24.3"
HISTORY_OPTIONS = "--all --full-history"
AUTHORIZED_PATHS = (
    "tests/test_processed_artifact_snapshot.py", "tests/test_workflow_execution.py",
)
FIXTURE = "normalized-coin-1-front"
RULE = "generic-api-key"

# Exact LF bytes of the existing candidate, not a new suppression policy.
_CANDIDATE = b'''[extend]
useDefault = true

[[rules]]
id = "generic-api-key"

# Limit the fixture exception to this exact extracted value in these two files.
[[rules.allowlists]]
description = "Known non-secret processed-artifact fixture identifiers"
condition = "AND"
regexTarget = "secret"
regexes = [
  \x27\x27\x27^normalized-coin-1-front$\x27\x27\x27
]
paths = [
  \x27\x27\x27^tests[\\\\/]test_processed_artifact_snapshot\\.py$\x27\x27\x27,
  \x27\x27\x27^tests[\\\\/]test_workflow_execution\\.py$\x27\x27\x27
]
'''
_BASELINE = _CANDIDATE.split(b"# Limit the fixture exception", 1)[0]
_WRONG_RULE = b'''
[[rules]]
id = "c07-synthetic-wrong-rule"
description = "Inert cross-rule boundary control only"
regex = \x27\x27\x27c07_wrong_rule = "(normalized-coin-1-front)"\x27\x27\x27
secretGroup = 1
'''


@dataclass(frozen=True)
class GitObject:
    oid: str
    kind: str
    data: bytes


@dataclass(frozen=True)
class Revision:
    commit: str
    parent: str | None
    path: str
    content: bytes


@dataclass(frozen=True, repr=False)
class Occurrence:
    rule: str
    path: str
    commit: str
    start_line: int
    end_line: int
    value: str
    role: str
    context: str

    def finding(self) -> dict:
        record = asdict(self)
        del record["role"], record["context"]
        return record


@dataclass(frozen=True)
class Case:
    case_id: str
    requirement: str
    revisions: tuple[Revision, ...]
    objects: tuple[GitObject, ...]
    expected: tuple[Occurrence, ...]
    exceptions: tuple[Occurrence, ...]
    baseline_config: bytes
    candidate_config: bytes
    blockers: tuple[str, ...]

    @property
    def snapshot_sha256(self) -> str:
        manifest = {
            "base": BASE, "criterion": CRITERION_SHA256, "workflow": WORKFLOW_SHA256,
            "scanner_version": SCANNER_VERSION, "history": HISTORY_OPTIONS,
            "case": asdict(self), "evidence_kind": "synthetic-definition-only",
        }
        return hashlib.sha256(json.dumps(
            manifest, sort_keys=True, separators=(",", ":"),
            default=lambda value: {"bytes_hex": value.hex()},
        ).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class EngineeringResult:
    summary: Summary
    status: str = "SYNTHETIC_RECONCILED_NOT_QUALIFIED"
    scanner_executed: bool = False
    qualified: bool = False


def sterile_git_environment(empty_home: str) -> dict[str, str]:
    """Environment recipe for offline object checks, not a containment claim.

    Callers still need explicit safe command arguments and fresh disposable
    repositories. This does not authorize scanner runs or native qualification.
    """
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC",
    }}
    env.update(HOME=empty_home, XDG_CONFIG_HOME=empty_home, GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_ATTR_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1",
               GIT_OPTIONAL_LOCKS="0", GIT_ALLOW_PROTOCOL="", GIT_PAGER="",
               GIT_NO_REPLACE_OBJECTS="1")
    return env


def _marker(role: str) -> str:
    # Public deterministic text, never copied from a credential or environment.
    return "C07Z" + hashlib.sha256(("C07 inert control " + role).encode()).hexdigest()


def _history(case_id: str, path: str, contents: tuple[bytes, ...]):
    objects: dict[str, GitObject] = {}

    def obj(kind: str, data: bytes) -> str:
        oid = hashlib.sha1(kind.encode() + b" " + str(len(data)).encode() + b"\0" + data).hexdigest()
        objects[oid] = GitObject(oid, kind, data)
        return oid

    revisions = []
    parent = None
    for index, content in enumerate(contents):
        child = obj("blob", content)
        parts = path.split("/")
        child = obj("tree", b"100644 " + parts[-1].encode() + b"\0" + bytes.fromhex(child))
        for part in reversed(parts[:-1]):
            child = obj("tree", b"40000 " + part.encode() + b"\0" + bytes.fromhex(child))
        commit = (f"tree {child}\n" + (f"parent {parent}\n" if parent else "") +
                  "author C07 Synthetic <c07@example.invalid> 978307200 +0000\n"
                  "committer C07 Synthetic <c07@example.invalid> 978307200 +0000\n\n" +
                  f"Inert {case_id} revision {index}\n").encode()
        oid = obj("commit", commit)
        revisions.append(Revision(oid, parent, path, content))
        parent = oid
    return tuple(revisions), tuple(objects[key] for key in sorted(objects))


def _source(text: str, line: int = 41) -> bytes:
    return (("# inert context\n" * (line - 1)) + text + "\n").encode()


def _assignment(value: str) -> str:
    return 'api' + '_key = "' + value + '"'


def _case(case_id: str, path: str, sources: tuple[bytes, ...], specs: tuple,
          exception_indices: tuple[int, ...] = (), wrong_rule: bool = False) -> Case:
    revisions, objects = _history(case_id, path, sources)
    expected = tuple(Occurrence(rule, path, revisions[revision].commit, line, line,
                                value, role, context)
                     for revision, line, value, rule, role, context in specs)
    blockers = ["NATIVE_SCANNER_NOT_EXECUTED", "BINARY_AND_EFFECTIVE_RULE_DIGESTS_UNBOUND",
                "NATIVE_ENVIRONMENT_AND_FINAL_REVIEW_PENDING"]
    if expected:
        blockers.append("B_DETECTION_NOT_EXECUTED")
    if exception_indices:
        blockers.extend(("INDEPENDENT_NON_SECRET_EVIDENCE_PENDING", "EXCEPTION_NOT_APPROVED"))
    supplement = _WRONG_RULE if wrong_rule else b""
    return Case(case_id, case_id[:3], revisions, objects, expected,
                tuple(expected[i] for i in exception_indices), _BASELINE + supplement,
                _CANDIDATE + supplement, tuple(blockers))


def build_cases() -> tuple[Case, ...]:
    """Return all 101 independently named P01-P08 subcases with no IO.

    Fresh immutable values are returned. Repeated contexts are intentional;
    no source file is imported, executed, or used as a fixture repository.
    """
    if hashlib.sha256(_CANDIDATE).hexdigest() != CONFIG_SHA256:
        raise ReconciliationError("catalog: candidate source identity mismatch")
    cases = [_case("P01/clean", "synthetic/clean.txt", (b"# clean inert text\n",), ())]

    # Exact relevant lines at BASE: all nine occurrences, with role/context.
    contexts = (
        (0, 147, 8, 'artifact_key="' + FIXTURE + '",', "descriptor-artifact-key"),
        (1, 816, 20, '"' + FIXTURE + '": StageArtifact(', "first-stage-artifact-key"),
        (1, 834, 28, '"source_normalized_key": "' + FIXTURE + '",', "first-source-key"),
        (1, 846, 20, '"' + FIXTURE + '": "image-normalization",', "first-producer-key"),
        (1, 853, 12, 'self.assertEqual(descriptor.artifact_key, "' + FIXTURE + '")', "assert-artifact-key"),
        (1, 857, 16, 'if item.artifact_key == "' + FIXTURE + '"', "selected-artifact-predicate"),
        (1, 874, 20, '"' + FIXTURE + '": StageArtifact(', "second-stage-artifact-key"),
        (1, 892, 28, '"source_normalized_key": "' + FIXTURE + '",', "second-source-key"),
        (1, 905, 24, '"' + FIXTURE + '": "image-normalization",', "second-producer-key"),
    )
    for index, line, indent, text, context in contexts:
        cases.append(_case(f"P02/path-{index}/{context}", AUTHORIZED_PATHS[index],
                           (_source(" " * indent + text, line),),
                           ((0, line, FIXTURE, RULE, "fixture", context),), (0,)))

    for index, path in enumerate(AUTHORIZED_PATHS):
        for layout in ("separate-line", "same-line"):
            key = _marker("P03-independent")
            joiner = "\n" if layout == "separate-line" else "; "
            cases.append(_case(f"P03/path-{index}/{layout}", path,
                               (_source(_assignment(FIXTURE) + joiner + _assignment(key)),),
                               ((0, 41, FIXTURE, RULE, "fixture", layout),
                                (0, 42 if layout == "separate-line" else 41, key, RULE,
                                 "independent-control", layout)), (0,)))
        for label in ("A", "B"):
            value = _marker(label)
            cases.append(_case(f"P04/path-{index}/{label}", path,
                               (_source(_assignment(value)),),
                               ((0, 41, value, RULE, "replacement-" + label, "independent-history"),)))
        values = (FIXTURE, _marker("A"), _marker("B"))
        cases.append(_case(f"P05/path-{index}/fixture-A-B", path,
                           tuple(_source(_assignment(value)) for value in values),
                           tuple((i, 41, value, RULE, "fixture" if i == 0 else "replacement",
                                  "replacement-history") for i, value in enumerate(values)), (0,)))

        filename = path.split("/")[-1]
        boundaries = {
            "outside": "synthetic/" + filename,
            "nested": "tests/nested/" + filename,
            "lookalike": path.replace("test_", "test-", 1),
            "prefix-name": "tests/prefix_" + filename,
            "suffix-name": path + ".bak",
            "prefix-path": "prefix/" + path,
            "suffix-path": path + "/child.py",
            "unicode-lookalike": path.replace("e", "\u0435", 1),
        }
        for name, other_path in boundaries.items():
            cases.append(_case(f"P06/path-{index}/{name}", other_path,
                               (_source(_assignment(FIXTURE)),),
                               ((0, 41, FIXTURE, RULE, "unapproved-path", name),)))
        cases.append(_case(f"P06/path-{index}/wrong-rule", path,
                           (_source('c07_wrong_rule = "' + FIXTURE + '"'),),
                           ((0, 41, FIXTURE, "c07-synthetic-wrong-rule", "wrong-rule",
                             "synthetic-rule-specific-control"),), wrong_rule=True))

        mutations = {f"char-{i:02d}": FIXTURE[:i] + "X" + FIXTURE[i + 1:]
                     for i in range(len(FIXTURE))}
        mutations.update(prefix="X" + FIXTURE, suffix=FIXTURE + "X",
                         **{"high-entropy-A": _marker("A"), "high-entropy-B": _marker("B")})
        for name, value in mutations.items():
            cases.append(_case(f"P07/path-{index}/{name}", path,
                               (_source(_assignment(value)),),
                               ((0, 41, value, RULE, "unapproved-value", name),)))

    for index, path in enumerate((*AUTHORIZED_PATHS, "synthetic/unrelated.txt")):
        controls = (
            (RULE, _marker("P08-generic")),
            ("github-pat", "gh" + "p_" + hashlib.sha256(b"C07 inert github").hexdigest()[:36]),
            ("aws-access-token", "AK" + "IA" + hashlib.sha256(b"C07 inert aws").hexdigest()[:16].upper()),
        )
        for rule, value in controls:
            cases.append(_case(f"P08/path-{index}/{rule}", path,
                               (_source(_assignment(value)),),
                               ((0, 41, value, rule, "builtin-control", "preserve-default-rule"),)))
    return tuple(cases)


def make_plan(cases: tuple[Case, ...], *, columns: Mapping | None = None) -> dict:
    """Predeclare P13 expectations, optionally with independently known columns.

    `columns` maps (case_id, expected-occurrence-index) to start_column and/or
    end_column. Bind it BEFORE reports; never derive it from a candidate report.
    Empty/partial case sets remain explicit subsets, never full-suite evidence.
    """
    columns = {} if columns is None else dict(columns)
    declared = []
    consumed = set()
    for case in cases:
        findings = []
        for index, occurrence in enumerate(case.expected):
            finding = occurrence.finding()
            key = (case.case_id, index)
            if key in columns:
                extra = columns[key]
                if (type(extra) is not dict or not extra or
                        not extra.keys() <= {"start_column", "end_column"} or
                        any(type(v) is not int or v < 1 for v in extra.values())):
                    raise ReconciliationError("columns: invalid explicit column binding")
                if ("start_column" in extra and "end_column" in extra and
                        extra["end_column"] < extra["start_column"]):
                    raise ReconciliationError("columns: reversed column range")
                finding.update(extra)
                consumed.add(key)
            findings.append(finding)
        exceptions = []
        # Select each explicit exception occurrence with its multiplicity.
        remaining = list(enumerate(case.expected))
        for exception in case.exceptions:
            for offset, (index, occurrence) in enumerate(remaining):
                if occurrence == exception:
                    exceptions.append(dict(findings[index]))
                    remaining.pop(offset)
                    break
            else:
                raise ReconciliationError("catalog: exception absent from expected B")
        binding = hashlib.sha256(json.dumps(
            {"case_snapshot": case.snapshot_sha256, "expected": findings, "exceptions": exceptions},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        declared.append({"case_id": case.case_id, "snapshot_sha256": binding,
                         "baseline_execution_id": case.case_id + "/B/" + binding,
                         "candidate_execution_id": case.case_id + "/C/" + binding,
                         "expected_baseline": findings, "exceptions": exceptions})
    if consumed != columns.keys():
        raise ReconciliationError("columns: unknown occurrence binding")
    if not declared or len({c["case_id"] for c in declared}) != len(declared):
        raise ReconciliationError("catalog: empty or duplicate case selection")
    return {"schema": "c07-findings-v1", "criterion_sha256": CRITERION_SHA256, "cases": declared}


def reconcile_synthetic(cases: tuple[Case, ...], reports: object, *,
                        columns: Mapping | None = None) -> EngineeringResult:
    """Apply merged P13 without ever granting scanner/native/qualification credit."""
    return EngineeringResult(reconcile(make_plan(cases, columns=columns), reports))
