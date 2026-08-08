"""Advisory OCR metadata stage for processed workflow image artifacts.

The stage selects cropped artifacts when available, otherwise normalized
artifacts, and delegates OCR analysis through an injected provider contract.

It does not import legacy OCR modules, mutate collection data, persist OCR
results, or register itself in the production pipeline.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
import re

from inference_telemetry import scan_id_from_workspace, telemetry_scan

from .workflow_models import JsonValue, StageArtifact, StageInput, StageResult
from .workflow_obverse_reverse_pairing import _read_bounded_artifact
from .workflow_ocr_models import OCRMetadataReport
from .workflow_pipeline import StageContractError, StageExecutionError


OCR_METADATA_STAGE_ID = "ocr-metadata-extraction"

_CROPPED_PREFIX = "cropped-"
_NORMALIZED_PREFIX = "normalized-"
_SAFE_COIN_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ALLOWED_ROLES = {"front", "reverse", "edge"}


@runtime_checkable
class OCRMetadataProvider(Protocol):
    """Injected OCR service returning importer-safe advisory metadata."""

    @property
    def provider_id(self) -> str:
        ...

    def analyze(
        self,
        *,
        source_coin_id: str,
        image_role: str,
        artifact_key: str,
        image_bytes: bytes,
    ) -> OCRMetadataReport:
        ...


def _parse_artifact_key(key: str) -> tuple[str, str, str] | None:
    """Return ``(variant, coin_id, role)`` for supported image artifacts."""

    for prefix, variant in (
        (_CROPPED_PREFIX, "cropped"),
        (_NORMALIZED_PREFIX, "normalized"),
    ):
        if not key.startswith(prefix):
            continue

        parts = key[len(prefix) :].rsplit("-", 1)
        if len(parts) != 2:
            return None

        coin_id, role = parts
        if (
            _SAFE_COIN_ID.fullmatch(coin_id) is None
            or role not in _ALLOWED_ROLES
        ):
            return None

        return variant, coin_id, role

    return None


def _select_artifacts(
    artifacts: dict[str, StageArtifact],
) -> tuple[tuple[str, str, str, StageArtifact], ...]:
    """Select one deterministic OCR input for every coin/role pair.

    Cropped artifacts are preferred over normalized artifacts.
    """

    selected: dict[
        tuple[str, str],
        tuple[str, str, str, StageArtifact],
    ] = {}

    for key, artifact in artifacts.items():
        parsed = _parse_artifact_key(key)
        if parsed is None:
            continue

        variant, coin_id, role = parsed
        identity = (coin_id, role)
        existing = selected.get(identity)

        if existing is None or (
            existing[0] == "normalized" and variant == "cropped"
        ):
            selected[identity] = (
                variant,
                coin_id,
                role,
                artifact,
            )

    return tuple(
        (
            variant,
            coin_id,
            role,
            artifacts[
                f"{variant}-{coin_id}-{role}"
            ],
        )
        for variant, coin_id, role, _artifact in sorted(
            selected.values(),
            key=lambda item: (
                item[1],
                {"front": 0, "reverse": 1, "edge": 2}[item[2]],
                item[0],
            ),
        )
    )


class OCRMetadataExtractionStage:
    """Produce bounded review-only OCR metadata for processed images."""

    def __init__(
        self,
        *,
        provider: OCRMetadataProvider | None = None,
    ) -> None:
        self._provider = provider

    @property
    def stage_id(self) -> str:
        return OCR_METADATA_STAGE_ID

    def execute(self, stage_input: StageInput) -> StageResult:
        selected = _select_artifacts(dict(stage_input.artifacts))

        if not selected:
            raise StageContractError(
                self.stage_id,
                "no cropped or normalized image artifacts were available.",
            )

        if self._provider is None:
            return StageResult(
                artifacts={},
                metadata={
                    "ocr_provider_available": False,
                    "ocr_processed_image_count": 0,
                    "ocr_reports": [],
                    "ocr_review_required": True,
                },
            )

        provider_id = self._provider.provider_id
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise StageContractError(
                self.stage_id,
                "OCR provider has an invalid provider_id.",
            )

        reports: list[JsonValue] = []

        for variant, coin_id, role, artifact in selected:
            if artifact.content_type != "image/jpeg":
                raise StageContractError(
                    self.stage_id,
                    f"selected OCR artifact {coin_id!r}/{role!r} "
                    "must be image/jpeg.",
                )

            payload = _read_bounded_artifact(
                stage_input.workspace,
                __import__("pathlib").Path(artifact.relative_path),
                stage_id=self.stage_id,
                label=f"OCR {variant} artifact ({coin_id}/{role})",
            )

            artifact_key = f"{variant}-{coin_id}-{role}"

            try:
                with telemetry_scan(
                    scan_id_from_workspace(stage_input.workspace)
                ):
                    report = self._provider.analyze(
                        source_coin_id=coin_id,
                        image_role=role,
                        artifact_key=artifact_key,
                        image_bytes=payload,
                    )
            except StageContractError:
                raise
            except Exception as exc:
                raise StageExecutionError(
                    self.stage_id,
                    exc,
                ) from exc

            if not isinstance(report, OCRMetadataReport):
                raise StageContractError(
                    self.stage_id,
                    "OCR provider returned an unsupported report type.",
                )

            try:
                report.validate()
            except ValueError as exc:
                raise StageContractError(
                    self.stage_id,
                    "OCR provider returned an invalid metadata report.",
                ) from exc

            report_payload = report.to_dict()
            report_payload["selected_variant"] = variant
            reports.append(report_payload)

        return StageResult(
            artifacts={},
            metadata={
                "ocr_provider_available": True,
                "ocr_provider_id": provider_id,
                "ocr_processed_image_count": len(reports),
                "ocr_reports": reports,
                "ocr_review_required": True,
            },
        )
