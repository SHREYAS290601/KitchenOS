from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    model_validator,
)


Confidence = Annotated[float, Field(ge=0.0, le=1.0, strict=True)]
PixelCoordinate = Annotated[StrictInt, Field(ge=0)]
PositiveDimension = Annotated[StrictInt, Field(gt=0, le=65_535)]
BoundingBox = tuple[
    PixelCoordinate,
    PixelCoordinate,
    PixelCoordinate,
    PixelCoordinate,
]
SafeText = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=512,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]
ShortText = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]
VersionText = Annotated[
    str,
    StringConstraints(
        strict=True,
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]
Sha256Digest = Annotated[
    str,
    StringConstraints(strict=True, pattern=r"^[0-9a-f]{64}$"),
]


class VisionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class BoundedRegion(VisionContract):
    bbox: BoundingBox

    @model_validator(mode="after")
    def validate_non_empty_bbox(self) -> "BoundedRegion":
        xmin, ymin, xmax, ymax = self.bbox
        if xmin >= xmax or ymin >= ymax:
            raise ValueError("bbox must describe a non-empty XYXY pixel region")
        return self


class Detection(BoundedRegion):
    label: ShortText
    confidence: Confidence


class SegmentRegion(BoundedRegion):
    detection_index: Annotated[StrictInt, Field(ge=0)]
    confidence: Confidence | None = None
    engine: ShortText
    engine_version: VersionText


class OcrCandidate(VisionContract):
    field: Literal["brand", "product_name", "package_size"]
    value: SafeText
    source: Literal["label_ocr", "receipt_ocr"]
    confidence: Confidence
    status: Literal["estimated"] = "estimated"


class BarcodeCandidate(VisionContract):
    value: Annotated[
        str,
        StringConstraints(strict=True, pattern=r"^[0-9]{8,14}$"),
    ]
    symbology: Literal["EAN13", "EAN8", "UPCA"]
    checksum_valid: Literal[True]
    decoder: ShortText
    decoder_version: VersionText
    decoder_quality: Annotated[StrictInt, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def validate_length_and_checksum(self) -> "BarcodeCandidate":
        expected_lengths = {"EAN13": 13, "EAN8": 8, "UPCA": 12}
        if len(self.value) != expected_lengths[self.symbology]:
            raise ValueError("barcode length does not match symbology")

        body = [int(digit) for digit in self.value[:-1]]
        first_weight = 1 if self.symbology == "EAN13" else 3
        weighted_sum = sum(
            digit * (first_weight if index % 2 == 0 else 4 - first_weight)
            for index, digit in enumerate(body)
        )
        expected_check_digit = (-weighted_sum) % 10
        if int(self.value[-1]) != expected_check_digit:
            raise ValueError("barcode checksum is invalid")
        return self


class ImageDimensions(VisionContract):
    width: PositiveDimension
    height: PositiveDimension


class InferenceGeometry(VisionContract):
    source_size: ImageDimensions
    normalized_size: ImageDimensions
    inference_size: ImageDimensions
    coordinate_space: Literal["inference_pixels"] = "inference_pixels"
    coordinate_convention: Literal["[x_min,y_min,x_max,y_max)"] = (
        "[x_min,y_min,x_max,y_max)"
    )
    source_exif_orientation: Literal[1, 2, 3, 4, 5, 6, 7, 8] = 1
    scale_x: Annotated[float, Field(gt=0.0, le=1.0, strict=True)]
    scale_y: Annotated[float, Field(gt=0.0, le=1.0, strict=True)]
    preprocessing_version: VersionText

    @model_validator(mode="after")
    def validate_scale(self) -> "InferenceGeometry":
        expected_x = self.inference_size.width / self.normalized_size.width
        expected_y = self.inference_size.height / self.normalized_size.height
        if abs(self.scale_x - expected_x) > 1e-9:
            raise ValueError("scale_x must map normalized width to inference width")
        if abs(self.scale_y - expected_y) > 1e-9:
            raise ValueError("scale_y must map normalized height to inference height")
        return self


class DetectionBatch(VisionContract):
    input_sha256: Sha256Digest
    geometry: InferenceGeometry
    detections: tuple[Detection, ...]
    engine_kind: Literal["fixture", "learned"]
    engine: ShortText
    engine_version: VersionText
    checkpoint_sha256: Sha256Digest | None = None

    @model_validator(mode="after")
    def validate_detection_bounds(self) -> "DetectionBatch":
        if self.engine_kind == "learned" and self.checkpoint_sha256 is None:
            raise ValueError("learned engine requires a checkpoint_sha256")
        width = self.geometry.inference_size.width
        height = self.geometry.inference_size.height
        if any(
            detection.bbox[2] > width or detection.bbox[3] > height
            for detection in self.detections
        ):
            raise ValueError("detection bbox must fit within inference dimensions")
        return self
