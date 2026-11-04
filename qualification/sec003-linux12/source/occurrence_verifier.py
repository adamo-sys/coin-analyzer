"""Fail-closed occurrence reconciliation for a trusted CI runner.

The CLI owns acquisition, never imports reports, and reads the approval digest
from independently administered CI configuration. That trust anchor authenticates
exact decision bytes; it does not prove credential revocation or nonuse.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

CONFIG = b'[extend]\nuseDefault = true\n'
HISTORY = '--full-history --all --root -m --no-ext-diff --no-textconv'
IDENTITY = ('Commit', 'File', 'RuleID', 'StartLine', 'EndLine', 'StartColumn', 'EndColumn')

class Rejected(ValueError):
    """Generic safe failure; never attach finding contents or subprocess output."""

def require(condition, reason):
    if not condition:
        raise Rejected(reason)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'duplicate_json_key')
        result[key] = value
    return result

def decode(raw):
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: require(False, 'nonfinite_json'))
    except (ValueError, TypeError, UnicodeError):
        raise Rejected('invalid_json') from None

def environment(repo):
    # No inherited credentials, Git overrides, Gitleaks configuration or prompts.
    env = {k: v for k, v in os.environ.items() if k.upper() in
           {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC'}}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_GLOBAL=os.devnull, GIT_ATTR_NOSYSTEM='1',
               GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1', GIT_ALLOW_PROTOCOL='',
               GIT_OPTIONAL_LOCKS='0', GIT_NO_REPLACE_OBJECTS='1', NO_COLOR='1')
    settings = {'core.hooksPath': str(repo.parent / 'hooks'), 'core.fsmonitor': 'false',
                'core.attributesFile': os.devnull, 'protocol.allow': 'never',
                'commit.gpgSign': 'false', 'tag.gpgSign': 'false'}
    env['GIT_CONFIG_COUNT'] = str(len(settings))
    for i, (key, value) in enumerate(settings.items()):
        env[f'GIT_CONFIG_KEY_{i}'] = key
        env[f'GIT_CONFIG_VALUE_{i}'] = value
    return env

def command(repo, argv, timeout=30, git_dir=None):
    env = environment(repo)
    if git_dir is not None:
        # Scanner source is an empty owned directory; bind only the inspected Git
        # database. Gitleaks 8.24.3 otherwise always loads source/.gitleaksignore.
        env['GIT_DIR'] = git_dir
    try:
        return subprocess.run(argv, cwd=repo, env=env,
                              capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        raise Rejected('process_failed') from None

def git(repo, *args):
    executable = shutil.which('git')
    require(executable is not None, 'git_unavailable')
    result = command(repo, [executable, *args])
    require(result.returncode == 0, 'git_failed')
    return result.stdout

def scope(repo):
    repo = Path(repo).resolve()
    require((repo / '.git').exists(), 'git_repository_required')
    top = Path(os.fsdecode(git(repo, 'rev-parse', '--show-toplevel')).strip()).resolve()
    require(top == repo, 'repository_root_required')
    grafts = Path(os.fsdecode(git(repo, 'rev-parse', '--git-path', 'info/grafts')).strip())
    if not grafts.is_absolute():
        grafts = repo / grafts
    require(not grafts.exists(), 'grafted_history_forbidden')
    require(git(repo, 'rev-parse', '--is-shallow-repository').strip() == b'false', 'shallow_history')
    return repo

def inventory(repo):
    refs = git(repo, 'for-each-ref', '--format=%(refname) %(objectname)')
    commits = git(repo, 'rev-list', '--all').splitlines()
    require(bool(commits), 'empty_history')
    require(all(re.fullmatch(b'[0-9a-f]{40}', item) for item in commits), 'unsupported_object_format')
    objects = git(repo, 'rev-list', '--objects', '--all', '--missing=print', '--no-object-names')
    require(not any(line.startswith(b'?') for line in objects.splitlines()), 'missing_objects')
    return sha(refs + b'\0' + b'\n'.join(sorted(commits))), set(item.decode() for item in commits)

def scannable_commit_count(repo):
    # Pinned DetectGit skips deleted and binary files before addCommit.
    # Numstat provides an independent metadata-only count for histories; unsupported formats reject.
    data = git(repo, 'log', '--format=GATE07:%H', '--numstat', '--diff-filter=d', *HISTORY.split())
    current = None
    commits = set()
    for line in data.splitlines():
        if line.startswith(b'GATE07:'):
            current = line[7:]
            require(re.fullmatch(b'[0-9a-f]{40}', current), 'invalid_history_counter')
        elif re.match(rb'[0-9]+\t[0-9]+\t', line):
            require(current is not None, 'missing_history_counter')
            commits.add(current)
        else:
            require(not line or line.startswith(b'-\t-\t'), 'unsupported_history_counter')
    return len(commits)

def path_ok(path):
    return (isinstance(path, str) and bool(path) and
            all(re.fullmatch(r'[A-Za-z0-9_.-]+', part) and part not in ('.', '..')
                for part in path.split('/')))

def findings(raw):
    rows = decode(raw)
    require(isinstance(rows, list), 'report_array_required')
    seen = set()
    for row in rows:
        require(isinstance(row, dict), 'finding_object_required')
        require(set(IDENTITY) | {'Fingerprint', 'Secret', 'Match'} <= row.keys(), 'incomplete_finding')
        require(isinstance(row['Commit'], str) and re.fullmatch('[0-9a-f]{40}', row['Commit']), 'invalid_commit')
        require(path_ok(row['File']), 'invalid_path')
        require(isinstance(row['RuleID'], str) and re.fullmatch('[a-zA-Z0-9_.-]+', row['RuleID']), 'invalid_rule')
        for key in ('StartLine', 'EndLine', 'StartColumn', 'EndColumn'):
            require(type(row[key]) is int and row[key] > 0, 'invalid_location')
        require(row['EndLine'] >= row['StartLine'], 'invalid_range')
        if row['StartLine'] == row['EndLine']:
            require(row['EndColumn'] >= row['StartColumn'], 'invalid_columns')
        require(all(isinstance(row[k], str) and row[k] for k in ('Secret', 'Match', 'Fingerprint')), 'invalid_text')
        expected = f"{row['Commit']}:{row['File']}:{row['RuleID']}:{row['StartLine']}"
        require(row['Fingerprint'] == expected, 'fingerprint_inconsistent')
        identity = tuple(row[key] for key in IDENTITY)
        require(identity not in seen, 'ambiguous_finding')
        seen.add(identity)
    return rows

def completion(log, commit_count, finding_count):
    commits = re.findall(rb'\b(\d+) commits? scanned\b', log)
    leaks = re.findall(rb'\bleaks found:\s*(\d+)\b', log)
    require(not re.search(rb'\b(?:ERR|FTL|panic:)\b', log), 'scanner_error_log')
    require(len(commits) == 1 and int(commits[0]) == commit_count, 'incomplete_scan')
    if finding_count:
        require(len(leaks) == 1 and int(leaks[0]) == finding_count, 'inconsistent_scan_count')
    else:
        require(not leaks and b'no leaks found' in log, 'missing_clean_summary')
    require(len(re.findall(rb'scanned ~[0-9]+ bytes[^\r\n]* in [0-9.]+(?:ms|s)', log)) == 1, 'missing_completion')

def scan_history(repo, executable, scanner_sha256):
    repo = scope(repo)
    executable = Path(executable).resolve()
    try:
        require(isinstance(scanner_sha256, str) and re.fullmatch('[0-9a-f]{64}', scanner_sha256)
                and sha(executable.read_bytes()) == scanner_sha256, 'scanner_identity')
    except OSError:
        raise Rejected('scanner_unavailable') from None
    version = command(repo, [str(executable), 'version'])
    require(version.returncode == 0 and version.stdout.strip() == b'8.24.3', 'scanner_version')
    before, commits = inventory(repo)
    git_dir = os.fsdecode(git(repo, 'rev-parse', '--absolute-git-dir')).strip()
    with tempfile.TemporaryDirectory(dir=repo.parent, prefix='scan-') as directory:
        config = Path(directory) / 'defaults.toml'
        ignore = Path(directory) / 'empty.ignore'
        config.write_bytes(CONFIG)
        ignore.write_bytes(b'')
        result = command(Path(directory), [str(executable), 'git', '.', '--config=' + str(config),
                         '--log-opts=' + HISTORY, '--redact=100', '--exit-code=2',
                         '--log-level=info', '--no-banner', '--report-format=json',
                         '--report-path=-', '--ignore-gitleaks-allow',
                         '--gitleaks-ignore-path=' + str(ignore)], timeout=40, git_dir=git_dir)
    require(result.returncode in (0, 2), 'scanner_failed')
    rows = findings(result.stdout)
    require(result.returncode == (2 if rows else 0), 'scanner_exit_inconsistent')
    completion(result.stderr, scannable_commit_count(repo), len(rows))
    after, _ = inventory(repo)
    require(before == after, 'history_changed_during_scan')
    return {'report': result.stdout, 'report_sha256': sha(result.stdout),
            'exit_code': result.returncode, 'complete': True,
            'commit_count': len(commits), 'finding_count': len(rows),
            'inventory_sha256': before}

def verify(repo, scan, approval_bytes, approval_sha256):
    """Return approved occurrence count or raise Rejected; caller owns acquisition.

    No finding is approved because metadata merely exists. All evidence must match
    anchored approval bytes. The trusted caller owns anchor authentication.
    """
    repo = scope(repo)
    require(isinstance(approval_bytes, bytes) and isinstance(approval_sha256, str), 'approval_required')
    require(re.fullmatch('[0-9a-f]{64}', approval_sha256) and
            sha(approval_bytes) == approval_sha256, 'approval_integrity')
    approval = decode(approval_bytes)
    require(isinstance(approval, dict) and set(approval) ==
            {'schema', 'classification', 'decision', 'approver', 'decision_ref', 'records'}, 'approval_schema')
    require(type(approval['schema']) is int and approval['schema'] == 1 and
            approval['classification'] == 'OCCURRENCE_APPROVAL' and
            approval['decision'] == 'approved' and
            all(isinstance(approval[k], str) and approval[k].strip()
                for k in ('approver', 'decision_ref')), 'approval_not_granted')
    require(isinstance(approval['records'], list), 'approval_records_required')
    require(isinstance(scan, dict) and set(scan) == {'report', 'report_sha256', 'exit_code',
            'complete', 'commit_count', 'finding_count', 'inventory_sha256'}, 'scan_receipt_schema')
    require(isinstance(scan['report'], bytes) and sha(scan['report']) == scan['report_sha256'], 'report_integrity')
    digest, commits = inventory(repo)
    require(scan['complete'] is True and type(scan['commit_count']) is int and
            scan['commit_count'] == len(commits) and scan['inventory_sha256'] == digest, 'scan_incomplete')
    rows = findings(scan['report'])
    require(type(scan['exit_code']) is int and scan['exit_code'] == (2 if rows else 0), 'invalid_exit')
    require(type(scan['finding_count']) is int and scan['finding_count'] == len(rows), 'invalid_count')
    actual = {tuple(row[k] for k in IDENTITY): row for row in rows}
    approved = set()
    for record in approval['records']:
        require(isinstance(record, dict) and set(record) == {'identity', 'finding_sha256',
                'blob_oid', 'blob_sha256', 'lines_sha256'}, 'record_schema')
        ident = record['identity']
        require(isinstance(ident, dict) and set(ident) == set(IDENTITY), 'identity_schema')
        require(all(isinstance(ident[k], str) for k in ('Commit', 'File', 'RuleID')) and
                all(type(ident[k]) is int for k in IDENTITY[3:]), 'identity_types')
        key = tuple(ident[k] for k in IDENTITY)
        require(key not in approved and key in actual, 'missing_or_ambiguous_occurrence')
        approved.add(key)
        row = actual[key]
        require(row['Commit'] in commits, 'unreachable_occurrence')
        require(record['finding_sha256'] == sha(canonical(row)), 'finding_altered')
        oid = git(repo, 'rev-parse', row['Commit'] + ':' + row['File']).decode().strip()
        require(re.fullmatch('[0-9a-f]{40}', oid) and oid == record['blob_oid'], 'blob_identity')
        blob = git(repo, 'cat-file', 'blob', oid)
        require(sha(blob) == record['blob_sha256'], 'blob_integrity')
        lines = blob.splitlines(keepends=True)
        require(row['EndLine'] <= len(lines), 'location_outside_blob')
        require(row['StartColumn'] <= len(lines[row['StartLine']-1].rstrip(b'\r\n')) and
                row['EndColumn'] <= len(lines[row['EndLine']-1].rstrip(b'\r\n')), 'column_outside_blob')
        selected = b''.join(lines[row['StartLine']-1:row['EndLine']])
        require(sha(selected) == record['lines_sha256'], 'line_integrity')
    require(approved == set(actual), 'unapproved_additional_occurrence')
    return len(approved)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--approval', required=True)
    parser.add_argument('--scanner', required=True)
    parser.add_argument('--scanner-sha256', required=True)
    args = parser.parse_args()
    try:
        scan = scan_history(args.repo, args.scanner, args.scanner_sha256)
        approval = Path(args.approval).read_bytes()
        count = verify(args.repo, scan, approval, os.environ.get('SEC003_GITLEAKS_APPROVAL_SHA256', ''))
        print(json.dumps({'result': 'PASS', 'approved_occurrences': count}))
        return 0
    except Exception:  # CLI never prints raw scanner/Git/input exception details.
        print('{"result":"REJECTED"}')
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
