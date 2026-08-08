"""Reproduce Benchmark v1 derivatives from the committed licensed sources."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
IMAGES = ROOT / "images"


def _save_jpeg(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, "JPEG", quality=92, optimize=True)


def _split_india() -> tuple[Image.Image, Image.Image]:
    with Image.open(SOURCE / "india-rupee-1918-pair.jpg") as source:
        image = source.convert("RGB")
    midpoint = image.width // 2
    return (
        image.crop((0, 0, midpoint, image.height)),
        image.crop((midpoint, 0, image.width, image.height)),
    )


def _rotate(image: Image.Image) -> Image.Image:
    return image.rotate(17, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(40, 40, 40))


def _low_contrast(image: Image.Image) -> Image.Image:
    image = ImageEnhance.Contrast(image.convert("RGB")).enhance(0.32)
    return image.filter(ImageFilter.GaussianBlur(radius=1.4))


def _glare(image: Image.Image) -> Image.Image:
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = base.size
    draw.ellipse(
        (width * 0.10, height * 0.08, width * 0.82, height * 0.56),
        fill=(255, 255, 255, 145),
    )
    return Image.alpha_composite(base, overlay).convert("RGB")


def main() -> None:
    india_front, india_reverse = _split_india()
    _save_jpeg(india_front, IMAGES / "india-rupee-1918" / "front.jpg")
    _save_jpeg(india_reverse, IMAGES / "india-rupee-1918" / "reverse.jpg")
    _save_jpeg(_rotate(india_front), IMAGES / "india-rupee-1918-rotated" / "front.jpg")
    _save_jpeg(_rotate(india_reverse), IMAGES / "india-rupee-1918-rotated" / "reverse.jpg")

    for role in ("front", "reverse"):
        with Image.open(SOURCE / f"newfoundland-1908-{role}.jpg") as source:
            _save_jpeg(
                _low_contrast(source),
                IMAGES / "newfoundland-1908-low-contrast" / f"{role}.jpg",
            )

    for role in ("front", "reverse"):
        with Image.open(SOURCE / f"us-cent-2013-{role}.png") as source:
            _save_jpeg(
                _glare(source),
                IMAGES / "us-cent-2013-glare" / f"{role}.jpg",
            )


if __name__ == "__main__":
    main()
