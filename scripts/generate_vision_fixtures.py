from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_FIXTURE_ROOT = Path(__file__).parents[1] / "tests" / "fixtures" / "vision"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _pixel_sha256(image: Image.Image) -> str:
    header = f"{image.mode}:{image.width}x{image.height}:".encode()
    return _sha256(header + image.tobytes())


def _rgb_landscape() -> Image.Image:
    pixels = bytes(
        channel
        for y in range(4)
        for x in range(8)
        for channel in (x * 24, y * 60, (x + y) * 16)
    )
    return Image.frombytes("RGB", (8, 4), pixels)


def _rgba_alpha() -> Image.Image:
    pixels = bytes(
        channel
        for y in range(4)
        for x in range(4)
        for channel in (220, x * 50, y * 50, (x + y) * 32)
    )
    return Image.frombytes("RGBA", (4, 4), pixels)


def _grayscale() -> Image.Image:
    pixels = bytes((x * 30 + y * 12) % 256 for y in range(6) for x in range(4))
    return Image.frombytes("L", (4, 6), pixels)


def _write_fixture(
    fixture_root: Path,
    filename: str,
    image: Image.Image,
    expected: dict[str, Any],
) -> dict[str, Any]:
    destination = fixture_root / filename
    image.save(destination, format="PNG", optimize=False, compress_level=9)
    payload = destination.read_bytes()
    return {
        "file": filename,
        "sha256": _sha256(payload),
        "pixel_sha256": _pixel_sha256(image),
        "dimensions": list(image.size),
        "mode": image.mode,
        "expected": expected,
    }


def _normalized_rgb(image: Image.Image) -> Image.Image:
    if "A" in image.getbands() or "transparency" in image.info:
        rgba_image = image.convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255, 255))
        return Image.alpha_composite(background, rgba_image).convert("RGB")
    return image.convert("RGB")


def generate(fixture_root: Path) -> dict[str, Any]:
    fixture_root.mkdir(parents=True, exist_ok=True)
    rgb_landscape = _rgb_landscape()
    rgba_alpha = _rgba_alpha()
    grayscale = _grayscale()
    rgb_crop = rgb_landscape.crop((2, 1, 6, 4))
    fixtures = [
        _write_fixture(
            fixture_root,
            "rgb_landscape.png",
            rgb_landscape,
            {
                "crop_bbox": [2, 1, 6, 4],
                "crop_pixel_sha256": _pixel_sha256(rgb_crop),
                "normalized_mode": "RGB",
                "normalized_pixel_sha256": _pixel_sha256(
                    _normalized_rgb(rgb_landscape)
                ),
            },
        ),
        _write_fixture(
            fixture_root,
            "rgba_alpha.png",
            rgba_alpha,
            {
                "normalized_mode": "RGB",
                "normalized_pixel_sha256": _pixel_sha256(
                    _normalized_rgb(rgba_alpha)
                ),
                "alpha_background": "white",
            },
        ),
        _write_fixture(
            fixture_root,
            "grayscale.png",
            grayscale,
            {
                "normalized_mode": "RGB",
                "normalized_pixel_sha256": _pixel_sha256(
                    _normalized_rgb(grayscale)
                ),
                "channels": "replicated",
            },
        ),
    ]
    manifest = {
        "schema_version": 1,
        "coordinate_convention": "[x_min,y_min,x_max,y_max)",
        "provenance": "synthetic",
        "license": "CC0-1.0",
        "generator": "scripts/generate_vision_fixtures.py",
        "fixtures": fixtures,
    }
    destination = fixture_root / "manifest.json"
    destination.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    generate(DEFAULT_FIXTURE_ROOT)


if __name__ == "__main__":
    main()
