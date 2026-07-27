"""Tests for the reviewed-OCR to confirmed-observation boundary."""
from __future__ import annotations

import ast
import inspect
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from capture_import.workflow_confirmed_observation_mapper import (
    ConfirmedObservationMapper,
    ConfirmedObservationMappingInput,
    DuplicateConfirmedObservationFieldError,
    IncompleteConfirmedObservationSourceError,
    MalformedConfirmedObservationSourceError,
    MissingConfirmedObservationProvenanceError,
    UnsupportedConfirmedObservationFieldError,
    map_review_session,
)
from capture_import.workflow_ocr_conflict_resolution import (
    OCRConflictResolutionDecision,
    OCRConflictResolutionRequest,
)
from capture_import.workflow_ocr_consolidation import (
    OCRMetadataConsolidationService,
)
from capture_import.workflow_confirmed_observation_models import (
    CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION,
    ConfirmedObservationSource,
)
from capture_import.workflow_ocr_models import (
    ALLOWED_OCR_FIELDS,
    OCRFieldCandidate,
    OCRMetadataReport,
)
from capture_import.workflow_ocr_review_models import (
    OCRFieldReview,
    OCRReportReview,
    OCRReviewDecision,
)
from capture_import.workflow_ocr_review_service import (
    OCRReviewMode,
    OCRReviewReconciliationService,
)
from capture_import.workflow_ocr_review_session import (
    OCRReviewSessionConflictResolutionRequest,
    OCRReviewSessionRequest,
    OCRReviewSessionResult,
    OCRReviewSessionService,
)


def _candidate(*, source_coin_id="coin-1", field_name="year", value="1967",
               image_role="front", artifact_key="crop-front",
               confidence_score=91.5, evidence=("clear digits",)):
    return OCRFieldCandidate(
        source_coin_id=source_coin_id, image_role=image_role,
        artifact_key=artifact_key, provider_id="test-ocr",
        field_name=field_name, raw_text=value, normalized_value=value,
        confidence_score=confidence_score, evidence=evidence,
    )


def _report(*candidates):
    return OCRMetadataReport(
        provider_available=True,
        candidates=tuple(sorted(candidates, key=lambda item: (
            item.source_coin_id, item.field_name, item.image_role,
            item.normalized_value, item.provider_id, item.artifact_key,
        ))),
    )


def _field_review(candidate, *, decision=OCRReviewDecision.APPROVE,
                  reviewed_value=None, reason="Confirmed by collector."):
    if decision is OCRReviewDecision.APPROVE and reviewed_value is None:
        reviewed_value = candidate.normalized_value
    return OCRFieldReview(
        source_coin_id=candidate.source_coin_id,
        image_role=candidate.image_role,
        artifact_key=candidate.artifact_key,
        provider_id=candidate.provider_id,
        field_name=candidate.field_name,
        original_value=candidate.normalized_value,
        decision=decision, reviewed_value=reviewed_value, reason=reason,
    )


def _review(*field_reviews, reviewer_id="collector-1"):
    return OCRReportReview(
        reviewer_id=reviewer_id,
        field_reviews=tuple(sorted(field_reviews, key=lambda x: x.identity_key)),
    )


def _result(report, review, *, mode=OCRReviewMode.STRICT_COMPLETE):
    return OCRReviewSessionService().run(request=OCRReviewSessionRequest(
        source_report=report, review=review, mode=mode,
    ))


def _source(report, review, result=None, *, session_id="session-1",
            fingerprint="opaque-fingerprint"):
    return ConfirmedObservationMappingInput(
        session_result=result or _result(report, review),
        source_report=report, report_review=review,
        review_session_id=session_id, source_fingerprint=fingerprint,
    )


def _approved_source(*, field_name="year", value="1967"):
    candidate = _candidate(field_name=field_name, value=value)
    report = _report(candidate)
    review = _review(_field_review(candidate))
    return _source(report, review)


def _replace_final_fields(source, fields):
    projection = replace(source.session_result.final_projection,
                         final_fields=fields)
    return replace(source, session_result=replace(
        source.session_result, final_projection=projection,
    ))


