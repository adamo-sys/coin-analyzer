"""Focused duplicate-evidence and decision tests for Sprint 4."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import unittest

from coin_collection import CoinItem

from capture_import.audit import AuditCoin, AuditSession
from capture_import.decisions import ImportDecisionModel
from capture_import.enums import (
    DuplicateCategory,
    DuplicateConfidence,
    DuplicateDecision,
    ErrorCategory,
    ImageRole,
    ImportPhase,
    ImportResult,
)
from capture_import.errors import InvalidManifest, PackageTooLarge, PreviewStale
from capture_import.limits import (
    AUDIT_SCHEMA_VERSION,
    MAX_DUPLICATE_AUDITS,
    MAX_DUPLICATE_EXISTING_ITEMS,
    MAX_DUPLICATE_MATCHED_IDS,
    MAX_DUPLICATE_REASONS,
)
from capture_import.models import CollectionBaseline, ImportDecision
from capture_import.package import CapturePackageValidator
from capture_import.preview import PackageImportPreviewBuilder, PreviewDecisionSet
from tests.capture_package_fixtures import package_bytes

NOW = "2026-07-19T12:00:00Z"
DESKTOP_ID = "11111111-1111-4111-8111-111111111111"
IMPORT_ID = "22222222-2222-4222-8222-222222222222"


def validate_package():
    payload = package_bytes()
    return CapturePackageValidator().validate_stream(
        BytesIO(payload),
        "show.ca-package",
        package_sha256=sha256(payload).hexdigest(),
        package_byte_length=len(payload),
    )


def role_hashes(package) -> tuple[tuple[ImageRole, str], ...]:
    return tuple(
        sorted(
            ((media.role, media.sha256) for media in package.media),
            key=lambda pair: pair[0].value,
        )
    )


def audit_for(
    package,
    *,
    package_sha256: str,
    created_by: str | None = None,
    session_id: str | None = None,
    hashes: tuple[tuple[ImageRole, str], ...] | None = None,
    phase: ImportPhase = ImportPhase.SUCCEEDED,
) -> AuditSession:
    succeeded = phase is ImportPhase.SUCCEEDED
    coin = package.manifest.coins[0]
    audit_coin = AuditCoin(
        source_coin_id=coin.id,
        desktop_item_id=DESKTOP_ID if succeeded else None,
        decision=DuplicateDecision.IMPORT_AS_NEW,
        source_position=0,
        mint=coin.mint,
        composition=coin.composition,
        is_bullion=coin.is_bullion,
        actual_silver_weight_oz=(
            None
            if coin.asw_troy_ounces is None
            else format(coin.asw_troy_ounces, "f")
        ),
        source_created_at=coin.created_at,
        source_updated_at=coin.updated_at,
        source_quantity=coin.quantity,
        image_role_hashes=hashes or role_hashes(package),
        managed_image_paths=(
            tuple(
                (role, f"coin_photos/collection/{DESKTOP_ID}/{role.value}.jpg")
                for role, _ in (hashes or role_hashes(package))
            )
            if succeeded
            else ()
        ),
    )
    return AuditSession(
        audit_schema_version=AUDIT_SCHEMA_VERSION,
        import_id=IMPORT_ID,
        started_at=NOW,
        completed_at=NOW,
        package_filename_basename="prior.ca-package",
        package_sha256=package_sha256,
        schema=package.manifest.schema,
        package_version=package.manifest.package_version,
        created_by=created_by or package.manifest.created_by,
        created_with=package.manifest.created_with,
        exported_at=package.manifest.exported_at,
        session_id=session_id or package.manifest.session.id,
        session_name=package.manifest.session.name,
        session_description=package.manifest.session.description,
        session_date=package.manifest.session.session_date,
        session_created_at=package.manifest.session.created_at,
        session_updated_at=package.manifest.session.updated_at,
        coin_provenance=(audit_coin,),
        proposed_count=1,
        imported_count=1 if succeeded else 0,
        skipped_count=0,
        phase=phase,
        final_status=ImportResult(phase.value),
        error_category=None if succeeded else ErrorCategory.ROLLED_BACK,
    )


def existing_item(**changes) -> CoinItem:
    values = {
        "id": DESKTOP_ID,
        "image_path": "",
        "country": "Canada",
        "denomination": "Dollar",
        "year": "1967",
        "grade": "",
        "notes": "Fixture",
        "date_added": "2026-07-18",
        "purchase_price": "12.50",
        "purchase_currency": "CAD",
        "purchase_source": "Dealer",
        "acquisition_date": "2026-07-18",
    }
    values.update(changes)
    return CoinItem(**values)


class PackageDuplicateDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.package = validate_package()
        self.baseline = CollectionBaseline("e" * 64, 20)
        self.builder = PackageImportPreviewBuilder()

    def test_exact_successful_replay_defaults_to_skip_and_can_be_overridden(self) -> None:
        audit = audit_for(
            self.package, package_sha256=self.package.package_sha256
        )
        preview = self.builder.build(
            self.package, self.baseline, completed_audits=(audit,)
        )

        exact = [
            candidate
            for candidate in preview.duplicate_candidates
            if candidate.category is DuplicateCategory.PACKAGE_REPLAY
        ]
        self.assertEqual(len(exact), 1)
        self.assertIs(exact[0].confidence, DuplicateConfidence.EXACT)
        self.assertEqual(exact[0].matched_desktop_ids, (DESKTOP_ID,))
        self.assertIs(preview.decisions[0].decision, DuplicateDecision.SKIP)
        changed = ImportDecisionModel.apply(
            preview,
            preview.decisions,
            "coin-1",
            DuplicateDecision.IMPORT_AS_NEW,
        )
        self.assertIs(changed[0].decision, DuplicateDecision.IMPORT_AS_NEW)

    def test_rolled_back_same_hash_is_not_a_successful_replay(self) -> None:
        audit = audit_for(
            self.package,
            package_sha256=self.package.package_sha256,
            phase=ImportPhase.ROLLED_BACK,
        )
        preview = self.builder.build(
            self.package, self.baseline, completed_audits=(audit,)
        )

        self.assertFalse(
            any(
                candidate.category is DuplicateCategory.PACKAGE_REPLAY
                for candidate in preview.duplicate_candidates
            )
        )
        self.assertIs(
            preview.decisions[0].decision, DuplicateDecision.IMPORT_AS_NEW
        )

    def test_source_session_and_both_hashes_are_high_confidence(self) -> None:
        audit = audit_for(self.package, package_sha256="f" * 64)
        preview = self.builder.build(
            self.package, self.baseline, completed_audits=(audit,)
        )

        candidate = next(
            value
            for value in preview.duplicate_candidates
            if value.category is DuplicateCategory.SOURCE_AND_MEDIA
        )
        self.assertIs(candidate.confidence, DuplicateConfidence.HIGH)
        self.assertIs(
            preview.decisions[0].decision, DuplicateDecision.IMPORT_AS_NEW
        )

    def test_both_and_one_media_hash_match_existing_imported_record(self) -> None:
        audit = audit_for(
            self.package,
            package_sha256="f" * 64,
            created_by="Different Producer",
            session_id="different-session",
        )
        both = self.builder.build(
            self.package,
            self.baseline,
            existing_items=(existing_item(),),
            completed_audits=(audit,),
        )
        self.assertTrue(
            any(
                candidate.category is DuplicateCategory.MEDIA_HASHES
                and candidate.confidence is DuplicateConfidence.HIGH
                for candidate in both.duplicate_candidates
            )
        )

        changed_hashes = tuple(
            (role, "0" * 64 if role is ImageRole.REVERSE else digest)
            for role, digest in role_hashes(self.package)
        )
        partial_audit = audit_for(
            self.package,
            package_sha256="f" * 64,
            created_by="Different Producer",
            session_id="different-session",
            hashes=changed_hashes,
        )
        partial = self.builder.build(
            self.package,
            self.baseline,
            existing_items=(existing_item(),),
            completed_audits=(partial_audit,),
        )
        self.assertTrue(
            any(
                candidate.category is DuplicateCategory.PARTIAL_MEDIA
                and candidate.confidence is DuplicateConfidence.WEAK
                for candidate in partial.duplicate_candidates
            )
        )

    def test_identity_with_compatible_acquisition_is_medium(self) -> None:
        preview = self.builder.build(
            self.package,
            self.baseline,
            existing_items=(existing_item(),),
        )
        candidate = next(
            value
            for value in preview.duplicate_candidates
            if value.category is DuplicateCategory.IDENTITY_AND_ACQUISITION
        )
        self.assertIs(candidate.confidence, DuplicateConfidence.MEDIUM)

    def test_identity_or_acquisition_details_alone_remain_weak(self) -> None:
        identity_only = existing_item(
            purchase_price="99.99",
            purchase_currency="USD",
            purchase_source="Other",
            acquisition_date="2020-01-01",
            notes="Other",
        )
        acquisition_only = existing_item(
            id="safe-other-id",
            country="United States",
            denomination="Cent",
            year="1909",
        )
        preview = self.builder.build(
            self.package,
            self.baseline,
            existing_items=(identity_only, acquisition_only),
        )
        categories = {
            candidate.category: candidate.confidence
            for candidate in preview.duplicate_candidates
        }
        self.assertIs(categories[DuplicateCategory.IDENTITY], DuplicateConfidence.WEAK)
        self.assertIs(
            categories[DuplicateCategory.ACQUISITION_DETAILS],
            DuplicateConfidence.WEAK,
        )

    def test_candidate_order_is_deterministic_for_reversed_inputs(self) -> None:
        first_audit = audit_for(self.package, package_sha256="f" * 64)
        second_audit = replace(
            first_audit,
            import_id="33333333-3333-4333-8333-333333333333",
            completed_at="2026-07-19T13:00:00Z",
        )
        items = (existing_item(), existing_item(id="safe-other-id"))
        first = self.builder.build(
            self.package,
            self.baseline,
            existing_items=items,
            completed_audits=(first_audit, second_audit),
        )
        second = self.builder.build(
            self.package,
            self.baseline,
            existing_items=tuple(reversed(items)),
            completed_audits=(second_audit, first_audit),
        )
        self.assertEqual(first, second)
        self.assertGreater(len(first.duplicate_candidates), 1)
        noncanonical = replace(
            first,
            duplicate_candidates=tuple(reversed(first.duplicate_candidates)),
        )
        with self.assertRaisesRegex(ValueError, "canonical ordering"):
            noncanonical.validate()

    def test_currency_is_context_for_price_not_standalone_evidence(self) -> None:
        unrelated = existing_item(
            country="United States",
            denomination="Cent",
            year="1909",
            purchase_price="99.99",
            purchase_source="Other",
            acquisition_date="2020-01-01",
            notes="Other",
        )
        preview = self.builder.build(
            self.package, self.baseline, existing_items=(unrelated,)
        )
        self.assertFalse(
            any(
                candidate.category is DuplicateCategory.ACQUISITION_DETAILS
                for candidate in preview.duplicate_candidates
            )
        )

        same_price = replace(unrelated, purchase_price="12.50")
        preview = self.builder.build(
            self.package, self.baseline, existing_items=(same_price,)
        )
        self.assertTrue(
            any(
                candidate.category is DuplicateCategory.ACQUISITION_DETAILS
                for candidate in preview.duplicate_candidates
            )
        )

        conflicting_currency = replace(same_price, purchase_currency="USD")
        preview = self.builder.build(
            self.package, self.baseline, existing_items=(conflicting_currency,)
        )
        self.assertFalse(
            any(
                candidate.category is DuplicateCategory.ACQUISITION_DETAILS
                for candidate in preview.duplicate_candidates
            )
        )

    def test_duplicate_inputs_are_bounded_before_comparison(self) -> None:
        item = existing_item()
        with self.assertRaises(PackageTooLarge):
            self.builder.build(
                self.package,
                self.baseline,
                existing_items=(item,) * (MAX_DUPLICATE_EXISTING_ITEMS + 1),
            )
        audit = audit_for(self.package, package_sha256="f" * 64)
        with self.assertRaises(PackageTooLarge):
            self.builder.build(
                self.package,
                self.baseline,
                completed_audits=(audit,) * (MAX_DUPLICATE_AUDITS + 1),
            )
        consumed = 0

        def unbounded_items():
            nonlocal consumed
            while True:
                consumed += 1
                yield item

        with self.assertRaises(PackageTooLarge):
            self.builder.build(
                self.package,
                self.baseline,
                existing_items=unbounded_items(),
            )
        self.assertEqual(consumed, MAX_DUPLICATE_EXISTING_ITEMS + 1)

    def test_duplicate_evidence_is_aggregated_capped_and_deterministic(self) -> None:
        items = tuple(existing_item(id=f"safe-{index:03d}") for index in range(20))
        first = self.builder.build(
            self.package, self.baseline, existing_items=items
        )
        second = self.builder.build(
            self.package, self.baseline, existing_items=tuple(reversed(items))
        )
        self.assertEqual(first, second)
        candidate = next(
            value
            for value in first.duplicate_candidates
            if value.category is DuplicateCategory.IDENTITY_AND_ACQUISITION
        )
        self.assertEqual(candidate.total_matches, 20)
        self.assertEqual(len(candidate.matched_desktop_ids), MAX_DUPLICATE_MATCHED_IDS)
        self.assertLessEqual(len(candidate.reasons), MAX_DUPLICATE_REASONS)

    def test_unsafe_mobile_source_ids_fail_closed(self) -> None:
        for unsafe in (
            r"C:\Users\alice",
            "/home/alice",
            "../secret",
            "coin\u202esecret",
            "coin\u007fsecret",
            "coin\u0085secret",
            "coin\u2028secret",
            "x" * 257,
            "coin\nsecret",
        ):
            with self.subTest(source_coin_id=repr(unsafe)):
                coin = replace(self.package.manifest.coins[0], id=unsafe)
                manifest = replace(self.package.manifest, coins=(coin,))
                hostile = replace(self.package, manifest=manifest)
                with self.assertRaises(InvalidManifest):
                    self.builder.build(hostile, self.baseline)

        valid = replace(self.package.manifest.coins[0], id="pièce-β-一")
        manifest = replace(self.package.manifest, coins=(valid,))
        media = tuple(
            replace(value, coin_id="pièce-β-一") for value in self.package.media
        )
        accepted = self.builder.build(
            replace(self.package, manifest=manifest, media=media), self.baseline
        )
        self.assertEqual(accepted.proposals[0].source_coin_id, "pièce-β-一")


class ImportDecisionModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preview = PackageImportPreviewBuilder().build(
            validate_package(), CollectionBaseline("1" * 64, 21)
        )

    def test_requires_exact_complete_ordered_decisions(self) -> None:
        valid = self.preview.decisions
        self.assertEqual(ImportDecisionModel.validate(self.preview, valid), valid)
        for decisions in (
            (),
            PreviewDecisionSet(
                valid.preview_fingerprint,
                valid.decisions + (ImportDecision("stale", DuplicateDecision.SKIP),),
            ),
            PreviewDecisionSet(
                valid.preview_fingerprint,
                (ImportDecision("stale", DuplicateDecision.SKIP),),
            ),
        ):
            with self.subTest(decisions=decisions):
                with self.assertRaises(PreviewStale):
                    ImportDecisionModel.validate(self.preview, decisions)

    def test_rejects_unknown_ids_and_non_enum_selections(self) -> None:
        for source_coin_id, decision in (
            ("stale", DuplicateDecision.SKIP),
            ("coin-1", "MERGE"),
            ("coin-1", "IMPORT_AS_NEW"),
            ({"coin-1": DuplicateDecision.SKIP}, DuplicateDecision.SKIP),
        ):
            with self.subTest(source_coin_id=source_coin_id, decision=decision):
                with self.assertRaises(PreviewStale):
                    ImportDecisionModel.apply(
                        self.preview,
                        self.preview.decisions,
                        source_coin_id,  # type: ignore[arg-type]
                        decision,  # type: ignore[arg-type]
                    )

    def test_decision_vocabulary_contains_no_mutating_merge_action(self) -> None:
        self.assertEqual(
            {decision.value for decision in DuplicateDecision},
            {"SKIP", "IMPORT_AS_NEW"},
        )

    def test_decisions_are_bound_to_package_baseline_and_duplicate_state(self) -> None:
        package = validate_package()
        initial = PackageImportPreviewBuilder().build(
            package, CollectionBaseline("1" * 64, 21)
        )
        approved = ImportDecisionModel.apply(
            initial,
            initial.decisions,
            "coin-1",
            DuplicateDecision.IMPORT_AS_NEW,
        )

        changed_baseline = PackageImportPreviewBuilder().build(
            package, CollectionBaseline("2" * 64, 21)
        )
        changed_package = replace(package, package_sha256="3" * 64)
        changed_package_preview = PackageImportPreviewBuilder().build(
            changed_package, CollectionBaseline("1" * 64, 21)
        )
        replay = PackageImportPreviewBuilder().build(
            package,
            CollectionBaseline("1" * 64, 21),
            completed_audits=(
                audit_for(package, package_sha256=package.package_sha256),
            ),
        )

        for stale_preview in (changed_baseline, changed_package_preview, replay):
            with self.subTest(fingerprint=stale_preview.decisions.preview_fingerprint):
                with self.assertRaises(PreviewStale):
                    ImportDecisionModel.validate(stale_preview, approved)
        self.assertIs(replay.decisions[0].decision, DuplicateDecision.SKIP)
        stale_raw_selection = {"coin-1": DuplicateDecision.IMPORT_AS_NEW}
        with self.assertRaises(PreviewStale):
            ImportDecisionModel.apply(
                replay,
                replay.decisions,
                stale_raw_selection,  # type: ignore[arg-type]
                DuplicateDecision.IMPORT_AS_NEW,
            )
        current_override = ImportDecisionModel.apply(
            replay,
            replay.decisions,
            "coin-1",
            DuplicateDecision.IMPORT_AS_NEW,
        )
        self.assertEqual(ImportDecisionModel.validate(replay, current_override), current_override)

        for stale_preview in (changed_baseline, changed_package_preview, replay):
            with self.subTest(stale_apply=stale_preview.decisions.preview_fingerprint):
                with self.assertRaises(PreviewStale):
                    ImportDecisionModel.apply(
                        stale_preview,
                        initial.decisions,
                        "coin-1",
                        DuplicateDecision.IMPORT_AS_NEW,
                    )


if __name__ == "__main__":
    unittest.main()
