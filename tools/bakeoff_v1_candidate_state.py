"""Trusted, privacy-safe freezing of uncommitted Bake-Off candidate state."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import unicodedata
from collections.abc import Iterable, Mapping
from hashlib import sha256
from pathlib import Path, PurePosixPath


class CandidateStateError(ValueError):
    """Raised when a candidate cannot be frozen without ambiguity."""


_EPHEMERAL_COMPONENTS = frozenset({"__pycache__", ".pytest_cache"})
_EPHEMERAL_FILES = frozenset({".coverage"})


def _canonical_bytes(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Mapping[str, object]) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _safe_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise CandidateStateError("candidate path must be a non-empty string")
    normalized = unicodedata.normalize("NFC", value.replace("\\", "/"))
    try:
        normalized.encode("utf-8", "strict")
    except UnicodeError as exc:
        raise CandidateStateError("candidate path is not valid UTF-8") from exc
    path = PurePosixPath(normalized)
    if path.is_absolute() or normalized != path.as_posix() or any(part in {"", ".", ".."} for part in path.parts):
        raise CandidateStateError("candidate path must be a safe relative path")
    return normalized


def _identity(value: Mapping[str, object]) -> dict[str, str]:
    expected = {"benchmark_id", "task_id", "run_id", "execution_protocol_version", "starting_sha"}
    if set(value) != expected or not all(isinstance(value[key], str) and value[key] for key in expected):
        raise CandidateStateError("candidate-state identity is invalid")
    if value["execution_protocol_version"] != "1.1":
        raise CandidateStateError("candidate-state freezer requires execution protocol v1.1")
    if len(str(value["starting_sha"])) != 40:
        raise CandidateStateError("candidate-state starting_sha must be a full Git SHA")
    return {key: str(value[key]) for key in sorted(expected)}


def _git(repository: Path, arguments: list[str], *, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-c", f"safe.directory={repository.resolve().as_posix()}", "-C", str(repository), *arguments],
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise CandidateStateError(f"candidate Git command failed: {' '.join(arguments)}")
    return result.stdout


def _validate_repository(repository: Path, starting_sha: str) -> None:
    if not repository.is_dir():
        raise CandidateStateError("candidate repository path is not a directory")
    head = _git(repository, ["rev-parse", "HEAD^{commit}"]).decode("ascii").strip()
    if head != starting_sha:
        raise CandidateStateError("candidate HEAD does not match the genuine task start")
    if _git(repository, ["remote"]).strip():
        raise CandidateStateError("candidate repository must not retain a remote")
    git_dir = Path(_git(repository, ["rev-parse", "--git-dir"]).decode("utf-8").strip())
    if not git_dir.is_absolute():
        git_dir = repository / git_dir
    if (git_dir / "objects" / "info" / "alternates").exists():
        raise CandidateStateError("candidate repository must not use alternates")
    partial = subprocess.run(
        ["git", "-c", f"safe.directory={repository.resolve().as_posix()}", "-C", str(repository), "config", "--get", "extensions.partialClone"],
        capture_output=True,
        check=False,
    )
    if partial.returncode == 0 and partial.stdout.strip():
        raise CandidateStateError("candidate repository must not use a promisor remote")


def _index_entries(repository: Path) -> list[dict[str, object]]:
    raw = _git(repository, ["ls-files", "--stage", "-z"])
    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    folded: set[str] = set()
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split()
            path = _safe_relative_path(raw_path.decode("utf-8", "strict"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise CandidateStateError("candidate Git index state is malformed") from exc
        if stage != "0":
            raise CandidateStateError("candidate Git index has unmerged entries")
        if path in seen or path.casefold() in folded:
            raise CandidateStateError("candidate Git index has duplicate canonical paths")
        if mode not in {"100644", "100755", "120000"} or len(object_id) not in {40, 64}:
            raise CandidateStateError("candidate Git index has unsupported entry metadata")
        seen.add(path)
        folded.add(path.casefold())
        entries.append({"path": path, "stage": 0, "mode": mode, "object_id": object_id})
    return sorted(entries, key=lambda entry: str(entry["path"]).encode("utf-8"))


def _is_ephemeral(relative: str) -> bool:
    path = PurePosixPath(relative)
    return path.name in _EPHEMERAL_FILES or any(part in _EPHEMERAL_COMPONENTS for part in path.parts)


def _is_protected_image_path(relative: str) -> bool:
    return relative.startswith("test_coins/") and relative != "test_coins/README.md"


def _worktree_entries(repository: Path, protected_paths: set[str]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    seen: set[str] = set()
    folded: set[str] = set()
    pending = [repository]
    while pending:
        current = pending.pop()
        try:
            children = sorted(os.scandir(current), key=lambda item: item.name.encode("utf-8", "surrogateescape"))
        except OSError as exc:
            raise CandidateStateError("candidate state is unreadable") from exc
        for child in children:
            if current == repository and child.name == ".git":
                continue
            relative = _safe_relative_path(str((Path(child.path)).relative_to(repository)).replace("\\", "/"))
            if relative in protected_paths or _is_protected_image_path(relative):
                raise CandidateStateError("protected path was materialized in candidate state")
            if _is_ephemeral(relative):
                continue
            try:
                mode = os.lstat(child.path).st_mode
            except OSError as exc:
                raise CandidateStateError("candidate state changed during collection") from exc
            if stat.S_ISLNK(mode):
                raise CandidateStateError("candidate state contains an unsafe symlink")
            if stat.S_ISDIR(mode):
                pending.append(Path(child.path))
                continue
            if not stat.S_ISREG(mode):
                raise CandidateStateError("candidate state contains an unsupported file type")
            if relative in seen or relative.casefold() in folded:
                raise CandidateStateError("candidate state has duplicate canonical paths")
            try:
                content = Path(child.path).read_bytes()
            except OSError as exc:
                raise CandidateStateError("candidate state is unreadable") from exc
            seen.add(relative)
            folded.add(relative.casefold())
            entries.append(
                {
                    "path": relative,
                    "entry_type": "file",
                    "mode": "100755" if mode & 0o111 else "100644",
                    "size": len(content),
                    "sha256": sha256(content).hexdigest(),
                }
            )
    return sorted(entries, key=lambda entry: str(entry["path"]).encode("utf-8"))


def _blob_oid(repository: Path, path: str, content: bytes) -> str:
    """Use Git's clean-filter-aware object identity for an indexed file."""
    return _git(repository, ["hash-object", "--stdin", f"--path={path}"], input_bytes=content).decode("ascii").strip()


