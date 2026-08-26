"""Build a five-case independent-reference pilot for Benchmark v2.

The pilot deliberately uses photographs that are independent from the frozen v2
query sources. It downloads the exact named Wikimedia Commons files, preserves
source-page/licence/author metadata in the generated reference manifest, and
writes a five-case benchmark manifest beside the frozen v2 manifest so existing
relative query-image paths remain valid.

Downloads are resumable: completed reference files remain cached. If Commons
throttles a missing image, the builder exits promptly instead of sleeping for a
long Retry-After interval; rerunning later continues with only missing files.
"""
from __future__ import annotations

from datetime import date
import html
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
REFERENCE_ROOT = ROOT / "reference_pilot"
REFERENCE_MANIFEST = REFERENCE_ROOT / "manifest.json"
PILOT_BENCHMARK_MANIFEST = ROOT / "reference_pilot_benchmark.json"
USER_AGENT = "CoinAnalyzerReferencePilot/1.0 (independent reference retrieval benchmark)"
RETRIEVED_AT = date.today().isoformat()
THUMB_WIDTH = 960
MAX_RETRY_AFTER_SECONDS = 30.0

SOURCES = {
    "india-10-paise-1965": {
        "obverse": ("10-paise-1965-obs.png",),
        "reverse": ("10-paise-1965-rev.png",),
    },
    "india-1-rupee-1918": {
        "obverse": ("Indian silver rupee 1918.JPG",),
        "reverse": ("Indian silver rupee of 1918.JPG",),
    },
    "us-spanish-trail-half-dollar-1935": {
        "obverse": ("Old Spanish Trail half dollar obverse.jpg",),
        "reverse": ("Old Spanish Trail half dollar reverse.jpg",),
    },
    "us-elgin-half-dollar-1936": {
        "obverse": ("Elgin (Illinois) Centennial half dollar obverse.jpg",),
        "reverse": ("Elgin (Illinois) Centennial half dollar reverse.jpg",),
    },
    "us-pilgrim-half-dollar-1920": {
        "obverse": (
            "Monnaie - Etats-Unis, 1-2 dollar, 1920 - btv1b11336935m (1 of 2).jpg",
            "Monnaie - Etats-Unis, 1-2 dollar, 1920 - btv1b11336935m (2 of 2).jpg",
        ),
        "reverse": (
            "Monnaie - Etats-Unis, 1-2 dollar, 1920 - btv1b11336935m (1 of 2).jpg",
            "Monnaie - Etats-Unis, 1-2 dollar, 1920 - btv1b11336935m (2 of 2).jpg",
        ),
    },
}


def _clean_html(value: str | None) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def _api_metadata(titles: list[str]) -> dict[str, dict[str, object]]:
    query = "|".join("File:" + title for title in titles)
    url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json&formatversion=2"
        "&prop=imageinfo&iiprop=url%7Cextmetadata"
        f"&iiurlwidth={THUMB_WIDTH}&titles=" + quote(query)
    )
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)
    pages = payload["query"]["pages"]
    result: dict[str, dict[str, object]] = {}
    for page in pages:
        if "missing" in page:
            continue
        info = page["imageinfo"][0]
        result[page["title"][5:]] = info
    return result


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=60) as response:
            return response.read()
    except HTTPError as error:
        if error.code != 429:
            raise
        retry_after = error.headers.get("Retry-After")
        try:
            delay = float(retry_after) if retry_after else None
        except (TypeError, ValueError):
            delay = None
        detail = f" Retry-After={delay:.0f}s." if delay is not None else ""
        raise RuntimeError(
            "Wikimedia Commons throttled a reference-image download (HTTP 429)."
            + detail
            + " Completed files are cached; rerun this command later to resume only the missing downloads."
        ) from error


def _safe_suffix(title: str) -> str:
    suffix = Path(title).suffix.casefold()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".img"


def _all_titles() -> list[str]:
    return sorted({title for sides in SOURCES.values() for titles in sides.values() for title in titles})


