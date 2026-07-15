import json
import os
from typing import Protocol, TypeVar
from urllib.request import Request, urlopen

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMClient(Protocol):
    def complete_structured(self, prompt: str, schema: type[SchemaT]) -> SchemaT: ...


class FailingLLM:
    def complete_structured(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        raise RuntimeError("LLM unavailable")


class FakeLLM:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses

    def complete_structured(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        for marker, payload in self.responses.items():
            if marker in prompt:
                return schema.model_validate(payload)
        raise RuntimeError("no canned response for prompt")


class LocalDemoLLM:
    """Deterministic Phase-4 implementation used without an external API key.

    It obeys the same structured boundary as a hosted model, which lets the
    complete product flow run locally and keeps provider wiring replaceable.
    """

    def complete_structured(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        fields = schema.model_fields
        if "answer" in fields:
            pantry = prompt.partition("Pantry: ")[2].partition("\n")[0].strip()
            preferences = prompt.partition("Preferences: ")[2].partition("\n")[0].strip()
            context = ""
            if pantry:
                context += f" Your pantry currently includes {pantry}."
            if preferences:
                context += f" Saved preferences: {preferences}."
            return schema.model_validate(
                {
                    "answer": (
                        "It looks like the item you are considering. Compare its label "
                        "with your dietary restrictions and past preferences before buying it."
                        + context
                    ),
                    "confidence": 0.7,
                    "asserted_identity": False,
                }
            )
        raise RuntimeError("local demo model does not support this schema")


class OpenRouterLLM:
    def __init__(self, *, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete_structured(self, prompt: str, schema: type[SchemaT]) -> SchemaT:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "strict": True,
                        "schema": schema.model_json_schema(),
                    },
                },
            }
        ).encode()
        request = Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            body = json.loads(response.read())
        content = body["choices"][0]["message"]["content"]
        return schema.model_validate_json(content)


def get_llm_client() -> LLMClient:
    api_key = os.environ.get("PANTRYOPS_LLM_API_KEY")
    if api_key and not api_key.endswith("changeme"):
        return OpenRouterLLM(
            api_key=api_key,
            model=os.environ.get("PANTRYOPS_LLM_MODEL", "deepseek/deepseek-v4-flash"),
            base_url=os.environ.get("PANTRYOPS_LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        )
    return LocalDemoLLM()
