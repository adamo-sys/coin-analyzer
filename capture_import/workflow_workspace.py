"""Workflow-owned, path-contained temporary workspace lifecycle (Sprint 7 Unit 5).

A :class:`WorkflowWorkspace` owns exactly one temporary directory beneath a
caller-configured trusted root.  Processing stages write their outputs into
this directory only; the workspace is cleaned on success, ordinary failure,
and cancellation.

Ownership model
---------------
- The creating instance is the sole owner.  Ownership is proven at cleanup
  by re-verifying the root identity and the workspace directory identity
  captured at creation (via ``path_object_identity``), plus plain-directory
  status that rejects links and reparse points.
- The workspace is ephemeral and single-process (ADR-007): no on-disk
  owner record, no lease, no registry, and no stale-workspace scavenging.
- The configured root is caller-owned.  It is created or verified with the
  Sprint 5 ``ensure_plain_directory`` primitive and is **never** deleted
  by this class.

Containment strategy
--------------------
- Allocation names are validated with the Sprint 5 ``_validate_relative_path``
  rules: absolute paths, ``..`` traversal, backslashes, drive letters,
  non-canonical forms, trailing dots/spaces, and Windows reserved names are
  all rejected.
- Allocated paths are lexically contained by construction (owned directory
  plus validated relative name); parent directories are created with
  ``ensure_plain_directory``, which rejects pre-existing link components.
- Duplicate allocations are detected under ``os.path.normcase`` so
  Windows case-folded aliases cannot collide silently.
- Windows 8.3 namespace hardening: any allocation component containing
  ``~`` is rejected before any state mutation, so NTFS short-name aliases
  cannot bypass duplicate detection.  Artifact names are machine-controlled
  internal identifiers and never require ``~``.

Cleanup semantics
-----------------
- ``close()`` is idempotent and also runs from ``__exit__``.
- Deletion is bounded (``max_entries``), iterative post-order, and never
  follows links: every file is deleted through the identity-verified
  open-then-delete pattern; directories are removed with ``rmdir``;
  links, reparse points, and special entries cause a fail-closed
  :class:`WorkspaceCleanupError` instead of traversal.
- Cleanup failure policy (per IMPORT_WORKFLOW.md "cleanup failure must not
  conceal the primary failure"):
  - ``close()`` raises :class:`WorkspaceCleanupError`, chained from the
    underlying ``OSError``.
  - ``__exit__`` with no in-flight exception propagates the cleanup error.
  - ``__exit__`` with an in-flight exception preserves the primary
    exception and attaches the cleanup failure via ``add_note``.
  - Cleanup failure is never silently ignored.

TOCTOU boundary
---------------
Stages are internal trusted components (ADR-007: no third-party code).
This class is fail-closed against accidents and filesystem anomalies —
malformed names, pre-planted links, identity substitution, runaway trees —
but it does not identity-monitor stage writes between allocation and
cleanup.  It holds no open descriptors of its own; every file handle used
during deletion is opened, verified, and closed inline.
"""

from __future__ import annotations

import itertools
import os
import secrets
import stat
from pathlib import Path
from typing import Callable

from ._filesystem import (
    delete_open_file,
    ensure_plain_directory,
    is_link_or_reparse,
    open_existing_binary_for_delete,
    path_object_identity,
    require_plain_directory,
)
from .models import _validate_relative_path
from .workflow_pipeline import ImportWorkflowError

TokenFactory = Callable[[], str]

DEFAULT_MAX_ENTRIES = 10_000
_TOKEN_HEX_LENGTH = 16


