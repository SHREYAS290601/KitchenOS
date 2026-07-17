from io import BytesIO
import warnings

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.app.deps import (
    DevUser,
    enforce_upload_rate_limit,
    get_current_user,
    get_db,
)
from backend.app.models.consent import RetentionPolicy
from backend.app.services.image_storage import ConsentRequired, store_image

router = APIRouter(prefix="/images", tags=["images"])

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_IMAGE_DIMENSION = 4096
_CHUNK_BYTES = 1024 * 1024
_EXPECTED_FORMAT = {"image/jpeg": "JPEG", "image/png": "PNG"}


class ImageTooLarge(ValueError):
    pass


class InvalidImage(ValueError):
    pass


async def read_validated_image(
    image: UploadFile,
    content_type: str,
) -> tuple[bytes, str]:
    expected_format = _EXPECTED_FORMAT.get(content_type)
    if expected_format is None:
        raise InvalidImage("image must be JPEG or PNG")

    raw = bytearray()
    while chunk := await image.read(_CHUNK_BYTES):
        if len(raw) + len(chunk) > MAX_IMAGE_BYTES:
            raise ImageTooLarge("image exceeds the 10 MB limit")
        raw.extend(chunk)
    if not raw:
        raise InvalidImage("image file is empty")

    data = await run_in_threadpool(
        _decode_and_reencode,
        bytes(raw),
        expected_format,
    )
    return data, content_type


def _decode_and_reencode(raw: bytes, expected_format: str) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as decoded:
                if decoded.format != expected_format:
                    raise InvalidImage("image content does not match its media type")
                width, height = decoded.size
                if (
                    width > MAX_IMAGE_DIMENSION
                    or height > MAX_IMAGE_DIMENSION
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise ImageTooLarge("image dimensions exceed the processing limit")
                decoded.load()
                output = BytesIO()
                if expected_format == "JPEG":
                    decoded.convert("RGB").save(output, format="JPEG", quality=90)
                else:
                    decoded.save(output, format="PNG", optimize=True)
    except ImageTooLarge:
        raise
    except InvalidImage:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise InvalidImage("image content is invalid") from exc
    return output.getvalue()


@router.post("", status_code=201)
async def upload_image(
    request: Request,
    image: UploadFile = File(...),
    capture_context: str = Form(...),
    shopping_session_id: str | None = Form(None),
    related_item_candidate: str | None = Form(None),
    retention_policy: RetentionPolicy = Form(RetentionPolicy.delete_after_answer),
    db: Session = Depends(get_db),
    user: DevUser = Depends(get_current_user),
    _rate_limit: None = Depends(enforce_upload_rate_limit),
) -> dict:
    content_type = image.content_type or "application/octet-stream"
    try:
        data, content_type = await read_validated_image(image, content_type)
    except ImageTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except InvalidImage as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        record = store_image(
            db,
            request.app.state.object_store,
            user_id=user.user_id,
            image_bytes=data,
            content_type=content_type,
            capture_context=capture_context,
            shopping_session_id=shopping_session_id,
            retention_policy=retention_policy,
            related_item_candidate=related_item_candidate,
        )
    except ConsentRequired as exc:
        raise HTTPException(
            status_code=403,
            detail="image consent: grant single-image, session, or always consent before uploading",
        ) from exc
    return {
        "image_id": str(record.image_id),
        "consent_status": record.consent_status,
        "retention_policy": record.retention_policy,
        "stored_for_future_enrichment": record.stored_for_future_enrichment,
    }
