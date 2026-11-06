"""SEC-003 R2 C11 source candidate; no entry point or platform implementation.

Use only in a separately authorized E helper, never S's timing loop. Ports must
be independently authenticated, reviewed and qualified. No object or identity
string authenticates its own origin. Retain this adapter and its pending owners,
buffers and errors until every uncertainty has been independently reconciled.
"""
from dataclasses import dataclass, field
import hashlib
from typing import Protocol

CHUNK = 8192
CAPS = {"stdout": 65536, "stderr": 1048576}
HOST_SHA256 = "94e35583349add109c0b38bc70d92ed281676df1cc7056ca2a34024911089fe2"


@dataclass(eq=False)
class Resource:
    kind: str
    handle: object
    identity: str
    closed: bool = False


@dataclass(frozen=True)
class Completion:
    """Error values may contain partial bytes; retain them as failure evidence."""
    value: object = None
    error: BaseException | None = None


@dataclass(eq=False)
class Operation:
    number: int
    kind: str
    resources: list[Resource]
    argument: object
    completion: Completion | None = None
    dispatch_uncertain: bool = False
    poll_error_recorded: bool = False
    consumed: bool = False


@dataclass(frozen=True)
class ExitObservation:
    process_identity: str
    guest_process_identity: str
    observation_id: str
    code: int


@dataclass
class Stream:
    name: str
    writer: Resource | None = None
    pipe: Resource | None = None
    operation: Operation | None = None
    received: int = 0
    stored: int = 0
    digest: object = field(default_factory=hashlib.sha256)
    buffer: bytes = b""
    offset: int = 0
    eof: bool = False
    flushed: bool = False
    reader: Resource | None = None
    raw: bytearray = field(default_factory=bytearray)
    readback_eof: bool = False


class Ports(Protocol):
    """Injected implementation required; none is supplied or qualified here.

    begin is nonblocking dispatch. register(kind, handle, identity) MUST run
    immediately after EACH successful acquisition, before another fallible
    action or exposure. Preserve partially acquired resources. No unregistered,
    duplicated or inherited task capability is allowed. poll returns Completion
    ONLY after actual underlying IO settled, even for failures; cancellation
    request/callback/process exit alone cannot mean settled. A dispatch exception
    does not mean no task started. The backend must retain uncertain ownership.

    Operations and exact results:
    OPEN_WRITER(stream): create-new protected binary sink, register
      '<stream>_writer', return that Resource.
    CONSTRUCT: register process plus stdin/stdout/stderr binary pipe ends;
      return (process, stdin, stdout, stderr), with these exact resource kinds.
      Do not start the process during construction.
    START(process): start registered process, return None on witnessed success.
    READ(resource, requested): return exact bytes, <=requested; b'' only for
      actual EOF. Pending descendants' pipe handles cannot become synthetic EOF.
    WRITE(resource, bytes): return actual positive byte count <=argument length.
      Partial writes are normal. Error leaves retained partial artifacts; do not
      hide unreported bytes/side effects or reissue an uncertain operation.
    FLUSH(writer): buffer flush then required OS durable-flush acknowledgment.
    CLOSE(resource): actual successful disposal, not merely a close request.
    WAIT_EXIT(process): return independent stable-handle ExitObservation.
    CANCEL(process): only independently authorized nonblocking cancellation
      dispatch; return None for request completion, never infer process exit.
    OPEN_READER(writer identity): protected pinned reopen, register
      '<stream>_reader' with SAME identity as disposed writer, return Resource.
      Reject reparse/ancestor/link/volume/type swaps and late-write uncertainty.
      Source/destination pinning remains a qualified C10 backend dependency.
    START/FLUSH/CLOSE/CANCEL success values are None. Every acquired resource,
    including readers, is published through register and independently closed.

    allowed(phase) uses externally supplied original absolute cutoff/authority;
    it must not reset time. False/throw rejects and inhibits new task IO.
    CANCEL dispatch and error accounting never depend on that check. The backend
    must separately enforce cancellation authority and original action cutoffs.
    Backend registry binds each number/resource to exact run/producer/E identity.
    begin/poll/control dispatch must not block on task IO. This source cannot
    establish that, QPC timing, authentication, containment, or namespace safety.
    A driver continues supervision without waiting for advance to finish IO.
    No operation may access resources outside its registered dependency set.
    Error completions may carry partial READ bytes or other failure payloads.
    Preserve those exact payloads with operation/resource bindings; they are not
    successful stream bytes and are never replayed or used to restore success.
    """

    def begin(self, operation: Operation, register) -> None: ...
    def poll(self, operation: Operation) -> Completion | None: ...
    def allowed(self, phase: str) -> bool: ...


