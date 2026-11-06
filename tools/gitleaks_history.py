"""Explicit ordinary-CI history scan. No SEC-003/native qualification claim.

The install script is a literal CI policy checked by validate_workflow. Publisher
checksums establish a pinned download, not independent publisher provenance.
Raw scanner output/reports never reach Actions logs, summaries or artifacts.
This is trusted-runner tooling, not an R2 containment/deadline implementation.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

VERSION = "8.24.3"
ARCHIVE_SHA256 = "9991e0b2903da4c8f6122b5c3186448b927a5da4deef1fe45271c3793f4ee29c"
# This selects a first-parent DIFF for merges, while traversing EVERY parent.
# Bare --first-parent would truncate traversal and is deliberately absent.
LOG_OPTIONS = "--all --full-history --root --diff-merges=first-parent --no-renames --no-ext-diff --no-textconv"
INSTALL_SCRIPT = '''set -euo pipefail
test "$(uname -m)" = x86_64
mkdir -m 700 "$RUNNER_TEMP/sec003-gitleaks"
cd "$RUNNER_TEMP/sec003-gitleaks"
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --tlsv1.2 \\
  https://github.com/gitleaks/gitleaks/releases/download/v8.24.3/gitleaks_8.24.3_linux_x64.tar.gz \\
  --output scanner.tar.gz
echo '9991e0b2903da4c8f6122b5c3186448b927a5da4deef1fe45271c3793f4ee29c  scanner.tar.gz' | sha256sum --check --status
tar -xzf scanner.tar.gz --no-same-owner --no-same-permissions gitleaks
chmod 700 gitleaks
'''
SCAN_SCRIPT = 'python -B tools/gitleaks_history.py "$RUNNER_TEMP/sec003-gitleaks/gitleaks"'
HYDRATE_SCRIPT = 'python -B tools/gitleaks_history.py --hydrate'
HYDRATION_SOURCE = "https://github.com/adamo-sys/coin-analyzer"


def scan_environment(empty_home):
    """Allowlist process environment; no credentials, scanner or Git overrides."""
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC",
    }}
    env.update(HOME=str(empty_home), XDG_CONFIG_HOME=str(empty_home),
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_CONFIG_SYSTEM=os.devnull, GIT_ATTR_NOSYSTEM="1",
               GIT_TERMINAL_PROMPT="0", GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0",
               GIT_ALLOW_PROTOCOL="", GIT_PAGER="", GIT_NO_REPLACE_OBJECTS="1",
               LC_ALL="C", NO_COLOR="1")
    return env


def acquisition_environment(empty_home):
    """Explicit public-object acquisition only; scanner environment stays offline."""
    env = scan_environment(empty_home)
    env["GIT_ALLOW_PROTOCOL"] = "https"
    return env


class HistoryError(ValueError):
    """Fixed stage identifier only, never child output or repository content."""


def _git(repo, env, timeout, *args, data=None):
    return subprocess.run(["git", "-C", str(repo), *args], env=env, input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          timeout=timeout, check=True).stdout.strip()


def _history_shape(repo, env, timeout):
    stage = "history-shape"
    try:
        if _git(repo, env, timeout, "rev-parse", "--is-shallow-repository") != b"false":
            raise ValueError()
        for relative in ("info/grafts", "objects/info/alternates"):
            location = Path(os.fsdecode(_git(repo, env, timeout, "rev-parse", "--git-path", relative)))
            location = location if location.is_absolute() else repo / location
            if location.exists() or location.is_symlink():
                raise ValueError()
        stage = "history-head"
        _git(repo, env, timeout, "rev-parse", "--verify", "HEAD")
    except (OSError, ValueError, subprocess.SubprocessError):
        raise HistoryError(stage) from None


def hydrate_history(repo, source=HYDRATION_SOURCE, *, timeout=180, diagnostics=None):
    """Acquire missing reachable objects, without checkout, ref updates or scanning.

    The CLI uses a fixed public HTTPS source and no credentials. Missing objects
    and every acquisition/completeness error fail closed. This is ordinary CI
    preparation, never native qualification, R2 containment or provenance proof.
    """
    stage = "history-shape"
    try:
        repo = Path(repo).resolve()
        with tempfile.TemporaryDirectory(prefix="gitleaks-acquisition-") as temp:
            env = acquisition_environment(temp)
            _history_shape(repo, env, timeout)
            stage = "history-objects"
            objects = _git(repo, env, timeout, "rev-list", "--objects", "--all",
                           "--missing=print", "--no-object-names").splitlines()
            missing = [line[1:] for line in objects if line.startswith(b"?")]
            if any(re.fullmatch(b"[0-9a-f]{40}", oid) is None for oid in missing):
                raise ValueError()
            if missing:
                stage = "object-acquisition"
                _git(repo, env, timeout, "fetch", "--no-tags", "--no-write-fetch-head",
                     "--no-recurse-submodules", "--no-auto-maintenance", "--no-filter",
                     "--stdin", source, data=b"\n".join(missing) + b"\n")
            stage = "history-objects"
            _git(repo, scan_environment(temp), timeout, "rev-list", "--objects", "--all", "--missing=error")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        if diagnostics is not None:
            diagnostics.append(str(error) if isinstance(error, HistoryError) else stage)
        return 1


def scan_command(tool, repo, config, report, ignore):
    return [*tool, "git", "--no-banner", "--redact=100", "--exit-code=2",
            "--report-format=json", "--report-path=" + str(report), "--log-level=error",
            "--config=" + str(config), "--gitleaks-ignore-path=" + str(ignore),
            "--ignore-gitleaks-allow", "--log-opts=" + LOG_OPTIONS, str(repo)]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate report field")
        result[key] = value
    return result


def load_report(data):
    if len(data) > 64 * 1024 * 1024:
        raise ValueError("oversized report")
    try:
        records = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, ValueError):
        raise ValueError("invalid report encoding or JSON") from None
    if type(records) is not list:
        raise ValueError("report must be a list")
    for record in records:
        if type(record) is not dict:
            raise ValueError("invalid finding")
        for key in ("RuleID", "File", "Commit", "Secret"):
            if type(record.get(key)) is not str or not record[key] or "\0" in record[key]:
                raise ValueError("missing finding identity")
        path = record["File"].replace("\\", "/")
        if ":" in path or any(p in ("", ".", "..") for p in path.split("/")):
            raise ValueError("ambiguous finding path")
        if re.fullmatch(r"[0-9a-f]{40}", record["Commit"]) is None:
            raise ValueError("invalid commit identity")
        for key in ("StartLine", "EndLine", "StartColumn", "EndColumn"):
            if type(record.get(key)) is not int or record[key] < 1:
                raise ValueError("missing finding coordinate")
        if record["EndLine"] < record["StartLine"] or (
            record["EndLine"] == record["StartLine"] and record["EndColumn"] < record["StartColumn"]
        ):
            raise ValueError("reversed finding coordinates")
    return records


def check_report(data, exit_code):
    records = load_report(data)
    if type(exit_code) is not int or exit_code != (2 if records else 0):
        raise ValueError("incomplete scan or inconsistent report/exit")
    return exit_code


def run_scan(tool, repo, config, *, timeout=480, diagnostics=None):
    """Execute a fixed CI scan, returning 0 clean, 2 detection, 1 failure.

    Direct-child timeout is ordinary CI behavior, never proof of descendant
    cessation, native qualification or R2's strict deadline conjunction.
    """
    stage = "scanner-config"
    try:
        repo, config = Path(repo).resolve(), Path(config).resolve()
        if not config.is_file() or config.is_symlink():
            raise ValueError()
        with tempfile.TemporaryDirectory(prefix="gitleaks-history-") as temp:
            env = scan_environment(temp)
            _history_shape(repo, env, timeout)
            stage = "history-objects"
            _git(repo, env, timeout, "rev-list", "--objects", "--all", "--missing=error")
            stage = "scanner-version"
            version = subprocess.run([*tool, "version"], env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, timeout=timeout, check=True)
            if version.stdout.strip() != VERSION.encode():
                raise ValueError()
            ignore = Path(temp) / ".gitleaksignore"
            ignore.write_bytes(b"")
            report = Path(temp) / "report.json"
            stage = "scanner-execution"
            result = subprocess.run(scan_command(tool, repo, config, report, ignore),
                                    cwd=temp, env=env, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=timeout, check=False)
            if result.returncode not in (0, 2) or report.is_symlink():
                raise ValueError()
            stage = "scanner-report"
            with report.open("rb") as stream:
                return check_report(stream.read(64 * 1024 * 1024 + 1), result.returncode)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        if diagnostics is not None:
            diagnostics.append(str(error) if isinstance(error, HistoryError) else stage)
        return 1


def validate_workflow(workflow):
    """Reject changes that bypass this required security job's control flow."""
    job = workflow["jobs"]["gitleaks"]
    if set(job) != {"runs-on", "timeout-minutes", "steps"} or job["runs-on"] != "ubuntu-24.04" or job["timeout-minutes"] != 10:
        raise ValueError("unexpected scanner job controls")
    steps = job["steps"]
    if type(steps) is not list or len(steps) != 5:
        raise ValueError("unexpected scanner steps")
    checkout, setup, hydrate, install, scan = steps
    if set(checkout) != {"name", "uses", "with"} or checkout["uses"] != "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1":
        raise ValueError("unexpected scanner checkout")
    expected = {"fetch-depth": 0, "persist-credentials": False,
                "sparse-checkout": "/*\n!/test_coins/*\n/test_coins/README.md\n",
                "sparse-checkout-cone-mode": False}
    if checkout["with"] != expected or type(checkout["with"].get("fetch-depth")) is not int:
        raise ValueError("scanner requires full history and protected exclusions")
    if setup != {"name": "Set up scanner wrapper Python", "uses": "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", "with": {"python-version": "3.12"}}:
        raise ValueError("unexpected scanner runtime")
    if hydrate != {"name": "Acquire complete history objects", "shell": "bash", "run": HYDRATE_SCRIPT + "\n"}:
        raise ValueError("unexpected history acquisition")
    if install != {"name": "Install checksum-pinned Gitleaks", "shell": "bash", "run": INSTALL_SCRIPT}:
        raise ValueError("unexpected scanner acquisition")
    if scan != {"name": "Scan all available Git history", "shell": "bash", "run": SCAN_SCRIPT + "\n"}:
        raise ValueError("unexpected scanner invocation")


def main():
    if len(sys.argv) != 2:
        return 1
    root = Path(__file__).resolve().parents[1]
    diagnostics = []
    if sys.argv[1] == "--hydrate":
        code = hydrate_history(root, diagnostics=diagnostics)
        print("History object acquisition completed." if code == 0 else
              "History object acquisition failed at " + diagnostics[0] + "; no clean result.")
    else:
        code = run_scan((str(Path(sys.argv[1]).resolve()),), root, root / ".gitleaks.toml",
                        diagnostics=diagnostics)
        print({0: "History scan completed cleanly.", 2: "History scan detected findings."}.get(
            code, "History scan failed at " + (diagnostics or ["unknown"])[0] + "; no clean result."))
    return code


if __name__ == "__main__":
    sys.exit(main())
