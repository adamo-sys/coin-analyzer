"""Build a five-case independent-reference pilot for Benchmark v2.

The pilot deliberately uses photographs that are independent from the frozen v2
query sources. It downloads the exact named Wikimedia Commons files, preserves
source-page/licence/author metadata in the generated reference manifest, and
writes a five-case benchmark manifest beside the frozen v2 manifest so existing
relative query-image paths remain valid.

Generated files are local benchmark artifacts and can be regenerated from this
source inventory; the downloaded reference images are not required to live in
Git history.
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

# These are intentionally different photographs from the frozen Benchmark v2
# query sources. The five cases were chosen because exact-identity independent
# reusable photographs are available with clear Commons provenance.
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
    # The Bibliotheque nationale de France pair is independently photographed.
    # Commons' numbered filenames do not encode side role, so both independent
    # images are offered to each side scorer; the scorer chooses the stronger
    # side match. This avoids inventing an obverse/reverse assignment.
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
        "&prop=imageinfo&iiprop=url%7Cextmetadata&titles=" + quote(query)
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
    for attempt in range(5):
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()
        except HTTPError as error:
            if error.code != 429 or attempt == 4:
                raise
            time.sleep(4.0 * (attempt + 1))
    raise RuntimeError("unreachable download retry state")


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

    for index, title in enumerate(titles, start=1):
        info = metadata[title]
        ext = info.get("extmetadata") if isinstance(info.get("extmetadata"), dict) else {}
        url = str(info["url"])
        path = REFERENCE_ROOT / "refs" / f"ref-{index:02d}{_safe_suffix(title)}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            path.write_bytes(_download(url))
            time.sleep(0.5)
        downloaded[title] = path
        provenance[title] = {
            "commons_title": title,
            "source_page": str(info.get("descriptionurl") or ""),
            "source_file_url": url,
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
        "version": "v2-independent-reference-pilot-1",
        "description": "Five exact-identity candidates using photographs independent from Benchmark v2 query sources.",
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
