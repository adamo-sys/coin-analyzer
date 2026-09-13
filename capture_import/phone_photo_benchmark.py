"""Local-only paired phone-photo baseline; never changes recognition policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

FIELDS = ("jurisdiction", "denomination", "year", "type_design")
SCHEMA = "coin-analyzer-phone-photo-v1"
EXECUTION_STATUSES = {
    "completed_prediction", "completed_abstention", "validation_rejected",
    "provider_runtime_failure", "not_attempted",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_digest(manifest: dict) -> str:
    return digest(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())


def validate_manifest(manifest: object) -> dict:
    """Validate metadata without opening any image or contacting a provider."""
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise ValueError("Invalid phone-photo manifest schema")
    if manifest.get("privacy") != "private-local-only":
        raise ValueError("Phone photographs must remain private-local-only")
    if manifest.get("version") != "1.0" or not manifest.get("label_provenance"):
        raise ValueError("Version and label provenance are required")
    rows = manifest.get("specimens")
    if not isinstance(rows, list) or not rows:
        raise ValueError("A nonempty specimen inventory is required")
    ids, paths, hashes = set(), set(), set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Specimen must be an object")  # noqa: TRY004 -- uniform malformed-manifest contract
        identity = row.get("specimen_id")
        if not isinstance(identity, str) or not re.fullmatch(r"CA-BENCH-\d{3}", identity):
            raise ValueError("Invalid specimen ID")
        if identity in ids:
            raise ValueError("Duplicate specimen ID")
        ids.add(identity)
        if row.get("difficulty") not in ("easy", "medium", "hard"):
            raise ValueError("Invalid difficulty")
        tags = row.get("challenge_tags")
        if not isinstance(tags, list) or not tags or any(
            not isinstance(tag, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", tag)
            for tag in tags
        ) or len(tags) != len(set(tags)):
            raise ValueError("Invalid challenge tags")
        images = row.get("images")
        if not isinstance(images, list) or len(images) != 2:
            raise ValueError("Exactly two images per specimen are required")
        if {image.get("role") for image in images if isinstance(image, dict)} != {"obverse", "reverse"}:
            raise ValueError("Exactly one reviewed obverse and reverse role are required")
        for image in images:
            if not isinstance(image, dict):
                raise ValueError("Image must be an object")  # noqa: TRY004 -- uniform malformed-manifest contract
            path, sha = image.get("path"), image.get("sha256")
            if not isinstance(path, str) or not re.fullmatch(r"IMG_\d{4}\.JPG", path):
                raise ValueError("Image reference must be an original relative filename")
            if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
                raise ValueError("Invalid image SHA-256")
            if path.casefold() in paths or sha in hashes:
                raise ValueError("Duplicate image reference or bytes")
            paths.add(path.casefold())
            hashes.add(sha)
        truth = row.get("ground_truth")
        if not isinstance(truth, dict) or set(truth) != set(FIELDS):
            raise ValueError("Exactly four ground-truth fields are required")
        for field in FIELDS:
            item = truth[field]
            if not isinstance(item, dict) or set(item) != {"value", "verification"}:
                raise ValueError("Invalid ground-truth record")
            value, status = item["value"], item["verification"]
            if status == "verified":
                if not isinstance(value, str) or not value.strip():
                    raise ValueError("Verified values must be nonempty strings")
                if field == "year" and not re.fullmatch(r"\d{4}", value):
                    raise ValueError("Verified year must have four digits")
            elif status != "unverified" or value is not None:
                raise ValueError("Unverified values must be null")
    return manifest


def load_manifest(path: Path) -> dict:
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON object key")
            result[key] = value
        return result

    manifest = validate_manifest(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys))
    freeze = path.with_suffix(".sha256")
    if freeze.exists() and freeze.read_text(encoding="ascii").strip() != manifest_digest(manifest):
        raise ValueError("Frozen manifest digest changed")
    return manifest


def read_images(manifest: dict, root: Path) -> list[tuple[bytes, bytes]]:
    """Read only explicitly enumerated files, checking containment and exact bytes."""
    validate_manifest(manifest)
    root = root.resolve(strict=True)
    pairs = []
    for row in manifest["specimens"]:
        pair = []
        for image in sorted(row["images"], key=lambda item: item["role"]):
            path = (root / image["path"]).resolve(strict=True)
            if path.parent != root:
                raise ValueError("Image escapes source directory")
            data = path.read_bytes()
            if digest(data) != image["sha256"]:
                raise ValueError(f"Image bytes changed: {image['path']}")
            pair.append(data)
        pairs.append((pair[0], pair[1]))
    return pairs


def normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def score(manifest: dict, predictions: list[dict]) -> dict:
    """Strict exact matching; unverified truth and execution errors are separate."""
    validate_manifest(manifest)
    if not isinstance(predictions, list) or any(not isinstance(p, dict) for p in predictions):
        raise ValueError("Predictions must be records")
    expected_ids = [r["specimen_id"] for r in manifest["specimens"]]
    actual_ids = [p.get("specimen_id") for p in predictions]
    if any(not isinstance(identity, str) for identity in actual_ids):
        raise ValueError("Prediction IDs must be strings")
    if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != set(expected_ids):
        raise ValueError("Predictions must cover every specimen exactly once")
    indexed = {p["specimen_id"]: p for p in predictions}
    rows = []
    for specimen in manifest["specimens"]:
        prediction = indexed[specimen["specimen_id"]]
        values = prediction.get("prediction")
        if not isinstance(values, dict) or not set(values).issubset(FIELDS):
            raise ValueError("Invalid prediction fields")
        if any(value is not None and not isinstance(value, str) for value in values.values()):
            raise ValueError("Prediction values must be strings or null")
        status = prediction.get("execution_status")
        if not isinstance(status, str) or status not in EXECUTION_STATUSES:
            raise ValueError("Explicit specimen execution status is required")
        failed = status in {"validation_rejected", "provider_runtime_failure", "not_attempted"}
        if (failed or status == "completed_abstention") and values:
            raise ValueError("Failed, rejected, unattempted or abstaining rows cannot supply predictions")
        if status == "completed_prediction" and not values:
            raise ValueError("A completed prediction must contain a validated field")
        if status == "validation_rejected" and (
            not isinstance(prediction.get("validator_failure"), str)
            or not prediction["validator_failure"].strip()
            or "raw_provider_output" not in prediction
        ):
            raise ValueError("Validator rejections require retained raw output and reason")
        results = {}
        for field, truth in specimen["ground_truth"].items():
            value = values.get(field)
            if truth["verification"] == "unverified":
                result = "unscorable"
            elif failed:
                result = {"validation_rejected": "validation_rejected",
                          "provider_runtime_failure": "execution_failed",
                          "not_attempted": "not_attempted"}[status]
            elif value is None or normalized(value) in {"", "unknown", "none", "n/a", "unavailable"}:
                result = "abstained"
            else:
                result = "correct" if normalized(value) == normalized(truth["value"]) else "incorrect"
            results[field] = result
        verified = [results[f] for f in FIELDS if specimen["ground_truth"][f]["verification"] == "verified"]
        rows.append({**prediction, "difficulty": specimen["difficulty"],
                     "challenge_tags": specimen["challenge_tags"],
                     "ground_truth": specimen["ground_truth"], "results": results,
                     "verified_field_count": len(verified),
                     "exact_identity": None if failed or not verified else all(v == "correct" for v in verified)})
    return {"execution": execution_summary(rows), "metrics": aggregate(rows), "by_difficulty": {
        level: aggregate([r for r in rows if r["difficulty"] == level])
        for level in ("easy", "medium", "hard")}, "by_challenge_tag": {
        tag: aggregate([r for r in rows if tag in r["challenge_tags"]])
        for tag in sorted({t for r in rows for t in r["challenge_tags"]})}, "specimens": rows}


def execution_summary(rows: list[dict]) -> dict:
    counts = Counter(row["execution_status"] for row in rows)
    return {"specimens_total": len(rows),
            "specimens_attempted": len(rows) - counts["not_attempted"],
            "specimens_with_validated_predictions": counts["completed_prediction"],
            "specimens_with_validated_abstentions": counts["completed_abstention"],
            "specimens_rejected_before_scoring": counts["validation_rejected"],
            "specimens_with_provider_runtime_failure": counts["provider_runtime_failure"],
            "specimens_not_attempted": counts["not_attempted"],
            "execution_complete": bool(rows) and counts["not_attempted"] == 0}


def aggregate(rows: list[dict]) -> dict:
    fields = {}
    for field in FIELDS:
        counts = Counter(row["results"][field] for row in rows)
        denominator = sum(counts[s] for s in ("correct", "incorrect", "abstained"))
        fields[field] = {s: counts[s] for s in ("correct", "incorrect", "abstained", "unscorable", "execution_failed", "validation_rejected", "not_attempted")}
        fields[field].update(denominator=denominator,
                             accuracy=counts["correct"] / denominator if denominator else None,
                             abstention_rate=counts["abstained"] / denominator if denominator else None)
    exact = [r["exact_identity"] for r in rows if r["exact_identity"] is not None]
    denominator = sum(f["denominator"] for f in fields.values())
    return {"specimen_count": len(rows), "execution": execution_summary(rows), "fields": fields,
            "exact_identity_denominator": len(exact),
            "exact_identity_correct": sum(exact),
            "exact_identity_accuracy": sum(exact) / len(exact) if exact else None,
            "abstention_rate": sum(f["abstained"] for f in fields.values()) / denominator if denominator else None,
            "infrastructure_failures": sum(r["execution_status"] == "provider_runtime_failure" for r in rows)}


def resume_rejected_rows(path: Path, expected_sha256: str, provenance: dict) -> tuple[dict, dict]:
    """Import only proven validator rejections from the original stopped baseline.

    This deliberately bounded migration cannot import successful predictions or
    arbitrary old failures. It replays the unchanged validator locally, not AI.
    """
    from .visual_identity_provider import (
        VisualIdentityMalformedOutput,
        _validated_report,
    )

    data = path.read_bytes()
    if digest(data) != expected_sha256:
        raise ValueError("Resume artifact SHA-256 mismatch")
    archive = json.loads(data)
    if not isinstance(archive, dict):
        raise ValueError("Resume archive must be an object")  # noqa: TRY004 -- uniform malformed-archive contract
    for key in ("schema", "manifest_sha256", "manifest", "provider_configuration",
                "provider_configuration_sha256", "provider_source_sha256", "privacy"):
        if archive.get(key) != provenance[key]:
            raise ValueError(f"Resume provenance mismatch: {key}")
    if archive.get("source_integrity_after_run") != "verified":
        raise ValueError("Resume archive lacks verified source integrity")
    rows = archive.get("specimens")
    ids = [r["specimen_id"] for r in provenance["manifest"]["specimens"]]
    if (not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows)
            or [r.get("specimen_id") for r in rows] != ids):
        raise ValueError("Resume archive specimen inventory differs")
    reused = {}
    for index, row in enumerate(rows):
        if row.get("prediction") != {}:
            raise ValueError("Only rejected evidence from a stopped run can be resumed")
        if row.get("ground_truth") != provenance["manifest"]["specimens"][index]["ground_truth"]:
            raise ValueError("Resume row ground truth differs from its specimen")
        failure = row.get("infrastructure_failure")
        if index > 0 and failure == "not_run_after_failure" and row.get("raw_provider_output") is None:
            continue
        if index != 0 or failure != "VisualIdentityMalformedOutput" or not isinstance(row.get("raw_provider_output"), dict):
            raise ValueError("Resume supports only retained structured validator rejections")
        if not isinstance(row.get("response_id"), str) or not row["response_id"]:
            raise ValueError("Resume rejection lacks response identity")
        try:
            _validated_report(row["raw_provider_output"], object())
        except VisualIdentityMalformedOutput as error:
            reason = str(error)
        else:
            raise ValueError("Archived rejection no longer fails the production validator")
        reused[row["specimen_id"]] = {
            key: row.get(key) for key in ("specimen_id", "prediction", "raw_provider_output",
                                        "response_id", "input_tokens", "output_tokens", "latency_seconds")}
        reused[row["specimen_id"]].update(
            execution_status="validation_rejected", validator_failure=reason,
            infrastructure_failure=None, reused_from_report_sha256=expected_sha256)
    if not reused:
        raise ValueError("Archive contains no reusable validator rejection")
    return reused, {"report_sha256": expected_sha256,
                    "original_generated_at": archive.get("generated_at"),
                    "original_git_commit": archive.get("git_commit"),
                    "original_scorer_source_sha256": archive.get("scorer_source_sha256"),
                    "reused_specimens": list(reused)}


def finalize_report(provenance: dict, predictions: list[dict], source_integrity: str,
                    *, interrupted: bool = False) -> dict:
    """Missing execution records stay explicitly unattempted and cannot be success."""
    manifest = provenance["manifest"]
    seen = {row["specimen_id"] for row in predictions}
    rows = [*predictions, *({"specimen_id": row["specimen_id"], "prediction": {},
                           "execution_status": "not_attempted", "infrastructure_failure": None}
                          for row in manifest["specimens"] if row["specimen_id"] not in seen)]
    scored = score(manifest, rows)
    return {**provenance, "source_integrity_after_run": source_integrity,
            "interrupted": interrupted,
            "baseline_complete": (not interrupted and source_integrity == "verified"
                                  and scored["execution"]["execution_complete"]), **scored}


def run_baseline(manifest: dict, root: Path, provider, *, upload_authorized: bool = False,
                 checkpoint=None, resume_report: Path | None = None, resume_sha256: str | None = None) -> dict:
    """One call per pair using original bytes and the production rank-one outcome."""
    if manifest.get("execution_blocker"):
        raise ValueError("Corpus evidence conflict unresolved; baseline execution is blocked")
    if not upload_authorized:
        raise PermissionError("Explicit authorization to upload these private photos is required")
    from .visual_identity_provider import (
        VisualIdentityImage,
        VisualIdentityMalformedOutput,
        VisualIdentityRequest,
    )

    pairs = read_images(manifest, root)  # Preflight entire corpus before any call.
    configuration = dict(provider.configuration)
    provenance: dict[str, Any] = {
        "schema": SCHEMA, "manifest_sha256": manifest_digest(manifest),
        "execution_contract_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "provider_configuration": configuration,
        "provider_configuration_sha256": digest(json.dumps(configuration, sort_keys=True).encode()),
        "provider_source_sha256": digest(Path(__file__).with_name("visual_identity_provider.py").read_bytes()),
        "scorer_source_sha256": digest(Path(__file__).read_bytes()),
        "runtime": {"python": sys.version, "platform": platform.platform()},
        "privacy": "private-local-only",
        "manifest": manifest,
    }
    reused = {}
    if (resume_report is None) != (resume_sha256 is None):
        raise ValueError("Resume report and pinned digest must be supplied together")
    if resume_report is not None:
        assert resume_sha256 is not None
        reused, provenance["resume"] = resume_rejected_rows(resume_report, resume_sha256, provenance)
    if checkpoint:
        checkpoint({"run_provenance": provenance})
    predictions = []
    interrupted = False
    for specimen, pair in zip(manifest["specimens"], pairs):
        if specimen["specimen_id"] in reused:
            predictions.append(reused[specimen["specimen_id"]])
            if checkpoint:
                checkpoint(predictions[-1])
            continue
        request = VisualIdentityRequest(specimen["specimen_id"], (
            VisualIdentityImage("obverse", "image/jpeg", pair[0]),
            VisualIdentityImage("reverse", "image/jpeg", pair[1]),
        ))
        started = perf_counter()
        try:
            report = provider.identify(request)
            raw = asdict(report)
            values = report.candidates[0].as_prediction() if report.outcome == "CANDIDATES" and report.candidates else {}
            if "country" in values:
                values["jurisdiction"] = values.pop("country")
        except KeyboardInterrupt:
            predictions.append({"specimen_id": specimen["specimen_id"], "prediction": {},
                                "execution_status": "provider_runtime_failure",
                                "infrastructure_failure": "KeyboardInterrupt"})
            if checkpoint:
                checkpoint(predictions[-1])
            interrupted = True
            break
        except Exception as error:  # noqa: BLE001 -- isolate arbitrary provider/runtime failures per specimen
            # Do not archive arbitrary exception text: it may contain credentials/URLs.
            rejected = isinstance(error, VisualIdentityMalformedOutput)
            predictions.append({"specimen_id": specimen["specimen_id"], "prediction": {},
                                "execution_status": "validation_rejected" if rejected else "provider_runtime_failure",
                                "validator_failure": str(error) if rejected else None,
                                "infrastructure_failure": None if rejected else type(error).__name__,
                                "raw_provider_output": getattr(error, "raw_provider_output", None),
                                "response_id": getattr(error, "response_id", None),
                                "input_tokens": getattr(error, "input_tokens", None),
                                "output_tokens": getattr(error, "output_tokens", None),
                                "latency_seconds": perf_counter() - started})
            if checkpoint:
                checkpoint(predictions[-1])
            continue  # Isolate this specimen; do not repair, retry or substitute.
        predictions.append({"specimen_id": specimen["specimen_id"], "prediction": values,
                            "execution_status": "completed_prediction" if values else "completed_abstention",
                            "infrastructure_failure": None, "raw_provider_output": raw,
                            "latency_seconds": perf_counter() - started})
        if checkpoint:
            checkpoint(predictions[-1])
    try:
        read_images(manifest, root)  # Verify source preservation, retaining evidence on failure.
        source_integrity = "verified"
    except (OSError, ValueError):
        source_integrity = "failed"
    return finalize_report(provenance, predictions, source_integrity, interrupted=interrupted)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--execute-openai-upload", action="store_true")
    parser.add_argument("--resume-rejected-report", type=Path)
    parser.add_argument("--resume-sha256")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    read_images(manifest, args.source)
    if not args.execute_openai_upload:
        print(json.dumps({"validated_specimens": len(manifest["specimens"]), "manifest_sha256": manifest_digest(manifest)}))
        return 0
    if manifest.get("execution_blocker"):
        raise ValueError("Corpus evidence conflict unresolved; baseline execution is blocked")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY unavailable; no provider executed")
    from .visual_identity_provider import OpenAITerraVisualIdentityProvider

    output = Path(__file__).resolve().parents[1] / "debug_outputs" / "phone-photo-v1"
    output.mkdir(parents=True, exist_ok=True)
    target = output / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    # Exclusive creation and per-response fsync keep paid evidence on interruption.
    with target.with_suffix(".jsonl").open("x", encoding="utf-8") as journal:
        def checkpoint(record):
            journal.write(json.dumps(record, ensure_ascii=False) + "\n")
            journal.flush()
            os.fsync(journal.fileno())

        report = run_baseline(manifest, args.source, OpenAITerraVisualIdentityProvider(),
                              upload_authorized=True, checkpoint=checkpoint,
                              resume_report=args.resume_rejected_report, resume_sha256=args.resume_sha256)
    with target.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(target)
    return 0 if report["baseline_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
