import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from command_center import (
    CommandCenterAuthority,
    CommandCenterSnapshot,
    collect_repository_status,
    project_command_center_snapshot,
    project_operator_status,
    project_repository_status,
    project_run_status,
)
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

    def test_custom_default_branch_is_stopped(self):
        status = project_repository_status(
            'develop', 'abc123', 'origin/develop', True,
            default_branch='develop',
        )
        self.assertEqual(status.state, 'STOPPED')
        self.assertTrue(status.on_default_branch)
        self.assertEqual(
            status.next_authorized_action,
            'Move implementation work to an authorized non-default branch.',
        )


    def test_dirty_custom_default_branch_is_stopped(self):
        status = project_repository_status(
            'develop', 'abc123', 'origin/develop', False,
            default_branch='develop',
        )
        self.assertFalse(status.clean)
        self.assertTrue(status.on_default_branch)
        self.assertEqual(status.state, 'STOPPED')
        self.assertEqual(
            status.next_authorized_action,
            'Move implementation work to an authorized non-default branch.',
        )


class CommandCenterSnapshotTests(unittest.TestCase):
    def test_ready_repository_with_pending_human_review(self):
        repository = project_repository_status('feature/test', 'abc123', None, True)
        run = project_run_status(make_run(OrchestratorState.READY_FOR_HUMAN_REVIEW))
        snapshot = project_command_center_snapshot(repository, run)

        self.assertIs(snapshot.repository, repository)
        self.assertIs(snapshot.run, run)
        self.assertEqual(snapshot.repository.state, 'READY')
        self.assertEqual(snapshot.run.state, 'NEEDS_AUTHORIZATION')
        self.assertTrue(snapshot.human_review_pending)
        self.assertIs(snapshot.execution_authority, CommandCenterAuthority.OBSERVATION_ONLY)

    def test_stopped_repository_does_not_hide_active_run(self):
        for branch in ('', 'main'):
            with self.subTest(branch=branch):
                repository = project_repository_status(branch, 'abc123', None, True)
                run = project_run_status(make_run(OrchestratorState.DIAGNOSED))
                snapshot = project_command_center_snapshot(repository, run)

                self.assertIs(snapshot.repository, repository)
                self.assertIs(snapshot.run, run)
                self.assertEqual(snapshot.repository.state, 'STOPPED')
                self.assertEqual(snapshot.run.state, 'DIAGNOSED')
                self.assertFalse(snapshot.human_review_pending)

    def test_dirty_repository_preserves_stopped_run_and_reason_fallback(self):
        for reason in ('review failed', None):
            with self.subTest(reason=reason):
                repository = project_repository_status('feature/test', 'abc123', None, False)
                run = project_run_status(make_run(OrchestratorState.STOPPED, reason))
                snapshot = project_command_center_snapshot(repository, run)

                self.assertIs(snapshot.repository, repository)
                self.assertIs(snapshot.run, run)
                self.assertEqual(snapshot.repository.state, 'DIRTY')
                self.assertEqual(snapshot.run.state, 'STOPPED')
                self.assertEqual(
                    snapshot.run.blocker,
                    reason or 'Orchestrator stopped without a terminal reason.',
                )
                self.assertIn('no automatic resume', snapshot.run.next_authorized_action)
                self.assertFalse(snapshot.human_review_pending)

    def test_all_state_combinations_remain_observation_only_without_side_effects(self):
        with patch('command_center.subprocess.run') as execute:
            for branch in ('feature/test', 'main', ''):
                for clean in (True, False):
                    for state in OrchestratorState:
                        with self.subTest(branch=branch, clean=clean, state=state):
                            repository = project_repository_status(branch, 'abc123', None, clean)
                            run = project_run_status(make_run(state))
                            snapshot = project_command_center_snapshot(repository, run)

                            self.assertIs(snapshot.repository, repository)
                            self.assertIs(snapshot.run, run)
                            self.assertIs(
                                snapshot.execution_authority,
                                CommandCenterAuthority.OBSERVATION_ONLY,
                            )
                            self.assertEqual(
                                snapshot.human_review_pending,
                                state is OrchestratorState.READY_FOR_HUMAN_REVIEW,
                            )
            execute.assert_not_called()

    def test_snapshot_and_components_are_immutable(self):
        repository = project_repository_status('feature/test', 'abc123', None, True)
        run = project_run_status(make_run(OrchestratorState.DIAGNOSED))
        snapshot = project_command_center_snapshot(repository, run)
        for target, attribute, value in (
            (snapshot, 'repository', repository),
            (snapshot, 'run', run),
            (snapshot, 'execution_authority', 'execute'),
            (snapshot, 'human_review_pending', True),
            (repository, 'state', 'READY'),
            (run, 'human_authorization_required', True),
        ):
            with self.subTest(attribute=attribute):
                with self.assertRaises(FrozenInstanceError):
                    setattr(target, attribute, value)

    def test_constructor_cannot_accept_execution_authority(self):
        repository = project_repository_status('feature/test', 'abc123', None, True)
        run = project_run_status(make_run(OrchestratorState.DIAGNOSED))
        self.assertRaises(TypeError, CommandCenterSnapshot, repository, run, "execute")


