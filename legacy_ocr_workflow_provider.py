"""Legacy OCR provider bridge for the workflow OCR stage.

This module is an application-layer adapter. It connects the immutable
workflow OCR provider contract to the existing OCRExperiment,
OCRValidationEngine, and OCRWorkflowAdapter implementations.

The provider is opt-in:
- no production pipeline registration occurs here;
- no collection mutation or persistence occurs;
- Tesseract remains optional;
- deterministic raw-text injection is supported for tests and controlled use.
"""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO
from pathlib import Path
import tempfile
from typing import Optional

from PIL import Image, UnidentifiedImageError

from capture_import.workflow_ocr_models import OCRMetadataReport
from capture_import.workflow_ocr_cleanup_diagnostics import (
    OCRProviderCleanupDiagnostic,
    OCRProviderCleanupDiagnosticSeverity,
)
from capture_import.workflow_ocr_provider_contracts import (
    OCRProviderCapabilities,
)
from capture_import.workflow_pipeline import StageContractError
from ocr_experiment import OCRExperiment
from ocr_validation import OCRValidationEngine
from ocr_workflow_adapter import OCRWorkflowAdapter


RawTextResolver = Callable[[str, str, str, bytes], Optional[str]]
CleanupDiagnosticSink = Callable[[OCRProviderCleanupDiagnostic], None]


class LegacyOCRWorkflowProvider:
    """Bridge processed image bytes into the legacy advisory OCR stack."""

    def __init__(
        self,
        *,
        experiment: OCRExperiment | None = None,
        validation_engine: OCRValidationEngine | None = None,
        adapter: OCRWorkflowAdapter | None = None,
        raw_text_resolver: RawTextResolver | None = None,
        cleanup_capabilities: OCRProviderCapabilities | None = None,
        cleanup_diagnostic_sink: CleanupDiagnosticSink | None = None,
    ) -> None:
        if (cleanup_capabilities is None) != (
            cleanup_diagnostic_sink is None
        ):
            raise ValueError(
                "cleanup_capabilities and cleanup_diagnostic_sink "
                "must be supplied together."
            )
        if cleanup_capabilities is not None:
            if not isinstance(
                cleanup_capabilities,
                OCRProviderCapabilities,
            ):
                raise TypeError(
                    "cleanup_capabilities must be OCRProviderCapabilities."
                )
            cleanup_capabilities.validate()
            if cleanup_capabilities.provider_id != self.provider_id:
                raise ValueError(
                    "cleanup capabilities must describe legacy-ocr."
                )
        if (
            cleanup_diagnostic_sink is not None
            and not callable(cleanup_diagnostic_sink)
        ):
            raise TypeError("cleanup_diagnostic_sink must be callable.")
        self._experiment = experiment or OCRExperiment()
        self._validation_engine = (
            validation_engine or OCRValidationEngine()
        )
        self._adapter = adapter or OCRWorkflowAdapter()
        self._raw_text_resolver = raw_text_resolver
        self._cleanup_capabilities = cleanup_capabilities
        self._cleanup_diagnostic_sink = cleanup_diagnostic_sink

    @property
    def provider_id(self) -> str:
        return "legacy-ocr"

    def analyze(
        self,
        *,
        source_coin_id: str,
        image_role: str,
        artifact_key: str,
        image_bytes: bytes,
    ) -> OCRMetadataReport:
        self._validate_image_bytes(image_bytes)

        raw_text = None
        if self._raw_text_resolver is not None:
            raw_text = self._raw_text_resolver(
                source_coin_id,
                image_role,
                artifact_key,
                image_bytes,
            )
            if raw_text is not None and not isinstance(raw_text, str):
                raise StageContractError(
                    "ocr-metadata-extraction",
                    "raw_text_resolver must return str or None.",
                )

        if raw_text is not None:
            suggestion = self._experiment.run(
                image_path="",
                raw_text=raw_text,
                engine=self.provider_id,
            )
        else:
            suggestion = self._run_with_temporary_image(
                image_bytes,
                artifact_key=artifact_key,
            )

        validation = self._validation_engine.validate(
            suggestion_report=suggestion
        )

        report = self._adapter.adapt(
            source_coin_id=source_coin_id,
            image_role=image_role,
            artifact_key=artifact_key,
            suggestion_report=suggestion,
            validation_report=validation,
        )
        report.validate()
        return report

    def _run_with_temporary_image(
        self,
        image_bytes: bytes,
        *,
        artifact_key: str,
    ):
        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".jpg",
                delete=False,
            ) as handle:
                handle.write(image_bytes)
                handle.flush()
                temporary_path = Path(handle.name)

            return self._experiment.run(
                image_path=str(temporary_path),
                raw_text=None,
                engine=self.provider_id,
            )
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    if self._cleanup_diagnostic_sink is not None:
                        self._publish_cleanup_diagnostic(
                            artifact_key=artifact_key,
                        )

    def _publish_cleanup_diagnostic(self, *, artifact_key: str) -> None:
        """Publish one advisory warning without endangering valid OCR output."""

        try:
            self._cleanup_diagnostic_sink(
                OCRProviderCleanupDiagnostic(
                    provider=self._cleanup_capabilities,
                    severity=OCRProviderCleanupDiagnosticSeverity.WARNING,
                    diagnostic_code="TEMPORARY_IMAGE_DELETE_FAILED",
                    artifact_key=artifact_key,
                )
            )
        except Exception:
            # The sink is advisory.  Its failure must not replace valid OCR
            # evidence or expose arbitrary callback exception text.
            pass

    @staticmethod
    def _validate_image_bytes(image_bytes: bytes) -> None:
        if not isinstance(image_bytes, bytes) or not image_bytes:
            raise StageContractError(
                "ocr-metadata-extraction",
                "OCR image payload must be non-empty bytes.",
            )

        try:
            with Image.open(BytesIO(image_bytes)) as image:
                if image.format != "JPEG":
                    raise StageContractError(
                        "ocr-metadata-extraction",
                        "OCR provider requires JPEG image bytes.",
                    )
                image.verify()
        except StageContractError:
            raise
        except (
            OSError,
            SyntaxError,
            UnidentifiedImageError,
            ValueError,
        ) as exc:
            raise StageContractError(
                "ocr-metadata-extraction",
                "OCR provider received invalid JPEG image bytes.",
            ) from exc
