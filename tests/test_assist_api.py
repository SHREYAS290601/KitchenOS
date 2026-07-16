import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_db
from backend.app.main import create_app
from backend.app.models.pantry_item import PantryItem
from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField


@pytest.fixture
def client(db, tables, monkeypatch, tmp_path):
    monkeypatch.setenv("PANTRYOPS_DATABASE_URL", "postgresql+psycopg://pantryops:pantryops@localhost:5432/pantryops")
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("PANTRYOPS_STORAGE_PATH", str(tmp_path))
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_assist_is_audited_and_never_mutates_ledger(client, db):
    item = PantryItem(
        user_id=uuid.uuid4(),
        canonical_name=SourcedField(value="yogurt", source=EvidenceSource.user_confirmed, confidence=1, status=FieldStatus.user_confirmed).model_dump(mode="json"),
        quantity_type="unknown",
        status="stored",
    )
    db.add(item)
    db.commit()
    before = item.canonical_name.copy()

    response = client.post("/shopping/assist", json={"question": "Should I buy this yogurt?"})
    db.refresh(item)

    assert response.status_code == 200
    body = response.json()
    assert body["audit"]["verdict"] == "pass"
    assert "looks like" in body["answer"].lower()
    assert item.canonical_name == before


def test_assist_degrades_when_llm_fails(client, monkeypatch):
    from backend.app.routes import assist
    from backend.app.agents.llm import FailingLLM

    monkeypatch.setattr(assist, "get_llm_client", lambda: FailingLLM())
    response = client.post("/shopping/assist", json={"question": "Should I buy this?"})
    assert response.status_code == 200
    assert response.json()["degraded"] is True


def test_assistant_applies_typed_preference_context():
    from backend.app.agents.auditor import AuditorAgent
    from backend.app.agents.llm import LocalDemoLLM
    from backend.app.agents.while_shopping_assistant import (
        AssistContext,
        PreferenceView,
        WhileShoppingAssistantAgent,
    )

    result = WhileShoppingAssistantAgent(LocalDemoLLM(), AuditorAgent()).run(
        AssistContext(
            question="Should I buy this yogurt?",
            pantry_names=["milk"],
            preferences=[
                PreferenceView(
                    preference_id="pref-yogurt-sour",
                    description="Avoid sour yogurt",
                )
            ],
        )
    )
    assert result.applied_preference_ids == ["pref-yogurt-sour"]
    assert "Avoid sour yogurt" in result.answer
    assert "milk" in result.answer
