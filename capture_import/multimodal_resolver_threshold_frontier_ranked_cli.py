"""Threshold frontier that preserves persisted best candidate IDs.

This wrapper fixes the v1 frontier helper, which overwrote best_candidate_id
with accepted_candidate_id and therefore made abstained rows unscorable again.
It delegates all threshold evaluation to the existing frontier module while
preserving enriched best-candidate IDs when present.
"""

from __future__ import annotations

from typing import Mapping

from . import multimodal_resolver_threshold_frontier_cli as base


def _augment_best_ids(rows: list[Mapping[str, object]]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in rows:
        clone = dict(row)
        persisted = row.get("best_candidate_id")
        accepted = row.get("accepted_candidate_id")
        clone["best_candidate_id"] = persisted if persisted is not None else accepted
        out.append(clone)
    return out


base._augment_best_ids = _augment_best_ids


def main(argv=None) -> int:
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
