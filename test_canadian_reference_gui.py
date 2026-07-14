"""GUI-facing tests for v8.8 Phase 6 Canadian References workspace panel."""

import os
import tempfile
import unittest
from unittest.mock import patch

from canadian_reference_provider import (
    AggregateValidationReport,
    AggregatedReferenceResult,
    CanadianIssue,
    ReferenceClaim,
    ReferenceConflict,
    ReferenceConflictType,
    ReferenceFilters,
    ReferenceIssueGroup,
    ReferenceProviderError,
    ReferenceRecord,
    ReferenceSeverity,
    ReferenceSource,
    ReferenceSourceType,
    ReferenceValidationFinding,
)
from coin_collection_gui import CoinCollectionGUI
from collector_workspace import CanadianReferenceReport


class FakeText:
    def __init__(self):
        self.content = ""

    def config(self, **_kwargs):
        pass

    def delete(self, _start, _end):
        self.content = ""

    def insert(self, _index, content):
        self.content += content


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeTree:
    def __init__(self):
        self.nodes = {}
        self.roots = []
        self._selection = ()
        self._next_id = 0

    def insert(self, parent, _index, text=""):
        self._next_id += 1
        item_id = f"node-{self._next_id}"
        self.nodes[item_id] = {"parent": parent, "text": text, "children": []}
        if parent:
            self.nodes[parent]["children"].append(item_id)
        else:
            self.roots.append(item_id)
        return item_id

    def get_children(self, item=""):
        return tuple(self.nodes[item]["children"]) if item else tuple(self.roots)

    def delete(self, *items):
        for item in items:
            self._delete(item)

    def _delete(self, item):
        for child in list(self.nodes[item]["children"]):
            self._delete(child)
        parent = self.nodes[item]["parent"]
        siblings = self.nodes[parent]["children"] if parent else self.roots
        siblings.remove(item)
        self.nodes.pop(item)

    def selection_set(self, item):
        self._selection = (item,)

    def selection(self):
        return self._selection

    def focus(self, _item):
        pass


class FakeWorkspace:
    def __init__(self, report):
        self.report = report
        self.calls = []
        self.refresh_count = 0

    def get_canadian_references(self, **kwargs):
        self.calls.append(kwargs)
        return self.report

    def refresh(self):
        self.refresh_count += 1


def make_report(*, degraded=False):
    first_source = ReferenceSource(
        source_id="source-a",
        source_name="Synthetic Source A",
        source_type=ReferenceSourceType.SYNTHETIC_TEST,
        attribution="Synthetic fixture",
    )
    second_source = ReferenceSource(
        source_id="source-b",
        source_name="Synthetic Source B",
        source_type=ReferenceSourceType.SYNTHETIC_TEST,
        attribution="Synthetic fixture",
    )
    issue = CanadianIssue(
        issue_id="ca-synthetic-1920",
        country="Canada",
        denomination="1 Cent",
        year="1920",
        composition="Bronze",
        weight="3.24 g",
        diameter="19.05 mm",
        catalogue_numbers={"synthetic": "SYN-1920"},
    )
    first_record = ReferenceRecord(issue=issue, source=first_source, source_record_id="a-1")
    second_record = ReferenceRecord(issue=issue, source=second_source, source_record_id="b-1")
    bronze_claim = ReferenceClaim(
        provider_id="provider-a",
        source=first_source,
        source_record_id="a-1",
        issue_id=issue.issue_id,
        field_name="composition",
        raw_value="Bronze",
        normalized_value="bronze",
    )
    copper_claim = ReferenceClaim(
        provider_id="provider-b",
        source=second_source,
        source_record_id="b-1",
        issue_id=issue.issue_id,
        field_name="composition",
        raw_value="Copper",
        normalized_value="copper",
    )
    group = ReferenceIssueGroup(
        issue_key=issue.issue_id,
        records=(first_record, second_record),
        claims=(bronze_claim, copper_claim),
        conflicts=(ReferenceConflict(
            issue_key=issue.issue_id,
            field_name="composition",
            conflict_type=ReferenceConflictType.COMPOSITION,
            claims=(bronze_claim, copper_claim),
        ),),
    )
    result = AggregatedReferenceResult(
        groups=(group,),
        provider_errors=(ReferenceProviderError("provider-b", "LOAD", "Synthetic provider warning"),),
    )
    validation = AggregateValidationReport(
        findings=(ReferenceValidationFinding(
            severity=ReferenceSeverity.WARNING,
            code="SYNTHETIC_WARNING",
            message="Synthetic validation warning",
            provider_id="provider-a",
        ),),
    )
    return CanadianReferenceReport(
        selection_type="issue_id",
        issue_id=issue.issue_id,
        provider_ids=["provider-a", "provider-b"],
        group_count=1,
        record_count=2,
        claim_count=2,
        conflict_count=1,
        provider_error_count=1,
        aggregate_result=result,
        validation_report=validation,
        summary={
            "provider_count": 2,
            "group_count": 1,
            "record_count": 2,
            "claim_count": 2,
            "conflict_count": 1,
        },
        engine_errors=["No Canadian reference providers configured."] if degraded else [],
    )


