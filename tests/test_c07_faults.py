"""Integrated inert fault-driver engineering tests; no scanner is invoked."""

import unittest
from dataclasses import replace

from tools import c07_faults as faults


class FaultDriverTests(unittest.TestCase):
    def test_all_finite_faults_and_clean_control_cross_required_boundary(self):
        result = faults.run_fault_suite(faults.OfflineFaultBackend())
        self.assertEqual(result["counts"], {"CLEAN": 1, "P11": 10, "P12": 34, "P14": 13})
        self.assertEqual(result["status"], "ENGINEERING_ONLY")
        self.assertEqual(result["execution_status"], "NOT_ADMITTED")
        self.assertFalse(result["qualified"])
        self.assertEqual(len(result["trials"]), 58)
        self.assertEqual({r["required_exit"] for r in result["trials"]}, {0, 1})

    def test_swallowed_failure_or_missing_counterexample_is_not_credited(self):
        reference = faults.OfflineFaultBackend()

        class Swallow:
            def exercise(self, trial):
                result = reference.exercise(trial)
                return replace(result, required_exit=0)

        with self.assertRaises(faults.DriverError):
            faults.run_fault_suite(Swallow())

        class NoCounterexample:
            def exercise(self, trial):
                if trial.family == "P11":
                    clean = next(t for t in faults.fault_trials() if t.family == "CLEAN")
                    return replace(reference.exercise(clean), trial_sha256=trial.snapshot_sha256,
                                   required_exit=1)
                return reference.exercise(trial)

        with self.assertRaises(faults.DriverError):
            faults.run_fault_suite(NoCounterexample())

    def test_wrong_binding_and_backend_exception_preserve_failure(self):
        reference = faults.OfflineFaultBackend()

        class WrongBinding:
            def exercise(self, trial):
                return replace(reference.exercise(trial), trial_sha256="0" * 64)

        class BrokenBackend:
            def exercise(self, trial):
                raise OSError("must not escape into sanitized report")

        for backend in (WrongBinding(), BrokenBackend()):
            with self.subTest(backend=type(backend).__name__):
                with self.assertRaises(faults.DriverError) as caught:
                    faults.run_fault_suite(backend)
                self.assertNotIn("must not escape", str(caught.exception))

    def test_unrelated_rejection_cannot_stand_in_for_each_named_fault(self):
        reference = faults.OfflineFaultBackend()
        wrong_version = next(t for t in faults.fault_trials()
                             if t.family == "P12" and t.name == "wrong-version")

        class SubstitutedFault:
            def exercise(self, trial):
                if trial.family in {"P12", "P14"}:
                    return replace(reference.exercise(wrong_version),
                                   trial_sha256=trial.snapshot_sha256)
                return reference.exercise(trial)

        with self.assertRaises(faults.DriverError):
            faults.run_fault_suite(SubstitutedFault())

    def test_manifest_binds_every_mutation_lane_and_case(self):
        trials = faults.fault_trials()
        self.assertEqual(trials, faults.fault_trials())
        operational = [t for t in trials if t.family == "P12"]
        self.assertEqual({t.lane for t in operational}, {"baseline", "candidate"})
        self.assertEqual(len({t.snapshot_sha256 for t in trials}), 58)
        for trial in trials:
            if trial.family == "P11":
                self.assertEqual({c.requirement for c in trial.cases},
                                 {"P03", "P04", "P05", "P06", "P07"})
        original = next(t for t in trials if t.family == "P11")
        changed = replace(original, name="unapproved")
        self.assertNotEqual(original.snapshot_sha256, changed.snapshot_sha256)
        with self.assertRaises(faults.DriverError):
            faults.OfflineFaultBackend().exercise(changed)


if __name__ == "__main__":
    unittest.main()
