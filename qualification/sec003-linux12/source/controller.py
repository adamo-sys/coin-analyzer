"""Offline App-controller foundation. Launch trusted deployment with python -I -S.
Only the injected authenticated transport may contact GitHub in a future deployment.
This module has no networking, fetch, checkout, shell, or candidate-code execution.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import types
import uuid
from argparse import Namespace

REPOSITORY = 'adamo-sys/coin-analyzer'
CHECK_NAME = 'sec003/trusted-gitleaks'
BOUNDARY_SHA256 = 'ef756290d7a256e9cab7afc12cc3844622728156ce5147cc44a1afbc2c296d51'
VERIFIER_SHA256 = '675ee801e6ea12d943f0a39101c5d37370b2c99b73c368d7115ce84c9ace5e5d'

class Rejected(ValueError):
    pass

def require(value):
    if not value:
        raise Rejected('controller_rejected')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False))

def integer(value):
    return type(value) is int and value > 0

def digest(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{'+str(length)+'}', value)

@dataclass(frozen=True)
class Job:
    """Operator-authenticated immutable snapshot receipt, never event/PR input.
    Provision fresh full upstream objects and refs externally; pin inventory only
    after authenticating upstream scope. No fetch provenance is inferred locally.
    """
    candidate: str
    verifier: str
    approval: str
    scanner: str
    git: str
    candidate_sha: str
    base_sha: str
    head_ref: str
    inventory_sha256: str
    approval_sha256: str
    scanner_sha256: str
    git_sha256: str

class Controller:
    """Serialized handler; deployment must prevent candidate access to this TCB.

    transport.identity(token) -> authenticated app_id/installation_id/repository_id.
    transport.request(method, path, body_or_None, token) -> authenticated JSON.
    No transport default exists. A mock implements this protocol in the tests.
    Credentials and webhook secret are external protected bytes, never environment
    forwarded to scanner. SQLite is controller-owned durable single-use state.
    """
    def __init__(self, *, job, transport, webhook_secret, token, app_id,
                 installation_id, repository_id, state_path, control_root,
                 boundary_path):
        self.job = job
        self.transport = transport
        self.secret = webhook_secret
        self.token = token
        self.app_id = app_id
        self.installation_id = installation_id
        self.repository_id = repository_id
        self.state_path = Path(state_path)
        self.control_root = Path(control_root)
        self.boundary_path = Path(boundary_path)

    def repository_ok(self, value):
        require(isinstance(value, dict) and integer(value.get('id')))
        require(value['id'] == self.repository_id and value.get('full_name') == REPOSITORY)

    def pull_ok(self, pr, number):
        require(isinstance(pr, dict) and integer(pr.get('number')) and pr['number'] == number)
        require(pr.get('state') == 'open')
        for side in ('base', 'head'):
            require(isinstance(pr.get(side), dict))
            self.repository_ok(pr[side].get('repo'))
        require(pr['base'].get('ref') == 'main' and pr['base'].get('sha') == self.job.base_sha)
        require(pr['head'].get('ref') == self.job.head_ref and
                pr['head'].get('sha') == self.job.candidate_sha)

    def event(self, raw, headers):
        require(isinstance(self.secret, bytes) and len(self.secret) >= 32)
        require(isinstance(raw, bytes) and 0 < len(raw) <= 1048576)
        # HTTP ingress must provide these normalized header names; duplicates must
        # be rejected there, rather than collapsed by a permissive web framework.
        require(isinstance(headers, dict) and headers.get('x-github-event') == 'pull_request')
        signature = headers.get('x-hub-signature-256')
        require(isinstance(signature, str) and re.fullmatch('sha256=[0-9a-f]{64}', signature))
        require(hmac.compare_digest(signature, 'sha256='+hmac.new(self.secret, raw, hashlib.sha256).hexdigest()))
        delivery = headers.get('x-github-delivery')
        require(isinstance(delivery, str) and str(uuid.UUID(delivery)) == delivery)
        e = decode(raw)
        require(isinstance(e, dict) and e.get('action') in
                ('opened', 'synchronize', 'reopened', 'ready_for_review'))
        self.repository_ok(e.get('repository'))
        require(isinstance(e.get('installation'), dict) and integer(e['installation'].get('id'))
                and e['installation']['id'] == self.installation_id)
        require(integer(e.get('number')))
        self.pull_ok(e.get('pull_request'), e['number'])
        return delivery, e['number']

    @contextmanager
    def database(self):
        db = sqlite3.connect(self.state_path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def claim(self, delivery, attempt, event_digest):
        with self.database() as db:
            db.execute('CREATE TABLE IF NOT EXISTS attempts (delivery TEXT PRIMARY KEY, '
                       'attempt TEXT UNIQUE NOT NULL, candidate_sha TEXT NOT NULL, '
                       'event_sha256 TEXT UNIQUE NOT NULL, check_id INTEGER, evidence_sha256 TEXT, '
                       'evidence BLOB, policy BLOB, state TEXT NOT NULL)')
            db.execute('INSERT INTO attempts(delivery,attempt,candidate_sha,event_sha256,state) '
                       'VALUES(?,?,?,?,?)',
                       (delivery,attempt,self.job.candidate_sha,event_digest,'running'))

    def record(self, attempt, state, check_id=None, evidence=None, policy=None):
        with self.database() as db:
            cur = db.execute('UPDATE attempts SET state=?, check_id=COALESCE(?,check_id), '
                'evidence_sha256=COALESCE(?,evidence_sha256), evidence=COALESCE(?,evidence), '
                'policy=COALESCE(?,policy) WHERE attempt=?',
                (state,check_id,sha(evidence) if evidence is not None else None,evidence,policy,attempt))
            require(cur.rowcount == 1)

    def api(self, method, path, body=None):
        require(isinstance(self.token, bytes) and bool(self.token))
        principal = self.transport.identity(self.token)
        expected = dict(app_id=self.app_id, installation_id=self.installation_id,
                        repository_id=self.repository_id)
        require(isinstance(principal, dict) and set(principal) == set(expected))
        require(all(integer(principal[k]) and principal[k] == expected[k] for k in expected))
        return self.transport.request(method, '/repos/'+REPOSITORY+path, body, self.token)

    def current(self, number):
        self.repository_ok(self.api('GET', ''))
        self.pull_ok(self.api('GET', '/pulls/'+str(number)), number)

    def load_boundary(self):
        raw = self.boundary_path.read_bytes()
        require(sha(raw) == BOUNDARY_SHA256)
        module = types.ModuleType('sec003_pinned_boundary')
        exec(compile(raw, '<pinned-trust10-boundary>', 'exec'), module.__dict__)
        return module

    def config_ok(self):
        require(type(self.job) is Job and all(integer(v) for v in
                (self.app_id,self.installation_id,self.repository_id)))
        require(digest(self.job.candidate_sha,40) and digest(self.job.base_sha,40))
        require(isinstance(self.job.head_ref,str) and re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_/-]*',self.job.head_ref))
        require(all(digest(getattr(self.job,k)) for k in
                ('inventory_sha256','approval_sha256','scanner_sha256','git_sha256')))
        candidate = Path(self.job.candidate).resolve(strict=True)
        control = self.control_root.resolve(strict=True)
        require(control.is_dir() and not control.is_relative_to(candidate))
        require(not self.state_path.resolve().is_relative_to(candidate))
        for path in (self.boundary_path,Path(self.job.verifier),Path(self.job.approval),
                     Path(self.job.scanner),Path(self.job.git)):
            require(not path.resolve(strict=True).is_relative_to(candidate))
        require(sha(Path(self.job.verifier).read_bytes()) == VERIFIER_SHA256)

    def owned_check(self, response, attempt, status, conclusion=None, check_id=None):
        require(isinstance(response,dict) and integer(response.get('id')))
        require(check_id is None or response['id'] == check_id)
        require(isinstance(response.get('app'),dict) and integer(response['app'].get('id'))
                and response['app']['id'] == self.app_id)
        require(response.get('name') == CHECK_NAME and response.get('head_sha') == self.job.candidate_sha
                and response.get('external_id') == attempt and response.get('status') == status)
        require(response.get('conclusion') == conclusion)
        return response['id']

    def handle(self, raw, headers):
        """Return PASS only after authenticated evidence and confirmed own-App update.
        Every failure returns a fixed rejection without sensitive diagnostics.
        A failed/ambiguous API call is never retried or converted into success.
        """
        attempt = uuid.uuid4().hex
        check_id = None
        claimed = False
        try:
            self.config_ok()
            delivery, number = self.event(raw, headers)
            self.claim(delivery,attempt,sha(raw))
            claimed = True
            self.current(number)
            start = dict(name=CHECK_NAME,head_sha=self.job.candidate_sha,
                         external_id=attempt,status='in_progress')
            response = self.api('POST','/check-runs',start)
            check_id = self.owned_check(response,attempt,'in_progress')
            self.record(attempt,'running',check_id=check_id)
            boundary = self.load_boundary()
            with tempfile.TemporaryDirectory(dir=self.control_root,prefix='worker-') as directory:
                control = Path(directory)
                key = __import__('os').urandom(32)
                (control/'key').write_bytes(key)
                policy = dict(schema=1,repository=REPOSITORY,candidate_sha=self.job.candidate_sha,
                    attempt_id=attempt,inventory_sha256=self.job.inventory_sha256,
                    verifier_sha256=VERIFIER_SHA256,scanner_sha256=self.job.scanner_sha256,
                    git_sha256=self.job.git_sha256,approval_sha256=self.job.approval_sha256)
                policy_raw = wire(policy)
                (control/'policy.json').write_bytes(policy_raw)
                request = {k:policy[k] for k in boundary.REQUEST_KEYS-{'policy_sha256'}}
                request['policy_sha256'] = sha(policy_raw)
                args = Namespace(candidate=self.job.candidate,verifier=self.job.verifier,
                    approval=self.job.approval,scanner=self.job.scanner,git=self.job.git,
                    key=str(control/'key'),policy=str(control/'policy.json'),
                    policy_sha256=request['policy_sha256'],repository=REPOSITORY,
                    candidate_sha=self.job.candidate_sha,attempt_id=attempt)
                evidence = wire(boundary.run(args))
                payload = boundary.check_payload(evidence,key,request,dict(request))
            self.current(number)
            evidence_digest = sha(evidence)
            payload['name'] = CHECK_NAME
            payload['output']['summary'] = 'Authenticated full-history evidence SHA-256: '+evidence_digest
            # Record authenticated envelope and exact policy before publication.
            # Never persist the worker key or App credential in evidence.
            self.record(attempt,'verified',evidence=evidence,policy=policy_raw)
            response = self.api('PATCH','/check-runs/'+str(check_id),payload)
            self.owned_check(response,attempt,'completed','success',check_id)
            self.record(attempt,'passed')
            return dict(result='PASS',candidate_sha=self.job.candidate_sha,
                        attempt_id=attempt,evidence_sha256=evidence_digest)
        except Exception:
            if claimed:
                try:
                    self.record(attempt,'rejected')
                except Exception:
                    pass
            if check_id is not None:
                try:
                    failure = dict(status='completed',conclusion='failure',output={
                        'title':'Trusted verification rejected','summary':'Required authenticated verification unavailable or rejected.'})
                    self.api('PATCH','/check-runs/'+str(check_id),failure)
                except Exception:
                    pass  # No success fallback; remote state can be ambiguous after response loss.
            return {'result':'REJECTED'}

if __name__ == '__main__':
    # No default credential or network adapter. Executable offline qualification:
    # python -I -S run_tests.py. A production launcher must supply the trusted TCB.
    print('{"result":"REJECTED","reason":"authenticated_transport_and_deployment_required"}')
    raise SystemExit(1)
