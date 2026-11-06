"""Offline synthetic checks only; never scanner or native qualification."""
import hashlib
import unittest
from copy import deepcopy
from dataclasses import replace

from tests.test_c07_synthetic import reports_for
from tools import c07_synthetic as old
from tools.c07_findings import ReconciliationError


class RemainingTests(unittest.TestCase):
    def test_catalog_available(self):
        from tools import c07_remaining as h
        self.assertEqual({d.case.requirement for d in h.build_definitions()},
                         {"P09", "P10"})

    def test_history_graph_objects_and_selection(self):
        from tools import c07_remaining as h
        for d in h.build_definitions():
            if d.case.requirement != "P09":
                continue
            objects = {o.oid: o for o in d.case.objects}
            for o in objects.values():
                self.assertEqual(o.oid, hashlib.sha1(
                    o.kind.encode() + b" " + str(len(o.data)).encode() + b"\0" + o.data
                ).hexdigest())
            parents = {o.oid: [line[7:].decode() for line in o.data.splitlines()
                              if line.startswith(b"parent ")]
                       for o in objects.values() if o.kind == "commit"}
            reached = set()
            pending = list(dict(d.refs).values())
            while pending:
                oid = pending.pop()
                if oid not in reached:
                    reached.add(oid)
                    pending.extend(parents[oid])
            self.assertTrue({f.commit for f in d.case.expected} <= reached)
            if d.topology == "merge-only":
                self.assertEqual(len(parents[d.case.expected[0].commit]), 2)
            if d.topology == "unmerged":
                self.assertEqual(len(d.refs), 2)
            # An event/head-only fabricated report must lose historical controls.
            plan = h.definition_plan(d)
            good = reports_for(plan)
            h.check_definition(d, good, supported=True)
            bad = deepcopy(good)
            bad[0]["candidate"].update(findings=[], exit_code=0)
            with self.assertRaises(ReconciliationError):
                h.check_definition(d, bad, supported=True)

    def test_path_and_line_endings_exact_scope(self):
        from tools import c07_remaining as h
        definitions = [d for d in h.build_definitions() if d.case.requirement == "P10"]
        self.assertEqual(len(definitions), 48)
        for d in definitions:
            plan = h.definition_plan(d)
            reports = reports_for(plan)
            result = h.check_definition(d, reports, supported=True)
            self.assertFalse(result.qualified)
            with self.assertRaises(ReconciliationError):
                h.check_definition(d, reports, supported=False)
            if d.separator == "\\":
                for lane in ("baseline", "candidate"):
                    for f in reports[0][lane]["findings"]:
                        f["path"] = f["path"].replace("/", "\\")
                h.check_definition(d, reports, supported=True)
            if d.topology == "case-coexistence":
                self.assertEqual(len(d.case.expected), 3)
                self.assertEqual(len({f.path for f in d.case.expected}), 2)
            if not d.case.exceptions:
                bad = deepcopy(reports)
                bad[0]["candidate"].update(findings=[], exit_code=0)
                with self.assertRaises(ReconciliationError):
                    h.check_definition(d, bad, supported=True)

    def test_policy_mutations_have_independent_p03_p07_counterexamples(self):
        from tools import c07_remaining as h
        for mutation in h.policy_mutations():
            self.assertNotEqual(mutation.config, old.build_cases()[0].candidate_config)
            with self.assertRaises(ReconciliationError):
                h.check_controls(replace(h.Controls(), config=mutation.config))
            self.assertEqual({c.requirement for c in mutation.controls},
                             {"P03", "P04", "P05", "P06", "P07"})
            rejected = 0
            for case in mutation.controls:
                good = reports_for(old.make_plan((case,)))
                old.reconcile_synthetic((case,), good)
                bad = h.weakened_reports(mutation, good)
                if bad != good:
                    rejected += 1
                    with self.assertRaises(ReconciliationError):
                        old.reconcile_synthetic((case,), bad)
            self.assertGreater(rejected, 0, mutation.name)

    def test_operational_and_workflow_mutations_reach_required_check(self):
        from tools import c07_remaining as h
        cases = (old.build_cases()[10],)
        good = reports_for(old.make_plan(cases))
        controls = h.Controls()
        h.required_check(cases, good, controls)
        for name in h.OPERATIONAL_FAILURES:
            for lane in ("baseline", "candidate"):
                with self.subTest(name=name, lane=lane):
                    broken, metadata = h.operational_failure(name, good, controls, lane)
                    with self.assertRaises(ReconciliationError):
                        h.required_check(cases, broken, metadata)
        for name, bad in h.workflow_mutations():
            with self.subTest(name=name), self.assertRaises(ReconciliationError):
                h.required_check(cases, good, bad)
        for mode in ("omit", "skip", "swallow", "early-success"):
            broken = deepcopy(good)
            if mode == "omit":
                broken = []
            elif mode == "skip":
                broken[0]["candidate"]["status"] = "skipped"
            elif mode == "swallow":
                broken[0]["candidate"]["exit_code"] = 0
            else:
                broken[0]["candidate"].update(findings=[], exit_code=0)
            with self.assertRaises(ReconciliationError):
                h.required_check(cases, broken, controls)
        with self.assertRaises(ReconciliationError):
            h.required_check((), [], controls)
        with self.assertRaises(ReconciliationError):
            h.check_controls(replace(controls, continue_on_error=0))

    def test_catalog_is_fresh_deterministic_and_bound(self):
        from tools import c07_remaining as h
        a, b = h.build_definitions(), h.build_definitions()
        self.assertEqual(a, b)
        self.assertEqual(len({d.case.case_id for d in a}), len(a))
        self.assertEqual(len({d.snapshot_sha256 for d in a}), len(a))
        for d in a:
            self.assertNotEqual(d.snapshot_sha256,
                                replace(d, refs=()).snapshot_sha256)
            with self.assertRaises(ReconciliationError):
                h.check_definition(replace(d, refs=()), reports_for(h.definition_plan(d)),
                                   supported=True)


if __name__ == "__main__":
    unittest.main()