def _collect_candidate_state(repository: Path, identity: Mapping[str, object], baseline: Mapping[str, object]) -> dict[str, object]:
    protected = set(baseline["protected_paths"])
    entries = _worktree_entries(repository, protected)
    index_entries = _index_entries(repository)
    baseline_entries = {str(entry["path"]): entry for entry in baseline["worktree_entries"]}
    final_entries = {str(entry["path"]): entry for entry in entries}
    baseline_index = {str(entry["path"]): entry for entry in baseline["index_entries"]}
    final_index = {str(entry["path"]): entry for entry in index_entries}
    protected.update(path for path in baseline_index if _is_protected_image_path(path))
    protected.update(path for path in final_index if _is_protected_image_path(path))
    for path in protected:
        if final_index.get(path) != baseline_index.get(path):
            raise CandidateStateError("protected path index entry changed")
    for path, index_entry in final_index.items():
        final = final_entries.get(path)
        baseline_index_entry = baseline_index.get(path)
        if final is None:
            continue
        if baseline_index_entry != index_entry:
            content = (repository / Path(*PurePosixPath(path).parts)).read_bytes()
            if index_entry["object_id"] != _blob_oid(repository, path, content):
                raise CandidateStateError("index/worktree representation is inconsistent")
    added = sorted(set(final_entries) - set(baseline_entries), key=lambda path: path.encode("utf-8"))
    deleted = sorted(set(baseline_entries) - set(final_entries), key=lambda path: path.encode("utf-8"))
    modified = sorted(
        [
            path
            for path in set(final_entries) & set(baseline_entries)
            if final_entries[path] != baseline_entries[path]
        ],
        key=lambda path: path.encode("utf-8"),
    )
    state = {
        "schema_version": "1.1",
        "identity": _identity(identity),
        "materialization_policy_sha256": baseline["materialization_policy_sha256"],
        "worktree_entries": entries,
        "index_entries": index_entries,
        "added_paths": added,
        "modified_paths": modified,
        "deleted_paths": deleted,
    }
    return state


