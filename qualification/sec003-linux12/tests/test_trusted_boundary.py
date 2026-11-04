"""New boundary controls only. Synthetic Git objects, approvals and keys.
Removing source pins, external paths, request binding or HMAC checks breaks tests.
No git commit command; fixture objects are manually constructed in test temp space.
"""
import argparse
import copy
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
import zlib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source'))  # Test runner only; worker uses -I -S.
try:
    import trusted_boundary as boundary
except ImportError:
    boundary = None


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def module(path):
    spec = importlib.util.spec_from_file_location('reference_matcher', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scanner = shutil.which('gitleaks')
        cls.git = shutil.which('git')
        if not cls.scanner or not cls.git:
            raise RuntimeError('required existing tools missing; qualification never skips')
        cls.matcher = module(ROOT / 'source/occurrence_verifier.py')
        cls.temp = tempfile.TemporaryDirectory(prefix='sec003-trust10-')
        cls.root = Path(cls.temp.name)
        cls.repo = cls.root / 'candidate'
        cls.repo.mkdir()
        db = cls.repo / '.git'
        (db/'objects').mkdir(parents=True)
        (db/'refs/heads').mkdir(parents=True)
        (db/'refs/sec003').mkdir(parents=True)
        (db/'HEAD').write_text('ref: refs/heads/main\n')
        (db/'config').write_text('[core]\nrepositoryformatversion = 0\nbare = false\n')
        def obj(kind, raw):
            data = kind.encode() + b' ' + str(len(raw)).encode() + b'\0' + raw
            oid = hashlib.sha1(data).hexdigest()
            p = db/'objects'/oid[:2]/oid[2:]
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(zlib.compress(data))
            return oid
        def tree(name, data):
            blob = obj('blob', data)
            return obj('tree', b'100644 ' + name.encode() + b'\0' + bytes.fromhex(blob))
        def commit(tree_oid, parent=None):
            header = 'tree ' + tree_oid + '\n'
            if parent:
                header += 'parent ' + parent + '\n'
            header += ('author Synthetic <synthetic@example.invalid> 978307200 +0000\n'
                       'committer Synthetic <synthetic@example.invalid> 978307200 +0000\n\nSynthetic only\n')
            return obj('commit', header.encode())
        marker = 'C07Z' + sha(b'SEC003 C07 inert marker Trust10')
        first = commit(tree('fixture.py', ('api_key = "' + marker + '"\n').encode()))
        # These malicious replacements are actual candidate Git objects, not only
        # untracked files. Build trees directly; never execute or commit PR code.
        hostile = {
            'README.md': b'Synthetic clean tip; historical marker removed.\n',
            'tools/security/occurrence_verifier.py': b"open('EXECUTED','w').write('bad')\n",
            'sitecustomize.py': b"open('EXECUTED','w').write('bad')\n",
            '.github/workflows/tests.yml': b'name: SEC003 trusted Gitleaks\njobs: {}\n',
            'result.json': b'{"result":"PASS","conclusion":"success"}',
            'approval.json': b'{"decision":"approved","records":[]}',
        }
        def nested_tree(files):
            groups = {}
            entries = []
            for path, content in files.items():
                first_part, sep, rest = path.partition('/')
                if sep:
                    groups.setdefault(first_part, {})[rest] = content
                else:
                    entries.append((first_part, b'100644', obj('blob', content)))
            for name, children in groups.items():
                entries.append((name, b'40000', nested_tree(children)))
            # Git tree ordering treats directories as name + '/'.
            entries.sort(key=lambda item: item[0] + ('/' if item[1] == b'40000' else ''))
            raw = b''.join(mode+b' '+name.encode()+b'\0'+bytes.fromhex(oid)
                           for name, mode, oid in entries)
            return obj('tree', raw)
        cls.head = commit(nested_tree(hostile), first)
        (db/'refs/heads/main').write_text(cls.head+'\n')
        (db/'refs/sec003/candidate').write_text(cls.head+'\n')
        # One baseline scanner acquisition authors test-only approval bytes in memory.
        scan = cls.matcher.scan_history(cls.repo, cls.scanner, sha(Path(cls.scanner).read_bytes()))
        rows = json.loads(scan['report'])
        if len(rows) != 1 or rows[0]['Commit'] != first:
            raise RuntimeError('synthetic full-history positive control failed')
        records = []
        for row in rows:
            oid = cls.matcher.git(cls.repo, 'rev-parse', row['Commit']+':'+row['File']).decode().strip()
            blob = cls.matcher.git(cls.repo, 'cat-file', 'blob', oid)
            selected = b''.join(blob.splitlines(keepends=True)[row['StartLine']-1:row['EndLine']])
            records.append(dict(identity={k:row[k] for k in cls.matcher.IDENTITY},
                                finding_sha256=sha(wire(row)),blob_oid=oid,
                                blob_sha256=sha(blob),lines_sha256=sha(selected)))
        cls.approval_bytes = wire(dict(schema=1,classification='OCCURRENCE_APPROVAL',decision='approved',
                                     approver='Synthetic test owner',decision_ref='synthetic:Trust10',records=records))
        cls.inventory = scan['inventory_sha256']

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.assertIsNotNone(boundary, 'trusted external boundary is not implemented')
        self.control = self.root / uuid.uuid4().hex
        self.control.mkdir()
        self.addCleanup(shutil.rmtree, self.control)
        self.source = self.control/'occurrence_verifier.py'
        shutil.copyfile(ROOT/'source/occurrence_verifier.py', self.source)
        self.approval = self.control/'approval.json'
        self.approval.write_bytes(self.approval_bytes)
        self.key = self.control/'worker.key'
        self.key.write_bytes(os.urandom(32))
        self.request = dict(repository='adamo-sys/coin-analyzer',candidate_sha=self.head,
                            attempt_id=uuid.uuid4().hex)
        self.policy = dict(schema=1,**self.request,inventory_sha256=self.inventory,
                           verifier_sha256=sha(self.source.read_bytes()),
                           scanner_sha256=sha(Path(self.scanner).read_bytes()),
                           git_sha256=sha(Path(self.git).read_bytes()),
                           approval_sha256=sha(self.approval_bytes))
        self.args = argparse.Namespace(candidate=str(self.repo),verifier=str(self.source),
            approval=str(self.approval),key=str(self.key),scanner=self.scanner,git=self.git,
            policy=str(self.control/'policy.json'),policy_sha256='',**self.request)
        self.pin_policy()

    def pin_policy(self):
        raw = wire(self.policy)
        Path(self.args.policy).write_bytes(raw)
        self.args.policy_sha256 = sha(raw)
        self.request['policy_sha256'] = self.args.policy_sha256
        self.request['inventory_sha256'] = self.inventory

    def run_worker(self):
        return boundary.run(self.args)

    def check(self, result):
        return boundary.check_payload(wire(result), self.key.read_bytes(), self.request, self.request)

    def reject(self):
        with self.assertRaises(boundary.Rejected):
            self.run_worker()

    def test_full_history_real_scanner_and_authenticated_check_payload(self):
        result = self.run_worker()
        self.assertEqual(result['decision']['approved_occurrences'], 1)
        payload = self.check(result)
        self.assertEqual(payload['name'], 'SEC003 trusted Gitleaks')
        self.assertEqual(payload['head_sha'], self.head)
        self.assertEqual(payload['conclusion'], 'success')
        self.assertEqual(payload['external_id'], self.request['attempt_id'])

    def test_candidate_code_workflow_and_forged_pass_never_execute(self):
        # A replacement matcher, Python startup and YAML can only be scan data.
        marker = self.repo/'EXECUTED'
        paths = {'tools/security/occurrence_verifier.py':"open('EXECUTED','w').write('bad')\n",
                 'sitecustomize.py':"open('EXECUTED','w').write('bad')\n",
                 '.github/workflows/tests.yml':'name: SEC003 trusted Gitleaks\njobs: {}\n',
                 'result.json':'{"result":"PASS","conclusion":"success"}',
                 'approval.json':'{"decision":"approved","records":[]}'}
        for name, text in paths.items():
            p = self.repo/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)
        try:
            # Isolated child is the actual external launcher entry point.
            cmd = [sys.executable, '-I', '-S', str(ROOT/'source/trusted_boundary.py')]
            for name, value in vars(self.args).items():
                cmd.extend(['--'+name.replace('_','-'), str(value)])
            proc = subprocess.run(cmd,cwd=self.repo,capture_output=True,timeout=60)
            self.assertEqual(proc.returncode,0,proc.stdout.decode())
            self.assertEqual(self.check(json.loads(proc.stdout))['conclusion'],'success')
            self.assertFalse(marker.exists())
            # Unapproved historical occurrence still cannot be suppressed by these files.
            self.approval.write_bytes(wire(dict(schema=1,classification='OCCURRENCE_APPROVAL',
                 decision='approved',approver='Synthetic',decision_ref='synthetic:empty',records=[])))
            self.policy['approval_sha256']=sha(self.approval.read_bytes())
            self.pin_policy()
            self.reject()
        finally:
            for name in paths:
                (self.repo/name).unlink()

    def test_external_verifier_modified_rejects_before_execution(self):
        marker=self.control/'EXECUTED'
        self.source.write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n')
        self.reject()
        self.assertFalse(marker.exists())

    def test_candidate_verifier_path_and_own_pin_are_not_authority(self):
        candidate=self.repo/'evil.py'
        candidate.write_text('raise RuntimeError("candidate execution")\n')
        self.addCleanup(candidate.unlink)
        self.args.verifier=str(candidate)
        self.policy['verifier_sha256']=sha(candidate.read_bytes())
        self.pin_policy()
        self.reject()

    def test_policy_substitution_without_external_digest_rejects(self):
        changed=copy.deepcopy(self.policy)
        changed['approval_sha256']='0'*64
        Path(self.args.policy).write_bytes(wire(changed))
        self.reject()

    def test_forged_approval_bytes_reject(self):
        self.approval.write_text('{"decision":"approved","records":[]}')
        self.reject()

    def test_missing_evidence_rejects(self):
        for name in ('approval','policy','verifier','key'):
            with self.subTest(name=name):
                old=getattr(self.args,name)
                setattr(self.args,name,str(self.control/'missing'))
                try:
                    self.reject()
                finally:
                    setattr(self.args,name,old)

    def test_missing_scanner_rejects(self):
        self.args.scanner=str(self.control/'missing.exe')
        self.reject()

    def test_scanner_identity_change_rejects(self):
        self.policy['scanner_sha256']='0'*64
        self.pin_policy()
        self.reject()

    def test_authenticated_wrong_scanner_fails_version(self):
        self.args.scanner=self.git
        self.policy['scanner_sha256']=sha(Path(self.git).read_bytes())
        self.pin_policy()
        self.reject()

    def test_scanner_process_and_completion_failures_cannot_sign_pass(self):
        # Inject only the external scanner process; real wrapper/source/hash/Git/
        # completion/matching logic runs. This is not native scanner qualification.
        real_run=subprocess.run
        for mode in ('exit_error','killed','malformed','missing_summary','timeout'):
            def injected(argv, *args, **kwargs):
                if Path(argv[0]).resolve()==Path(self.scanner).resolve() and argv[1]=='git':
                    if mode=='timeout':
                        raise subprocess.TimeoutExpired(argv,1)
                    code={'exit_error':1,'killed':-9}.get(mode,0)
                    report=b'broken' if mode=='malformed' else b'[]'
                    return subprocess.CompletedProcess(argv,code,report,b'')
                return real_run(argv,*args,**kwargs)
            with self.subTest(mode=mode), patch('subprocess.run',side_effect=injected):
                self.reject()

    def test_git_identity_change_rejects(self):
        self.policy['git_sha256']='0'*64
        self.pin_policy()
        self.reject()

    def test_wrong_candidate_sha_and_ref_reject(self):
        self.args.candidate_sha='0'*40
        self.reject()
        self.args.candidate_sha=self.head
        ref=self.repo/'.git/refs/sec003/candidate'
        ref.write_text('0'*40+'\n')
        try:
            self.reject()
        finally:
            ref.write_text(self.head+'\n')

    def test_inventory_subset_or_stale_fetch_receipt_rejects(self):
        self.policy['inventory_sha256']='0'*64
        self.pin_policy()
        self.reject()

    def test_unapproved_historical_occurrence_rejects(self):
        doc=json.loads(self.approval_bytes)
        doc['records']=[]
        self.approval.write_bytes(wire(doc))
        self.policy['approval_sha256']=sha(self.approval.read_bytes())
        self.pin_policy()
        self.reject()

    def test_check_publisher_rejects_unkeyed_forged_missing_and_stale_evidence(self):
        result=self.run_worker()
        for raw in (b'',b'{"result":"PASS"}',wire({'decision':result['decision'],'mac':'0'*64})):
            with self.subTest(raw_kind=len(raw)), self.assertRaises(boundary.Rejected):
                boundary.check_payload(raw,self.key.read_bytes(),self.request,self.request)
        changed=copy.deepcopy(result)
        changed['decision']['candidate_sha']='0'*40
        with self.assertRaises(boundary.Rejected):
            self.check(changed)
        current=dict(self.request,candidate_sha='0'*40)
        with self.assertRaises(boundary.Rejected):
            boundary.check_payload(wire(result),self.key.read_bytes(),self.request,current)
        stale=dict(self.request,attempt_id='f'*32)
        with self.assertRaises(boundary.Rejected):
            boundary.check_payload(wire(result),self.key.read_bytes(),stale,stale)

    def test_check_publisher_rejects_authenticated_nonpass_or_extra_fields(self):
        result=self.run_worker()
        for change in ({'result':'REJECTED'},{'approved_occurrences':True},{'extra':'PASS'}):
            d=dict(result['decision'],**change)
            env={'decision':d,'mac':hmac.new(self.key.read_bytes(),wire(d),hashlib.sha256).hexdigest()}
            with self.subTest(change=change), self.assertRaises(boundary.Rejected):
                self.check(env)

    def test_duplicate_json_policy_rejects(self):
        raw=wire(self.policy)
        raw=raw[:-1]+b',"schema":1}'
        Path(self.args.policy).write_bytes(raw)
        self.args.policy_sha256=sha(raw)
        self.reject()

    def test_cli_missing_evidence_nonzero_no_pass(self):
        proc=subprocess.run([sys.executable,'-I','-S',str(ROOT/'source/trusted_boundary.py')],
                            capture_output=True,timeout=10)
        self.assertNotEqual(proc.returncode,0)
        self.assertNotIn(b'PASS',proc.stdout)


if __name__=='__main__':
    unittest.main(verbosity=2)
