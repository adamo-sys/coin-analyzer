"""Dependency-light desktop bootstrap, also used by the Windows launcher."""
import sys


def main(*, evaluator=None, launch=None, output=None, version=None):
    output = sys.stderr if output is None else output
    version = sys.version_info if version is None else version
    if tuple(version[:2]) < (3, 12) or version[0] != 3:
        print("Coin Analyzer requires Python 3.12+ (3.x). Use the project .venv interpreter.",
              file=output)
        return 1
    from runtime_readiness import Capability, Status, evaluate_readiness
    try:
        report = (evaluator or evaluate_readiness)()
    except Exception:
        print("Runtime checks could not complete. Verify the project .venv and dependencies.",
              file=output)
        return 1
    for capability in Capability:
        print(capability.value.upper() + ": " + report.status_for(capability).value,
              file=output)
    for check in report.checks:
        if check.status != Status.READY:
            print(check.check_id + ": " + check.message + " " + check.action, file=output)
    if report.status_for(Capability.CORE) != Status.READY:
        return 1
    try:
        if launch is None:
            from coin_collection_gui import main as launch
        launch()
    except Exception:
        print("Coin Analyzer could not start. Verify the desktop display, project files, "
              "and dependencies in the selected interpreter.", file=output)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
