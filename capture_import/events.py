"""Structured observability events for the capture-package import pipeline.

Events are immutable dataclasses with strict typing. They are designed for:
- progress UI rendering
- debugging and post-mortem analysis
- performance profiling
- telemetry export
- future plugin hooks

Events are not coupled to logging; they are domain facts about import execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class EventSeverity(str, Enum):
    """Importance level for observability and filtering."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EventType(str, Enum):
    """Every event that the import pipeline can emit."""

    IMPORT_STARTED = "IMPORT_STARTED"
    PACKAGE_VALIDATED = "PACKAGE_VALIDATED"
    COLLECTION_CREATED = "COLLECTION_CREATED"
    IMAGES_IMPORTED = "IMAGES_IMPORTED"
    COLLECTION_COMMITTED = "COLLECTION_COMMITTED"
    IMPORT_COMPLETE = "IMPORT_COMPLETE"
    ROLLBACK_STARTED = "ROLLBACK_STARTED"
    ROLLBACK_COMPLETE = "ROLLBACK_COMPLETE"
    RECOVERY_TRIGGERED = "RECOVERY_TRIGGERED"
    RECOVERY_COMPLETE = "RECOVERY_COMPLETE"
    CANCELLED = "CANCELLED"
    # Sprint 7 preprocessing pipeline lifecycle.  These events describe
    # nondurable preparation only; the transaction events above retain
    # their existing semantics, ordering, and ownership.
    PIPELINE_STARTED = "PIPELINE_STARTED"
    STAGE_STARTED = "STAGE_STARTED"
    STAGE_COMPLETED = "STAGE_COMPLETED"
    STAGE_FAILED = "STAGE_FAILED"
    PIPELINE_COMPLETED = "PIPELINE_COMPLETED"
    PIPELINE_CANCELLED = "PIPELINE_CANCELLED"
    PROGRESS = "PROGRESS"


@dataclass(frozen=True, slots=True)
class ImportEvent:
    """Base for every structured import event."""

    event_type: EventType
    timestamp: str
    import_id: str | None
    severity: EventSeverity
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary for JSON encoding."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "import_id": self.import_id,
            "severity": self.severity.value,
            "context": self.context,
        }


