"""Offline Coin Analyzer Doctor. Run with python -m coin_analyzer_doctor."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import sys

from runtime_readiness import Capability, Status, evaluate_readiness
from doctor_health import evaluate_health


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default echoes arbitrary supplied argument values.
        self.print_usage(sys.stderr)
        self.exit(2, "Invalid Doctor arguments. Use --help for supported options.\n")


def build_parser():
    parser = _Parser(prog="coin-analyzer-doctor", description="Offline diagnostics; private paths require explicit opt-in.")
    parser.add_argument("--json", action="store_true", help="Emit one JSON diagnostic document.")
    parser.add_argument("--collection", metavar="PATH", help="Read-only collection inspection.")
    parser.add_argument("--managed-images", metavar="PATH", help="Check references under this managed root; requires --collection.")
    parser.add_argument("--probe-directory", metavar="PATH", help="Allow an owned disposable write/lock probe in an existing directory.")
    return parser


def main(argv=None, *, readiness=evaluate_readiness, health=evaluate_health, output=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.managed_images is not None and args.collection is None:
        parser.error("Managed images require a collection.")
    output = sys.stdout if output is None else output
    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            report = readiness()
            checks = health(report, collection=args.collection, managed_images=args.managed_images,
                            probe=args.probe_directory)
        required = {"storage.collection": args.collection,
                    "images.references": args.managed_images,
                    "persistence.probe": args.probe_directory}
        by_id = {check.check_id: check for check in checks}
        blocked = report.status_for(Capability.CORE) != Status.READY or any(
            selected is not None and (name not in by_id or by_id[name].status != Status.READY)
            for name, selected in required.items())
        all_checks = report.checks + tuple(checks)
        overall = "blocked" if blocked else (
            "degraded" if any(check.status != Status.READY for check in all_checks) else "ready")
        payload = {"schema_version": 1, "overall": overall,
                   "capabilities": {cap.value: report.status_for(cap).value for cap in Capability},
                   "checks": [{"check_id": c.check_id, "capability": c.capability.value,
                               "status": c.status.value, "message": c.message, "action": c.action}
                              for c in all_checks]}
    except Exception:
        blocked = True
        payload = {"schema_version": 1, "overall": "blocked",
                   "capabilities": {cap.value: "unverified" for cap in Capability},
                   "checks": [{"check_id": "doctor.execution", "capability": "core",
                               "status": "unverified", "message": "Doctor could not complete safely.",
                               "action": "Verify the runtime and selected inputs; no repair was attempted."}]}
    if args.json:
        print(json.dumps(payload, ensure_ascii=True), file=output)
    else:
        print("Coin Analyzer Doctor: " + payload["overall"].upper(), file=output)
        for cap, status in payload["capabilities"].items():
            print(cap.upper() + (" (optional)" if cap != "core" else "") + ": " + status, file=output)
        for check in payload["checks"]:
            print(f"[{check['status']}] {check['check_id']}: {check['message']} {check['action']}".rstrip(), file=output)
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
