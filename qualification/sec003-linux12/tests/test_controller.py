"""Synthetic controller controls; mock only GitHub, not worker/verifier logic.
Removing event HMAC, identity/freshness, pins, ownership or ledger checks must
allow a rejected case to publish success and fail these assertions.
"""
import copy
from contextlib import closing
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
import uuid
from unittest.mock import patch

import test_trusted_boundary as fixtures
from test_trusted_boundary import wire, sha
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'source'))
try:
    import controller
except ImportError:
    controller = None

REPO = '/repos/adamo-sys/coin-analyzer'
SECRET = b'SYNTHETIC webhook secret 32 bytes!!'

class MockGitHub:
    """No network. Stateful Check Runs and current PR; no real credential."""
    def __init__(self, pr):
        self.pr = pr
        self.checks = {}
        self.calls = []
        self.pr_reads = 0
        self.change_on_second_read = False
        self.corrupt = None
        self.unavailable = False
        self.principal = dict(app_id=77, installation_id=88, repository_id=99)
    def identity(self, token):
        if self.unavailable or token != b'synthetic-installation-token':
            raise OSError('synthetic authentication unavailable')
        return copy.deepcopy(self.principal)
    def request(self, method, path, body, token):
        self.identity(token)
        self.calls.append((method, path, copy.deepcopy(body)))
        if method == 'GET' and path == REPO:
            return dict(id=99, full_name='adamo-sys/coin-analyzer')
        if method == 'GET' and path == REPO+'/pulls/7':
            self.pr_reads += 1
            pr = copy.deepcopy(self.pr)
            if self.change_on_second_read and self.pr_reads >= 2:
                pr['head']['sha'] = 'a'*40
            return pr
        if method == 'POST' and path == REPO+'/check-runs':
            value = dict(body, id=123, app=dict(id=77))
            self.checks[123] = value
        elif method == 'PATCH' and path == REPO+'/check-runs/123':
            self.checks[123].update(body)
            value = self.checks[123]
        else:
            raise AssertionError('unexpected synthetic API route')
        value = copy.deepcopy(value)
        if self.corrupt:
            self.corrupt(value)
        return value

