"""Trusted reconstructed materialization primitives for Bake-Off V1.

This module is orchestrator-side only.  It deliberately does not launch Codex
or deliver a contestant prompt.  ``reconstructed-materializer-v1`` is a new
implementation generation, provenance-bound to the retained RUN-002/RUN-003
evidence rather than claimed to be executable-identical to that lost runner.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import unicodedata
from collections.abc import Iterable, Mapping
from hashlib import sha256
from pathlib import Path, PurePosixPath

IMPLEMENTATION_GENERATION = "reconstructed-materializer-v1"
SANDBOX_IDENTITY = r"DESKTOP-94V1OOQ\CodexSandboxOffline"
_HISTORICAL_EVIDENCE_SHA256 = (
    "22e84e6e4b42cd917d0e2b43a4997bb4b7bd3d52dab051c2278113aedb3de748",
    "e32bed187e3df2175ef79dc3c8167a9e77129cbe97fc301fb17d7327ed926f9d",
    "3e311ba042ecc38f4e13a242d42ba5e76ae6f57405cfa1c89da808b3d39a5d42",
    "1a809d2ddf633b58d9e0b01e314da5981b338b44c0368d004b4102e9119f3fbc",
)


class ReconstructedRunnerError(ValueError):
    """Raised when a candidate cannot satisfy the reconstructed isolation policy."""


def _canonical_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Mapping[str, object]) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _safe_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReconstructedRunnerError("materialization path must be a non-empty string")
    normalized = unicodedata.normalize("NFC", value.replace("\\", "/"))
    path = PurePosixPath(normalized)
    if path.is_absolute() or normalized != path.as_posix() or any(part in {"", ".", ".."} for part in path.parts):
        raise ReconstructedRunnerError("materialization path must be a safe relative path")
    return normalized


def _git(repository: Path, arguments: list[str], *, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={repository.resolve().as_posix()}", "-C", str(repository), *arguments],
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ReconstructedRunnerError(f"Git command failed: {' '.join(arguments)}")
    return result.stdout


def _parse_tree(repository: Path, starting_sha: str, protected_paths: set[str]) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return commit/tree, safe-blob, and protected-blob object IDs from tree metadata only."""
    commit = _git(repository, ["rev-parse", f"{starting_sha}^{{commit}}"]).decode("ascii").strip()
    if commit != starting_sha:
        raise ReconstructedRunnerError("starting SHA is not a genuine local commit")
    raw = _git(repository, ["ls-tree", "-r", "-t", "-z", starting_sha])
    root_tree = _git(repository, ["rev-parse", f"{starting_sha}^{{tree}}"]).decode("ascii").strip()
    commit_and_trees = {starting_sha, root_tree}
    safe_blobs: set[str] = set()
    protected_blobs: set[str] = set()
    effective_protected_paths = set(protected_paths)
    paths_seen: set[str] = set()
    for entry in (record for record in raw.split(b"\0") if record):
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split()
            path = _safe_relative_path(raw_path.decode("utf-8", "strict"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ReconstructedRunnerError("task-start tree metadata is malformed") from exc
        if path in paths_seen:
            raise ReconstructedRunnerError("task-start tree has duplicate paths")
        paths_seen.add(path)
        if mode == "120000":
            raise ReconstructedRunnerError("task-start tree contains an unsafe symlink")
        if object_type == "tree":
            commit_and_trees.add(object_id)
        elif object_type == "blob":
            is_protected_category = path.startswith("test_coins/") and path != "test_coins/README.md"
            if path in protected_paths or is_protected_category:
                effective_protected_paths.add(path)
                protected_blobs.add(object_id)
            else:
                safe_blobs.add(object_id)
        else:
            raise ReconstructedRunnerError("task-start tree contains an unsupported object type")
    absent = protected_paths - paths_seen
    if absent:
        raise ReconstructedRunnerError("declared protected path is absent from the task-start tree")
    if safe_blobs & protected_blobs:
        raise ReconstructedRunnerError("protected and safe object categories overlap")
    return (
        sorted(commit_and_trees),
        sorted(safe_blobs),
        sorted(protected_blobs),
        sorted(effective_protected_paths, key=lambda item: item.encode("utf-8")),
    )


def _write_sparse_patterns(candidate: Path, protected_paths: Iterable[str]) -> None:
    """Exclude exactly protected paths while retaining every other tracked entry."""
    git_dir = candidate / ".git"
    info = git_dir / "info"
    info.mkdir(parents=True, exist_ok=True)
    patterns = ["/*", *(f"!/{path}" for path in sorted(protected_paths, key=lambda item: item.encode("utf-8")))]
    (info / "sparse-checkout").write_text("\n".join(patterns) + "\n", encoding="utf-8", newline="\n")
    _git(candidate, ["config", "core.sparseCheckout", "true"])
    _git(candidate, ["config", "core.sparseCheckoutCone", "false"])
    _git(candidate, ["read-tree", "-mu", "HEAD"])


def _is_link_or_reparse(path: Path) -> bool:
    try:
        status = path.lstat()
    except OSError as exc:
        raise ReconstructedRunnerError("candidate path is unreadable") from exc
    return stat.S_ISLNK(status.st_mode) or bool(getattr(status, "st_file_attributes", 0) & 0x400)


def _assert_no_links(candidate: Path) -> None:
    for root, directories, files in os.walk(candidate, followlinks=False):
        current = Path(root)
        if _is_link_or_reparse(current):
            raise ReconstructedRunnerError("candidate contains a filesystem link or reparse point")
        for name in [*directories, *files]:
            if _is_link_or_reparse(current / name):
                raise ReconstructedRunnerError("candidate contains a filesystem link or reparse point")


def verify_candidate_isolation(candidate_repository: Path, *, protected_object_ids: Iterable[str]) -> None:
    """Fail closed on every supported route from a candidate to source objects."""
    candidate = candidate_repository.resolve()
    git_dir = candidate / ".git"
    if not candidate.is_dir() or not git_dir.is_dir() or _is_link_or_reparse(git_dir):
        raise ReconstructedRunnerError("candidate Git directory is not a standalone directory")
    _assert_no_links(candidate)
    if _git(candidate, ["remote"]).strip():
        raise ReconstructedRunnerError("candidate must not retain a remote")
    git_prefix = ["git", "-c", f"safe.directory={candidate.as_posix()}", "-C", str(candidate)]
    for configuration in ("extensions.partialClone", "remote.origin.promisor", "remote.origin.partialclonefilter"):
        result = subprocess.run([*git_prefix, "config", "--get", configuration], capture_output=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            raise ReconstructedRunnerError("candidate must not use promisor or partial-clone configuration")
    for path in (git_dir / "objects" / "info" / "alternates", git_dir / "objects" / "info" / "http-alternates"):
        if path.exists() or path.is_symlink():
            raise ReconstructedRunnerError("candidate must not use alternates")
    common_dir = Path(_git(candidate, ["rev-parse", "--git-common-dir"]).decode("utf-8").strip())
    if not common_dir.is_absolute():
        common_dir = candidate / common_dir
    if common_dir.resolve() != git_dir.resolve():
        raise ReconstructedRunnerError("candidate must not use a shared object directory")
    for object_id in protected_object_ids:
        if subprocess.run([*git_prefix, "cat-file", "-e", f"{object_id}^{{blob}}"], capture_output=True, check=False).returncode == 0:
            raise ReconstructedRunnerError("protected object resolves from candidate")


def materialize_candidate(
    *,
    source_repository: Path,
    candidate_repository: Path,
    starting_sha: str,
    identity: Mapping[str, str],
    source_release: str,
    protected_paths: Iterable[str],
) -> dict[str, object]:
    """Create a standalone sparse candidate through an explicitly selected Git pack.

    The source is read only through Git's object transport. Protected blob IDs are
    excluded before ``pack-objects`` receives its object list, so their contents
    are neither opened nor copied by this materializer.
    """
    source = source_repository.resolve()
    candidate = candidate_repository.resolve()
    if not source.is_dir() or not (source / ".git").exists():
        raise ReconstructedRunnerError("source repository is unavailable")
    if candidate.exists():
        raise ReconstructedRunnerError("candidate destination must not exist")
    if not candidate.parent.is_dir() or _is_link_or_reparse(candidate.parent):
        raise ReconstructedRunnerError("candidate parent must be a real existing directory")
    normalized_protected = sorted({_safe_relative_path(path) for path in protected_paths}, key=lambda item: item.encode("utf-8"))
    commit_and_trees, safe_blobs, protected_blobs, effective_protected = _parse_tree(source, starting_sha, set(normalized_protected))
    object_ids = [*commit_and_trees, *safe_blobs]
    policy = {
        "schema_version": "1",
        "implementation_generation": IMPLEMENTATION_GENERATION,
        "historical_evidence_sha256": list(_HISTORICAL_EVIDENCE_SHA256),
        "source_release": source_release,
        "starting_sha": starting_sha,
        "identity": {key: identity[key] for key in sorted(identity)},
        "protected_paths": effective_protected,
        "required_commit_and_tree_object_ids": commit_and_trees,
        "safe_blob_object_ids": safe_blobs,
        "protected_blob_object_ids": protected_blobs,
    }
    candidate.mkdir()
    _git(candidate, ["init", "--quiet", "--initial-branch", "bakeoff-contestant"])
    packed = _git(source, ["pack-objects", "--no-reuse-delta", "--no-reuse-object", "--stdout"], input_bytes=("\n".join(object_ids) + "\n").encode("ascii"))
    _git(candidate, ["index-pack", "--stdin"], input_bytes=packed)
    _git(candidate, ["update-ref", "refs/heads/bakeoff-contestant", starting_sha])
    _git(candidate, ["symbolic-ref", "HEAD", "refs/heads/bakeoff-contestant"])
    _write_sparse_patterns(candidate, effective_protected)
    head = _git(candidate, ["rev-parse", "HEAD^{commit}"]).decode("ascii").strip()
    if head != starting_sha:
        raise ReconstructedRunnerError("candidate did not retain the genuine task-start identity")
    verify_candidate_isolation(candidate, protected_object_ids=protected_blobs)
    result: dict[str, object] = dict(policy)
    result["materialization_policy_sha256"] = _digest(policy)
    return result


def candidate_scoped_git_environment(candidate_repository: Path) -> dict[str, str]:
    """Return process-only Git trust for the one disposable candidate."""
    return {
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "safe.directory",
        "GIT_CONFIG_VALUE_0": candidate_repository.resolve().as_posix(),
    }


def _grant_sandbox_modify(path: Path, sandbox_identity: str) -> None:
    if sandbox_identity != SANDBOX_IDENTITY:
        raise ReconstructedRunnerError("sandbox identity is not the frozen baseline identity")
    if not path.is_dir() or _is_link_or_reparse(path):
        raise ReconstructedRunnerError("sandbox ACL target must be a real disposable directory")
    result = subprocess.run(
        ["icacls", str(path), "/grant", f"{sandbox_identity}:(OI)(CI)M", "/T", "/C"],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ReconstructedRunnerError("candidate-scoped sandbox ACL could not be applied")


def prepare_sandbox_execution_paths(
    *,
    candidate_repository: Path,
    evidence_directory: Path,
    sandbox_identity: str = SANDBOX_IDENTITY,
) -> dict[str, str]:
    """Prepare only the pre-created disposable paths for the baseline identity.

    The returned environment is passed only to the contestant process. It avoids
    persistent global ``safe.directory`` configuration.
    """
    candidate = candidate_repository.resolve()
    evidence = evidence_directory.resolve()
    if not candidate.is_dir() or _is_link_or_reparse(candidate):
        raise ReconstructedRunnerError("candidate directory must exist before sandbox preparation")
    if evidence.exists():
        raise ReconstructedRunnerError("evidence directory must be freshly pre-created by this procedure")
    if not evidence.parent.is_dir() or _is_link_or_reparse(evidence.parent):
        raise ReconstructedRunnerError("evidence parent must be a real existing directory")
    evidence.mkdir()
    _grant_sandbox_modify(candidate, sandbox_identity)
    _grant_sandbox_modify(evidence, sandbox_identity)
    return candidate_scoped_git_environment(candidate)


def materializer_sha256() -> str:
    """Return the exact bytes digest of this trusted materializer implementation."""
    return sha256(Path(__file__).read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def launcher_configuration_sha256(specification: Mapping[str, object]) -> str:
    """Hash the launcher declaration, excluding its self-identifying digest field."""
    unsigned = dict(specification)
    unsigned.pop("launcher_configuration_sha256", None)
    return _digest(unsigned)


def load_runner_specification(path: Path) -> dict[str, object]:
    """Load and validate the sealed reconstructed runner declaration."""
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise ReconstructedRunnerError("runner specification is unavailable or malformed") from exc
    expected = {
        "schema_version",
        "implementation_generation",
        "infrastructure_discontinuity",
        "historical_evidence_sha256",
        "materializer",
        "launcher",
        "launcher_configuration_sha256",
    }
    if not isinstance(payload, dict) or set(payload) != expected or payload["schema_version"] != "1":
        raise ReconstructedRunnerError("runner specification has an invalid field set")
    if payload["implementation_generation"] != IMPLEMENTATION_GENERATION:
        raise ReconstructedRunnerError("runner specification has an unexpected implementation generation")
    if payload["infrastructure_discontinuity"] != {
        "historical_runs": ["RUN-002", "RUN-003"],
        "historical_materializer": "implementation-A-unrecoverable",
        "future_runs": "RUN-004-onward",
    }:
        raise ReconstructedRunnerError("runner specification infrastructure discontinuity is invalid")
    if payload["historical_evidence_sha256"] != list(_HISTORICAL_EVIDENCE_SHA256):
        raise ReconstructedRunnerError("runner specification historical evidence does not match the retained records")
    materializer = payload["materializer"]
    if not isinstance(materializer, dict) or materializer != {"path": "tools/bakeoff_v1_runner.py", "sha256": materializer_sha256()}:
        raise ReconstructedRunnerError("runner specification materializer identity does not match this implementation")
    launcher = payload["launcher"]
    if not isinstance(launcher, dict) or set(launcher) != {"cli_version", "node_executable", "codex_js", "global_arguments", "exec_arguments"}:
        raise ReconstructedRunnerError("runner specification launcher is invalid")
    if not all(isinstance(launcher[field], str) and launcher[field] for field in ("cli_version", "node_executable", "codex_js")):
        raise ReconstructedRunnerError("runner specification launcher paths are invalid")
    if not all(isinstance(launcher[field], list) and all(isinstance(item, str) for item in launcher[field]) for field in ("global_arguments", "exec_arguments")):
        raise ReconstructedRunnerError("runner specification launcher arguments are invalid")
    if payload["launcher_configuration_sha256"] != launcher_configuration_sha256(payload):
        raise ReconstructedRunnerError("runner specification launcher digest is invalid")
    return payload


def build_launcher_command(
    specification: Mapping[str, object],
    *,
    candidate_repository: Path,
    final_output: Path,
) -> list[str]:
    """Build, but never execute, the historically evidenced Codex command."""
    launcher = specification.get("launcher")
    if not isinstance(launcher, Mapping):
        raise ReconstructedRunnerError("runner specification launcher is invalid")
    candidate = str(candidate_repository).replace("\\", "/")
    output = str(final_output).replace("\\", "/")
    arguments = [*launcher["global_arguments"], *launcher["exec_arguments"]]
    return [
        str(launcher["node_executable"]),
        str(launcher["codex_js"]),
        *(argument.replace("{candidate}", candidate).replace("{final_output}", output) for argument in arguments),
    ]
