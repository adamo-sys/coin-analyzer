"""Reproduce Benchmark v2 from independently selected Commons sources.

The source inventory was fixed before any visual provider was run.  This
script downloads the exact named Commons files, records current source hashes
and metadata, and creates paired 960px-or-smaller JPEG evaluation images.
"""

from __future__ import annotations

from datetime import date
import hashlib
import html
from io import BytesIO
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from PIL import Image


ROOT = Path(__file__).resolve().parent
RETRIEVED_AT = date(2026, 8, 8).isoformat()
USER_AGENT = "CoinAnalyzerBenchmarkBuilder/1.0 (reproducible evaluation dataset)"


def case(case_id, country, denomination, year, era, difficulty, *, composite=None, reverse_first=False, obverse=None, reverse=None, type_design=None, license="PUBLIC-DOMAIN", author=None, reused=False, notes=""):
    return dict(id=case_id, underlying_identity=case_id, country=country, denomination=denomination, year=year, era=era, difficulty=difficulty, composite=composite, reverse_first=reverse_first, obverse=obverse, reverse=reverse, type_design=type_design, license=license, author=author, reused=reused, notes=notes)


CASES = (
    case("canada-5-cents-1964", "Canada", "5 cents", "1964", "modern", ["clean", "studio", "silver-color"], composite="Canada $0.05 1964.jpg", reverse_first=True, type_design="Elizabeth II beaver", license="CC0-1.0", author="Awmcphee"),
    case("canada-10-cents-1955", "Canada", "10 cents", "1955", "modern", ["clean", "studio", "silver-color"], composite="Canada $0.1 1955.jpg", reverse_first=True, type_design="Elizabeth II Bluenose", license="CC-BY-SA-4.0", author="Coin design: Emanuel Hahn; photograph: Mister rf"),
    case("canada-25-cents-1967", "Canada", "25 cents", "1967", "modern", ["clean", "studio", "silver-color", "commemorative"], composite="Canada $0.25 1967.jpg", reverse_first=True, type_design="Centennial bobcat", author="Awmcphee"),
    case("india-10-paise-1965", "India", "10 paise", "1965", "modern", ["clean", "studio", "scalloped", "worn"], composite="10 Indian paise (1965).jpg", type_design="Republic contemporary scalloped", license="CC-BY-SA-4.0", author="Reserve Bank of India / AKS.9955"),
    case("india-2-rupees-2012", "India", "2 rupees", "2012", "modern", ["clean", "studio", "silver-color"], composite="2 Indian rupee (2012).jpg", type_design="Rupee symbol with lotus", license="CC-BY-SA-4.0", author="Reserve Bank of India / AKS.9955"),
    case("india-1-rupee-1918", "India", "1 rupee", "1918", "early-modern", ["clean", "studio", "silver-color", "worn"], composite="1 Indian rupee (1918).jpg", type_design="George V crowned bust", license="CC-BY-SA-4.0", author="AKS.9955", reused=True, notes="Same Commons source identity used in Benchmark v1; v2 derivatives are independently recorded."),
    case("bhutan-half-rupee-1955", "Bhutan", "1/2 rupee", "1955", "modern", ["clean", "studio", "silver-color", "worn"], composite="Half Rupee (1955).jpg", type_design="Jigme Dorji and auspicious symbols", license="CC-BY-SA-4.0", author="AKS.9955", notes="Country and design label corrected during source-page verification before freeze; selected source identity unchanged."),
    case("switzerland-2-francs-1980", "Switzerland", "2 francs", "1980", "modern", ["clean", "studio", "silver-color"], composite="2 Swiss Francs (1980).jpg", type_design="Standing Helvetia", author="AKS.9955"),
    case("liberia-1-cent-1847", "Liberia", "1 cent", "1847", "nineteenth-century", ["archive-scan", "copper-color", "worn"], obverse="Liberian one-cent coin, 1847, obverse.jpg", reverse="Liberian one-cent coin, 1847, reverse.jpg", type_design="Liberty seated", author="Nyttend"),
    case("liberia-2-cents-1862", "Liberia", "2 cents", "1862", "nineteenth-century", ["archive-scan", "copper-color", "worn"], obverse="Liberian two-cent coin, 1862, obverse.jpg", reverse="Liberian two-cent coin, 1862, reverse.jpg", type_design="Liberty seated", author="Nyttend"),
    case("liberia-1-cent-1896", "Liberia", "1 cent", "1896", "nineteenth-century", ["archive-scan", "copper-color", "worn"], obverse="Liberian one-cent coin, 1896, obverse.jpg", reverse="Liberian one-cent coin, 1896, reverse.jpg", author="Nyttend"),
    case("us-spanish-trail-half-dollar-1935", "United States", "1/2 dollar", "1935", "early-modern", ["archive-scan", "silver-color", "commemorative"], composite="Spanish trail memorial half dollar commemorative obverse reverse.jpg", reverse_first=True, type_design="Old Spanish Trail commemorative", author="Bobby131313"),
    case("us-columbia-half-dollar-1936", "United States", "1/2 dollar", "1936", "early-modern", ["archive-scan", "silver-color", "commemorative"], composite="Columbia sesquentennial half dollar commorative obverse reverse.jpg", type_design="Columbia Sesquicentennial commemorative", author="Bobby131313"),
    case("us-elgin-half-dollar-1936", "United States", "1/2 dollar", "1936", "early-modern", ["archive-scan", "silver-color", "commemorative"], composite="Elgin centennial half dollar commemorative obverse reverse.jpg", type_design="Elgin Centennial commemorative", author="Bobby131313"),
    case("us-pilgrim-half-dollar-1920", "United States", "1/2 dollar", "1920", "early-modern", ["archive-scan", "silver-color", "commemorative"], composite="Pilgrim Tercentenary half dollar commemorative obverse and reverse.jpg", type_design="Pilgrim Tercentenary commemorative", author="Coin: Cyrus Dallin; image: Bobby131313"),
    case("australia-sixpence-1910", "Australia", "6 pence", "1910", "early-modern", ["low-resolution", "silver-color", "worn"], obverse="1910-Australian-Sixpence-Obverse.jpg", reverse="1910-Australian-Sixpence-Reverse.jpg", type_design="Edward VII and Australian arms", author="Australian Coin Information"),
    case("belgian-congo-1-franc-1887", "Congo Free State", "1 franc", "1887", "nineteenth-century", ["clean", "studio", "silver-color"], composite="Obverse and Reverse of an 1887 Belgian Congo 1 Franc coin.png", type_design="Leopold II Congo Free State", license="CC-BY-SA-4.0", author="apuking"),
    case("indonesia-100-rupiah-1995", "Indonesia", "100 rupiah", "1995", "modern", ["clean", "studio", "gold-color"], composite="IDR 100 Coin (obverse and reverse).jpg", author="Bank Indonesia"),
    case("france-1-centime-1797", "France", "1 centime", "1797", "eighteenth-century", ["archive-scan", "copper-color", "worn"], obverse="0,01-franc-1797-obverse.png", reverse="0,01-franc-1797-reverse.png", author="French Republic"),
    case("philippines-10-pesos-2015", "Philippines", "10 pesos", "2015", "modern", ["handheld", "commemorative", "bimetallic", "realistic-background"], obverse="Commemorative 10 Philippine Peso Coin — Remembering the People Power Revolution (Obverse).jpg", reverse="Commemorative 10 Philippine Peso Coin — Remembering the People Power Revolution (Reverse).jpg", type_design="People Power Revolution commemorative", author="Bangko Sentral ng Pilipinas / Pandakekok9"),
)


