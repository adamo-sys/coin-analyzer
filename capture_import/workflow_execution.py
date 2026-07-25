"""Sequential execution engine for the import workflow pipeline.

This module implements Sprint 7 Units 4 and 6: deterministic, single-threaded
execution of a :class:`ProcessingPipeline` with cooperative cancellation and
pipeline lifecycle events, ``PreparedImport`` assembly, and the workflow's
single durable handoff to a transaction delegate.

Failure contract (frozen for Sprint 7):

- Stage returns an invalid ``StageResult`` (or a non-``StageResult``)
  → :class:`StageContractError`.
- Stage raises an ordinary exception
  → ``raise StageExecutionError(stage_id, exc) from exc``.
- Stage raises a workflow-typed exception (``ImportWorkflowError``
  subclass) → propagated unwrapped; ``WorkflowCancelledError`` additionally
  records ``PIPELINE_CANCELLED``.
- Cancellation requested by the caller → :class:`WorkflowCancelledError`
  raised unwrapped at cooperative boundaries.

Cancellation is checked before each stage, after each stage, after the final
stage, and — when a transaction delegate is supplied — once more immediately
before the handoff (the third boundary defined in
``docs/architecture/IMPORT_WORKFLOW.md``).  A terminal pipeline event is
emitted on every pipeline path: ``PIPELINE_COMPLETED``,
``PIPELINE_CANCELLED``, or ``STAGE_FAILED``.  ``PreparedImport`` assembly
failures raise :class:`StageContractError` without a pipeline-terminal
event: the stages completed, but no handoff occurred.

Merge policy: artifact and metadata keys must be unique across stages.
A later stage re-emitting a key produced by an earlier stage is a wiring
error and fails fast with :class:`StageContractError`, consistent with
the duplicate ``stage_id`` construction policy and ADR-007 fail-fast.

Transaction handoff (Unit 6):

- When ``transaction`` is supplied to :meth:`ImportWorkflow.execute`, the
  merged outcome is assembled into a validated ``PreparedImport`` (declared
  artifacts must exist as plain regular files in the workspace; verified
  sizes become ``expected_size``) and the delegate is invoked **exactly
  once** with it.  ``PreparedImport`` is the only object that crosses the
  durability boundary.
- The delegate owns every durable side effect: ``TransactionService``,
  journals, rollback, and recovery remain Sprint 6-owned.  This module
  imports none of them.
- Delegate exceptions propagate unwrapped: transaction and recovery errors
  are never converted into stage errors (IMPORT_WORKFLOW.md error model).
- With ``transaction=None`` the engine remains purely ephemeral and returns
  the :class:`PipelineOutcome` (Unit 4 behavior, unchanged).

Deliberately excluded:

- Workspace creation, containment, and cleanup (Unit 5,
  ``workflow_workspace.py``).  The caller supplies an absolute workspace
  path; this engine never creates or deletes it.
- Reference processing stages (Unit 7).  The concrete mapping from a
  ``PreparedImport`` to coordinator/transaction inputs (snapshot, package,
  preview, decisions) belongs to the application layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib
import os
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Callable, Mapping, TypeVar, overload

from PIL import Image, UnidentifiedImageError

from ._filesystem import (
    handle_matches_path,
    handle_object_identity,
    open_plain_child_directory,
    open_plain_child_file_readonly,
    open_plain_directory_handle,
    require_plain_regular_file,
)
from .events import ImportEventBus
from .image_validation import require_complete_jpeg
from .limits import (
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    MAX_PROCESSED_ARTIFACT_SIZE,
)
from .workflow_models import (
    ImportRequest,
    JsonValue,
    PreparedArtifactDescriptor,
    PreparedArtifactSet,
    PreparedFile,
    PreparedImport,
    PreparedWorkspaceLease,
    StageArtifact,
    StageInput,
    StageResult,
)
from .workflow_pipeline import (
    ImportWorkflowError,
    ProcessingPipeline,
    ProcessingStage,
    StageContractError,
    StageExecutionError,
    WorkflowCancelledError,
)

_CANCELLED_BY_CALLER = "cancelled by caller"
_CANCELLED_BY_STAGE = "cancelled by stage"

T = TypeVar("T")
_ROLE_ORDER = {"front": 0, "reverse": 1, "edge": 2}
_MIN_CROP_CONFIDENCE = 0.65
_NORMALIZATION_STAGE_ID = "image-normalization"
_CROP_STAGE_ID = "crop-detection"


@dataclass(frozen=True, slots=True)
class PipelineOutcome:
    """Accumulated result of one successful pipeline execution.

    ``artifacts`` is the union of every stage's produced artifacts;
    ``metadata`` is the union of every stage's metadata.  Both mappings
    are snapshots taken at completion.  Use :func:`assemble_prepared_import`
    to verify workspace files and build the durable handoff object.
    """

    artifacts: Mapping[str, StageArtifact]
    metadata: Mapping[str, JsonValue]


def assemble_prepared_import(
    request: ImportRequest,
    outcome: PipelineOutcome,
    workspace: Path,
    artifact_stages: Mapping[str, str],
) -> PreparedImport:
    """Build and validate the sole object that crosses the durability boundary.

    Every declared artifact must exist beneath ``workspace`` as a plain
    regular file: links and reparse points are rejected fail-closed via
    :func:`require_plain_regular_file`, and the verified size becomes
    ``PreparedFile.expected_size``.  Byte-integrity hashing stays with the
    Sprint 5/6 snapshot path, so ``sha256`` remains ``None`` here.  Files
    are emitted in pipeline execution (insertion) order.  Lexical
    containment is guaranteed by the frozen ``_validate_relative_path``
    contract every artifact passed at result-application time.

    Args:
        request: The immutable import request being executed.
        outcome: Merged outcome of a successful pipeline execution.
        workspace: Absolute workspace path the stages wrote into.
        artifact_stages: Artifact key → producing stage id, used to
            attribute assembly failures to the declaring stage.

    Returns:
        A validated ``PreparedImport``.

    Raises:
        StageContractError: If a declared artifact is missing or is not a
            plain regular file.  The original ``OSError`` is preserved via
            exception chaining.  No pipeline-terminal event accompanies an
            assembly failure: the stages completed, but no handoff occurred.
    """
    processed_artifacts = _assemble_processed_artifacts(
        outcome, workspace, artifact_stages
    )
    selected = (
        {item.artifact_key: item for item in processed_artifacts.descriptors}
        if processed_artifacts is not None
        else {}
    )
    try:
        files: list[PreparedFile] = []
        for key, artifact in outcome.artifacts.items():
            candidate = workspace / artifact.relative_path
            try:
                info = require_plain_regular_file(candidate)
            except OSError as exc:
                raise StageContractError(
                    artifact_stages.get(key, "<unknown>"),
                    f"declared artifact {key!r} is not an existing plain regular "
                    f"file in the workspace: {artifact.relative_path!r}.",
                ) from exc
            producer_stage = artifact_stages.get(key)
            files.append(
                PreparedFile(
                    relative_path=artifact.relative_path,
                    expected_size=info.st_size,
                    sha256=(
                        selected[key].expected_sha256 if key in selected else None
                    ),
                    artifact_key=key,
                    content_type=artifact.content_type,
                    producer_stage=producer_stage,
                    durability_classification=(
                        "PROCESSED_SELECTED"
                        if key in selected
                        else (
                            "PROCESSED_CANDIDATE"
                            if producer_stage
                            in {_NORMALIZATION_STAGE_ID, _CROP_STAGE_ID}
                            else "EPHEMERAL"
                        )
                    ),
                )
            )
        prepared = PreparedImport(
            request=request,
            files=tuple(files),
            metadata=dict(outcome.metadata),
            processed_artifacts=processed_artifacts,
        )
        prepared.validate()
        return prepared
    except Exception:
        if processed_artifacts is not None:
            processed_artifacts.close_if_unclaimed()
        raise


def _open_candidate(
    root_handle, relative_path: str
) -> tuple[Any, tuple[Any, ...]]:
    parts = PurePosixPath(relative_path).parts
    if not parts:
        raise OSError("A prepared artifact path is empty.")
    chain = []
    parent = root_handle
    try:
        for component in parts[:-1]:
            child = open_plain_child_directory(parent, component)
            chain.append(child)
            parent = child
        handle = open_plain_child_file_readonly(parent, parts[-1])
        if not root_handle.verify_path() or any(
            not directory.verify_path() for directory in chain
        ):
            handle.close()
            raise OSError("A prepared artifact parent identity changed.")
        return handle, tuple(chain)
    except Exception:
        for directory in reversed(chain):
            directory.close()
        raise


def _close_candidate(handle, chain) -> None:
    if not handle.closed:
        handle.close()
    for directory in reversed(chain):
        directory.close()


def _read_verified_jpeg(handle, path: Path) -> tuple[bytes, int, int, str]:
    before = os.fstat(handle.fileno())
    if before.st_size < 1 or before.st_size > MAX_PROCESSED_ARTIFACT_SIZE:
        raise ValueError("A processed JPEG exceeds its byte limit.")
    handle.seek(0)
    payload = handle.read(MAX_PROCESSED_ARTIFACT_SIZE + 1)
    if len(payload) != before.st_size or len(payload) > MAX_PROCESSED_ARTIFACT_SIZE:
        raise ValueError("A processed JPEG changed or exceeds its byte limit.")
    require_complete_jpeg(payload)
    try:
        with Image.open(BytesIO(payload)) as probe:
            probe.verify()
        with Image.open(BytesIO(payload)) as image:
            if image.format != "JPEG" or image.info.get("progressive"):
                raise ValueError("A processed artifact must be a baseline JPEG.")
            width, height = image.size
            image.load()
    except (OSError, UnidentifiedImageError) as error:
        raise ValueError("A processed artifact is not a valid JPEG.") from error
    if (
        width < 1
        or height < 1
        or width > MAX_IMAGE_DIMENSION
        or height > MAX_IMAGE_DIMENSION
        or width * height > MAX_IMAGE_PIXELS
    ):
        raise ValueError("A processed JPEG exceeds its dimension limits.")
    after = os.fstat(handle.fileno())
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or not handle_matches_path(handle, path):
        raise OSError("A processed artifact changed while it was read.")
    return payload, width, height, hashlib.sha256(payload).hexdigest()


def _assemble_processed_artifacts(
    outcome: PipelineOutcome,
    workspace: Path,
    artifact_stages: Mapping[str, str],
) -> PreparedArtifactSet | None:
    records = outcome.metadata.get("crop_records")
    if records is None:
        return None
    if not isinstance(records, list) or not records:
        raise StageContractError("crop-detection", "crop_records must be non-empty.")
    crop_record_fields = {
        "coin_id",
        "role",
        "x",
        "y",
        "width",
        "height",
        "crop_confidence",
        "crop_applied",
        "source_normalized_key",
        "source_width",
        "source_height",
    }
    if any(
        not isinstance(record, dict) or set(record) != crop_record_fields
        for record in records
    ):
        raise StageContractError(
            "crop-detection", "A crop record does not match its closed schema."
        )

    root_handle = None
    selected_handles = []
    selected_chains = []
    selected_by_key = {}
    other_handles = []
    try:
        root_handle = open_plain_directory_handle(workspace)
        descriptors: list[PreparedArtifactDescriptor] = []
        seen_pairs: set[tuple[str, str]] = set()
        expected_candidate_keys: set[str] = set()
        normalized_keys = [
            key
            for key in outcome.artifacts
            if artifact_stages.get(key) == _NORMALIZATION_STAGE_ID
        ]
        cropped_keys = [
            key
            for key in outcome.artifacts
            if artifact_stages.get(key) == _CROP_STAGE_ID
        ]
        if len(normalized_keys) != len(records) or len(cropped_keys) != len(records):
            raise ValueError("Processed candidate routing is incomplete.")
        # The crop stage emits records and artifacts in the same deterministic
        # lexical order. Preserve that typed association here; durable
        # front/reverse/edge ordering is applied only to final descriptors.
        cropped_key_by_pair = {
            (record["coin_id"], record["role"]): key
            for record, key in zip(records, cropped_keys)
            if isinstance(record, dict)
        }
        if len(cropped_key_by_pair) != len(records):
            raise ValueError("Cropped candidate routing is ambiguous.")
        for raw in records:
            coin_id = raw["coin_id"]
            role = raw["role"]
            normalized_key = raw["source_normalized_key"]
            if (
                not isinstance(coin_id, str)
                or not coin_id
                or role not in _ROLE_ORDER
                or not isinstance(normalized_key, str)
                or not normalized_key
            ):
                raise ValueError("A crop record identity is invalid.")
            pair = (coin_id, role)
            if pair in seen_pairs:
                raise ValueError("Duplicate crop record.")
            seen_pairs.add(pair)
            cropped_key = cropped_key_by_pair.get(pair)
            if cropped_key is None:
                raise ValueError("A cropped candidate route is missing.")
            expected_candidate_keys.update((normalized_key, cropped_key))
            normalized = outcome.artifacts.get(normalized_key)
            cropped = outcome.artifacts.get(cropped_key)
            if normalized is None or cropped is None:
                raise ValueError("A processed candidate is missing.")
            if (
                normalized.content_type != "image/jpeg"
                or cropped.content_type != "image/jpeg"
            ):
                raise ValueError("Processed candidates must be JPEG.")
            norm_path = workspace / normalized.relative_path
            crop_path = workspace / cropped.relative_path
            norm_handle, norm_chain = _open_candidate(
                root_handle, normalized.relative_path
            )
            other_handles.append((norm_handle, norm_chain))
            crop_handle, crop_chain = _open_candidate(
                root_handle, cropped.relative_path
            )
            other_handles.append((crop_handle, crop_chain))
            norm_payload, norm_width, norm_height, norm_digest = _read_verified_jpeg(
                norm_handle, norm_path
            )
            crop_payload, crop_width, crop_height, crop_digest = _read_verified_jpeg(
                crop_handle, crop_path
            )
            applied = raw["crop_applied"]
            confidence = raw["crop_confidence"]
            integer_fields = (
                raw["x"],
                raw["y"],
                raw["width"],
                raw["height"],
                raw["source_width"],
                raw["source_height"],
            )
            if (
                not isinstance(applied, bool)
                or isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not __import__("math").isfinite(confidence)
                or not 0.0 <= confidence <= 1.0
                or applied is not (confidence >= _MIN_CROP_CONFIDENCE)
                or any(
                    isinstance(value, bool) or not isinstance(value, int)
                    for value in integer_fields
                )
                or (raw["source_width"], raw["source_height"])
                != (norm_width, norm_height)
            ):
                raise ValueError("The crop decision is inconsistent.")
            if applied:
                if (
                    raw["x"] < 0
                    or raw["y"] < 0
                    or raw["width"] < 1
                    or raw["height"] < 1
                    or raw["x"] + raw["width"] > norm_width
                    or raw["y"] + raw["height"] > norm_height
                    or (raw["width"], raw["height"]) != (crop_width, crop_height)
                ):
                    raise ValueError("The applied crop geometry is inconsistent.")
                selected_key, selected_artifact = cropped_key, cropped
                selected_handle = crop_handle
                selected_chain = crop_chain
                payload, width, height, digest = (
                    crop_payload,
                    crop_width,
                    crop_height,
                    crop_digest,
                )
            else:
                if (
                    confidence != 0.0
                    or (raw["x"], raw["y"], raw["width"], raw["height"])
                    != (0, 0, norm_width, norm_height)
                    or crop_payload != norm_payload
                    or (crop_width, crop_height, crop_digest)
                    != (norm_width, norm_height, norm_digest)
                ):
                    raise ValueError("The crop fallback is not an exact full frame.")
                selected_key, selected_artifact = normalized_key, normalized
                selected_handle = norm_handle
                selected_chain = norm_chain
                payload, width, height, digest = (
                    norm_payload,
                    norm_width,
                    norm_height,
                    norm_digest,
                )
            if selected_key in selected_by_key:
                raise ValueError("A selected artifact key is duplicated.")
            selected_handles.append(selected_handle)
            selected_chains.append(selected_chain)
            selected_by_key[selected_key] = (selected_handle, selected_chain)
            other_handles.remove((selected_handle, selected_chain))
            descriptors.append(
                PreparedArtifactDescriptor(
                    artifact_key=selected_key,
                    source_coin_id=coin_id,
                    role=role,
                    variant="CROPPED" if applied else "NORMALIZED",
                    content_type="image/jpeg",
                    expected_byte_length=len(payload),
                    expected_sha256=digest,
                    workspace_relative_path=selected_artifact.relative_path,
                    root_identity=root_handle.identity,
                    parent_identity=(
                        selected_chain[-1].identity
                        if selected_chain
                        else root_handle.identity
                    ),
                    file_identity=handle_object_identity(selected_handle),
                )
            )
        candidate_keys = {
            key
            for key in outcome.artifacts
            if artifact_stages.get(key)
            in {_NORMALIZATION_STAGE_ID, _CROP_STAGE_ID}
        }
        if candidate_keys != expected_candidate_keys:
            raise ValueError("Processed candidate inventory is inconsistent.")
        descriptors.sort(
            key=lambda value: (
                value.source_coin_id,
                _ROLE_ORDER[value.role],
                value.variant,
                value.artifact_key,
            )
        )
        # Sorting descriptors requires the corresponding handles to follow them.
        ordered_pairs = tuple(
            selected_by_key[item.artifact_key] for item in descriptors
        )
        lease = PreparedWorkspaceLease(
            workspace,
            root_handle,
            tuple(pair[0] for pair in ordered_pairs),
            tuple(pair[1] for pair in ordered_pairs),
        )
        root_handle = None
        selected_handles = []
        selected_chains = []
        return PreparedArtifactSet(tuple(descriptors), lease)
    except (StageContractError, ValueError, OSError) as error:
        if isinstance(error, StageContractError):
            raise
        raise StageContractError(
            "crop-detection", "processed artifact assembly failed."
        ) from error
    finally:
        for handle, chain in other_handles:
            _close_candidate(handle, chain)
        for handle, chain in zip(selected_handles, selected_chains):
            _close_candidate(handle, chain)
        if root_handle is not None:
            root_handle.close()


class ImportWorkflow:
    """Run a ``ProcessingPipeline`` sequentially with cancellation and events.

    One workflow instance may execute its immutable pipeline any number of
    times; execution state is local to each ``execute`` call.  Threading
    is out of scope for Sprint 7 (ADR-007).
    """

    def __init__(
        self,
        pipeline: ProcessingPipeline,
        *,
        event_bus: ImportEventBus | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        if not isinstance(pipeline, ProcessingPipeline):
            raise TypeError(
                "pipeline must be a ProcessingPipeline, not "
                f"{type(pipeline).__name__}."
            )
        self._pipeline = pipeline
        self._event_bus = event_bus
        self._is_cancelled = is_cancelled

    # -- Public execution ---------------------------------------------------

    @overload
    def execute(
        self,
        request: ImportRequest,
        workspace: Path,
        *,
        import_id: str | None = None,
        transaction: None = None,
    ) -> PipelineOutcome: ...

    @overload
    def execute(
        self,
        request: ImportRequest,
        workspace: Path,
        *,
        import_id: str | None = None,
        transaction: Callable[[PreparedImport], T],
    ) -> T: ...

    def execute(
        self,
        request: ImportRequest,
        workspace: Path,
        *,
        import_id: str | None = None,
        transaction: Callable[[PreparedImport], Any] | None = None,
    ) -> Any:
        """Run every stage exactly once in declared order.

        Args:
            request: Immutable import request (validated up front).
            workspace: Absolute path stages may write into.  Owned by the
                caller; no cleanup is performed here.
            import_id: Optional correlation id propagated to events.
            transaction: Optional durable handoff delegate.  When supplied,
                the merged outcome is assembled into a validated
                ``PreparedImport`` — the only object that crosses the
                durability boundary — and the delegate is invoked exactly
                once with it.  The delegate owns every durable side effect
                (transaction, journal, rollback, recovery); its return
                value becomes the result of this call and its exceptions
                propagate unwrapped.

        Returns:
            ``PipelineOutcome`` with merged artifacts and metadata when
            ``transaction`` is ``None``; otherwise the delegate's return
            value.

        Raises:
            TypeError: If ``transaction`` is not callable.
            ValueError: If ``request`` or ``workspace`` is malformed.
            StageContractError: If a stage violates its result contract or
                ``PreparedImport`` assembly fails.
            StageExecutionError: If a stage raises an ordinary exception.
            WorkflowCancelledError: If cancellation is requested at a
                cooperative boundary.
        """
        request.validate()
        if not isinstance(workspace, Path) or not workspace.is_absolute():
            raise ValueError("workspace must be an absolute pathlib.Path.")
        if transaction is not None and not callable(transaction):
            raise TypeError(
                "transaction must be a callable accepting a PreparedImport, "
                f"not {type(transaction).__name__}."
            )

        stages = self._pipeline.stages
        stage_count = len(stages)
        if self._event_bus is not None:
            self._event_bus.record_pipeline_started(
                import_id=import_id,
                stage_ids=self._pipeline.stage_ids,
            )

        artifacts: dict[str, StageArtifact] = {}
        artifact_stages: dict[str, str] = {}
        metadata: dict[str, JsonValue] = {}

        for index, stage in enumerate(stages):
            stage_id = stage.stage_id
            self._raise_if_cancelled(import_id, stage_id, index)
            self._record_stage_started(import_id, stage_id, index, stage_count)

            stage_input = StageInput(
                request=request,
                workspace=workspace,
                artifacts=dict(artifacts),
            )
            result = self._execute_stage(stage, stage_input, import_id, index)
            self._apply_result(result, stage_id, import_id, index, artifacts, metadata)
            for key in result.artifacts:
                artifact_stages[key] = stage_id

            self._record_stage_completed(import_id, stage_id, index)
            self._raise_if_cancelled(import_id, stage_id, index)

        outcome = PipelineOutcome(artifacts=dict(artifacts), metadata=dict(metadata))

        # Post-pipeline boundary, before any assembly or handoff work.
        self._raise_if_cancelled(import_id, None, None)

        if transaction is None:
            # Purely ephemeral execution (Unit 4 behavior, unchanged).
            if self._event_bus is not None:
                self._event_bus.record_pipeline_completed(
                    import_id=import_id,
                    stage_count=stage_count,
                )
            return outcome

        # Durable handoff: build the sole boundary object, then honour the
        # third architecture cancellation boundary immediately before the
        # delegate is invoked exactly once.
        prepared = assemble_prepared_import(request, outcome, workspace, artifact_stages)
        try:
            self._raise_if_cancelled(import_id, None, None)
            if self._event_bus is not None:
                self._event_bus.record_pipeline_completed(
                    import_id=import_id,
                    stage_count=stage_count,
                )
            return transaction(prepared)
        finally:
            if prepared.processed_artifacts is not None:
                prepared.processed_artifacts.close_if_unclaimed()

    # -- Stage execution and result contract ---------------------------------

    def _execute_stage(
        self,
        stage: ProcessingStage,
        stage_input: StageInput,
        import_id: str | None,
        index: int,
    ) -> StageResult:
        """Invoke one stage, mapping exceptions onto the failure contract."""
        stage_id = stage.stage_id
        try:
            return stage.execute(stage_input)
        except WorkflowCancelledError:
            # Cooperative cancellation signalled by the stage itself:
            # unwrapped, but still a terminal pipeline event.
            if self._event_bus is not None:
                self._event_bus.record_pipeline_cancelled(
                    import_id=import_id,
                    stage_id=stage_id,
                    stage_index=index,
                    reason=_CANCELLED_BY_STAGE,
                )
            raise
        except ImportWorkflowError as exc:
            # Already workflow-typed (e.g. StageContractError): never rewrap.
            self._record_stage_failed(import_id, stage_id, index, type(exc).__name__)
            raise
        except Exception as exc:
            self._record_stage_failed(import_id, stage_id, index, type(exc).__name__)
            raise StageExecutionError(stage_id, exc) from exc

    def _apply_result(
        self,
        result: StageResult,
        stage_id: str,
        import_id: str | None,
        index: int,
        artifacts: dict[str, StageArtifact],
        metadata: dict[str, JsonValue],
    ) -> None:
        """Validate a stage result and merge it into the accumulators.

        Raises:
            StageContractError: On non-``StageResult`` returns, model
                validation failures, or duplicate artifact/metadata keys.
        """
        if not isinstance(result, StageResult):
            self._record_stage_failed(import_id, stage_id, index, "StageContractError")
            raise StageContractError(
                stage_id,
                f"execute returned {type(result).__name__}, expected StageResult.",
            )
        try:
            self._pipeline.validate_stage_result(result, stage_id)
        except StageContractError as exc:
            self._record_stage_failed(import_id, stage_id, index, type(exc).__name__)
            raise  # Preserves the original ValueError chain.
        for key in result.artifacts:
            if key in artifacts:
                self._record_stage_failed(
                    import_id, stage_id, index, "StageContractError"
                )
                raise StageContractError(
                    stage_id,
                    f"duplicate artifact key {key!r}: already produced by an "
                    "earlier stage.",
                )
        for key in result.metadata:
            if key in metadata:
                self._record_stage_failed(
                    import_id, stage_id, index, "StageContractError"
                )
                raise StageContractError(
                    stage_id,
                    f"duplicate metadata key {key!r}: already produced by an "
                    "earlier stage.",
                )
        artifacts.update(result.artifacts)
        metadata.update(result.metadata)

    # -- Cancellation ---------------------------------------------------------

    def _raise_if_cancelled(
        self,
        import_id: str | None,
        stage_id: str | None,
        stage_index: int | None,
    ) -> None:
        """Raise WorkflowCancelledError (unwrapped) at a safe boundary.

        Cancellation is cooperative and checked only at stage boundaries
        in this layer.  Once a future transaction handoff occurs, Sprint 6
        semantics remain authoritative for the durable commit boundary.
        """
        if self._is_cancelled is not None and self._is_cancelled():
            if self._event_bus is not None:
                self._event_bus.record_pipeline_cancelled(
                    import_id=import_id,
                    stage_id=stage_id,
                    stage_index=stage_index,
                    reason=_CANCELLED_BY_CALLER,
                )
            raise WorkflowCancelledError("workflow cancelled by caller")

    # -- Event helpers ---------------------------------------------------------

    def _record_stage_started(
        self,
        import_id: str | None,
        stage_id: str,
        index: int,
        stage_count: int,
    ) -> None:
        if self._event_bus is not None:
            self._event_bus.record_stage_started(
                import_id=import_id,
                stage_id=stage_id,
                stage_index=index,
                stage_count=stage_count,
            )

    def _record_stage_completed(
        self,
        import_id: str | None,
        stage_id: str,
        index: int,
    ) -> None:
        if self._event_bus is not None:
            self._event_bus.record_stage_completed(
                import_id=import_id,
                stage_id=stage_id,
                stage_index=index,
            )

    def _record_stage_failed(
        self,
        import_id: str | None,
        stage_id: str,
        index: int,
        error_type: str,
    ) -> None:
        if self._event_bus is not None:
            self._event_bus.record_stage_failed(
                import_id=import_id,
                stage_id=stage_id,
                stage_index=index,
                error_type=error_type,
            )