class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.BoundaryTests.setUpClass()
    @classmethod
    def tearDownClass(cls):
        fixtures.BoundaryTests.tearDownClass()
    def setUp(self):
        self.assertIsNotNone(controller, 'controller not implemented')
        self.fx = fixtures.BoundaryTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)
        f = self.fx
        repo = dict(id=99, full_name='adamo-sys/coin-analyzer')
        self.pr = dict(number=7, state='open', base=dict(ref='main', sha=f.head, repo=repo),
                       head=dict(ref='synthetic-controller', sha=f.head, repo=repo))
        self.event = dict(action='synchronize', number=7, repository=repo,
                          installation=dict(id=88), pull_request=copy.deepcopy(self.pr))
        self.api = MockGitHub(copy.deepcopy(self.pr))
        self.job = controller.Job(candidate=str(f.repo), verifier=str(f.source),
            approval=str(f.approval), scanner=f.scanner, git=f.git,
            candidate_sha=f.head, base_sha=f.head, head_ref='synthetic-controller',
            inventory_sha256=f.inventory, approval_sha256=sha(f.approval_bytes),
            scanner_sha256=sha(Path(f.scanner).read_bytes()),
            git_sha256=sha(Path(f.git).read_bytes()))
        self.kw = dict(job=self.job, transport=self.api, webhook_secret=SECRET,
            token=b'synthetic-installation-token', app_id=77, installation_id=88,
            repository_id=99, state_path=f.control/'attempts.sqlite',
            control_root=f.control, boundary_path=Path(__file__).resolve().parents[1]/'source/trusted_boundary.py')
        self.c = controller.Controller(**self.kw)
    def send(self, event=None, headers=None, raw=None):
        if raw is None:
            payload=copy.deepcopy(self.event if event is None else event)
            payload['sender']={'id':uuid.uuid4().int,'login':'synthetic-only'}
            raw=wire(payload)
        h = {'x-github-event':'pull_request','x-github-delivery':str(uuid.uuid4()),
             'x-hub-signature-256':'sha256='+hmac.new(SECRET,raw,hashlib.sha256).hexdigest()}
        h.update(headers or {})
        return self.c.handle(raw,h)
    def rejected(self, **kw):
        self.assertEqual(self.send(**kw)['result'], 'REJECTED')
        self.assertFalse(any(v.get('conclusion')=='success' for v in self.api.checks.values()))
    def test_authenticated_full_history_success_and_retained_evidence(self):
        result = self.send()
        self.assertEqual(result['result'],'PASS')
        check = self.api.checks[123]
        self.assertEqual(check['name'],'sec003/trusted-gitleaks')
        self.assertEqual(check['head_sha'],self.fx.head)
        self.assertEqual(check['conclusion'],'success')
        self.assertIn(result['evidence_sha256'],check['output']['summary'])
        with closing(sqlite3.connect(self.kw['state_path'])) as db:
            row=db.execute('select candidate_sha, evidence_sha256, state from attempts').fetchone()
        self.assertEqual(row,(self.fx.head,result['evidence_sha256'],'passed'))
    def test_unsigned_or_forged_webhook(self):
        for sig in ('','sha1='+'0'*40,'sha256='+'0'*64):
            with self.subTest(sig=sig): self.rejected(headers={'x-hub-signature-256':sig})
    def test_malformed_signed_event(self):
        for raw in (b'{}',b'[]',b'null',b'{',b'{"action":1,"action":2}',b'{"n":NaN}'):
            with self.subTest(raw=raw): self.rejected(raw=raw)
    def test_wrong_event_type_and_delivery(self):
        for h in ({'x-github-event':'check_run'},{'x-github-event':'push'},
                  {'x-github-delivery':'../bad'}):
            with self.subTest(h=h): self.rejected(headers=h)
    def test_foreign_repository_identity(self):
        for key,value in (('id',100),('id',True),('full_name','attacker/coin-analyzer')):
            e=copy.deepcopy(self.event);e['repository'][key]=value
            with self.subTest(key=key,value=value): self.rejected(event=e)
    def test_installation_action_number_types(self):
        for change in ('installation','action','number'):
            e=copy.deepcopy(self.event)
            if change=='installation': e['installation']['id']=89
            elif change=='action': e['action']='closed'
            else: e['number']=True
            with self.subTest(change=change): self.rejected(event=e)
    def test_unauthorized_base_or_fork_or_ref(self):
        for change in ('base','fork','ref','closed'):
            e=copy.deepcopy(self.event);pr=e['pull_request']
            if change=='base':pr['base']['ref']='other'
            if change=='fork':pr['head']['repo']['id']=100
            if change=='ref':pr['head']['ref']='../../main'
            if change=='closed':pr['state']='closed'
            with self.subTest(change=change):self.rejected(event=e)
    def test_changed_event_sha_or_base(self):
        for side in ('head','base'):
            e=copy.deepcopy(self.event);e['pull_request'][side]['sha']='a'*40
            with self.subTest(side=side):self.rejected(event=e)
    def test_stale_api_head(self):
        self.api.pr['head']['sha']='a'*40
        self.rejected()
    def test_sha_changes_during_scan(self):
        self.api.change_on_second_read=True
        self.rejected()
        self.assertEqual(self.api.checks[123]['conclusion'],'failure')
    def test_repository_and_app_identity_transport_confusion(self):
        for field in ('app_id','installation_id','repository_id'):
            self.api.principal[field]+=1
            with self.subTest(field=field):self.rejected()
            self.api.principal[field]-=1
    def test_unavailable_credentials(self):
        for token in (None,b'',b'wrong'):
            self.c=controller.Controller(**dict(self.kw,token=token))
            with self.subTest(token=bool(token)):self.rejected()
        self.c=controller.Controller(**self.kw);self.api.unavailable=True
        self.rejected()
    def test_webhook_secret_unavailable(self):
        self.c=controller.Controller(**dict(self.kw,webhook_secret=b''))
        self.rejected()
    def test_replay_after_restart_is_consumed_even_on_failure(self):
        delivery=str(uuid.uuid4())
        self.api.unavailable=True
        self.rejected(headers={'x-github-delivery':delivery})
        self.api.unavailable=False
        self.c=controller.Controller(**self.kw)
        self.rejected(headers={'x-github-delivery':delivery})
    def test_database_context_closes_handle(self):
        with self.c.database() as db:
            self.assertEqual(db.execute('select 1').fetchone(),(1,))
        try:
            with self.assertRaises(sqlite3.ProgrammingError):db.execute('select 1')
        finally:db.close()
    def test_signed_body_replay_with_changed_unsigned_delivery_header(self):
        raw=wire(self.event)
        self.api.unavailable=True
        self.rejected(raw=raw)
        self.api.unavailable=False
        self.rejected(raw=raw)  # Same signed body, different UUID delivery header.
    def test_ledger_unavailable(self):
        self.c=controller.Controller(**dict(self.kw,state_path=self.fx.control/'missing'/'db'))
        self.rejected()
    def test_forged_check_run_response(self):
        for field in ('app','id','head_sha','external_id','name','status'):
            def corrupt(v):
                v[field]={'id':15368} if field=='app' else (True if field=='id' else 'forged')
            self.api.corrupt=corrupt
            with self.subTest(field=field):self.rejected()
            self.api.checks.clear()
    def test_forged_completed_response_cannot_claim_engineering_pass(self):
        def corrupt(v):
            if v.get('status')=='completed':v['conclusion']='neutral'
        self.api.corrupt=corrupt
        self.rejected()
    def test_candidate_verifier_replacement_rejected_before_execution(self):
        self.fx.source.write_text("raise RuntimeError('candidate replacement executed')")
        self.rejected()
    def test_boundary_source_substitution(self):
        replacement=self.fx.control/'boundary.py'
        marker=self.fx.control/'EXECUTED'
        replacement.write_text('open('+repr(str(marker))+',"w").write("bad")')
        self.c=controller.Controller(**dict(self.kw,boundary_path=replacement))
        self.rejected();self.assertFalse(marker.exists())
    def test_forged_approval_or_invalid_anchor(self):
        self.fx.approval.write_bytes(b'{"decision":"approved","records":[]}')
        self.rejected()
    def test_missing_approval(self):
        self.fx.approval.unlink();self.rejected()
    def test_missing_historical_approval_fails_closed(self):
        d=json.loads(self.fx.approval_bytes);d['records']=[]
        self.fx.approval.write_bytes(wire(d))
        from dataclasses import replace
        self.job=replace(self.job,approval_sha256=sha(wire(d)))
        self.c=controller.Controller(**dict(self.kw,job=self.job));self.rejected()
    def test_missing_git_object(self):
        ref=self.fx.repo/'.git/refs/sec003/candidate'
        old=ref.read_bytes();ref.write_text('a'*40+'\n')
        try:self.rejected()
        finally:ref.write_bytes(old)
    def test_missing_blob_object(self):
        objects=list((self.fx.repo/'.git/objects').glob('*/*'))
        import zlib
        p=next(p for p in objects if zlib.decompress(p.read_bytes()).startswith(b'blob '))
        raw=p.read_bytes();p.unlink()
        try:self.rejected()
        finally:p.write_bytes(raw)
    def test_shallow_history(self):
        p=self.fx.repo/'.git/shallow';p.write_text(self.fx.head+'\n')
        try:self.rejected()
        finally:p.unlink()
    def test_scanner_failure_timeout_and_incomplete_report(self):
        real=subprocess.run
        for mode in ('error','timeout','incomplete'):
            def injected(argv,*args,**kw):
                if Path(argv[0]).resolve()==Path(self.fx.scanner).resolve() and argv[1]=='git':
                    if mode=='timeout':raise subprocess.TimeoutExpired(argv,1)
                    return subprocess.CompletedProcess(argv,1 if mode=='error' else 0,b'[]',b'')
                return real(argv,*args,**kw)
            with self.subTest(mode=mode),patch('subprocess.run',side_effect=injected):self.rejected()
    def test_create_failure_consumes_attempt_and_restart_cannot_retry(self):
        raw=wire(self.event)
        real=self.api.request
        def broken(method,path,body,token):
            if method=='POST':raise OSError('synthetic create outage')
            return real(method,path,body,token)
        with patch.object(self.api,'request',side_effect=broken):self.rejected(raw=raw)
        self.c=controller.Controller(**self.kw)
        self.rejected(raw=raw)
        with closing(sqlite3.connect(self.kw['state_path'])) as db:
            self.assertEqual(db.execute('select state from attempts').fetchall(),[('rejected',)])
    def test_publication_failure_never_returns_pass(self):
        real=self.api.request
        def broken(method,path,body,token):
            if method=='PATCH' and body.get('conclusion')=='success':
                raise OSError('synthetic publication outage')
            return real(method,path,body,token)
        with patch.object(self.api,'request',side_effect=broken):self.rejected()
        self.assertEqual(self.api.checks[123]['conclusion'],'failure')
    def test_success_response_loss_is_rejected_and_not_retried(self):
        raw=wire(self.event)
        real=self.api.request
        def lost(method,path,body,token):
            if method=='PATCH':
                if body.get('conclusion')=='success':real(method,path,body,token)
                raise OSError('synthetic response loss; cleanup unavailable')
            return real(method,path,body,token)
        with patch.object(self.api,'request',side_effect=lost):
            self.assertEqual(self.send(raw=raw)['result'],'REJECTED')
        # Authenticated evidence already completed; remote success may have applied.
        # Handler cannot promise remote failure after ambiguous transport loss.
        self.assertEqual(self.api.checks[123]['conclusion'],'success')
        with closing(sqlite3.connect(self.kw['state_path'])) as db:
            state,evidence=db.execute('select state,evidence_sha256 from attempts').fetchone()
        self.assertEqual(state,'rejected');self.assertRegex(evidence,'^[0-9a-f]{64}$')
        self.c=controller.Controller(**self.kw)
        self.assertEqual(self.send(raw=raw)['result'],'REJECTED')
    def test_worker_result_substitution(self):
        # Trust-10 validates MAC and exact request even if worker channel is replaced.
        real=self.c.load_boundary
        for mode in ('forged','changed_sha','stale_attempt'):
            def load():
                boundary=real();run=boundary.run
                def substituted(args):
                    envelope=run(args)
                    if mode=='forged':envelope['mac']='0'*64
                    elif mode=='changed_sha':envelope['decision']['candidate_sha']='a'*40
                    else:envelope['decision']['attempt_id']='f'*32
                    if mode!='forged':
                        key=Path(args.key).read_bytes()
                        envelope['mac']=hmac.new(key,wire(envelope['decision']),hashlib.sha256).hexdigest()
                    return envelope
                boundary.run=substituted
                return boundary
            with self.subTest(mode=mode),patch.object(self.c,'load_boundary',side_effect=load):self.rejected()

if __name__=='__main__':unittest.main(verbosity=2)