# Commons repeatedly throttled these small originals and explicitly recommends
# its listed thumbnail derivatives. These exact derivative URLs are therefore
# fixed source files, not replacement identities.
SOURCE_URL_OVERRIDES = {
    "Pilgrim Tercentenary half dollar commemorative obverse and reverse.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/Pilgrim_Tercentenary_half_dollar_commemorative_obverse_and_reverse.jpg/330px-Pilgrim_Tercentenary_half_dollar_commemorative_obverse_and_reverse.jpg",
    "Spanish trail memorial half dollar commemorative obverse reverse.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Spanish_trail_memorial_half_dollar_commemorative_obverse_reverse.jpg/330px-Spanish_trail_memorial_half_dollar_commemorative_obverse_reverse.jpg",
}


def _api_metadata(titles):
    query = "|".join("File:" + title for title in titles)
    url = "https://commons.wikimedia.org/w/api.php?action=query&format=json&formatversion=2&prop=imageinfo&iiprop=url%7Cextmetadata&iiurlwidth=960&titles=" + quote(query)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        payload = json.load(response)
    pages = payload["query"]["pages"]
    return {page["title"][5:]: page["imageinfo"][0] for page in pages if "missing" not in page}


def _clean_html(value):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def _download(url):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(5):
        try:
            with urlopen(request, timeout=60) as response:
                payload = response.read()
            time.sleep(3.0)
            return payload
        except HTTPError as error:
            if error.code != 429 or attempt == 4:
                raise
            time.sleep(5.0 * (attempt + 1))
    raise RuntimeError("unreachable download retry state")


