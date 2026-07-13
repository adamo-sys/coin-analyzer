"""Tests for v8.8 Phase 4A Canadian reference provider contracts."""

import json
import unittest
from dataclasses import FrozenInstanceError

from canadian_reference_provider import (
    CanadianIssue,
    ReferenceFilters,
    ReferenceProvider,
    ReferenceProviderCapabilities,
    ReferenceProviderCapability,
    ReferenceProviderError,
    ReferenceQuery,
    ReferenceRecord,
    ReferenceSearchResult,
    ReferenceSeverity,
    ReferenceSource,
    ReferenceSourceType,
    SourceRef,
    normalize_catalogue_id,
    normalize_country,
    normalize_denomination,
    normalize_measurement,
    normalize_variety,
    sort_reference_records,
    validate_record,
    validate_records,
)


def synthetic_source(source_id="synthetic"):
    return ReferenceSource(
        source_id=source_id,
        source_name="Synthetic Canadian Reference",
        source_type=ReferenceSourceType.SYNTHETIC_TEST,
        edition="2026 test",
        licence="Synthetic test data",
        attribution="Synthetic fixture only",
    )


def synthetic_issue(issue_id="ca-1920-cent", **overrides):
    data = {
        "issue_id": issue_id,
        "country": "Canada",
        "authority": "Dominion of Canada",
        "denomination": "1 Cent",
        "year": "1920",
        "date_text": "1920",
        "monarch": "George V",
        "series": "Synthetic Small Cent",
        "composition": "Bronze",
        "weight": "3.24 g",
        "diameter": "19.05 mm",
        "catalogue_numbers": {"synthetic": "TEST-1920-CENT"},
        "design_markers": ("synthetic obverse marker",),
        "source_refs": (
            SourceRef(
                source_id="synthetic",
                source_record_id="row-1",
                field_name="denomination",
                raw_value="1 Cent",
                normalized_value="1 cent",
            ),
        ),
    }
    data.update(overrides)
    return CanadianIssue(**data)


def synthetic_record(issue_id="ca-1920-cent", **issue_overrides):
    return ReferenceRecord(
        issue=synthetic_issue(issue_id, **issue_overrides),
        source=synthetic_source(),
        source_record_id="row-1",
        fields_supplied=("country", "denomination", "year"),
    )


class FakeReferenceProvider:
    def __init__(self, records):
        self._records = tuple(records)
        self._source = synthetic_source()

    def provider_id(self):
        return "fake-provider"

    def capabilities(self):
        return ReferenceProviderCapabilities(
            provider_id=self.provider_id(),
            source_type=ReferenceSourceType.SYNTHETIC_TEST,
            capabilities=(
                ReferenceProviderCapability.ISSUE_LOOKUP,
                ReferenceProviderCapability.SEARCH,
                ReferenceProviderCapability.FILTERS,
                ReferenceProviderCapability.VALIDATION,
            ),
            supports_field_provenance=True,
            supports_filters=True,
            network_required=False,
        )

    def get_source_metadata(self):
        return self._source

    def validate(self):
        return validate_records(self.provider_id(), self._records)

    def get_issue(self, issue_id):
        for record in self._records:
            if record.issue.issue_id == issue_id:
                return record
        return None

    def search(self, query):
        text = (query.text or "").lower()
        records = [
            record for record in self._records
            if text in record.issue.denomination.lower() or text in record.issue.year.lower()
        ]
        return ReferenceSearchResult(self.provider_id(), tuple(records))

    def list_issues(self, filters=None):
        filters = filters or ReferenceFilters()
        records = list(self._records)
        if filters.year:
            records = [record for record in records if record.issue.year == filters.year]
        if filters.denomination:
            wanted = normalize_denomination(filters.denomination)
            records = [record for record in records if record.issue.normalized_denomination == wanted]
        return ReferenceSearchResult(self.provider_id(), tuple(records))


