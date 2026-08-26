"""Build a five-case independent-reference pilot for Benchmark v2.

The pilot deliberately uses photographs that are independent from the frozen v2
query sources. It downloads exact reference images, preserves provenance, and
writes a five-case benchmark manifest beside the frozen v2 manifest.

Downloads are resumable. Commons remains the primary source, but the two Old
Spanish Trail references have fixed U.S. Mint fallbacks so a Commons 429 cannot
block completion of the pilot.
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

# Independent institutional images. These are used only when Commons throttles
# the corresponding Old Spanish Trail download. Keeping them explicit makes the
# fallback deterministic and avoids retry loops or guessed CDN paths.
FALLBACK_URLS = {
    "Old Spanish Trail half dollar obverse.jpg": (
        "https://www.usmint.gov/learn/coins-and-medals/commemorative-coins/old-spanish-trail-half/"
        "_jcr_content/root/container_1426747781/imagegallerypdp/item_1753815828436.coreimg.jpeg/"
        "1753816109894/1935-old-spanish-trail-quadricentennial-commemorative-silver-half-dollar-coin-obverse.jpeg"
    ),
    "Old Spanish Trail half dollar reverse.jpg": (
        "https://www.usmint.gov/learn/coins-and-medals/commemorative-coins/old-spanish-trail-half/"
        "_jcr_content/root/container_1426747781/imagegallerypdp/item_1753816076650.coreimg.jpeg/"
        "1753816140449/1935-old-spanish-trail-quadricentennial-commemorative-silver-half-dollar-coin-reverse.jpeg"
    ),
}
FALLBACK_SOURCE_PAGE = "https://www.usmint.gov/learn/coins-and-medals/commemorative-coins/old-spanish-trail-half"


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
    result: dict[str, dict[str, object]] = {}
    for page in payload["query"]["pages"]:
        if "missing" not in page:
            result[page["title"][5:]] = page["imageinfo"][0]
    return result


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.read()


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
        primary_url = str(info.get("thumburl") or original_url)
        retrieved_url = primary_url
        retrieval_source = "Wikimedia Commons"
        path = REFERENCE_ROOT / "refs" / f"ref-{index:02d}{_safe_suffix(title)}"
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.is_file() and path.stat().st_size > 0:
            cached_count += 1
            print(f"Cached {index}/{len(titles)}: {title}", flush=True)
        else:
            print(f"Downloading {index}/{len(titles)}: {title}", flush=True)
            try:
                payload = _download(primary_url)
            except HTTPError as error:
                fallback_url = FALLBACK_URLS.get(title)
                if error.code == 429 and fallback_url:
                    print(f"Commons throttled {title}; using fixed U.S. Mint fallback.", flush=True)
                    payload = _download(fallback_url)
                    retrieved_url = fallback_url
                    retrieval_source = "United States Mint"
                elif error.code == 429:
                    retry_after = error.headers.get("Retry-After")
                    print(
                        "Wikimedia Commons throttled a reference-image download (HTTP 429). "
                        f"Retry-After={retry_after or 'unknown'}s. Completed files are cached; rerun later to resume.",
                        flush=True,
                    )
                    print(f"Resume status: {cached_count}/{len(titles)} files cached; none removed.", flush=True)
                    return 75
                else:
                    raise
            path.write_bytes(payload)
            cached_count += 1
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
    for case_id, sides in SOURCES.items():
        candidate = {"id": case_id, "provenance": {}}
        for role in ("obverse", "reverse"):
            role_titles = sides[role]
            candidate[role] = [downloaded[title].relative_to(REFERENCE_ROOT).as_posix() for title in role_titles]
            candidate["provenance"][role] = [provenance[title] for title in role_titles]
        candidates.append(candidate)

    reference_manifest = {
        "schema": "coin-analyzer-reference-image-catalogue",
        "version": "v2-independent-reference-pilot-4",
        "description": "Five exact-identity candidates using independent photographs; Old Spanish Trail references have deterministic U.S. Mint fallbacks for Commons throttling.",
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