def _default_token() -> str:
    return secrets.token_hex(_TOKEN_HEX_LENGTH // 2)


class WorkflowWorkspaceError(ImportWorkflowError):
    """Base for all workflow workspace lifecycle failures."""


class WorkspaceCreationError(WorkflowWorkspaceError):
    """The workspace could not be created or safely initialized."""


class WorkspacePathError(WorkflowWorkspaceError):
    """An allocation name violates containment or collides with another path."""


class WorkspaceCleanupError(WorkflowWorkspaceError):
    """The owned workspace could not be removed completely and safely."""


class WorkspaceClosedError(WorkflowWorkspaceError):
    """The workspace was used after its owning instance was closed."""


def _validate_token(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _TOKEN_HEX_LENGTH
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise WorkspaceCreationError(
            f"workspace token must be a {_TOKEN_HEX_LENGTH}-character "
            f"lowercase hexadecimal string, got {value!r}."
        )
    return value


def _delete_verified_file(path: Path) -> None:
    """Delete one plain file through the identity-checked no-follow pattern."""

    path.chmod(stat.S_IWRITE | stat.S_IREAD)
    with open_existing_binary_for_delete(path) as handle:
        delete_open_file(handle, path)


def _remove_owned_tree_contents(directory: Path, *, max_entries: int) -> None:
    """Remove every entry beneath ``directory`` without following links.

    Fail-closed: links, reparse points, special entries, or a tree larger
    than ``max_entries`` raise ``OSError`` instead of being traversed.
    The top directory itself is left in place for the caller to remove
    after its identity is re-verified.
    """

    entries = 0
    stack: list[tuple[Path, bool]] = [(directory, False)]
    while stack:
        current, children_done = stack.pop()
        info = current.lstat()
        if is_link_or_reparse(current) or not stat.S_ISDIR(info.st_mode):
            raise OSError(f"Refusing to remove a non-plain directory: {current}")
        if children_done:
            if current != directory:
                # The top directory is left for the caller to remove after
                # its identity is re-verified.
                current.rmdir()
            continue
        stack.append((current, True))
        # Bounded enumeration: materialize at most the remaining entry
        # budget plus one sentinel, so a runaway flat directory cannot
        # exhaust memory before the bound is enforced.  The per-child
        # accounting below preserves the exact ``max_entries`` semantics:
        # precisely ``max_entries`` entries are processed before the
        # (``max_entries`` + 1)-th entry fails closed.
        remaining = max_entries - entries
        children = list(itertools.islice(current.iterdir(), remaining + 1))
        for child in children:
            entries += 1
            if entries > max_entries:
                raise OSError(
                    f"Workspace entry bound exceeded ({max_entries}): refusing "
                    "to remove an unbounded tree."
                )
            if is_link_or_reparse(child):
                raise OSError(f"Refusing to remove a link or reparse point: {child}")
            child_info = child.lstat()
            if stat.S_ISDIR(child_info.st_mode):
                stack.append((child, False))
            elif stat.S_ISREG(child_info.st_mode):
                _delete_verified_file(child)
            else:
                raise OSError(f"Refusing to remove a special entry: {child}")


class WorkflowWorkspace:
    """Own one path-contained temporary workspace directory for one workflow run.

    Creation is eager: the directory ``root / "workflow-<token>"`` is made
    during ``__init__``.  Cleanup happens through ``close()`` (also aliased
    as ``cleanup()``) or by exiting a ``with`` block.  Instances are single
    use: once closed, allocation raises :class:`WorkspaceClosedError` and
    re-entering the context manager is rejected.
    """

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        token_factory: TokenFactory = _default_token,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        root_path = Path(root)
        if not root_path.is_absolute():
            raise ValueError("workspace root must be an absolute path.")
        if (
            isinstance(max_entries, bool)
            or not isinstance(max_entries, int)
            or max_entries < 1
        ):
            raise ValueError("max_entries must be a positive integer.")
        self._root = root_path.absolute()
        self._max_entries = max_entries
        token = _validate_token(token_factory())
        self._workspace_id = token
        self._directory = self._root / f"workflow-{token}"
        self._allocated: set[str] = set()
        self._closed = False
        self._entered = False
        directory_created = False
        try:
            ensure_plain_directory(self._root)
            self._root_identity = path_object_identity(self._root)
            os.mkdir(self._directory, 0o700)
            directory_created = True
            self._directory_identity = path_object_identity(self._directory)
        except Exception as error:
            if isinstance(error, WorkflowWorkspaceError):
                raise
            cleanup_error = self._cleanup_failed_create() if directory_created else None
            creation_error = WorkspaceCreationError(
                f"workspace could not be created beneath {self._root}."
            )
            if cleanup_error is not None:
                creation_error.add_note(
                    f"partial creation cleanup also failed: {cleanup_error}"
                )
            raise creation_error from error

    # -- Identity -------------------------------------------------------------

    @property
    def path(self) -> Path:
        """Absolute path of the owned workspace directory (inspection only)."""
        return self._directory

    @property
    def workspace_id(self) -> str:
        """Unique token identifying this workspace within the trusted root."""
        return self._workspace_id

    @property
    def is_closed(self) -> bool:
        return self._closed

    # -- Path allocation --------------------------------------------------------

    def allocate_path(self, name: str) -> Path:
        """Reserve and return a contained child path for a stage output.

        The name must be a canonical relative POSIX path (see
        ``_validate_relative_path``).  Parent directories are created
        plain-verified; the file itself is not created.  Re-allocating a
        name that was already allocated — including a Windows case-folded
        alias — raises :class:`WorkspacePathError`.
        """

        if self._closed:
            raise WorkspaceClosedError(
                f"workspace {self._workspace_id} is closed; allocation is not "
                "permitted."
            )
        try:
            relative = _validate_relative_path(name, "allocation name")
        except ValueError as error:
            raise WorkspacePathError(
                f"allocation name {name!r} is not a contained relative path."
            ) from error
        # Windows 8.3 namespace hardening: short-name aliases (``LONGFI~1.BIN``)
        # can resolve to an existing long-name entry while bypassing the
        # duplicate-allocation set.  Workspace artifact names are
        # machine-controlled internal identifiers, so ``~`` is rejected in
        # every component before any state mutation or directory creation.
        parts = relative.split("/")
        if any("~" in part for part in parts):
            raise WorkspacePathError(
                f"allocation name {name!r} contains '~', rejected as Windows "
                "8.3 namespace hardening."
            )
        collision_key = os.path.normcase(relative)
        if collision_key in self._allocated:
            raise WorkspacePathError(
                f"allocation name {name!r} collides with an earlier allocation."
            )
        candidate = self._directory.joinpath(*parts)
        try:
            ensure_plain_directory(candidate.parent)
        except OSError as error:
            raise WorkspacePathError(
                f"allocation name {name!r} cannot be contained safely."
            ) from error
        self._allocated.add(collision_key)
        return candidate

    # -- Cleanup ------------------------------------------------------------

    def close(self) -> None:
        """Idempotently remove the exact owned workspace directory.

        Raises:
            WorkspaceCleanupError: If ownership cannot be re-proven, the
                tree violates fail-closed rules, or deletion fails.  Chained
                from the underlying ``OSError``.
        """

        if self._closed:
            return
        try:
            require_plain_directory(self._root)
            if path_object_identity(self._root) != self._root_identity:
                raise OSError("The workspace root identity changed.")
            if not self._directory.exists():
                raise OSError("The owned workspace directory is missing.")
            if (
                self._directory.parent != self._root
                or self._directory.name != f"workflow-{self._workspace_id}"
            ):
                raise OSError("The workspace directory no longer matches its owner.")
            info = self._directory.lstat()
            if is_link_or_reparse(self._directory) or not stat.S_ISDIR(info.st_mode):
                raise OSError("The owned workspace is not a plain directory.")
            if path_object_identity(self._directory) != self._directory_identity:
                raise OSError("The workspace directory identity changed.")
            _remove_owned_tree_contents(self._directory, max_entries=self._max_entries)
            if path_object_identity(self._directory) != self._directory_identity:
                raise OSError("The workspace directory identity changed during cleanup.")
            if is_link_or_reparse(self._directory):
                raise OSError("The workspace directory was substituted during cleanup.")
            self._directory.rmdir()
        except Exception as error:
            if isinstance(error, WorkspaceCleanupError):
                raise
            raise WorkspaceCleanupError(
                f"workspace {self._workspace_id} could not be cleaned safely."
            ) from error
        self._closed = True

    def cleanup(self) -> None:
        """Alias for :meth:`close` mirroring the snapshot handle contract."""
        self.close()

    # -- Context manager ------------------------------------------------------

    def __enter__(self) -> "WorkflowWorkspace":
        if self._closed:
            raise WorkspaceClosedError(
                f"workspace {self._workspace_id} is closed; re-entry is not "
                "permitted."
            )
        if self._entered:
            raise WorkspaceClosedError(
                f"workspace {self._workspace_id} does not support nested entry."
            )
        self._entered = True
        return self

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        try:
            self.close()
        except WorkspaceCleanupError as cleanup_error:
            if exc is None:
                raise
            # Preserve the primary exception; attach, never replace.
            exc.add_note(
                f"workspace cleanup also failed: {cleanup_error}"
            )
        return None

    # -- Creation failure handling ----------------------------------------------

    def _cleanup_failed_create(self) -> OSError | None:
        """Best-effort removal of a partially created (still empty) owned directory.

        Returns the cleanup ``OSError`` on failure so the caller can attach
        it to the primary creation error without replacing it.
        """

        try:
            if self._directory.exists() and not is_link_or_reparse(self._directory):
                self._directory.rmdir()
        except OSError as error:
            return error
        return None
