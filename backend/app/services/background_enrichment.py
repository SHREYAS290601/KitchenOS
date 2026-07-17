from sqlalchemy.orm import Session

from backend.app.agents.background_enrichment import BackgroundEnrichmentProposal
from backend.app.models.pantry_item import PantryItem
from backend.app.services.ledger import ApplyResult, apply_update


def apply_enrichment_proposal(
    db: Session,
    item: PantryItem,
    proposal: BackgroundEnrichmentProposal,
) -> list[ApplyResult]:
    """Structured tool boundary between proposal-only agents and the ledger."""
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
    if proposal.needs_user_review:
        item.needs_user_review = True
        db.flush()
    return results