class CanadianReferenceGUITests(unittest.TestCase):
    def setUp(self):
        self.gui = object.__new__(CoinCollectionGUI)

    @staticmethod
    def _tab(mode="issue_id"):
        return {
            "mode_var": FakeVar(mode),
            "issue_id_var": FakeVar("ca-synthetic-1920"),
            "query_vars": {
                key: FakeVar(value)
                for key, value in {"text": "cent", "country": "Canada", "denomination": "", "year": "", "authority": "", "mintmark": "", "variety": ""}.items()
            },
            "filter_vars": {
                key: FakeVar(value)
                for key, value in {"country": "Canada", "denomination": "1 Cent", "year": "1920", "authority": "", "monarch": "", "series": ""}.items()
            },
            "summary_var": FakeVar(),
            "result_tree": FakeTree(),
            "records_text": FakeText(),
            "claims_text": FakeText(),
            "conflicts_text": FakeText(),
            "diagnostics_text": FakeText(),
            "current_report": None,
            "current_request": None,
            "tree_groups": {},
        }

    def test_exact_request_uses_workspace_api_and_renders_groups(self):
        tab = self._tab()
        workspace = FakeWorkspace(make_report())

        self.gui._run_canadian_references_tab(tab, workspace)

        self.assertEqual(workspace.calls, [{"issue_id": "ca-synthetic-1920"}])
        self.assertEqual(len(tab["result_tree"].get_children()), 1)
        self.assertIn("Groups: 1", tab["summary_var"].get())
        self.assertIn("Synthetic Source A", tab["records_text"].content)
        self.assertIn("Raw value: Bronze", tab["claims_text"].content)
        self.assertIn("Source Disagreements", tab["conflicts_text"].content)

    def test_search_and_filter_requests_are_explicit_and_mutually_separate(self):
        search = self.gui._canadian_reference_request(self._tab("query"))
        filters = self.gui._canadian_reference_request(self._tab("filters"))

        self.assertEqual(set(search), {"query"})
        self.assertEqual(search["query"].text, "cent")
        self.assertEqual(search["query"].country, "Canada")
        self.assertEqual(set(filters), {"filters"})
        self.assertIsInstance(filters["filters"], ReferenceFilters)
        self.assertEqual(filters["filters"].year, "1920")

    def test_conflicts_and_diagnostics_preserve_each_source(self):
        tab = self._tab()
        workspace = FakeWorkspace(make_report())

        self.gui._run_canadian_references_tab(tab, workspace)

        self.assertIn("provider=provider-a", tab["conflicts_text"].content)
        self.assertIn("provider=provider-b", tab["conflicts_text"].content)
        self.assertNotIn("Preferred", tab["conflicts_text"].content)
        self.assertIn("Synthetic provider warning", tab["diagnostics_text"].content)
        self.assertIn("SYNTHETIC_WARNING", tab["diagnostics_text"].content)

    def test_refresh_replays_last_submitted_request_not_unsubmitted_edits(self):
        tab = self._tab()
        workspace = FakeWorkspace(make_report())
        self.gui._run_canadian_references_tab(tab, workspace)
        tab["issue_id_var"].set("ca-unsubmitted-edit")

        self.gui._refresh_canadian_references_tab(tab, workspace)

        self.assertEqual(workspace.refresh_count, 1)
        self.assertEqual(workspace.calls[-1], {"issue_id": "ca-synthetic-1920", "refresh": True})

    def test_degraded_report_and_no_request_states_are_readable(self):
        tab = self._tab()
        workspace = FakeWorkspace(make_report(degraded=True))

        self.gui._render_canadian_reference_prompt(tab)
        self.assertEqual(workspace.calls, [])
        self.assertIn("Enter an exact issue ID", tab["summary_var"].get())

        self.gui._run_canadian_references_tab(tab, workspace)
        self.assertIn("No Canadian reference providers configured.", tab["diagnostics_text"].content)

    def test_markdown_export_uses_current_report(self):
        tab = self._tab()
        tab["current_report"] = make_report()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "canadian_references.md")
            with patch("coin_collection_gui.filedialog.asksaveasfilename", return_value=path), \
                 patch("coin_collection_gui.messagebox.showinfo") as showinfo:
                self.gui._export_canadian_references_markdown(tab)
            with open(path, "r", encoding="utf-8") as handle:
                content = handle.read()

        self.assertIn("Canadian Reference Claims", content)
        self.assertIn("Conflict: composition", content)
        showinfo.assert_called_once()

    def test_reference_configuration_uses_one_already_owned_dependency(self):
        self.assertEqual(
            self.gui._workspace_reference_configuration_for("aggregator", None),
            {"reference_provider_aggregator": "aggregator"},
        )
        self.assertEqual(
            self.gui._workspace_reference_configuration_for(None, ["provider"]),
            {"reference_providers": ["provider"]},
        )
        with self.assertRaises(ValueError):
            self.gui._workspace_reference_configuration_for("aggregator", ["provider"])


if __name__ == "__main__":
    unittest.main()
