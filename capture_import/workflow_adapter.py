"""Application-layer adapter from ``PreparedImport`` to the coordinator seam.

Sprint 7 Unit 7.  This module is the only application-layer bridge between
the workflow boundary object and the existing durable path::

    prepared.validate()
    coordinator.prepare(prepared.request.source)
    coordinator.commit(staged, decisions)

Contract (owner-mandated):

- one-way, stateless translation only — no business logic, no workflow
  state or lifecycle, no retries, no alternate failure policy;
- it does not inspect or reinterpret artifact contents;
- ``PreparedImport`` is passed through unchanged and remains immutable;
- every durable effect stays inside the existing
  ``PackageImportCoordinator`` / ``TransactionService`` seam, reachable
  exclusively through the Unit 6 transaction delegate (this function is
  supplied to ``ImportWorkflow.execute`` as that delegate);
- coordinator, transaction, rollback, and recovery exceptions propagate
  unwrapped.

``ImportWorkflow`` itself remains unaware of this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .coordinator import PackageImportCoordinator
from .preview import PreviewDecisionSet
from .workflow_models import PreparedImport

if TYPE_CHECKING:
    from .transaction import PackageImportExecutionResult


def commit_prepared_import(
    prepared: PreparedImport,
    decisions: PreviewDecisionSet,
    *,
    coordinator: PackageImportCoordinator,
) -> PackageImportExecutionResult:
    """Drive the existing prepare/commit seam for one ``PreparedImport``.

    Args:
        prepared: The validated workflow boundary object.  Its source and
            optional processed-artifact ownership object are routed unchanged;
            artifact contents are never inspected here.
        decisions: The externally supplied preview decisions, passed to
            ``PackageImportCoordinator.commit`` unchanged.
        coordinator: The existing application coordinator.  Its public
            signatures are used exactly as-is.

    Returns:
        The coordinator's commit result, unchanged.

    Raises:
        TypeError: If ``prepared`` or ``decisions`` has the wrong type.
        ValueError: If ``prepared`` fails its own model validation.
    """
    if not isinstance(prepared, PreparedImport):
        raise TypeError(
            f"prepared must be a PreparedImport, not {type(prepared).__name__}."
        )
    prepared.validate()
    if not isinstance(decisions, PreviewDecisionSet):
        raise TypeError(
            f"decisions must be a PreviewDecisionSet, not "
            f"{type(decisions).__name__}."
        )
    if prepared.processed_artifacts is None:
        staged = coordinator.prepare(prepared.request.source)
    else:
        staged = coordinator.prepare(
            prepared.request.source,
            processed_artifacts=prepared.processed_artifacts,
        )
    return coordinator.commit(staged, decisions)
