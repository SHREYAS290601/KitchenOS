class LifecycleError(ValueError):
    """Raised on an illegal lifecycle transition; names both states."""


# Manifest §12: forward path with legal skips along it, plus side states.
# A table, not conditionals — every state is a key; terminal states map to empty sets.
TRANSITIONS: dict[str, set[str]] = {
    "planned": {"bought", "archived"},
    "bought": {"estimated", "enriched", "stored"},
    "estimated": {"enriched", "stored"},
    "enriched": {"stored"},
    "stored": {"opened", "expired_or_discarded", "archived"},
    "opened": {
        "partially_used", "low_quantity", "used_up",
        "expired_or_discarded", "review_eligible",
    },
    "partially_used": {
        "low_quantity", "used_up", "expired_or_discarded", "review_eligible",
    },
    "low_quantity": {"used_up", "expired_or_discarded", "reorder_candidate"},
    "used_up": {"reorder_candidate", "review_eligible", "archived"},
    "expired_or_discarded": {"reorder_candidate", "archived"},
    "review_eligible": {"reviewed"},
    "reviewed": {"reorder_candidate", "archived"},
    "reorder_candidate": {"planned", "archived"},
    "archived": set(),
}


def advance(current: str, target: str) -> str:
    if current not in TRANSITIONS:
        raise LifecycleError(f"{current!r} is not a lifecycle state")
    if target not in TRANSITIONS:
        raise LifecycleError(f"{target!r} is not a lifecycle state")
    if target not in TRANSITIONS[current]:
        allowed = ", ".join(sorted(TRANSITIONS[current])) or "none (terminal state)"
        raise LifecycleError(
            f"cannot move from {current!r} to {target!r} — allowed next states: {allowed}"
        )
    return target
