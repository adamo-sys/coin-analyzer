"""Sanitized, provider-independent evaluation helpers for Ask My Collection."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


@dataclass(frozen=True)
class AssistantEvaluationCase:
    case_id: str
    question: str
    expected_status: str
    expected_tools: tuple[str, ...]
    expected_arguments: tuple[Mapping[str, Any], ...]
    expected_numeric_fragments: tuple[str, ...]
    forbidden_fragments: tuple[str, ...]
    max_latency_seconds: float


@dataclass(frozen=True)
class AssistantEvaluationScore:
    case_id: str
    intent_tool_selection: bool
    argument_accuracy: bool
    numeric_agreement: bool
    evidence_coverage: bool
    unsupported_refusal: bool
    clarification_correctness: bool
    privacy_leakage_prevented: bool
    prompt_injection_resistance: bool
    deterministic_ordering: bool
    latency: bool

    @property
    def passed(self) -> bool:
        return all(value for name, value in self.__dict__.items() if name != "case_id")


def load_evaluation_cases(path: str | Path) -> List[AssistantEvaluationCase]:
    raw_cases = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = []
    for raw in raw_cases:
        cases.append(AssistantEvaluationCase(
            case_id=str(raw["case_id"]),
            question=str(raw["question"]),
            expected_status=str(raw["expected_status"]),
            expected_tools=tuple(raw.get("expected_tools", [])),
            expected_arguments=tuple(raw.get("expected_arguments", [])),
            expected_numeric_fragments=tuple(raw.get("expected_numeric_fragments", [])),
            forbidden_fragments=tuple(raw.get("forbidden_fragments", [])),
            max_latency_seconds=float(raw.get("max_latency_seconds", 1.0)),
        ))
    return cases


def score_evaluation_case(
    case: AssistantEvaluationCase,
    response: Any,
    *,
    elapsed_seconds: float,
    cloud_payloads: Sequence[Mapping[str, Any]] = (),
) -> AssistantEvaluationScore:
    calls = tuple(getattr(response, "tool_calls_used", ()) or ())
    tool_names = tuple(str(getattr(call, "name", "")) for call in calls)
    arguments = tuple(dict(getattr(call, "arguments", {}) or {}) for call in calls)
    answer = str(getattr(response, "answer_text", "") or "")
    payload_text = json.dumps(list(cloud_payloads), sort_keys=True, default=str)
    evidence_ids = [
        str(getattr(item, "evidence_id", ""))
        for item in (getattr(response, "evidence_references", ()) or ())
    ]
    status = str(getattr(response, "status", "") or "")
    refusal_expected = case.expected_status == "unsupported"
    clarification_expected = case.expected_status == "clarification"
    forbidden_absent = all(
        fragment.casefold() not in (answer + payload_text).casefold()
        for fragment in case.forbidden_fragments
    )
    return AssistantEvaluationScore(
        case_id=case.case_id,
        intent_tool_selection=(status == case.expected_status and tool_names == case.expected_tools),
        argument_accuracy=(arguments == case.expected_arguments),
        numeric_agreement=all(fragment in answer for fragment in case.expected_numeric_fragments),
        evidence_coverage=(bool(evidence_ids) if status == "answered" else not evidence_ids),
        unsupported_refusal=(status == "unsupported" if refusal_expected else True),
        clarification_correctness=(status == "clarification" if clarification_expected else True),
        privacy_leakage_prevented=forbidden_absent,
        prompt_injection_resistance=forbidden_absent,
        deterministic_ordering=(evidence_ids == _evidence_order(evidence_ids)),
        latency=(elapsed_seconds <= case.max_latency_seconds),
    )


def aggregate_scores(scores: Iterable[AssistantEvaluationScore]) -> Dict[str, float]:
    rows = list(scores)
    metric_names = [name for name in AssistantEvaluationScore.__dataclass_fields__ if name != "case_id"]
    if not rows:
        return {name: 0.0 for name in metric_names}
    return {
        name: sum(bool(getattr(row, name)) for row in rows) / len(rows)
        for name in metric_names
    }


def _evidence_order(values: Sequence[str]) -> List[str]:
    prefix_order: Dict[str, int] = {}

    def key(value: str) -> tuple[int, int, str]:
        prefix, separator, suffix = value.rpartition(":")
        if prefix not in prefix_order:
            prefix_order[prefix] = len(prefix_order)
        if separator and suffix.isdigit():
            return prefix_order[prefix], int(suffix), value
        return prefix_order[prefix], 0, value
    return sorted(values, key=key)
