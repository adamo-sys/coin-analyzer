"""Bounded runtime coordination for the legacy advisory coin detector.

This module is deliberately separate from ``capture_import``. It has no GUI,
persistence, provider, OCR, or computer-vision dependencies and owns no durable
state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from time import monotonic
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, Protocol
from uuid import uuid4


LEGACY_COIN_RECOGNITION = "legacy_coin_recognizer"
TelemetryCallback = Callable[[str, Mapping[str, object]], None]


class RecognitionStage(str, Enum):
    INTAKE = "INTAKE"
    ROUTING = "ROUTING"
    CAPABILITY = "CAPABILITY"
    REVIEW = "REVIEW"


class RecognitionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    NEEDS_INPUT = "NEEDS_INPUT"
    AWAITING_COLLECTOR_REVIEW = "AWAITING_COLLECTOR_REVIEW"


class RecognitionRoute(str, Enum):
    RUN_CAPABILITY = "RUN_CAPABILITY"
    REQUEST_IMAGE = "REQUEST_IMAGE"
    REQUIRE_COLLECTOR_REVIEW = "REQUIRE_COLLECTOR_REVIEW"


@dataclass(frozen=True, slots=True)
class RecognitionCapabilityResult:
    capability: str
    success: bool
    findings: Mapping[str, object] = field(default_factory=dict)
    confidence: float | None = None
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source_metadata: Mapping[str, object] = field(default_factory=dict)
    failure_category: str = ""

    def __post_init__(self) -> None:
        capability = str(self.capability or "").strip()
        if not capability:
            raise ValueError("capability is required.")
        if not isinstance(self.success, bool):
            raise ValueError("success must be boolean.")
        confidence = self.confidence
        if confidence is not None:
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise ValueError("generic confidence must be numeric or None.")
            confidence = float(confidence)
            if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                raise ValueError("generic confidence must be finite and between 0 and 1.")
        object.__setattr__(self, "capability", capability)
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "findings", MappingProxyType(dict(self.findings)))
        object.__setattr__(
            self, "source_metadata", MappingProxyType(dict(self.source_metadata))
        )
        object.__setattr__(self, "evidence", _dedupe(self.evidence))
        object.__setattr__(self, "warnings", _dedupe(self.warnings))
        object.__setattr__(
            self, "failure_category", str(self.failure_category or "").strip()
        )


class RecognitionCapability(Protocol):
    name: str

    def execute(self, image_reference: str) -> RecognitionCapabilityResult:
        ...


class RecognitionCapabilityRegistry:
    """Explicit allowlist of constructed capabilities."""

    def __init__(self, capabilities: Iterable[RecognitionCapability] = ()) -> None:
        self._capabilities: dict[str, RecognitionCapability] = {}
        for capability in capabilities:
            self.register(capability)

    def register(self, capability: RecognitionCapability) -> None:
        name = str(getattr(capability, "name", "") or "").strip()
        if not name or not callable(getattr(capability, "execute", None)):
            raise ValueError("a capability requires a name and execute method.")
        if name in self._capabilities:
            raise ValueError(f"capability already registered: {name}")
        self._capabilities[name] = capability

    def get(self, name: str) -> RecognitionCapability:
        key = str(name or "").strip()
        if key not in self._capabilities:
            raise KeyError(f"unknown recognition capability: {key}")
        return self._capabilities[key]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._capabilities))


@dataclass(frozen=True, slots=True)
class RecognitionRouteDecision:
    route: RecognitionRoute
    reason: str
    capability: str = ""


@dataclass(slots=True)
class RecognitionState:
    """Temporary state for one attempt; never a collection record."""

    scan_id: str
    image_reference: str
    stage: RecognitionStage = RecognitionStage.INTAKE
    status: RecognitionStatus = RecognitionStatus.ACTIVE
    results: list[RecognitionCapabilityResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    last_route: RecognitionRouteDecision | None = None
    capability_calls: int = 0


class DeterministicRecognitionRouter:
    critical_findings = ("country", "denomination", "year")

    def __init__(self, capability: str = LEGACY_COIN_RECOGNITION) -> None:
        self.capability = str(capability or "").strip()

    def route(self, state: RecognitionState) -> RecognitionRouteDecision:
        if not state.image_reference:
            return RecognitionRouteDecision(
                RecognitionRoute.REQUEST_IMAGE,
                "An image is required before recognition can run.",
            )
        if not state.results:
            return RecognitionRouteDecision(
                RecognitionRoute.RUN_CAPABILITY,
                "The allowlisted legacy detector has not run.",
                self.capability,
            )
        result = state.results[-1]
        if not result.success:
            reason = "The detector failed; collector review is required."
        else:
            missing = tuple(
                name
                for name in self.critical_findings
                if _missing_finding(result.findings.get(name))
            )
            if missing:
                reason = f"Critical findings are incomplete: {', '.join(missing)}."
            elif result.confidence is None:
                reason = "Generic confidence is unavailable; source scores remain advisory."
            else:
                reason = "Recognition is advisory and requires collector review."
        return RecognitionRouteDecision(
            RecognitionRoute.REQUIRE_COLLECTOR_REVIEW,
            reason,
        )


class RecognitionOrchestrator:
    """Invoke at most one capability and terminate after at most two routes."""

    def __init__(
        self,
        registry: RecognitionCapabilityRegistry,
        *,
        router: DeterministicRecognitionRouter | None = None,
        telemetry: TelemetryCallback | None = None,
        clock: Callable[[], float] = monotonic,
        max_capability_calls: int = 1,
    ) -> None:
        if max_capability_calls != 1:
            raise ValueError("legacy recognition requires a hard one-call limit.")
        self.registry = registry
        self.router = router or DeterministicRecognitionRouter()
        self.telemetry = telemetry
        self.clock = clock

    def run(self, image_reference: str) -> RecognitionState:
        state = RecognitionState(
            scan_id=f"scan_{uuid4().hex}",
            image_reference=str(image_reference or "").strip(),
        )
        self._emit("recognition.started", state)
        first = self._route(state)
        if first.route is not RecognitionRoute.RUN_CAPABILITY:
            return self._finish(state, first)

        self._invoke_once(state, first.capability)
        second = self._route(state)
        if second.route is RecognitionRoute.RUN_CAPABILITY:
            failure = RecognitionCapabilityResult(
                capability=second.capability or "unknown",
                success=False,
                warnings=("Recognition capability-call limit reached.",),
                failure_category="call_limit",
            )
            state.results.append(failure)
            state.warnings = list(_dedupe((*state.warnings, *failure.warnings)))
            second = RecognitionRouteDecision(
                RecognitionRoute.REQUIRE_COLLECTOR_REVIEW,
                "Capability-call limit reached; collector review is required.",
            )
            state.last_route = second
        return self._finish(state, second)

    def _route(self, state: RecognitionState) -> RecognitionRouteDecision:
        state.stage = RecognitionStage.ROUTING
        decision = self.router.route(state)
        state.last_route = decision
        self._emit("recognition.routed", state, route=decision.route.value)
        return decision

    def _invoke_once(self, state: RecognitionState, capability_name: str) -> None:
        state.stage = RecognitionStage.CAPABILITY
        state.capability_calls = 1
        try:
            started = self.clock()
        except Exception:
            started = None
        try:
            capability = self.registry.get(capability_name)
            result = capability.execute(state.image_reference)
            if result.capability != capability_name:
                raise ValueError("capability result name does not match registration.")
        except Exception as error:
            result = RecognitionCapabilityResult(
                capability=capability_name or "unknown",
                success=False,
                warnings=(f"Recognition capability failed: {error.__class__.__name__}.",),
                failure_category=error.__class__.__name__,
            )
        state.results.append(result)
        state.warnings = list(_dedupe((*state.warnings, *result.warnings)))
        duration_ms = _duration_ms(started, self.clock)
        self._emit(
            "recognition.capability_completed",
            state,
            capability=result.capability,
            success=result.success,
            duration_ms=duration_ms,
            failure_category=result.failure_category,
        )

    def _finish(
        self, state: RecognitionState, decision: RecognitionRouteDecision
    ) -> RecognitionState:
        state.stage = RecognitionStage.REVIEW
        if decision.route is RecognitionRoute.REQUEST_IMAGE:
            state.status = RecognitionStatus.NEEDS_INPUT
            event = "recognition.needs_input"
        else:
            state.status = RecognitionStatus.AWAITING_COLLECTOR_REVIEW
            event = "recognition.awaiting_review"
        self._emit(event, state, route=decision.route.value)
        return state

    def _emit(self, event: str, state: RecognitionState, **values: object) -> None:
        if self.telemetry is None:
            return
        result = state.results[-1] if state.results else None
        payload: dict[str, object] = {
            "scan_id": state.scan_id,
            "stage": state.stage.value,
            "status": state.status.value,
            "warning_count": len(state.warnings),
            "evidence_count": len(result.evidence) if result else 0,
        }
        if result is not None and result.confidence is not None:
            payload["confidence"] = result.confidence
        payload.update(
            {name: value for name, value in values.items() if value not in (None, "")}
        )
        try:
            self.telemetry(event, MappingProxyType(payload))
        except Exception:
            pass


def _duration_ms(started: float | None, clock: Callable[[], float]) -> int:
    if started is None:
        return 0
    try:
        return max(0, int(round((clock() - started) * 1000)))
    except Exception:
        return 0


def _dedupe(values: Iterable[object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(text for value in values if (text := str(value or "").strip())))


def _missing_finding(value: object) -> bool:
    return value is None or str(value).strip().casefold() in {"", "unknown", "none"}
