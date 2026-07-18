from collections.abc import Sequence
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app.vision.errors import UnsafeImageError


MAX_ENCODED_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096
MAX_IMAGE_PIXELS = MAX_IMAGE_DIMENSION * MAX_IMAGE_DIMENSION
ALLOWED_IMAGE_FORMATS = frozenset({"JPEG", "PNG"})
ALLOWED_IMAGE_MODES = frozenset({"RGB", "RGBA", "L", "P"})


def resize_max_side(image: Image.Image, max_side: int) -> Image.Image:
    """Return a copy bounded by ``max_side`` without upscaling the source."""
    if isinstance(max_side, bool) or not isinstance(max_side, int) or max_side <= 0:
        raise ValueError("max_side must be a positive integer")

    width, height = image.size
    largest_side = max(width, height)
    if largest_side <= max_side:
        return image.copy()

    scale = max_side / largest_side
    resized_size = (
        max(1, round(width * scale)),
        max(1, round(height * scale)),
    )
    return image.resize(resized_size, resample=Image.Resampling.LANCZOS)


def crop_bbox(image: Image.Image, bbox: Sequence[int]) -> Image.Image:
    """Crop a strict integer ``[xmin, ymin, xmax, ymax]`` pixel region."""
    if len(bbox) != 4 or any(
        isinstance(coordinate, bool) or not isinstance(coordinate, int)
        for coordinate in bbox
    ):
        raise ValueError("bbox must contain four integer XYXY coordinates")

    xmin, ymin, xmax, ymax = bbox
    width, height = image.size
    if (
        xmin < 0
        or ymin < 0
        or xmax > width
        or ymax > height
        or xmin >= xmax
        or ymin >= ymax
    ):
        raise ValueError("bbox must be non-empty and within image bounds")

    return image.crop((xmin, ymin, xmax, ymax))


def normalize_image(image: Image.Image) -> Image.Image:
    """Apply EXIF orientation and return a new RGB image on a white background."""
    oriented_image = ImageOps.exif_transpose(image)
    has_transparency = (
        "A" in oriented_image.getbands() or "transparency" in oriented_image.info
    )
    if not has_transparency:
        return (
            oriented_image.copy()
            if oriented_image.mode == "RGB"
            else oriented_image.convert("RGB")
        )

    rgba_image = oriented_image.convert("RGBA")
    white_background = Image.new("RGBA", oriented_image.size, (255, 255, 255, 255))
    return Image.alpha_composite(white_background, rgba_image).convert("RGB")


def decode_image(payload: bytes) -> Image.Image:
    """Decode bounded JPEG/PNG bytes into a metadata-free normalized RGB image."""
    if (
        not isinstance(payload, bytes)
        or not payload
        or len(payload) > MAX_ENCODED_IMAGE_BYTES
    ):
        raise UnsafeImageError("Image could not be safely decoded")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as source:
                width, height = source.size
                if (
                    source.format not in ALLOWED_IMAGE_FORMATS
                    or source.mode not in ALLOWED_IMAGE_MODES
                    or getattr(source, "n_frames", 1) != 1
                    or width <= 0
                    or height <= 0
                    or width > MAX_IMAGE_DIMENSION
                    or height > MAX_IMAGE_DIMENSION
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise UnsafeImageError("Image could not be safely decoded")
                source.load()
                normalized = normalize_image(source)
    except UnsafeImageError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise UnsafeImageError("Image could not be safely decoded") from exc

    return Image.frombytes("RGB", normalized.size, normalized.tobytes())
