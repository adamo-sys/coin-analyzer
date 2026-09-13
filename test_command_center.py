import unittest

from command_center import project_run_status
from orchestrator import OrchestratorRun, OrchestratorState


def make_run(state, terminal_reason=None, human_review_required=False):
    return OrchestratorRun(run_id="run-1", state=state, diagnostic_finding=None, remediation_package=None, implementation_result=None, implementation_review=None, reviewer_report=None, transitions=(), terminal_reason=terminal_reason, human_review_required=human_review_required)


class CommandCenterTests(unittest.TestCase):
    def test_ready_for_human_review_requires_authorization(self):
        status = project_run_status(make_run(OrchestratorState.READY_FOR_HUMAN_REVIEW, human_review_required=True))
        self.assertEqual(status.state, "NEEDS_AUTHORIZATION")
        self.assertIsNone(status.blocker)
        self.assertTrue(status.human_authorization_required)

    def test_stopped_surfaces_blocker_and_no_auto_resume(self):
        status = project_run_status(make_run(OrchestratorState.STOPPED, terminal_reason="review failed"))
        self.assertEqual(status.state, "STOPPED")
        self.assertEqual(status.blocker, "review failed")
        self.assertIn("no automatic resume", status.next_authorized_action.lower())
        self.assertFalse(status.human_authorization_required)

    def test_nonterminal_is_observation_only(self):
        status = project_run_status(make_run(OrchestratorState.DIAGNOSED))
        self.assertEqual(status.state, "DIAGNOSED")
        self.assertIsNone(status.blocker)
        self.assertIn("takes no action", status.next_authorized_action)
        self.assertFalse(status.human_authorization_required)


if __name__ == "__main__":
    unittest.main()
