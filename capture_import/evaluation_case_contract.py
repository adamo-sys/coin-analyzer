"""Provider-independent evaluation case metadata shared by benchmark paths.

The contract does not load images, execute providers, score results, or replace
the OCR and visual benchmark manifests.  Those harnesses project their existing
validated cases into this common, privacy-explicit representation when a
cross-provider comparison needs it.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path, PurePosixPath
import re
from typing import Iterable, Mapping


SCHEMA = "coin-analyzer-evaluation-cases"
SCHEMA_VERSION = "1"
PRIVACY_CLASSIFICATIONS = frozenset(
    {"public_reference", "synthetic", "private_local", "uncertain_local_only"}
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvaluationCaseContractError(ValueError):
    """The common evaluation contract is unsafe or malformed."""


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationCaseContractError(f"{name} must be a non-empty string.")
    return value.strip()


def _identifier(value: object, name: str) -> str:
    text = _text(value, name)
    if _IDENTIFIER.fullmatch(text) is None:
        raise EvaluationCaseContractError(f"{name} is not a safe identifier.")
    return text


def _relative_reference(value: object, name: str) -> str:
    text = _text(value, name)
    if "\\" in text:
        raise EvaluationCaseContractError(f"{name} must use POSIX separators.")
    reference = PurePosixPath(text)
    if (
        not reference.parts
        or reference.is_absolute()
        or ".." in reference.parts
        or ":" in reference.parts[0]
    ):
        raise EvaluationCaseContractError(f"{name} must be a sanitized relative path.")
    return reference.as_posix()


def _source_reference(value: object, name: str) -> str:
    text = _text(value, name)
    lowered = text.casefold()
    if (
        "\\" in text
        or text.startswith("/")
        or re.match(r"^[A-Za-z]:", text)
        or lowered.startswith("file:")
    ):
        raise EvaluationCaseContractError(f"{name} must not contain a local path.")
    return text


def _optional_sha256(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    digest = _text(value, name)
    if _SHA256.fullmatch(digest) is None:
        raise EvaluationCaseContractError(f"{name} must be lowercase SHA-256.")
    return digest


def _expected_value(value: object, name: str) -> str | int | float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise EvaluationCaseContractError(f"{name} must be text or a finite number.")
    if isinstance(value, str):
        return _text(value, name)
    if isinstance(value, float) and not math.isfinite(value):
        raise EvaluationCaseContractError(f"{name} must be finite.")
    return value


@dataclass(frozen=True, slots=True)
class EvaluationInput:
    role: str
    reference: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _identifier(self.role, "input.role"))
        object.__setattr__(
            self,
            "reference",
            _relative_reference(self.reference, "input.reference"),
        )


@dataclass(frozen=True, slots=True)
class ExpectedFinding:
    field: str
    value: str | int | float

    def __post_init__(self) -> None:
        object.__setattr__(self, "field", _identifier(self.field, "finding.field"))
        object.__setattr__(
            self,
            "value",
            _expected_value(self.value, f"finding.{self.field}"),
        )


@dataclass(frozen=True, slots=True)
class EvaluationProvenance:
    role: str
    source_reference: str
    license: str
    author: str
    label_method: str
    source_sha256: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", _identifier(self.role, "provenance.role"))
        for name in ("source_reference", "license", "author", "label_method"):
            object.__setattr__(
                self,
                name,
                (
                    _source_reference(getattr(self, name), f"provenance.{name}")
                    if name == "source_reference"
                    else _text(getattr(self, name), f"provenance.{name}")
                ),
            )
        object.__setattr__(
            self,
            "source_sha256",
            _optional_sha256(self.source_sha256, "provenance.source_sha256"),
        )


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    specimen_id: str | None
    inputs: tuple[EvaluationInput, ...]
    expected_findings: tuple[ExpectedFinding, ...]
    allowed_abstention: bool
    provenance: tuple[EvaluationProvenance, ...]
    privacy_classification: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _identifier(self.case_id, "case_id"))
        if self.specimen_id is not None:
            object.__setattr__(
                self,
                "specimen_id",
                _identifier(self.specimen_id, "specimen_id"),
            )
        if not isinstance(self.allowed_abstention, bool):
            raise EvaluationCaseContractError("allowed_abstention must be boolean.")
        if self.privacy_classification not in PRIVACY_CLASSIFICATIONS:
            raise EvaluationCaseContractError("privacy_classification is unsupported.")
        self._validate_ordered_unique(self.inputs, "role", "inputs")
        self._validate_ordered_unique(
            self.expected_findings, "field", "expected_findings"
        )
        self._validate_ordered_unique(self.provenance, "role", "provenance")

    @staticmethod
    def _validate_ordered_unique(values: tuple[object, ...], attribute: str, name: str) -> None:
        if not isinstance(values, tuple) or not values:
            raise EvaluationCaseContractError(f"{name} must be a non-empty tuple.")
        keys = tuple(getattr(value, attribute) for value in values)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise EvaluationCaseContractError(
                f"{name} must be unique and sorted by {attribute}."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            **({"specimen_id": self.specimen_id} if self.specimen_id else {}),
            "inputs": [
                {
                    "role": item.role,
                    "reference": item.reference,
                }
                for item in self.inputs
            ],
            "expected_findings": [
                {"field": item.field, "value": item.value}
                for item in self.expected_findings
            ],
            "allowed_abstention": self.allowed_abstention,
            "provenance": [
                {
                    "role": item.role,
                    "source_reference": item.source_reference,
                    "license": item.license,
                    "author": item.author,
                    "label_method": item.label_method,
                    **(
                        {"source_sha256": item.source_sha256}
                        if item.source_sha256
                        else {}
                    ),
                }
                for item in self.provenance
            ],
            "privacy_classification": self.privacy_classification,
        }


@dataclass(frozen=True, slots=True)
class EvaluationCaseManifest:
    cases: tuple[EvaluationCase, ...]
    schema: str = SCHEMA
    version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema != SCHEMA or self.version != SCHEMA_VERSION:
            raise EvaluationCaseContractError("evaluation manifest schema/version is unsupported.")
        if not isinstance(self.cases, tuple) or not self.cases:
            raise EvaluationCaseContractError("cases must be a non-empty tuple.")
        case_ids = tuple(case.case_id for case in self.cases)
        if case_ids != tuple(sorted(case_ids)) or len(case_ids) != len(set(case_ids)):
            raise EvaluationCaseContractError("cases must have unique, sorted case IDs.")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "version": self.version,
            "cases": [case.to_dict() for case in self.cases],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), allow_nan=False, sort_keys=True, separators=(",", ":")
        )


def canonical_manifest(cases: Iterable[EvaluationCase]) -> EvaluationCaseManifest:
    return EvaluationCaseManifest(cases=tuple(sorted(cases, key=lambda case: case.case_id)))


def parse_evaluation_case_manifest(payload: object) -> EvaluationCaseManifest:
    if not isinstance(payload, Mapping):
        raise EvaluationCaseContractError("manifest must be an object.")
    if set(payload) != {"schema", "version", "cases"}:
        raise EvaluationCaseContractError("manifest fields do not match the schema.")
    if payload["schema"] != SCHEMA or payload["version"] != SCHEMA_VERSION:
        raise EvaluationCaseContractError("evaluation manifest schema/version is unsupported.")
    raw_cases = payload["cases"]
    if not isinstance(raw_cases, list):
        raise EvaluationCaseContractError("cases must be an array.")
    return canonical_manifest(_parse_case(item, index) for index, item in enumerate(raw_cases))


def load_evaluation_case_manifest(path: str | Path) -> EvaluationCaseManifest:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvaluationCaseContractError(f"cannot read evaluation manifest: {error}") from error
    return parse_evaluation_case_manifest(payload)


def _parse_case(payload: object, index: int) -> EvaluationCase:
    if not isinstance(payload, Mapping):
        raise EvaluationCaseContractError(f"cases[{index}] must be an object.")
    required = {
        "case_id",
        "inputs",
        "expected_findings",
        "allowed_abstention",
        "provenance",
        "privacy_classification",
    }
    if not required.issubset(payload) or set(payload) - required - {"specimen_id"}:
        raise EvaluationCaseContractError(f"cases[{index}] fields do not match the schema.")
    inputs = payload["inputs"]
    findings = payload["expected_findings"]
    provenance = payload["provenance"]
    if not all(isinstance(value, list) for value in (inputs, findings, provenance)):
        raise EvaluationCaseContractError(f"cases[{index}] collections must be arrays.")
    if any(not isinstance(item, Mapping) for values in (inputs, findings, provenance) for item in values):
        raise EvaluationCaseContractError(f"cases[{index}] collection entries must be objects.")
    for item in inputs:
        if set(item) != {"role", "reference"}:
            raise EvaluationCaseContractError(f"cases[{index}].inputs fields are unsupported.")
    if any(set(item) != {"field", "value"} for item in findings):
        raise EvaluationCaseContractError(f"cases[{index}].expected_findings fields are unsupported.")
    provenance_fields = {"role", "source_reference", "license", "author", "label_method"}
    if any(set(item) not in (provenance_fields, provenance_fields | {"source_sha256"}) for item in provenance):
        raise EvaluationCaseContractError(f"cases[{index}].provenance fields are unsupported.")
    return EvaluationCase(
        case_id=payload["case_id"],
        specimen_id=payload.get("specimen_id"),
        inputs=tuple(
            sorted(
                (
                    EvaluationInput(
                        role=item["role"],
                        reference=item["reference"],
                    )
                    for item in inputs
                ),
                key=lambda item: item.role,
            )
        ),
        expected_findings=tuple(
            sorted(
                (
                    ExpectedFinding(field=item["field"], value=item["value"])
                    for item in findings
                ),
                key=lambda item: item.field,
            )
        ),
        allowed_abstention=payload["allowed_abstention"],
        provenance=tuple(
            sorted(
                (
                    EvaluationProvenance(
                        role=item["role"],
                        source_reference=item["source_reference"],
                        license=item["license"],
                        author=item["author"],
                        label_method=item["label_method"],
                        source_sha256=item.get("source_sha256"),
                    )
                    for item in provenance
                ),
                key=lambda item: item.role,
            )
        ),
        privacy_classification=payload["privacy_classification"],
    )
