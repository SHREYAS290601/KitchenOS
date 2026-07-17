from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.llm import get_llm_client
from backend.app.agents.while_shopping_assistant import AssistContext, WhileShoppingAssistantAgent
from backend.app.deps import DevUser, get_current_user, get_db
from backend.app.models.consent import RetentionPolicy
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.models.pantry_item import PantryItem
from backend.app.schemas.assist import AssistRequest, AssistResponse
from backend.app.services.checkin import consent_allows_processing
from backend.app.services.retention import mark_retention_due

router = APIRouter(prefix="/shopping/assist", tags=["assist"])


@router.post("", response_model=AssistResponse)
def assist(
    payload: AssistRequest,
    db: Session = Depends(get_db),
    user: DevUser = Depends(get_current_user),
) -> AssistResponse:
    image = None
    if payload.image_id is not None:
        image = db.get(ImageEvidenceRecord, payload.image_id)
        if image is None:
            raise HTTPException(status_code=404, detail=f"image {payload.image_id} not found")
        if image.user_id != user.user_id or image.deleted_at is not None:
            raise HTTPException(status_code=404, detail=f"image {payload.image_id} not found")

    items = db.execute(select(PantryItem).where(PantryItem.user_id == user.user_id)).scalars()
    pantry_names = [str(item.canonical_name["value"]) for item in items if item.canonical_name]
    image_consented = image is None or consent_allows_processing(db, image)
    result = WhileShoppingAssistantAgent(get_llm_client()).run(
        AssistContext(
            question=payload.question,
            pantry_names=pantry_names,
            uses_image=image is not None,
            image_consented=image_consented,
            has_identity_evidence=False,
        )
    )
    if image and image.retention_policy == RetentionPolicy.delete_after_answer:
        mark_retention_due(db, image)
    return AssistResponse(
        **result.model_dump(),
        image_id=image.image_id if image else None,
    )
