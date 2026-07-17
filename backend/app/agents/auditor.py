import re
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from backend.app.schemas.sourced_field import FieldStatus

if TYPE_CHECKING:
    from backend.app.agents.background_enrichment import BackgroundEnrichmentProposal


class AuditProposal(BaseModel):
    answer: str
    uses_image: bool = False
    asserted_identity: bool = False
    confidence: float | None = None


class AuditContext(BaseModel):
    image_consented: bool = True
    has_identity_evidence: bool = False


class AuditVerdict(BaseModel):
    verdict: Literal["pass", "block", "needs_review"]
    reasons: list[str] = Field(default_factory=list)


class AuditorAgent:
    _medical = re.compile(r"\b(safe for|safe to eat|allergy-safe|treats?|cures?|medical advice)\b", re.I)

    def review(self, proposal: AuditProposal, context: AuditContext) -> AuditVerdict:
        reasons: list[str] = []
        if proposal.uses_image and not context.image_consented:
            reasons.append("processing_without_consent")
        if self._medical.search(proposal.answer):
            reasons.append("medical_or_safety_claim")
        if proposal.asserted_identity and not context.has_identity_evidence:
            reasons.append("unsupported_identity_claim")
        if reasons:
            return AuditVerdict(verdict="block", reasons=reasons)
        if proposal.confidence is not None and proposal.confidence < 0.5 and not re.search(r"estimated|might|may|looks like", proposal.answer, re.I):
            return AuditVerdict(verdict="needs_review", reasons=["low_confidence_shown_as_fact"])
        return AuditVerdict(verdict="pass")

    def review_background(
        self,
        proposal: "BackgroundEnrichmentProposal",
        *,
        consent_valid: bool,
    ) -> AuditVerdict:
        if not consent_valid:
            return AuditVerdict(verdict="block", reasons=["processing_without_consent"])
        if any(
            candidate.field.status != FieldStatus.estimated
            for candidate in proposal.candidates
        ):
            return AuditVerdict(verdict="block", reasons=["non_estimate_background_write"])
        if proposal.needs_user_review:
            return AuditVerdict(verdict="needs_review", reasons=["low_confidence_estimate"])
        return AuditVerdict(verdict="pass")
