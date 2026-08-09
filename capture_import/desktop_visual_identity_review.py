"""Explicit human review for one provider-neutral visual identity proposal.

The visual provider proposes; this module preserves its raw evidence and lets
the desktop operator correct, reject, or defer the proposal.  Collection
mutation remains in the established reviewed-coin persistence boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable
from uuid import uuid4
import zipfile

from .canonical_identity import (
    CanonicalizedField,
    canonicalize_denomination,
    canonicalize_jurisdiction,
)
from .enums import ImageRole
from .media import CapturePackageMediaValidator
from .package import CapturePackageValidator
from .reviewed_coin_collection_entry import ReviewedCoinDraft
from .visual_identity_provider import (
    VisualIdentityCandidate,
    VisualIdentityImage,
    VisualIdentityReport,
    VisualIdentityRequest,
)


class VisualReviewError(ValueError):
    """A visual result cannot safely enter operator review."""


class VisualIdentityAvailabilityError(RuntimeError):
    """The explicitly requested remote provider is not configured."""


@dataclass(frozen=True, slots=True)
class VisualIdentityProposal:
    """One top-ranked proposal with raw, canonical, and provider evidence."""

    candidate: VisualIdentityCandidate
    canonical_country: CanonicalizedField
    canonical_denomination: CanonicalizedField
    provider_id: str
    model_id: str

    @property
    def initial_country(self) -> str:
        value = self.canonical_country.canonical_value
        return value.display_name if value is not None else self.candidate.country

    @property
    def initial_denomination(self) -> str:
        value = self.canonical_denomination.canonical_value
        return value.display_name if value is not None else self.candidate.denomination


@dataclass(frozen=True, slots=True)
class ConfirmedVisualIdentity:
    """The operator-edited identity awaiting the separate save confirmation."""

    country: str
    denomination: str
    year: str
    type_design: str

    def to_reviewed_coin_draft(
        self, proposal: VisualIdentityProposal
    ) -> ReviewedCoinDraft:
        values = {
            "country": self.country.strip(),
            "denomination": self.denomination.strip(),
            "year": self.year.strip(),
        }
        missing = tuple(name for name, value in values.items() if not value)
        if missing:
            raise VisualReviewError(
                "Country, denomination, and year must be confirmed before saving."
            )
        candidate = proposal.candidate
        evidence = " | ".join(candidate.evidence_observations)
        canonical_country = proposal.canonical_country.canonical_value
        canonical_denomination = proposal.canonical_denomination.canonical_value
        draft = ReviewedCoinDraft(
            source_coin_id="coin-1",
            country=values["country"],
            denomination=values["denomination"],
            year=values["year"],
            unmapped_fields=tuple(
                (name, value)
                for name, value in (
                    ("type_design", self.type_design.strip()),
                    ("visual_raw_country", candidate.country),
                    ("visual_raw_denomination", candidate.denomination),
                    (
                        "visual_canonical_country",
                        canonical_country.display_name
                        if canonical_country is not None
                        else "unmapped",
                    ),
                    (
                        "visual_country_rules",
                        ",".join(proposal.canonical_country.normalization_rules)
                        or "unmapped",
                    ),
                    (
                        "visual_canonical_denomination",
                        canonical_denomination.display_name
                        if canonical_denomination is not None
                        else "unmapped",
                    ),
                    (
                        "visual_denomination_rules",
                        ",".join(
                            proposal.canonical_denomination.normalization_rules
                        )
                        or "unmapped",
                    ),
                    ("visual_provider", proposal.provider_id),
                    ("visual_model", proposal.model_id),
                    ("visual_confidence", f"{candidate.confidence:.3f}"),
                    ("visual_evidence", evidence),
                )
                if value
            ),
        )
        draft.validate()
        return draft


def create_visual_identity_proposal(
    report: VisualIdentityReport,
) -> VisualIdentityProposal:
    """Select only the provider's explicit rank-one candidate for review."""

    if not isinstance(report, VisualIdentityReport):
        raise TypeError("report must be a VisualIdentityReport.")
    if report.outcome != "CANDIDATES" or not report.candidates:
        raise VisualReviewError("The visual provider abstained; no coin was changed.")
    candidate = report.candidates[0]
    country = canonicalize_jurisdiction(candidate.country)
    jurisdiction_id = (
        country.canonical_value.canonical_id
        if country.canonical_value is not None
        else None
    )
    denomination = canonicalize_denomination(
        candidate.denomination,
        jurisdiction_id=jurisdiction_id,
    )
    return VisualIdentityProposal(
        candidate=candidate,
        canonical_country=country,
        canonical_denomination=denomination,
        provider_id=report.provider_id,
        model_id=report.model_id,
    )


