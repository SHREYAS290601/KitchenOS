import pytest

from backend.app.pantry.lifecycle import TRANSITIONS, LifecycleError, advance

MANIFEST_STATES = {
    "planned", "bought", "estimated", "enriched", "stored", "opened",
    "partially_used", "low_quantity", "used_up", "expired_or_discarded",
    "review_eligible", "reviewed", "reorder_candidate", "archived",
}


def test_every_manifest_state_is_a_transition_key():
    assert set(TRANSITIONS.keys()) == MANIFEST_STATES


def test_forward_path_is_allowed():
    path = ["planned", "bought", "estimated", "enriched", "stored", "opened",
            "partially_used", "low_quantity", "used_up", "reorder_candidate",
            "archived"]
    for current, target in zip(path, path[1:]):
        assert advance(current, target) == target


def test_manifest_milk_example_path():
    # bought → enriched skips 'estimated'; opened → used_up skips middle states
    for current, target in [("planned", "bought"), ("bought", "enriched"),
                            ("enriched", "stored"), ("stored", "opened"),
                            ("opened", "used_up"), ("used_up", "reorder_candidate"),
                            ("reorder_candidate", "planned")]:
        assert advance(current, target) == target


def test_side_states():
    assert advance("stored", "expired_or_discarded") == "expired_or_discarded"
    assert advance("opened", "review_eligible") == "review_eligible"
    assert advance("review_eligible", "reviewed") == "reviewed"


def test_illegal_jump_rejected():
    with pytest.raises(LifecycleError, match="planned"):
        advance("planned", "used_up")


def test_archived_is_terminal():
    with pytest.raises(LifecycleError, match="archived"):
        advance("archived", "planned")


def test_unknown_state_rejected():
    with pytest.raises(LifecycleError, match="not a lifecycle state"):
        advance("planned", "teleported")
