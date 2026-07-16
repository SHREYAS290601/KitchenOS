import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from backend.app.deps import get_db
from backend.app.models.consent import RetentionPolicy
from backend.app.services.image_storage import ConsentRequired, store_image

router = APIRouter(prefix="/images", tags=["images"])


@router.post("", status_code=201)
async def upload_image(
    request: Request,
    image: UploadFile = File(...),
    capture_context: str = Form(...),
    shopping_session_id: str | None = Form(None),
    related_item_candidate: str | None = Form(None),
    retention_policy: RetentionPolicy = Form(RetentionPolicy.delete_after_answer),
    user_id: uuid.UUID = Form(uuid.UUID("00000000-0000-0000-0000-000000000001")),
    db: Session = Depends(get_db),
) -> dict:
    content_type = image.content_type or "application/octet-stream"
    if content_type not in {"image/jpeg", "image/png"}:
        raise HTTPException(status_code=422, detail="image must be JPEG or PNG")
    data = await image.read()
    if not data:
        raise HTTPException(status_code=422, detail="image file is empty")
    try:
        record = store_image(
            db,
            request.app.state.object_store,
            user_id=user_id,
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
