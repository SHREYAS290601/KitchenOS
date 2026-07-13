# ADR 003: ML/LLM stack — models, provider, and agent orchestration

**Status:** Accepted (2026-07-13)

## Context

Phases 4–8 need concrete model and tooling choices: the specs previously said "PaddleOCR", "YOLO/RT-DETR", "SAM-style", left the LLM provider abstract, and chose a custom agent state machine over LangGraph. The product owner pinned all five on 2026-07-13.

## Decisions

| Concern | Choice | Notes |
| ------- | ------ | ----- |
| OCR | **PaddleOCR-VL v1.6** | `PaddleOCRVL(pipeline_version="v1.6")`; `predict()` output saved as JSON/Markdown per image for fixtures |
| Detection | **Roboflow RF-DETR nano** (rf-detr-small if accuracy demands) | replaces YOLO/RT-DETR |
| Segmentation | **SAM3** | bbox-crop fallback stays for no-GPU environments (`PANTRYOPS_VISION_SEGMENTER=sam3\|bbox`) |
| LLM | **deepseek/deepseek-v4-flash** | chosen for speed; model id in `PANTRYOPS_LLM_MODEL`, never hardcoded |
| LLM access | **OpenRouter** (openrouter client lib) | key in `PANTRYOPS_LLM_API_KEY`, base URL `PANTRYOPS_LLM_BASE_URL` |
| Agent orchestration | **LangGraph + LangSmith** | supersedes the ADR-era custom state machine; LangSmith tracing toggled by `LANGSMITH_TRACING` |

## Superseded decision

Architecture §7 originally chose a custom state machine over LangGraph ("fewer moving parts, deterministic tests"). Overridden by the product owner: LangGraph's stateful graphs + LangSmith observability now carry the 19-agent orchestration.

## Consequences

- **Invariants survive the framework.** LangGraph nodes produce proposals only; the single ledger write path (`services/ledger.py::apply_update()`) is invoked exclusively as a structured tool, and the Auditor remains the last node before any user-facing output. The AST boundary guard from Phase 2 must also cover `agents/` graph code.
- Deterministic agent tests mock the OpenRouter client at the graph boundary; LangSmith tracing stays off in tests (`LANGSMITH_TRACING=false`).
- Vision tests remain fixture-driven; real RF-DETR/SAM3/PaddleOCR-VL inference runs only under `-m integration`.
- Model swaps (e.g. deepseek-v4-flash → another OpenRouter id) are config changes, not code changes.