class ConfirmedObservationMapperTests(unittest.TestCase):
    def setUp(self):
        self.mapper = ConfirmedObservationMapper()

    def test_maps_approved_field_and_links(self):
        result = self.mapper.map_review_session(_approved_source())
        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertEqual(item.schema_version,
                         CURRENT_CONFIRMED_OBSERVATION_SCHEMA_VERSION)
        self.assertEqual((item.source_coin_id, item.reviewer_id),
                         ("coin-1", "collector-1"))
        self.assertEqual((item.review_session_id, item.source_fingerprint),
                         ("session-1", "opaque-fingerprint"))

    def test_exact_corrected_value_is_not_canonicalized(self):
        candidate = _candidate()
        report = _report(candidate)
        review = _review(_field_review(
            candidate, decision=OCRReviewDecision.CORRECT,
            reviewed_value="1968", reason="Final digit corrected.",
        ))
        observation = self.mapper.map_review_session(
            _source(report, review))[0].observations[0]
        self.assertEqual(observation.submitted_value, "1968")
        self.assertIsNone(observation.canonical_value)
        self.assertIsNone(observation.rationale)
        self.assertIs(observation.source_type,
                      ConfirmedObservationSource.OCR_REVIEW)

    def test_preserves_source_provenance(self):
        provenance = self.mapper.map_review_session(
            _approved_source())[0].observations[0].provenance[0]
        self.assertEqual(
            (provenance.provider_id, provenance.image_role,
             provenance.artifact_key, provenance.source_value,
             provenance.confidence_score, provenance.evidence),
            ("test-ocr", "front", "crop-front", "1967", 91.5,
             ("clear digits",)),
        )

    def test_agreed_field_preserves_sorted_multi_provenance(self):
        reverse = _candidate(image_role="reverse", artifact_key="z-reverse",
                             confidence_score=88.0,
                             evidence=("reverse legend",))
        front = _candidate(artifact_key="a-front", confidence_score=95.0)
        report = _report(reverse, front)
        review = _review(_field_review(reverse), _field_review(front))
        provenance = self.mapper.map_review_session(
            _source(report, review))[0].observations[0].provenance
        self.assertEqual(len(provenance), 2)
        self.assertEqual(provenance,
                         tuple(sorted(provenance, key=lambda x: x.identity)))
        self.assertEqual({x.confidence_score for x in provenance}, {88.0, 95.0})

    def test_multiple_coins_and_fields_are_deterministic(self):
        candidates = (
            _candidate(source_coin_id="coin-b"),
            _candidate(source_coin_id="coin-a", field_name="country",
                       value="Canada", artifact_key="country"),
            _candidate(source_coin_id="coin-a", field_name="denomination",
                       value="25 cents", artifact_key="denomination"),
        )
        report = _report(*candidates)
        review = _review(*(_field_review(x) for x in candidates))
        mapped = self.mapper.map_review_session(_source(report, review))
        self.assertEqual(tuple(x.source_coin_id for x in mapped),
                         ("coin-a", "coin-b"))
        self.assertEqual(tuple(x.field_name for x in mapped[0].observations),
                         ("country", "denomination"))
        self.assertEqual(mapped, self.mapper.map_review_session(
            _source(report, review)))

    def test_all_current_ocr_fields_are_supported(self):
        for field_name in sorted(ALLOWED_OCR_FIELDS):
            with self.subTest(field_name=field_name):
                mapped = self.mapper.map_review_session(
                    _approved_source(field_name=field_name, value="value"))
                self.assertEqual(mapped[0].observations[0].field_name,
                                 field_name)

    def test_rejected_candidate_is_excluded(self):
        accepted = _candidate()
        rejected = _candidate(field_name="country", value="Unknown",
                              artifact_key="country")
        report = _report(accepted, rejected)
        review = _review(
            _field_review(accepted),
            _field_review(rejected, decision=OCRReviewDecision.REJECT,
                          reason="Not legible."),
        )
        observations = self.mapper.map_review_session(
            _source(report, review))[0].observations
        self.assertEqual(tuple(x.field_name for x in observations), ("year",))

    def test_rejected_only_session_is_rejected(self):
        candidate = _candidate()
        report = _report(candidate)
        review = _review(_field_review(
            candidate, decision=OCRReviewDecision.REJECT))
        with self.assertRaises(IncompleteConfirmedObservationSourceError):
            self.mapper.map_review_session(_source(report, review))

    def test_unresolved_conflict_is_rejected(self):
        front = _candidate()
        reverse = _candidate(image_role="reverse", artifact_key="reverse",
                             value="1968")
        report = _report(front, reverse)
        review = _review(_field_review(front), _field_review(reverse))
        with self.assertRaises(IncompleteConfirmedObservationSourceError):
            self.mapper.map_review_session(
                _source(report, review, _result(report, review)))

    def test_resolved_conflict_maps_the_exact_selected_value(self):
        front = _candidate()
        reverse = _candidate(image_role="reverse", artifact_key="reverse",
                             value="1968")
        report = _report(front, reverse)
        review = _review(_field_review(front), _field_review(reverse))
        reconciliation = OCRReviewReconciliationService().reconcile(
            source_report=report, review=review,
            mode=OCRReviewMode.STRICT_COMPLETE,
        )
        field = OCRMetadataConsolidationService().consolidate(
            reconciliation=reconciliation,
        ).fields[0]
        result = OCRReviewSessionService().run(request=OCRReviewSessionRequest(
            source_report=report,
            review=review,
            mode=OCRReviewMode.STRICT_COMPLETE,
            conflict_resolution_requests=(
                OCRReviewSessionConflictResolutionRequest(
                    field=field,
                    request=OCRConflictResolutionRequest(
                        decision=(
                            OCRConflictResolutionDecision.SELECT_EXISTING_VALUE
                        ),
                        value="1968",
                    ),
                ),
            ),
        ))

        observation = self.mapper.map_review_session(
            _source(report, review, result))[0].observations[0]

        self.assertEqual(observation.submitted_value, "1968")
        self.assertEqual(len(observation.provenance), 2)
    def test_deferred_and_missing_fields_are_rejected(self):
        candidate = _candidate()
        report = _report(candidate)
        review = _review(_field_review(
            candidate, decision=OCRReviewDecision.DEFER))
        with self.assertRaises(IncompleteConfirmedObservationSourceError):
            self.mapper.map_review_session(_source(
                report, review, _result(report, review,
                                        mode=OCRReviewMode.PARTIAL)))
        country = _candidate(field_name="country", value="Canada",
                             artifact_key="country")
        report = _report(candidate, country)
        review = _review(_field_review(candidate))
        with self.assertRaises(IncompleteConfirmedObservationSourceError):
            self.mapper.map_review_session(_source(
                report, review, _result(report, review,
                                        mode=OCRReviewMode.PARTIAL)))

    def test_grade_and_unknown_fields_are_explicitly_rejected(self):
        source = _approved_source()
        field = source.session_result.final_projection.final_fields[0]
        for name in ("grade", "material"):
            with self.subTest(name=name):
                bad = replace(field, source_field=replace(
                    field.source_field, field_name=name))
                with self.assertRaises(
                        UnsupportedConfirmedObservationFieldError):
                    self.mapper.map_review_session(
                        _replace_final_fields(source, (bad,)))

    def test_blank_final_value_is_rejected(self):
        source = _approved_source()
        field = source.session_result.final_projection.final_fields[0]
        with self.assertRaises(MalformedConfirmedObservationSourceError):
            self.mapper.map_review_session(_replace_final_fields(
                source, (replace(field, final_value=" "),)))

    def test_missing_and_duplicate_final_provenance_are_rejected(self):
        source = _approved_source()
        field = source.session_result.final_projection.final_fields[0]
        bad = replace(field, source_field=replace(
            field.source_field, provenance=()))
        with self.assertRaises(MissingConfirmedObservationProvenanceError):
            self.mapper.map_review_session(_replace_final_fields(source, (bad,)))
        with self.assertRaises(DuplicateConfirmedObservationFieldError):
            self.mapper.map_review_session(
                _replace_final_fields(source, (field, field)))

    def test_mismatched_reviewer_is_rejected(self):
        source = _approved_source()
        source = replace(source, report_review=replace(
            source.report_review, reviewer_id="collector-2"))
        with self.assertRaises(MalformedConfirmedObservationSourceError):
            self.mapper.map_review_session(source)

    def test_missing_candidate_or_review_is_rejected(self):
        source = _approved_source()
        with self.assertRaises(MissingConfirmedObservationProvenanceError):
            self.mapper.map_review_session(replace(
                source, source_report=_report()))
        year = _candidate()
        country = _candidate(field_name="country", value="Canada",
                             artifact_key="country")
        report = _report(year, country)
        full_review = _review(_field_review(year), _field_review(country))
        source = _source(report, full_review)
        with self.assertRaises(MissingConfirmedObservationProvenanceError):
            self.mapper.map_review_session(replace(
                source, report_review=_review(_field_review(year))))

    def test_changed_review_provenance_is_rejected(self):
        source = _approved_source()
        altered = replace(source.report_review.field_reviews[0],
                          reason="Different audit reason.")
        with self.assertRaises(MissingConfirmedObservationProvenanceError):
            self.mapper.map_review_session(replace(
                source, report_review=_review(altered)))

    def test_underlying_contracts_and_input_types_are_validated(self):
        source = _approved_source()
        with self.assertRaises(ValueError):
            self.mapper.map_review_session(replace(
                source, source_report=replace(source.source_report,
                                              candidates=[])))
        invalid = (
            replace(source, session_result=object()),
            replace(source, source_report=object()),
            replace(source, report_review=object()),
            replace(source, review_session_id=1),
            replace(source, source_fingerprint=1),
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    self.mapper.map_review_session(value)
        with self.assertRaises(TypeError):
            self.mapper.map_review_session(object())

    def test_invalid_optional_link_is_rejected_by_output_contract(self):
        with self.assertRaises(ValueError):
            self.mapper.map_review_session(replace(
                _approved_source(), review_session_id=" "))

    def test_mapping_failure_is_atomic_and_stateless(self):
        a = _candidate(source_coin_id="coin-a")
        b = _candidate(source_coin_id="coin-b", artifact_key="b")
        report = _report(a, b)
        review = _review(_field_review(a), _field_review(b))
        source = _source(report, review)
        fields = source.session_result.final_projection.final_fields
        bad = replace(fields[1], source_field=replace(
            fields[1].source_field, provenance=()))
        with self.assertRaises(MissingConfirmedObservationProvenanceError):
            self.mapper.map_review_session(
                _replace_final_fields(source, (fields[0], bad)))
        self.assertEqual(ConfirmedObservationMapper.__slots__, ())
        self.assertFalse(hasattr(self.mapper, "__dict__"))

    def test_convenience_function_and_immutability(self):
        source = _approved_source()
        result = map_review_session(source)
        self.assertEqual(result, self.mapper.map_review_session(source))
        with self.assertRaises(FrozenInstanceError):
            source.review_session_id = "changed"
        with self.assertRaises(FrozenInstanceError):
            result[0].reviewer_id = "changed"


class ConfirmedObservationMapperArchitectureTests(unittest.TestCase):
    def test_no_forbidden_integration_imports(self):
        path = Path(inspect.getfile(ConfirmedObservationMapper))
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {alias.name for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                    for alias in node.names}
        for fragment in ("desktop", "collection", "persistence", "sqlite",
                         "pathlib", "os", "uuid", "datetime"):
            with self.subTest(fragment=fragment):
                self.assertFalse(any(fragment in name for name in imported),
                                 imported)

    def test_input_is_the_minimum_source_bundle(self):
        self.assertEqual(
            tuple(ConfirmedObservationMappingInput.__dataclass_fields__),
            ("session_result", "source_report", "report_review",
             "review_session_id", "source_fingerprint"),
        )


if __name__ == "__main__":
    unittest.main()
