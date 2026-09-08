"""Finalize one completed identification execution into the AI audit store.

This module is deliberately downstream of execution, verification, human review,
and persistence. It records already-established outcomes only. It does not call
an executor, invoke a provider, authorize collection mutation, retry work, or
alter collection state when audit persistence succeeds or fails.
"""

from __future__ import annotations

from ai_execution_audit import (
    AIExecutionAuditRecord,
    HumanDisposition,
    PersistenceDisposition,
    build_ai_execution_audit_record,
)
from ai_execution_audit_store import AIExecutionAuditStore
from identification_specialist import IdentificationSpecialistRequest
from identification_specialist_execution import IdentificationSpecialistExecutionReport


def finalize_identification_execution_audit(
    *,
    execution_id: str,
    occurred_at: str,
    workflow_id: str,
    request: IdentificationSpecialistRequest,
    report: IdentificationSpecialistExecutionReport,
    human_disposition: HumanDisposition,
    persistence_disposition: PersistenceDisposition,
    store: AIExecutionAuditStore,
) -> AIExecutionAuditRecord:
    """Append one already-completed identification outcome to the audit store.

    The caller supplies the human and persistence dispositions after those
    authorities have acted. This function never infers either disposition and
    never re-executes the specialist. Audit-store failure is therefore an audit
    failure only; no collection write is attempted or rolled back here.
    """

    if not isinstance(store, AIExecutionAuditStore):
        raise TypeError("store must be an AIExecutionAuditStore.")

    record = build_ai_execution_audit_record(
        execution_id=execution_id,
        occurred_at=occurred_at,
        workflow_id=workflow_id,
        request=request,
        report=report,
        human_disposition=human_disposition,
        persistence_disposition=persistence_disposition,
    )
    store.append(record)
    return record
