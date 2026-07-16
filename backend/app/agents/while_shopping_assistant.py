from pydantic import BaseModel, Field

from backend.app.agents.auditor import AuditContext, AuditProposal, AuditVerdict, AuditorAgent
from backend.app.agents.llm import LLMClient


class PreferenceView(BaseModel):
    preference_id: str
    description: str


class AssistContext(BaseModel):
    question: str
    pantry_names: list[str] = Field(default_factory=list)
    preferences: list[PreferenceView] = Field(default_factory=list)
    uses_image: bool = False
    image_consented: bool = True
    has_identity_evidence: bool = False


class AssistDraft(BaseModel):
    answer: str
    confidence: float | None = None
    asserted_identity: bool = False


class AssistResult(BaseModel):
    answer: str
    applied_preference_ids: list[str]
    audit: AuditVerdict
    degraded: bool = False


class WhileShoppingAssistantAgent:
    def __init__(self, llm: LLMClient, auditor: AuditorAgent | None = None):
        self.llm = llm
        self.auditor = auditor or AuditorAgent()

    def run(self, context: AssistContext) -> AssistResult:
        degraded = False
        try:
            draft = self.llm.complete_structured(
                "[ASSIST]\n"
                f"Question: {context.question}\n"
                f"Pantry: {', '.join(context.pantry_names)}\n"
                f"Preferences: {', '.join(p.description for p in context.preferences)}",
                AssistDraft,
            )
        except Exception:
            degraded = True
            draft = AssistDraft(
                answer=(
                    "I cannot analyze the product right now. Compare the package label "
                    "with your dietary restrictions and saved preferences before buying it."
                ),
                confidence=None,
            )
        verdict = self.auditor.review(
            AuditProposal(
                answer=draft.answer,
                uses_image=context.uses_image,
                asserted_identity=draft.asserted_identity,
                confidence=draft.confidence,
            ),
            AuditContext(
                image_consented=context.image_consented,
                has_identity_evidence=context.has_identity_evidence,
            ),
        )
        answer = draft.answer
        if verdict.verdict == "block":
            degraded = True
            answer = (
                "I cannot verify that claim. Check the package label and follow your "
                "documented dietary restrictions; I will not make a safety or exact identity claim."
            )
        return AssistResult(
            answer=answer,
            applied_preference_ids=[p.preference_id for p in context.preferences],
            audit=verdict,
            degraded=degraded,
        )
