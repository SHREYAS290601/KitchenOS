from io import BytesIO

import pytest
from PIL import Image

from backend.app.vision.errors import UnsafeImageError
from backend.app.vision.preprocessing import (
    crop_bbox,
    decode_image,
    normalize_image,
    resize_max_side,
)


def _snapshot(image: Image.Image) -> tuple[str, tuple[int, int], bytes]:
    return image.mode, image.size, image.tobytes()


@pytest.mark.parametrize(
    ("source_size", "expected_size"),
    [
        ((2000, 1000), (1280, 640)),
        ((1000, 2000), (640, 1280)),
        ((640, 320), (640, 320)),
    ],
)
def test_resize_max_side_preserves_aspect_ratio_without_mutation(
    source_size: tuple[int, int],
    expected_size: tuple[int, int],
) -> None:
    source = Image.new("RGB", source_size, (12, 34, 56))
    before = _snapshot(source)

    result = resize_max_side(source, 1280)

    assert result.size == expected_size
    assert result is not source
    assert _snapshot(source) == before


@pytest.mark.parametrize("max_side", [0, -1, 12.5, True])
def test_resize_max_side_rejects_invalid_limit(max_side: object) -> None:
    with pytest.raises(ValueError, match="max_side"):
        resize_max_side(Image.new("RGB", (4, 3)), max_side)  # type: ignore[arg-type]


def test_crop_bbox_returns_exact_xyxy_region_without_mutation() -> None:
    source = Image.new("RGB", (4, 3))
    source.putdata([(value, value, value) for value in range(12)])
    before = _snapshot(source)
    bbox = [1, 1, 4, 3]

    result = crop_bbox(source, bbox)

    assert result.size == (3, 2)
    assert [
        result.getpixel((x, y))
        for y in range(result.height)
        for x in range(result.width)
    ] == [
        (5, 5, 5),
        (6, 6, 6),
        (7, 7, 7),
        (9, 9, 9),
        (10, 10, 10),
        (11, 11, 11),
    ]
    assert result is not source
    assert bbox == [1, 1, 4, 3]
    assert _snapshot(source) == before


@pytest.mark.parametrize(
    "bbox",
    [
        [-1, 0, 2, 2],
        [0, -1, 2, 2],
        [0, 0, 5, 2],
        [0, 0, 2, 4],
        [2, 0, 2, 2],
        [3, 0, 2, 2],
        [0, 2, 2, 2],
        [0, 3, 2, 2],
        [0, 0, 2],
        [0.0, 0, 2, 2],
    ],
)
def test_crop_bbox_rejects_invalid_bounds(bbox: list[object]) -> None:
    with pytest.raises(ValueError, match="bbox"):
        crop_bbox(Image.new("RGB", (4, 3)), bbox)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("mode", "pixel", "expected"),
    [
        ("RGB", (12, 34, 56), (12, 34, 56)),
        ("RGBA", (10, 20, 30, 0), (255, 255, 255)),
        ("L", 17, (17, 17, 17)),
    ],
)
def test_normalize_image_returns_new_rgb_image_without_mutation(
    mode: str,
    pixel: int | tuple[int, ...],
    expected: tuple[int, int, int],
) -> None:
    source = Image.new(mode, (2, 2), pixel)
    before = _snapshot(source)

    result = normalize_image(source)

    assert result.mode == "RGB"
    assert result.size == source.size
    assert result.getpixel((0, 0)) == expected
    assert result is not source
    assert _snapshot(source) == before


def test_normalize_image_applies_exif_orientation_without_mutation() -> None:
    source = Image.new("RGB", (2, 1))
    source.putdata([(255, 0, 0), (0, 0, 255)])
    source.getexif()[274] = 3
    before = _snapshot(source)

    result = normalize_image(source)

    assert result.getpixel((0, 0)) == (0, 0, 255)
    assert result.getpixel((1, 0)) == (255, 0, 0)
    assert result.getexif().get(274) is None
    assert _snapshot(source) == before


def test_normalize_image_composites_palette_transparency_on_white() -> None:
    source = Image.new("P", (1, 1))
    source.putpalette([0, 0, 0] * 256)
    source.info["transparency"] = 0
    before = _snapshot(source)

    result = normalize_image(source)

    assert result.getpixel((0, 0)) == (255, 255, 255)
    assert _snapshot(source) == before


def _encode(image: Image.Image, image_format: str) -> bytes:
    destination = BytesIO()
    image.save(destination, format=image_format)
    return destination.getvalue()


def test_decode_image_accepts_bounded_png_and_strips_metadata() -> None:
    source = Image.new("RGBA", (2, 2), (10, 20, 30, 0))

    result = decode_image(_encode(source, "PNG"))

    assert result.mode == "RGB"
    assert result.size == (2, 2)
    assert result.getpixel((0, 0)) == (255, 255, 255)
    assert result.info == {}


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        _encode(Image.new("RGB", (2, 2)), "BMP"),
        _encode(Image.new("RGB", (4097, 1)), "PNG"),
    ],
)
def test_decode_image_rejects_unsafe_payloads(payload: bytes) -> None:
    with pytest.raises(UnsafeImageError, match="safely decoded"):
        decode_image(payload)


def test_decode_image_rejects_encoded_size_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.app.vision.preprocessing.MAX_ENCODED_IMAGE_BYTES",
        4,
    )

    with pytest.raises(UnsafeImageError, match="safely decoded"):
        decode_image(_encode(Image.new("RGB", (2, 2)), "PNG"))


def test_decode_image_treats_decompression_bomb_as_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1)

    with pytest.raises(UnsafeImageError, match="safely decoded"):
        decode_image(_encode(Image.new("RGB", (2, 2)), "PNG"))
