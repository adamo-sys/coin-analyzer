"""Foundation preflight acceptance tests use only synthetic temporary repos."""

from contextlib import chdir, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('task_state', ROOT / 'tools/task-state.py')
assert SPEC is not None and SPEC.loader is not None
task_state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(task_state)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.env = mock.patch.dict(os.environ, {
            'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_AUTHOR_NAME': 'Synthetic Test', 'GIT_AUTHOR_EMAIL': 'test@example.invalid',
            'GIT_COMMITTER_NAME': 'Synthetic Test', 'GIT_COMMITTER_EMAIL': 'test@example.invalid',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.git('init', '-b', 'main')
        (self.repo / 'source.txt').write_text('synthetic baseline\n', encoding='utf-8')
        self.git('add', 'source.txt')
        self.git('commit', '-m', 'Synthetic baseline')
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.git('update-ref', 'refs/remotes/origin/main', self.base)

    def git(self, *args):
        result = subprocess.run(['git', '-c', 'commit.gpgSign=false', *args],
                                cwd=self.repo, check=True, capture_output=True, text=True)
        return result.stdout

    def invoke(self, *args):
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = task_state.main(['preflight', '--repo', str(self.repo),
                                    '--task-class', 'tooling', '--format', 'json', *args])
        return code, json.loads(stream.getvalue())

    def commit_change(self):
        (self.repo / 'source.txt').write_text('synthetic change\n', encoding='utf-8')
        self.git('add', 'source.txt')
        self.git('commit', '-m', 'Synthetic change')

    def test_clean_expected_branch_and_head(self):
        code, report = self.invoke('--expect-branch', 'main', '--expect-head', self.base, '--require-clean')
        self.assertEqual(code, 0)
        self.assertTrue(report['working_tree']['tracked_clean'])
        self.assertEqual(report['repository']['head'], self.base)
        self.assertEqual(report['relationships']['head_vs_local_main'], {'ahead': 0, 'behind': 0})

    def test_dirty_staged_unstaged_and_scoped_untracked_counts(self):
        (self.repo / 'source.txt').write_text('staged', encoding='utf-8')
        self.git('add', 'source.txt')
        (self.repo / 'source.txt').write_text('unstaged', encoding='utf-8')
        (self.repo / 'new.txt').write_text('synthetic', encoding='utf-8')
        (self.repo / 'unrelated.txt').write_text('synthetic', encoding='utf-8')
        code, report = self.invoke('--require-clean', '--expect-path', 'new.txt')
        self.assertEqual(code, 4)
        state = report['working_tree']
        self.assertEqual((state['staged_count'], state['unstaged_count'], state['untracked_count']), (1, 1, 1))
        self.assertIsNone(state['untracked_total'])
        self.assertNotIn('unrelated.txt', json.dumps(report))

    def test_detached_head_expected_branch_mismatch(self):
        self.git('checkout', '--detach', self.base)
        code, report = self.invoke('--expect-branch', 'main')
        self.assertEqual(code, 4)
        self.assertIsNone(report['repository']['branch'])
        self.assertIn('expected_branch', report['mismatches'])

    def test_stale_recorded_origin_and_local_main_divergence(self):
        self.commit_change()
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report['relationships']['local_main_vs_recorded_origin_main'], {'ahead': 1, 'behind': 0})
        self.assertEqual(report['evidence']['remote_freshness'], 'unverified_local_ref_only')

    def test_candidate_already_merged(self):
        self.git('branch', 'candidate')
        self.commit_change()
        _, report = self.invoke('--candidate-branch', 'candidate')
        self.assertEqual(report['candidate']['unique_commits_vs_main'], 0)
        self.assertTrue(report['candidate']['ancestrally_merged_into_main'])

    def test_candidate_unique_work_and_file_difference(self):
        self.git('checkout', '-b', 'candidate')
        self.commit_change()
        _, report = self.invoke('--candidate-branch', 'candidate', '--expect-path', 'source.txt')
        self.assertEqual(report['candidate']['unique_commits_vs_main'], 1)
        self.assertFalse(report['candidate']['ancestrally_merged_into_main'])
        self.assertFalse(report['paths'][0]['head_equals_main'])

    def test_missing_candidate_is_observation(self):
        code, report = self.invoke('--candidate-branch', 'not-created')
        self.assertEqual(code, 0)
        self.assertFalse(report['candidate']['exists'])
        self.assertIsNone(report['candidate']['ancestrally_merged_into_main'])

    def test_invalid_candidate_is_argument_error(self):
        for name in ('bad..branch', 'foo//bar', '-bad', 'HEAD'):
            with self.subTest(name=name):
                self.assertEqual(self.invoke('--candidate-branch=' + name)[0], 2)

    def test_missing_expected_path(self):
        code, report = self.invoke('--expect-path', 'missing.txt')
        self.assertEqual(code, 4)
        self.assertIn('expected_path_missing', report['mismatches'])

    def test_scope_and_filename_mismatch(self):
        (self.repo / 'source.txt').write_text('synthetic change', encoding='utf-8')
        code, report = self.invoke('--scope-path', 'other.txt', '--expect-path', 'source.txt')
        self.assertEqual(code, 4)
        self.assertIn('tracked_changes_outside_scope', report['mismatches'])
        self.assertIn('expected_path_outside_scope', report['mismatches'])

    def test_identical_committed_file_does_not_claim_working_file_equivalence(self):
        (self.repo / 'source.txt').write_text('unstaged change', encoding='utf-8')
        _, report = self.invoke('--expect-path', 'source.txt')
        self.assertTrue(report['paths'][0]['head_equals_main'])
        self.assertEqual(report['evidence']['file_equivalence'], 'committed_HEAD_vs_local_main_only')
        self.assertFalse(report['working_tree']['tracked_clean'])

    def test_malformed_config_and_schema(self):
        for value in ('invalid: [', '{}', 'schema_version: 1\nschema_version: 1',
                      '!!python/object/apply:os.system [echo unsafe]'):
            with self.subTest(value=value):
                config = self.repo / 'config.yml'
                config.write_text(value, encoding='utf-8')
                code, report = self.invoke('--config', str(config))
                self.assertEqual(code, 2)
                self.assertIn('error', report)

    def test_invalid_task_profile_schema(self):
        config = task_state.load_config(ROOT / '.ops/tasks.yml')
        config['task_classes']['tooling']['validation_profile'] = 'missing'
        path = self.repo / 'config.yml'
        path.write_text(json.dumps(config), encoding='utf-8')
        self.assertEqual(self.invoke('--config', str(path))[0], 2)

    def test_missing_git_and_controlled_failure_redact_raw_output(self):
        with mock.patch.object(task_state.subprocess, 'run', side_effect=FileNotFoundError):
            self.assertEqual(self.invoke()[0], 3)
        failure = subprocess.CompletedProcess([], 128, b'', b'private-path-secret')
        with mock.patch.object(task_state.subprocess, 'run', return_value=failure):
            code, report = self.invoke()
            self.assertEqual(code, 3)
            self.assertNotIn('private-path-secret', json.dumps(report))

    def test_protected_paths_never_get_path_git_queries(self):
        run = task_state.Git.run
        queried = []

        def record(instance, *args, **kwargs):
            queried.append(args)
            return run(instance, *args, **kwargs)

        with mock.patch.object(task_state.Git, 'run', record):
            code, report = self.invoke('--expect-path', 'data/private.json', '--expect-path', 'photos/coin.JPG')
        self.assertEqual(code, 4)
        self.assertEqual(report['blocked_path_count'], 2)
        self.assertEqual(report['paths'], [])
        self.assertFalse(any('data/private.json' in arg or 'photos/coin.JPG' in arg for call in queried for arg in call))
        self.assertNotIn('private.json', json.dumps(report))

    def test_unsafe_literal_paths_are_rejected(self):
        for path in ('../secret', '/absolute', 'C:/secret', 'dir\\secret', ':(glob)*', 'a/../b', '.git/config'):
            with self.subTest(path=path):
                code, _ = self.invoke('--expect-path', path)
                self.assertIn(code, (2, 4))

    def test_directory_request_does_not_enumerate_children(self):
        (self.repo / 'folder').mkdir()
        (self.repo / 'folder/child.txt').write_text('synthetic', encoding='utf-8')
        code, report = self.invoke('--expect-path', 'folder')
        self.assertEqual(code, 4)
        self.assertEqual(report['working_tree']['untracked_count'], 0)
        self.assertNotIn('child.txt', json.dumps(report))

    def test_output_stability_and_required_fields(self):
        first = self.invoke()
        self.assertEqual(first, self.invoke())
        self.assertEqual(set(first[1]), {'schema_version', 'operation', 'repository', 'relationships',
                                        'working_tree', 'paths', 'blocked_path_count', 'candidate',
                                        'task', 'mismatches', 'evidence'})
        self.assertIn('# Task preflight', task_state.markdown(first[1]))

    def test_windows_aliases_rejected_before_git_or_filesystem_access(self):
        for value in ('data./private.yml', 'notes /private.yml', 'TEST_C~1/photo.txt', 'aux.txt', 'COM1'):
            with self.subTest(value=value):
                with mock.patch.object(task_state.Git, 'run', side_effect=AssertionError('Git must not run')):
                    self.assertEqual(self.invoke('--expect-path', value)[0], 2)
                config = self.repo / value
                with mock.patch.object(task_state, 'linked_path', side_effect=AssertionError('No filesystem access')):
                    self.assertEqual(self.invoke('--config', str(config))[0], 2)

    def test_config_cannot_disable_minimum_protection(self):
        config = task_state.load_config(ROOT / '.ops/tasks.yml')
        config['protected_paths'] = ['additional-private-folder']
        path = self.repo / 'config.yml'
        path.write_text(json.dumps(config), encoding='utf-8')
        code, report = self.invoke('--config', str(path), '--expect-path', '.git/config')
        self.assertEqual(code, 4)
        self.assertEqual(report['blocked_path_count'], 1)

    def test_config_in_protected_folder_rejected_before_metadata_access(self):
        with mock.patch.object(task_state, 'linked_path', side_effect=AssertionError('No filesystem access')):
            for value in ('data/secret.yml', 'benchmarks/phone-photo-v1/secret.yml'):
                self.assertEqual(self.invoke('--config', str(self.repo / value))[0], 2)

    def test_relative_config_under_protected_cwd_rejected_before_inspection(self):
        for directory in ('data', 'notes', 'benchmarks/phone-photo-v1'):
            with self.subTest(directory=directory):
                cwd = self.repo / directory
                cwd.mkdir(parents=True, exist_ok=True)
                with chdir(cwd), \
                        mock.patch.object(task_state, 'linked_path', side_effect=AssertionError('No metadata inspection')), \
                        mock.patch.object(Path, 'read_text', side_effect=AssertionError('No config read')):
                    code, report = self.invoke('--config', 'config.yml')
                self.assertEqual(code, 2)
                self.assertIn('protected', report['error'])

    def test_config_traversal_rejected_before_absolute_path_or_inspection(self):
        for value in ('../config.yml', 'allowed/../../config.yml',
                      str(self.repo / 'allowed/../config.yml')):
            with self.subTest(value=value):
                with mock.patch.object(Path, 'absolute', side_effect=AssertionError('No normalization')), \
                        mock.patch.object(task_state, 'linked_path', side_effect=AssertionError('No metadata inspection')):
                    self.assertEqual(self.invoke('--config', value)[0], 2)

    def test_allowed_relative_config_uses_same_absolute_path_for_all_access(self):
        content = (ROOT / '.ops/tasks.yml').read_text(encoding='utf-8')
        expected = self.repo / 'config.yml'
        expected.write_text(content, encoding='utf-8')
        observed = []
        real_stat, real_read = Path.stat, Path.read_text

        def inspect_stat(path, *args, **kwargs):
            observed.append(('stat', path))
            return real_stat(path, *args, **kwargs)

        def inspect_read(path, *args, **kwargs):
            observed.append(('read', path))
            return real_read(path, *args, **kwargs)

        with chdir(self.repo), \
                mock.patch.object(task_state, 'linked_path', return_value=False) as links, \
                mock.patch.object(Path, 'stat', inspect_stat), \
                mock.patch.object(Path, 'read_text', inspect_read), \
                mock.patch.object(Path, 'resolve', side_effect=AssertionError('Must not follow links')):
            config = task_state.load_config(Path('config.yml'))
        self.assertEqual(config['schema_version'], 1)
        links.assert_called_once_with(expected)
        self.assertEqual(observed, [('stat', expected), ('read', expected)])

    def test_allowed_absolute_config_ignores_protected_cwd(self):
        path = self.repo / 'config.yml'
        path.write_text((ROOT / '.ops/tasks.yml').read_text(encoding='utf-8'), encoding='utf-8')
        protected_cwd = self.repo / 'data'
        protected_cwd.mkdir()
        with chdir(protected_cwd):
            config = task_state.load_config(path)
        self.assertEqual(config['schema_version'], 1)

    def test_reparse_point_is_blocked_without_following_it(self):
        metadata = mock.Mock(st_mode=0, st_file_attributes=0x400)
        with mock.patch.object(Path, 'lstat', return_value=metadata):
            self.assertTrue(task_state.linked_path(self.repo / 'linked'))

    def test_missing_main_and_origin_are_unavailable(self):
        self.git('checkout', '-b', 'feature')
        self.git('branch', '-D', 'main')
        self.git('update-ref', '-d', 'refs/remotes/origin/main')
        code, report = self.invoke('--candidate-branch', 'feature')
        self.assertEqual(code, 0)
        self.assertIsNone(report['repository']['local_main'])
        self.assertIsNone(report['relationships']['head_vs_recorded_origin_main'])
        self.assertIsNone(report['candidate']['unique_commits_vs_main'])

    def test_shallow_history_does_not_claim_ancestry_counts(self):
        self.commit_change()
        tip = self.git('rev-parse', 'HEAD').strip()
        (self.repo / '.git/shallow').write_text(tip + '\n', encoding='ascii')
        code, report = self.invoke('--candidate-branch', 'main')
        self.assertEqual(code, 0)
        self.assertTrue(report['repository']['shallow'])
        self.assertTrue(all(v is None for v in report['relationships'].values()))
        self.assertIsNone(report['candidate']['ancestrally_merged_into_main'])

    def test_ignored_file_not_counted_as_untracked(self):
        (self.repo / '.gitignore').write_text('ignored.txt\n', encoding='utf-8')
        (self.repo / 'ignored.txt').write_text('synthetic', encoding='utf-8')
        code, report = self.invoke('--expect-path', 'ignored.txt')
        self.assertEqual(code, 0)
        self.assertEqual(report['working_tree']['untracked_count'], 0)

    def test_rename_scope_includes_both_sides_and_handles_spaces(self):
        self.git('mv', 'source.txt', 'new name.txt')
        code, report = self.invoke('--scope-path', 'new name.txt')
        self.assertEqual(code, 4)
        self.assertEqual(report['working_tree']['tracked_changes_outside_scope'], 1)
        self.assertEqual(report['working_tree']['staged_count'], 2)

    def test_expected_head_mismatch(self):
        code, report = self.invoke('--expect-head', '0' * 40)
        self.assertEqual(code, 4)
        self.assertIn('expected_head', report['mismatches'])

    def test_unborn_head_is_missing_prerequisite(self):
        self.git('checkout', '--orphan', 'unborn')
        self.assertEqual(self.invoke()[0], 3)

    def test_no_mutation_and_only_bounded_read_only_git_commands(self):
        def snapshot():
            return {str(p.relative_to(self.repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in self.repo.rglob('*') if p.is_file()}

        before = snapshot()
        run = task_state.subprocess.run
        with mock.patch.object(task_state.subprocess, 'run', wraps=run) as observed:
            self.assertEqual(self.invoke('--expect-path', 'source.txt', '--candidate-branch', 'main')[0], 0)
        self.assertEqual(before, snapshot())
        allowed = {'rev-parse', 'symbolic-ref', 'status', 'ls-files', 'ls-tree', 'check-ref-format', 'rev-list'}
        for call in observed.call_args_list:
            command = call.args[0]
            self.assertEqual(command[:4], ['git', '--no-optional-locks', '-c', 'core.fsmonitor=false'])
            self.assertIn(command[4], allowed)
            self.assertEqual(call.kwargs['env']['GIT_NO_LAZY_FETCH'], '1')
            self.assertEqual(call.kwargs['timeout'], 15)


if __name__ == '__main__':
    unittest.main()