def create_materialization_manifest(
    repository: Path,
    identity: Mapping[str, object],
    *,
    protected_paths: Iterable[str],
) -> dict[str, object]:
    """Record the trusted, materialized task-start state before prompt delivery."""
    normalized_identity = _identity(identity)
    requested_protected = {_safe_relative_path(path) for path in protected_paths}
    _validate_repository(repository, normalized_identity["starting_sha"])
    if _git(repository, ["status", "--porcelain=v1"]).strip():
        raise CandidateStateError("candidate must be clean before materialization is recorded")
    material = {
        "schema_version": "1.1",
        "identity": normalized_identity,
        "protected_paths": [],
        "ephemeral_components": sorted(_EPHEMERAL_COMPONENTS),
        "ephemeral_files": sorted(_EPHEMERAL_FILES),
        "worktree_entries": [],
        "index_entries": [],
    }
    material["index_entries"] = _index_entries(repository)
    requested_protected.update(path for path in (str(entry["path"]) for entry in material["index_entries"]) if _is_protected_image_path(path))
    material["protected_paths"] = sorted(requested_protected, key=lambda path: path.encode("utf-8"))
    material["worktree_entries"] = _worktree_entries(repository, set(material["protected_paths"]))
    material["materialization_policy_sha256"] = _digest(material)
    return material


def freeze_candidate_state(
    repository: Path,
    identity: Mapping[str, object],
    materialization_manifest: Mapping[str, object],
) -> dict[str, object]:
    """Double-collect an uncommitted candidate and return its canonical identity."""
    normalized_identity = _identity(identity)
    if not isinstance(materialization_manifest, Mapping):
        raise CandidateStateError("materialization manifest is invalid")
    baseline = dict(materialization_manifest)
    expected_fields = {
        "schema_version",
        "identity",
        "protected_paths",
        "ephemeral_components",
        "ephemeral_files",
        "worktree_entries",
        "index_entries",
        "materialization_policy_sha256",
    }
    if set(baseline) != expected_fields or baseline["schema_version"] != "1.1" or baseline["identity"] != normalized_identity:
        raise CandidateStateError("materialization manifest is invalid")
    unsigned = dict(baseline)
    actual_policy_digest = unsigned.pop("materialization_policy_sha256")
    if actual_policy_digest != _digest(unsigned):
        raise CandidateStateError("materialization manifest fingerprint is invalid")
    _validate_repository(repository, normalized_identity["starting_sha"])
    first = _collect_candidate_state(repository, normalized_identity, baseline)
    second = _collect_candidate_state(repository, normalized_identity, baseline)
    if _canonical_bytes(first) != _canonical_bytes(second):
        raise CandidateStateError("candidate state changed during freeze")
    state = dict(first)
    state["candidate_state_sha256"] = _digest(first)
    return state


def verify_frozen_worktree_copy(
    repository: Path,
    candidate_state: Mapping[str, object],
    materialization_manifest: Mapping[str, object],
) -> None:
    """Fail closed when a trusted grading copy differs from the frozen worktree."""
    if not isinstance(candidate_state, Mapping) or not isinstance(materialization_manifest, Mapping):
        raise CandidateStateError("frozen candidate state is invalid")
    protected = materialization_manifest.get("protected_paths")
    entries = candidate_state.get("worktree_entries")
    if not isinstance(protected, list) or not all(isinstance(path, str) for path in protected) or not isinstance(entries, list):
        raise CandidateStateError("frozen candidate state is invalid")
    if _worktree_entries(repository, set(protected)) != entries:
        raise CandidateStateError("trusted grading copy does not match frozen candidate state")
