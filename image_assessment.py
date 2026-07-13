"""Deterministic image readiness assessment for downstream analysis.

Level A only: file checks, basic image metrics, role coverage, and explainable
downstream permissions. This module does not identify, OCR, grade, mutate,
move files, call external APIs, or perform advanced computer vision.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np

from coin_collection import CoinItem, ItemPhoto, PhotoRole
from photo_vault import SUPPORTED_PHOTO_EXTENSIONS


DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00"


class ImageReadinessDecision(str, Enum):
    READY = "READY"
    MAYBE = "MAYBE"
    NOT_READY = "NOT_READY"


class ImageAssessmentConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DownstreamUse(str, Enum):
    BROAD_IDENTIFICATION = "BROAD_IDENTIFICATION"
    OCR = "OCR"
    VARIETY_ATTRIBUTION = "VARIETY_ATTRIBUTION"
    GRADE_ESTIMATION = "GRADE_ESTIMATION"
    SUBMISSION_READINESS = "SUBMISSION_READINESS"


class DownstreamPermission(str, Enum):
    YES = "YES"
    MAYBE = "MAYBE"
    NO = "NO"


class ImageIssueSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


FRONT_ROLES = {PhotoRole.FRONT}
BACK_ROLES = {PhotoRole.BACK}
LABEL_ROLES = {PhotoRole.HOLDER_FRONT, PhotoRole.HOLDER_BACK, PhotoRole.CERT_LABEL}
DETAIL_ROLES = {PhotoRole.DETAIL, PhotoRole.EDGE}


@dataclass
class PhotoQualityAssessment:
    photo_id: str = ""
    path: str = ""
    role: str = PhotoRole.OTHER.value
    readiness_score: int = 0
    decision: ImageReadinessDecision = ImageReadinessDecision.NOT_READY
    confidence: ImageAssessmentConfidence = ImageAssessmentConfidence.LOW
    strengths: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    blocking_issues: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    permitted_uses: Dict[str, DownstreamPermission] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = DETERMINISTIC_GENERATED_AT
    engine_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "photo_id": self.photo_id,
            "path": self.path,
            "role": self.role,
            "readiness_score": self.readiness_score,
            "decision": self.decision.value,
            "confidence": self.confidence.value,
            "strengths": list(self.strengths),
            "issues": list(self.issues),
            "blocking_issues": list(self.blocking_issues),
            "recommended_actions": list(self.recommended_actions),
            "permitted_uses": {key: value.value for key, value in self.permitted_uses.items()},
            "metrics": dict(self.metrics),
            "generated_at": self.generated_at,
            "engine_errors": list(self.engine_errors),
        }


@dataclass
class PhotoSetReadinessReport:
    item_id: str = ""
    candidate_id: str = ""
    overall_readiness_score: int = 0
    decision: ImageReadinessDecision = ImageReadinessDecision.NOT_READY
    confidence: ImageAssessmentConfidence = ImageAssessmentConfidence.LOW
    photo_assessments: List[PhotoQualityAssessment] = field(default_factory=list)
    required_roles_present: Dict[str, bool] = field(default_factory=dict)
    missing_roles: List[str] = field(default_factory=list)
    downstream_permissions: Dict[str, DownstreamPermission] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    blocking_issues: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    generated_at: str = DETERMINISTIC_GENERATED_AT
    engine_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "candidate_id": self.candidate_id,
            "overall_readiness_score": self.overall_readiness_score,
            "decision": self.decision.value,
            "confidence": self.confidence.value,
            "photo_assessments": [assessment.to_dict() for assessment in self.photo_assessments],
            "required_roles_present": dict(self.required_roles_present),
            "missing_roles": list(self.missing_roles),
            "downstream_permissions": {
                key: value.value for key, value in self.downstream_permissions.items()
            },
            "evidence": list(self.evidence),
            "blocking_issues": list(self.blocking_issues),
            "recommended_actions": list(self.recommended_actions),
            "generated_at": self.generated_at,
            "engine_errors": list(self.engine_errors),
        }


@dataclass
class _PhotoInput:
    photo_id: str
    path: str
    role: PhotoRole
    raw_role: str
    malformed_role: bool = False
    missing_role: bool = False


class ImageAssessmentEngine:
    """Assess photo readiness using deterministic Level A checks only."""

    min_tiny_dimension = 300
    min_good_dimension = 800
    very_low_sharpness = 20.0
    moderate_blur_sharpness = 80.0
    low_contrast = 20.0
    underexposed_brightness = 45.0
    overexposed_brightness = 215.0
    blown_highlight_ratio = 0.12

    def __init__(self, generated_at: str = DETERMINISTIC_GENERATED_AT):
        self.generated_at = str(generated_at or DETERMINISTIC_GENERATED_AT)

    def assess_photo(self, photo: Any) -> PhotoQualityAssessment:
        return self._assess_photo_input(self._coerce_photo(photo, 0))

    def assess_paths(self, paths: Iterable[str]) -> PhotoSetReadinessReport:
        photos = [ItemPhoto(path=str(path or ""), role=PhotoRole.OTHER, display_order=index) for index, path in enumerate(paths or [])]
        return self.assess_photos(photos)

    def assess_item(self, item: CoinItem, certified_expected: bool = False) -> PhotoSetReadinessReport:
        if not item:
            return self.assess_photos([], certified_expected=certified_expected)
        return self.assess_photos(
            item.normalized_photos(),
            item_id=getattr(item, "id", ""),
            certified_expected=certified_expected,
        )

    def assess_photos(
        self,
        photos: Iterable[Any],
        item_id: str = "",
        candidate_id: str = "",
        certified_expected: bool = False,
    ) -> PhotoSetReadinessReport:
        inputs = [self._coerce_photo(photo, index) for index, photo in enumerate(photos or [])]
        duplicate_paths = self._duplicate_path_keys(inputs)
        assessments = []
        for photo_input in inputs:
            assessment = self._assess_photo_input(photo_input)
            if self._path_key(photo_input.path) in duplicate_paths:
                assessment.issues.append("Duplicate photo reference in this set.")
                assessment.recommended_actions.append("Remove duplicate photo references before downstream analysis.")
                assessment.readiness_score = max(0, assessment.readiness_score - 5)
                assessment.decision = self._decision_for_score(assessment.readiness_score, assessment.blocking_issues)
            assessments.append(assessment)
        return self._aggregate_photo_set(
            assessments,
            item_id=str(item_id or ""),
            candidate_id=str(candidate_id or ""),
            certified_expected=bool(certified_expected),
            duplicate_count=sum(max(0, len(paths) - 1) for paths in duplicate_paths.values()),
        )

    def _assess_photo_input(self, photo: _PhotoInput) -> PhotoQualityAssessment:
        strengths: List[str] = []
        issues: List[str] = []
        blocking: List[str] = []
        actions: List[str] = []
        errors: List[str] = []
        metrics: Dict[str, Any] = {}
        score = 100

        path = photo.path
        extension = os.path.splitext(path)[1].lower()
        if not path:
            return self._fatal_photo(photo, "Missing photo path.", "Attach a readable image file.")
        if extension not in SUPPORTED_PHOTO_EXTENSIONS:
            issues.append(f"Unsupported image format: {extension or 'none'}.")
            actions.append("Use a supported image format such as JPG, PNG, WEBP, BMP, or TIFF.")
            score = min(score, 20)
        else:
            strengths.append("Image format is supported.")
        if not os.path.exists(path):
            return self._fatal_photo(photo, "Image file is missing.", "Check the path or wait for cloud sync.")
        if not os.path.isfile(path):
            return self._fatal_photo(photo, "Photo path is not a file.", "Choose a readable image file.")
        try:
            size = os.path.getsize(path)
        except OSError as exc:
            return self._fatal_photo(photo, "Image file is inaccessible.", "Check file permissions or cloud sync.", str(exc))
        metrics["file_size_bytes"] = int(size)
        if size == 0:
            return self._fatal_photo(photo, "Image file is zero bytes.", "Wait for sync or replace the image file.")

        if photo.missing_role:
            issues.append("Photo role is missing.")
            actions.append("Assign a photo role such as FRONT, BACK, DETAIL, or CERT_LABEL.")
            score = min(score, 85)
        elif photo.malformed_role:
            issues.append(f"Photo role is not recognized: {photo.raw_role}.")
            actions.append("Review and relabel the photo role.")
            score -= 5
        else:
            strengths.append(f"Photo role is {photo.role.value}.")

        if extension in SUPPORTED_PHOTO_EXTENSIONS:
            image, read_error = self._read_image(path)
            if image is None:
                return self._fatal_photo(photo, "Image file could not be decoded.", "Replace or re-export the image file.", read_error)
            image_metrics = self._image_metrics(image)
            metrics.update(image_metrics)
            score = self._apply_image_metric_scoring(score, image_metrics, strengths, issues, actions)
        else:
            blocking.append("Unsupported image format blocks reliable image-quality checks.")

        score = max(0, min(100, int(round(score))))
        decision = self._decision_for_score(score, blocking)
        confidence = self._photo_confidence(metrics, issues, blocking)
        return PhotoQualityAssessment(
            photo_id=photo.photo_id,
            path=path,
            role=photo.role.value,
            readiness_score=score,
            decision=decision,
            confidence=confidence,
            strengths=self._dedupe(strengths),
            issues=self._dedupe(issues),
            blocking_issues=self._dedupe(blocking),
            recommended_actions=self._dedupe(actions),
            permitted_uses=self._photo_permissions(score, blocking),
            metrics=metrics,
            generated_at=self.generated_at,
            engine_errors=self._dedupe(errors),
        )

    def _apply_image_metric_scoring(
        self,
        score: int,
        metrics: Dict[str, Any],
        strengths: List[str],
        issues: List[str],
        actions: List[str],
    ) -> int:
        width = metrics["width"]
        height = metrics["height"]
        minimum_dimension = min(width, height)
        if minimum_dimension < self.min_tiny_dimension:
            score -= 35
            issues.append("Image resolution is extremely small.")
            actions.append("Retake or export a higher-resolution photo.")
        elif minimum_dimension < self.min_good_dimension:
            score -= 15
            issues.append("Image resolution is limited.")
            actions.append("Use a higher-resolution photo for detailed analysis.")
        else:
            strengths.append("Image resolution is sufficient for Level A checks.")

        sharpness = metrics["sharpness"]
        if sharpness < self.very_low_sharpness:
            score -= 30
            issues.append("Image appears very blurred by the sharpness heuristic.")
            actions.append("Retake the photo with steadier focus.")
        elif sharpness < self.moderate_blur_sharpness:
            score -= 15
            issues.append("Image appears moderately blurred by the sharpness heuristic.")
            actions.append("Retake the photo if detailed analysis is needed.")
        else:
            strengths.append("Sharpness is acceptable for Level A checks.")

        contrast = metrics["contrast"]
        if contrast < self.low_contrast:
            score -= 15
            issues.append("Image contrast is low.")
            actions.append("Retake with more even lighting or better contrast.")
        else:
            strengths.append("Contrast is acceptable.")

        brightness = metrics["brightness"]
        if brightness < self.underexposed_brightness:
            score -= 20
            issues.append("Image appears underexposed.")
            actions.append("Retake with more light.")
        elif brightness > self.overexposed_brightness:
            score -= 20
            issues.append("Image appears overexposed.")
            actions.append("Retake with less direct light.")
        else:
            strengths.append("Brightness is within the usable range.")

        if metrics["blown_highlight_ratio"] > self.blown_highlight_ratio:
            score -= 15
            issues.append("Image has a high ratio of blown highlights.")
            actions.append("Retake at an angle or with softer lighting to reduce glare.")
        return score

    def _aggregate_photo_set(
        self,
        assessments: List[PhotoQualityAssessment],
        item_id: str,
        candidate_id: str,
        certified_expected: bool,
        duplicate_count: int,
    ) -> PhotoSetReadinessReport:
        evidence: List[str] = []
        blocking: List[str] = []
        actions: List[str] = []
        errors: List[str] = []
        permissions = self._empty_permissions(DownstreamPermission.NO)
        required_roles = {"front": False, "back": False, "label": False, "detail": False}

        if not assessments:
            blocking.append("No photos are attached for assessment.")
            actions.append("Attach at least front and back photos.")
            return PhotoSetReadinessReport(
                item_id=item_id,
                candidate_id=candidate_id,
                overall_readiness_score=0,
                decision=ImageReadinessDecision.NOT_READY,
                confidence=ImageAssessmentConfidence.LOW,
                photo_assessments=[],
                required_roles_present=required_roles,
                missing_roles=["front", "back"],
                downstream_permissions=permissions,
                evidence=[],
                blocking_issues=blocking,
                recommended_actions=actions,
                generated_at=self.generated_at,
                engine_errors=[],
            )

        valid = [assessment for assessment in assessments if not assessment.blocking_issues]
        usable = [assessment for assessment in assessments if assessment.readiness_score >= 50 and not assessment.blocking_issues]
        roles = {PhotoRole.normalize(assessment.role) for assessment in assessments}
        required_roles["front"] = bool(roles & FRONT_ROLES)
        required_roles["back"] = bool(roles & BACK_ROLES)
        required_roles["label"] = bool(roles & LABEL_ROLES)
        required_roles["detail"] = bool(roles & DETAIL_ROLES)
        missing_roles = [
            role for role in ["front", "back"]
            if not required_roles[role]
        ]
        if certified_expected and not required_roles["label"]:
            missing_roles.append("certification label")

        if valid:
            score = int(round(sum(assessment.readiness_score for assessment in valid) / len(valid)))
        else:
            score = 0
        if len(assessments) == 1:
            score -= 25
            evidence.append("Only one photo is available.")
            actions.append("Add the missing side of the collectible.")
        if not required_roles["front"]:
            score -= 20
            blocking.append("No front or obverse photo is present.")
            actions.append("Add a front or obverse photo.")
        else:
            evidence.append("Front or obverse photo is present.")
        if not required_roles["back"]:
            score -= 20
            blocking.append("No back or reverse photo is present.")
            actions.append("Add a back or reverse photo.")
        else:
            evidence.append("Back or reverse photo is present.")
        if duplicate_count:
            score -= min(15, duplicate_count * 5)
            evidence.append(f"Duplicate photo references detected: {duplicate_count}.")
            actions.append("Remove duplicate photo references.")
        if certified_expected and not required_roles["label"]:
            score -= 20
            blocking.append("Certified item is missing a holder or certification-label photo.")
            actions.append("Add a holder or certification-label photo.")

        for assessment in assessments:
            errors.extend(assessment.engine_errors)
            blocking.extend(assessment.blocking_issues)
        score = max(0, min(100, score))
        permissions = self._set_permissions(score, usable, required_roles, certified_expected)
        decision = self._set_decision(score, permissions, blocking)
        confidence = self._set_confidence(assessments, missing_roles, blocking)
        return PhotoSetReadinessReport(
            item_id=item_id,
            candidate_id=candidate_id,
            overall_readiness_score=score,
            decision=decision,
            confidence=confidence,
            photo_assessments=assessments,
            required_roles_present=required_roles,
            missing_roles=missing_roles,
            downstream_permissions=permissions,
            evidence=self._dedupe(evidence),
            blocking_issues=self._dedupe(blocking),
            recommended_actions=self._dedupe(actions + [
                action
                for assessment in assessments
                for action in assessment.recommended_actions
                if assessment.decision != ImageReadinessDecision.READY
            ]),
            generated_at=self.generated_at,
            engine_errors=self._dedupe(errors),
        )

    def _set_permissions(
        self,
        score: int,
        usable: List[PhotoQualityAssessment],
        roles: Dict[str, bool],
        certified_expected: bool,
    ) -> Dict[str, DownstreamPermission]:
        permissions = self._empty_permissions(DownstreamPermission.NO)
        has_front_back = roles["front"] and roles["back"]
        if usable:
            permissions[DownstreamUse.BROAD_IDENTIFICATION.value] = (
                DownstreamPermission.YES if has_front_back and score >= 70 else DownstreamPermission.MAYBE
            )
            permissions[DownstreamUse.OCR.value] = (
                DownstreamPermission.YES if score >= 80 else DownstreamPermission.MAYBE
            )
        if has_front_back and roles["detail"] and score >= 80:
            permissions[DownstreamUse.VARIETY_ATTRIBUTION.value] = DownstreamPermission.YES
        elif has_front_back and score >= 70:
            permissions[DownstreamUse.VARIETY_ATTRIBUTION.value] = DownstreamPermission.MAYBE
        if has_front_back and score >= 80:
            permissions[DownstreamUse.GRADE_ESTIMATION.value] = DownstreamPermission.YES
        elif has_front_back and score >= 60:
            permissions[DownstreamUse.GRADE_ESTIMATION.value] = DownstreamPermission.MAYBE
        label_ok = (not certified_expected) or roles["label"]
        if has_front_back and label_ok and score >= 85:
            permissions[DownstreamUse.SUBMISSION_READINESS.value] = DownstreamPermission.YES
        elif has_front_back and label_ok and score >= 70:
            permissions[DownstreamUse.SUBMISSION_READINESS.value] = DownstreamPermission.MAYBE
        return permissions

    def _set_decision(
        self,
        score: int,
        permissions: Dict[str, DownstreamPermission],
        blocking: List[str],
    ) -> ImageReadinessDecision:
        if score < 50 or all(value == DownstreamPermission.NO for value in permissions.values()):
            return ImageReadinessDecision.NOT_READY
        if score >= 80 and not blocking and any(value == DownstreamPermission.YES for value in permissions.values()):
            return ImageReadinessDecision.READY
        return ImageReadinessDecision.MAYBE

    def _set_confidence(
        self,
        assessments: List[PhotoQualityAssessment],
        missing_roles: List[str],
        blocking: List[str],
    ) -> ImageAssessmentConfidence:
        if blocking or any(assessment.confidence == ImageAssessmentConfidence.LOW for assessment in assessments):
            return ImageAssessmentConfidence.LOW
        if missing_roles or any(assessment.confidence == ImageAssessmentConfidence.MEDIUM for assessment in assessments):
            return ImageAssessmentConfidence.MEDIUM
        return ImageAssessmentConfidence.HIGH

    def _fatal_photo(
        self,
        photo: _PhotoInput,
        issue: str,
        action: str,
        error: str = "",
    ) -> PhotoQualityAssessment:
        return PhotoQualityAssessment(
            photo_id=photo.photo_id,
            path=photo.path,
            role=photo.role.value,
            readiness_score=0,
            decision=ImageReadinessDecision.NOT_READY,
            confidence=ImageAssessmentConfidence.LOW,
            strengths=[],
            issues=[],
            blocking_issues=[issue],
            recommended_actions=[action],
            permitted_uses=self._empty_permissions(DownstreamPermission.NO),
            metrics={},
            generated_at=self.generated_at,
            engine_errors=[error] if error else [],
        )

    @staticmethod
    def _decision_for_score(score: int, blocking: List[str]) -> ImageReadinessDecision:
        if blocking or score < 50:
            return ImageReadinessDecision.NOT_READY
        if score >= 80:
            return ImageReadinessDecision.READY
        return ImageReadinessDecision.MAYBE

    @staticmethod
    def _photo_confidence(
        metrics: Dict[str, Any],
        issues: List[str],
        blocking: List[str],
    ) -> ImageAssessmentConfidence:
        if blocking or not metrics:
            return ImageAssessmentConfidence.LOW
        if issues:
            return ImageAssessmentConfidence.MEDIUM
        return ImageAssessmentConfidence.HIGH

    def _photo_permissions(
        self,
        score: int,
        blocking: List[str],
    ) -> Dict[str, DownstreamPermission]:
        if blocking or score < 50:
            return self._empty_permissions(DownstreamPermission.NO)
        if score >= 80:
            return self._empty_permissions(DownstreamPermission.YES)
        return self._empty_permissions(DownstreamPermission.MAYBE)

    @staticmethod
    def _empty_permissions(value: DownstreamPermission) -> Dict[str, DownstreamPermission]:
        return {use.value: value for use in DownstreamUse}

    def _coerce_photo(self, photo: Any, index: int) -> _PhotoInput:
        if isinstance(photo, ItemPhoto):
            return _PhotoInput(
                photo_id=str(index),
                path=photo.path,
                role=PhotoRole.normalize(photo.role),
                raw_role=PhotoRole.normalize(photo.role).value,
            )
        if isinstance(photo, str):
            return _PhotoInput(
                photo_id=str(index),
                path=photo,
                role=PhotoRole.OTHER,
                raw_role="",
                missing_role=True,
            )
        if isinstance(photo, dict):
            raw_role = str(photo.get("role") or photo.get("photo_role") or "").strip()
            normalized = PhotoRole.normalize(raw_role)
            return _PhotoInput(
                photo_id=str(photo.get("photo_id") or photo.get("id") or index),
                path=str(photo.get("path") or photo.get("file_path") or "").strip(),
                role=normalized,
                raw_role=raw_role,
                missing_role=not raw_role,
                malformed_role=bool(raw_role and raw_role.upper().replace(" ", "_").replace("-", "_") not in {role.value for role in PhotoRole}),
            )
        path = str(getattr(photo, "path", "") or getattr(photo, "file_path", "") or "").strip()
        raw_role = str(getattr(photo, "role", "") or getattr(photo, "photo_role", "") or "").strip()
        normalized = PhotoRole.normalize(raw_role)
        return _PhotoInput(
            photo_id=str(getattr(photo, "photo_id", "") or getattr(photo, "id", "") or index),
            path=path,
            role=normalized,
            raw_role=raw_role,
            missing_role=not raw_role,
            malformed_role=bool(raw_role and raw_role.upper().replace(" ", "_").replace("-", "_") not in {role.value for role in PhotoRole}),
        )

    @staticmethod
    def _read_image(path: str) -> Tuple[Optional[np.ndarray], str]:
        try:
            image = cv2.imread(path)
            if image is None:
                return None, ""
            return image, ""
        except Exception as exc:
            return None, str(exc)

    @staticmethod
    def _image_metrics(image: np.ndarray) -> Dict[str, Any]:
        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        sharpness = float(np.var(cv2.Laplacian(gray, cv2.CV_64F)))
        contrast = float(np.std(gray))
        brightness = float(np.mean(gray))
        blown = float(np.mean(gray >= 245))
        return {
            "width": int(width),
            "height": int(height),
            "orientation": "LANDSCAPE" if width > height else "PORTRAIT" if height > width else "SQUARE",
            "sharpness": round(sharpness, 3),
            "contrast": round(contrast, 3),
            "brightness": round(brightness, 3),
            "blown_highlight_ratio": round(blown, 5),
        }

    @classmethod
    def _duplicate_path_keys(cls, photos: List[_PhotoInput]) -> Dict[str, List[str]]:
        grouped: Dict[str, List[str]] = {}
        for photo in photos:
            key = cls._path_key(photo.path)
            if key:
                grouped.setdefault(key, []).append(photo.path)
        return {key: paths for key, paths in grouped.items() if len(paths) > 1}

    @staticmethod
    def _path_key(path: str) -> str:
        return os.path.normcase(os.path.abspath(str(path or "").strip())) if path else ""

    @staticmethod
    def _dedupe(values: Iterable[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            text = str(value or "").strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                result.append(text)
        return result
