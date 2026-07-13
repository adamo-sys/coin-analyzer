"""Tests for v8.8 Phase 4B local and manual reference providers."""

import json
import os
import tempfile
import unittest

from canadian_reference_provider import (
    CanadianIssue,
    LocalJsonReferenceProvider,
    ManualReferenceProvider,
    ReferenceFilters,
    ReferenceProvider,
    ReferenceProviderCapability,
    ReferenceQuery,
    ReferenceRecord,
    ReferenceSource,
    ReferenceSourceType,
    SourceRef,
)


def synthetic_source(source_id="synthetic-canadian-reference"):
    return ReferenceSource(
        source_id=source_id,
        source_name="Synthetic Canadian Reference",
        source_type=ReferenceSourceType.SYNTHETIC_TEST,
        edition="2026 test",
        licence="Synthetic test data",
        attribution="Synthetic fixture only",
    )


def synthetic_issue(issue_id="ca-1920-cent", **overrides):
    values = {
        "issue_id": issue_id,
        "country": "CAN",
        "authority": "Dominion of Canada",
        "denomination": "1 Cents",
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
                source_id="synthetic-canadian-reference",
                source_record_id="row-1",
                field_name="denomination",
                raw_value="1 Cents",
                normalized_value="1 cent",
            ),
        ),
    }
    values.update(overrides)
    return CanadianIssue(**values)


def synthetic_record(issue_id="ca-1920-cent", source=None, **overrides):
    return ReferenceRecord(
        issue=synthetic_issue(issue_id, **overrides),
        source=source or synthetic_source(),
        source_record_id="row-1",
        fields_supplied=("country", "denomination", "year"),
    )


def payload_for(records, source=None, **overrides):
    source = source or synthetic_source()
    issues = []
    for record in records:
        issue = record.issue.to_dict()
        issue.update({
            "source_record_id": record.source_record_id,
            "confidence": record.confidence,
            "fields_supplied": list(record.fields_supplied),
            "warnings": list(record.warnings),
        })
        issues.append(issue)
    payload = {
        "schema_version": 1,
        "provider_id": "synthetic-canadian-reference",
        "source": source.to_dict(),
        "issues": issues,
    }
    payload.update(overrides)
    return payload


