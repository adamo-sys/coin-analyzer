from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from capture_import.visual_evaluation_harness import (
    load_visual_manifest,
    replay_threshold_frontier,
)
from capture_import.visual_evaluation_runner import run_visual_benchmark
from capture_import.visual_identity_provider import (
    VisualIdentityCandidate,
    VisualIdentityReport,
)


class _Clock:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


class _AbstainingProvider:
    provider_id = "fake-visual"
    model_id = "gpt-5.6-terra"
    configuration = {"fixed": True}

    def identify(self, request):
        candidate = VisualIdentityCandidate(
            rank=1,
            country="Canada",
            denomination="5 cents",
            year="1964",
            type_design="Elizabeth II and beaver",
            confidence=0.9,
            evidence_observations=("visible legends",),
            supporting_image_roles=("obverse", "reverse"),
            provider_id=self.provider_id,
            model_id=self.model_id,
        )
        return VisualIdentityReport(
            outcome="ABSTAINED",
            candidates=(),
            provider_id=self.provider_id,
            model_id=self.model_id,
            response_id="response-1",
            input_tokens=100,
            output_tokens=20,
            raw_structured_result={"outcome": "ABSTAINED", "candidates": []},
            diagnostic_candidates=(candidate,),
        )


class DiagnosticReplayRebuildTests(unittest.TestCase):
    def test_abstention_retains_diagnostics_without_public_prediction(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = load_visual_manifest(root / "benchmarks" / "v2" / "manifest.json")
        one_case = replace(manifest, version="diagnostic-rebuild", cases=(manifest.cases[0],))

        report = run_visual_benchmark(
            one_case,
            _AbstainingProvider(),
            clock=_Clock(1.0, 1.1),
            git_commit="test",
        )

        row = report["cases"][0]
        self.assertEqual(row["outcome"], "ABSTAINED")
        self.assertEqual(row["predictions"], [])
        self.assertEqual(row["ranked_candidates"], [])
        self.assertEqual(row["best_candidate_id"], "candidate-1")
        self.assertEqual(
            row["diagnostic_candidates"][0]["candidate_id"],
            "candidate-1",
        )
        self.assertEqual(row["diagnostic_candidates"][0]["source_score"], 0.9)

    def test_threshold_replay_uses_best_candidate_id_for_abstained_row(self) -> None:
        expected = {
            "country": "Canada",
            "denomination": "5 cents",
            "year": "1964",
        }
        row = {
            "case_id": "abstained-case",
            "outcome": "ABSTAINED",
            "identity_certain": True,
            "expected": expected,
            "predictions": [],
            "ranked_candidates": [],
            "best_candidate_id": "candidate-best",
            "diagnostic_candidates": [
                {
                    "candidate_id": "candidate-other",
                    "country": "United States",
                    "denomination": "5 cents",
                    "year": "1964",
                    "source_score": 0.99,
                },
                {
                    "candidate_id": "candidate-best",
                    **expected,
                    "source_score": 0.8,
                },
            ],
        }

        frontier = replay_threshold_frontier([row], [0.75, 0.85])

        self.assertEqual(frontier[0]["scorable_cases"], 1)
        self.assertEqual(frontier[0]["predicted_cases"], 1)
        self.assertEqual(frontier[0]["full_required_identity_accuracy"], 1.0)
        self.assertEqual(frontier[1]["scorable_cases"], 1)
        self.assertEqual(frontier[1]["abstained_cases"], 1)

    def test_threshold_replay_fails_closed_for_stale_or_duplicate_id(self) -> None:
        base = {
            "case_id": "bad-reference",
            "outcome": "ABSTAINED",
            "identity_certain": True,
            "expected": {
                "country": "Canada",
                "denomination": "5 cents",
                "year": "1964",
            },
            "predictions": [],
            "ranked_candidates": [],
        }

        stale = {
            **base,
            "best_candidate_id": "missing",
            "diagnostic_candidates": [
                {
                    "candidate_id": "candidate-1",
                    "country": "Canada",
                    "denomination": "5 cents",
                    "year": "1964",
                    "source_score": 0.9,
                }
            ],
        }
        duplicate = {
            **base,
            "case_id": "duplicate-reference",
            "best_candidate_id": "candidate-1",
            "diagnostic_candidates": [
                {
                    "candidate_id": "candidate-1",
                    "country": "Canada",
                    "denomination": "5 cents",
                    "year": "1964",
                    "source_score": 0.9,
                },
                {
                    "candidate_id": "candidate-1",
                    "country": "Canada",
                    "denomination": "10 cents",
                    "year": "1964",
                    "source_score": 0.8,
                },
            ],
        }

        frontier = replay_threshold_frontier([stale, duplicate], [0.5])[0]

        self.assertEqual(frontier["scorable_cases"], 0)
        self.assertEqual(frontier["unscorable_cases"], 2)
        self.assertEqual(
            frontier["unscorable_case_ids"],
            ["bad-reference", "duplicate-reference"],
        )


if __name__ == "__main__":
    unittest.main()