Clock = Callable[[], str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ImportEventBus:
    """Lightweight, in-memory event recorder for one import session.

    Not a generic pub/sub — events are accumulated for querying,
    progress rendering, and eventual persistence. Thread-safety is
    the caller's responsibility (the import lock already serializes).

    **Lifecycle**
    One bus instance is scoped to exactly one import session. It must not
    be retained or reused across imports. In-memory event accumulation is
    therefore intentionally session-bounded.

    **Failure contract**
    ``record()`` and ``record_progress()`` are internal synchronous
    operations that operate on service-controlled inputs. They are
    expected to be noexcept under normal conditions.  Do not add broad
    exception swallowing; programming errors should be visible.
    """
    """Lightweight, in-memory event recorder for one import session.

    Not a generic pub/sub — events are accumulated for querying,
    progress rendering, and eventual persistence. Thread-safety is
    the caller's responsibility (the import lock already serializes).
    """

    def __init__(
        self,
        *,
        clock: Clock = _utc_now,
        events: list[ImportEvent] | None = None,
    ) -> None:
        self._clock = clock
        self._events: list[ImportEvent] = list(events) if events is not None else []

    # -- Recording ---------------------------------------------------------

    def record(
        self,
        event_type: EventType,
        *,
        import_id: str | None = None,
        severity: EventSeverity = EventSeverity.INFO,
        **context: Any,
    ) -> ImportEvent:
        """Append one event and return it."""
        event = ImportEvent(
            event_type=event_type,
            timestamp=self._clock(),
            import_id=import_id,
            severity=severity,
            context=context,
        )
        self._events.append(event)
        return event

    def record_started(
        self,
        *,
        import_id: str,
        package_basename: str,
        proposed_count: int,
    ) -> ImportEvent:
        return self.record(
            EventType.IMPORT_STARTED,
            import_id=import_id,
            severity=EventSeverity.INFO,
            package_basename=package_basename,
            proposed_count=proposed_count,
        )

    def record_validated(
        self,
        *,
        import_id: str,
        package_sha256: str,
        package_byte_length: int,
    ) -> ImportEvent:
        return self.record(
            EventType.PACKAGE_VALIDATED,
            import_id=import_id,
            severity=EventSeverity.INFO,
            package_sha256=package_sha256,
            package_byte_length=package_byte_length,
        )

    def record_collection_created(
        self,
        *,
        import_id: str,
        journal_phase: str,
    ) -> ImportEvent:
        return self.record(
            EventType.COLLECTION_CREATED,
            import_id=import_id,
            severity=EventSeverity.INFO,
            journal_phase=journal_phase,
        )

    def record_images_imported(
        self,
        *,
        import_id: str,
        image_count: int,
        created_relative_paths: tuple[str, ...],
    ) -> ImportEvent:
        return self.record(
            EventType.IMAGES_IMPORTED,
            import_id=import_id,
            severity=EventSeverity.INFO,
            image_count=image_count,
            created_relative_paths=created_relative_paths,
        )

    def record_collection_committed(
        self,
        *,
        import_id: str,
        committed_count: int,
        desktop_item_ids: tuple[str, ...],
    ) -> ImportEvent:
        return self.record(
            EventType.COLLECTION_COMMITTED,
            import_id=import_id,
            severity=EventSeverity.INFO,
            committed_count=committed_count,
            desktop_item_ids=desktop_item_ids,
        )

    def record_complete(
        self,
        *,
        import_id: str,
        status: str,
        imported_count: int,
        skipped_count: int,
        image_count: int,
    ) -> ImportEvent:
        return self.record(
            EventType.IMPORT_COMPLETE,
            import_id=import_id,
            severity=EventSeverity.INFO,
            status=status,
            imported_count=imported_count,
            skipped_count=skipped_count,
            image_count=image_count,
        )

    def record_rollback_started(
        self,
        *,
        import_id: str | None,
        reason: str,
    ) -> ImportEvent:
        return self.record(
            EventType.ROLLBACK_STARTED,
            import_id=import_id,
            severity=EventSeverity.WARNING,
            reason=reason,
        )

    def record_rollback_complete(
        self,
        *,
        import_id: str | None,
        status: str,
    ) -> ImportEvent:
        return self.record(
            EventType.ROLLBACK_COMPLETE,
            import_id=import_id,
            severity=EventSeverity.INFO,
            status=status,
        )

    def record_recovery_triggered(
        self,
        *,
        import_id: str,
        journal_phase: str,
        recovery_attempt_count: int,
    ) -> ImportEvent:
        return self.record(
            EventType.RECOVERY_TRIGGERED,
            import_id=import_id,
            severity=EventSeverity.WARNING,
            journal_phase=journal_phase,
            recovery_attempt_count=recovery_attempt_count,
        )

    def record_recovery_complete(
        self,
        *,
        import_id: str,
        final_phase: str,
    ) -> ImportEvent:
        return self.record(
            EventType.RECOVERY_COMPLETE,
            import_id=import_id,
            severity=EventSeverity.INFO,
            final_phase=final_phase,
        )

    def record_cancelled(
        self,
        *,
        import_id: str | None,
        reason: str,
    ) -> ImportEvent:
        return self.record(
            EventType.CANCELLED,
            import_id=import_id,
            severity=EventSeverity.INFO,
            reason=reason,
        )

    # -- Pipeline lifecycle (Sprint 7 preprocessing) ------------------------

    def record_pipeline_started(
        self,
        *,
        import_id: str | None,
        stage_ids: tuple[str, ...],
    ) -> ImportEvent:
        return self.record(
            EventType.PIPELINE_STARTED,
            import_id=import_id,
            severity=EventSeverity.INFO,
            stage_ids=stage_ids,
            stage_count=len(stage_ids),
        )

    def record_stage_started(
        self,
        *,
        import_id: str | None,
        stage_id: str,
        stage_index: int,
        stage_count: int,
    ) -> ImportEvent:
        return self.record(
            EventType.STAGE_STARTED,
            import_id=import_id,
            severity=EventSeverity.INFO,
            stage_id=stage_id,
            stage_index=stage_index,
            stage_count=stage_count,
        )

    def record_stage_completed(
        self,
        *,
        import_id: str | None,
        stage_id: str,
        stage_index: int,
    ) -> ImportEvent:
        return self.record(
            EventType.STAGE_COMPLETED,
            import_id=import_id,
            severity=EventSeverity.INFO,
            stage_id=stage_id,
            stage_index=stage_index,
        )

    def record_stage_failed(
        self,
        *,
        import_id: str | None,
        stage_id: str,
        stage_index: int,
        error_type: str,
    ) -> ImportEvent:
        return self.record(
            EventType.STAGE_FAILED,
            import_id=import_id,
            severity=EventSeverity.ERROR,
            stage_id=stage_id,
            stage_index=stage_index,
            error_type=error_type,
        )

    def record_pipeline_completed(
        self,
        *,
        import_id: str | None,
        stage_count: int,
    ) -> ImportEvent:
        return self.record(
            EventType.PIPELINE_COMPLETED,
            import_id=import_id,
            severity=EventSeverity.INFO,
            stage_count=stage_count,
        )

    def record_pipeline_cancelled(
        self,
        *,
        import_id: str | None,
        stage_id: str | None,
        stage_index: int | None,
        reason: str,
    ) -> ImportEvent:
        return self.record(
            EventType.PIPELINE_CANCELLED,
            import_id=import_id,
            severity=EventSeverity.INFO,
            stage_id=stage_id,
            stage_index=stage_index,
            reason=reason,
        )

    def record_progress(
        self,
        *,
        import_id: str,
        stage: str,
        current: int,
        total: int,
    ) -> ImportEvent:
        return self.record(
            EventType.PROGRESS,
            import_id=import_id,
            severity=EventSeverity.DEBUG,
            stage=stage,
            current=current,
            total=total,
        )

    # -- Querying ----------------------------------------------------------

    @property
    def events(self) -> tuple[ImportEvent, ...]:
        """All recorded events, immutable."""
        return tuple(self._events)

    def by_type(self, event_type: EventType) -> tuple[ImportEvent, ...]:
        """Filter events by type."""
        return tuple(e for e in self._events if e.event_type is event_type)

    def by_severity(self, severity: EventSeverity) -> tuple[ImportEvent, ...]:
        """Filter events at or above the given severity level."""
        order = list(EventSeverity)
        threshold = order.index(severity)
        return tuple(
            e for e in self._events if order.index(e.severity) >= threshold
        )

    def latest(self) -> ImportEvent | None:
        """Most recent event, or None if empty."""
        return self._events[-1] if self._events else None

    def to_dicts(self) -> list[dict[str, Any]]:
        """Serialize all events to plain dictionaries."""
        return [e.to_dict() for e in self._events]

    def __len__(self) -> int:
        return len(self._events)

    def __bool__(self) -> bool:
        return bool(self._events)
