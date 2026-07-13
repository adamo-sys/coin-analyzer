"""Neutral Canadian reference provider contracts.

v8.8 Phase 4A only: DTOs, provider protocol, provenance, normalization,
capabilities, validation, and structured errors. This module does not load
catalogues, scrape websites, call networks, identify coins, grade coins,
price coins, or integrate with the GUI/workspace.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple, runtime_checkable


REFERENCE_JSON_SCHEMA_VERSION = 1


class ReferenceSourceType(str, Enum):
    LOCAL_JSON = "LOCAL_JSON"
    MANUAL = "MANUAL"
    OPEN_DATA = "OPEN_DATA"
    LICENSED = "LICENSED"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"


class ReferenceProviderCapability(str, Enum):
    ISSUE_LOOKUP = "ISSUE_LOOKUP"
    SEARCH = "SEARCH"
    FILTERS = "FILTERS"
    FIELD_PROVENANCE = "FIELD_PROVENANCE"
    CONFLICT_REPORTING = "CONFLICT_REPORTING"
    EXPORT = "EXPORT"
    VALIDATION = "VALIDATION"


class ReferenceSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ReferenceConflictType(str, Enum):
    MINTAGE = "MINTAGE"
    WEIGHT = "WEIGHT"
    DIAMETER = "DIAMETER"
    COMPOSITION = "COMPOSITION"
    VARIETY = "VARIETY"
    CATALOGUE_NUMBER = "CATALOGUE_NUMBER"
    DATE_TEXT = "DATE_TEXT"
    OTHER = "OTHER"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def normalize_text(value: Any) -> str:
    return _clean(value).lower()


def normalize_country(value: Any) -> str:
    aliases = {"can": "canada", "ca": "canada"}
    text = normalize_text(value)
    return aliases.get(text, text)


def normalize_authority(value: Any) -> str:
    return normalize_text(value)


def normalize_denomination(value: Any) -> str:
    text = normalize_text(value).replace("cents", "cent")
    text = text.replace(" dollar", " dollar")
    return text


def normalize_year(value: Any) -> str:
    return _clean(value)


def normalize_date_text(value: Any) -> str:
    return _clean(value)


def normalize_mintmark(value: Any) -> str:
    return normalize_text(value)


def normalize_composition(value: Any) -> str:
    return normalize_text(value)


def normalize_variety(value: Any) -> str:
    return normalize_text(value)


def normalize_catalogue_id(value: Any) -> str:
    text = normalize_text(value)
    text = text.replace("#", "")
    text = re.sub(r"\s+", "", text)
    return text


def normalize_measurement(value: Any) -> Tuple[str, str]:
    text = _clean(value)
    if not text:
        return "", ""
    match = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*([a-zA-Z]+)$", text)
    if not match:
        return text, ""
    return match.group(1), match.group(2).lower()


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _enum_member(enum_type: Any, value: Any, default: Any) -> Any:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value or ""))
    except ValueError:
        return default


def _string_tuple(values: Iterable[Any]) -> Tuple[str, ...]:
    return tuple(str(value or "").strip() for value in values or [] if str(value or "").strip())


@dataclass(frozen=True)
class ReferenceSource:
    source_id: str
    source_name: str
    source_type: ReferenceSourceType
    edition: str = ""
    url: str = ""
    licence: str = ""
    attribution: str = ""
    retrieved_at: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _clean(self.source_id))
        object.__setattr__(self, "source_name", _clean(self.source_name))
        object.__setattr__(self, "source_type", _enum_member(ReferenceSourceType, self.source_type, ReferenceSourceType.MANUAL))
        object.__setattr__(self, "edition", _clean(self.edition))
        object.__setattr__(self, "url", _clean(self.url))
        object.__setattr__(self, "licence", _clean(self.licence))
        object.__setattr__(self, "attribution", _clean(self.attribution))
        object.__setattr__(self, "retrieved_at", _clean(self.retrieved_at))
        object.__setattr__(self, "notes", _clean(self.notes))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_type": self.source_type.value,
            "edition": self.edition,
            "url": self.url,
            "licence": self.licence,
            "attribution": self.attribution,
            "retrieved_at": self.retrieved_at,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class SourceRef:
    source_id: str
    source_record_id: str = ""
    field_name: str = ""
    raw_value: str = ""
    normalized_value: str = ""
    confidence: float = 1.0
    notes: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_id", _clean(self.source_id))
        object.__setattr__(self, "source_record_id", _clean(self.source_record_id))
        object.__setattr__(self, "field_name", _clean(self.field_name))
        object.__setattr__(self, "raw_value", str(self.raw_value or "").strip())
        object.__setattr__(self, "normalized_value", str(self.normalized_value or "").strip())
        try:
            confidence = float(self.confidence)
        except (TypeError, ValueError):
            confidence = 0.0
        object.__setattr__(self, "confidence", max(0.0, min(1.0, confidence)))
        object.__setattr__(self, "notes", _clean(self.notes))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_record_id": self.source_record_id,
            "field_name": self.field_name,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "confidence": self.confidence,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class CanadianIssue:
    issue_id: str
    country: str = "Canada"
    authority: str = ""
    denomination: str = ""
    year: str = ""
    date_text: str = ""
    monarch: str = ""
    series: str = ""
    mint: str = ""
    mintmark: str = ""
    variety: str = ""
    composition: str = ""
    weight: str = ""
    diameter: str = ""
    shape: str = ""
    orientation: str = ""
    mintage: str = ""
    catalogue_numbers: Dict[str, str] = field(default_factory=dict)
    design_markers: Tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""
    source_refs: Tuple[SourceRef, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for attr in (
            "issue_id", "country", "authority", "denomination", "year", "date_text",
            "monarch", "series", "mint", "mintmark", "variety", "composition",
            "weight", "diameter", "shape", "orientation", "mintage", "notes",
        ):
            object.__setattr__(self, attr, _clean(getattr(self, attr)))
        object.__setattr__(self, "catalogue_numbers", {
            _clean(key): _clean(value)
            for key, value in dict(self.catalogue_numbers or {}).items()
            if _clean(key) and _clean(value)
        })
        object.__setattr__(self, "design_markers", _string_tuple(self.design_markers))
        object.__setattr__(self, "source_refs", tuple(
            ref if isinstance(ref, SourceRef) else SourceRef(**dict(ref))
            for ref in self.source_refs or []
        ))

    @property
    def normalized_country(self) -> str:
        return normalize_country(self.country)

    @property
    def normalized_denomination(self) -> str:
        return normalize_denomination(self.denomination)

    @property
    def normalized_year(self) -> str:
        return normalize_year(self.year)

    @property
    def normalized_variety(self) -> str:
        return normalize_variety(self.variety)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "country": self.country,
            "authority": self.authority,
            "denomination": self.denomination,
            "year": self.year,
            "date_text": self.date_text,
            "monarch": self.monarch,
            "series": self.series,
            "mint": self.mint,
            "mintmark": self.mintmark,
            "variety": self.variety,
            "composition": self.composition,
            "weight": self.weight,
            "diameter": self.diameter,
            "shape": self.shape,
            "orientation": self.orientation,
            "mintage": self.mintage,
            "catalogue_numbers": dict(sorted(self.catalogue_numbers.items())),
            "design_markers": list(self.design_markers),
            "notes": self.notes,
            "source_refs": [ref.to_dict() for ref in self.source_refs],
        }


@dataclass(frozen=True)
class ReferenceRecord:
    issue: CanadianIssue
    source: ReferenceSource
    source_record_id: str = ""
    confidence: float = 1.0
    fields_supplied: Tuple[str, ...] = field(default_factory=tuple)
    warnings: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.issue, CanadianIssue):
            object.__setattr__(self, "issue", CanadianIssue(**dict(self.issue)))
        if not isinstance(self.source, ReferenceSource):
            object.__setattr__(self, "source", ReferenceSource(**dict(self.source)))
        object.__setattr__(self, "source_record_id", _clean(self.source_record_id))
        try:
            confidence = float(self.confidence)
        except (TypeError, ValueError):
            confidence = 0.0
        object.__setattr__(self, "confidence", max(0.0, min(1.0, confidence)))
        object.__setattr__(self, "fields_supplied", _string_tuple(self.fields_supplied))
        object.__setattr__(self, "warnings", _string_tuple(self.warnings))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue": self.issue.to_dict(),
            "source": self.source.to_dict(),
            "source_record_id": self.source_record_id,
            "confidence": self.confidence,
            "fields_supplied": list(self.fields_supplied),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ReferenceQuery:
    text: str = ""
    country: str = ""
    denomination: str = ""
    year: str = ""
    authority: str = ""
    mintmark: str = ""
    variety: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "text": _clean(self.text),
            "country": _clean(self.country),
            "denomination": _clean(self.denomination),
            "year": _clean(self.year),
            "authority": _clean(self.authority),
            "mintmark": _clean(self.mintmark),
            "variety": _clean(self.variety),
        }


@dataclass(frozen=True)
class ReferenceFilters:
    country: str = ""
    denomination: str = ""
    year: str = ""
    authority: str = ""
    monarch: str = ""
    series: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "country": _clean(self.country),
            "denomination": _clean(self.denomination),
            "year": _clean(self.year),
            "authority": _clean(self.authority),
            "monarch": _clean(self.monarch),
            "series": _clean(self.series),
        }


@dataclass(frozen=True)
class ReferenceProviderCapabilities:
    provider_id: str
    source_type: ReferenceSourceType
    capabilities: Tuple[ReferenceProviderCapability, ...] = field(default_factory=tuple)
    supports_field_provenance: bool = False
    supports_conflicts: bool = False
    supports_filters: bool = False
    mutable: bool = False
    network_required: bool = False
    licence_required: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _clean(self.provider_id))
        object.__setattr__(self, "source_type", _enum_member(ReferenceSourceType, self.source_type, ReferenceSourceType.MANUAL))
        object.__setattr__(self, "capabilities", tuple(
            capability if isinstance(capability, ReferenceProviderCapability)
            else ReferenceProviderCapability(str(capability))
            for capability in self.capabilities or []
        ))

    def has(self, capability: ReferenceProviderCapability) -> bool:
        return capability in self.capabilities

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "source_type": self.source_type.value,
            "capabilities": [capability.value for capability in self.capabilities],
            "supports_field_provenance": self.supports_field_provenance,
            "supports_conflicts": self.supports_conflicts,
            "supports_filters": self.supports_filters,
            "mutable": self.mutable,
            "network_required": self.network_required,
            "licence_required": self.licence_required,
        }


@dataclass(frozen=True)
class ReferenceProviderError:
    provider_id: str
    code: str
    message: str
    severity: ReferenceSeverity = ReferenceSeverity.ERROR

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _clean(self.provider_id))
        object.__setattr__(self, "code", _clean(self.code))
        object.__setattr__(self, "message", _clean(self.message))
        object.__setattr__(self, "severity", _enum_member(ReferenceSeverity, self.severity, ReferenceSeverity.ERROR))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
        }


@dataclass(frozen=True)
class ReferenceValidationFinding:
    severity: ReferenceSeverity
    code: str
    message: str
    provider_id: str = ""
    issue_id: str = ""
    source_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "severity", _enum_member(ReferenceSeverity, self.severity, ReferenceSeverity.WARNING))
        object.__setattr__(self, "code", _clean(self.code))
        object.__setattr__(self, "message", _clean(self.message))
        object.__setattr__(self, "provider_id", _clean(self.provider_id))
        object.__setattr__(self, "issue_id", _clean(self.issue_id))
        object.__setattr__(self, "source_id", _clean(self.source_id))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "provider_id": self.provider_id,
            "issue_id": self.issue_id,
            "source_id": self.source_id,
        }


@dataclass(frozen=True)
class ReferenceValidationReport:
    provider_id: str
    total_records: int = 0
    valid_records: int = 0
    findings: Tuple[ReferenceValidationFinding, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _clean(self.provider_id))
        object.__setattr__(self, "findings", tuple(
            finding if isinstance(finding, ReferenceValidationFinding)
            else ReferenceValidationFinding(**dict(finding))
            for finding in self.findings or []
        ))

    @property
    def error_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == ReferenceSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == ReferenceSeverity.WARNING)

    @property
    def status(self) -> str:
        return "ERROR" if self.error_count else "WARNING" if self.warning_count else "OK"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "status": self.status,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class ReferenceSearchResult:
    provider_id: str
    records: Tuple[ReferenceRecord, ...] = field(default_factory=tuple)
    warnings: Tuple[str, ...] = field(default_factory=tuple)
    provider_errors: Tuple[ReferenceProviderError, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "provider_id", _clean(self.provider_id))
        object.__setattr__(self, "records", tuple(sort_reference_records(self.records)))
        object.__setattr__(self, "warnings", _string_tuple(self.warnings))
        object.__setattr__(self, "provider_errors", tuple(
            error if isinstance(error, ReferenceProviderError)
            else ReferenceProviderError(**dict(error))
            for error in self.provider_errors or []
        ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "records": [record.to_dict() for record in self.records],
            "warnings": list(self.warnings),
            "provider_errors": [error.to_dict() for error in self.provider_errors],
        }


@runtime_checkable
class ReferenceProvider(Protocol):
    def provider_id(self) -> str:
        ...

    def capabilities(self) -> ReferenceProviderCapabilities:
        ...

    def get_source_metadata(self) -> ReferenceSource:
        ...

    def validate(self) -> ReferenceValidationReport:
        ...

    def get_issue(self, issue_id: str) -> Optional[ReferenceRecord]:
        ...

    def search(self, query: ReferenceQuery) -> ReferenceSearchResult:
        ...

    def list_issues(self, filters: Optional[ReferenceFilters] = None) -> ReferenceSearchResult:
        ...


class LocalJsonReferenceProvider:
    """Read a versioned reference file without changing it or its records."""

    def __init__(self, path: str, provider_id: str = "") -> None:
        self._path = os.fspath(path)
        self._configured_provider_id = _clean(provider_id)
        self._records: Tuple[ReferenceRecord, ...] = ()
        self._source: Optional[ReferenceSource] = None
        self._validation_report: Optional[ReferenceValidationReport] = None
        self._provider_errors: Tuple[ReferenceProviderError, ...] = ()
        self._load_attempted = False
        self._loaded = False

    def provider_id(self) -> str:
        if self._configured_provider_id:
            return self._configured_provider_id
        if self._source and self._source.source_id:
            return self._source.source_id
        return "local-json-reference"

    def capabilities(self) -> ReferenceProviderCapabilities:
        return ReferenceProviderCapabilities(
            provider_id=self.provider_id(),
            source_type=ReferenceSourceType.LOCAL_JSON,
            capabilities=(
                ReferenceProviderCapability.ISSUE_LOOKUP,
                ReferenceProviderCapability.SEARCH,
                ReferenceProviderCapability.FILTERS,
                ReferenceProviderCapability.FIELD_PROVENANCE,
                ReferenceProviderCapability.VALIDATION,
            ),
            supports_field_provenance=True,
            supports_filters=True,
            network_required=False,
        )

    def get_source_metadata(self) -> ReferenceSource:
        self._ensure_loaded()
        return self._source or _fallback_source(self.provider_id(), ReferenceSourceType.LOCAL_JSON)

    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> ReferenceValidationReport:
        self._load_attempted = True
        self._loaded = False
        self._records = ()
        self._source = None
        self._provider_errors = ()
        findings: List[ReferenceValidationFinding] = []

        try:
            with open(self._path, "r", encoding="utf-8") as reference_file:
                payload = json.load(reference_file)
        except FileNotFoundError:
            return self._load_failed(
                "LOCAL_REFERENCE_FILE_MISSING",
                "Local reference file was not found.",
                findings,
            )
        except (OSError, UnicodeDecodeError) as exc:
            return self._load_failed(
                "LOCAL_REFERENCE_LOAD_FAILED",
                f"Local reference file could not be read: {exc}.",
                findings,
            )
        except json.JSONDecodeError as exc:
            return self._load_failed(
                "LOCAL_REFERENCE_JSON_MALFORMED",
                f"Local reference JSON is malformed: {exc.msg}.",
                findings,
            )

        if not isinstance(payload, dict):
            return self._load_failed(
                "LOCAL_REFERENCE_LOAD_FAILED",
                "Local reference JSON must contain an object at its root.",
                findings,
            )

        if "schema_version" not in payload:
            return self._load_failed(
                "LOCAL_REFERENCE_SCHEMA_MISSING",
                "Local reference JSON is missing schema_version.",
                findings,
            )
        if payload.get("schema_version") != REFERENCE_JSON_SCHEMA_VERSION:
            return self._load_failed(
                "LOCAL_REFERENCE_SCHEMA_UNSUPPORTED",
                "Local reference JSON uses an unsupported schema version.",
                findings,
            )
        if not isinstance(payload.get("source"), dict):
            return self._load_failed(
                "LOCAL_REFERENCE_SOURCE_MISSING",
                "Local reference JSON is missing source metadata.",
                findings,
            )
        if not isinstance(payload.get("issues"), list):
            return self._load_failed(
                "LOCAL_REFERENCE_ISSUES_MISSING",
                "Local reference JSON is missing its issues list.",
                findings,
            )

        try:
            self._source = _source_from_payload(payload["source"])
        except (TypeError, ValueError) as exc:
            return self._load_failed(
                "LOCAL_REFERENCE_SOURCE_MISSING",
                f"Local reference source metadata is invalid: {exc}.",
                findings,
            )

        if not self._configured_provider_id:
            self._configured_provider_id = _clean(payload.get("provider_id"))

        records: List[ReferenceRecord] = []
        for index, issue_payload in enumerate(payload["issues"]):
            try:
                records.append(_record_from_payload(issue_payload, self._source))
            except (TypeError, ValueError, KeyError) as exc:
                findings.append(ReferenceValidationFinding(
                    ReferenceSeverity.ERROR,
                    "LOCAL_REFERENCE_RECORD_INVALID",
                    f"Issue record {index + 1} is invalid: {exc}.",
                    provider_id=self.provider_id(),
                    source_id=self._source.source_id,
                ))

        self._records = tuple(sort_reference_records(records))
        self._validation_report = _validation_report(self.provider_id(), self._records, findings)
        self._loaded = True
        return self._validation_report

    def validate(self) -> ReferenceValidationReport:
        self._ensure_loaded()
        return self._validation_report or _validation_report(self.provider_id(), (), ())

    def get_issue(self, issue_id: str) -> Optional[ReferenceRecord]:
        if not self._ensure_loaded():
            return None
        wanted = _clean(issue_id)
        return next((record for record in self._records if record.issue.issue_id == wanted), None)

    def search(self, query: ReferenceQuery) -> ReferenceSearchResult:
        if not self._ensure_loaded():
            return _error_result(self.provider_id(), self._provider_errors)
        return ReferenceSearchResult(
            self.provider_id(),
            tuple(record for record in self._records if _record_matches_query(record, query)),
        )

    def list_issues(self, filters: Optional[ReferenceFilters] = None) -> ReferenceSearchResult:
        if not self._ensure_loaded():
            return _error_result(self.provider_id(), self._provider_errors)
        effective_filters = filters or ReferenceFilters()
        return ReferenceSearchResult(
            self.provider_id(),
            tuple(record for record in self._records if _record_matches_filters(record, effective_filters)),
        )

    def _ensure_loaded(self) -> bool:
        if not self._load_attempted:
            self.load()
        return self._loaded

    def _load_failed(
        self,
        code: str,
        message: str,
        findings: Iterable[ReferenceValidationFinding],
    ) -> ReferenceValidationReport:
        error = ReferenceProviderError(self.provider_id(), code, message)
        self._provider_errors = (error,)
        finding = ReferenceValidationFinding(
            ReferenceSeverity.ERROR,
            code,
            message,
            provider_id=self.provider_id(),
        )
        self._validation_report = _validation_report(self.provider_id(), (), tuple(findings) + (finding,))
        return self._validation_report


class ManualReferenceProvider:
    """Own user-entered reference records in memory until explicitly exported."""

    def __init__(
        self,
        records: Optional[Iterable[ReferenceRecord]] = None,
        source: Optional[ReferenceSource] = None,
        provider_id: str = "manual-reference",
    ) -> None:
        self._provider_id = _clean(provider_id) or "manual-reference"
        self._source = source or _fallback_source(self._provider_id, ReferenceSourceType.MANUAL)
        self._records: Tuple[ReferenceRecord, ...] = ()
        self._validation_report = _validation_report(self._provider_id, (), ())
        self.replace_records(records or ())

    def provider_id(self) -> str:
        return self._provider_id

    def capabilities(self) -> ReferenceProviderCapabilities:
        return ReferenceProviderCapabilities(
            provider_id=self.provider_id(),
            source_type=ReferenceSourceType.MANUAL,
            capabilities=(
                ReferenceProviderCapability.ISSUE_LOOKUP,
                ReferenceProviderCapability.SEARCH,
                ReferenceProviderCapability.FILTERS,
                ReferenceProviderCapability.FIELD_PROVENANCE,
                ReferenceProviderCapability.EXPORT,
                ReferenceProviderCapability.VALIDATION,
            ),
            supports_field_provenance=True,
            supports_filters=True,
            mutable=True,
            network_required=False,
        )

    def get_source_metadata(self) -> ReferenceSource:
        return self._source

    def validate(self) -> ReferenceValidationReport:
        return self._validation_report

    def get_issue(self, issue_id: str) -> Optional[ReferenceRecord]:
        wanted = _clean(issue_id)
        return next((record for record in self._records if record.issue.issue_id == wanted), None)

    def search(self, query: ReferenceQuery) -> ReferenceSearchResult:
        return ReferenceSearchResult(
            self.provider_id(),
            tuple(record for record in self._records if _record_matches_query(record, query)),
        )

    def list_issues(self, filters: Optional[ReferenceFilters] = None) -> ReferenceSearchResult:
        effective_filters = filters or ReferenceFilters()
        return ReferenceSearchResult(
            self.provider_id(),
            tuple(record for record in self._records if _record_matches_filters(record, effective_filters)),
        )

    def add_record(self, record: ReferenceRecord) -> ReferenceValidationReport:
        if not isinstance(record, ReferenceRecord):
            raise TypeError("record must be a ReferenceRecord")
        self._records = tuple(sort_reference_records(self._records + (record,)))
        self._validation_report = validate_records(self.provider_id(), self._records)
        return self._validation_report

    def replace_records(self, records: Iterable[ReferenceRecord]) -> ReferenceValidationReport:
        normalized_records = tuple(records or ())
        if not all(isinstance(record, ReferenceRecord) for record in normalized_records):
            raise TypeError("records must contain only ReferenceRecord values")
        self._records = tuple(sort_reference_records(normalized_records))
        self._validation_report = validate_records(self.provider_id(), self._records)
        return self._validation_report

    def export_json(self, path: str) -> bool:
        payload = {
            "schema_version": REFERENCE_JSON_SCHEMA_VERSION,
            "provider_id": self.provider_id(),
            "source": self._source.to_dict(),
            "issues": [_record_to_payload(record, self._source) for record in self._records],
        }
        try:
            with open(os.fspath(path), "w", encoding="utf-8", newline="\n") as reference_file:
                json.dump(payload, reference_file, indent=2, sort_keys=True)
                reference_file.write("\n")
        except (OSError, TypeError, ValueError):
            return False
        return True


def reference_sort_key(record: ReferenceRecord) -> Tuple[str, str, str, str, str]:
    issue = record.issue
    return (
        issue.normalized_country,
        issue.normalized_denomination,
        issue.normalized_year or normalize_date_text(issue.date_text),
        issue.normalized_variety,
        issue.issue_id,
    )


def sort_reference_records(records: Iterable[ReferenceRecord]) -> List[ReferenceRecord]:
    return sorted(list(records or []), key=reference_sort_key)


def _fallback_source(provider_id: str, source_type: ReferenceSourceType) -> ReferenceSource:
    return ReferenceSource(
        source_id=_clean(provider_id) or "reference-provider",
        source_name="Local Reference" if source_type == ReferenceSourceType.LOCAL_JSON else "Manual Reference",
        source_type=source_type,
    )


def _source_from_payload(payload: Dict[str, Any]) -> ReferenceSource:
    if not isinstance(payload, dict):
        raise TypeError("source must be an object")
    return ReferenceSource(**payload)


def _record_from_payload(payload: Dict[str, Any], default_source: ReferenceSource) -> ReferenceRecord:
    if not isinstance(payload, dict):
        raise TypeError("issue record must be an object")
    issue_data = dict(payload)
    source_record_id = issue_data.pop("source_record_id", "")
    confidence = issue_data.pop("confidence", 1.0)
    fields_supplied = issue_data.pop("fields_supplied", ())
    warnings = issue_data.pop("warnings", ())
    record_source_payload = issue_data.pop("record_source", None)
    record_source = _source_from_payload(record_source_payload) if record_source_payload is not None else default_source
    issue = CanadianIssue(**issue_data)
    return ReferenceRecord(
        issue=issue,
        source=record_source,
        source_record_id=source_record_id,
        confidence=confidence,
        fields_supplied=fields_supplied,
        warnings=warnings,
    )


def _record_to_payload(record: ReferenceRecord, default_source: ReferenceSource) -> Dict[str, Any]:
    payload = record.issue.to_dict()
    payload.update({
        "source_record_id": record.source_record_id,
        "confidence": record.confidence,
        "fields_supplied": list(record.fields_supplied),
        "warnings": list(record.warnings),
    })
    if record.source != default_source:
        payload["record_source"] = record.source.to_dict()
    return payload


def _validation_report(
    provider_id: str,
    records: Iterable[ReferenceRecord],
    extra_findings: Iterable[ReferenceValidationFinding],
) -> ReferenceValidationReport:
    normalized_records = tuple(records or ())
    record_report = validate_records(provider_id, normalized_records)
    findings = tuple(extra_findings or ()) + record_report.findings
    return ReferenceValidationReport(
        provider_id=provider_id,
        total_records=record_report.total_records,
        valid_records=record_report.valid_records,
        findings=tuple(sorted(
            findings,
            key=lambda finding: (finding.severity.value, finding.code, finding.issue_id, finding.source_id),
        )),
    )


def _error_result(
    provider_id: str,
    provider_errors: Iterable[ReferenceProviderError],
) -> ReferenceSearchResult:
    return ReferenceSearchResult(provider_id, provider_errors=tuple(provider_errors or ()))


def _record_matches_query(record: ReferenceRecord, query: ReferenceQuery) -> bool:
    if not isinstance(query, ReferenceQuery):
        return False
    issue = record.issue
    field_matches = (
        (query.country, issue.normalized_country, normalize_country),
        (query.denomination, issue.normalized_denomination, normalize_denomination),
        (query.year, issue.normalized_year, normalize_year),
        (query.authority, normalize_authority(issue.authority), normalize_authority),
        (query.mintmark, normalize_mintmark(issue.mintmark), normalize_mintmark),
        (query.variety, issue.normalized_variety, normalize_variety),
    )
    if any(value and normalizer(value) != candidate for value, candidate, normalizer in field_matches):
        return False
    tokens = tuple(token for token in normalize_text(query.text).split() if token)
    searchable = _record_search_text(record)
    return all(token in searchable for token in tokens)


def _record_matches_filters(record: ReferenceRecord, filters: ReferenceFilters) -> bool:
    if not isinstance(filters, ReferenceFilters):
        return False
    issue = record.issue
    field_matches = (
        (filters.country, issue.normalized_country, normalize_country),
        (filters.denomination, issue.normalized_denomination, normalize_denomination),
        (filters.year, issue.normalized_year, normalize_year),
        (filters.authority, normalize_authority(issue.authority), normalize_authority),
        (filters.monarch, normalize_text(issue.monarch), normalize_text),
        (filters.series, normalize_text(issue.series), normalize_text),
    )
    return not any(value and normalizer(value) != candidate for value, candidate, normalizer in field_matches)


def _record_search_text(record: ReferenceRecord) -> str:
    issue = record.issue
    values = (
        issue.issue_id,
        issue.country,
        issue.authority,
        issue.denomination,
        issue.year,
        issue.date_text,
        issue.monarch,
        issue.series,
        issue.mint,
        issue.mintmark,
        issue.variety,
        issue.composition,
        *issue.catalogue_numbers.values(),
        *issue.design_markers,
    )
    return normalize_text(" ".join(str(value) for value in values if value))


def validate_record(record: ReferenceRecord, provider_id: str = "") -> List[ReferenceValidationFinding]:
    provider = _clean(provider_id) or record.source.source_id
    findings: List[ReferenceValidationFinding] = []
    issue = record.issue
    source = record.source

    required_issue_fields = {
        "issue_id": issue.issue_id,
        "country": issue.country,
        "denomination": issue.denomination,
    }
    if not (issue.year or issue.date_text):
        findings.append(ReferenceValidationFinding(
            ReferenceSeverity.ERROR,
            "MISSING_DATE",
            "Issue must provide year or date_text.",
            provider_id=provider,
            issue_id=issue.issue_id,
            source_id=source.source_id,
        ))
    for field_name, value in required_issue_fields.items():
        if not value:
            findings.append(ReferenceValidationFinding(
                ReferenceSeverity.ERROR,
                f"MISSING_{field_name.upper()}",
                f"Issue is missing required field: {field_name}.",
                provider_id=provider,
                issue_id=issue.issue_id,
                source_id=source.source_id,
            ))

    if not source.source_id:
        findings.append(ReferenceValidationFinding(
            ReferenceSeverity.ERROR,
            "MISSING_SOURCE_ID",
            "Reference source is missing source_id.",
            provider_id=provider,
            issue_id=issue.issue_id,
            source_id=source.source_id,
        ))
    if not source.source_name:
        findings.append(ReferenceValidationFinding(
            ReferenceSeverity.ERROR,
            "MISSING_SOURCE_NAME",
            "Reference source is missing source_name.",
            provider_id=provider,
            issue_id=issue.issue_id,
            source_id=source.source_id,
        ))

    findings.extend(_validate_measurement(issue.weight, "weight", {"g", "kg", "mg"}, provider, issue, source))
    findings.extend(_validate_measurement(issue.diameter, "diameter", {"mm", "cm"}, provider, issue, source))

    normalized_catalogue_values: Dict[str, str] = {}
    for namespace, value in issue.catalogue_numbers.items():
        normalized = normalize_catalogue_id(value)
        if not normalized:
            continue
        if normalized in normalized_catalogue_values:
            findings.append(ReferenceValidationFinding(
                ReferenceSeverity.ERROR,
                "DUPLICATE_CATALOGUE_IDENTIFIER",
                f"Duplicate catalogue identifier: {value}.",
                provider_id=provider,
                issue_id=issue.issue_id,
                source_id=source.source_id,
            ))
        normalized_catalogue_values[normalized] = namespace

    if not issue.source_refs:
        findings.append(ReferenceValidationFinding(
            ReferenceSeverity.WARNING,
            "MISSING_FIELD_PROVENANCE",
            "Issue has no field-level source references.",
            provider_id=provider,
            issue_id=issue.issue_id,
            source_id=source.source_id,
        ))
    return sorted(findings, key=lambda finding: (finding.severity.value, finding.code, finding.issue_id, finding.source_id))


def validate_records(provider_id: str, records: Iterable[ReferenceRecord]) -> ReferenceValidationReport:
    normalized_records = list(records or [])
    findings: List[ReferenceValidationFinding] = []
    issue_ids: Dict[str, int] = {}
    source_ids: Dict[str, int] = {}
    valid_count = 0
    for record in normalized_records:
        issue_ids[record.issue.issue_id] = issue_ids.get(record.issue.issue_id, 0) + 1
        source_ids[record.source.source_id] = source_ids.get(record.source.source_id, 0) + 1
        record_findings = validate_record(record, provider_id)
        findings.extend(record_findings)
        if not any(finding.severity == ReferenceSeverity.ERROR for finding in record_findings):
            valid_count += 1

    for issue_id, count in issue_ids.items():
        if issue_id and count > 1:
            findings.append(ReferenceValidationFinding(
                ReferenceSeverity.ERROR,
                "DUPLICATE_ISSUE_ID",
                f"Duplicate issue_id appears {count} times.",
                provider_id=provider_id,
                issue_id=issue_id,
            ))
    for source_id, count in source_ids.items():
        if source_id and count > 1:
            findings.append(ReferenceValidationFinding(
                ReferenceSeverity.WARNING,
                "DUPLICATE_SOURCE_ID",
                f"Source_id appears across {count} records.",
                provider_id=provider_id,
                source_id=source_id,
            ))

    findings = sorted(findings, key=lambda finding: (finding.severity.value, finding.code, finding.issue_id, finding.source_id))
    return ReferenceValidationReport(provider_id, len(normalized_records), valid_count, tuple(findings))


def _validate_measurement(
    raw_value: str,
    field_name: str,
    allowed_units: set,
    provider_id: str,
    issue: CanadianIssue,
    source: ReferenceSource,
) -> List[ReferenceValidationFinding]:
    if not raw_value:
        return []
    number, unit = normalize_measurement(raw_value)
    if not unit or not re.match(r"^[+-]?\d+(?:\.\d+)?$", number):
        return [ReferenceValidationFinding(
            ReferenceSeverity.WARNING,
            f"INVALID_{field_name.upper()}_FORMAT",
            f"{field_name} should include a numeric value and unit.",
            provider_id=provider_id,
            issue_id=issue.issue_id,
            source_id=source.source_id,
        )]
    if unit not in allowed_units:
        return [ReferenceValidationFinding(
            ReferenceSeverity.ERROR,
            f"INVALID_{field_name.upper()}_UNIT",
            f"{field_name} uses unsupported unit: {unit}.",
            provider_id=provider_id,
            issue_id=issue.issue_id,
            source_id=source.source_id,
        )]
    return []
