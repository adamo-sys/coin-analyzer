"""Deterministic read-only denomination-label consistency audit.

The audit boundary intentionally accepts only jurisdiction and denomination
labels. Collection identifiers, notes, photo metadata, and complete collection
records do not cross this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from capture_import.canonical_identity import (
    canonicalize_denomination,
    canonicalize_jurisdiction,
)


class DenominationAuditCategory(str, Enum):
    CANONICAL = "canonical"
    PROPOSED = "proposed"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class DenominationAuditRecord:
    jurisdiction: str | None
    denomination: str | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "jurisdiction": self.jurisdiction,
            "denomination": self.denomination,
        }


@dataclass(frozen=True, slots=True)
class DenominationAuditFinding:
    category: DenominationAuditCategory
    jurisdiction: str
    canonical_denomination: str | None
    observed_labels: tuple[str, ...]
    count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "category": self.category.value,
            "jurisdiction": self.jurisdiction,
            "canonical_denomination": self.canonical_denomination,
            "observed_labels": list(self.observed_labels),
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class DenominationLabelAuditReport:
    findings: tuple[DenominationAuditFinding, ...]
    records_scanned: int

    @property
    def canonical_count(self) -> int:
        return sum(
            finding.count
            for finding in self.findings
            if finding.category is DenominationAuditCategory.CANONICAL
        )

    @property
    def proposed_count(self) -> int:
        return sum(
            finding.count
            for finding in self.findings
            if finding.category is DenominationAuditCategory.PROPOSED
        )

    @property
    def review_count(self) -> int:
        return sum(
            finding.count
            for finding in self.findings
            if finding.category is DenominationAuditCategory.REVIEW
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "records_scanned": self.records_scanned,
            "canonical_count": self.canonical_count,
            "proposed_count": self.proposed_count,
            "review_count": self.review_count,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def format_text(self) -> str:
        lines = [
            "DENOMINATION LABEL CONSISTENCY AUDIT",
            "",
            f"Records scanned: {self.records_scanned}",
            f"Canonical: {self.canonical_count}",
            f"Proposed: {self.proposed_count}",
            f"Review: {self.review_count}",
            "",
            "This report is read-only. No collection data is modified.",
            "",
        ]

        if not self.findings:
            lines.append("No denomination labels found.")
            return "\n".join(lines)

        current_category = None
        for finding in self.findings:
            if finding.category is not current_category:
                current_category = finding.category
                lines.extend(["", current_category.value.upper()])

            labels = ", ".join(repr(label) for label in finding.observed_labels)
            target = (
                f" -> {finding.canonical_denomination}"
                if finding.canonical_denomination is not None
                else ""
            )
            lines.append(
                f"- {finding.jurisdiction}: {labels}{target} "
                f"(count={finding.count})"
            )

        return "\n".join(lines)


def audit_denomination_labels(
    records: Iterable[DenominationAuditRecord],
) -> DenominationLabelAuditReport:
    """Audit denomination labels without mutating source data."""

    rows = tuple(records)
    grouped: dict[
        tuple[DenominationAuditCategory, str, str | None],
        dict[str, int],
    ] = {}

    for record in rows:
        jurisdiction = canonicalize_jurisdiction(record.jurisdiction)

        if not jurisdiction.is_mapped or jurisdiction.canonical_value is None:
            _add_group(
                grouped,
                DenominationAuditCategory.REVIEW,
                _display_raw(record.jurisdiction),
                None,
                _display_raw(record.denomination),
            )
            continue

        canonical_jurisdiction = jurisdiction.canonical_value
        denomination = canonicalize_denomination(
            record.denomination,
            jurisdiction_id=canonical_jurisdiction.canonical_id,
        )

        if not denomination.is_mapped or denomination.canonical_value is None:
            _add_group(
                grouped,
                DenominationAuditCategory.REVIEW,
                canonical_jurisdiction.display_name,
                None,
                _display_raw(record.denomination),
            )
            continue

        canonical_label = denomination.canonical_value.display_name
        raw_label = _display_raw(record.denomination)
        category = (
            DenominationAuditCategory.CANONICAL
            if raw_label == canonical_label
            else DenominationAuditCategory.PROPOSED
        )

        _add_group(
            grouped,
            category,
            canonical_jurisdiction.display_name,
            canonical_label,
            raw_label,
        )

    findings = []
    category_order = {
        DenominationAuditCategory.CANONICAL: 0,
        DenominationAuditCategory.PROPOSED: 1,
        DenominationAuditCategory.REVIEW: 2,
    }

    for (category, jurisdiction, canonical_label), labels in grouped.items():
        findings.append(
            DenominationAuditFinding(
                category=category,
                jurisdiction=jurisdiction,
                canonical_denomination=canonical_label,
                observed_labels=tuple(
                    sorted(labels, key=lambda value: (value.casefold(), value))
                ),
                count=sum(labels.values()),
            )
        )

    findings.sort(
        key=lambda finding: (
            category_order[finding.category],
            finding.jurisdiction.casefold(),
            (finding.canonical_denomination or "").casefold(),
            tuple(label.casefold() for label in finding.observed_labels),
        )
    )

    return DenominationLabelAuditReport(
        findings=tuple(findings),
        records_scanned=len(rows),
    )


def _add_group(
    grouped: dict[
        tuple[DenominationAuditCategory, str, str | None],
        dict[str, int],
    ],
    category: DenominationAuditCategory,
    jurisdiction: str,
    canonical_label: str | None,
    raw_label: str,
) -> None:
    key = (category, jurisdiction, canonical_label)
    labels = grouped.setdefault(key, {})
    labels[raw_label] = labels.get(raw_label, 0) + 1


def _display_raw(value: str | None) -> str:
    if value is None:
        return "<missing>"
    text = value.strip()
    return text if text else "<missing>"