def _save(image, path):
    image = image.convert("RGB")
    image.thumbnail((960, 960), Image.Resampling.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=92, optimize=True)


def _rgb_with_white_matte(image):
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        return Image.alpha_composite(background, rgba).convert("RGB"), True
    return image.convert("RGB"), False


def main():
    titles = sorted({title for item in CASES for title in (item["composite"], item["obverse"], item["reverse"]) if title})
    metadata = _api_metadata(titles)
    missing = sorted(set(titles) - set(metadata))
    if missing:
        raise RuntimeError("Missing Commons files: " + ", ".join(missing))
    source_root = ROOT / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    source_payloads = {}
    for title in titles:
        info = metadata[title]
        suffix = Path(title).suffix.lower() or ".img"
        source_path = source_root / (hashlib.sha256(title.encode("utf-8")).hexdigest()[:16] + suffix)
        if source_path.is_file():
            payload = source_path.read_bytes()
        else:
            payload = _download(SOURCE_URL_OVERRIDES.get(title, info.get("thumburl", info["url"])))
            source_path.write_bytes(payload)
        source_payloads[title] = (payload, source_path)

    manifest_cases = []
    for item in CASES:
        output_root = ROOT / "images" / item["id"]
        source_by_role = {}
        if item["composite"]:
            title = item["composite"]
            payload, _ = source_payloads[title]
            with Image.open(BytesIO(payload)) as source:
                image, had_transparency = _rgb_with_white_matte(source)
            midpoint = image.width // 2
            left = image.crop((0, 0, midpoint, image.height))
            right = image.crop((midpoint, 0, image.width, image.height))
            role_images = ({"obverse": right, "reverse": left} if item["reverse_first"] else {"obverse": left, "reverse": right})
            source_by_role = {"obverse": title, "reverse": title}
            side_order = "right obverse/left reverse" if item["reverse_first"] else "left obverse/right reverse"
            transparency = "; transparency composited over white" if had_transparency else ""
            transform_by_role = {role: f"Composite split at horizontal midpoint ({side_order}){transparency}; resized only if needed to fit 960x960; JPEG quality 92" for role in ("obverse", "reverse")}
        else:
            role_images = {}
            transform_by_role = {}
            for role in ("obverse", "reverse"):
                title = item[role]
                payload, _ = source_payloads[title]
                with Image.open(BytesIO(payload)) as source:
                    role_images[role], had_transparency = _rgb_with_white_matte(source)
                source_by_role[role] = title
                transparency = "Transparency composited over white; " if had_transparency else ""
                transform_by_role[role] = f"{transparency}resized only if needed to fit 960x960; JPEG quality 92"
        image_entries = {}
        for role in ("obverse", "reverse"):
            output = output_root / f"{role}.jpg"
            _save(role_images[role], output)
            title = source_by_role[role]
            info = metadata[title]
            ext = info.get("extmetadata", {})
            payload, source_path = source_payloads[title]
            image_entries[role] = {
                "role": role,
                "path": output.relative_to(ROOT).as_posix(),
                "source_asset_path": source_path.relative_to(ROOT).as_posix(),
                "source_page": info["descriptionurl"],
                "source_file_url": SOURCE_URL_OVERRIDES.get(title, info.get("thumburl", info["url"])),
                "author": item["author"] or _clean_html(ext.get("Artist", {}).get("value", "")),
                "license": item["license"],
                "retrieved_at": RETRIEVED_AT,
                "source_sha256": hashlib.sha256(payload).hexdigest(),
                "transformation": transform_by_role[role],
            }
        expected = {"country": item["country"], "denomination": item["denomination"], "year": item["year"]}
        if item["type_design"]:
            expected["type_design"] = item["type_design"]
        manifest_cases.append({
            "id": item["id"], "underlying_identity": item["underlying_identity"],
            "obverse": image_entries["obverse"], "reverse": image_entries["reverse"],
            "expected": expected, "identity_certain": True, "era": item["era"],
            "difficulty": sorted(item["difficulty"]), "previously_used": item["reused"], "notes": item["notes"],
        })
    manifest = {
        "schema": "coin-analyzer-visual-benchmark", "version": "v2.0",
        "description": "Model-independent paired-image visual coin identification benchmark.",
        "selection_policy": "Selected and labelled before any candidate visual provider was run; no model outputs influenced inclusion, labels, or transforms.",
        "type_design_policy": "Optional concise source-verifiable design label; omitted where a stable label was not independently clear.",
        "cases": manifest_cases,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
