"""C07 native-driver preparation primitives, with NO execution entry point.

Only the frozen inert catalogs may be materialized. Raw report translation is
structural, not authentication or native coordinate qualification. No scanner is
launched, run admitted, exception approved, or historical allowance consumed.
This is not an R2 supervisor/backend. Full native qualification remains separate.
"""

from decimal import Context, Decimal, localcontext
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zlib

from tools import c07_remaining, c07_synthetic
from tools.gitleaks_history import LOG_OPTIONS, load_report, scan_environment


def _catalog():
    result = {c.case_id: (c, (("refs/heads/main", c.revisions[-1].commit),), c.snapshot_sha256)
              for c in c07_synthetic.build_cases()}
    result.update({d.case.case_id: (d.case, d.refs, d.snapshot_sha256)
                   for d in c07_remaining.build_definitions()})
    return result


def materialize(case, destination, *, refs=None):
    """Create one fresh local-only Git fixture; preserve partial failure output.

    No remotes/hooks/templates or source-checkout objects. Git command execution
    reads/writes public inert test objects only. No cleanup/retry on failure.
    Working-tree checkout is deliberate: unsupported case coexistence is a
    failure requiring platform disposition, never a silently skipped case.
    """
    entry = _catalog().get(case.case_id)
    if entry is None or case != entry[0] or (refs is not None and refs != entry[1]):
        raise ValueError("fixture differs from frozen catalog")
    refs = entry[1]
    root = Path(destination)
    if root.exists() or root.is_symlink():
        raise ValueError("fixture destination must be fresh")
    root.mkdir(parents=False)
    gitdir = root / ".git"
    (gitdir / "objects").mkdir(parents=True)
    (gitdir / "refs/heads").mkdir(parents=True)
    (gitdir / "HEAD").write_bytes(b"ref: refs/heads/main\n")
    (gitdir / "config").write_bytes(b"[core]\nrepositoryformatversion = 0\nbare = false\nautocrlf = false\n")
    for obj in case.objects:
        payload = obj.kind.encode() + b" " + str(len(obj.data)).encode() + b"\0" + obj.data
        if hashlib.sha1(payload).hexdigest() != obj.oid:
            raise ValueError("fixture object identity mismatch")
        target = gitdir / "objects" / obj.oid[:2] / obj.oid[2:]
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(zlib.compress(payload))
    for name, oid in refs:
        target = gitdir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(oid.encode() + b"\n")
    empty_home = gitdir / "empty-home"
    empty_home.mkdir()
    env = scan_environment(empty_home)
    for args in (("fsck", "--strict"), ("checkout", "--force", "main")):
        subprocess.run(["git", "-C", str(root), *args], env=env, capture_output=True,
                       timeout=10, check=True)
    # Compare the actual checked-out tree bytes, including case coexistence.
    paths = subprocess.run(["git", "-C", str(root), "ls-tree", "-rz", "HEAD"],
                           env=env, capture_output=True, timeout=10, check=True).stdout
    objects = {obj.oid: obj.data for obj in case.objects if obj.kind == "blob"}
    for item in paths.split(b"\0"):
        if not item:
            continue
        identity, name = item.split(b"\t", 1)
        oid = identity.split()[2].decode()
        if (root / name.decode("utf-8")).read_bytes() != objects[oid]:
            raise ValueError("native fixture topology/content mismatch")
    return {"case_id": case.case_id, "snapshot_sha256": entry[2], "refs": list(refs),
            "status": "ENGINEERING_MATERIALIZED", "qualified": False}


def adapt_report(data, *, allowed_values):
    """Map exact 8.24.3 JSON field names, preserving every supplied coordinate.

    Never use redacted production reports here. Only independently predeclared
    inert values may cross this interface. Native byte/column semantics and plan
    columns must be bound independently BEFORE execution, not inferred here.
    Errors never include report values, paths, commits or supplied identifiers.
    """
    if type(allowed_values) not in (set, frozenset) or any(
        type(value) is not str or not value or "\0" in value for value in allowed_values
    ):
        raise ValueError("expected an exact set of predeclared inert values")
    records = load_report(data)
    known = {"RuleID", "Description", "StartLine", "EndLine", "StartColumn", "EndColumn",
             "Match", "Secret", "File", "SymlinkFile", "Commit", "Link", "Entropy",
             "Author", "Email", "Date", "Message", "Tags", "Fingerprint"}
    result = []
    for record in records:
        if not record.keys() <= known or record["Secret"] == "REDACTED" or record["Secret"] not in allowed_values:
            raise ValueError("unknown field or unapproved/redacted value")
        result.append({"rule": record["RuleID"], "path": record["File"].replace("\\", "/"),
                       "commit": record["Commit"], "value": record["Secret"],
                       "start_line": record["StartLine"], "end_line": record["EndLine"],
                       "start_column": record["StartColumn"], "end_column": record["EndColumn"]})
    return result


