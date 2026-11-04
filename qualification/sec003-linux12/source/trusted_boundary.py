"""External-controller prototype; invoke from immutable trusted deployment: python -I -S.

The caller authenticates policy_sha256 and owns every argument, candidate Git
metadata and key. Candidate jobs MUST NOT invoke this with publication authority.
This module performs no network IO or GitHub publication. See ../DESIGN.md.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import types

CHECK_NAME = 'SEC003 trusted Gitleaks'
REQUEST_KEYS = {'repository', 'candidate_sha', 'attempt_id', 'policy_sha256', 'inventory_sha256'}
POLICY_KEYS = (REQUEST_KEYS - {'policy_sha256'}) | {
    'schema', 'verifier_sha256', 'scanner_sha256', 'git_sha256', 'approval_sha256'}
DECISION_KEYS = REQUEST_KEYS | {'schema', 'result', 'approved_occurrences'}


class Rejected(ValueError):
    """Safe fixed failure: never include scanner reports, keys or raw diagnostics."""


def require(condition):
    if not condition:
        raise Rejected('boundary_rejected')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def unique_pairs(items):
    result = {}
    for key, value in items:
        require(key not in result)
        result[key] = value
    return result


def decode(raw):
    try:
        return json.loads(raw, object_pairs_hook=unique_pairs,
                          parse_constant=lambda _: require(False))
    except Exception:
        raise Rejected('boundary_rejected') from None


def digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def request_ok(value):
    require(isinstance(value, dict) and set(value) == REQUEST_KEYS)
    require(value['repository'] == 'adamo-sys/coin-analyzer')
    require(isinstance(value['candidate_sha'], str) and
            re.fullmatch('[0-9a-f]{40}', value['candidate_sha']))
    require(isinstance(value['attempt_id'], str) and
            re.fullmatch('[0-9a-f]{32}', value['attempt_id']))
    require(digest(value['policy_sha256']) and digest(value['inventory_sha256']))


def outside(candidate, path):
    resolved = Path(path).resolve(strict=True)
    require(not resolved.is_relative_to(candidate) and resolved.is_file())
    return resolved


def authenticated_module(raw):
    # Execute exactly the authenticated byte string. No importlib/sys.path lookup,
    # adjacent modules, cached bytecode or reopening of the source after hashing.
    result = types.ModuleType('sec003_authenticated_occurrence_verifier')
    exec(compile(raw, '<authenticated-occurrence-verifier>', 'exec'), result.__dict__)
    return result


def run(args):
    """Return authenticated PASS envelope or raise Rejected. No imported scan result.

    All paths/expected pins/request fields are controller inputs, never PR inputs.
    A fresh controller-owned candidate object store is a required precondition.
    """
    try:
        candidate = Path(args.candidate).resolve(strict=True)
        require(candidate.is_dir())
        # Establish evidence origin and exact policy before loading any verifier.
        policy_path = outside(candidate, args.policy)
        raw_policy = policy_path.read_bytes()
        require(digest(args.policy_sha256) and sha(raw_policy) == args.policy_sha256)
        policy = decode(raw_policy)
        require(isinstance(policy, dict) and set(policy) == POLICY_KEYS)
        require(type(policy['schema']) is int and policy['schema'] == 1)
        request = {k: policy[k] for k in REQUEST_KEYS - {'policy_sha256'}}
        request['policy_sha256'] = args.policy_sha256
        request_ok(request)
        require(all(getattr(args, k) == request[k] for k in
                    ('repository', 'candidate_sha', 'attempt_id')))
        require(all(digest(policy[k]) for k in
                    ('verifier_sha256', 'scanner_sha256', 'git_sha256', 'approval_sha256')))
        source = outside(candidate, args.verifier).read_bytes()
        require(sha(source) == policy['verifier_sha256'])
        approval = outside(candidate, args.approval).read_bytes()
        require(sha(approval) == policy['approval_sha256'])
        key = outside(candidate, args.key).read_bytes()
        require(len(key) == 32)
        git_path = outside(candidate, args.git)
        scanner = outside(candidate, args.scanner)
        require(sha(git_path.read_bytes()) == policy['git_sha256'])
        require(sha(scanner.read_bytes()) == policy['scanner_sha256'])
        # Only trusted tool directories. The inherited matcher locates Git with
        # shutil.which; bind that lookup to the authenticated executable.
        old_path = os.environ.get('PATH')
        old_cwd = Path.cwd()
        try:
            os.environ['PATH'] = str(git_path.parent) + os.pathsep + os.defpath
            os.chdir(git_path.parent)
            require(Path(shutil.which('git') or '').resolve() == git_path)
            verifier = authenticated_module(source)
            repo = verifier.scope(candidate)
            require(verifier.git(repo, 'rev-parse', '--verify', 'HEAD').decode().strip() ==
                    request['candidate_sha'])
            require(verifier.git(repo, 'show-ref', '--verify', '--hash',
                                 'refs/sec003/candidate').decode().strip() == request['candidate_sha'])
            before, commits = verifier.inventory(repo)
            require(before == request['inventory_sha256'] and request['candidate_sha'] in commits)
            scan = verifier.scan_history(repo, str(scanner), policy['scanner_sha256'])
            count = verifier.verify(repo, scan, approval, policy['approval_sha256'])
            require(verifier.inventory(repo)[0] == before)
            require(verifier.git(repo, 'rev-parse', '--verify', 'HEAD').decode().strip() ==
                    request['candidate_sha'])
            require(type(count) is int and count >= 0)
        finally:
            os.chdir(old_cwd)
            if old_path is None:
                os.environ.pop('PATH', None)
            else:
                os.environ['PATH'] = old_path
        decision = dict(request, schema=1, result='PASS', approved_occurrences=count)
        return {'decision': decision, 'mac': hmac.new(key, wire(decision), hashlib.sha256).hexdigest()}
    except Exception:
        raise Rejected('boundary_rejected') from None


def check_payload(raw, key, request, current_request):
    """Offline publisher contract. Inputs come from protected controller state.

    The controller supplies current_request after authenticated API refresh,
    consumes the attempt once, and owns the App credentials. This function does
    not prove that source or persist consumed attempts; it does not publish.
    """
    try:
        request_ok(request)
        request_ok(current_request)
        require(request == current_request and isinstance(key, bytes) and len(key) == 32)
        envelope = decode(raw)
        require(isinstance(envelope, dict) and set(envelope) == {'decision', 'mac'})
        d = envelope['decision']
        require(isinstance(d, dict) and set(d) == DECISION_KEYS and digest(envelope['mac']))
        expected = hmac.new(key, wire(d), hashlib.sha256).hexdigest()
        require(hmac.compare_digest(envelope['mac'], expected))
        require(type(d['schema']) is int and d['schema'] == 1 and d['result'] == 'PASS')
        require(type(d['approved_occurrences']) is int and d['approved_occurrences'] >= 0)
        require(all(d[k] == request[k] for k in REQUEST_KEYS))
        return {'name': CHECK_NAME, 'head_sha': request['candidate_sha'],
                'external_id': request['attempt_id'], 'status': 'completed', 'conclusion': 'success',
                'output': {'title': 'Trusted occurrence verification passed',
                           'summary': 'Authenticated full-history decision; no finding contents.'}}
    except Exception:
        raise Rejected('boundary_rejected') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate', 'verifier', 'approval', 'key', 'scanner', 'git', 'policy',
                 'policy-sha256', 'repository', 'candidate-sha', 'attempt-id'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        print(wire(run(args)).decode())
        return 0
    except Exception:
        print('{"result":"REJECTED"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