def _pilot_benchmark() -> dict[str, object]:
    source = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    wanted = set(SOURCES)
    cases = [case for case in source.get("cases", []) if case.get("id") in wanted]
    found = {case.get("id") for case in cases}
    missing = sorted(wanted - found)
    if missing:
        raise RuntimeError("Benchmark v2 is missing pilot cases: " + ", ".join(missing))
    payload = dict(source)
    payload["version"] = str(source.get("version") or "v2.0") + "+reference-pilot"
    payload["cases"] = cases
    payload["notes"] = "Five-case independent-reference retrieval pilot; query images are unchanged Benchmark v2 derivatives."
    return payload


def main() -> int:
    titles = _all_titles()
    metadata = _api_metadata(titles)
    missing = sorted(set(titles) - set(metadata))
    if missing:
        raise RuntimeError("Missing Commons reference files: " + ", ".join(missing))

    REFERENCE_ROOT.mkdir(parents=True, exist_ok=True)
    downloaded: dict[str, Path] = {}
    provenance: dict[str, dict[str, object]] = {}
    cached_count = 0

    for index, title in enumerate(titles, start=1):
        info = metadata[title]
        ext = info.get("extmetadata") if isinstance(info.get("extmetadata"), dict) else {}
        original_url = str(info["url"])
        download_url = str(info.get("thumburl") or original_url)
        path = REFERENCE_ROOT / "refs" / f"ref-{index:02d}{_safe_suffix(title)}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file() and path.stat().st_size > 0:
            cached_count += 1
            print(f"Cached {index}/{len(titles)}: {title}", flush=True)
        else:
            print(f"Downloading {index}/{len(titles)}: {title}", flush=True)
            try:
                payload = _download(download_url)
            except RuntimeError as error:
                print(str(error), flush=True)
                print(
                    f"Resume status: {cached_count}/{len(titles)} reference files already cached. "
                    "No cached files were removed.",
                    flush=True,
                )
                return 75
            path.write_bytes(payload)
            cached_count += 1
            time.sleep(2.0)
        downloaded[title] = path
        provenance[title] = {
            "commons_title": title,
            "source_page": str(info.get("descriptionurl") or ""),
            "source_file_url": original_url,
            "retrieved_file_url": download_url,
            "retrieved_width": info.get("thumbwidth"),
            "author": _clean_html((ext.get("Artist") or {}).get("value") if isinstance(ext.get("Artist"), dict) else ""),
            "license": str((ext.get("LicenseShortName") or {}).get("value") if isinstance(ext.get("LicenseShortName"), dict) else ""),
            "credit": _clean_html((ext.get("Credit") or {}).get("value") if isinstance(ext.get("Credit"), dict) else ""),
            "retrieved_at": RETRIEVED_AT,
        }

    candidates = []
    for case_id, sides in SOURCES.items():
        candidate = {"id": case_id, "provenance": {}}
        for role in ("obverse", "reverse"):
            role_titles = sides[role]
            candidate[role] = [downloaded[title].relative_to(REFERENCE_ROOT).as_posix() for title in role_titles]
            candidate["provenance"][role] = [provenance[title] for title in role_titles]
        candidates.append(candidate)

    reference_manifest = {
        "schema": "coin-analyzer-reference-image-catalogue",
        "version": "v2-independent-reference-pilot-3",
        "description": "Five exact-identity candidates using independent photographs; downloads are cached and resumable across Commons throttling.",
        "candidates": candidates,
    }
    REFERENCE_MANIFEST.write_text(json.dumps(reference_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    PILOT_BENCHMARK_MANIFEST.write_text(json.dumps(_pilot_benchmark(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote reference catalogue: {REFERENCE_MANIFEST}")
    print(f"Wrote pilot benchmark: {PILOT_BENCHMARK_MANIFEST}")
    print(f"Cases: {len(candidates)}; unique independent reference files: {len(titles)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
