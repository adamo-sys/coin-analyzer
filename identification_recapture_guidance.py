"""Deterministic, advisory photo suggestions from existing desktop evidence."""

from collections.abc import Mapping

from legacy_coin_recognition_capability import complete_year


def build_recapture_guidance(
    result: Mapping[str, object], *, reverse_missing: bool = False,
) -> tuple[str, ...]:
    """Return at most two suggestions, date first, without changing evidence.

    Consume the adapter's complete-year list, not scores or raw OCR. An absent
    or malformed list does not establish missing date evidence. The caller must
    establish missing reverse input from explicit supplied-photo roles; OCR
    orientation or absence of reverse-specific recognition is insufficient.
    Mintmarks and image defects have no validated signals in this boundary.
    """
    if result.get("success") is not True:
        return ()
    suggestions = []
    candidates = result.get("year_candidates")
    if isinstance(candidates, list):
        years = {year for value in candidates if (year := complete_year(value)) is not None}
        if len(years) > 1:
            suggestions.append("The date readings disagree. Try a clearer close-up of the date.")
        elif not candidates and complete_year(result.get("year")) is None:
            suggestions.append("No complete date was read. Take a closer photo of the coin's date.")

    unresolved = any(
        str(result.get(field) or "").strip().casefold() in {"", "none", "unknown"}
        for field in ("country", "denomination", "year")
    )
    if reverse_missing is True and unresolved:
        suggestions.append("Photograph the reverse side to provide additional identification evidence.")
    return tuple(suggestions)
