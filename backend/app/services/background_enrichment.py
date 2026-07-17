import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.auditor import AuditorAgent
from backend.app.agents.background_enrichment import BackgroundEnrichmentProposal
from backend.app.models.background_job import BackgroundJob
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.models.pantry_item import PantryItem
from backend.app.services.checkin import consent_allows_processing
from backend.app.services.ledger import ApplyResult, apply_update


class EnrichmentAuditBlocked(PermissionError):
    pass


def apply_enrichment_proposal(
    db: Session,
    item: PantryItem,
    proposal: BackgroundEnrichmentProposal,
    *,
    job: BackgroundJob,
    auditor: AuditorAgent | None = None,
) -> list[ApplyResult]:
    """Structured tool boundary between proposal-only agents and the ledger."""
    image_ids = [uuid.UUID(image_id) for image_id in job.image_ids]
    images = list(
        db.scalars(
            select(ImageEvidenceRecord).where(
                ImageEvidenceRecord.image_id.in_(image_ids),
                ImageEvidenceRecord.user_id == job.user_id,
                ImageEvidenceRecord.deleted_at.is_(None),
            )
        )
    )
    consent_valid = (
        item.user_id == job.user_id
        and len(images) == len(image_ids)
        and all(consent_allows_processing(db, image) for image in images)
    )
    audit = (auditor or AuditorAgent()).review_background(
        proposal,
        consent_valid=consent_valid,
    )
    if audit.verdict == "block":
        raise EnrichmentAuditBlocked(",".join(audit.reasons))
    results = [
        apply_update(
            db,
            item,
            candidate.field_name,
            candidate.field,
            actor="background_enrichment",
        )
        for candidate in proposal.candidates
    ]
    if proposal.needs_user_review or audit.verdict == "needs_review":
        item.needs_user_review = True
        db.flush()
    return results
