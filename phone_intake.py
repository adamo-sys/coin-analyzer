"""Explicit Phone Inbox pairs and fail-closed save completion; no inference authority."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from atomic_json import write_json_atomically
from capture_import.lock import PackageImportLock
from capture_import.standalone_image_intake import canonical_standalone_image_payload


class PhoneIntakeError(ValueError):
    """Pairing or recovery requires collector attention."""


class PhoneIntake:
    def __init__(self, path: str = "data/phone_intake.json") -> None:
        self.path = Path(path).absolute()

    def records(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data["version"] != 1 or not isinstance(data["pairs"], dict):
                raise ValueError("Invalid intake state")
            for key, pair in data["pairs"].items():
                if pair["id"] != key or pair["state"] not in {"READY", "SAVING", "SAVED"}:
                    raise ValueError("Invalid pair")
                if set(pair["images"]) != {"front", "reverse"}:
                    raise ValueError("Invalid roles")
            return data["pairs"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise PhoneIntakeError("Phone Intake state is unreadable; do not reimport or resave.") from error

    @contextmanager
    def _edit(self) -> Iterator[dict[str, Any]]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = PackageImportLock.acquire(self.path.with_suffix(".lock"), import_id=str(uuid4()))
        try:
            pairs = self.records()
            yield pairs
            write_json_atomically(str(self.path), {"version": 1, "pairs": pairs})
        finally:
            lock.release()

    @staticmethod
    def image(path: str) -> dict[str, str]:
        source = Path(path).absolute()
        if source.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            raise PhoneIntakeError("Paired review requires JPEG or PNG images.")
        from PIL import Image
        with Image.open(source) as image:
            image.verify()
        return {"path": str(source), "sha256": sha256(source.read_bytes()).hexdigest()}

    def confirm_pair(self, front: str, reverse: str) -> str:
        images = {"front": self.image(front), "reverse": self.image(reverse)}
        hashes = {image["sha256"] for image in images.values()}
        if len(hashes) != 2:
            raise PhoneIntakeError("Select two different images for one coin.")
        with self._edit() as pairs:
            if any(hashes.intersection(image["sha256"] for image in p["images"].values()) for p in pairs.values()):
                raise PhoneIntakeError("An image already belongs to a confirmed pair; open that pair instead.")
            pair_id = str(uuid4())
            pairs[pair_id] = {"id": pair_id, "images": images, "state": "READY", "save": None}
        return pair_id

    def swap(self, pair_id: str) -> None:
        with self._edit() as pairs:
            pair = pairs[pair_id]
            if pair["state"] != "READY":
                raise PhoneIntakeError("A saving or saved pair cannot change roles.")
            pair["images"]["front"], pair["images"]["reverse"] = pair["images"]["reverse"], pair["images"]["front"]

    def review_paths(self, pair_id: str) -> tuple[str, str]:
        pair = self.records()[pair_id]
        if pair["state"] != "READY":
            raise PhoneIntakeError("This pair is saved or requires recovery; it cannot be saved again.")
        for image in pair["images"].values():
            if PhoneIntake.image(image["path"]) != image:
                raise PhoneIntakeError("A confirmed pair image changed; review is blocked.")
        return pair["images"]["front"]["path"], pair["images"]["reverse"]["path"]

    def reserve(self, pair_id: str, collection_path: str, draft: Any) -> dict[str, Any]:
        self.review_paths(pair_id)
        with self._edit() as pairs:
            pair = pairs[pair_id]
            if pair["state"] != "READY":
                raise PhoneIntakeError("The pair is no longer available.")
            intent = {
                "collection": str(Path(collection_path).absolute()), "media_base": str(Path.cwd()),
                "item_id": str(uuid4()), "date_added": datetime.now().isoformat(),
                "identity": {name: getattr(draft, name).strip() for name in ("country", "denomination", "year", "type_design")},
            }
            pair["save"] = intent
            pair["state"] = "SAVING"
        return intent

    @staticmethod
    def _saved_record(pair: dict[str, Any], collection_path: str) -> dict[str, Any] | None:
        intent = pair["save"]
        path = Path(collection_path).absolute()
        if path != Path(intent["collection"]):
            raise PhoneIntakeError("Open the original target collection before recovery.")
        # Read disk, never infer success from a possibly stale in-memory collection.
        records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if not isinstance(records, list):
            raise PhoneIntakeError("Cannot establish collection save outcome.")
        matches = [row for row in records if row["id"] == intent["item_id"]]
        if not matches:
            return None
        if len(matches) != 1:
            raise PhoneIntakeError("Ambiguous saved collection record.")
        record = matches[0]
        if record.get("date_added") != intent["date_added"] or any(record.get(k, "") != v for k, v in intent["identity"].items()):
            raise PhoneIntakeError("Saved record differs from the reserved review; recovery is blocked.")
        photos = record.get("photos", [])
        for image in pair["images"].values():
            if PhoneIntake.image(image["path"]) != image:
                raise PhoneIntakeError("A confirmed pair image changed; recovery is blocked.")
        expected = {
            "FRONT": sha256(canonical_standalone_image_payload(pair["images"]["front"]["path"])).hexdigest(),
            "BACK": sha256(canonical_standalone_image_payload(pair["images"]["reverse"]["path"])).hexdigest(),
        }
        if len(photos) != 2:
            raise PhoneIntakeError("Saved photo evidence does not match the pair.")
        actual = {photo["role"]: sha256((Path(intent["media_base"]) / photo["path"]).read_bytes()).hexdigest() for photo in photos}
        if actual != expected:
            raise PhoneIntakeError("Saved photo evidence does not match the pair.")
        return record

    def complete(self, pair_id: str, collection_path: str) -> str:
        """Reconcile only; never create a coin, invoke a provider, or retry a save."""
        with self._edit() as pairs:
            pair = pairs[pair_id]
            if pair["state"] not in {"SAVING", "SAVED"}:
                raise PhoneIntakeError("There is no save to reconcile.")
            if self._saved_record(pair, collection_path) is None:
                raise PhoneIntakeError("Save outcome unresolved. No automatic resave is permitted.")
            pair["state"] = "SAVED"
            item_id = pair["save"]["item_id"]
        return item_id

    def clean_save_failure(self, pair_id: str, collection_path: str) -> None:
        """Only the caller's proven rolled-back persistence error may release intent."""
        with self._edit() as pairs:
            pair = pairs[pair_id]
            if pair["state"] != "SAVING" or self._saved_record(pair, collection_path) is not None:
                raise PhoneIntakeError("Save outcome requires recovery; do not resave.")
            pair["state"], pair["save"] = "READY", None