class OperatorStatusTests(unittest.TestCase):
    def snapshot(self, branch="feature/test", clean=True,
                 state=OrchestratorState.DIAGNOSED, reason=None):
        return project_command_center_snapshot(
            project_repository_status(branch, "abc123", None, clean),
            project_run_status(make_run(state, reason)),
        )

    def test_ordinary_run_has_compact_state_result_action_output(self):
        snapshot = self.snapshot()
        self.assertEqual(project_operator_status(snapshot), (
            "STATE: DIAGNOSED | repository=READY | run=DIAGNOSED | "
            "authority=observation_only | human_review_pending=no\n"
            "RESULT: Orchestrator run is not terminal.\n"
            "NEXT ACTION: Observe the current bounded run; Command Center takes no action."
        ))

    def test_repository_stopped_precedes_run_and_exposes_branch_reason(self):
        for branch in ("main", ""):
            with self.subTest(branch=branch):
                snapshot = self.snapshot(branch=branch)
                output = project_operator_status(snapshot)
                self.assertTrue(output.startswith("STATE: STOPPED |"))
                self.assertIn("run=DIAGNOSED", output)
                self.assertIn(f"branch={branch!r}", output)
                self.assertIn(f"on_default_branch={branch == 'main'}", output)
                self.assertTrue(output.endswith(snapshot.repository.next_authorized_action))

    def test_dirty_repository_selects_tracked_change_review(self):
        snapshot = self.snapshot(clean=False)
        output = project_operator_status(snapshot)
        self.assertTrue(output.startswith("STATE: DIRTY |"))
        self.assertIn("Repository has tracked changes.", output)
        self.assertTrue(output.endswith(snapshot.repository.next_authorized_action))

    def test_stopped_run_preserves_blocker_including_missing_reason_fallback(self):
        for reason in ("review failed", None):
            with self.subTest(reason=reason):
                snapshot = self.snapshot(state=OrchestratorState.STOPPED, reason=reason)
                output = project_operator_status(snapshot)
                self.assertTrue(output.startswith("STATE: STOPPED |"))
                self.assertIn(f"Blocker: {snapshot.run.blocker}", output)
                self.assertTrue(output.endswith(snapshot.run.next_authorized_action))

    def test_human_review_is_needs_authorization(self):
        snapshot = self.snapshot(state=OrchestratorState.READY_FOR_HUMAN_REVIEW)
        output = project_operator_status(snapshot)
        self.assertTrue(output.startswith("STATE: NEEDS_AUTHORIZATION |"))
        self.assertIn("human_review_pending=yes", output)
        self.assertTrue(output.endswith(snapshot.run.next_authorized_action))

    def test_conflicting_states_have_deterministic_actions_and_keep_review_visible(self):
        cases = (
            ("main", True, OrchestratorState.STOPPED, "STOPPED", "repository"),
            ("main", True, OrchestratorState.READY_FOR_HUMAN_REVIEW, "STOPPED", "repository"),
            ("feature/test", False, OrchestratorState.STOPPED, "STOPPED", "run"),
            ("feature/test", False, OrchestratorState.READY_FOR_HUMAN_REVIEW, "DIRTY", "repository"),
        )
        for branch, clean, state, expected, winner in cases:
            with self.subTest(branch=branch, clean=clean, state=state):
                snapshot = self.snapshot(branch, clean, state, "review failed")
                output = project_operator_status(snapshot)
                self.assertEqual(output, project_operator_status(snapshot))
                self.assertTrue(output.startswith(f"STATE: {expected} |"))
                self.assertIn(f"repository={snapshot.repository.state}", output)
                self.assertIn(f"run={snapshot.run.state}", output)
                self.assertTrue(output.endswith(getattr(snapshot, winner).next_authorized_action))
                if snapshot.human_review_pending:
                    self.assertIn("run=NEEDS_AUTHORIZATION", output)
                    self.assertIn("human_review_pending=yes", output)
                if snapshot.run.blocker:
                    self.assertIn(f"Blocker: {snapshot.run.blocker}", output)

    def test_all_states_are_pure_observations_without_authority_override(self):
        snapshots = [
            self.snapshot(branch, clean, state)
            for branch in ("feature/test", "main", "")
            for clean in (True, False)
            for state in OrchestratorState
        ]
        before = repr(snapshots)
        with (
            patch("command_center.collect_repository_status") as collect,
            patch("command_center._git") as git,
            patch("command_center.subprocess.run") as execute,
            patch("orchestrator.execute_orchestrator_run") as orchestrate,
            patch("builtins.open") as open_file,
        ):
            for snapshot in snapshots:
                output = project_operator_status(snapshot)
                self.assertIsInstance(output, str)
                self.assertIn("authority=observation_only", output)
                self.assertIs(snapshot.execution_authority, CommandCenterAuthority.OBSERVATION_ONLY)
            self.assertRaises(
                TypeError, project_operator_status, snapshots[0], execution_authority="execute"
            )
            for effect in (collect, git, execute, orchestrate, open_file):
                effect.assert_not_called()
        self.assertEqual(repr(snapshots), before)


if __name__ == "__main__":
    unittest.main()
