"""Allowlisted adapter for the unchanged legacy ``CoinRecognizer``."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from legacy_recognition_orchestration import (
    LEGACY_COIN_RECOGNITION,
    RecognitionCapabilityResult,
)


class LegacyCoinRecognitionCapability:
    name = LEGACY_COIN_RECOGNITION

    def __init__(self, recognizer_factory: Callable[[], Any] | None = None) -> None:
        self._recognizer_factory = recognizer_factory

    def execute(self, image_reference: str) -> RecognitionCapabilityResult:
        try:
            output = self._recognizer().detect_coin(image_reference)
        except Exception as error:
            return RecognitionCapabilityResult(
                capability=self.name,
                success=False,
                warnings=(f"Coin recognizer failed: {error.__class__.__name__}.",),
                source_metadata={"legacy_error": str(error)},
                failure_category=error.__class__.__name__,
            )
        try:
            success = output["success"]
        except Exception as error:
            return RecognitionCapabilityResult(
                capability=self.name,
                success=False,
                warnings=(f"Coin recognizer result failed: {error.__class__.__name__}.",),
                source_metadata={"legacy_error": str(error)},
                failure_category=error.__class__.__name__,
            )
        if not isinstance(output, Mapping):
            error = TypeError("Coin recognizer result must be a mapping.")
            return RecognitionCapabilityResult(
                capability=self.name,
                success=False,
                warnings=("Coin recognizer result failed: TypeError.",),
                source_metadata={"legacy_error": str(error)},
                failure_category="TypeError",
            )
        if not success:
            legacy_error = output.get("error", "Detection failed")
            return RecognitionCapabilityResult(
                capability=self.name,
                success=False,
                warnings=(str(legacy_error),),
                source_metadata={"legacy_error": legacy_error},
                failure_category="detector_failure",
            )

        findings = {
            "country": output.get("country", "Unknown"),
            "denomination": output.get("denomination", "Unknown"),
            "year": output.get("year", "Unknown"),
        }
        warnings = tuple(
            f"Detector did not produce a usable {name} finding."
            for name, value in findings.items()
            if value is None or str(value).strip().casefold() in {"", "unknown", "none"}
        )
        evidence = []
        if output.get("orientation"):
            evidence.append("Detector reported an image orientation.")
        year_candidates = output.get("year_candidates")
        if isinstance(year_candidates, list):
            evidence.append(f"Detector reported {len(year_candidates)} year candidates.")
        metadata = {
            name: output[name]
            for name in (
                "denomination_confidence",
                "year_confidence",
                "country_confidence",
            )
            if name in output
        }
        return RecognitionCapabilityResult(
            capability=self.name,
            success=True,
            findings=findings,
            confidence=None,
            evidence=tuple(evidence),
            warnings=warnings,
            source_metadata=metadata,
        )

    def _recognizer(self) -> Any:
        if self._recognizer_factory is not None:
            return self._recognizer_factory()
        from coin_recognition import CoinRecognizer

        return CoinRecognizer()


def to_legacy_detector_result(
    result: RecognitionCapabilityResult,
) -> dict[str, object]:
    """Restore the exact dictionary shape historically observed by the GUI."""

    if result.success:
        return {
            "success": True,
            "country": result.findings.get("country", "Unknown"),
            "denomination": result.findings.get("denomination", "Unknown"),
            "year": result.findings.get("year", "Unknown"),
            "confidence": result.source_metadata.get("denomination_confidence", 0.0),
            "year_confidence": result.source_metadata.get("year_confidence", 0.0),
            "method": "coin_recognition",
        }
    return {
        "success": False,
        "error": result.source_metadata.get("legacy_error", "Detection failed"),
        "country": "Unknown",
        "denomination": "Unknown",
        "year": "Unknown",
        "confidence": 0.0,
        "method": "coin_recognition",
    }
