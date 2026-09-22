"""Read-only task-start observations. No execution or publication authority."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from typing import Any


MINIMUM_PROTECTED = ['.git', 'data', 'test_coins', 'debug_outputs', 'backups',
                     'exports', 'notes', 'credentials', '.env*', '*.pem', '*.key',
                     '*.jpg', '*.jpeg', '*.png', '*.webp', '*.heic', '*.sqlite*', '*.db',
                     'benchmarks/phone-photo-v1']


class PreflightError(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def unsafe_component(value: str) -> bool:
    return (value.endswith((' ', '.')) or '~' in value
            or bool(re.fullmatch(r'(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?', value)))


def unsafe_component_no_alias(value: str) -> bool:
    return (value.endswith((' ', '.'))
            or bool(re.fullmatch(r'(?i)(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?', value)))


def relative_path(value: str) -> str:
    """Accept literal, portable relative paths, never Git pathspec expressions."""
    if (not value or '\\' in value or ':' in value or value.startswith('/')
            or any(ord(c) < 32 for c in value)
            or any(p in ('', '.', '..') for p in value.split('/'))
            or any(unsafe_component(p) for p in value.split('/'))
            or any(c in value for c in '*?[]')):
        raise PreflightError('Expected paths must be literal repository-relative paths.')
    return value


def load_config(path: Path) -> dict[str, Any]:
    # Reject traversal before deriving an absolute lexical path. Do not resolve:
    # resolving would follow links before the protected-path and link checks.
    if '..' in path.parts:
        raise PreflightError('Configuration must not contain traversal.')
    # Validate lexical relative-path aliases before absolutizing. Absolute parent
    # directories may legitimately include platform-generated alias components.
    if (not path.is_absolute()
            and any(unsafe_component(part) or part == '..' or ':' in part or any(ord(c) < 32 for c in part)
                    for part in path.parts)):
        raise PreflightError('Configuration must not be a protected or linked path.')
    try:
        path = path.absolute()
    except OSError as exc:
        raise PreflightError('Configuration path is unavailable.', 3) from exc
    if (any(unsafe_component_no_alias(part) or part == '..' or ':' in part or any(ord(c) < 32 for c in part)
            for part in path.parts if part != path.anchor)
            or protected(path.as_posix(), MINIMUM_PROTECTED) or linked_path(path)):
        raise PreflightError('Configuration must not be a protected or linked path.')
    try:
        import yaml
    except ImportError as exc:
        raise PreflightError('PyYAML is unavailable; use the declared development environment.', 3) from exc

    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader: Any, node: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            if not isinstance(key, str) or key in result:
                raise PreflightError('Configuration keys must be unique strings.')
            result[key] = loader.construct_object(value_node)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        if path.stat().st_size > 65536:
            raise PreflightError('Configuration exceeds the 64 KiB limit.')
        config = yaml.load(path.read_text(encoding='utf-8'), Loader=UniqueLoader)
    except (OSError, UnicodeError, yaml.YAMLError, RecursionError) as exc:
        raise PreflightError('Configuration is unavailable or malformed.') from exc
    required = {'schema_version', 'guidance', 'validation_profiles', 'task_classes', 'protected_paths'}
    if not isinstance(config, dict) or set(config) != required or type(config['schema_version']) is not int or config['schema_version'] != 1:
        raise PreflightError('Configuration must have the schema version 1 fields.')

    def strings(value: Any) -> bool:
        return isinstance(value, list) and bool(value) and all(isinstance(s, str) and bool(s.strip()) for s in value)

    if not strings(config['guidance']) or not strings(config['protected_paths']):
        raise PreflightError('Guidance and protected paths must be nonempty string lists.')
    for value in config['guidance']:
        relative_path(value)
    profiles, classes = config['validation_profiles'], config['task_classes']
    if not isinstance(profiles, dict) or not profiles or not all(strings(v) for v in profiles.values()):
        raise PreflightError('Validation profiles must contain minimum requirement lists.')
    if not isinstance(classes, dict) or set(classes) != {'documentation', 'tests', 'tooling', 'production'}:
        raise PreflightError('Configuration must define the four supported task classes.')
    for value in classes.values():
        if (not isinstance(value, dict) or set(value) != {'validation_profile'}
                or not isinstance(value['validation_profile'], str)
                or value['validation_profile'] not in profiles):
            raise PreflightError('Task class references an invalid validation profile.')
    return config


class Git:
    def __init__(self, cwd: Path, retry_safe_directory: bool = False):
        self.cwd = cwd
        self.retry_safe_directory = retry_safe_directory

    def run(self, *args: str, allowed: tuple[int, ...] = (0,)) -> str:
        env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0', GIT_NO_LAZY_FETCH='1')

        def command(trusted: bool) -> list[str]:
            result = ['git', '--no-optional-locks', '-c', 'core.fsmonitor=false']
            if trusted:
                result.extend(('-c', f'safe.directory={self.cwd}'))
            return [*result, *args]

        try:
            result = subprocess.run(
                command(False),
                cwd=self.cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PreflightError('Git is unavailable or its read-only inspection timed out.', 3) from exc
        if (result.returncode not in allowed and self.retry_safe_directory
                and b'detected dubious ownership' in result.stderr.lower()):
            try:
                result = subprocess.run(
                    command(True),
                    cwd=self.cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=15, check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise PreflightError('Git is unavailable or its read-only inspection timed out.', 3) from exc
        if result.returncode not in allowed:
            # Never echo raw Git output: it may contain private paths or remote URLs.
            raise PreflightError('A read-only Git inspection failed; verify repository access and trust.', 3)
        return result.stdout.decode('utf-8', errors='surrogateescape')

    def ref(self, name: str) -> str | None:
        return self.run('rev-parse', '--verify', '--quiet', name, allowed=(0, 1)).strip() or None

    def relationship(self, left: str | None, right: str | None) -> dict[str, int] | None:
        if left is None or right is None:
            return None
        counts = self.run('rev-list', '--left-right', '--count', f'{left}...{right}').split()
        if len(counts) != 2 or not all(c.isdigit() for c in counts):
            raise PreflightError('Git returned an invalid relationship count.', 3)
        return {'ahead': int(counts[0]), 'behind': int(counts[1])}


def protected(path: str, patterns: list[str]) -> bool:
    parts = PurePosixPath(path.lower()).parts
    prefixes = ['/'.join(parts[start:end]) for start in range(len(parts))
                for end in range(start + 1, len(parts) + 1)]
    return any(fnmatch.fnmatchcase(item, pattern.lower())
               for pattern in patterns for item in [*parts, *prefixes])


def linked_path(path: Path) -> bool:
    """Check each component without following a symlink or Windows reparse point."""
    for component in [*reversed(path.parents), path]:
        try:
            info = component.lstat()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise PreflightError('Requested path metadata is unavailable.', 3) from exc
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            return True
    return False


def status_records(raw: str) -> list[tuple[str, str]]:
    items = iter(raw.split('\0'))
    records: list[tuple[str, str]] = []
    for item in items:
        if not item:
            continue
        if len(item) < 4 or item[2] != ' ':
            raise PreflightError('Git returned an invalid status record.', 3)
        records.append((item[:2], item[3:]))
        if 'R' in item[:2] or 'C' in item[:2]:
            # --no-renames normally prevents this; do not silently lose the source.
            source = next(items, '')
            if not source:
                raise PreflightError('Git returned an incomplete rename record.', 3)
            records.append((item[:2], source))
    return records


def worktree_records(raw: str) -> list[dict[str, str | None]]:
    """Parse the documented, line-delimited Git worktree porcelain format."""
    records: list[dict[str, str | None]] = []
    for block in raw.split('\n\n'):
        if not block:
            continue
        path: str | None = None
        head: str | None = None
        branch: str | None = None
        detached = False
        for line in block.splitlines():
            if line.startswith('worktree ') and path is None:
                path = line.removeprefix('worktree ')
            elif line.startswith('HEAD ') and head is None:
                head = line.removeprefix('HEAD ')
            elif line.startswith('branch refs/heads/') and branch is None:
                branch = line.removeprefix('branch refs/heads/')
            elif line == 'detached' and not detached:
                detached = True
            elif line == 'locked' or line.startswith('locked '):
                continue
            elif line == 'prunable' or line.startswith('prunable '):
                continue
            else:
                raise PreflightError('Git returned invalid worktree metadata.', 3)
        if (not path or not head or not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', head)
                or (branch is None) == (not detached)):
            raise PreflightError('Git returned invalid worktree metadata.', 3)
        records.append({'path': path, 'head': head.lower(), 'branch': branch})
    if not records or len({item['path'] for item in records}) != len(records):
        raise PreflightError('Git returned invalid worktree metadata.', 3)
    return sorted(records, key=lambda item: item['path'] or '')


def inventory(args: argparse.Namespace) -> dict[str, Any]:
    """Observe registered worktree state without assigning a disposition."""
    git = Git(Path(args.repo))
    root = Path(git.run('rev-parse', '--show-toplevel').strip())
    git.cwd = root
    base = git.ref(args.base)
    if base is None:
        raise PreflightError('Inventory base revision is unavailable.', 3)
    shallow = git.run('rev-parse', '--is-shallow-repository').strip() == 'true'
    worktrees = []
    for record in worktree_records(git.run('worktree', 'list', '--porcelain')):
        child = Git(Path(record['path'] or ''), retry_safe_directory=True)
        tracked_dirty = bool(status_records(child.run(
            'status', '--porcelain=v1', '-z', '--untracked-files=no', '--no-renames'
        )))
        relation = child.relationship(record['head'], base) if not shallow else None
        worktrees.append({
            **record,
            'tracked_dirty': tracked_dirty,
            'head_contained_by_base': relation['ahead'] == 0 if relation else None,
            'unique_commits_vs_base': relation['ahead'] if relation else None,
        })
    return {
        'schema_version': 1, 'operation': 'inventory',
        'repository': {'root': str(root), 'identity': str(root), 'base': base, 'shallow': shallow},
        'worktrees': worktrees,
        'evidence': {'remote_freshness': 'unverified_local_ref_only',
                     'validation': 'not_run', 'ci': 'unverified',
                     'authority': 'observations_only'},
    }


def inspect(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    requested = sorted(set(relative_path(p) for p in args.expect_path))
    scope = sorted(set(relative_path(p) for p in args.scope_path))
    if args.expect_head and not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', args.expect_head):
        raise PreflightError('Expected HEAD must be a full hexadecimal object ID.')
    git = Git(Path(args.repo))
    root = Path(git.run('rev-parse', '--show-toplevel').strip())
    git.cwd = root
    branch = git.run('symbolic-ref', '--quiet', '--short', 'HEAD', allowed=(0, 1)).strip() or None
    head = git.ref('HEAD')
    if head is None:
        raise PreflightError('Repository has no committed HEAD.', 3)
    main = git.ref('refs/heads/main')
    origin_main = git.ref('refs/remotes/origin/main')
    shallow = git.run('rev-parse', '--is-shallow-repository').strip() == 'true'
    records = status_records(git.run('status', '--porcelain=v1', '-z', '--untracked-files=no', '--no-renames'))
    mismatch: list[str] = []
    if args.expect_branch is not None and branch != args.expect_branch:
        mismatch.append('expected_branch')
    if args.expect_head and head != args.expect_head.lower():
        mismatch.append('expected_head')
    if args.require_clean and records:
        mismatch.append('tracked_checkout_dirty')
    outside_scope = sum(path not in scope for _, path in records) if scope else None
    if outside_scope:
        mismatch.append('tracked_changes_outside_scope')
    if scope and any(p not in scope for p in requested):
        mismatch.append('expected_path_outside_scope')

    paths = []
    untracked: set[str] = set()
    blocked_count = 0
    for value in sorted(set(requested + scope)):
        if protected(value, [*MINIMUM_PROTECTED, *config['protected_paths']]):
            blocked_count += 1
            continue
        path = root / value
        # Reject symlinks/junctions, including ancestors, before filesystem reads.
        if linked_path(path):
            blocked_count += 1
            continue
        exists = path.exists()
        if value in requested and not exists:
            mismatch.append('expected_path_missing')
        # Only exact files; never recurse into a requested directory.
        is_file = path.is_file()
        if exists and not is_file:
            mismatch.append('expected_path_not_file')
        if is_file:
            literal = f':(literal){value}'
            raw = git.run('ls-files', '--others', '--exclude-standard', '-z', '--', literal)
            untracked.update(p for p in raw.split('\0') if p == value)
        tree_head = git.run('ls-tree', '-z', head, '--', f':(literal){value}') if head else ''
        tree_main = git.run('ls-tree', '-z', main, '--', f':(literal){value}') if main else ''
        # Object IDs and modes compare committed content; never open file contents.
        equivalent = (tree_head == tree_main) if tree_head and tree_main else None
        paths.append({'path': value, 'exists': exists, 'is_file': is_file,
                      'head_equals_main': equivalent,
                      'head_tracked': bool(tree_head), 'main_tracked': bool(tree_main)})
    if blocked_count:
        mismatch.append('protected_or_linked_path_requested')

    candidate = None
    if args.candidate_branch:
        name = args.candidate_branch
        if name.startswith('-') or name == 'HEAD':
            raise PreflightError('Candidate must be a literal local branch name.')
        reference = f'refs/heads/{name}'
        if git.run('check-ref-format', '--normalize', reference, allowed=(0, 1)).strip() != reference:
            raise PreflightError('Candidate must be a literal local branch name.')
        commit = git.ref(f'refs/heads/{name}')
        relation = git.relationship(commit, main) if not shallow else None
        candidate = {'branch': name, 'exists': commit is not None, 'head': commit,
                     'unique_commits_vs_main': relation['ahead'] if relation else None,
                     'ancestrally_merged_into_main': relation['ahead'] == 0 if relation else None}
    task_class = args.task_class
    profile = config['task_classes'][task_class]['validation_profile']
    return {
        'schema_version': 1, 'operation': 'preflight',
        'repository': {'root': str(root), 'identity': str(root), 'branch': branch,
                       'head': head, 'local_main': main, 'recorded_origin_main': origin_main,
                       'shallow': shallow},
        'relationships': {
            'head_vs_local_main': git.relationship(head, main) if not shallow else None,
            'head_vs_recorded_origin_main': git.relationship(head, origin_main) if not shallow else None,
            'local_main_vs_recorded_origin_main': git.relationship(main, origin_main) if not shallow else None,
        },
        'working_tree': {'tracked_clean': not records,
                         'staged_count': sum(x != ' ' for (x, _), _path in records),
                         'unstaged_count': sum(y != ' ' for (_, y), _path in records),
                         'untracked_count': len(untracked),
                         'untracked_count_scope': 'explicit_nonprotected_files_only',
                         'untracked_total': None, 'tracked_changes_outside_scope': outside_scope},
        'paths': paths, 'blocked_path_count': blocked_count, 'candidate': candidate,
        'task': {'class': task_class, 'validation_profile': profile,
                 'minimum_requirements': config['validation_profiles'][profile],
                 'guidance': config['guidance']},
        'mismatches': sorted(set(mismatch)),
        'evidence': {'remote_freshness': 'unverified_local_ref_only',
                     'validation': 'not_run', 'ci': 'unverified',
                     'file_equivalence': 'committed_HEAD_vs_local_main_only',
                     'authority': 'observations_only'},
    }


def markdown(report: dict[str, Any]) -> str:
    def literal(value: Any) -> str:
        payload = json.dumps(value, sort_keys=True, ensure_ascii=True)
        fence = '`' * max(1, max((len(m.group()) + 1 for m in re.finditer(r'`+', payload)), default=1))
        return fence + ' ' + payload + ' ' + fence

    title = 'Task preflight' if report['operation'] == 'preflight' else 'Task inventory'
    lines = ['# ' + title, '', 'Observations only; no execution or publication authority.', '']
    for key, value in report.items():
        lines.extend(['## ' + key.replace('_', ' ').capitalize(), ''])
        if isinstance(value, dict):
            lines.extend('- ' + name.replace('_', ' ') + ': ' + literal(item) for name, item in value.items())
        elif isinstance(value, list):
            lines.extend(['- ' + literal(item) for item in value] or ['None.'])
        else:
            lines.append(literal(value))
        lines.append('')
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    preflight = commands.add_parser('preflight')
    preflight.add_argument('--repo', default='.')
    preflight.add_argument('--config', default=str(Path(__file__).resolve().parents[1] / '.ops/tasks.yml'))
    preflight.add_argument('--format', choices=('markdown', 'json'), default='markdown')
    preflight.add_argument('--task-class', choices=('documentation', 'tests', 'tooling', 'production'), required=True)
    preflight.add_argument('--expect-branch')
    preflight.add_argument('--expect-head')
    preflight.add_argument('--require-clean', action='store_true')
    preflight.add_argument('--expect-path', action='append', default=[])
    preflight.add_argument('--scope-path', action='append', default=[])
    preflight.add_argument('--candidate-branch')
    inventory_command = commands.add_parser('inventory')
    inventory_command.add_argument('--repo', default='.')
    inventory_command.add_argument('--base', required=True)
    inventory_command.add_argument('--format', choices=('markdown', 'json'), default='markdown')
    args = parser.parse_args(argv)
    try:
        if args.command == 'preflight':
            report = inspect(args, load_config(Path(args.config)))
            code = 4 if report['mismatches'] else 0
        else:
            report = inventory(args)
            code = 0
    except PreflightError as exc:
        report = {'schema_version': 1, 'operation': args.command, 'error': str(exc), 'exit_code': exc.code}
        code = exc.code
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True) if args.format == 'json' else markdown(report))
    return code


if __name__ == '__main__':
    sys.exit(main())
