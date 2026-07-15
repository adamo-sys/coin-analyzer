"""Durable, collector-confirmed observations for future offline evaluation."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from atomic_json import write_json_atomically


OBSERVATION_SCHEMA_VERSION = "1"
CONFIRMED_OBSERVATIONS_FILENAME = "confirmed_observations.json"
DEFAULT_CONFIRMED_OBSERVATIONS_PATH = os.path.join(
    "collection_data",
    "app_state",
    CONFIRMED_OBSERVATIONS_FILENAME,
)


class ObservationOutcome(str, Enum):
    ACCEPTED = "ACCEPTED"
    CORRECTED = "CORRECTED"
    DEFERRED = "DEFERRED"
    REJECTED = "REJECTED"


class FeedbackCategory(str, Enum):
    OCR_MISREAD = "OCR_MISREAD"
    IDENTIFICATION_MISMATCH = "IDENTIFICATION_MISMATCH"
    IMAGE_READINESS_FALSE_POSITIVE = "IMAGE_READINESS_FALSE_POSITIVE"
    IMAGE_READINESS_FALSE_NEGATIVE = "IMAGE_READINESS_FALSE_NEGATIVE"
    REFERENCE_DATA_CONFLICT = "REFERENCE_DATA_CONFLICT"
    COLLECTION_DUPLICATE_MISS = "COLLECTION_DUPLICATE_MISS"
    COLLECTION_WORKFLOW_FRICTION = "COLLECTION_WORKFLOW_FRICTION"
    OTHER = "OTHER"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _normalized_photo_reference(value: Any) -> str:
    path = _normalized_text(value)
    return os.path.normcase(os.path.normpath(path)) if path else ""


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _normalized_values(values: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(values, Mapping):
        return {}
    return _json_safe(values)


def _stable_identifier(parts: Mapping[str, Any]) -> str:
    payload = json.dumps(_json_safe(parts), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, payload))


@dataclass(frozen=True)
class ConfirmedObservationRecord:
    """One immutable collector outcome, independent from production engines."""

    observation_id: str
    created_at: str
    outcome: ObservationOutcome
    category: FeedbackCategory
    suggested_values: Dict[str, Any]
    confirmed_values: Dict[str, Any]
    engine_name: str
    engine_version: str
    recognition_method: str
    application_version: str
    photo_references: Tuple[str, ...] = ()
    evidence_snapshot: Dict[str, Any] = field(default_factory=dict)
    source_workflow: str = ""
    collector_note: str = ""
    schema_version: str = OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "observation_id", _normalized_text(self.observation_id))
        object.__setattr__(self, "created_at", _normalized_text(self.created_at))
        object.__setattr__(self, "suggested_values", _normalized_values(self.suggested_values))
        object.__setattr__(self, "confirmed_values", _normalized_values(self.confirmed_values))
        object.__setattr__(self, "engine_name", _normalized_text(self.engine_name))
        object.__setattr__(self, "engine_version", _normalized_text(self.engine_version))
        object.__setattr__(self, "recognition_method", _normalized_text(self.recognition_method))
        object.__setattr__(self, "application_version", _normalized_text(self.application_version))
        object.__setattr__(self, "photo_references", tuple(
            reference for reference in (_normalized_photo_reference(item) for item in self.photo_references)
            if reference
        ))
        object.__setattr__(self, "evidence_snapshot", _normalized_values(self.evidence_snapshot))
        object.__setattr__(self, "source_workflow", _normalized_text(self.source_workflow))
        object.__setattr__(self, "collector_note", str(self.collector_note or "").strip())
        object.__setattr__(self, "schema_version", _normalized_text(self.schema_version))

    def validation_errors(self) -> List[str]:
        errors = []
        if self.schema_version != OBSERVATION_SCHEMA_VERSION:
            errors.append(f"Unsupported observation schema version: {self.schema_version or '<blank>'}")
        if not self.observation_id:
            errors.append("observation_id is required")
        if not self.created_at:
            errors.append("created_at is required")
        else:
            try:
                datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            except ValueError:
                errors.append("created_at must be ISO-8601")
        for name, value in [
            ("engine_name", self.engine_name),
            ("engine_version", self.engine_version),
            ("recognition_method", self.recognition_method),
            ("application_version", self.application_version),
            ("source_workflow", self.source_workflow),
        ]:
            if not value:
                errors.append(f"{name} is required")
        if self.outcome in {ObservationOutcome.ACCEPTED, ObservationOutcome.CORRECTED} and not self.confirmed_values:
            errors.append("confirmed_values are required for accepted or corrected outcomes")
        if self.outcome in {ObservationOutcome.DEFERRED, ObservationOutcome.REJECTED} and self.confirmed_values:
            errors.append("confirmed_values must be empty for deferred or rejected outcomes")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "observation_id": self.observation_id,
            "created_at": self.created_at,
            "outcome": self.outcome.value,
            "category": self.category.value,
            "suggested_values": _json_safe(self.suggested_values),
            "confirmed_values": _json_safe(self.confirmed_values),
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "recognition_method": self.recognition_method,
            "application_version": self.application_version,
            "photo_references": list(self.photo_references),
            "evidence_snapshot": _json_safe(self.evidence_snapshot),
            "source_workflow": self.source_workflow,
            "collector_note": self.collector_note,
        }

    def identity_dict(self) -> Dict[str, Any]:
        payload = self.to_dict()
        payload.pop("created_at", None)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ConfirmedObservationRecord":
        if not isinstance(payload, Mapping):
            raise ValueError("Observation record must be an object")
        try:
            outcome = ObservationOutcome(str(payload.get("outcome") or "").upper())
            category = FeedbackCategory(str(payload.get("category") or "").upper())
        except ValueError as error:
            raise ValueError(f"Invalid observation enum: {error}") from error
        record = cls(
            schema_version=str(payload.get("schema_version") or ""),
            observation_id=str(payload.get("observation_id") or ""),
            created_at=str(payload.get("created_at") or ""),
            outcome=outcome,
            category=category,
            suggested_values=payload.get("suggested_values") or {},
            confirmed_values=payload.get("confirmed_values") or {},
            engine_name=str(payload.get("engine_name") or ""),
            engine_version=str(payload.get("engine_version") or ""),
            recognition_method=str(payload.get("recognition_method") or ""),
            application_version=str(payload.get("application_version") or ""),
            photo_references=tuple(payload.get("photo_references") or ()),
            evidence_snapshot=payload.get("evidence_snapshot") or {},
            source_workflow=str(payload.get("source_workflow") or ""),
            collector_note=str(payload.get("collector_note") or ""),
        )
        errors = record.validation_errors()
        if errors:
            raise ValueError("; ".join(errors))
        return record

    @classmethod
    def for_detection_save(
        cls,
        detection_result: Mapping[str, Any],
        saved_values: Mapping[str, Any],
        collection_item_id: str,
        application_version: str,
        photos: Optional[Iterable[Any]] = None,
        created_at: Optional[str] = None,
        collector_note: str = "",
    ) -> "ConfirmedObservationRecord":
        suggested = {
            "country": _normalized_text(detection_result.get("country")),
            "denomination": _normalized_text(detection_result.get("denomination")),
            "year": _normalized_text(detection_result.get("year")),
        }
        confirmed = {
            "country": _normalized_text(saved_values.get("country")),
            "denomination": _normalized_text(saved_values.get("denomination")),
            "year": _normalized_text(saved_values.get("year")),
        }
        accepted = all(suggested[name].casefold() == confirmed[name].casefold() for name in suggested)
        outcome = ObservationOutcome.ACCEPTED if accepted else ObservationOutcome.CORRECTED
        references = tuple(
            _normalized_photo_reference(getattr(photo, "path", photo))
            for photo in (photos or ())
            if _normalized_photo_reference(getattr(photo, "path", photo))
        )
        if not references:
            image_path = _normalized_photo_reference(detection_result.get("image_path"))
            references = (image_path,) if image_path else ()
        identity = {
            "collection_item_id": _normalized_text(collection_item_id),
            "source_workflow": "collection_entry_detection_save",
            "outcome": outcome.value,
            "suggested_values": suggested,
            "confirmed_values": confirmed,
            "photo_references": references,
            "method": _normalized_text(detection_result.get("method")),
        }
        return cls(
            observation_id=_stable_identifier(identity),
            created_at=created_at or _utc_now(),
            outcome=outcome,
            category=FeedbackCategory.OTHER if accepted else FeedbackCategory.IDENTIFICATION_MISMATCH,
            suggested_values=suggested,
            confirmed_values=confirmed,
            engine_name=_normalized_text(detection_result.get("engine_name")) or "coin_recognition",
            engine_version=_normalized_text(detection_result.get("engine_version")) or "unknown",
            recognition_method=_normalized_text(detection_result.get("method")) or "unknown",
            application_version=application_version,
            photo_references=references,
            evidence_snapshot={
                "confidence": detection_result.get("confidence", 0.0),
                "year_confidence": detection_result.get("year_confidence", 0.0),
                "method": detection_result.get("method", "unknown"),
            },
            source_workflow="collection_entry_detection_save",
            collector_note=collector_note,
        )


@dataclass
class ObservationLoadResult:
    records: List[ConfirmedObservationRecord] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    path: str = ""

    @property
    def success(self) -> bool:
        return not self.errors


@dataclass
class AppendResult:
    success: bool
    status: str
    observation: Optional[ConfirmedObservationRecord] = None
    already_recorded: bool = False
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class ConfirmedObservationStore:
    """Read and append collector-confirmed records without engine integration."""

    def __init__(self, path: str = DEFAULT_CONFIRMED_OBSERVATIONS_PATH):
        self.path = path

    def load(self) -> ObservationLoadResult:
        if not os.path.exists(self.path):
            return ObservationLoadResult(path=self.path)
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as error:
            return ObservationLoadResult(path=self.path, errors=[f"Could not read observation store: {error}"])
        if not isinstance(payload, Mapping):
            return ObservationLoadResult(path=self.path, errors=["Observation store root must be an object"])
        schema_version = _normalized_text(payload.get("schema_version"))
        if schema_version != OBSERVATION_SCHEMA_VERSION:
            return ObservationLoadResult(
                path=self.path,
                errors=[f"Unsupported observation store schema version: {schema_version or '<blank>'}"],
            )
        rows = payload.get("records")
        if not isinstance(rows, list):
            return ObservationLoadResult(path=self.path, errors=["Observation store records must be a list"])
        result = ObservationLoadResult(path=self.path)
        for index, row in enumerate(rows):
            try:
                result.records.append(ConfirmedObservationRecord.from_dict(row))
            except Exception as error:
                result.warnings.append(f"Skipped malformed observation at index {index}: {error}")
        result.records.sort(key=lambda record: (record.created_at, record.observation_id))
        return result

    def contains(self, observation_id: str) -> bool:
        return any(record.observation_id == observation_id for record in self.load().records)

    def append(self, observation: ConfirmedObservationRecord) -> AppendResult:
        validation_errors = observation.validation_errors()
        if validation_errors:
            return AppendResult(False, "Observation validation failed", observation=observation, errors=validation_errors)
        loaded = self.load()
        if not loaded.success:
            return AppendResult(False, "Observation store is unavailable", observation=observation, errors=loaded.errors)
        if loaded.warnings:
            return AppendResult(
                False,
                "Observation store requires manual repair before writing",
                observation=observation,
                warnings=loaded.warnings,
            )
        for existing in loaded.records:
            if existing.observation_id != observation.observation_id:
                continue
            if existing.identity_dict() == observation.identity_dict():
                return AppendResult(True, "Observation already recorded", observation=existing, already_recorded=True)
            return AppendResult(
                False,
                "Observation ID conflict",
                observation=observation,
                errors=[f"Observation ID {observation.observation_id} already exists with different content"],
            )
        records = sorted(loaded.records + [observation], key=lambda record: (record.created_at, record.observation_id))
        payload = {
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "records": [record.to_dict() for record in records],
        }
        try:
            write_json_atomically(self.path, payload, indent=2, ensure_ascii=False)
        except Exception as error:
            return AppendResult(False, "Observation write failed", observation=observation, errors=[str(error)])
        return AppendResult(True, "Observation recorded", observation=observation)
