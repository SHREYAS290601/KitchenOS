import pytest

from backend.app.agents.auditor import AuditContext, AuditProposal, AuditorAgent


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        ("This is safe for your allergy.", "medical_or_safety_claim"),
        ("This is definitely Chobani yogurt.", "unsupported_identity_claim"),
    ],
)
def test_auditor_blocks_unsafe_or_unsourced_claims(answer, reason):
    verdict = AuditorAgent().review(
        AuditProposal(answer=answer, asserted_identity=True),
        AuditContext(has_identity_evidence=False, image_consented=True),
    )
    assert verdict.verdict == "block"
    assert reason in verdict.reasons


def test_auditor_blocks_nonconsented_image_and_flags_low_confidence_fact():
    no_consent = AuditorAgent().review(
        AuditProposal(answer="It looks suitable.", uses_image=True),
        AuditContext(image_consented=False),
    )
    low_confidence = AuditorAgent().review(
        AuditProposal(answer="This is yogurt.", confidence=0.4),
        AuditContext(image_consented=True),
    )
    assert no_consent.verdict == "block"
    assert low_confidence.verdict == "needs_review"


def test_auditor_passes_clean_answer():
    verdict = AuditorAgent().review(
        AuditProposal(answer="It looks like yogurt; compare the label with your preferences."),
        AuditContext(image_consented=True),
    )
    assert verdict.verdict == "pass"
    assert verdict.reasons == []
