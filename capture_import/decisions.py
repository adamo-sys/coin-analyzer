"""Strict in-memory Skip/Import-as-new decision handling."""

from __future__ import annotations

from .enums import DuplicateDecision
from .errors import PreviewStale
from .models import ImportDecision
from .preview import PackageImportPreview, PreviewDecisionSet


class ImportDecisionModel:
    """Validate explicit collector decisions against one immutable preview."""

    @staticmethod
    def validate(
        preview: PackageImportPreview,
        decisions: PreviewDecisionSet,
    ) -> PreviewDecisionSet:
        if not isinstance(preview, PackageImportPreview):
            raise ValueError("preview must be a PackageImportPreview.")
        preview.validate()
        if not isinstance(decisions, PreviewDecisionSet):
            raise PreviewStale()
        try:
            decisions.validate()
        except ValueError as error:
            raise PreviewStale(error) from error
        if decisions.preview_fingerprint != preview.decisions.preview_fingerprint:
            raise PreviewStale()
        expected = tuple(proposal.source_coin_id for proposal in preview.proposals)
        actual = tuple(decision.source_coin_id for decision in decisions)
        if actual != expected or len(set(actual)) != len(actual):
            raise PreviewStale()
        return decisions

    @classmethod
    def apply(
        cls,
        preview: PackageImportPreview,
        current_decisions: PreviewDecisionSet,
        source_coin_id: str,
        decision: DuplicateDecision,
    ) -> PreviewDecisionSet:
        """Apply one explicit choice to state already bound to ``preview``."""

        cls.validate(preview, current_decisions)
        if not isinstance(source_coin_id, str) or not isinstance(
            decision, DuplicateDecision
        ):
            raise PreviewStale()
        expected = tuple(value.source_coin_id for value in current_decisions)
        if source_coin_id not in expected:
            raise PreviewStale()
        decisions = tuple(
            ImportDecision(value.source_coin_id, decision)
            if value.source_coin_id == source_coin_id
            else value
            for value in current_decisions
        )
        return cls.validate(
            preview,
            PreviewDecisionSet(
                preview_fingerprint=preview.decisions.preview_fingerprint,
                decisions=decisions,
            ),
        )
