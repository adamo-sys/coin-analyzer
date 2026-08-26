#!/usr/bin/env python3
"""Hands-off local orchestrator for the adversarial-reference benchmark preparation.

Run from the repository root:
    python benchmarks/adversarial_reference/run_pipeline.py

The runner executes only bounded preparation/diagnostic steps that exist in the
checked-out branch. It deliberately does NOT run retrieval scoring and does NOT
modify source_inventory_v1.json. It stops on a real blocker and prints the next
action instead of requiring the user to approve each intermediate step.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
PYTHON = sys.executable


def run(script: str, *, required: bool = True) -> int:
    path = ROOT / script
    if not path.is_file():
        if required:
            print(f"BLOCKED: required step missing: {script}")
            return 2
        print(f"SKIP: {script} not present")
        return 0
    print(f"\n=== {script} ===")
    proc = subprocess.run([PYTHON, str(path)], cwd=REPO)
    if proc.returncode:
        print(f"BLOCKED: {script} exited {proc.returncode}")
    return proc.returncode


def load(name: str) -> dict:
    path = ROOT / name
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    print("Adversarial reference pipeline: preparation mode")
    print("Guardrails: frozen cases; inventory unchanged; retrieval scoring disabled.")

    # Rebuild the current deterministic preparation artifacts in dependency order.
    for script in (
        "assemble_final_asset_candidate_plan.py",
        "select_numista_1956_reference_candidate.py",
        "seed_final_two_dime_assets.py",
        "select_unique_final_assets.py",
        "report_unresolved_unique_asset_slots.py",
    ):
        rc = run(script)
        if rc:
            return rc

    audit = load("unique_final_assets.json")
    summary = audit.get("summary") or {}
    selected = int(summary.get("slots_selected") or summary.get("selected_slots") or 0)
    unresolved = int(summary.get("slots_unresolved") or summary.get("unresolved_slots") or 0)
    unique = int(summary.get("selected_unique_sha256") or summary.get("unique_sha256") or selected)

    unresolved_payload = load("unresolved_unique_asset_slots.json")
    unresolved_rows = (
        unresolved_payload.get("unresolved")
        or unresolved_payload.get("slots")
        or unresolved_payload.get("results")
        or []
    )
    if isinstance(unresolved_rows, list) and unresolved_rows:
        unresolved = len(unresolved_rows)

    print("\n=== PIPELINE CHECKPOINT ===")
    print(f"Selected slots: {selected or 'see audit'}")
    print(f"Unresolved slots: {unresolved}")
    print(f"Unique selected hashes: {unique or 'see audit'}")

    if unresolved:
        print("\nPreparation is not yet freeze-ready.")
        print("The runner stopped before retrieval scoring, as designed.")
        print("Next engineering task: resolve only the remaining unique-asset slots, then rerun this same command.")
        return 3

    if selected and selected != 25:
        print(f"BLOCKED: expected 25 selected slots, found {selected}.")
        return 4
    if unique and unique != 25:
        print(f"BLOCKED: expected 25 unique asset hashes, found {unique}.")
        return 5

    rc = run("audit_source_asset_independence.py")
    if rc:
        return rc

    print("\nPREPARATION COMPLETE: candidate set resolved and independence audit executed.")
    print("Retrieval scoring was NOT run. source_inventory_v1.json was NOT modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
