"""Grounded, read-only natural-language access to collection analytics.

The language model plans and explains. Existing deterministic engines remain
the source of truth, and every value sent to a provider passes through a small
field allowlist with bounded output.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
import json
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple

from collection_intelligence import CollectionIntelligenceEngine
from portfolio_performance import PortfolioPerformanceEngine


MAX_QUESTION_LENGTH = 1000
MAX_TOOL_CALLS = 3
MAX_RESULT_LIMIT = 25
DEFAULT_RESULT_LIMIT = 10
MAX_TEXT_LENGTH = 120
MAX_ANSWER_LENGTH = 3000

FILTER_ARGUMENTS = (
    "country",
    "issuer",
    "denomination",
    "year",
    "acquisition_source",
    "acquisition_year",
)


class AssistantValidationError(ValueError):
    """Raised when a model plan or tool request violates the allowlist."""


class AssistantProviderError(RuntimeError):
    """Raised when an optional language-model provider cannot complete a call."""


@dataclass(frozen=True)
class AssistantToolCall:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "arguments": dict(self.arguments)}


@dataclass(frozen=True)
class AssistantQueryPlan:
    status: str
    tool_calls: Tuple[AssistantToolCall, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class AssistantEvidenceReference:
    evidence_id: str
    tool_name: str
    label: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "evidence_id": self.evidence_id,
            "tool_name": self.tool_name,
            "label": self.label,
        }


@dataclass(frozen=True)
class AssistantToolResult:
    tool_call: AssistantToolCall
    summary: str
    data: Mapping[str, Any]
    evidence: Tuple[AssistantEvidenceReference, ...]
    limitations: Tuple[str, ...] = ()
    truncated: bool = False

    def cloud_payload(self) -> Dict[str, Any]:
        """Return the only collection-derived payload allowed to reach a provider."""
        return {
            "tool": self.tool_call.name,
            "summary": self.summary,
            "data": dict(self.data),
            "evidence": [reference.to_dict() for reference in self.evidence],
            "limitations": list(self.limitations),
            "truncated": self.truncated,
        }


@dataclass(frozen=True)
class GroundedAssistantResponse:
    answer_text: str
    status: str
    tool_calls_used: Tuple[AssistantToolCall, ...] = ()
    evidence_references: Tuple[AssistantEvidenceReference, ...] = ()
    limitations: Tuple[str, ...] = ()
    provider_name: str = ""
    model_name: str = ""
    truncated: bool = False
    repair_attempted: bool = False

    def evidence_text(self) -> str:
        lines = [f"{item.evidence_id}: {item.label}" for item in self.evidence_references]
        if self.limitations:
            lines.extend(["", "Limitations:"])
            lines.extend(f"- {item}" for item in self.limitations)
        return "\n".join(lines) if lines else "No collection evidence was used."


class LanguageModelAdapter(Protocol):
    """Vendor-neutral model boundary used by production and fake adapters."""

    provider_name: str
    model_name: str

    def plan(
        self,
        question: str,
        tool_schemas: Sequence[Mapping[str, Any]],
        *,
        repair_error: Optional[str] = None,
    ) -> Any:
        ...

    def explain(self, question: str, evidence: Sequence[Mapping[str, Any]]) -> Any:
        ...


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    allowed_arguments: Tuple[str, ...]
    default_limit: Optional[int] = None

    def schema(self) -> Dict[str, Any]:
        properties: Dict[str, Any] = {}
        for name in self.allowed_arguments:
            if name == "limit":
                properties[name] = {"type": "integer", "minimum": 1, "maximum": MAX_RESULT_LIMIT}
            else:
                properties[name] = {"type": "string", "maxLength": MAX_TEXT_LENGTH}
        return {
            "name": self.name,
            "description": self.description,
            "arguments": properties,
            "additionalProperties": False,
        }


class ReadOnlyAssistantToolRegistry:
    """Explicit allowlist over existing deterministic collection engines."""

    _definitions = (
        ToolDefinition(
            "inventory_count",
            "Count matching collection records and total owned quantity.",
            FILTER_ARGUMENTS,
        ),
        ToolDefinition(
            "inventory_list",
            "List a bounded set of matching collection records using privacy-safe fields.",
            FILTER_ARGUMENTS + ("limit",),
            DEFAULT_RESULT_LIMIT,
        ),
        ToolDefinition(
            "collection_gaps",
            "List known internal date-run gaps for matching country and denomination series.",
            ("country", "denomination", "limit"),
            DEFAULT_RESULT_LIMIT,
        ),
        ToolDefinition(
            "collection_duplicates",
            "List likely duplicate holdings detected by collection intelligence.",
            ("country", "denomination", "year", "limit"),
            DEFAULT_RESULT_LIMIT,
        ),
        ToolDefinition(
            "collection_upgrade_candidates",
            "List deterministic higher-grade duplicate upgrade candidates.",
            ("country", "denomination", "year", "limit"),
            DEFAULT_RESULT_LIMIT,
        ),
        ToolDefinition(
            "collection_priorities",
            "Explain existing deterministic acquisition-priority results.",
            ("country", "denomination", "year", "limit"),
            DEFAULT_RESULT_LIMIT,
        ),
        ToolDefinition(
            "portfolio_acquisition_coverage",
            "Report acquisition cost, date, source, and legacy-estimate coverage.",
            (),
        ),
        ToolDefinition(
            "portfolio_cost_by_currency",
            "Report exact recorded acquisition costs isolated by currency.",
            (),
        ),
        ToolDefinition(
            "portfolio_cost_by_source",
            "Report bounded acquisition-cost rows grouped by source and currency.",
            ("limit",),
            DEFAULT_RESULT_LIMIT,
        ),
        ToolDefinition(
            "portfolio_cost_by_acquisition_year",
            "Report bounded acquisition-cost rows grouped by acquisition year and currency.",
            ("limit",),
            DEFAULT_RESULT_LIMIT,
        ),
        ToolDefinition(
            "portfolio_comparable_cad",
            "Report the comparable-CAD subset, exact exclusions, gain/loss, and ROI semantics.",
            (),
        ),
    )

    def __init__(
        self,
        workspace: Any,
        *,
        want_list_intents: Optional[Iterable[Any]] = None,
        portfolio_engine_options: Optional[Mapping[str, Any]] = None,
    ) -> None:
        if not hasattr(workspace, "collection_items_snapshot"):
            raise TypeError("workspace must provide collection_items_snapshot()")
        self._workspace = workspace
        self._items = tuple(workspace.collection_items_snapshot())
        self._intelligence = CollectionIntelligenceEngine(self._items)
        self._portfolio = PortfolioPerformanceEngine(
            self._items,
            staged_want_list_intents=want_list_intents,
            **dict(portfolio_engine_options or {}),
        )
        self._definition_by_name = {definition.name: definition for definition in self._definitions}

    def tool_schemas(self) -> Tuple[Mapping[str, Any], ...]:
        return tuple(definition.schema() for definition in self._definitions)

    def validate_call(self, call: AssistantToolCall) -> AssistantToolCall:
        definition = self._definition_by_name.get(call.name)
        if definition is None:
            raise AssistantValidationError(f"Unknown assistant tool: {call.name}")
        if not isinstance(call.arguments, Mapping):
            raise AssistantValidationError("Tool arguments must be an object.")
        unknown = sorted(set(call.arguments) - set(definition.allowed_arguments))
        if unknown:
            raise AssistantValidationError(
                f"Unknown argument(s) for {call.name}: {', '.join(unknown)}"
            )
        arguments: Dict[str, Any] = {}
        for name, raw_value in call.arguments.items():
            if name == "limit":
                if isinstance(raw_value, bool) or not isinstance(raw_value, int):
                    raise AssistantValidationError("limit must be an integer.")
                if not 1 <= raw_value <= MAX_RESULT_LIMIT:
                    raise AssistantValidationError(
                        f"limit must be between 1 and {MAX_RESULT_LIMIT}."
                    )
                arguments[name] = raw_value
                continue
            if not isinstance(raw_value, str):
                raise AssistantValidationError(f"{name} must be text.")
            value = raw_value.strip()
            if not value:
                continue
            if len(value) > MAX_TEXT_LENGTH:
                raise AssistantValidationError(f"{name} exceeds {MAX_TEXT_LENGTH} characters.")
            if name == "acquisition_year" and not re.fullmatch(r"\d{4}", value):
                raise AssistantValidationError("acquisition_year must use YYYY format.")
            arguments[name] = value
        if definition.default_limit is not None and "limit" not in arguments:
            arguments["limit"] = definition.default_limit
        return AssistantToolCall(call.name, arguments)

    def execute(self, call: AssistantToolCall) -> AssistantToolResult:
        call = self.validate_call(call)
        handler = getattr(self, f"_tool_{call.name}")
        result = handler(call)
        if _contains_truncation_marker(result.data):
            result = replace(
                result,
                truncated=True,
                limitations=_dedupe(result.limitations + (
                    f"One or more evidence fields exceeded {MAX_TEXT_LENGTH} characters and were truncated.",
                )),
            )
        return result

    def _tool_inventory_count(self, call: AssistantToolCall) -> AssistantToolResult:
        matches = self._matching_items(call.arguments)
        quantity = sum(_quantity(item) for item in matches)
        data = {
            "filters": self._safe_filters(call.arguments),
            "record_count": len(matches),
            "quantity_count": quantity,
        }
        summary = f"Matched {len(matches)} collection record(s) representing quantity {quantity}."
        return self._single_result(call, summary, data, "Inventory count")

    def _tool_inventory_list(self, call: AssistantToolCall) -> AssistantToolResult:
        matches = self._matching_items(call.arguments)
        limit = int(call.arguments["limit"])
        rows = [self._safe_item(item) for item in matches[:limit]]
        truncated = len(matches) > limit
        evidence = tuple(
            AssistantEvidenceReference(
                f"{call.name}:{index + 1}",
                call.name,
                _coin_label(row),
            )
            for index, row in enumerate(rows)
        )
        data = {
            "filters": self._safe_filters(call.arguments),
            "matching_record_count": len(matches),
            "items": rows,
        }
        summary = f"Listed {len(rows)} of {len(matches)} matching collection record(s)."
        return AssistantToolResult(call, summary, data, evidence, truncated=truncated)

    def _tool_collection_gaps(self, call: AssistantToolCall) -> AssistantToolResult:
        rows = [
            row for row in self._intelligence.generate_gap_report_rows()
            if self._row_matches(row, call.arguments)
        ]
        rows.sort(key=lambda row: (_fold(row.get("country")), _fold(row.get("denomination"))))
        limit = int(call.arguments["limit"])
        safe_rows = []
        for row in rows[:limit]:
            safe_rows.append({
                "country": _safe_text(row.get("country")),
                "denomination": _safe_text(row.get("denomination")),
                "years_owned": _safe_text(row.get("years_owned")),
                "missing_years": _safe_text(row.get("missing_years")),
                "completion_percentage": _number_text(row.get("completion_percentage")),
                "priority_tier": _safe_text(row.get("priority_tier")),
                "suggested_next_acquisitions": _safe_text(row.get("suggested_next_acquisitions")),
            })
        evidence = self._row_evidence(call.name, safe_rows, lambda row: (
            f"{row['country']} {row['denomination']} gaps: {row['missing_years'] or 'none'}"
        ))
        summary = f"Found {len(rows)} matching series row(s); returned {len(safe_rows)}."
        limitations = (
            "Missing years are inferred only between the earliest and latest recorded years; they are not a canonical issue checklist.",
        )
        return AssistantToolResult(
            call,
            summary,
            {"series": safe_rows, "matching_series_count": len(rows)},
            evidence,
            limitations,
            len(rows) > limit,
        )

    def _tool_collection_duplicates(self, call: AssistantToolCall) -> AssistantToolResult:
        rows = [row for row in self._intelligence.detect_duplicates() if self._row_matches(row, call.arguments)]
        limit = int(call.arguments["limit"])
        safe_rows = [{
            "country": _safe_text(row.get("country")),
            "denomination": _safe_text(row.get("denomination")),
            "year": _safe_text(row.get("year")),
            "reference": _safe_text(row.get("reference")),
            "quantity_count": int(row.get("count") or 0),
            "record_ids": sorted(_safe_text(getattr(item, "id", "")) for item in row.get("items", [])),
        } for row in rows[:limit]]
        evidence = self._row_evidence(call.name, safe_rows, lambda row: (
            f"{_coin_label(row)}: quantity {row['quantity_count']}"
        ))
        return AssistantToolResult(
            call,
            f"Found {len(rows)} likely duplicate group(s); returned {len(safe_rows)}.",
            {"duplicate_groups": safe_rows, "matching_group_count": len(rows)},
            evidence,
            ("Duplicate groups are deterministic identity matches and still require collector review.",),
            len(rows) > limit,
        )

    def _tool_collection_upgrade_candidates(self, call: AssistantToolCall) -> AssistantToolResult:
        rows = [
            row for row in self._intelligence.detect_upgrade_candidates()
            if self._row_matches(row, call.arguments)
        ]
        limit = int(call.arguments["limit"])
        safe_rows = []
        for row in rows[:limit]:
            safe_rows.append({
                "country": _safe_text(row.get("country")),
                "denomination": _safe_text(row.get("denomination")),
                "year": _safe_text(row.get("year")),
                "current_best_grade": _safe_text(row.get("current_best_grade")),
                "best_item_id": _safe_text(getattr(row.get("best_item"), "id", "")),
                "replacement_item_ids": sorted(
                    _safe_text(getattr(item, "id", ""))
                    for item in row.get("replacement_candidates", [])
                ),
                "reason": _safe_text(row.get("reason")),
            })
        evidence = self._row_evidence(call.name, safe_rows, lambda row: (
            f"{_coin_label(row)}: best recorded grade {row['current_best_grade']}"
        ))
        return AssistantToolResult(
            call,
            f"Found {len(rows)} deterministic upgrade candidate(s); returned {len(safe_rows)}.",
            {"upgrade_candidates": safe_rows, "matching_candidate_count": len(rows)},
            evidence,
            ("Upgrade candidates compare recorded grades among duplicate holdings; they do not use inferred market prices.",),
            len(rows) > limit,
        )

    def _tool_collection_priorities(self, call: AssistantToolCall) -> AssistantToolResult:
        targets = self._intelligence.generate_acquisition_priorities()
        rows = []
        for target in targets:
            data = target.to_dict()
            if self._row_matches(data, call.arguments):
                rows.append(data)
        limit = int(call.arguments["limit"])
        safe_rows = [{
            "country": _safe_text(row.get("country")),
            "denomination": _safe_text(row.get("denomination")),
            "year": _safe_text(row.get("year")),
            "target_type": _safe_text(row.get("target_type")),
            "priority_score": int(row.get("priority_score") or 0),
            "estimated_impact": _safe_text(row.get("estimated_impact")),
            "reason": _safe_text(row.get("reason")),
            "current_best_grade": _safe_text(row.get("current_best_grade")),
        } for row in rows[:limit]]
        evidence = self._row_evidence(call.name, safe_rows, lambda row: (
            f"{_coin_label(row)}: {row['target_type']} priority {row['priority_score']}"
        ))
        return AssistantToolResult(
            call,
            f"Found {len(rows)} matching priority result(s); returned {len(safe_rows)}.",
            {"priority_results": safe_rows, "matching_result_count": len(rows)},
            evidence,
            ("Priority scores are existing deterministic collection-intelligence guidance, not market valuations.",),
            len(rows) > limit,
        )

    def _financial_summary(self) -> Any:
        return self._portfolio.portfolio_financial_summary()

    def _tool_portfolio_acquisition_coverage(self, call: AssistantToolCall) -> AssistantToolResult:
        summary = self._financial_summary()
        data = {
            "collection_record_count": summary.collection_record_count,
            "total_quantity_count": summary.total_quantity_count,
            "acquisition_cost": _coverage_data(summary.acquisition_cost_record_count, summary.collection_record_count, summary.acquisition_cost_coverage_percent),
            "acquisition_date": _coverage_data(summary.acquisition_date_record_count, summary.collection_record_count, summary.acquisition_date_coverage_percent),
            "acquisition_source": _coverage_data(summary.acquisition_source_record_count, summary.collection_record_count, summary.acquisition_source_coverage_percent),
            "usable_legacy_estimate": _coverage_data(summary.usable_valuation_record_count, summary.collection_record_count, summary.usable_valuation_coverage_percent),
        }
        text = (
            f"Acquisition-cost coverage is {data['acquisition_cost']['percent']}% "
            f"({data['acquisition_cost']['covered']}/{data['acquisition_cost']['total']} records)."
        )
        return self._single_result(call, text, data, "Portfolio acquisition coverage")

    def _tool_portfolio_cost_by_currency(self, call: AssistantToolCall) -> AssistantToolResult:
        summary = self._financial_summary()
        rows = [
            {"currency": currency, "recorded_cost": _decimal_text(value)}
            for currency, value in sorted(summary.recorded_costs_by_currency.items())
        ]
        evidence = self._row_evidence(call.name, rows, lambda row: (
            f"{row['currency']} recorded acquisition cost: {row['recorded_cost']}"
        ))
        text = "Recorded acquisition costs by currency: " + (
            " | ".join(f"{row['currency']} {row['recorded_cost']}" for row in rows)
            if rows else "none recorded"
        ) + "."
        return AssistantToolResult(
            call,
            text,
            {"currency_totals": rows},
            evidence or (AssistantEvidenceReference(f"{call.name}:1", call.name, "No recorded costs"),),
            ("Currencies are isolated; no exchange-rate conversion is performed.",),
        )

    def _tool_portfolio_cost_by_source(self, call: AssistantToolCall) -> AssistantToolResult:
        return self._portfolio_breakdown_result(call, self._financial_summary().source_breakdown, "source")

    def _tool_portfolio_cost_by_acquisition_year(self, call: AssistantToolCall) -> AssistantToolResult:
        return self._portfolio_breakdown_result(
            call,
            self._financial_summary().acquisition_year_breakdown,
            "acquisition year",
        )

    def _tool_portfolio_comparable_cad(self, call: AssistantToolCall) -> AssistantToolResult:
        summary = self._financial_summary()
        data = {
            "collection_record_count": summary.collection_record_count,
            "eligible_record_count": summary.comparable_cad_record_count,
            "excluded_record_count": summary.comparable_excluded_record_count,
            "comparable_cad_cost": _decimal_text(summary.comparable_cad_cost),
            "approximate_legacy_estimated_cad_value": _decimal_text(summary.comparable_approximate_estimated_cad_value),
            "estimated_gain_loss_cad": _decimal_text(summary.estimated_gain_loss),
            "estimated_roi_percent": (
                _decimal_text(summary.estimated_roi_percent)
                if summary.estimated_roi_percent is not None else None
            ),
            "exclusions": dict(sorted(summary.comparison_exclusions.items())),
        }
        roi = data["estimated_roi_percent"]
        text = (
            f"Comparable CAD subset: {data['eligible_record_count']}/{data['collection_record_count']} records; "
            f"cost CAD {data['comparable_cad_cost']}; approximate legacy estimate CAD "
            f"{data['approximate_legacy_estimated_cad_value']}; estimated gain/loss CAD "
            f"{data['estimated_gain_loss_cad']}; ROI {roi + '%' if roi is not None else 'unavailable'}."
        )
        limitations = (
            "Only records with CAD acquisition cost and a usable positive legacy estimate are comparable.",
            "Legacy estimate_cad values are approximate; this is not realized gain, tax, or investment advice.",
        )
        return self._single_result(call, text, data, "Comparable CAD portfolio subset", limitations)

    def _portfolio_breakdown_result(self, call: AssistantToolCall, rows: Sequence[Any], label: str) -> AssistantToolResult:
        limit = int(call.arguments["limit"])
        safe_rows = [row.to_dict() for row in rows[:limit]]
        safe_rows = [_sanitize_json(row) for row in safe_rows]
        evidence = self._row_evidence(call.name, safe_rows, lambda row: (
            f"{label.title()} {row['label']}: {row['record_count']} record(s); "
            + _currency_map_text(row["recorded_costs_by_currency"])
        ))
        return AssistantToolResult(
            call,
            f"Returned {len(safe_rows)} of {len(rows)} {label} breakdown row(s).",
            {"breakdown": safe_rows, "matching_row_count": len(rows)},
            evidence,
            ("Costs remain isolated by currency; blank group labels are reported explicitly.",),
            len(rows) > limit,
        )

    def _single_result(
        self,
        call: AssistantToolCall,
        summary: str,
        data: Mapping[str, Any],
        label: str,
        limitations: Tuple[str, ...] = (),
    ) -> AssistantToolResult:
        evidence = (AssistantEvidenceReference(f"{call.name}:1", call.name, label),)
        return AssistantToolResult(call, summary, _sanitize_json(data), evidence, limitations)

    @staticmethod
    def _row_evidence(tool_name: str, rows: Sequence[Mapping[str, Any]], labeler: Any) -> Tuple[AssistantEvidenceReference, ...]:
        return tuple(
            AssistantEvidenceReference(f"{tool_name}:{index + 1}", tool_name, _safe_text(labeler(row)))
            for index, row in enumerate(rows)
        )

    def _matching_items(self, arguments: Mapping[str, Any]) -> List[Any]:
        matches = [item for item in self._items if self._item_matches(item, arguments)]
        return sorted(matches, key=_item_sort_key)

    @staticmethod
    def _item_matches(item: Any, arguments: Mapping[str, Any]) -> bool:
        values = {
            "country": getattr(item, "country", ""),
            "issuer": getattr(item, "issuer", ""),
            "denomination": getattr(item, "denomination", ""),
            "year": getattr(item, "year", ""),
            "acquisition_source": getattr(item, "purchase_source", ""),
            "acquisition_year": str(getattr(item, "acquisition_date", "") or "")[:4],
        }
        return all(
            _fold(values[name]) == _fold(expected)
            for name, expected in arguments.items()
            if name in FILTER_ARGUMENTS
        )

    @staticmethod
    def _row_matches(row: Mapping[str, Any], arguments: Mapping[str, Any]) -> bool:
        for name in ("country", "denomination", "year"):
            expected = arguments.get(name)
            if expected and _fold(row.get(name)) != _fold(expected):
                return False
        return True

    @staticmethod
    def _safe_filters(arguments: Mapping[str, Any]) -> Dict[str, str]:
        return {
            name: _safe_text(value)
            for name, value in arguments.items()
            if name in FILTER_ARGUMENTS
        }

    @staticmethod
    def _safe_item(item: Any) -> Dict[str, Any]:
        """Privacy allowlist: intentionally excludes paths, notes, comments, and images."""
        return {
            "item_id": _safe_text(getattr(item, "id", "")),
            "country": _safe_text(getattr(item, "country", "")),
            "issuer": _safe_text(getattr(item, "issuer", "")),
            "denomination": _safe_text(getattr(item, "denomination", "")),
            "year": _safe_text(getattr(item, "year", "")),
            "grade": _safe_text(getattr(item, "grade", "")),
            "quantity": _quantity(item),
            "acquisition_date": _safe_text(getattr(item, "acquisition_date", "")),
            "purchase_currency": _safe_text(getattr(item, "purchase_currency", "")),
            "purchase_source": _safe_text(getattr(item, "purchase_source", "")),
        }


class GroundedCollectionAssistant:
    """Validate plans, execute allowlisted tools, and ground final explanations."""

    def __init__(self, adapter: LanguageModelAdapter, registry: ReadOnlyAssistantToolRegistry) -> None:
        self.adapter = adapter
        self.registry = registry

    def ask(self, question: str) -> GroundedAssistantResponse:
        question = str(question or "").strip()
        if not question:
            return self._response("Enter a collection question.", "clarification")
        if len(question) > MAX_QUESTION_LENGTH:
            return self._response(
                f"Questions must be {MAX_QUESTION_LENGTH} characters or fewer.",
                "clarification",
            )

        repair_attempted = False
        try:
            raw_plan = self.adapter.plan(question, self.registry.tool_schemas())
            plan = self._validate_plan(raw_plan)
        except Exception as first_error:
            repair_attempted = True
            try:
                raw_plan = self.adapter.plan(
                    question,
                    self.registry.tool_schemas(),
                    repair_error=_safe_error(first_error),
                )
                plan = self._validate_plan(raw_plan)
            except Exception as second_error:
                return self._response(
                    "The provider returned an invalid query plan. No collection tools were run.",
                    "error",
                    limitations=(f"Plan validation failed after one repair attempt: {_safe_error(second_error)}",),
                    repair_attempted=True,
                )

        if plan.status in {"clarification", "unsupported"}:
            message = plan.message or (
                "Please clarify the collection question."
                if plan.status == "clarification"
                else "That request is outside the read-only Ask My Collection capabilities."
            )
            return self._response(message, plan.status, repair_attempted=repair_attempted)

        results: List[AssistantToolResult] = []
        try:
            for call in plan.tool_calls:
                results.append(self.registry.execute(call))
        except AssistantValidationError as error:
            return self._response(
                "The requested collection operation was rejected by the tool allowlist.",
                "error",
                limitations=(_safe_error(error),),
                repair_attempted=repair_attempted,
            )
        except Exception as error:
            return self._response(
                "A deterministic collection tool could not complete the request.",
                "error",
                limitations=(_safe_error(error),),
                repair_attempted=repair_attempted,
            )

        cloud_evidence = [result.cloud_payload() for result in results]
        limitations = tuple(item for result in results for item in result.limitations)
        evidence = tuple(item for result in results for item in result.evidence)
        deterministic_answer = "\n".join(f"- {result.summary}" for result in results)
        try:
            raw_explanation = self.adapter.explain(question, cloud_evidence)
            explanation, cited_ids, model_limitations = validate_explanation(
                raw_explanation,
                question,
                cloud_evidence,
                {item.evidence_id for item in evidence},
            )
            limitations = limitations + tuple(model_limitations)
            answer = explanation.strip()
            if deterministic_answer:
                answer += "\n\nVerified facts:\n" + deterministic_answer
            if not cited_ids and evidence:
                raise AssistantValidationError("Explanation did not cite returned evidence.")
        except Exception as error:
            answer = "Verified collection results:\n" + deterministic_answer
            limitations = limitations + (
                f"The model explanation was rejected; deterministic tool text is shown instead: {_safe_error(error)}",
            )

        return GroundedAssistantResponse(
            answer_text=answer,
            status="answered",
            tool_calls_used=tuple(result.tool_call for result in results),
            evidence_references=evidence,
            limitations=_dedupe(limitations),
            provider_name=_safe_text(getattr(self.adapter, "provider_name", "")),
            model_name=_safe_text(getattr(self.adapter, "model_name", "")),
            truncated=any(result.truncated for result in results),
            repair_attempted=repair_attempted,
        )

    def _validate_plan(self, raw_plan: Any) -> AssistantQueryPlan:
        plan = validate_query_plan(raw_plan)
        if plan.status != "execute":
            return plan
        return AssistantQueryPlan(
            status=plan.status,
            tool_calls=tuple(self.registry.validate_call(call) for call in plan.tool_calls),
            message=plan.message,
        )

    def _response(
        self,
        answer: str,
        status: str,
        *,
        limitations: Tuple[str, ...] = (),
        repair_attempted: bool = False,
    ) -> GroundedAssistantResponse:
        return GroundedAssistantResponse(
            answer_text=answer,
            status=status,
            limitations=limitations,
            provider_name=_safe_text(getattr(self.adapter, "provider_name", "")),
            model_name=_safe_text(getattr(self.adapter, "model_name", "")),
            repair_attempted=repair_attempted,
        )


def validate_query_plan(raw_plan: Any) -> AssistantQueryPlan:
    if isinstance(raw_plan, AssistantQueryPlan):
        plan = raw_plan
    else:
        if not isinstance(raw_plan, Mapping):
            raise AssistantValidationError("Query plan must be an object.")
        unknown = set(raw_plan) - {"status", "tool_calls", "message"}
        if unknown:
            raise AssistantValidationError(f"Unknown query-plan fields: {', '.join(sorted(unknown))}")
        raw_calls = raw_plan.get("tool_calls", ())
        if not isinstance(raw_calls, (list, tuple)):
            raise AssistantValidationError("tool_calls must be a list.")
        calls = []
        for raw_call in raw_calls:
            if isinstance(raw_call, AssistantToolCall):
                calls.append(raw_call)
                continue
            if not isinstance(raw_call, Mapping):
                raise AssistantValidationError("Each tool call must be an object.")
            if set(raw_call) - {"name", "arguments"}:
                raise AssistantValidationError("Tool calls contain unknown fields.")
            calls.append(AssistantToolCall(str(raw_call.get("name") or ""), raw_call.get("arguments", {})))
        plan = AssistantQueryPlan(
            status=str(raw_plan.get("status") or ""),
            tool_calls=tuple(calls),
            message=str(raw_plan.get("message") or ""),
        )
    if plan.status not in {"execute", "clarification", "unsupported"}:
        raise AssistantValidationError("Plan status must be execute, clarification, or unsupported.")
    if len(plan.tool_calls) > MAX_TOOL_CALLS:
        raise AssistantValidationError(f"A plan may call at most {MAX_TOOL_CALLS} tools.")
    tool_names = [call.name for call in plan.tool_calls]
    if len(tool_names) != len(set(tool_names)):
        raise AssistantValidationError("A plan cannot call the same tool more than once.")
    if plan.status == "execute" and not plan.tool_calls:
        raise AssistantValidationError("Execute plans require at least one tool call.")
    if plan.status != "execute" and plan.tool_calls:
        raise AssistantValidationError("Non-execute plans cannot contain tool calls.")
    if len(plan.message) > MAX_TEXT_LENGTH * 4:
        raise AssistantValidationError("Plan message is too long.")
    return plan


def validate_explanation(
    raw: Any,
    question: str,
    evidence: Sequence[Mapping[str, Any]],
    allowed_evidence_ids: set[str],
) -> Tuple[str, Tuple[str, ...], Tuple[str, ...]]:
    if not isinstance(raw, Mapping):
        raise AssistantValidationError("Explanation must be an object.")
    unknown = set(raw) - {"answer", "evidence_ids", "limitations"}
    if unknown:
        raise AssistantValidationError("Explanation contains unknown fields.")
    answer = raw.get("answer")
    evidence_ids = raw.get("evidence_ids", ())
    limitations = raw.get("limitations", ())
    if not isinstance(answer, str) or not answer.strip():
        raise AssistantValidationError("Explanation answer must be non-empty text.")
    if len(answer) > MAX_ANSWER_LENGTH:
        raise AssistantValidationError("Explanation answer is too long.")
    if not isinstance(evidence_ids, (list, tuple)) or not all(isinstance(value, str) for value in evidence_ids):
        raise AssistantValidationError("evidence_ids must be a list of strings.")
    if set(evidence_ids) - allowed_evidence_ids:
        raise AssistantValidationError("Explanation cited evidence that was not returned by tools.")
    if not isinstance(limitations, (list, tuple)) or not all(isinstance(value, str) for value in limitations):
        raise AssistantValidationError("limitations must be a list of strings.")
    allowed_numbers = _numeric_tokens(question + json.dumps(evidence, sort_keys=True, default=str))
    invented_numbers = _numeric_tokens(answer) - allowed_numbers
    if invented_numbers:
        raise AssistantValidationError(
            "Explanation introduced unsupported numeric value(s): " + ", ".join(sorted(invented_numbers))
        )
    return answer, tuple(evidence_ids), tuple(_safe_text(value) for value in limitations if value.strip())


def _sanitize_json(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, float):
        return _number_text(value)
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, Mapping):
        return {str(key): _sanitize_json(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(item) for item in value]
    return _safe_text(value)


def _safe_text(value: Any, limit: int = MAX_TEXT_LENGTH) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _safe_error(error: Exception) -> str:
    return _safe_text(str(error) or error.__class__.__name__, 240)


def _fold(value: Any) -> str:
    return str(value or "").strip().casefold()


def _quantity(item: Any) -> int:
    try:
        return max(int(getattr(item, "quantity", 1) or 1), 1)
    except (TypeError, ValueError):
        return 1


def _item_sort_key(item: Any) -> Tuple[str, ...]:
    return (
        _fold(getattr(item, "country", "")),
        _fold(getattr(item, "issuer", "")),
        _fold(getattr(item, "denomination", "")),
        _fold(getattr(item, "year", "")),
        _fold(getattr(item, "id", "")),
    )


def _coin_label(row: Mapping[str, Any]) -> str:
    return " ".join(
        str(row.get(name) or "").strip()
        for name in ("country", "denomination", "year")
        if str(row.get(name) or "").strip()
    ) or str(row.get("item_id") or "Collection item")


def _decimal_text(value: Any) -> str:
    return format(Decimal(str(value)), "f")


def _number_text(value: Any) -> str:
    if isinstance(value, float):
        return format(value, ".10g")
    return str(value)


def _coverage_data(covered: int, total: int, percent: Decimal) -> Dict[str, Any]:
    return {"covered": covered, "total": total, "percent": _decimal_text(percent)}


def _currency_map_text(values: Mapping[str, Any]) -> str:
    if not values:
        return "no recorded acquisition cost"
    return " | ".join(f"{currency} {value}" for currency, value in sorted(values.items()))


def _numeric_tokens(text: str) -> set[str]:
    return set(re.findall(r"(?<![\w])[-+]?\d+(?:[.,]\d+)*(?:%)?", text))


def _dedupe(values: Iterable[str]) -> Tuple[str, ...]:
    seen = set()
    result = []
    for value in values:
        safe = _safe_text(value, 300)
        if safe and safe not in seen:
            result.append(safe)
            seen.add(safe)
    return tuple(result)


def _contains_truncation_marker(value: Any) -> bool:
    if isinstance(value, str):
        return value.endswith("…")
    if isinstance(value, Mapping):
        return any(_contains_truncation_marker(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_truncation_marker(item) for item in value)
    return False