class CaptureAdapter:
    """Single driver/owner; concurrent advance/receipt/snapshot is forbidden."""

    def __init__(self, ports: Ports, run_nonce: str, producer_id: str,
                 guest_process_identity: str, admission: bytes):
        for value in (run_nonce, producer_id):
            if (type(value) is not str or len(value) != 64
                    or any(c not in "0123456789abcdef" for c in value)):
                raise ValueError("RUN_PRODUCER_BINDING")
        if (type(admission) is not bytes or not 1 <= len(admission) <= 4096
                or type(guest_process_identity) is not str
                or not 1 <= len(guest_process_identity) <= 256
                or guest_process_identity.upper() in {"UNKNOWN", "UNAVAILABLE"}):
            raise ValueError("ADMISSION_IDENTITY")
        self.ports = ports
        self.run_nonce, self.producer_id = run_nonce, producer_id
        self.guest_identity, self.admission = guest_process_identity, admission
        self.resources: list[Resource] = []
        self.pending: list[Operation] = []
        self.errors: list[tuple[str, BaseException | None]] = []
        self.failed_operations: list[Operation] = []
        self.rejected = self.poisoned = self.cutoff_lost = False
        self.sequence = 0
        self.stage = "OPEN_STDOUT"
        self.control: Operation | None = None
        self.process: Resource | None = None
        self.stdin: Resource | None = None
        self.input_op: Operation | None = None
        self.input_offset = 0
        self.stdin_completed = False
        self.wait_op: Operation | None = None
        self.exit: ExitObservation | None = None
        self.exit_uncertainty_recorded = False
        self.start_attempted = self.cancel_attempted = False
        self.streams = [Stream("stdout"), Stream("stderr")]
        self.cleanup_ops: dict[Resource, Operation] = {}
        self.flush_attempted: set[Resource] = set()
        self.close_attempted: set[Resource] = set()
        self.finished = False

    def _fail(self, code, error=None, poison=False):
        self.rejected = True
        self.poisoned |= poison
        self.errors.append((code, error))

    def _allowed(self, phase):
        if self.cutoff_lost:
            return False
        try:
            if self.ports.allowed(phase) is True:
                return True
            self._fail("EXTERNAL_CUTOFF_OR_PERMISSION")
        except BaseException as error:
            self._fail("REMAINING_TIME_CHECK", error)
        self.cutoff_lost = True
        return False

    def _register(self, op, kind, handle, identity):
        # First protected action after successful acquisition, including partials.
        resource = Resource(kind, handle, identity)
        self.resources.append(resource)
        op.resources.append(resource)
        if (op.completion is not None or type(identity) is not str
                or not identity or len(self.resources) > 8
                or any(r.handle is handle for r in self.resources[:-1])):
            self._fail("ACQUISITION_REGISTRY", poison=True)
        if kind == "process" and self.process is None:
            self.process = resource
        return resource

    def _begin(self, kind, resources=(), argument=None, phase="CAPTURE"):
        if kind != "CANCEL" and not self._allowed(phase):
            return None
        self.sequence += 1
        op = Operation(self.sequence, kind, list(resources), argument)
        self.pending.append(op)  # Before potentially partial dispatch.
        if kind == "START":
            self.start_attempted = True
        try:
            self.ports.begin(op, lambda k, h, i: self._register(op, k, h, i))
        except BaseException as error:
            op.dispatch_uncertain = True
            self._fail("DISPATCH_" + kind, error, poison=True)
        return op

    def _poll(self):
        for op in tuple(self.pending):
            if op.completion is not None:
                continue
            try:
                result = self.ports.poll(op)
                if result is not None:
                    if type(result) is not Completion:
                        raise ValueError("COMPLETION_TYPE")
                    op.completion = result
                    if result.error is not None:
                        self.failed_operations.append(op)
                        self._fail("TASK_" + op.kind, result.error, poison=True)
                    elif op.kind in {"START", "FLUSH", "CLOSE", "CANCEL"}:
                        if result.value is not None:
                            self._fail("COMPLETION_VALUE", poison=True)
                        elif op.kind == "CLOSE":
                            op.resources[0].closed = True
            except BaseException as error:
                if not op.poll_error_recorded:
                    op.poll_error_recorded = True
                    self._fail("POLL_" + op.kind, error, poison=True)
        # No pending operation or its resources are lost when an error occurs.
        self.pending[:] = [op for op in self.pending
                           if op.completion is None or not op.consumed]

    def _take(self, op):
        if op is None or op.completion is None or op.consumed:
            return None
        op.consumed = True
        return op.completion

    def _owned(self, value, kind):
        return (type(value) is Resource and value in self.resources
                and value.kind == kind and not value.closed)

    def _cancel(self):
        # A broken remaining-time check cannot skip permitted cancellation.
        if self.process is not None and self.start_attempted and not self.cancel_attempted:
            self.cancel_attempted = True
            self._begin("CANCEL", (self.process,))

    def _setup(self):
        if self.control is None:
            if self.rejected:
                return
            if self.stage.startswith("OPEN_"):
                self.control = self._begin("OPEN_WRITER",
                    argument=self.stage[5:].lower(), phase="ACQUIRE")
            elif self.stage == "CONSTRUCT":
                self.control = self._begin("CONSTRUCT", phase="ACQUIRE")
            elif self.stage == "START":
                self.control = self._begin("START", (self.process,))
            return
        done = self._take(self.control)
        if done is None:
            return
        self.control = None
        if done.error is not None:
            return
        if self.stage.startswith("OPEN_"):
            stream = self.streams[0 if self.stage == "OPEN_STDOUT" else 1]
            if not self._owned(done.value, stream.name + "_writer"):
                self._fail("WRITER_ACQUISITION", poison=True)
                return
            stream.writer = done.value
            self.stage = "OPEN_STDERR" if stream.name == "stdout" else "CONSTRUCT"
        elif self.stage == "CONSTRUCT":
            value = done.value
            kinds = ("process", "stdin", "stdout", "stderr")
            if (type(value) is not tuple or len(value) != 4
                    or not all(self._owned(r, k) for r, k in zip(value, kinds))
                    or len({id(r) for r in value}) != 4):
                self._fail("PROCESS_CONSTRUCTION", poison=True)
                return
            self.process, self.stdin, self.streams[0].pipe, self.streams[1].pipe = value
            self.stage = "START"
        elif self.stage == "START":
            self.stage = "RUN"

    def _input(self):
        done = self._take(self.input_op)
        if done is not None:
            kind = self.input_op.kind
            self.input_op = None
            if done.error is None:
                if kind == "CLOSE":
                    self.stdin_completed = self.input_offset == len(self.admission)
                elif (type(done.value) is int
                      and 0 < done.value <= len(self.admission) - self.input_offset):
                    self.input_offset += done.value
                else:
                    self._fail("STDIN_PARTIAL_WRITE", poison=True)
        if self.input_op is None and not self.rejected and not self.stdin_completed:
            if self.input_offset < len(self.admission):
                self.input_op = self._begin("WRITE", (self.stdin,),
                                            self.admission[self.input_offset:])
            else:
                self.close_attempted.add(self.stdin)
                self.input_op = self._begin("CLOSE", (self.stdin,), phase="CLEANUP")

    def _stream(self, stream):
        done = self._take(stream.operation)
        if done is not None:
            kind = stream.operation.kind
            stream.operation = None
            if done.error is None:
                value = done.value
                if kind == "READ":
                    if type(value) is not bytes:
                        self._fail("NON_BINARY_READ", poison=True)
                    elif not value:
                        stream.eof = True
                    else:
                        stream.buffer, stream.offset = value, 0
                        stream.received += len(value)
                        stream.digest.update(value)
                        if len(value) > CHUNK or stream.received > CAPS[stream.name]:
                            self._fail("STREAM_OVERSIZE_" + stream.name, poison=True)
                elif (type(value) is int
                      and 0 < value <= len(stream.buffer) - stream.offset):
                    stream.offset += value
                    stream.stored += value
                    if stream.offset == len(stream.buffer):
                        stream.buffer, stream.offset = b"", 0
                else:
                    self._fail("SINK_PARTIAL_WRITE", poison=True)
        if stream.operation is None and not self.rejected:
            if stream.buffer:
                stream.operation = self._begin("WRITE", (stream.writer,),
                                                stream.buffer[stream.offset:])
            elif not stream.eof:
                stream.operation = self._begin("READ", (stream.pipe,), CHUNK)

    def _observe_exit(self):
        done = self._take(self.wait_op)
        if done is not None and done.error is None:
            value = done.value
            if (type(value) is ExitObservation
                    and value.process_identity == self.process.identity
                    and value.guest_process_identity == self.guest_identity
                    and type(value.code) is int
                    and type(value.observation_id) is str and value.observation_id
                    and value.observation_id.upper() not in {"UNKNOWN", "UNAVAILABLE"}):
                self.exit = value
                if value.code != 0:
                    self._fail("ABNORMAL_EXIT")
            else:
                self._fail("EXIT_BINDING", poison=True)
        if self.wait_op is None and self.start_attempted and self.process is not None:
            self.wait_op = self._begin("WAIT_EXIT", (self.process,), phase="CLEANUP")

    def _busy(self, resource):
        return any(op.completion is None and resource in op.resources for op in self.pending)

    def _cleanup(self):
        for resource, op in tuple(self.cleanup_ops.items()):
            done = self._take(op)
            if done is not None:
                del self.cleanup_ops[resource]
                if done.error is None and op.kind == "FLUSH":
                    for stream in self.streams:
                        if stream.writer is resource:
                            stream.flushed = True
        # Normal path enters only after full drain. Failure path attempts every
        # independently idle resource; pending dependency prevents unsafe disposal.
        writers = [r for r in self.resources if r.kind.endswith("_writer")]
        for resource in writers:
            if resource not in self.flush_attempted and not self._busy(resource):
                self.flush_attempted.add(resource)
                op = self._begin("FLUSH", (resource,), phase="CLEANUP")
                if op is not None:
                    self.cleanup_ops[resource] = op
        if self.exit is None and self.process is not None:
            self.exit_uncertainty_recorded = True  # Before any process close.
        for resource in self.resources:
            if (resource.closed or resource in self.close_attempted
                    or resource in self.cleanup_ops or self._busy(resource)):
                continue
            if resource in writers and resource not in self.flush_attempted:
                continue
            self.close_attempted.add(resource)
            op = self._begin("CLOSE", (resource,), phase="CLEANUP")
            if op is not None:
                self.cleanup_ops[resource] = op

    def _readback(self, stream):
        done = self._take(stream.operation)
        if done is not None:
            kind = stream.operation.kind
            stream.operation = None
            if done.error is not None:
                return
            if kind == "OPEN_READER":
                value = done.value
                if (not self._owned(value, stream.name + "_reader")
                        or value.identity != stream.writer.identity):
                    self._fail("READBACK_IDENTITY", poison=True)
                    return
                stream.reader = value
            elif kind == "READ":
                if type(done.value) is not bytes:
                    self._fail("READBACK_BINARY", poison=True)
                    return
                stream.raw.extend(done.value)  # Preserve entire returned chunk.
                if len(done.value) > CHUNK or len(stream.raw) > CAPS[stream.name]:
                    self._fail("READBACK_OVERSIZE", poison=True)
                    return
                if not done.value:
                    stream.readback_eof = True
            elif kind == "CLOSE":
                if (len(stream.raw) != stream.received
                        or stream.stored != stream.received
                        or hashlib.sha256(stream.raw).digest() != stream.digest.digest()):
                    self._fail("RAW_CAPTURE_MISMATCH", poison=True)
                return
        if self.rejected or stream.operation is not None:
            return
        if stream.reader is None:
            stream.operation = self._begin("OPEN_READER", argument=stream.writer.identity,
                                            phase="READBACK")
        elif not stream.readback_eof:
            stream.operation = self._begin("READ", (stream.reader,), CHUNK, phase="READBACK")
        elif not stream.reader.closed:
            self.close_attempted.add(stream.reader)
            stream.operation = self._begin("CLOSE", (stream.reader,), phase="CLEANUP")

    def advance(self):
        """One scheduling pass, no task waits; external driver supplies cadence.

        A pending pipe after parent exit stays pending. Driver must supervise
        original cutoffs and retain this object even if it reports INCOMPLETE.
        """
        if self.finished:
            return
        self._poll()
        self._allowed("OBSERVE")
        if self.stage not in {"RUN", "READBACK"}:
            self._setup()
        if self.stage == "RUN":
            self._input()
            for stream in self.streams:
                self._stream(stream)
        if self.start_attempted:
            self._observe_exit()
        if self.rejected:
            self._cancel()
        drained = (self.stdin_completed and self.exit is not None
                   and all(s.eof and not s.buffer for s in self.streams))
        if self.rejected or (self.stage == "RUN" and drained):
            self._cleanup()
            if (not self.rejected and all(r.closed for r in self.resources)
                    and all(s.flushed for s in self.streams)
                    and all(op.completion is not None for op in self.pending)):
                self.stage = "READBACK"
        if self.stage == "READBACK" and not self.rejected:
            for stream in self.streams:
                self._readback(stream)
            self.finished = (not self.rejected and all(s.readback_eof and s.reader.closed
                             for s in self.streams))
        for op in self.pending:
            if op.kind == "CANCEL" and op.completion is not None:
                self._take(op)

    def receipt(self):
        """Local status, never CORE_COMPLETE/acceptance or a durable ledger.

        Retain the adapter: this receipt does not transfer pending ownership,
        authorize disposal/deletion/retry or upgrade a rejected admitted run.
        Successful READ overflow bytes remain in buffers; failed completions
        retain their entire values (including partial raw bytes) and resource
        bindings in failed_operations, outside successful counts/hashes. Spool
        partials remain on disk. Undelivered bytes are UNKNOWN, not captured.
        """
        return {
            "run_nonce": self.run_nonce, "producer_id": self.producer_id,
            "state": "POISONED" if self.poisoned else (
                "CAPTURE_COMPLETE_SOURCE_INTERFACE" if self.finished and not self.rejected
                else "INCOMPLETE"),
            "rejected": self.rejected, "errors": tuple(self.errors),
            "failed_operations": tuple(self.failed_operations),
            "pending_operations": tuple(op for op in self.pending if op.completion is None),
            "unclosed_resources": tuple(r for r in self.resources if not r.closed),
            "retained_buffers": tuple((s.name, s.buffer, s.offset) for s in self.streams),
            "received_counts": tuple((s.name, s.received) for s in self.streams),
            "stored_counts": tuple((s.name, s.stored) for s in self.streams),
            "exit_uncertainty_recorded": self.exit_uncertainty_recorded,
            "runtime_acceptance": "NOT_ESTABLISHED",
        }

    def snapshot(self, capture_snapshot_type):
        """Exact C9 interface; caller must independently bind factory to HOST_SHA256.

        C9 strictly validates terminal UTF-8/canonical framing and ledger
        sequence/hash linkage. stderr is binary and is never decoded here.
        Neither this factory call nor a matching reference authenticates capture.
        """
        if (not self.finished or self.rejected or self.exit is None
                or any(not r.closed for r in self.resources)
                or any(op.completion is None for op in self.pending)):
            raise ValueError("CAPTURE_NOT_COMPLETE")
        stdout, stderr = (bytes(s.raw) for s in self.streams)
        return capture_snapshot_type(
            run_nonce=self.run_nonce, producer_id=self.producer_id,
            stdout=stdout, stderr=stderr, stdout_bytes=len(stdout), stderr_bytes=len(stderr),
            stdin_completed=self.stdin_completed, both_eof_and_drained=True,
            writers_disposed=True, flushes_acknowledged=True,
            all_async_io_completed=True, exit_observed=True, exit_code=self.exit.code,
            guest_process_identity=self.exit.guest_process_identity,
            trusted_observation_id=self.exit.observation_id)
