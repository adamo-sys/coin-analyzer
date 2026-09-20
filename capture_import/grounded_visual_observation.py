"""Provider-neutral contract for grounded, non-identity visual observations."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol, runtime_checkable


GROUNDED_VISUAL_OBSERVATION_SCAN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_GROUNDED_VISUAL_OBSERVATION_ROLES = {"obverse", "reverse"}
_GROUNDED_VISUAL_OBSERVATION_MEDIA_TYPES = {"image/jpeg", "image/png"}
_MAX_OBSERVATION_ITEMS = 8


class GroundedVisualObservationContractError(ValueError):
    """A grounded visual observation request or result violates the contract."""


@dataclass(frozen=True, slots=True)
class GroundedVisualObservationImage:
    """Exactly one coin-side image supplied to an observation provider."""

    role: str
    media_type: str
    data: bytes

    def __post_init__(self) -> None:
        if self.role not in _GROUNDED_VISUAL_OBSERVATION_ROLES:
            raise GroundedVisualObservationContractError(
                "image role must be obverse or reverse."
            )
        if self.media_type not in _GROUNDED_VISUAL_OBSERVATION_MEDIA_TYPES:
            raise GroundedVisualObservationContractError(
                "image media type must be JPEG or PNG."
            )
        if not isinstance(self.data, bytes) or not self.data:
            raise GroundedVisualObservationContractError(
                "image data must be non-empty bytes."
            )


@dataclass(frozen=True, slots=True)
class GroundedVisualObservationRequest:
    """A request for observation of one side only, without identity inference."""

    scan_id: str
    image: GroundedVisualObservationImage

    def __post_init__(self) -> None:
        if (
            not isinstance(self.scan_id, str)
            or GROUNDED_VISUAL_OBSERVATION_SCAN_ID_PATTERN.fullmatch(self.scan_id)
            is None
        ):
            raise GroundedVisualObservationContractError(
                "scan_id must contain only letters, numbers, underscores, or "
                "hyphens and be at most 64 characters."
            )
        if not isinstance(self.image, GroundedVisualObservationImage):
            raise GroundedVisualObservationContractError(
                "image must be GroundedVisualObservationImage."
            )


@dataclass(frozen=True, slots=True)
class GroundedVisualObservation:
    """Pixel-grounded evidence from one coin side; never an identity decision."""

    role: str
    visible_text: tuple[str, ...] = ()
    script: str | None = None
    portrait: str | None = None
    motifs: tuple[str, ...] = ()
    construction: str | None = None
    shape: str | None = None
    date_like: str | None = None
    denomination_mark: str | None = None

    def __post_init__(self) -> None:
        if self.role not in _GROUNDED_VISUAL_OBSERVATION_ROLES:
            raise GroundedVisualObservationContractError(
                "observation role must be obverse or reverse."
            )
        _validate_string_tuple(
            self.visible_text, "visible_text", maximum_items=_MAX_OBSERVATION_ITEMS
        )
        _validate_string_tuple(
            self.motifs, "motifs", maximum_items=_MAX_OBSERVATION_ITEMS
        )
        for name in (
            "script",
            "portrait",
            "construction",
            "shape",
            "date_like",
            "denomination_mark",
        ):
            _validate_optional_string(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class GroundedVisualObservationReport:
    """Provider metadata plus one grounded observation."""

    observation: GroundedVisualObservation
    provider_id: str
    model_id: str
    response_id: str | None
    input_tokens: int | None
    output_tokens: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.observation, GroundedVisualObservation):
            raise GroundedVisualObservationContractError(
                "observation must be GroundedVisualObservation."
            )
        _validate_nonempty_string(self.provider_id, "provider_id")
        _validate_nonempty_string(self.model_id, "model_id")
        if self.response_id is not None:
            _validate_nonempty_string(self.response_id, "response_id")
        _validate_token_count(self.input_tokens, "input_tokens")
        _validate_token_count(self.output_tokens, "output_tokens")


@runtime_checkable
class GroundedVisualObservationProvider(Protocol):
    """Provider interface for one-side, non-identity visual observation."""

    @property
    def provider_id(self) -> str: ...

    @property
    def model_id(self) -> str: ...

    def observe(
        self, request: GroundedVisualObservationRequest
    ) -> GroundedVisualObservationReport: ...


def _validate_nonempty_string(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise GroundedVisualObservationContractError(
            f"{name} must be a non-empty string."
        )


def _validate_optional_string(value: object, name: str) -> None:
    if value is None:
        return
    _validate_nonempty_string(value, name)


def _validate_string_tuple(
    value: object, name: str, *, maximum_items: int
) -> None:
    if not isinstance(value, tuple) or len(value) > maximum_items:
        raise GroundedVisualObservationContractError(
            f"{name} must be a tuple with at most {maximum_items} entries."
        )
    for item in value:
        _validate_nonempty_string(item, f"{name} entry")


def _validate_token_count(value: object, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise GroundedVisualObservationContractError(
            f"{name} must be a non-negative integer or None."
        )
