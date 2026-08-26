"""Build an independent-reference benchmark for Benchmark v2.

The benchmark uses photographs independent from the frozen v2 query sources.
Downloads are resumable, and blocked sources do not prevent a useful partial run:
complete cached cases are emitted when at least MIN_COMPLETE_CASES are available.
Generated manifests are invalidated before each build so a failed expansion cannot
silently leave an older benchmark runnable under a misleading artifact name.
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
MIN_COMPLETE_CASES = 8

SOURCES = {
    "canada-5-cents-1964": {"obverse": ("Canada $0.05 1964.jpg",), "reverse": ("Canada $0.05 1964.jpg",)},
    "canada-10-cents-1955": {"obverse": ("Canada $0.1 1955.jpg",), "reverse": ("Canada $0.1 1955.jpg",)},
    "india-10-paise-1965": {"obverse": ("10-paise-1965-obs.png",), "reverse": ("10-paise-1965-rev.png",)},
    "india-1-rupee-1918": {"obverse": ("Indian silver rupee 1918.JPG",), "reverse": ("Indian silver rupee of 1918.JPG",)},
    "switzerland-2-francs-1980": {"obverse": ("2 Swiss Francs (1980).jpg",), "reverse": ("2 Swiss Francs (1980).jpg",)},
    "us-spanish-trail-half-dollar-1935": {"obverse": ("Old Spanish Trail half dollar obverse.jpg",), "reverse": ("Old Spanish Trail half dollar reverse.jpg",)},
    "us-elgin-half-dollar-1936": {"obverse": ("Elgin (Illinois) Centennial half dollar obverse.jpg",), "reverse": ("Elgin (Illinois) Centennial half dollar reverse.jpg",)},
    "us-pilgrim-half-dollar-1920": {
        "obverse": ("Monnaie - Etats-Unis, 1-2 dollar, 1920 - btv1b11336935m (1 of 2).jpg", "Monnaie - Etats-Unis, 1-2 dollar, 1920 - btv1b11336935m (2 of 2).jpg"),
        "reverse": ("Monnaie - Etats-Unis, 1-2 dollar, 1920 - btv1b11336935m (1 of 2).jpg", "Monnaie - Etats-Unis, 1-2 dollar, 1920 - btv1b11336935m (2 of 2).jpg"),
    },
    "australia-sixpence-1910": {"obverse": ("1910-Australian-Sixpence-Obverse.jpg",), "reverse": ("1910-Australian-Sixpence-Reverse.jpg",)},
    "indonesia-100-rupiah-1995": {"obverse": ("IDR 100 Coin (obverse and reverse).jpg",), "reverse": ("IDR 100 Coin (obverse and reverse).jpg",)},
}

FALLBACK_URLS = {
    "Old Spanish Trail half dollar obverse.jpg": "https://www.usmint.gov/learn/coins-and-medals/commemorative-coins/old-spanish-trail-half/_jcr_content/root/container_1426747781/imagegallerypdp/item_1753815828436.coreimg.jpeg/1753816109894/1935-old-spanish-trail-quadricentennial-commemorative-silver-half-dollar-coin-obverse.jpeg",
    "Old Spanish Trail half dollar reverse.jpg": "https://www.usmint.gov/learn/coins-and-medals/commemorative-coins/old-spanish-trail-half/_jcr_content/root/container_1426747781/imagegallerypdp/item_1753816076650.coreimg.jpeg/1753816140449/1935-old-spanish-trail-quadricentennial-commemorative-silver-half-dollar-coin-reverse.jpeg",
}
FALLBACK_SOURCE_PAGE = "https://www.usmint.gov/learn/coins-and-medals/commemorative-coins/old-spanish-trail-half"


def _clean_html(value: str | None) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def _api_metadata(titles: list[str]) -> dict[str, dict[str, object]]:
    query = "|".join("File:" + title for title in titles)
    url = "https://commons.wikimedia.org/w/api.php?action=query&format=json&formatversion=2&prop=imageinfo&iiprop=url%7Cextmetadata" + f"&iiurlwidth={THUMB_WIDTH}&titles=" + quote(query)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)
    return {page["title"][5:]: page["imageinfo"][0] for page in payload["query"]["pages"] if "missing" not in page}


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.read()


def _safe_suffix(title: str) -> str:
    suffix = Path(title).suffix.casefold()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".img"


def _all_titles() -> list[str]:
    return sorted({title for sides in SOURCES.values() for titles in sides.values() for title in titles})


def _invalidate_generated_manifests() -> None:
    removed = []
    for path in (REFERENCE_MANIFEST, PILOT_BENCHMARK_MANIFEST):
        if path.exists():
            path.unlink()
            removed.append(str(path))
    if removed:
        print("Invalidated stale generated manifests:", flush=True)
        for path in removed:
            print(f"  {path}", flush=True)


def _pilot_benchmark(case_ids: set[str]) -> dict[str, object]:
    source = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    cases = [case for case in source.get("cases", []) if case.get("id") in case_ids]
    found = {case.get("id") for case in cases}
    missing = sorted(case_ids - found)
    if missing:
        raise RuntimeError("Benchmark v2 is missing reference cases: " + ", ".join(missing))
    payload = dict(source)
    payload["version"] = str(source.get("version") or "v2.0") + "+reference-10"
    payload["reference_build"] = {
        "target_cases": len(SOURCES),
        "minimum_complete_cases": MIN_COMPLETE_CASES,
        "complete_cases": len(cases),
        "complete_case_ids": sorted(case_ids),
    }
    payload["cases"] = cases
    payload["notes"] = f"Independent-reference retrieval benchmark targeting {len(SOURCES)} varied identities; {len(cases)} complete reference cases available in this build."
    return payload


def main() -> int:
    # Do this before any network work. A failed build must never leave an older
    # manifest that a later benchmark command can mistake for the current run.
    _invalidate_generated_manifests()

    titles = _all_titles()
    metadata = _api_metadata(titles)
    missing_metadata = sorted(set(titles) - set(metadata))
    if missing_metadata:
        raise RuntimeError("Missing Commons reference files: " + ", ".join(missing_metadata))

    REFERENCE_ROOT.mkdir(parents=True, exist_ok=True)
    downloaded: dict[str, Path] = {}
    provenance: dict[str, dict[str, object]] = {}
    unavailable: set[str] = set()

    for index, title in enumerate(titles, start=1):
        info = metadata[title]
        ext = info.get("extmetadata") if isinstance(info.get("extmetadata"), dict) else {}
        original_url = str(info["url"])
        primary_url = str(info.get("thumburl") or original_url)
        retrieved_url = primary_url
        retrieval_source = "Wikimedia Commons"
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_")
        path = REFERENCE_ROOT / "refs_v2" / safe_name
        if path.suffix.casefold() not in {".jpg", ".jpeg", ".png", ".webp"}:
            path = path.with_suffix(_safe_suffix(title))
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.is_file() and path.stat().st_size > 0:
            print(f"Cached {index}/{len(titles)}: {title}", flush=True)
        else:
            print(f"Downloading {index}/{len(titles)}: {title}", flush=True)
            try:
                payload = _download(primary_url)
            except HTTPError as error:
                fallback_url = FALLBACK_URLS.get(title)
                if error.code == 429 and fallback_url:
                    print(f"Commons throttled {title}; trying fixed U.S. Mint fallback.", flush=True)
                    try:
                        payload = _download(fallback_url)
                        retrieved_url = fallback_url
                        retrieval_source = "United States Mint"
                    except HTTPError as fallback_error:
                        print(f"Fallback unavailable for {title} (HTTP {fallback_error.code}); marking reference unavailable.", flush=True)
                        unavailable.add(title)
                        continue
                elif error.code == 429:
                    print(f"Commons throttled {title}; marking reference unavailable for this run.", flush=True)
                    unavailable.add(title)
                    continue
                else:
                    raise
            path.write_bytes(payload)
            time.sleep(2.0)

        downloaded[title] = path
        provenance[title] = {
            "commons_title": title,
            "commons_source_page": str(info.get("descriptionurl") or ""),
            "commons_file_url": original_url,
            "retrieved_file_url": retrieved_url,
            "retrieval_source": retrieval_source,
            "fallback_source_page": FALLBACK_SOURCE_PAGE if retrieval_source == "United States Mint" else None,
            "retrieved_width": info.get("thumbwidth") if retrieval_source == "Wikimedia Commons" else None,
            "author": _clean_html((ext.get("Artist") or {}).get("value") if isinstance(ext.get("Artist"), dict) else ""),
            "license": str((ext.get("LicenseShortName") or {}).get("value") if isinstance(ext.get("LicenseShortName"), dict) else ""),
            "credit": _clean_html((ext.get("Credit") or {}).get("value") if isinstance(ext.get("Credit"), dict) else ""),
            "retrieved_at": RETRIEVED_AT,
        }

    candidates = []
    skipped: list[str] = []
    for case_id, sides in SOURCES.items():
        required_titles = {title for role_titles in sides.values() for title in role_titles}
        if not required_titles.issubset(downloaded):
            skipped.append(case_id)
            continue
        candidate = {"id": case_id, "provenance": {}}
        for role in ("obverse", "reverse"):
            role_titles = sides[role]
            candidate[role] = [downloaded[title].relative_to(REFERENCE_ROOT).as_posix() for title in role_titles]
            candidate["provenance"][role] = [provenance[title] for title in role_titles]
        candidates.append(candidate)

    if len(candidates) < MIN_COMPLETE_CASES:
        print(f"Only {len(candidates)} complete reference cases; need at least {MIN_COMPLETE_CASES}. Generated manifests remain absent.", flush=True)
        if skipped:
            print("Incomplete cases: " + ", ".join(skipped), flush=True)
        return 75

    complete_ids = {candidate["id"] for candidate in candidates}
    reference_manifest = {
        "schema": "coin-analyzer-reference-image-catalogue",
        "version": "v2-independent-reference-10",
        "description": f"Independent-photo reference benchmark targeting {len(SOURCES)} varied Benchmark v2 identities; {len(candidates)} complete cases available.",
        "target_cases": len(SOURCES),
        "minimum_complete_cases": MIN_COMPLETE_CASES,
        "complete_cases": len(candidates),
        "complete_case_ids": sorted(complete_ids),
        "partial": len(candidates) < len(SOURCES),
        "skipped_cases": skipped,
        "unavailable_titles": sorted(unavailable),
        "candidates": candidates,
    }
    REFERENCE_MANIFEST.write_text(json.dumps(reference_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    PILOT_BENCHMARK_MANIFEST.write_text(json.dumps(_pilot_benchmark(complete_ids), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote reference catalogue: {REFERENCE_MANIFEST}")
    print(f"Wrote benchmark manifest: {PILOT_BENCHMARK_MANIFEST}")
    print(f"Complete cases: {len(candidates)}/{len(SOURCES)}")
    if skipped:
        print("Skipped incomplete cases: " + ", ".join(skipped))
    print(f"Available independent reference files: {len(downloaded)}/{len(titles)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
