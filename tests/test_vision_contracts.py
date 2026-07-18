from pathlib import Path
import subprocess
import sys
import tomllib

import pytest
from pydantic import ValidationError

from backend.app.vision.contracts import (
    BarcodeCandidate,
    Detection,
    DetectionBatch,
    ImageDimensions,
    InferenceGeometry,
    OcrCandidate,
    SegmentRegion,
)
from backend.app.vision.errors import ModelAssetsUnavailable


def test_detection_is_strict_immutable_category_evidence() -> None:
    detection = Detection(
        label="tomato",
        bbox=(1, 2, 8, 10),
        confidence=0.86,
    )

    assert detection.bbox == (1, 2, 8, 10)
    assert "brand" not in type(detection).model_fields
    with pytest.raises(ValidationError):
        detection.label = "yogurt"


@pytest.mark.parametrize(
    "payload",
    [
        {"bbox": (1, 2, 1, 10), "confidence": 0.5},
        {"bbox": (-1, 2, 8, 10), "confidence": 0.5},
        {"bbox": (1.0, 2, 8, 10), "confidence": 0.5},
        {"bbox": (1, 2, 8, 10), "confidence": -0.1},
        {"bbox": (1, 2, 8, 10), "confidence": None},
    ],
)
def test_detection_rejects_invalid_geometry_or_confidence(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        Detection(
            label="tomato",
            **payload,
        )


def test_segment_and_ocr_estimates_require_confidence_and_are_immutable() -> None:
    segment = SegmentRegion(
        detection_index=0,
        bbox=(1, 2, 8, 10),
        confidence=0.75,
        engine="bbox_fallback",
        engine_version="1.0",
    )
    candidate = OcrCandidate(
        field="brand",
        value="Chobani",
        source="label_ocr",
        confidence=0.84,
    )

    assert segment.confidence == 0.75
    assert candidate.status == "estimated"
    with pytest.raises(ValidationError):
        OcrCandidate(
            field="brand",
            value="Chobani",
            source="label_ocr",
            confidence=None,
        )
    with pytest.raises(ValidationError):
        candidate.value = "Other"


def test_bbox_fallback_region_does_not_invent_confidence() -> None:
    segment = SegmentRegion(
        detection_index=0,
        bbox=(1, 2, 8, 10),
        engine="bbox_fallback",
        engine_version="1.0",
    )

    assert segment.confidence is None


def test_barcode_candidate_keeps_native_quality_not_fake_probability() -> None:
    candidate = BarcodeCandidate(
        value="036000291452",
        symbology="UPCA",
        checksum_valid=True,
        decoder="zbar",
        decoder_version="0.23.93",
        decoder_quality=88,
    )

    assert candidate.decoder_quality == 88
    assert "confidence" not in type(candidate).model_fields


def test_invalid_barcode_checksum_cannot_become_a_candidate() -> None:
    with pytest.raises(ValidationError):
        BarcodeCandidate(
            value="036000291452",
            symbology="UPCA",
            checksum_valid=False,
            decoder="zbar",
            decoder_version="0.23.93",
        )


@pytest.mark.parametrize(
    ("value", "symbology"),
    [
        ("036000291453", "UPCA"),
        ("036000291452", "EAN13"),
        ("12345670", "EAN13"),
    ],
)
def test_barcode_candidate_validates_length_and_checksum(
    value: str,
    symbology: str,
) -> None:
    with pytest.raises(ValidationError):
        BarcodeCandidate(
            value=value,
            symbology=symbology,
            checksum_valid=True,
            decoder="zbar",
            decoder_version="0.23.93",
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"label": " "},
        {"label": "tomato\nother"},
        {"label": "x" * 129},
    ],
)
def test_detection_rejects_empty_control_or_unbounded_text(
    payload: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        Detection(bbox=(0, 0, 1, 1), confidence=0.5, **payload)


def test_detection_batch_binds_boxes_to_reproducible_geometry() -> None:
    geometry = InferenceGeometry(
        source_size=ImageDimensions(width=16, height=8),
        normalized_size=ImageDimensions(width=16, height=8),
        inference_size=ImageDimensions(width=8, height=4),
        source_exif_orientation=1,
        scale_x=0.5,
        scale_y=0.5,
        preprocessing_version="1.0",
    )
    detection = Detection(
        label="tomato",
        bbox=(1, 1, 8, 4),
        confidence=0.0,
    )

    batch = DetectionBatch(
        input_sha256="a" * 64,
        geometry=geometry,
        detections=(detection,),
        engine_kind="fixture",
        engine="fixture-detector",
        engine_version="1.0",
        checkpoint_sha256=None,
    )

    assert batch.geometry.coordinate_space == "inference_pixels"
    assert batch.detections == (detection,)


def test_detection_batch_rejects_box_outside_inference_dimensions() -> None:
    geometry = InferenceGeometry(
        source_size=ImageDimensions(width=8, height=4),
        normalized_size=ImageDimensions(width=8, height=4),
        inference_size=ImageDimensions(width=8, height=4),
        source_exif_orientation=1,
        scale_x=1.0,
        scale_y=1.0,
        preprocessing_version="1.0",
    )
    detection = Detection(
        label="tomato",
        bbox=(1, 1, 9, 4),
        confidence=0.5,
    )

    with pytest.raises(ValidationError, match="inference dimensions"):
        DetectionBatch(
            input_sha256="a" * 64,
            geometry=geometry,
            detections=(detection,),
            engine_kind="fixture",
            engine="fixture-detector",
            engine_version="1.0",
        )


def test_learned_detection_batch_requires_checkpoint_digest() -> None:
    geometry = InferenceGeometry(
        source_size=ImageDimensions(width=8, height=4),
        normalized_size=ImageDimensions(width=8, height=4),
        inference_size=ImageDimensions(width=8, height=4),
        source_exif_orientation=1,
        scale_x=1.0,
        scale_y=1.0,
        preprocessing_version="1.0",
    )

    with pytest.raises(ValidationError, match="checkpoint"):
        DetectionBatch(
            input_sha256="a" * 64,
            geometry=geometry,
            detections=(),
            engine_kind="learned",
            engine="rf-detr",
            engine_version="1.0",
        )

    learned = DetectionBatch(
        input_sha256="a" * 64,
        geometry=geometry,
        detections=(),
        engine_kind="learned",
        engine="rf-detr",
        engine_version="1.0",
        checkpoint_sha256="b" * 64,
    )

    assert learned.checkpoint_sha256 == "b" * 64


@pytest.mark.parametrize(
    ("scale_x", "scale_y", "message"),
    [
        (0.4, 0.5, "scale_x"),
        (0.5, 0.4, "scale_y"),
    ],
)
def test_inference_geometry_rejects_inconsistent_scale(
    scale_x: float,
    scale_y: float,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        InferenceGeometry(
            source_size=ImageDimensions(width=16, height=8),
            normalized_size=ImageDimensions(width=16, height=8),
            inference_size=ImageDimensions(width=8, height=4),
            source_exif_orientation=1,
            scale_x=scale_x,
            scale_y=scale_y,
            preprocessing_version="1.0",
        )


def test_model_assets_error_is_actionable_without_exposing_a_path() -> None:
    error = ModelAssetsUnavailable(
        model_name="sam3",
        fetch_command="uv run python scripts/fetch_models.py --model sam3",
    )

    message = str(error)
    assert message == "Required local model assets are unavailable."
    assert "/Users/" not in message


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model_name": "", "fetch_command": "fetch sam3"},
        {"model_name": "sam3\nother", "fetch_command": "fetch sam3"},
        {"model_name": "sam3", "fetch_command": ""},
        {"model_name": "sam3", "fetch_command": "fetch sam3\nother"},
    ],
)
def test_model_assets_error_rejects_unsafe_diagnostics(
    kwargs: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        ModelAssetsUnavailable(**kwargs)


def test_importing_vision_foundation_loads_no_model_runtime() -> None:
    code = """
import sys
import backend.app.vision.contracts
import backend.app.vision.errors
import backend.app.vision.preprocessing
blocked = ("torch", "rfdetr", "sam3", "paddle", "pyzbar", "cv2")
loaded = sorted(name for name in sys.modules if name.split(".")[0] in blocked)
raise SystemExit("heavy runtimes loaded: " + repr(loaded) if loaded else 0)
"""

    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr


def test_pytest_registers_and_excludes_model_integration_profiles() -> None:
    config_path = Path(__file__).parents[1] / "pyproject.toml"
    pytest_config = tomllib.loads(config_path.read_text())["tool"]["pytest"][
        "ini_options"
    ]

    markers = pytest_config["markers"]
    addopts = pytest_config["addopts"]
    assert any(entry.startswith("integration:") for entry in markers)
    assert any(entry.startswith("integration_cpu:") for entry in markers)
    assert any(entry.startswith("integration_gpu:") for entry in markers)
    assert "not integration" in addopts
    assert "not integration_cpu" in addopts
    assert "not integration_gpu" in addopts
    assert "--strict-markers" in addopts