class ReferenceProviderCoreTests(unittest.TestCase):
    def test_valid_dto_construction_and_serialization(self):
        record = synthetic_record()

        payload = record.to_dict()

        self.assertEqual(payload["issue"]["issue_id"], "ca-1920-cent")
        self.assertEqual(payload["source"]["source_type"], "SYNTHETIC_TEST")
        self.assertEqual(payload["issue"]["source_refs"][0]["raw_value"], "1 Cent")
        self.assertEqual(payload["issue"]["source_refs"][0]["normalized_value"], "1 cent")

    def test_required_field_validation(self):
        record = ReferenceRecord(
            issue=synthetic_issue("", country="", denomination="", year="", date_text=""),
            source=synthetic_source(),
        )

        findings = validate_record(record, "test-provider")
        codes = {finding.code for finding in findings}

        self.assertIn("MISSING_ISSUE_ID", codes)
        self.assertIn("MISSING_COUNTRY", codes)
        self.assertIn("MISSING_DENOMINATION", codes)
        self.assertIn("MISSING_DATE", codes)

    def test_incomplete_record_validation_warns_for_missing_field_provenance(self):
        record = synthetic_record(source_refs=())

        findings = validate_record(record, "test-provider")

        self.assertIn("MISSING_FIELD_PROVENANCE", {finding.code for finding in findings})

    def test_invalid_measurements_and_units(self):
        record = synthetic_record(weight="3.24 oz", diameter="nineteen mm")

        findings = validate_record(record, "test-provider")
        codes = {finding.code for finding in findings}

        self.assertIn("INVALID_WEIGHT_UNIT", codes)
        self.assertIn("INVALID_DIAMETER_FORMAT", codes)

    def test_duplicate_catalogue_identifiers_where_prohibited(self):
        record = synthetic_record(catalogue_numbers={"synthetic": "TEST 1", "manual": "TEST#1"})

        findings = validate_record(record, "test-provider")

        self.assertIn("DUPLICATE_CATALOGUE_IDENTIFIER", {finding.code for finding in findings})

    def test_raw_and_normalized_value_preservation(self):
        issue = synthetic_issue(
            country="CAN",
            denomination="1 Cent",
            variety="Near 6",
            source_refs=(SourceRef("synthetic", field_name="variety", raw_value="Near 6", normalized_value="near 6"),),
        )

        self.assertEqual(issue.country, "CAN")
        self.assertEqual(issue.normalized_country, "canada")
        self.assertEqual(issue.denomination, "1 Cent")
        self.assertEqual(issue.normalized_denomination, "1 cent")
        self.assertEqual(issue.variety, "Near 6")
        self.assertEqual(issue.normalized_variety, "near 6")
        self.assertEqual(issue.source_refs[0].raw_value, "Near 6")

    def test_source_attribution_preservation(self):
        source = synthetic_source("source-a")
        issue = synthetic_issue(source_refs=(SourceRef("source-a", "record-1", "mintage", "Synthetic raw", "synthetic raw"),))
        record = ReferenceRecord(issue, source, source_record_id="record-1")

        payload = record.to_dict()

        self.assertEqual(payload["source"]["source_id"], "source-a")
        self.assertEqual(payload["issue"]["source_refs"][0]["source_id"], "source-a")
        self.assertEqual(payload["issue"]["source_refs"][0]["source_record_id"], "record-1")

    def test_deterministic_serialization(self):
        record = synthetic_record(catalogue_numbers={"b": "B-1", "a": "A-1"})

        first = json.dumps(record.to_dict(), sort_keys=True)
        second = json.dumps(record.to_dict(), sort_keys=True)

        self.assertEqual(first, second)
        self.assertEqual(list(record.to_dict()["issue"]["catalogue_numbers"]), ["a", "b"])

    def test_deterministic_ordering(self):
        records = [
            synthetic_record("z", denomination="5 cents", year="1921"),
            synthetic_record("a", denomination="1 cent", year="1920"),
            synthetic_record("m", denomination="1 cent", year="1919"),
        ]

        ordered = sort_reference_records(records)

        self.assertEqual([record.issue.issue_id for record in ordered], ["m", "a", "z"])

    def test_provider_capability_declarations(self):
        capabilities = FakeReferenceProvider([synthetic_record()]).capabilities()

        self.assertTrue(capabilities.has(ReferenceProviderCapability.ISSUE_LOOKUP))
        self.assertTrue(capabilities.supports_field_provenance)
        self.assertFalse(capabilities.network_required)
        self.assertEqual(capabilities.to_dict()["source_type"], "SYNTHETIC_TEST")

    def test_provider_protocol_conformance_using_synthetic_fake_provider(self):
        provider = FakeReferenceProvider([synthetic_record()])

        self.assertIsInstance(provider, ReferenceProvider)
        self.assertEqual(provider.provider_id(), "fake-provider")
        self.assertEqual(provider.get_issue("ca-1920-cent").issue.year, "1920")
        self.assertEqual(provider.search(ReferenceQuery(text="cent")).records[0].issue.issue_id, "ca-1920-cent")

    def test_structured_provider_errors(self):
        error = ReferenceProviderError("fake-provider", "UNAVAILABLE", "Provider unavailable.", ReferenceSeverity.ERROR)
        result = ReferenceSearchResult("fake-provider", provider_errors=(error,))

        payload = result.to_dict()

        self.assertEqual(payload["provider_errors"][0]["code"], "UNAVAILABLE")
        self.assertEqual(payload["provider_errors"][0]["severity"], "ERROR")

    def test_no_network_access_required_by_contracts(self):
        provider = FakeReferenceProvider([synthetic_record()])

        self.assertFalse(provider.capabilities().network_required)
        self.assertEqual(provider.list_issues().provider_errors, ())

    def test_no_mutation_of_frozen_dtos(self):
        issue = synthetic_issue()

        with self.assertRaises(FrozenInstanceError):
            issue.issue_id = "changed"

    def test_validation_report_counts_and_status(self):
        valid = synthetic_record("valid")
        invalid = ReferenceRecord(synthetic_issue("", denomination="", year="", date_text=""), synthetic_source())

        report = validate_records("fake-provider", [valid, invalid])

        self.assertEqual(report.total_records, 2)
        self.assertEqual(report.valid_records, 1)
        self.assertEqual(report.status, "ERROR")
        self.assertGreater(report.error_count, 0)

    def test_duplicate_issue_ids_are_reported(self):
        report = validate_records("fake-provider", [synthetic_record("dup"), synthetic_record("dup")])

        self.assertIn("DUPLICATE_ISSUE_ID", {finding.code for finding in report.findings})

    def test_normalization_helpers(self):
        self.assertEqual(normalize_country("CAN"), "canada")
        self.assertEqual(normalize_denomination("1 Cents"), "1 cent")
        self.assertEqual(normalize_variety(" Near 6 "), "near 6")
        self.assertEqual(normalize_catalogue_id("KM# 28"), "km28")
        self.assertEqual(normalize_measurement("19.05 mm"), ("19.05", "mm"))

    def test_list_issues_filters(self):
        provider = FakeReferenceProvider([
            synthetic_record("cent-1920", denomination="1 Cent", year="1920"),
            synthetic_record("dime-1936", denomination="10 cents", year="1936"),
        ])

        result = provider.list_issues(ReferenceFilters(year="1936"))

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0].issue.issue_id, "dime-1936")


if __name__ == "__main__":
    unittest.main()
