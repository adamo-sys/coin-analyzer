"""Capture advisory evidence for the pinned mutmut 3.7.0 CLI (stdlib only)."""

import argparse
from enum import Enum
import json
import os
from pathlib import Path
import re
import subprocess


class ReportState(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    UNAVAILABLE = "UNAVAILABLE"


# mutmut 3.7.0: results() emits "<mutant>: <status>", omitting killed mutants.
# Source: boxed/mutmut, tag 3.7.0, src/mutmut/__main__.py.
STATUSES = {
    "killed", "survived", "no tests", "check was interrupted by user",
    "not checked", "skipped", "suspicious", "timeout", "caught by type check",
    "segfault",
}
RESULT_LINE = re.compile(r"\s*([A-Za-z_][A-Za-z_0-9.]*)\s*: (.+?)\s*")


def run_command(arguments):
    """Keep stdout/stderr separate and retain actual process exit codes."""
    try:
        result = subprocess.run(arguments, capture_output=True, text=True,
                                encoding="utf-8", errors="backslashreplace", check=False)
        return {"command": arguments, "exit_code": result.returncode,
                "stdout": result.stdout, "stderr": result.stderr, "error": None}
    except OSError as error:
        # No process exit code exists if the executable could not be started.
        return {"command": arguments, "exit_code": None, "stdout": "", "stderr": "",
                "error": str(error)}


def capture(run_outcome, run_exit_code):
    primary = run_command(["mutmut", "results"])
    report = {
        "state": ReportState.UNAVAILABLE,
        "mutmut_version": "3.7.0",
        "mutation_run": {"outcome": run_outcome, "exit_code": run_exit_code},
        "results": primary, "survivor_count": None, "details": [], "errors": [],
    }
    if primary["exit_code"] != 0:
        report["errors"].append("Primary results retrieval failed.")
        return report

    survivors = []
    for line in primary["stdout"].splitlines():
        if not line.strip():
            continue
        match = RESULT_LINE.fullmatch(line)
        if match is None or match[2] not in STATUSES:
            report["errors"].append("Unrecognized mutmut 3.7.0 results output.")
            return report
        if match[2] == "survived":
            survivors.append(match[1])

    report["state"] = ReportState.COMPLETE
    if run_outcome != "success" or run_exit_code != 0:
        report["state"] = ReportState.INCOMPLETE
        report["errors"].append("Mutation execution did not complete successfully.")

    for mutant in survivors:
        command = run_command(["mutmut", "show", mutant])
        valid_header = command["stdout"].splitlines()[:1] == [f"# {mutant}: survived"]
        state = (ReportState.COMPLETE if command["exit_code"] == 0 and valid_header
                 else ReportState.INCOMPLETE)
        report["details"].append({"mutant": mutant, "state": state, **command})
        if state == ReportState.INCOMPLETE:
            report["state"] = ReportState.INCOMPLETE
            report["errors"].append(f"Survivor detail retrieval failed: {mutant}")

    # Never turn missing/partial evidence into an authoritative zero.
    if report["state"] == ReportState.COMPLETE:
        report["survivor_count"] = len(survivors)
    return report


def render_command(command):
    return (
        f"Command: {command['command']!r}\n"
        f"Exit code: {command['exit_code']}\n"
        f"Launch error: {command['error']}\n"
        f"stdout:\n{command['stdout']}\n"
        f"stderr:\n{command['stderr']}\n"
    )


def render_report(report):
    lines = [
        f"Report state: {report['state'].value}",
        f"Mutation run outcome: {report['mutation_run']['outcome']}",
        f"Mutation run exit code: {report['mutation_run']['exit_code']}",
        "Evidence capture status is not a mutation score.",
    ]
    if report["state"] == ReportState.COMPLETE:
        lines.append(f"Survivor count: {report['survivor_count']}")
        if report["survivor_count"] == 0:
            lines.append("No survivor entries reported")
    else:
        lines.append("Survivor count: unknown (evidence incomplete or unavailable)")
    lines.extend(report["errors"])
    for detail in report["details"]:
        lines.extend([
            f"\nMUTANT: {detail['mutant']}",
            f"Detail state: {detail['state'].value}",
            render_command(detail),
        ])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--run-outcome", default=os.environ.get("MUTMUT_RUN_OUTCOME", "unknown"))
    parser.add_argument("--run-exit-code", default=os.environ.get("MUTMUT_RUN_EXIT_CODE"))
    args = parser.parse_args(argv)
    try:
        run_exit_code = int(args.run_exit_code) if args.run_exit_code else None
    except ValueError:
        run_exit_code = None  # Unknown execution evidence cannot produce COMPLETE.
    report = capture(args.run_outcome, run_exit_code)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "mutmut-results.txt").write_text(
        render_command(report["results"]), encoding="utf-8")
    rendered = render_report(report)
    (args.output_dir / "mutmut-survivor-diffs.txt").write_text(rendered, encoding="utf-8")
    (args.output_dir / "mutmut-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(rendered, end="")
    return 0 if report["state"] == ReportState.COMPLETE else 1


if __name__ == "__main__":
    raise SystemExit(main())
