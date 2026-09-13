import unittest
from unittest.mock import patch

from command_center import collect_repository_status, project_repository_status, project_run_status
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




class RepositoryStatusTests(unittest.TestCase):
    def test_clean_feature_branch_is_ready(self):
        status = project_repository_status('feature/test', 'abc123', 'origin/feature/test', True)
        self.assertEqual(status.state, 'READY')
        self.assertFalse(status.on_default_branch)

    def test_dirty_feature_branch_is_dirty(self):
        status = project_repository_status('feature/test', 'abc123', 'origin/feature/test', False)
        self.assertEqual(status.state, 'DIRTY')
        self.assertIn('Review tracked changes', status.next_authorized_action)

    def test_detached_head_is_stopped(self):
        status = project_repository_status('', 'abc123', None, True)
        self.assertEqual(status.state, 'STOPPED')
        self.assertIn('Restore an authorized named non-default branch', status.next_authorized_action)

    def test_default_branch_is_stopped(self):
        status = project_repository_status('main', 'abc123', 'origin/main', True)
        self.assertEqual(status.state, 'STOPPED')
        self.assertTrue(status.on_default_branch)


if __name__ == "__main__":
    unittest.main()
