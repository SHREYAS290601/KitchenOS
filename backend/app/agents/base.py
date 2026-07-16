"""Agent protocol (agents.md preamble): every agent takes a Pydantic context
and returns a Pydantic proposal. Agents PROPOSE; structured tools commit.
No agent touches the ledger — services map proposals to apply_update()."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class Agent(Protocol):
    def run(self, context: BaseModel) -> BaseModel: ...
