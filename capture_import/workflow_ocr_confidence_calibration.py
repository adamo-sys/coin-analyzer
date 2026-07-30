"""Deterministic, transient calibration of raw OCR candidate confidence.

Calibration here means an explicit transformation from the existing provider
confidence scale into integer basis points under a named immutable profile.  It
does not claim statistical correctness, rank providers or values, apply a
threshold, alter ensemble findings, or authorize downstream decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
import re

from .workflow_ocr_models import (
    ALLOWED_OCR_FIELDS as _ALLOWED_OCR_FIELDS,
    OCRFieldCandidate as _OCRFieldCandidate,
    OCRMetadataReport as _OCRMetadataReport,
)
from .workflow_ocr_provider_contracts import (
    OCRProviderCapabilities as _OCRProviderCapabilities,
)
from .workflow_ocr_provider_execution import (
    OCRProviderExecutionBatch as _OCRProviderExecutionBatch,
    OCRProviderExecutionStatus as _OCRProviderExecutionStatus,
)


__all__ = [
    "OCRConfidenceCalibrationContractError",
    "InvalidOCRConfidenceCalibrationContextError",
    "OCRConfidenceCalibrationError",
    "OCRConfidenceCalibrationProfileNotFoundError",
    "OCRConfidenceCalibrationCoverageError",
    "OCRConfidenceCalibrationInputError",
    "OCRConfidenceCalibrationPoint",
    "OCRConfidenceCalibrationProfile",
    "OCRConfidenceCalibrationRegistry",
    "OCRCalibratedCandidateConfidence",
    "OCRCalibratedExecutionConfidence",
    "resolve_ocr_confidence_calibration_profile",
    "calibrate_ocr_confidence_value",
    "calibrate_ocr_execution_confidence",
]


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_MIN_BPS = 0
_MAX_BPS = 10_000


class OCRConfidenceCalibrationContractError(ValueError):
    """A Unit 1D calibration value contract is malformed."""


class InvalidOCRConfidenceCalibrationContextError(
    OCRConfidenceCalibrationContractError
):
    """Profile, registry, evidence, or aggregate invariants were violated."""


class OCRConfidenceCalibrationError(Exception):
    """Base for bounded operational calibration failures."""

    __slots__ = ("_locked",)

    def __init__(self, message: str) -> None:
        if type(self) is OCRConfidenceCalibrationError:
            raise TypeError(
                "OCRConfidenceCalibrationError cannot be constructed directly."
            )
        object.__setattr__(self, "_locked", False)
        super().__init__(message)
        object.__setattr__(self, "_locked", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_locked", False):
            raise AttributeError("OCR confidence calibration errors are immutable.")
        object.__setattr__(self, name, value)


class OCRConfidenceCalibrationProfileNotFoundError(
    OCRConfidenceCalibrationError
):
    """No exact provider/field profile or provider fallback exists."""

    __slots__ = ("_provider_id", "_field_name")

    def __init__(self, provider_id: str, field_name: str) -> None:
        provider = _validate_identifier(provider_id, "provider_id")
        field = _validate_field_name(field_name)
        object.__setattr__(self, "_provider_id", provider)
        object.__setattr__(self, "_field_name", field)
        super().__init__(
            f"No OCR confidence calibration profile covers "
            f"{provider!r}/{field!r}."
        )

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def field_name(self) -> str:
        return self._field_name


class OCRConfidenceCalibrationCoverageError(OCRConfidenceCalibrationError):
    """A complete execution batch cannot be calibrated by the registry."""

    __slots__ = ("_provider_id", "_field_name")

    def __init__(self, provider_id: str, field_name: str) -> None:
        provider = _validate_identifier(provider_id, "provider_id")
        field = _validate_field_name(field_name)
        object.__setattr__(self, "_provider_id", provider)
        object.__setattr__(self, "_field_name", field)
        super().__init__(
            f"OCR confidence calibration coverage is incomplete for "
            f"{provider!r}/{field!r}."
        )

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def field_name(self) -> str:
        return self._field_name


class OCRConfidenceCalibrationInputError(OCRConfidenceCalibrationError):
    """A raw confidence value cannot be applied to its selected profile."""

    __slots__ = ("_provider_id", "_field_name", "_profile_id")

    def __init__(
        self,
        provider_id: str,
        field_name: str | None,
        profile_id: str,
    ) -> None:
        provider = _validate_identifier(provider_id, "provider_id")
        field = (
            None
            if field_name is None
            else _validate_field_name(field_name)
        )
        profile = _validate_identifier(profile_id, "profile_id")
        object.__setattr__(self, "_provider_id", provider)
        object.__setattr__(self, "_field_name", field)
        object.__setattr__(self, "_profile_id", profile)
        scope = "*" if field is None else field
        super().__init__(
            f"Raw OCR confidence is invalid for calibration profile "
            f"{profile!r} ({provider!r}/{scope!r})."
        )

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def field_name(self) -> str | None:
        return self._field_name

    @property
    def profile_id(self) -> str:
        return self._profile_id


@dataclass(frozen=True, slots=True)
class OCRConfidenceCalibrationPoint:
    """One exact control point on a 0..10,000 basis-point input scale."""

    raw_confidence_bps: int
    calibrated_confidence_bps: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _validate_bps(self.raw_confidence_bps, "raw_confidence_bps")
        _validate_bps(
            self.calibrated_confidence_bps,
            "calibrated_confidence_bps",
        )


@dataclass(frozen=True, slots=True)
class OCRConfidenceCalibrationProfile:
    """Named monotonic piecewise-linear mapping for one exact provider scope."""

    profile_id: str
    provider_id: str
    field_name: str | None
    points: tuple[OCRConfidenceCalibrationPoint, ...]

    def __post_init__(self) -> None:
        self.validate()

    @property
    def scope_key(self) -> tuple[str, str | None]:
        return (self.provider_id, self.field_name)

    def validate(self) -> None:
        _validate_identifier(self.profile_id, "profile_id")
        _validate_identifier(self.provider_id, "provider_id")
        if self.field_name is not None:
            _validate_field_name(self.field_name)
        if not isinstance(self.points, tuple) or len(self.points) < 2:
            raise InvalidOCRConfidenceCalibrationContextError(
                "points must be an immutable tuple with at least two values."
            )
        for point in self.points:
            if not isinstance(point, OCRConfidenceCalibrationPoint):
                raise InvalidOCRConfidenceCalibrationContextError(
                    "points must contain OCRConfidenceCalibrationPoint values."
                )
            point.validate()
        raw_values = tuple(point.raw_confidence_bps for point in self.points)
        calibrated_values = tuple(
            point.calibrated_confidence_bps for point in self.points
        )
        if raw_values[0] != _MIN_BPS or raw_values[-1] != _MAX_BPS:
            raise InvalidOCRConfidenceCalibrationContextError(
                "profile points must cover raw confidence from 0 through 10,000."
            )
        if any(
            right <= left
            for left, right in zip(raw_values, raw_values[1:])
        ):
            raise InvalidOCRConfidenceCalibrationContextError(
                "profile raw confidence points must be strictly increasing."
            )
        if any(
            right < left
            for left, right in zip(calibrated_values, calibrated_values[1:])
        ):
            raise InvalidOCRConfidenceCalibrationContextError(
                "profile calibrated confidence points must be nondecreasing."
            )


@dataclass(frozen=True, slots=True)
class OCRConfidenceCalibrationRegistry:
    """Immutable canonical set of exact provider calibration profiles."""

    profiles: tuple[OCRConfidenceCalibrationProfile, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.profiles, tuple) or not self.profiles:
            raise InvalidOCRConfidenceCalibrationContextError(
                "profiles must be a nonempty immutable tuple."
            )
        for profile in self.profiles:
            if not isinstance(profile, OCRConfidenceCalibrationProfile):
                raise InvalidOCRConfidenceCalibrationContextError(
                    "profiles must contain OCRConfidenceCalibrationProfile values."
                )
            profile.validate()
        profile_ids = tuple(profile.profile_id for profile in self.profiles)
        scopes = tuple(profile.scope_key for profile in self.profiles)
        if len(set(profile_ids)) != len(profile_ids):
            raise InvalidOCRConfidenceCalibrationContextError(
                "profiles must not contain duplicate profile IDs."
            )
        if len(set(scopes)) != len(scopes):
            raise InvalidOCRConfidenceCalibrationContextError(
                "profiles must not contain duplicate provider/field scopes."
            )
        if self.profiles != tuple(
            sorted(self.profiles, key=_profile_order_key)
        ):
            raise InvalidOCRConfidenceCalibrationContextError(
                "profiles must use canonical provider and field order."
            )


@dataclass(frozen=True, slots=True)
class OCRCalibratedCandidateConfidence:
    """Calibrated score retaining exact capability, report, candidate, and profile."""

    provider: _OCRProviderCapabilities
    report: _OCRMetadataReport
    candidate: _OCRFieldCandidate
    profile: OCRConfidenceCalibrationProfile
    raw_confidence: float
    calibrated_confidence_bps: int

    def __post_init__(self) -> None:
        self.validate()

    @property
    def provider_id(self) -> str:
        return self.provider.provider_id

    @property
    def field_name(self) -> str:
        return self.candidate.field_name

    @property
    def profile_id(self) -> str:
        return self.profile.profile_id

    def validate(self) -> None:
        _validate_provider(self.provider)
        _validate_report(self.report)
        _validate_candidate(self.candidate)
        if not any(item is self.candidate for item in self.report.candidates):
            raise InvalidOCRConfidenceCalibrationContextError(
                "candidate must retain exact identity from report."
            )
        if self.candidate.provider_id != self.provider.provider_id:
            raise InvalidOCRConfidenceCalibrationContextError(
                "candidate provider must match capability identity."
            )
        if not isinstance(self.profile, OCRConfidenceCalibrationProfile):
            raise InvalidOCRConfidenceCalibrationContextError(
                "profile must be an OCRConfidenceCalibrationProfile."
            )
        self.profile.validate()
        if (
            self.profile.provider_id != self.provider.provider_id
            or (
                self.profile.field_name is not None
                and self.profile.field_name != self.candidate.field_name
            )
        ):
            raise InvalidOCRConfidenceCalibrationContextError(
                "profile scope must match candidate provider and field."
            )
        if (
            type(self.raw_confidence) is not type(self.candidate.confidence_score)
            or self.raw_confidence != self.candidate.confidence_score
        ):
            raise InvalidOCRConfidenceCalibrationContextError(
                "raw_confidence must exactly retain candidate confidence."
            )
        _validate_bps(
            self.calibrated_confidence_bps,
            "calibrated_confidence_bps",
        )
        try:
            expected = calibrate_ocr_confidence_value(
                self.raw_confidence,
                self.profile,
            )
        except OCRConfidenceCalibrationError as error:
            raise InvalidOCRConfidenceCalibrationContextError(
                "raw confidence cannot be calibrated by profile."
            ) from error
        if self.calibrated_confidence_bps != expected:
            raise InvalidOCRConfidenceCalibrationContextError(
                "calibrated_confidence_bps does not match profile calculation."
            )


@dataclass(frozen=True, slots=True)
class OCRCalibratedExecutionConfidence:
    """Complete calibrated candidate evidence for one exact execution batch."""

    batch: _OCRProviderExecutionBatch
    registry: OCRConfidenceCalibrationRegistry
    candidates: tuple[OCRCalibratedCandidateConfidence, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _validate_batch(self.batch)
        if not isinstance(self.registry, OCRConfidenceCalibrationRegistry):
            raise InvalidOCRConfidenceCalibrationContextError(
                "registry must be an OCRConfidenceCalibrationRegistry."
            )
        self.registry.validate()
        if not isinstance(self.candidates, tuple):
            raise InvalidOCRConfidenceCalibrationContextError(
                "candidates must be an immutable tuple."
            )
        expected = _expected_calibrated_candidates(self.batch, self.registry)
        if len(self.candidates) != len(expected):
            raise InvalidOCRConfidenceCalibrationContextError(
                "candidates must cover every successful report candidate."
            )
        for actual, wanted in zip(self.candidates, expected, strict=True):
            if not isinstance(actual, OCRCalibratedCandidateConfidence):
                raise InvalidOCRConfidenceCalibrationContextError(
                    "candidates must contain OCRCalibratedCandidateConfidence values."
                )
            actual.validate()
            if not _calibrated_candidate_matches_identity(actual, wanted):
                raise InvalidOCRConfidenceCalibrationContextError(
                    "calibrated candidate does not match batch and registry."
                )


def resolve_ocr_confidence_calibration_profile(
    registry: OCRConfidenceCalibrationRegistry,
    provider_id: str,
    field_name: str,
) -> OCRConfidenceCalibrationProfile:
    """Resolve an exact field profile, then its exact provider fallback."""

    if not isinstance(registry, OCRConfidenceCalibrationRegistry):
        raise InvalidOCRConfidenceCalibrationContextError(
            "registry must be an OCRConfidenceCalibrationRegistry."
        )
    registry.validate()
    provider = _validate_identifier(provider_id, "provider_id")
    field = _validate_field_name(field_name)
    for profile in registry.profiles:
        if (
            profile.provider_id == provider
            and profile.field_name == field
        ):
            return profile
    for profile in registry.profiles:
        if (
            profile.provider_id == provider
            and profile.field_name is None
        ):
            return profile
    raise OCRConfidenceCalibrationProfileNotFoundError(provider, field)


def calibrate_ocr_confidence_value(
    raw_confidence: object,
    profile: OCRConfidenceCalibrationProfile,
) -> int:
    """Map raw 0..100 confidence to basis points using integer interpolation.

    Raw confidence is first converted to source basis points with Decimal text
    conversion and ROUND_HALF_UP.  Piecewise interpolation also rounds half up.
    No value is clamped.
    """

    if not isinstance(profile, OCRConfidenceCalibrationProfile):
        raise InvalidOCRConfidenceCalibrationContextError(
            "profile must be an OCRConfidenceCalibrationProfile."
        )
    profile.validate()
    raw_bps = _raw_confidence_to_bps(raw_confidence, profile)
    for left, right in zip(profile.points, profile.points[1:]):
        if raw_bps > right.raw_confidence_bps:
            continue
        if raw_bps == left.raw_confidence_bps:
            return left.calibrated_confidence_bps
        if raw_bps == right.raw_confidence_bps:
            return right.calibrated_confidence_bps
        raw_delta = raw_bps - left.raw_confidence_bps
        raw_width = right.raw_confidence_bps - left.raw_confidence_bps
        calibrated_delta = (
            right.calibrated_confidence_bps
            - left.calibrated_confidence_bps
        )
        increment = _divide_half_up(raw_delta * calibrated_delta, raw_width)
        result = left.calibrated_confidence_bps + increment
        return _validate_bps(result, "calibrated result")
    raise OCRConfidenceCalibrationInputError(
        profile.provider_id,
        profile.field_name,
        profile.profile_id,
    )


def calibrate_ocr_execution_confidence(
    batch: _OCRProviderExecutionBatch,
    registry: OCRConfidenceCalibrationRegistry,
) -> OCRCalibratedExecutionConfidence:
    """Calibrate every successful candidate atomically in evidence order."""

    _validate_batch(batch)
    if not isinstance(registry, OCRConfidenceCalibrationRegistry):
        raise InvalidOCRConfidenceCalibrationContextError(
            "registry must be an OCRConfidenceCalibrationRegistry."
        )
    registry.validate()
    plans = _calibration_plans(batch, registry)
    candidates = tuple(
        OCRCalibratedCandidateConfidence(
            provider=provider,
            report=report,
            candidate=candidate,
            profile=profile,
            raw_confidence=candidate.confidence_score,
            calibrated_confidence_bps=calibrate_ocr_confidence_value(
                candidate.confidence_score,
                profile,
            ),
        )
        for provider, report, candidate, profile in plans
    )
    return OCRCalibratedExecutionConfidence(
        batch=batch,
        registry=registry,
        candidates=candidates,
    )


def _calibration_plans(
    batch: _OCRProviderExecutionBatch,
    registry: OCRConfidenceCalibrationRegistry,
) -> tuple[
    tuple[
        _OCRProviderCapabilities,
        _OCRMetadataReport,
        _OCRFieldCandidate,
        OCRConfidenceCalibrationProfile,
    ],
    ...,
]:
    plans: list[
        tuple[
            _OCRProviderCapabilities,
            _OCRMetadataReport,
            _OCRFieldCandidate,
            OCRConfidenceCalibrationProfile,
        ]
    ] = []
    seen_candidates: set[int] = set()
    for outcome in batch.outcomes:
        if outcome.status is _OCRProviderExecutionStatus.FAILED:
            continue
        report = outcome.report
        for candidate in report.candidates:
            identity = id(candidate)
            if identity in seen_candidates:
                raise InvalidOCRConfidenceCalibrationContextError(
                    "successful candidates must have unique object identity."
                )
            seen_candidates.add(identity)
            try:
                profile = resolve_ocr_confidence_calibration_profile(
                    registry,
                    outcome.provider_id,
                    candidate.field_name,
                )
            except OCRConfidenceCalibrationProfileNotFoundError as error:
                raise OCRConfidenceCalibrationCoverageError(
                    outcome.provider_id,
                    candidate.field_name,
                ) from error
            _raw_confidence_to_bps(candidate.confidence_score, profile)
            plans.append(
                (
                    outcome.capabilities,
                    report,
                    candidate,
                    profile,
                )
            )
    return tuple(plans)


def _expected_calibrated_candidates(
    batch: _OCRProviderExecutionBatch,
    registry: OCRConfidenceCalibrationRegistry,
) -> tuple[OCRCalibratedCandidateConfidence, ...]:
    try:
        plans = _calibration_plans(batch, registry)
    except OCRConfidenceCalibrationError as error:
        raise InvalidOCRConfidenceCalibrationContextError(
            "registry does not completely calibrate the execution batch."
        ) from error
    return tuple(
        OCRCalibratedCandidateConfidence(
            provider=provider,
            report=report,
            candidate=candidate,
            profile=profile,
            raw_confidence=candidate.confidence_score,
            calibrated_confidence_bps=calibrate_ocr_confidence_value(
                candidate.confidence_score,
                profile,
            ),
        )
        for provider, report, candidate, profile in plans
    )


def _raw_confidence_to_bps(
    raw_confidence: object,
    profile: OCRConfidenceCalibrationProfile,
) -> int:
    if (
        isinstance(raw_confidence, bool)
        or not isinstance(raw_confidence, (int, float))
    ):
        raise OCRConfidenceCalibrationInputError(
            profile.provider_id,
            profile.field_name,
            profile.profile_id,
        )
    numeric = float(raw_confidence)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 100.0:
        raise OCRConfidenceCalibrationInputError(
            profile.provider_id,
            profile.field_name,
            profile.profile_id,
        )
    try:
        decimal_value = Decimal(str(raw_confidence))
        raw_bps = int(
            (decimal_value * Decimal(100)).quantize(
                Decimal(1),
                rounding=ROUND_HALF_UP,
            )
        )
    except (InvalidOperation, ValueError, OverflowError) as error:
        raise OCRConfidenceCalibrationInputError(
            profile.provider_id,
            profile.field_name,
            profile.profile_id,
        ) from error
    if not _MIN_BPS <= raw_bps <= _MAX_BPS:
        raise OCRConfidenceCalibrationInputError(
            profile.provider_id,
            profile.field_name,
            profile.profile_id,
        )
    return raw_bps


def _profile_order_key(
    profile: OCRConfidenceCalibrationProfile,
) -> tuple[str, bool, str]:
    return (
        profile.provider_id,
        profile.field_name is None,
        "" if profile.field_name is None else profile.field_name,
    )


def _calibrated_candidate_matches_identity(
    actual: OCRCalibratedCandidateConfidence,
    expected: OCRCalibratedCandidateConfidence,
) -> bool:
    return (
        actual.provider is expected.provider
        and actual.report is expected.report
        and actual.candidate is expected.candidate
        and actual.profile is expected.profile
        and type(actual.raw_confidence) is type(expected.raw_confidence)
        and actual.raw_confidence == expected.raw_confidence
        and actual.calibrated_confidence_bps
        == expected.calibrated_confidence_bps
    )


def _validate_batch(value: object) -> _OCRProviderExecutionBatch:
    if not isinstance(value, _OCRProviderExecutionBatch):
        raise InvalidOCRConfidenceCalibrationContextError(
            "batch must be an OCRProviderExecutionBatch."
        )
    try:
        value.validate()
    except Exception as error:
        raise InvalidOCRConfidenceCalibrationContextError(
            "batch violates OCRProviderExecutionBatch."
        ) from error
    return value


def _validate_provider(value: object) -> _OCRProviderCapabilities:
    if not isinstance(value, _OCRProviderCapabilities):
        raise InvalidOCRConfidenceCalibrationContextError(
            "provider must be OCRProviderCapabilities."
        )
    try:
        value.validate()
    except Exception as error:
        raise InvalidOCRConfidenceCalibrationContextError(
            "provider violates OCRProviderCapabilities."
        ) from error
    return value


def _validate_report(value: object) -> _OCRMetadataReport:
    if not isinstance(value, _OCRMetadataReport):
        raise InvalidOCRConfidenceCalibrationContextError(
            "report must be an OCRMetadataReport."
        )
    try:
        value.validate()
    except Exception as error:
        raise InvalidOCRConfidenceCalibrationContextError(
            "report violates OCRMetadataReport."
        ) from error
    return value


def _validate_candidate(value: object) -> _OCRFieldCandidate:
    if not isinstance(value, _OCRFieldCandidate):
        raise InvalidOCRConfidenceCalibrationContextError(
            "candidate must be an OCRFieldCandidate."
        )
    try:
        value.validate()
    except Exception as error:
        raise InvalidOCRConfidenceCalibrationContextError(
            "candidate violates OCRFieldCandidate."
        ) from error
    return value


def _validate_identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise InvalidOCRConfidenceCalibrationContextError(
            f"{name} must use the bounded lowercase identifier grammar."
        )
    return value


def _validate_field_name(value: object) -> str:
    if not isinstance(value, str) or value not in _ALLOWED_OCR_FIELDS:
        raise InvalidOCRConfidenceCalibrationContextError(
            "field_name must be a canonical OCR field."
        )
    return value


def _validate_bps(value: object, name: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not _MIN_BPS <= value <= _MAX_BPS
    ):
        raise InvalidOCRConfidenceCalibrationContextError(
            f"{name} must be an integer from 0 through 10,000."
        )
    return value


def _divide_half_up(numerator: int, denominator: int) -> int:
    if numerator < 0 or denominator <= 0:
        raise InvalidOCRConfidenceCalibrationContextError(
            "interpolation requires nonnegative values and positive width."
        )
    return (2 * numerator + denominator) // (2 * denominator)
