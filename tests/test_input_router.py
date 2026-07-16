from backend.app.agents.input_router import InputRouterAgent, RouterContext
from backend.app.agents.llm import FailingLLM


def test_router_routes_supported_intents_with_structured_output():
    router = InputRouterAgent(FailingLLM())

    shopping = router.run(RouterContext(text="Should I buy this yogurt?", has_image=True))
    usage = router.run(RouterContext(text="I used a lot of milk"))
    recipe = router.run(RouterContext(text="What can I cook tonight?"))
    checklist = router.run(RouterContext(text="cross off milk", checklist_item_id="item-1"))

    assert shopping.intent == "shopping_assist"
    assert shopping.agents == ["while_shopping_assistant"]
    assert shopping.payload["item_candidate"] == "yogurt"
    assert usage.intent == "consumption_update"
    assert recipe.intent == "recipe_request"
    assert recipe.phase_status == "coming_in_phase_8"
    assert checklist.intent == "checklist_action"
    assert checklist.payload["checklist_item_id"] == "item-1"
