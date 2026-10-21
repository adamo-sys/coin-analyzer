"""Build an allowlisted credential-free shell into a NEW output directory.

This builds files only; it does not serve them, provision TLS or grant access.
"""

import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "offline_pwa"
ASSETS = {
    "index.html": "text/html",
    "app.js": "text/javascript",
    "storage.js": "text/javascript",
    "media.js": "text/javascript",
    "style.css": "text/css",
    "manifest.webmanifest": "application/manifest+json",
    "icon-192.png": "image/png",
    "icon-512.png": "image/png",
}


def icon(size):
    """Procedural opaque app icon, containing no photographic source material."""

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data))
        )

    pixels = bytearray()
    for y in range(size):
        pixels.append(0)
        for x in range(size):
            radius = (x - size / 2) ** 2 + (y - size / 2) ** 2
            pixels.extend(
                (225, 184, 103) if radius < (size * 0.32) ** 2 else (23, 43, 48)
            )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def build(output):
    output.mkdir(parents=True, exist_ok=False)
    assets = []
    for name, mime in ASSETS.items():
        data = (
            icon(int(name.split("-")[1].split(".")[0]))
            if name.startswith("icon-")
            else (SOURCE / name).read_bytes()
        )
        (output / name).write_bytes(data)
        assets.append(
            {"path": name, "type": mime, "sha256": hashlib.sha256(data).hexdigest()}
        )
    worker = (SOURCE / "worker.js").read_text(encoding="utf-8")
    version = hashlib.sha256(
        json.dumps(assets, sort_keys=True).encode() + worker.encode()
    ).hexdigest()
    manifest = {"version": version, "assets": assets}
    (output / "shell.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    if worker.count("__SHELL_MANIFEST__") != 1:
        raise ValueError("Worker must contain exactly one manifest placeholder")
    (output / "sw.js").write_text(
        worker.replace("__SHELL_MANIFEST__", json.dumps(manifest)), encoding="utf-8"
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python tools/build_offline_pwa.py NEW_OUTPUT_DIRECTORY"
        )
    build(Path(sys.argv[1]))