def check_resources(accounting):
    """Check proposed arithmetic only; supplied review references aren't verified.

    This does NOT certify headroom or admit an operation. The owner/verifier must
    authenticate complete interval/counter reconciliation separately. Existing
    unknown/unmetered intervals and exhausted allowances cannot be reset here.
    """
    required = {"ceiling_seconds", "charged_seconds", "reserved_seconds", "requested_seconds",
                "accounting_reconciliation", "unmetered_intervals", "counter_state"}
    if type(accounting) is not dict or accounting.keys() != required:
        raise ValueError("incomplete resource declaration")
    if accounting["unmetered_intervals"] != []:
        raise ValueError("unresolved accounting intervals")
    for key, prefix in (("accounting_reconciliation", "reviewed-ledger-sha256:"),
                        ("counter_state", "reviewed-counters-sha256:")):
        value = accounting[key]
        if type(value) is not str or re.fullmatch(re.escape(prefix) + r"[0-9a-f]{64}", value) is None:
            raise ValueError("resource review reference is unbound")
    numbers = {}
    for key in ("ceiling_seconds", "charged_seconds", "reserved_seconds", "requested_seconds"):
        # Bounded fixed-point seconds: reject exponent/rounding/precision attacks.
        if type(accounting[key]) is not str or re.fullmatch(
            r"(?:0|[1-9][0-9]{0,4})(?:\.[0-9]{1,9})?", accounting[key]
        ) is None:
            raise ValueError("resource amount must be bounded fixed-point seconds")
        numbers[key] = Decimal(accounting[key])
    # An explicit context also excludes changes to the caller's ambient context.
    with localcontext(Context(prec=40)):
        remainder = numbers["ceiling_seconds"] - sum(numbers[k] for k in (
            "charged_seconds", "reserved_seconds", "requested_seconds"))
    if numbers["ceiling_seconds"] != 36000 or numbers["requested_seconds"] <= 0 or remainder < 0:
        raise ValueError("unapproved ceiling or unavailable allocation")
    return str(remainder)


def preparation_manifest():
    """Deterministic source/graph package, never an execution authorization."""
    result = {
        "schema": "c07-preparation-v1", "execution_status": "NOT_ADMITTED", "qualified": False,
        "criterion_sha256": c07_synthetic.CRITERION_SHA256, "scanner_version": "8.24.3",
        "history_options": LOG_OPTIONS,
        "cases": [{"case_id": cid, "snapshot_sha256": entry[2], "refs": list(entry[1]),
                   "baseline_config_sha256": hashlib.sha256(entry[0].baseline_config).hexdigest(),
                   "candidate_config_sha256": hashlib.sha256(entry[0].candidate_config).hexdigest()}
                  for cid, entry in sorted(_catalog().items())],
        "required_external_bindings": [
            "EXACT_OWNER_EXECUTION_AUTHORIZATION", "NATIVE_UBUNTU_AND_WINDOWS_11_24H2_X64",
            "BINARY_AND_EFFECTIVE_DEFAULT_RULE_IDENTITIES", "NATIVE_COLUMN_SEMANTICS",
            "PREDECLARED_FINDINGS_AND_B_DETECTABILITY", "INDEPENDENT_NON_SECRET_EVIDENCE",
            "EACH_EXACT_EXCEPTION_DECISION", "AUTHENTICATED_RESOURCE_AND_COUNTER_RECONCILIATION",
            "INDEPENDENT_HUMAN_AND_CUSTODY_ROLES", "EXACT_RETENTION_DESTINATION_AND_ACCESS",
            "FINAL_NATIVE_DRIVER_AND_PROCESS_BACKEND_REVIEW", "P11_P12_P14_NATIVE_FAULT_DRIVERS",
            "R2_BACKEND_AND_ALL_C12",
        ],
    }
    result["manifest_sha256"] = hashlib.sha256(json.dumps(
        result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return result
