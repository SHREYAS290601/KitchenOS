from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import get_db
from backend.app.models.consent import ConsentState
from backend.app.schemas.consent import ConsentResponse, ConsentUpdate
from backend.app.services.consent import grant, revoke

router = APIRouter(prefix="/consent", tags=["consent"])


@router.post("", response_model=ConsentResponse)
def update_consent(payload: ConsentUpdate, db: Session = Depends(get_db)) -> ConsentResponse:
    try:
        if payload.state == ConsentState.revoked:
            row = revoke(db, payload.user_id)
        else:
            row = grant(
                db,
                payload.user_id,
                payload.state,
                session_id=payload.shopping_session_id,
                retention_policy=payload.retention_policy,
            )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ConsentResponse(
        user_id=row.user_id,
        state=row.state,
        shopping_session_id=row.session_id,
        retention_policy=row.retention_policy,
    )
