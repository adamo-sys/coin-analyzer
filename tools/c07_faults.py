"""Finite integrated P11/P12/P14 offline drivers, never native qualification.

The reference backend applies the frozen, explicitly hypothetical mutations to
inert findings and executes the real required-check/reconciliation boundary.
An injected backend may supply observations, but this interface authenticates
neither that backend nor a scanner run. No execution entry point is provided.
"""

from copy import deepcopy
from collections import Counter
from dataclasses import asdict, dataclass, replace
import hashlib
import json

from tools import c07_remaining as remaining, c07_synthetic as synthetic
from tools.c07_findings import ReconciliationError, reconcile


class DriverError(ValueError):
    """Incomplete engineering suite; never a partially successful result."""


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Trial:
    family: str
    name: str
    lane: str
    cases: tuple
    config: bytes

    @property
    def snapshot_sha256(self):
        return _digest({"family": self.family, "name": self.name, "lane": self.lane,
                        "plan": synthetic.make_plan(self.cases),
                        "config_sha256": hashlib.sha256(self.config).hexdigest(),
                        "criterion": synthetic.CRITERION_SHA256})


@dataclass(frozen=True)
class Observation:
    trial_sha256: str
    reports: object
    controls: remaining.Controls
    required_exit: int


def fault_trials():
    """Fresh immutable finite recipes; all P11 counterexamples and both P12 lanes."""
    cases = synthetic.build_cases()
    config = remaining.Controls().config
    clean = tuple(c for c in cases if c.requirement == "P01")
    # A clean control prevents an always-failing adapter from earning credit.
    result = [Trial("CLEAN", "complete-clean", "both", clean, config)]
    result += [Trial("P11", m.name, "candidate", m.controls, m.config)
               for m in remaining.policy_mutations()]
    control = tuple(c for c in cases if c.requirement == "P03")
    result += [Trial("P12", name, lane, control, config)
               for name in remaining.OPERATIONAL_FAILURES for lane in ("baseline", "candidate")]
    result += [Trial("P14", name, "both", control, config)
               for name, _ in remaining.workflow_mutations()]
    return tuple(result)


def _inert_reports(plan):
    """Reference engineering input, explicitly not a scanner observation."""
    reports = []
    for case in plan["cases"]:
        baseline = deepcopy(case["expected_baseline"])
        candidate = deepcopy(baseline)
        for exception in case["exceptions"]:
            candidate.remove(exception)
        row = {"case_id": case["case_id"], "snapshot_sha256": case["snapshot_sha256"]}
        for lane, findings in (("baseline", baseline), ("candidate", candidate)):
            row[lane] = {"execution_id": case[lane + "_execution_id"], "status": "completed",
                         "started_at": "2001-01-01T00:00:00Z", "finished_at": "2001-01-01T00:00:01Z",
                         "exit_code": 2 if findings else 0, "findings": findings}
        reports.append(row)
    return reports


class OfflineFaultBackend:
    """Concrete in-memory backend exercising actual frozen rejection functions."""

    def exercise(self, trial):
        if type(trial) is not Trial or trial not in fault_trials():
            raise DriverError("unapproved fault recipe")
        reports = _inert_reports(synthetic.make_plan(trial.cases))
        controls = remaining.Controls()
        if trial.family == "P11":
            mutation = next(m for m in remaining.policy_mutations() if m.name == trial.name)
            reports = remaining.weakened_reports(mutation, reports)
            controls = replace(controls, config=trial.config)
        elif trial.family == "P12":
            reports, controls = remaining.operational_failure(trial.name, reports, controls, trial.lane)
        elif trial.family == "P14":
            controls = dict(remaining.workflow_mutations())[trial.name]
        try:
            remaining.required_check(trial.cases, reports, controls)
            code = 0
        except ReconciliationError:
            code = 1
        return Observation(trial.snapshot_sha256, reports, controls, code)