class ReferenceLocalManualProviderTests(unittest.TestCase):
    def write_payload(self, payload):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = os.path.join(temp_dir.name, "reference.json")
        with open(path, "w", encoding="utf-8") as reference_file:
            json.dump(payload, reference_file)
        return path

    def test_empty_local_provider_loads_versioned_json(self):
        provider = LocalJsonReferenceProvider(self.write_payload(payload_for([])))

        report = provider.load()

        self.assertTrue(provider.loaded())
        self.assertEqual(report.status, "OK")
        self.assertEqual(provider.list_issues().records, ())

    def test_valid_json_preserves_raw_normalized_and_attribution_values(self):
        provider = LocalJsonReferenceProvider(self.write_payload(payload_for([synthetic_record()])))

        record = provider.get_issue("ca-1920-cent")

        self.assertEqual(record.issue.country, "CAN")
        self.assertEqual(record.issue.normalized_country, "canada")
        self.assertEqual(record.issue.denomination, "1 Cents")
        self.assertEqual(record.issue.normalized_denomination, "1 cent")
        self.assertEqual(record.source.attribution, "Synthetic fixture only")
        self.assertEqual(record.issue.source_refs[0].raw_value, "1 Cents")
        self.assertEqual(record.issue.source_refs[0].normalized_value, "1 cent")

    def test_query_lazily_loads_and_orders_results_deterministically(self):
        records = [
            synthetic_record("z-1921", denomination="5 Cents", year="1921"),
            synthetic_record("a-1919", year="1919"),
            synthetic_record("b-1920", year="1920"),
        ]
        provider = LocalJsonReferenceProvider(self.write_payload(payload_for(records)))

        result = provider.search(ReferenceQuery(text="cent"))

        self.assertTrue(provider.loaded())
        self.assertEqual([record.issue.issue_id for record in result.records], ["a-1919", "b-1920", "z-1921"])

    def test_search_and_filters_apply_normalized_exact_fields(self):
        records = [
            synthetic_record("cent", year="1920"),
            synthetic_record("dime", denomination="10 Cents", year="1936", series="Synthetic Dime"),
        ]
        provider = LocalJsonReferenceProvider(self.write_payload(payload_for(records)))

        query_result = provider.search(ReferenceQuery(text="synthetic", denomination="1 Cent", year="1920"))
        filter_result = provider.list_issues(ReferenceFilters(denomination="10 Cent", year="1936"))

        self.assertEqual([record.issue.issue_id for record in query_result.records], ["cent"])
        self.assertEqual([record.issue.issue_id for record in filter_result.records], ["dime"])

    def test_missing_file_returns_structured_error(self):
        provider = LocalJsonReferenceProvider(os.path.join(tempfile.gettempdir(), "missing-reference-file.json"))

        result = provider.list_issues()

        self.assertFalse(provider.loaded())
        self.assertEqual(result.provider_errors[0].code, "LOCAL_REFERENCE_FILE_MISSING")
        self.assertEqual(provider.validate().status, "ERROR")

    def test_malformed_json_returns_structured_error(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = os.path.join(temp_dir.name, "reference.json")
        with open(path, "w", encoding="utf-8") as reference_file:
            reference_file.write("{")

        provider = LocalJsonReferenceProvider(path)

        self.assertEqual(provider.search(ReferenceQuery()).provider_errors[0].code, "LOCAL_REFERENCE_JSON_MALFORMED")

    def test_schema_and_required_top_level_errors(self):
        missing_version = LocalJsonReferenceProvider(self.write_payload({"source": synthetic_source().to_dict(), "issues": []}))
        unsupported = LocalJsonReferenceProvider(self.write_payload(payload_for([], schema_version=2)))
        missing_source = LocalJsonReferenceProvider(self.write_payload({"schema_version": 1, "issues": []}))
        missing_issues = LocalJsonReferenceProvider(self.write_payload({"schema_version": 1, "source": synthetic_source().to_dict()}))

        self.assertEqual(missing_version.list_issues().provider_errors[0].code, "LOCAL_REFERENCE_SCHEMA_MISSING")
        self.assertEqual(unsupported.list_issues().provider_errors[0].code, "LOCAL_REFERENCE_SCHEMA_UNSUPPORTED")
        self.assertEqual(missing_source.list_issues().provider_errors[0].code, "LOCAL_REFERENCE_SOURCE_MISSING")
        self.assertEqual(missing_issues.list_issues().provider_errors[0].code, "LOCAL_REFERENCE_ISSUES_MISSING")

    def test_partial_load_keeps_valid_records_when_one_record_is_malformed(self):
        payload = payload_for([synthetic_record()])
        payload["issues"].append("not an issue object")
        provider = LocalJsonReferenceProvider(self.write_payload(payload))

        report = provider.load()

        self.assertTrue(provider.loaded())
        self.assertEqual([record.issue.issue_id for record in provider.list_issues().records], ["ca-1920-cent"])
        self.assertIn("LOCAL_REFERENCE_RECORD_INVALID", {finding.code for finding in report.findings})

    def test_duplicate_issue_and_source_ids_are_reported(self):
        provider = LocalJsonReferenceProvider(self.write_payload(payload_for([
            synthetic_record("duplicate"),
            synthetic_record("duplicate"),
        ])))

        codes = {finding.code for finding in provider.validate().findings}

        self.assertIn("DUPLICATE_ISSUE_ID", codes)
        self.assertIn("DUPLICATE_SOURCE_ID", codes)

    def test_invalid_record_validation_does_not_block_loading(self):
        provider = LocalJsonReferenceProvider(self.write_payload(payload_for([
            synthetic_record("valid"),
            synthetic_record("invalid", weight="3 oz"),
        ])))

        result = provider.list_issues()

        self.assertEqual([record.issue.issue_id for record in result.records], ["invalid", "valid"])
        self.assertIn("INVALID_WEIGHT_UNIT", {finding.code for finding in provider.validate().findings})

    def test_local_provider_capabilities_and_protocol_conformance(self):
        provider = LocalJsonReferenceProvider(self.write_payload(payload_for([])))

        self.assertIsInstance(provider, ReferenceProvider)
        self.assertTrue(provider.capabilities().has(ReferenceProviderCapability.SEARCH))
        self.assertFalse(provider.capabilities().network_required)
        self.assertFalse(provider.capabilities().mutable)

    def test_manual_provider_add_and_replace_records(self):
        provider = ManualReferenceProvider()

        add_report = provider.add_record(synthetic_record("later", year="1921"))
        replace_report = provider.replace_records([synthetic_record("earlier", year="1919")])

        self.assertEqual(add_report.total_records, 1)
        self.assertEqual(replace_report.total_records, 1)
        self.assertEqual([record.issue.issue_id for record in provider.list_issues().records], ["earlier"])

    def test_manual_provider_preserves_records_without_mutating_input(self):
        record = synthetic_record()
        provider = ManualReferenceProvider([record])

        result = provider.get_issue("ca-1920-cent")

        self.assertIs(result, record)
        self.assertEqual(record.issue.denomination, "1 Cents")

    def test_manual_provider_export_round_trips_to_local_json(self):
        source = ReferenceSource(
            source_id="manual-source",
            source_name="Manual Synthetic Reference",
            source_type=ReferenceSourceType.MANUAL,
            attribution="Collector entered",
        )
        record = synthetic_record("manual-1920", source=source)
        provider = ManualReferenceProvider([record], source=source, provider_id="manual-provider")
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = os.path.join(temp_dir.name, "export.json")

        self.assertTrue(provider.export_json(path))
        round_trip = LocalJsonReferenceProvider(path)
        exported_record = round_trip.get_issue("manual-1920")

        self.assertEqual(exported_record.to_dict(), record.to_dict())
        self.assertEqual(round_trip.provider_id(), "manual-provider")

    def test_manual_export_failure_is_non_destructive(self):
        provider = ManualReferenceProvider([synthetic_record()])

        self.assertFalse(provider.export_json(os.path.join(tempfile.gettempdir(), "missing", "export.json")))
        self.assertIsNotNone(provider.get_issue("ca-1920-cent"))

    def test_manual_provider_capabilities_and_protocol_conformance(self):
        provider = ManualReferenceProvider([synthetic_record()])

        self.assertIsInstance(provider, ReferenceProvider)
        self.assertTrue(provider.capabilities().has(ReferenceProviderCapability.EXPORT))
        self.assertTrue(provider.capabilities().mutable)
        self.assertFalse(provider.capabilities().network_required)


if __name__ == "__main__":
    unittest.main()
