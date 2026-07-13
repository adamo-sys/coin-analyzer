"""Tests for v8.8 Phase 4C reference aggregation and conflict reporting."""

import json
import unittest

from canadian_reference_provider import (
    CanadianIssue,
    ManualReferenceProvider,
    ReferenceFilters,
    ReferenceProvider,
    ReferenceProviderAggregator,
    ReferenceProviderCapabilities,
    ReferenceProviderCapability,
    ReferenceProviderError,
    ReferenceQuery,
    ReferenceRecord,
    ReferenceSearchResult,
    ReferenceSource,
    ReferenceSourceType,
    ReferenceValidationReport,
    SourceRef,
    normalize_text,
    validate_records,
)


def synthetic_source(source_id):
    return ReferenceSource(
        source_id=source_id,
        source_name=f"Synthetic {source_id}",
        source_type=ReferenceSourceType.SYNTHETIC_TEST,
        attribution="Synthetic fixture only",
    )


def synthetic_record(issue_id="shared-issue", source_id="source-a", **overrides):
    values = {
        "issue_id": issue_id,
        "country": "Canada",
        "authority": "Dominion of Canada",
        "denomination": "1 Cent",
        "year": "1920",
        "date_text": "1920",
        "series": "Synthetic Small Cent",
        "composition": "Bronze",
        "weight": "3.24 g",
        "diameter": "19.05 mm",
        "mintage": "Synthetic mintage A",
        "variety": "Synthetic variety",
        "catalogue_numbers": {"synthetic": "SYN-1920"},
        "source_refs": (
            SourceRef(
                source_id=source_id,
                source_record_id=f"{source_id}-row",
                field_name="composition",
                raw_value="Bronze",
                normalized_value="bronze",
            ),
        ),
    }
    values.update(overrides)
    source = synthetic_source(source_id)
    return ReferenceRecord(
        issue=CanadianIssue(**values),
        source=source,
        source_record_id=f"{source_id}-row",
        fields_supplied=("country", "denomination", "year"),
    )


class SyntheticProvider:
    def __init__(self, provider_id, records=(), errors=(), fail_operations=(), validation_error=False):
        self._provider_id = provider_id
        self._records = tuple(records)
        self._errors = tuple(errors)
        self._fail_operations = frozenset(fail_operations)
        self._validation_error = validation_error

    def provider_id(self):
        return self._provider_id

    def capabilities(self):
        return ReferenceProviderCapabilities(
            provider_id=self._provider_id,
            source_type=ReferenceSourceType.SYNTHETIC_TEST,
            capabilities=(
                ReferenceProviderCapability.ISSUE_LOOKUP,
                ReferenceProviderCapability.SEARCH,
                ReferenceProviderCapability.FILTERS,
                ReferenceProviderCapability.FIELD_PROVENANCE,
                ReferenceProviderCapability.VALIDATION,
            ),
            supports_field_provenance=True,
            supports_filters=True,
            network_required=False,
        )

    def get_source_metadata(self):
        return self._records[0].source if self._records else synthetic_source(self._provider_id)

    def validate(self):
        if self._validation_error:
            raise RuntimeError("synthetic validation failure")
        return validate_records(self._provider_id, self._records)

    def get_issue(self, issue_id):
        if "get_issue" in self._fail_operations:
            raise RuntimeError("synthetic lookup failure")
        wanted = normalize_text(issue_id)
        return next((record for record in self._records if normalize_text(record.issue.issue_id) == wanted), None)

    def search(self, query):
        if "search" in self._fail_operations:
            raise RuntimeError("synthetic search failure")
        return ReferenceSearchResult(self._provider_id, self._records, provider_errors=self._errors)

    def list_issues(self, filters=None):
        if "list_issues" in self._fail_operations:
            raise RuntimeError("synthetic list failure")
        return ReferenceSearchResult(self._provider_id, self._records, provider_errors=self._errors)


