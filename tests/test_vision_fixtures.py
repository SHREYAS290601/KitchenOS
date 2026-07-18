import hashlib
import json
from pathlib import Path

from PIL import Image

from backend.app.vision.preprocessing import crop_bbox, normalize_image
from scripts.generate_vision_fixtures import generate


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "vision"
EXPECTED_FIXTURES = {
    "grayscale.png",
    "rgb_landscape.png",
    "rgba_alpha.png",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _pixel_sha256(image: Image.Image) -> str:
    header = f"{image.mode}:{image.width}x{image.height}:".encode()
    return _sha256(header + image.tobytes())


def test_synthetic_vision_fixture_manifest_is_complete_and_reproducible() -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())

    assert manifest["schema_version"] == 1
    assert manifest["coordinate_convention"] == "[x_min,y_min,x_max,y_max)"
    assert manifest["provenance"] == "synthetic"
    assert manifest["license"] == "CC0-1.0"
    assert {entry["file"] for entry in manifest["fixtures"]} == EXPECTED_FIXTURES

    for entry in manifest["fixtures"]:
        fixture_path = FIXTURE_ROOT / entry["file"]
        file_payload = fixture_path.read_bytes()
        with Image.open(fixture_path) as image:
            image.load()
            assert image.info == {}
            assert list(image.size) == entry["dimensions"]
            assert image.mode == entry["mode"]
            assert _pixel_sha256(image) == entry["pixel_sha256"]
            expected = entry["expected"]
            assert _pixel_sha256(normalize_image(image)) == expected[
                "normalized_pixel_sha256"
            ]
            if "crop_bbox" in expected:
                assert _pixel_sha256(crop_bbox(image, expected["crop_bbox"])) == expected[
                    "crop_pixel_sha256"
                ]
        assert _sha256(file_payload) == entry["sha256"]


def test_fixture_generator_reproduces_committed_bytes(tmp_path: Path) -> None:
    generated_manifest = generate(tmp_path)
    committed_manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())

    assert generated_manifest == committed_manifest
    for filename in EXPECTED_FIXTURES:
        assert (tmp_path / filename).read_bytes() == (FIXTURE_ROOT / filename).read_bytes()
