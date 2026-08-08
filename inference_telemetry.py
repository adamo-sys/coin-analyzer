"""Best-effort telemetry for OCR and model-assisted inference boundaries."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import threading
from time import perf_counter
from typing import Callable, Mapping, Protocol, TypeVar

from inference_pricing import estimate_inference_cost_usd


DEFAULT_TELEMETRY_PATH = Path("collection_data/telemetry/inference.jsonl")
_SCAN_ID: ContextVar[str | None] = ContextVar("inference_scan_id", default=None)
_DEFAULT_SINK = None
_DEFAULT_SINK_LOCK = threading.Lock()
T = TypeVar("T")
_ERROR_TYPE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


@dataclass(frozen=True, slots=True)
class InferenceTelemetryRecord:
    scan_id: str
    stage: str
    provider: str
    model: str
    duration_ms: float
    success: bool
    error_type: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None

    def __post_init__(self) -> None:
        for name in ("scan_id", "stage", "provider", "model"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise ValueError(f"{name} must be a non-empty string.")
        _validate_finite_non_negative_number("duration_ms", self.duration_ms)
        if not isinstance(self.success, bool):
            raise ValueError("success must be a boolean.")
        if self.success != (self.error_type is None):
            raise ValueError("success and error_type disagree.")
        if self.error_type is not None and (
            not isinstance(self.error_type, str)
            or _ERROR_TYPE_PATTERN.fullmatch(self.error_type) is None
        ):
            raise ValueError(
                "error_type must be a stable exception/type identifier or None."
            )
        for name in ("input_tokens", "output_tokens"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise ValueError(f"{name} must be a non-negative integer or None.")
        if self.estimated_cost_usd is not None:
            _validate_finite_non_negative_number(
                "estimated_cost_usd",
                self.estimated_cost_usd,
            )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class TelemetrySink(Protocol):
    def write(self, record: InferenceTelemetryRecord) -> None:
        ...


class JsonlTelemetryStore:
    """Thread-safe append storage isolated from collection schemas."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).absolute()
        self._lock = threading.Lock()

    def write(self, record: InferenceTelemetryRecord) -> None:
        if not isinstance(record, InferenceTelemetryRecord):
            raise TypeError("record must be InferenceTelemetryRecord.")
        payload = json.dumps(
            record.to_dict(),
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(payload + "\n")
                handle.flush()


def get_default_telemetry_sink() -> TelemetrySink:
    global _DEFAULT_SINK
    if _DEFAULT_SINK is None:
        with _DEFAULT_SINK_LOCK:
            if _DEFAULT_SINK is None:
                _DEFAULT_SINK = JsonlTelemetryStore(DEFAULT_TELEMETRY_PATH)
    return _DEFAULT_SINK


@contextmanager
def telemetry_scan(scan_id: str):
    value = str(scan_id or "").strip()
    if not value:
        raise ValueError("scan_id must be a non-empty string.")
    token = _SCAN_ID.set(value)
    try:
        yield
    finally:
        _SCAN_ID.reset(token)


def current_scan_id() -> str:
    return _SCAN_ID.get() or "unscoped"


def scan_id_from_workspace(workspace: str | Path) -> str:
    """Reuse a canonical workflow token without persisting an operational path."""

    path = Path(workspace)
    name = path.name
    if name.startswith("workflow-") and len(name) > len("workflow-"):
        return name[len("workflow-") :]
    digest = hashlib.sha256(str(path.absolute()).encode("utf-8")).hexdigest()
    return f"workspace-{digest[:32]}"


def response_token_usage(response: object) -> tuple[int | None, int | None]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None, None
    if isinstance(usage, Mapping):
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
    else:
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
    return _optional_token_count(input_tokens), _optional_token_count(output_tokens)


def instrument_inference(
    operation: Callable[[], T],
    *,
    stage: str,
    provider: str,
    model: str,
    sink: TelemetrySink | None,
    scan_id: str | None = None,
    clock: Callable[[], float] = perf_counter,
    usage_resolver: Callable[[T], tuple[int | None, int | None]] | None = None,
) -> T:
    """Run one inference call, emit best-effort telemetry, and preserve behavior."""

    try:
        started = clock()
    except Exception:
        started = None
    try:
        result = operation()
    except Exception as error:
        _record_best_effort(
            sink,
            started=started,
            clock=clock,
            scan_id=scan_id,
            stage=stage,
            provider=provider,
            model=model,
            success=False,
            error_type=error.__class__.__name__,
        )
        raise

    _record_best_effort(
        sink,
        started=started,
        clock=clock,
        scan_id=scan_id,
        stage=stage,
        provider=provider,
        model=model,
        success=True,
        error_type=None,
        result=result,
        usage_resolver=usage_resolver,
    )
    return result


def _optional_token_count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _record_best_effort(
    sink: TelemetrySink | None,
    *,
    started: float | None,
    clock: Callable[[], float],
    scan_id: str | None,
    stage: str,
    provider: str,
    model: str,
    success: bool,
    error_type: str | None,
    result: object = None,
    usage_resolver: Callable[[object], tuple[int | None, int | None]] | None = None,
) -> None:
    if sink is None:
        return
    try:
        if started is None:
            return
        duration_ms = max(0.0, (clock() - started) * 1000.0)
        input_tokens = output_tokens = None
        if success and usage_resolver is not None:
            try:
                input_tokens, output_tokens = usage_resolver(result)
            except Exception:
                input_tokens = output_tokens = None
        record = InferenceTelemetryRecord(
            scan_id=scan_id or current_scan_id(),
            stage=stage,
            provider=provider,
            model=model,
            duration_ms=duration_ms,
            success=success,
            error_type=error_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimate_inference_cost_usd(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )
        sink.write(record)
    except Exception:
        # Every telemetry-side operation is advisory. None may replace the
        # primary return value or provider exception.
        pass


def _validate_finite_non_negative_number(name: str, value: object) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ValueError(f"{name} must be a finite non-negative number.")