def _p11_counterexample(trial, reports):
    plan = synthetic.make_plan(trial.cases)
    expected = _inert_reports(plan)
    # Authenticate no provenance here. Structurally require complete, valid B
    # for every planned case, plus all C metadata, before testing suppression.
    repaired = deepcopy(reports)
    wanted = {r["case_id"]: r for r in expected}
    for row in repaired:
        row["candidate"]["findings"] = deepcopy(wanted[row["case_id"]]["candidate"]["findings"])
        row["candidate"]["exit_code"] = wanted[row["case_id"]]["candidate"]["exit_code"]
    reconcile(plan, repaired)
    candidate_plan, candidate_reports = deepcopy(plan), deepcopy(reports)
    observed = {r["case_id"]: r for r in reports}
    lost = 0

    def identities(findings):
        return Counter(json.dumps(dict(f, path=f["path"].replace("\\", "/")),
                                  sort_keys=True, separators=(",", ":")) for f in findings)

    for case, row in zip(candidate_plan["cases"], candidate_reports):
        actual = observed[case["case_id"]]["candidate"]
        case["expected_baseline"], case["exceptions"] = deepcopy(actual["findings"]), []
        row["baseline"] = dict(deepcopy(actual), execution_id=case["baseline_execution_id"])
        retained = identities(wanted[case["case_id"]]["candidate"]["findings"])
        actual_findings = identities(actual["findings"])
        if actual_findings - retained:
            raise DriverError("unexpected P11 candidate finding")
        lost += (retained - actual_findings).total()
    reconcile(candidate_plan, candidate_reports)  # Strict C record/exit validation.
    if not lost:
        raise DriverError("missing P11 behavioral counterexample")


def _exact_effect(observed, expected):
    """Type-exact comparison of the frozen OFFLINE fault recipe, not provenance."""
    if type(observed) is not type(expected):
        return False
    if type(expected) is dict:
        return (observed.keys() == expected.keys()
                and all(_exact_effect(observed[k], v) for k, v in expected.items()))
    if type(expected) in (list, tuple):
        return len(observed) == len(expected) and all(
            _exact_effect(a, b) for a, b in zip(observed, expected))
    return observed == expected


def run_fault_suite(backend):
    """Require every finite recipe and propagation; return sanitized metadata only.

    No retry, partial promotion or native credit. P11 must have a behavioral
    counterexample under the independent multiset check, not just changed config.
    Exact frozen offline effects must match, so one unrelated rejection cannot
    stand in for every named fault. Native execution evidence needs a separately
    reviewed native driver; these reference timestamps/effects are inert only.
    Backend exceptions are chained away because their diagnostics may be private.
    """
    rows, counts = [], {"CLEAN": 0, "P11": 0, "P12": 0, "P14": 0}
    for index, trial in enumerate(fault_trials()):
        try:
            observed = backend.exercise(trial)
        except Exception:
            raise DriverError(f"trial[{index}]: backend incomplete") from None
        if (type(observed) is not Observation or observed.trial_sha256 != trial.snapshot_sha256
                or type(observed.required_exit) is not int
                or observed.required_exit != (0 if trial.family == "CLEAN" else 1)):
            raise DriverError(f"trial[{index}]: binding or required-check propagation")
        expected = OfflineFaultBackend().exercise(trial)
        if (type(observed.controls) is not remaining.Controls
                or not _exact_effect(asdict(observed.controls), asdict(expected.controls))
                or not _exact_effect(observed.reports, expected.reports)):
            raise DriverError(f"trial[{index}]: declared offline fault not observed")
        try:
            remaining.required_check(trial.cases, observed.reports, observed.controls)
            rejected = False
        except ReconciliationError:
            rejected = True
        if rejected != (trial.family != "CLEAN"):
            raise DriverError(f"trial[{index}]: incorrect independent outcome")
        if trial.family == "P11":
            try:
                _p11_counterexample(trial, observed.reports)
            except (ValueError, KeyError, TypeError):
                raise DriverError(f"trial[{index}]: incomplete behavioral counterexample") from None
        rows.append({"family": trial.family, "name": trial.name, "lane": trial.lane,
                     "trial_sha256": trial.snapshot_sha256, "required_exit": observed.required_exit})
        counts[trial.family] += 1
    result = {"schema": "c07-offline-faults-v1", "status": "ENGINEERING_ONLY",
              "execution_status": "NOT_ADMITTED", "qualified": False,
              "criterion_sha256": synthetic.CRITERION_SHA256, "counts": counts, "trials": rows}
    result["manifest_sha256"] = _digest(result)
    return result