def create_visual_request_from_capture_package(
    package_path: str | Path,
) -> VisualIdentityRequest:
    """Read the exact validated obverse/reverse bytes from an intake package."""

    path = Path(package_path)
    payload = path.read_bytes()
    validated = CapturePackageValidator().validate_stream(
        package=BytesIO(payload),
        package_basename=path.name,
        package_sha256=sha256(payload).hexdigest(),
        package_byte_length=len(payload),
    )
    media_by_role = {item.role: item for item in validated.media}
    images = []
    with zipfile.ZipFile(path, "r") as archive:
        for role, provider_role in (
            (ImageRole.FRONT, "obverse"),
            (ImageRole.REVERSE, "reverse"),
        ):
            descriptor = media_by_role.get(role)
            if descriptor is None:
                raise VisualReviewError("Both coin image sides are required.")
            image_payload = archive.read(descriptor.archive_path)
            CapturePackageMediaValidator().verify_payload(
                image_payload, descriptor
            )
            images.append(
                VisualIdentityImage(
                    role=provider_role,
                    media_type=descriptor.mime_type,
                    data=image_payload,
                )
            )
    return VisualIdentityRequest(
        scan_id=f"desktop-visual-{uuid4().hex}",
        images=(images[0], images[1]),
    )


class VisualIdentityReviewDialog:
    """Small explicit review screen; it never saves or mutates collection state."""

    def __init__(
        self,
        parent,
        *,
        proposal: VisualIdentityProposal,
        on_confirm: Callable[[ConfirmedVisualIdentity], None],
        on_reject: Callable[[], None],
        on_defer: Callable[[], None],
    ) -> None:
        self.proposal = proposal
        self._on_confirm = on_confirm
        self._on_reject = on_reject
        self._on_defer = on_defer
        self._closed = False
        self.window = tk.Toplevel(parent)
        self.window.title("AI-Assisted Coin Identity Review")
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.defer)

        frame = ttk.Frame(self.window, padding=14)
        frame.grid(sticky="nsew")
        candidate = proposal.candidate
        ttk.Label(
            frame,
            text="AI-generated proposal — verify every field before saving.",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        ttk.Label(
            frame,
            text=(
                f"Provider: {proposal.provider_id}  Model: {proposal.model_id}  "
                f"Confidence: {candidate.confidence:.0%}"
            ),
        ).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(
            frame,
            text="Evidence: " + " | ".join(candidate.evidence_observations),
            wraplength=640,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 10))
        ttk.Label(
            frame,
            text="Supporting image roles: " + ", ".join(candidate.supporting_image_roles),
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 8))

        self.country = tk.StringVar(value=proposal.initial_country)
        self.denomination = tk.StringVar(value=proposal.initial_denomination)
        self.year = tk.StringVar(value=candidate.year or "")
        self.type_design = tk.StringVar(value=candidate.type_design or "")
        for row, (label, variable) in enumerate(
            (
                ("Country / jurisdiction", self.country),
                ("Denomination", self.denomination),
                ("Year", self.year),
                ("Type / design", self.type_design),
            ),
            start=4,
        ):
            ttk.Label(frame, text=label + ":").grid(row=row, column=0, sticky="w")
            ttk.Entry(frame, textvariable=variable, width=52).grid(
                row=row, column=1, sticky="ew", pady=2
            )

        raw = (
            f"Raw provider values: {candidate.country}; {candidate.denomination}; "
            f"{candidate.year or 'unknown'}; {candidate.type_design or 'unknown'}"
        )
        ttk.Label(frame, text=raw, wraplength=640).grid(
            row=8, column=0, columnspan=2, sticky="w", pady=(10, 4)
        )
        country_rules = ", ".join(proposal.canonical_country.normalization_rules) or "unmapped"
        denomination_rules = ", ".join(
            proposal.canonical_denomination.normalization_rules
        ) or "unmapped"
        ttk.Label(
            frame,
            text=(
                "Canonical presentation rules — country: " + country_rules
                + "; denomination: " + denomination_rules
            ),
            wraplength=640,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(0, 4))
        buttons = ttk.Frame(frame)
        buttons.grid(row=10, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Reject", command=self.reject).pack(side="left")
        ttk.Button(buttons, text="Defer", command=self.defer).pack(
            side="left", padx=8
        )
        ttk.Button(
            buttons,
            text="Confirm Reviewed Identity…",
            command=self.confirm,
        ).pack(side="left")
        frame.columnconfigure(1, weight=1)

    def confirm(self) -> None:
        reviewed = ConfirmedVisualIdentity(
            country=self.country.get(),
            denomination=self.denomination.get(),
            year=self.year.get(),
            type_design=self.type_design.get(),
        )
        try:
            reviewed.to_reviewed_coin_draft(self.proposal)
        except VisualReviewError as error:
            messagebox.showwarning(
                "Visual Review Incomplete", str(error), parent=self.window
            )
            return
        if self._finish():
            self._on_confirm(reviewed)

    def reject(self) -> None:
        if self._finish():
            self._on_reject()

    def defer(self) -> None:
        if self._finish():
            self._on_defer()

    def _finish(self) -> bool:
        if self._closed:
            return False
        self._closed = True
        self.window.destroy()
        return True


def create_visual_identity_review_dialog(**kwargs) -> VisualIdentityReviewDialog:
    return VisualIdentityReviewDialog(**kwargs)
