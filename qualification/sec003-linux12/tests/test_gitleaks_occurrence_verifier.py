"""Tests use only generated nonfunctional material and owned Git histories.
Removing exact identity/content or completion checks must break these controls.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from tools.security import occurrence_verifier as target
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parent
SYNTH = Path(tempfile.gettempdir())
SCANNER = shutil.which('gitleaks')
DIGEST = '8f397272f513c00b573f50380c4724e4b3ac759be1de313d907bb968c5d14c09'
OPTS = '--full-history --all --root -m --no-ext-diff --no-textconv'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

class History:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(dir=SYNTH, prefix='gate07-')
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.env = {k: v for k, v in os.environ.items() if k.upper() in
                    {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC'}}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_SYSTEM=os.devnull,
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM='1',
                        GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1',
                        GIT_ALLOW_PROTOCOL='', GIT_OPTIONAL_LOCKS='0', NO_COLOR='1',
                        GIT_AUTHOR_DATE='2001-01-01T00:00:00+0000',
                        GIT_COMMITTER_DATE='2001-01-01T00:00:00+0000')
        hooks = self.root / 'hooks'
        hooks.mkdir()
        settings = {'core.hooksPath': str(hooks), 'core.fsmonitor': 'false',
                    'core.autocrlf': 'false', 'commit.gpgSign': 'false',
                    'tag.gpgSign': 'false', 'protocol.allow': 'never',
                    'user.name': 'Gate07 Synthetic', 'user.email': 'gate07@example.invalid'}
        self.env['GIT_CONFIG_COUNT'] = str(len(settings))
        for i, (key, value) in enumerate(settings.items()):
            self.env[f'GIT_CONFIG_KEY_{i}'] = key
            self.env[f'GIT_CONFIG_VALUE_{i}'] = value
        template = self.root / 'template'
        template.mkdir()
        self.git('init', '-b', 'main', '--template=' + str(template))
        (self.repo / '.gate07-synthetic').write_bytes(b'GATE07 SYNTHETIC ONLY\n')
        self.commit = self.write('fixture.py', 'A')

    def git(self, *args):
        p = subprocess.run(['git', *args], cwd=self.repo, env=self.env,
                           capture_output=True, timeout=20)
        if p.returncode:
            raise RuntimeError('synthetic_git_failure')
        return p.stdout

    def write(self, path, label, padding=0):
        # Public deterministic seeds only; no issued provider credential.
        value = 'C07Z' + sha(('SEC003 C07 inert marker ' + label).encode())
        data = ('# synthetic\n' * padding + 'api' + '_key = "' + value + '"\n').encode()
        dest = self.repo / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        self.git('add', '--', path)
        self.git('commit', '-m', 'Synthetic fixture ' + label)
        return self.git('rev-parse', 'HEAD').decode().strip()

    def cleanup(self):
        # Windows Git objects can be read-only. All paths stay in this owned temp root.
        def repair(func, path, exc):
            os.chmod(path, 0o700)
            func(path)
        shutil.rmtree(self.root, onerror=repair)
        self.temp.cleanup()

    def inventory(self):
        refs = self.git('for-each-ref', '--format=%(refname) %(objectname)')
        commits = self.git('rev-list', '--all').splitlines()
        return sha(refs + b'\0' + b'\n'.join(sorted(commits))), len(commits)

    def scan_stub(self):
        row = {'RuleID': 'generic-api-key', 'File': 'fixture.py',
               'StartLine': 1, 'EndLine': 1, 'StartColumn': 12, 'EndColumn': 79,
               'Commit': self.commit, 'Fingerprint': self.commit + ':fixture.py:generic-api-key:1',
               'Secret': 'REDACTED', 'Match': 'api_key = "REDACTED"',
               'Author': 'Gate07 Synthetic', 'Email': 'gate07@example.invalid'}
        raw = wire([row])
        inventory, count = self.inventory()
        return {'report': raw, 'report_sha256': sha(raw), 'exit_code': 2,
                'complete': True, 'commit_count': count, 'finding_count': 1,
                'inventory_sha256': inventory}

    def approval(self, scan):
        # Independent test authoring; verifier never creates approvals.
        records = []
        for row in json.loads(scan['report']):
            oid = self.git('rev-parse', row['Commit'] + ':' + row['File']).decode().strip()
            blob = self.git('cat-file', 'blob', oid)
            lines = blob.splitlines(keepends=True)
            records.append({'identity': {key: row[key] for key in
                           ('Commit', 'File', 'RuleID', 'StartLine', 'EndLine', 'StartColumn', 'EndColumn')},
                            'finding_sha256': sha(wire(row)), 'blob_oid': oid,
                            'blob_sha256': sha(blob),
                            'lines_sha256': sha(b''.join(lines[row['StartLine']-1:row['EndLine']]))})
        doc = {'schema': 1, 'classification': 'OCCURRENCE_APPROVAL',
               'decision': 'approved', 'approver': 'Synthetic Owner',
               'decision_ref': 'https://example.invalid/synthetic-decision', 'records': records}
        raw = wire(doc)
        return raw, sha(raw)

class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.h = History()
        self.addCleanup(self.h.cleanup)
        self.scan = self.h.scan_stub()
        self.approval, self.anchor = self.h.approval(self.scan)

    def check(self, scan=None, approval=None, anchor=None):
        return target.verify(self.h.repo, self.scan if scan is None else scan,
                             self.approval if approval is None else approval,
                             self.anchor if anchor is None else anchor)

    def mutate_row(self, key, value):
        scan = copy.deepcopy(self.scan)
        rows = json.loads(scan['report'])
        rows[0][key] = value
        scan['report'] = wire(rows)
        scan['report_sha256'] = sha(scan['report'])
        return scan

    def test_exact_known_occurrence(self):
        self.assertEqual(self.check(), 1)

    def test_changed_secret_and_forged_fingerprint(self):
        with self.assertRaises(target.Rejected):
            self.check(self.mutate_row('Secret', 'SUBSTITUTED_SYNTHETIC'))

    def test_changed_file_identity(self):
        with self.assertRaises(target.Rejected):
            self.check(self.mutate_row('File', 'other.py'))

    def test_changed_commit_identity(self):
        with self.assertRaises(target.Rejected):
            self.check(self.mutate_row('Commit', 'a' * 40))

    def test_relocated_line_identity(self):
        with self.assertRaises(target.Rejected):
            self.check(self.mutate_row('StartLine', 2))

    def test_changed_rule_or_columns(self):
        for key, value in [('RuleID', 'other-rule'), ('StartColumn', 13), ('EndColumn', 80)]:
            with self.subTest(key=key), self.assertRaises(target.Rejected):
                self.check(self.mutate_row(key, value))

    def test_added_genuine_secret_finding(self):
        scan = copy.deepcopy(self.scan)
        rows = json.loads(scan['report'])
        row = dict(rows[0], File='new.py')
        rows.append(row)
        scan.update(report=wire(rows), report_sha256=sha(wire(rows)), finding_count=2)
        with self.assertRaises(target.Rejected):
            self.check(scan)

    def test_missing_and_duplicate_findings(self):
        for rows in ([], json.loads(self.scan['report']) * 2):
            scan = dict(self.scan, report=wire(rows), report_sha256=sha(wire(rows)), finding_count=len(rows))
            with self.subTest(count=len(rows)), self.assertRaises(target.Rejected):
                self.check(scan)

    def test_incomplete_receipts_and_exit_collision(self):
        for key, value in [('complete', False), ('commit_count', 0), ('finding_count', 0),
                           ('exit_code', 1), ('exit_code', 0), ('exit_code', True),
                           ('report_sha256', '0'*64), ('inventory_sha256', '0'*64)]:
            with self.subTest(key=key), self.assertRaises(target.Rejected):
                self.check(dict(self.scan, **{key: value}))

    def test_malformed_scanner_results(self):
        for raw in (b'', b'[', b'null', b'{}', b'[{}]', b'[NaN]',
                    b'[{"RuleID":"a","RuleID":"b"}]'):
            with self.subTest(kind=len(raw)), self.assertRaises(target.Rejected):
                self.check(dict(self.scan, report=raw, report_sha256=sha(raw)))

    def test_missing_or_altered_approval_evidence(self):
        for raw in (b'', b'{}', self.approval + b' ', b'null'):
            with self.subTest(kind=len(raw)), self.assertRaises(target.Rejected):
                self.check(approval=raw)
        with self.assertRaises(target.Rejected):
            self.check(anchor='0'*64)

    def test_reanchored_inconsistent_blob_evidence(self):
        for key in ('blob_oid', 'blob_sha256', 'lines_sha256', 'finding_sha256'):
            doc = json.loads(self.approval)
            doc['records'][0][key] = '0' * (40 if key == 'blob_oid' else 64)
            raw = wire(doc)
            with self.subTest(key=key), self.assertRaises(target.Rejected):
                self.check(approval=raw, anchor=sha(raw))

    def test_ambiguous_or_missing_approval_records(self):
        for records in ([], json.loads(self.approval)['records'] * 2):
            doc = json.loads(self.approval)
            doc['records'] = records
            raw = wire(doc)
            with self.subTest(count=len(records)), self.assertRaises(target.Rejected):
                self.check(approval=raw, anchor=sha(raw))

    def test_metadata_does_not_establish_approval(self):
        doc = json.loads(self.approval)
        doc['decision'] = 'unreviewed'
        raw = wire(doc)
        with self.assertRaises(target.Rejected):
            self.check(approval=raw, anchor=sha(raw))

    def test_unsafe_paths_and_bad_types(self):
        for key, value in [('File', '../fixture.py'), ('File', '/fixture.py'),
                           ('File', 'C:/fixture.py'), ('StartLine', True),
                           ('StartLine', 0), ('EndLine', 10000), ('Secret', None)]:
            with self.subTest(key=key, kind=type(value).__name__), self.assertRaises(target.Rejected):
                self.check(self.mutate_row(key, value))

    def test_scope_guard_rejects_non_repository(self):
        with self.assertRaises(target.Rejected):
            target.verify(self.h.root, self.scan, self.approval, self.anchor)

    def test_well_formed_truncation_disagrees_with_scanner_receipt(self):
        raw = b'[]'
        with self.assertRaises(target.Rejected):
            self.check(dict(self.scan, report=raw, report_sha256=sha(raw)))

    def test_history_changes_after_scan(self):
        self.h.write('new.py', 'B')
        with self.assertRaises(target.Rejected):
            self.check()

class AcquisitionControlsTests(unittest.TestCase):
    def setUp(self):
        self.h = History()
        self.addCleanup(self.h.cleanup)

    def fake_scan(self, code=2, raw=None, log=None):
        receipt = self.h.scan_stub()
        raw = receipt['report'] if raw is None else raw
        log = (b'1 commits scanned.\nscanned ~100 bytes in 1ms\nleaks found: 1\n'
               if log is None else log)
        calls = []
        def command(repo, argv, timeout=30, git_dir=None):
            calls.append(argv)
            if argv[-1] == 'version':
                return subprocess.CompletedProcess(argv, 0, b'8.24.3\n', b'')
            if len(argv) > 1 and argv[1] == 'git':
                return subprocess.CompletedProcess(argv, code, raw, log)
            return original(repo, argv, timeout, git_dir=git_dir)
        original = target.command
        with patch.object(target, 'command', side_effect=command):
            scan = target.scan_history(self.h.repo, sys.executable,
                                       sha(Path(sys.executable).read_bytes()))
        return scan, calls

    def test_acquisition_retains_exact_full_history_defaults_and_no_suppression(self):
        _, calls = self.fake_scan()
        argv = next(x for x in calls if len(x) > 1 and x[1] == 'git')
        self.assertIn('--log-opts=' + OPTS, argv)
        for option in ('--redact=100', '--exit-code=2', '--log-level=info',
                       '--no-banner', '--report-format=json', '--report-path=-',
                       '--ignore-gitleaks-allow'):
            self.assertIn(option, argv)
        self.assertTrue(any(x.startswith('--gitleaks-ignore-path=') for x in argv))
        self.assertEqual(target.CONFIG, b'[extend]\nuseDefault = true\n')

    def test_scanner_failure_malformed_output_and_missing_completion_fail_closed(self):
        for code, raw, log in ((1,None,None), (127,None,None), (2,b'',None),
                               (2,b'[',None), (2,b'[]',None), (2,None,b''),
                               (2,None,b'1 commits scanned.'),
                               (2,None,b'ERR synthetic'), (0,None,None)):
            with self.subTest(code=code, raw_length=None if raw is None else len(raw)), self.assertRaises(target.Rejected):
                self.fake_scan(code, raw, log)

    def test_inherited_credentials_configuration_and_git_overrides_are_removed(self):
        with patch.dict(os.environ, {'GITHUB_TOKEN':'synthetic', 'CI_TOKEN':'synthetic',
                         'SEC003_GITLEAKS_APPROVAL_SHA256':'synthetic',
                         'GITLEAKS_CONFIG':'synthetic', 'GIT_DIR':'synthetic',
                         'GIT_CONFIG_VALUE_99':'synthetic', 'HOME':'synthetic'}):
            env = target.environment(self.h.repo)
        for key in ('GITHUB_TOKEN','CI_TOKEN','SEC003_GITLEAKS_APPROVAL_SHA256',
                    'GITLEAKS_CONFIG','GIT_DIR','GIT_CONFIG_VALUE_99','HOME'):
            self.assertNotIn(key,env)
        self.assertEqual(env['GIT_NO_LAZY_FETCH'],'1')
        self.assertEqual(env['GIT_ALLOW_PROTOCOL'],'')

    def test_missing_anchor_and_unattested_provenance_reject(self):
        scan = self.h.scan_stub()
        raw, anchor = self.h.approval(scan)
        for bad in ('', 'not-a-digest', '0'*64):
            with self.subTest(anchor_length=len(bad)), self.assertRaises(target.Rejected):
                target.verify(self.h.repo,scan,raw,bad)
        for key in ('approver','decision_ref'):
            doc=json.loads(raw)
            doc[key]=' '
            altered=wire(doc)
            with self.subTest(key=key), self.assertRaises(target.Rejected):
                target.verify(self.h.repo,scan,altered,sha(altered))

    def test_missing_git_objects_reject(self):
        original=target.git
        def git(repo,*args):
            if '--missing=print' in args:
                return b'?' + b'0'*40 + b'\n'
            return original(repo,*args)
        with patch.object(target,'git',side_effect=git), self.assertRaises(target.Rejected):
            target.inventory(self.h.repo)

class ScannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SCANNER:
            raise unittest.SkipTest('installed_scanner_unavailable')
        if sha(Path(SCANNER).read_bytes()) != DIGEST:
            raise RuntimeError('installed_scanner_identity')

    def setUp(self):
        self.h = History()
        self.addCleanup(self.h.cleanup)

    def acquire(self):
        self.assertTrue(callable(getattr(target, 'scan_history', None)), 'scanner acquisition not implemented')
        return target.scan_history(self.h.repo, SCANNER, DIGEST)

    def test_real_exact_known_occurrence(self):
        scan = self.acquire()
        rows = json.loads(scan['report'])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['Commit'], self.h.commit)
        self.assertEqual(rows[0]['RuleID'], 'generic-api-key')
        self.assertEqual(rows[0]['File'], 'fixture.py')
        self.assertEqual(rows[0]['StartLine'], 1)
        approval, anchor = self.h.approval(scan)
        self.assertEqual(target.verify(self.h.repo, scan, approval, anchor), 1)

    def test_real_substitution_relocation_and_addition(self):
        scan = self.acquire()
        approval, anchor = self.h.approval(scan)
        self.h.write('fixture.py', 'B')
        substituted = self.acquire()
        self.assertTrue(any(r['Commit'] != self.h.commit for r in json.loads(substituted['report'])))
        with self.assertRaises(target.Rejected):
            target.verify(self.h.repo, substituted, approval, anchor)
        self.h.write('relocated.py', 'A', padding=5)
        moved = self.acquire()
        self.assertTrue(any(r['File'] == 'relocated.py' and r['StartLine'] == 6
                            for r in json.loads(moved['report'])))
        with self.assertRaises(target.Rejected):
            target.verify(self.h.repo, moved, approval, anchor)
        self.h.write('new.py', 'C')
        extra = self.acquire()
        self.assertTrue(any(r['File'] == 'new.py' for r in json.loads(extra['report'])))
        with self.assertRaises(target.Rejected):
            target.verify(self.h.repo, extra, approval, anchor)

    def test_real_deleted_and_unmerged_side_history(self):
        scan = self.acquire()
        approval, anchor = self.h.approval(scan)
        self.h.git('checkout', '-b', 'side')
        side = self.h.write('side.py', 'B')
        self.h.git('checkout', 'main')
        deleted = self.h.write('deleted.py', 'C')
        (self.h.repo / 'deleted.py').unlink()
        self.h.git('add', '--', 'deleted.py')
        self.h.git('commit', '-m', 'Synthetic deletion')
        scan = self.acquire()
        commits = {row['Commit'] for row in json.loads(scan['report'])}
        self.assertIn(side, commits)
        self.assertIn(deleted, commits)
        with self.assertRaises(target.Rejected):
            target.verify(self.h.repo, scan, approval, anchor)

    def test_cli_accepts_exact_and_rejects_altered_evidence_privately(self):
        scan = self.acquire()
        approval, anchor = self.h.approval(scan)
        evidence = self.h.root / 'synthetic-approval.json'
        evidence.write_bytes(approval)
        argv = [__import__('sys').executable, '-B', str(Path(target.__file__)),
                '--repo', str(self.h.repo), '--approval', str(evidence),
                '--scanner', SCANNER, '--scanner-sha256', DIGEST]
        p = subprocess.run(argv, cwd=ROOT, env=dict(self.h.env, SEC003_GITLEAKS_APPROVAL_SHA256=anchor), capture_output=True, timeout=40)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(json.loads(p.stdout), {'result': 'PASS', 'approved_occurrences': 1})
        evidence.write_bytes(approval + b' ')
        p = subprocess.run(argv, cwd=ROOT, env=dict(self.h.env, SEC003_GITLEAKS_APPROVAL_SHA256=anchor), capture_output=True, timeout=40)
        self.assertEqual(p.returncode, 1)
        self.assertEqual(p.stdout.strip(), b'{"result":"REJECTED"}')
        self.assertEqual(p.stderr, b'')

    def test_cli_missing_anchor_or_file_fails_privately(self):
        scan = self.acquire()
        approval, anchor = self.h.approval(scan)
        evidence=self.h.root/'approval.json'
        evidence.write_bytes(approval)
        argv=[sys.executable,'-B',str(Path(target.__file__)), '--repo',str(self.h.repo),
              '--approval',str(evidence),'--scanner',SCANNER,'--scanner-sha256',DIGEST]
        for env in (self.h.env, dict(self.h.env,SEC003_GITLEAKS_APPROVAL_SHA256='0'*64)):
            result=subprocess.run(argv,env=env,capture_output=True,timeout=40)
            self.assertEqual((result.returncode,result.stdout.strip(),result.stderr),
                             (1,b'{"result":"REJECTED"}',b''))
        evidence.unlink()
        result=subprocess.run(argv,env=dict(self.h.env,SEC003_GITLEAKS_APPROVAL_SHA256=anchor),
                              capture_output=True,timeout=40)
        self.assertEqual((result.returncode,result.stdout.strip(),result.stderr),
                         (1,b'{"result":"REJECTED"}',b''))

    def test_repository_ignore_and_inline_allow_cannot_suppress_occurrences(self):
        scan=self.acquire()
        original_count=scan['finding_count']
        (self.h.repo/'.gitleaksignore').write_text(json.loads(scan['report'])[0]['Fingerprint']+'\n')
        data=(self.h.repo/'fixture.py').read_text().rstrip()+' # gitleaks:allow\n'
        (self.h.repo/'fixture.py').write_text(data)
        self.h.git('add','fixture.py')
        self.h.git('commit','-m','Synthetic inline suppression control')
        scan=self.acquire()
        self.assertGreater(scan['finding_count'],original_count)

    def test_completion_parser_rejects_missing_conflicting_or_error_transcripts(self):
        self.assertTrue(callable(getattr(target, 'completion', None)), 'completion validator not implemented')
        for log in (b'', b'1 commits scanned', b'1 commits scanned\nleaks found: 1\nERR synthetic',
                    b'1 commits scanned\n2 commits scanned\nleaks found: 1'):
            with self.subTest(length=len(log)), self.assertRaises(target.Rejected):
                target.completion(log, 1, 1)

class WorkflowIntegrationTests(unittest.TestCase):
    def test_workflow_uses_authenticated_occurrence_gate(self):
        import yaml
        from tests.test_repository_privacy_boundaries import WorkflowLoader
        workflow = yaml.load((ROOT.parent / '.github/workflows/tests.yml').read_text(), Loader=WorkflowLoader)
        steps = workflow['jobs']['gitleaks']['steps']
        scan = steps[-1]
        self.assertIn('python -B tools/security/occurrence_verifier.py', scan['run'])
        self.assertEqual(scan['env']['SEC003_GITLEAKS_APPROVAL_SHA256'],
                         '${{ vars.SEC003_GITLEAKS_APPROVAL_SHA256 }}')
        self.assertNotIn('--approval-sha256', scan['run'])
        self.assertIn('--approval security/gitleaks-approvals.json', scan['run'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
