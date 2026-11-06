"""Concrete INERT binary-handle Ports for the retained C11 source interface.

All operations use in-memory BytesIO and synthetic process observations. begin
only registers dispatch; poll performs finite inert work. This is NOT an R2
backend, supervisor, native process runner, containment or durability proof.
No native scanner/WSL execution is implemented or admitted. Keep unresolved
operations and resources alive with their CaptureAdapter; no automatic retry.
"""

from dataclasses import dataclass
import hashlib
import io
import json


@dataclass(frozen=True)
class ClockSample:
    ticks: int
    frequency: int
    boot: str


@dataclass(frozen=True)
class Fault:
    operation: str
    resource: str
    mode: str
    payload: bytes = b""


class OfflineCapturePorts:
    """Executable offline implementation of begin/poll/allowed, not a native port.

    The integer counter is externally injected. Its structural validation and
    arithmetic cannot authenticate QPC or clock provenance. Faults are one-shot
    explicit recipe inputs; held pipe reads never manufacture EOF from parent
    exit. FLUSH acknowledges only the inert BytesIO operation, not OS durability.
    """

    def __init__(self, interface, *, clock, stdout, stderr, faults=(),
                 write_limit=8192, read_limit=8192, hold_stdout_open=False):
        if any(type(v) is not bytes for v in (stdout, stderr)):
            raise ValueError("inert streams must be exact bytes")
        if (any(type(v) is not int or not 1 <= v <= 8192 for v in (write_limit, read_limit))
                or type(hold_stdout_open) is not bool):
            raise ValueError("invalid inert operation bounds")
        if type(faults) is not tuple or any(type(f) is not Fault or
                f.operation not in {"OPEN_WRITER", "CONSTRUCT", "START", "READ", "WRITE",
                                    "FLUSH", "CLOSE", "WAIT_EXIT", "CANCEL", "OPEN_READER"} or
                f.mode not in {"error", "pending", "partial-error", "partial-acquire"} or
                type(f.resource) is not str or type(f.payload) is not bytes for f in faults):
            raise ValueError("invalid inert fault recipe")
        self.interface, self.clock = interface, clock
        initial = clock()  # First counter sample, before any synthetic acquisition.
        self._validate_sample(initial)
        self.t0, self.frequency, self.boot = initial.ticks, initial.frequency, initial.boot
        self.deadline = self.t0 + 420 * self.frequency
        if self.deadline > (1 << 63) - 1:
            raise ValueError("counter deadline overflow")
        self.last_ticks = self.t0
        self.deadline_detected = None
        self.flags = set()
        self.write_limit, self.read_limit = write_limit, read_limit
        self.stdout, self.stderr = stdout, stderr
        self.hold_stdout_open = hold_stdout_open
        self.faults = list(faults)
        self.operations, self.results, self.registrations = {}, {}, {}
        self.events, self.resources, self.sinks = [], [], {}
        self.started = False
        self.stdin_bytes = b""

    @staticmethod
    def _validate_sample(sample):
        if (type(sample) is not ClockSample or type(sample.ticks) is not int
                or not 0 <= sample.ticks <= (1 << 63) - 1
                or type(sample.frequency) is not int or not 1 <= sample.frequency <= 10**9
                or type(sample.boot) is not str or not sample.boot or len(sample.boot) > 256):
            raise ValueError("invalid integer clock observation")

    def allowed(self, phase):
        try:
            sample = self.clock()
            self._validate_sample(sample)
            if (sample.boot != self.boot or sample.frequency != self.frequency
                    or sample.ticks < self.last_ticks):
                raise ValueError("clock continuity")
            self.last_ticks = sample.ticks
            if sample.ticks >= self.deadline:
                self.flags.add("DEADLINE_EXCEEDED")
                if self.deadline_detected is None:
                    self.deadline_detected = sample.ticks
            if phase not in {"ACQUIRE", "CAPTURE", "CLEANUP", "READBACK", "OBSERVE"}:
                self.flags.add("UNKNOWN_PHASE")
            # Original subordinate host-worker cutoff, never a resettable timer.
            cutoff = self.t0 + (330 if phase in {"ACQUIRE", "CAPTURE"} else 420) * self.frequency
            if sample.ticks >= cutoff:
                self.flags.add("STAGE_CUTOFF")
        except Exception:
            self.flags.add("CLOCK_DISCONTINUITY")
        return not self.flags

    def begin(self, operation, register):
        if (type(operation) is not self.interface.Operation or
                type(operation.number) is not int or operation.number in self.operations or
                not 1 <= operation.number <= 8192):
            raise ValueError("operation identity or registry bound")
        if any(r not in self.resources for r in operation.resources):
            raise ValueError("unowned operation resource")
        self.operations[operation.number] = operation
        self.registrations[operation.number] = register

    def _register(self, operation, kind, handle, identity=None):
        identity = identity or "inert:" + kind
        resource = self.registrations[operation.number](kind, handle, identity)
        self.resources.append(resource)  # Immediately after each acquisition.
        return resource

    def _resource_kind(self, operation):
        if operation.kind == "OPEN_WRITER":
            return operation.argument + "_writer"
        if operation.kind == "OPEN_READER":
            return next((r.kind for r in self.resources if r.identity == operation.argument
                         and r.kind.endswith("_writer")), "unknown")
        return operation.resources[0].kind if operation.resources else ""

    def poll(self, operation):
        if self.operations.get(operation.number) is not operation:
            raise ValueError("unknown operation identity")
        if operation.number in self.results:
            return self.results[operation.number]
        kind = self._resource_kind(operation)
        fault = next((f for f in self.faults if f.operation == operation.kind
                      and f.resource == kind), None)
        if fault is not None and fault.mode == "pending":
            return None
        resource = operation.resources[0] if operation.resources else None
        if (operation.kind == "READ" and kind == "stdout" and self.hold_stdout_open
                and resource.handle.tell() == len(self.stdout)):
            return None
        self.events.append((operation.kind, kind))
        if fault is not None:
            self.faults.remove(fault)
        try:
            if fault is not None and fault.mode == "partial-acquire":
                if operation.kind != "CONSTRUCT":
                    raise ValueError("unsupported partial acquisition")
                self._register(operation, "process", object())
                self._register(operation, "stdin", io.BytesIO())
                raise OSError("inert partial construction")
            if fault is not None and fault.mode in {"error", "partial-error"}:
                raise OSError("inert injected failure")
            value = self._perform(operation, kind, resource)
            result = self.interface.Completion(value)
        except Exception as error:
            value = fault.payload if fault is not None and fault.mode == "partial-error" else None
            result = self.interface.Completion(value=value, error=error)
        self.results[operation.number] = result
        return result

    def _perform(self, operation, kind, resource):
        name, argument = operation.kind, operation.argument
        if name == "OPEN_WRITER":
            handle = io.BytesIO()
            owned = self._register(operation, kind, handle)
            self.sinks[owned.identity] = b""
            return owned
        if name == "CONSTRUCT":
            return (self._register(operation, "process", object()),
                    self._register(operation, "stdin", io.BytesIO()),
                    self._register(operation, "stdout", io.BytesIO(self.stdout)),
                    self._register(operation, "stderr", io.BytesIO(self.stderr)))
        if name == "START":
            self.started = True
        elif name == "READ":
            return resource.handle.read(min(argument, self.read_limit))
        elif name == "WRITE":
            count = resource.handle.write(argument[:self.write_limit])
            if kind == "stdin":
                self.stdin_bytes = resource.handle.getvalue()
            return count
        elif name == "FLUSH":
            resource.handle.flush()
        elif name == "CLOSE":
            if kind.endswith("_writer"):
                self.sinks[resource.identity] = resource.handle.getvalue()
            if kind != "process":
                resource.handle.close()
        elif name == "WAIT_EXIT":
            return self.interface.ExitObservation(resource.identity, "inert-guest", "inert-exit", 0)
        elif name == "CANCEL":
            # A request is recorded even after a broken clock check. It never
            # proves exit, guest state or completion of an outstanding pipe IO.
            return None
        elif name == "OPEN_READER":
            writer = next(r for r in self.resources if r.identity == argument
                          and r.kind.endswith("_writer"))
            if not writer.closed:
                raise ValueError("writer not disposed")
            return self._register(operation, kind.replace("_writer", "_reader"),
                                  io.BytesIO(self.sinks[argument]), argument)
        else:
            raise ValueError("unsupported inert operation")
        return None

    def manifest(self):
        """Sanitized deterministic observations, preserving all unavailable claims."""
        result = {"schema": "c07-inert-ports-v1", "runtime_acceptance": "NOT_ESTABLISHED",
                  "native_backend": "UNAVAILABLE", "qualified": False,
                  "t0_ticks": self.t0, "frequency": self.frequency,
                  "deadline_ticks": self.deadline, "last_observed_ticks": self.last_ticks,
                  "deadline_detected_ticks": self.deadline_detected,
                  "detection_latency_ticks": (None if self.deadline_detected is None else
                                               self.deadline_detected - self.deadline),
                  "rejection_flags": sorted(self.flags), "registered_operations": len(self.operations),
                  "unsettled_operations": sorted(set(self.operations) - set(self.results)),
                  "acquired_resources": len(self.resources),
                  "unclosed_resources": sorted(r.kind for r in self.resources if not r.closed)}
        result["manifest_sha256"] = hashlib.sha256(json.dumps(
            result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return result
