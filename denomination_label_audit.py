"""Read-only audit of collection denomination label consistency."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from capture_import.canonical_identity import (
    CanonicalizationStatus,
    canonicalize_denomination,
    canonicalize_jurisdiction,
)


CANONICAL = "canonical"
PROPOSED = "proposed"
REVIEW = "review"


@dataclass(frozen=True)
class DenominationLabelFinding:
    country: str
    current_label: str
    record_count: int
    status: str
    proposed_label: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class DenominationLabelAudit:
    findings: tuple[DenominationLabelFinding, ...]

    @property
    def record_count(self) -> int:
        return sum(finding.record_count for finding in self.findings)

    def format_text(self) -> str:
        lines = [
            "Denomination Label Audit",
            "Read-only report: no collection data was changed.",
            "",
        ]
        for finding in self.findings:
            location = finding.country or "(country not set)"
            label = finding.current_label or "(blank)"
            detail = f"{location} | {label} | {finding.record_count} record(s)"
            if finding.status == PROPOSED:
                detail += f" | proposed: {finding.proposed_label}"
            elif finding.status == REVIEW and finding.reason:
                detail += f" | review: {finding.reason}"
            else:
                detail += " | canonical"
            lines.append(detail)
        if not self.findings:
            lines.append("No denomination labels found.")
        return "\n".join(lines)


def audit_denomination_labels(
    records: Iterable[Mapping[str, object]],
) -> DenominationLabelAudit:
    """Return a deterministic, metadata-only label audit without mutating records."""

    counts: dict[tuple[str, str], int] = {}
    for record in records:
        country = str(record.get("country") or "").strip()
        denomination = str(record.get("denomination") or "").strip()
        key = (country, denomination)
        counts[key] = counts.get(key, 0) + 1

    findings: list[DenominationLabelFinding] = []
    for (country, denomination), count in sorted(
        counts.items(),
        key=lambda item: (
            item[0][0].casefold(),
            item[0][0],
            item[0][1].casefold(),
            item[0][1],
        ),
    ):
        jurisdiction = canonicalize_jurisdiction(country)
        jurisdiction_id = (
            jurisdiction.canonical_value.canonical_id
            if jurisdiction.status is CanonicalizationStatus.MAPPED
            and jurisdiction.canonical_value is not None
            else None
        )
        canonical = canonicalize_denomination(
            denomination,
            jurisdiction_id=jurisdiction_id,
        )

        if (
            canonical.status is not CanonicalizationStatus.MAPPED
            or canonical.canonical_value is None
        ):
            findings.append(
                DenominationLabelFinding(
                    country=country,
                    current_label=denomination,
                    record_count=count,
                    status=REVIEW,
                    reason="no safe canonical mapping",
                )
            )
            continue

        proposed = canonical.canonical_value.display_name
        status = CANONICAL if denomination == proposed else PROPOSED
        findings.append(
            DenominationLabelFinding(
                country=country,
                current_label=denomination,
                record_count=count,
                status=status,
                proposed_label=proposed if status == PROPOSED else None,
            )
        )

    return DenominationLabelAudit(tuple(findings))
