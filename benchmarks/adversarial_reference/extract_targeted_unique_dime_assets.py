#!/usr/bin/env python3
"""Extract direct image candidates for the four unresolved Canadian dime slots.

Consumes targeted_unique_dime_candidate_plan.json and fetches each page, extracting image-like
URLs while filtering obvious UI/provider artifacts and already-known duplicate hashes. This is a
pre-retrieval source acquisition step: it does not mutate source_inventory_v1.json and does not
run retrieval scoring.
"""
from __future__ import annotations

import hashlib
import html.parser
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "targeted_unique_dime_candidate_plan.json"
OUTPUT = ROOT / "targeted_unique_dime_asset_candidates.json"
USER_AGENT = "coin-analyzer-adversarial-benchmark/1.0"
TIMEOUT = 30
MAX_BYTES = 20 * 1024 * 1024

KNOWN_DUPLICATE_SHA256 = {
    "20b3f7377b7f86b841fa3afa02e26393da286a8c2aefa32dda364b5d8f7ac90a",
}

BAD_URL_TOKENS = (
    "sprite", "logo", "icon", "button", "favicon", "search.jpg", "search.png",
    "/catalogue/catalogues/", "/catalogue/images/miniatures/", "/medias/btn_",
)


class ImgParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs):
        attrs = dict(attrs)
        if tag.lower() == "img":
            for key in ("src", "data-src", "data-original", "data-lazy-src"):
                value = attrs.get(key)
                if isinstance(value, str) and value:
                    self.urls.append(value)
            srcset = attrs.get("srcset") or attrs.get("data-srcset")
            if isinstance(srcset, str):
                for part in srcset.split(","):
                    url = part.strip().split(" ", 1)[0]
                    if url:
                        self.urls.append(url)
        elif tag.lower() == "meta":
            prop = str(attrs.get("property") or attrs.get("name") or "").lower()
            if prop in {"og:image", "twitter:image", "twitter:image:src"}:
                value = attrs.get("content")
                if isinstance(value, str) and value:
                    self.urls.append(value)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _page_url(row: dict) -> str:
    for key in ("source_page_url", "page_url", "url"):
        value = row.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    for key in ("candidate", "page", "source"):
        nested = row.get(key)
        if isinstance(nested, dict):
            value = _page_url(nested)
            if value:
                return value
    return ""


def _fetch_text(url: str) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = resp.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("page too large")
        return data.decode("utf-8", errors="replace"), str(resp.geturl() or url)


def _fetch_image_hash(url: str) -> tuple[str, int, str] | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            ctype = str(resp.headers.get("Content-Type") or "")
            if ctype and not ctype.lower().startswith("image/"):
                return None
            data = resp.read(MAX_BYTES + 1)
            if not data or len(data) > MAX_BYTES:
                return None
            return hashlib.sha256(data).hexdigest(), len(data), str(resp.geturl() or url)
    except Exception:
        return None


def _candidate_urls(page_url: str, html_text: str) -> list[str]:
    parser = ImgParser()
    parser.feed(html_text)
    seen: set[str] = set()
    out: list[str] = []
    for raw in parser.urls:
        url = urllib.parse.urljoin(page_url, raw)
        low = url.lower()
        if not url.startswith(("http://", "https://")):
            continue
        if any(tok in low for tok in BAD_URL_TOKENS):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def main() -> int:
    payload = _load(INPUT)
    rows = payload.get("targets") or payload.get("slots") or payload.get("items") or []
    if not isinstance(rows, list):
        rows = []

    results = []
    pages_fetched = 0
    page_errors = 0
    total_candidates = 0
    rejected_known_dup = 0

    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        case_id = str(row.get("case_id") or row.get("id") or "")
        side = str(row.get("side") or "")
        page_url = _page_url(row)
        print(f"[{i}/{len(rows)}] {case_id}.{side} | page={page_url or 'MISSING'}")
        entry = {"case_id": case_id, "side": side, "source_page_url": page_url, "candidates": []}
        if not page_url:
            entry["status"] = "missing-page-url"
            results.append(entry)
            continue
        try:
            text, final_page = _fetch_text(page_url)
            pages_fetched += 1
            entry["final_page_url"] = final_page
            urls = _candidate_urls(final_page, text)
            candidates = []
            for rank, url in enumerate(urls, 1):
                hashed = _fetch_image_hash(url)
                if not hashed:
                    continue
                sha, size, final_url = hashed
                if sha in KNOWN_DUPLICATE_SHA256:
                    rejected_known_dup += 1
                    continue
                candidates.append({
                    "rank": rank,
                    "asset_url": url,
                    "final_url": final_url,
                    "sha256": sha,
                    "bytes": size,
                })
            entry["candidates"] = candidates
            entry["status"] = "candidates-found" if candidates else "no-unique-candidates"
            total_candidates += len(candidates)
        except Exception as exc:
            page_errors += 1
            entry["status"] = "fetch-error"
            entry["error"] = str(exc)
        results.append(entry)

    output = {
        "schema": "coin-analyzer-targeted-unique-dime-asset-candidates-v1",
        "inventory_modified": False,
        "retrieval_scoring_run": False,
        "results": results,
        "summary": {
            "targets": len(results),
            "pages_fetched": pages_fetched,
            "page_errors": page_errors,
            "slots_with_candidates": sum(1 for r in results if r.get("candidates")),
            "slots_without_candidates": sum(1 for r in results if not r.get("candidates")),
            "unique_candidates_found": total_candidates,
            "known_duplicate_assets_rejected": rejected_known_dup,
        },
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    s = output["summary"]
    print(f"Targets: {s['targets']}")
    print(f"Pages fetched: {s['pages_fetched']}")
    print(f"Page errors: {s['page_errors']}")
    print(f"Slots with candidates: {s['slots_with_candidates']}")
    print(f"Slots without candidates: {s['slots_without_candidates']}")
    print(f"Unique candidates found: {s['unique_candidates_found']}")
    print(f"Known duplicate assets rejected: {s['known_duplicate_assets_rejected']}")
    print(f"Wrote targeted asset candidates: {OUTPUT}")
    print("Frozen case set unchanged; source_inventory_v1.json unchanged; no retrieval scoring run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
