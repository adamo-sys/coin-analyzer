"""Generated, bounded capture-package fixtures for Sprint 3 tests."""

from __future__ import annotations

from io import BytesIO
import json
import zipfile

from PIL import Image


def image_bytes(image_format: str = "PNG", size: tuple[int, int] = (2, 3)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, (150, 120, 80)).save(output, format=image_format)
    return output.getvalue()


def manifest_dict(
    front: bytes | None = None,
    reverse: bytes | None = None,
) -> dict[str, object]:
    front = image_bytes() if front is None else front
    reverse = image_bytes("JPEG") if reverse is None else reverse

    def photo(path: str, mime: str, payload: bytes, width: int = 2, height: int = 3) -> dict[str, object]:
        return {
            "path": path,
            "original_name": "private-source-name.heic",
            "mime_type": mime,
            "byte_length": len(payload),
            "width": width,
            "height": height,
            "captured_at": "2026-07-18T12:00:00Z",
        }

    return {
        "schema": "coin-analyzer.capture-package",
        "package_version": "1.0",
        "created_by": "Coin Analyzer Mobile Companion",
        "created_with": "0.2.0",
        "exported_at": "2026-07-18T12:00:00Z",
        "session": {
            "id": "session-1",
            "name": "Toronto Coin Expo",
            "description": "",
            "session_date": "2026-07-18",
            "created_at": "2026-07-18T12:00:00Z",
            "updated_at": "2026-07-18T12:00:00Z",
        },
        "coins": [
            {
                "id": "coin-1",
                "position": 0,
                "country": "Canada",
                "denomination": "Dollar",
                "year": "1967",
                "mint": "",
                "purchase_price": "12.50",
                "purchase_currency": "cad",
                "seller": "Dealer",
                "purchase_date": "2026-07-18",
                "notes": "Fixture",
                "quantity": 1,
                "composition": "silver",
                "is_bullion": False,
                "asw_troy_ounces": "0.6",
                "photos": {
                    "front": photo("images/front.png", "image/png", front),
                    "reverse": photo("images/reverse.jpg", "image/jpeg", reverse),
                },
                "created_at": "2026-07-18T12:00:00Z",
                "updated_at": "2026-07-18T12:00:00Z",
            }
        ],
    }


def package_bytes(
    *,
    manifest: dict[str, object] | bytes | None = None,
    front: bytes | None = None,
    reverse: bytes | None = None,
    extras: dict[str, bytes] | None = None,
    directories: bool = True,
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    front = image_bytes() if front is None else front
    reverse = image_bytes("JPEG") if reverse is None else reverse
    if manifest is None:
        manifest = manifest_dict(front, reverse)
    manifest_payload = (
        manifest
        if isinstance(manifest, bytes)
        else json.dumps(manifest, separators=(",", ":")).encode("utf-8")
    )
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        archive.writestr("capture_package.json", manifest_payload)
        if directories:
            archive.writestr("images/", b"")
        archive.writestr("images/front.png", front)
        archive.writestr("images/reverse.jpg", reverse)
        for name, payload in (extras or {}).items():
            archive.writestr(name, payload)
    return output.getvalue()
