from typing import Literal

from pydantic import BaseModel


class ConsumptionClarification(BaseModel):
    question: str
    options: list[str] | None = None
    input_type: Literal["capacity_bucket", "count", "item_selection"]


class ConsumptionUpdateAgent:
    def clarify(self, canonical_name: str, quantity_type: str) -> ConsumptionClarification:
        if quantity_type == "count":
            return ConsumptionClarification(
                question=f"How many {canonical_name} are left?",
                input_type="count",
            )
        return ConsumptionClarification(
            question=f"How much {canonical_name} is left?",
            options=["full", "3/4", "1/2", "1/4", "empty"],
            input_type="capacity_bucket",
        )