class ReferenceAggregationConflictTests(unittest.TestCase):
    def test_empty_aggregator_returns_empty_deterministic_result(self):
        aggregator = ReferenceProviderAggregator()

        result = aggregator.list_issues()

        self.assertEqual(result.groups, ())
        self.assertEqual(result.provider_errors, ())
        self.assertEqual(aggregator.validate().provider_reports, ())

    def test_one_provider_supports_get_search_and_list(self):
        record = synthetic_record()
        aggregator = ReferenceProviderAggregator([SyntheticProvider("provider-a", [record])])

        self.assertEqual(len(aggregator.get_issue("SHARED-ISSUE").groups), 1)
        self.assertEqual(len(aggregator.search(ReferenceQuery(text="cent")).groups), 1)
        self.assertEqual(len(aggregator.list_issues(ReferenceFilters(year="1920")).groups), 1)

    def test_same_normalized_issue_id_groups_records_from_multiple_providers(self):
        first = synthetic_record("Shared-Issue", "source-a")
        second = synthetic_record(" shared-issue ", "source-b")
        aggregator = ReferenceProviderAggregator([
            SyntheticProvider("provider-a", [first]),
            SyntheticProvider("provider-b", [second]),
        ])

        group = aggregator.list_issues().groups[0]

        self.assertEqual(group.issue_key, "shared-issue")
        self.assertEqual(group.records, (first, second))
        self.assertEqual({claim.provider_id for claim in group.claims}, {"provider-a", "provider-b"})

    def test_similar_metadata_with_different_issue_ids_remains_separate(self):
        first = synthetic_record("issue-a")
        second = synthetic_record("issue-b")
        aggregator = ReferenceProviderAggregator([
            SyntheticProvider("provider-a", [first]),
            SyntheticProvider("provider-b", [second]),
        ])

        self.assertEqual([group.issue_key for group in aggregator.list_issues().groups], ["issue-a", "issue-b"])

    def test_provider_registration_order_is_preserved_and_duplicate_ids_fail(self):
        first = SyntheticProvider("first", [synthetic_record(source_id="first-source")])
        second = SyntheticProvider("second", [synthetic_record(source_id="second-source")])
        aggregator = ReferenceProviderAggregator([first, second])

        self.assertEqual(aggregator.provider_ids(), ("first", "second"))
        self.assertEqual(aggregator.providers(), (first, second))
        with self.assertRaises(ValueError):
            aggregator.register(SyntheticProvider("first"))

    def test_matching_claims_report_no_conflict(self):
        aggregator = ReferenceProviderAggregator([
            SyntheticProvider("provider-a", [synthetic_record(source_id="source-a")]),
            SyntheticProvider("provider-b", [synthetic_record(source_id="source-b")]),
        ])

        self.assertEqual(aggregator.list_issues().groups[0].conflicts, ())

    def test_conflicting_supported_fields_are_reported_without_winner(self):
        overrides = {
            "date_text": "1920 issue date",
            "mintage": "Synthetic mintage B",
            "weight": "3.25 g",
            "diameter": "19.10 mm",
            "composition": "Copper",
            "variety": "Synthetic alternate",
            "catalogue_numbers": {"synthetic": "SYN-1920-B"},
            "source_refs": (),
        }
        aggregator = ReferenceProviderAggregator([
            SyntheticProvider("provider-a", [synthetic_record(source_id="source-a")]),
            SyntheticProvider("provider-b", [synthetic_record(source_id="source-b", **overrides)]),
        ])

        conflicts = {conflict.field_name: conflict for conflict in aggregator.list_issues().groups[0].conflicts}

        self.assertEqual(set(conflicts), {
            "catalogue_numbers.synthetic", "composition", "date_text", "diameter",
            "mintage", "variety", "weight",
        })
        self.assertTrue(all(len(conflict.claims) == 2 for conflict in conflicts.values()))
        self.assertFalse(hasattr(conflicts["weight"], "selected_value"))

    def test_different_catalogue_namespaces_are_not_conflicts(self):
        first = synthetic_record(source_id="source-a", catalogue_numbers={"source-a": "A-1"})
        second = synthetic_record(source_id="source-b", catalogue_numbers={"source-b": "B-9"})
        aggregator = ReferenceProviderAggregator([
            SyntheticProvider("provider-a", [first]),
            SyntheticProvider("provider-b", [second]),
        ])

        self.assertEqual(aggregator.list_issues().groups[0].conflicts, ())

    def test_claims_preserve_field_provenance_and_raw_values(self):
        record = synthetic_record()
        aggregator = ReferenceProviderAggregator([SyntheticProvider("provider-a", [record])])

        claim = next(claim for claim in aggregator.list_issues().groups[0].claims if claim.field_name == "composition")

        self.assertEqual(claim.source.source_id, "source-a")
        self.assertEqual(claim.source_record_id, "source-a-row")
        self.assertEqual(claim.raw_value, "Bronze")
        self.assertEqual(claim.normalized_value, "bronze")
        self.assertEqual(claim.source_ref, record.issue.source_refs[0])

    def test_manual_provider_has_no_implicit_priority(self):
        local = SyntheticProvider("local", [synthetic_record(source_id="local-source", composition="Bronze")])
        manual_source = ReferenceSource("manual-source", "Manual", ReferenceSourceType.MANUAL)
        manual_record = ReferenceRecord(
            issue=synthetic_record(source_id="manual-source", composition="Copper").issue,
            source=manual_source,
            source_record_id="manual-row",
        )
        manual = ManualReferenceProvider([manual_record], source=manual_source, provider_id="manual")
        aggregator = ReferenceProviderAggregator([local, manual])

        group = aggregator.list_issues().groups[0]
        conflict = next(conflict for conflict in group.conflicts if conflict.field_name == "composition")

        self.assertEqual([claim.provider_id for claim in conflict.claims], ["local", "manual"])
        self.assertEqual([record.source.source_id for record in group.records], ["local-source", "manual-source"])

    def test_one_failed_provider_is_isolated_from_healthy_results(self):
        aggregator = ReferenceProviderAggregator([
            SyntheticProvider("failed", fail_operations=("search",)),
            SyntheticProvider("healthy", [synthetic_record(source_id="healthy-source")]),
        ])

        result = aggregator.search(ReferenceQuery(text="cent"))

        self.assertEqual(len(result.groups), 1)
        self.assertEqual(result.provider_errors[0].provider_id, "failed")
        self.assertEqual(result.provider_errors[0].code, "AGGREGATE_PROVIDER_SEARCH_FAILED")

    def test_multiple_failures_are_reported_in_registration_order(self):
        aggregator = ReferenceProviderAggregator([
            SyntheticProvider("first", fail_operations=("list_issues",)),
            SyntheticProvider("second", fail_operations=("list_issues",)),
            SyntheticProvider("healthy", [synthetic_record(source_id="healthy-source")]),
        ])

        result = aggregator.list_issues()

        self.assertEqual([error.provider_id for error in result.provider_errors], ["first", "second"])
        self.assertEqual(len(result.groups), 1)

    def test_provider_result_errors_are_preserved(self):
        error = ReferenceProviderError("provider-a", "SOURCE_UNAVAILABLE", "Synthetic source unavailable.")
        aggregator = ReferenceProviderAggregator([SyntheticProvider("provider-a", errors=(error,))])

        result = aggregator.list_issues()

        self.assertEqual(result.provider_errors, (error,))

    def test_aggregate_validation_preserves_reports_and_isolates_failure(self):
        healthy = SyntheticProvider("healthy", [synthetic_record(source_id="healthy-source")])
        failed = SyntheticProvider("failed", validation_error=True)
        aggregator = ReferenceProviderAggregator([healthy, failed])

        report = aggregator.validate()

        self.assertEqual([item.provider_id for item in report.provider_reports], ["healthy"])
        self.assertEqual(report.provider_errors[0].code, "AGGREGATE_PROVIDER_VALIDATE_FAILED")
        self.assertIn("AGGREGATE_PROVIDER_VALIDATE_FAILED", {finding.code for finding in report.findings})

    def test_aggregate_serialization_and_order_are_deterministic(self):
        aggregator = ReferenceProviderAggregator([
            SyntheticProvider("provider-b", [synthetic_record("z-issue", "source-b")]),
            SyntheticProvider("provider-a", [synthetic_record("a-issue", "source-a")]),
        ])

        first = json.dumps(aggregator.list_issues().to_dict(), sort_keys=True)
        second = json.dumps(aggregator.list_issues().to_dict(), sort_keys=True)

        self.assertEqual(first, second)
        self.assertEqual([group.issue_key for group in aggregator.list_issues().groups], ["a-issue", "z-issue"])

    def test_aggregation_does_not_mutate_provider_records_or_require_network(self):
        record = synthetic_record()
        before = record.to_dict()
        provider = SyntheticProvider("provider-a", [record])
        aggregator = ReferenceProviderAggregator([provider])

        group = aggregator.list_issues().groups[0]

        self.assertIs(group.records[0], record)
        self.assertEqual(record.to_dict(), before)
        self.assertFalse(provider.capabilities().network_required)
        self.assertIsInstance(provider, ReferenceProvider)


if __name__ == "__main__":
    unittest.main()
