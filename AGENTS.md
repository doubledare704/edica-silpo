# Universal Coding Agent Guidelines

## 🛠️ Stack & Runtime Constraints
- **Language & Runtime:** Python 3.12+ (використовувати `typing.override`, `type` statements, нові фічі типізації).
- **Package Manager:** `uv` (FastAPI, LangGraph, Pydantic v2).
- **Frontend:** SvelteKit (Svelte 5) + Tailwind CSS + Web Audio API.
- **MCP Client:** Виключно опублікований пакет `silpo-py-mcp` (режим `mock_mode=True` за замовчуванням).
- **Voice TTS:** Respeecher API (з можливістю вимкнення та мокування через конфіг).
- **Architecture Principles:** Strict SOLID, KISS, YAGNI.

## 🔄 Back-Driven Execution Protocol
1. **Never Invent Architecture:** Заборонено додавати нові ноди, ендпоінти чи поля в `AgentState` поза специфікацією в `.docs/TECH_SPEC.md`.
2. **Task State Discipline:** Перед виконанням роботи обов'язково прочитай `.docs/TASKS.md`. Обирай ТІЛЬКИ одну першу невиконану задачу `[ ]`.
3. **TDD First:** Спочатку створи юніт-тест для задачі у `backend/tests/`, перевір його падіння, і лише потім напиши мінімальний код реалізації.
4. **State Update & Stop:** Після успішного проходження тесту зміни статус задачі в `.docs/TASKS.md` на `[x]` і ЗУПИНИСЬ для рев'ю користувачем.

## 🏗️ Code Quality Guardrails
- **Enums:** Усі ноди (`NodeName`) та інтенти (`IntentEnum`) реалізовувати суворо через `StrEnum`.
- **FastAPI SSE:** Використовувати нативний `StreamingResponse` (`media_type="text/event-stream"`) без додаткових сторонніх бібліотек.
- **Checkpoints:** Використовувати `MemorySaver` із `configurable: {"thread_id": ...}` для збереження контексту чату.

