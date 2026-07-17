import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import DevUser, get_current_user, get_db
from backend.app.models.consent import ConsentState
from backend.app.schemas.consent import ConsentResponse, ConsentUpdate
from backend.app.services.consent import grant, revoke

router = APIRouter(prefix="/consent", tags=["consent"])


@router.post("", response_model=ConsentResponse)
def update_consent(
    payload: ConsentUpdate,
    db: Session = Depends(get_db),
    user: DevUser = Depends(get_current_user),
) -> ConsentResponse:
    try:
        if payload.state == ConsentState.revoked:
            row = revoke(db, user.user_id)
        else:
            row = grant(
                db,
                user.user_id,
                payload.state,
                session_id=(
                    str(uuid.uuid4())
                    if payload.state == ConsentState.granted_for_session
                    else None
                ),
                retention_policy=payload.retention_policy,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ConsentResponse(
        user_id=str(row.user_id),
        state=row.state,
        shopping_session_id=row.session_id,
        retention_policy=row.retention_policy,
    )
