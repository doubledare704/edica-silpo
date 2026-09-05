# Universal Coding Agent Guidelines

## 🛠️ Stack & Runtime Constraints
- **Language & Runtime:** Python 3.12+ (використовувати `typing.override`, `type` statements, нові фічі типізації, вбудовані дженеріки `dict`, `list`, `X | None` замість `typing.Dict`, `typing.List`, `typing.Optional`).
- **Package Manager:** `uv` is the required package manager for installs, lockfile sync, and all project commands.
- **Formatting & Linting:** Use `ruff format` for formatting and `ruff check` for linting; use `pyrefly` for static type / import validation where applicable.
- **Frontend:** SvelteKit (Svelte 5) + Tailwind CSS + Web Audio API.
- **MCP Client:** Виключно опублікований пакет `silpo-py-mcp` (режим `mock_mode=True` за замовчуванням).
- **Voice TTS:** Respeecher API (з можливістю вимкнення та мокування через конфіг).
- **Architecture Principles:** Strict SOLID, KISS, YAGNI.

## 🔄 Back-Driven Execution Protocol
1. **Never Invent Architecture:** Заборонено додавати нові ноди, ендпоінти чи поля в `AgentState` поза специфікацією в `.docs/TECH_SPEC.md`.
2. **Task State Discipline:** Перед виконанням роботи обов'язково прочитай `.docs/TASKS.md`. Обирай ТІЛЬКИ одну першу невиконану задачу `[ ]`.
3. **TDD First:** Спочатку створи юніт-тест для задачі у `backend/tests/`, перевір його падіння, і лише потім напиши мінімальний код реалізації.
4. **State Update & Stop:** Після успішного проходження тесту зміни статус задачі в `.docs/TASKS.md` на `[x]` і ЗУПИНИСЬ для рев'ю користувачем.
5. **Project Management Discipline:** Keep the task board in `.docs/TASKS.md` current. Before work begins, mark the selected task as in-progress in the local workflow if used; after completion, update the task as done and summarize any blockers or follow-ups.
6. **Validation Gate:** Before declaring work complete, run the relevant project checks through `uv` and the repo's formatter/linter tools, such as `uv run ruff format --check .`, `uv run ruff check .`, and `uv run pyrefly check` when the project is configured for it.

## 🏗️ Code Quality Guardrails
- **Modern Typing:** Суворо використовувати вбудовані дженеріки (`dict`, `list`, `set`, `tuple`) та union синтаксис `X | None` / `X | Y` замість `typing.Dict`, `typing.List`, `typing.Optional`, `typing.Union`.
- **Enums:** Усі ноди (`NodeName`) та інтенти (`IntentEnum`) реалізовувати суворо через `StrEnum`.
- **Comments:** Не використовуй коментарі по коду занадто часто, код має бути самоописуючий, назви змінних і функцій описують що вони виконують і не вимагають додаткового пояснення.
- **FastAPI SSE:** Використовувати нативний `StreamingResponse` (`media_type="text/event-stream"`) без додаткових сторонніх бібліотек.
- **Checkpoints:** Використовувати `MemorySaver` із `configurable: {"thread_id": ...}` для збереження контексту чату.
- **Tooling Rule:** Do not use bare `pip install` or ad hoc global Python tooling for repo work. Use `uv`-managed commands and project-local dependencies only.
- **Formatting Rule:** Run the formatter before final validation; keep code style consistent and avoid manual drift from the repo defaults.
- **Lint & Type Rule:** Treat `ruff` and `pyrefly` as required verification steps for Python code quality, not optional extras.

### NO GLOBAL VARIABLES OR `global` KEYWORD
* **Strictly Prohibited:** Never use the `global` keyword or mutable module-level state (`_VAR = None`).
* **Why:** Global state creates race conditions, breaks async safety, hinders parallel test execution, and hides dependencies.

#### Approved Alternatives:
1. **Caching/Singletons:** Use `@functools.lru_cache(maxsize=1)` for lazy singletons, and reset using `.cache_clear()` in tests.
2. **Dependency Injection:** Wrap stateful nodes/handlers inside classes or factory closures. Pass dependencies via initializers or function arguments.
3. **Application State:** Store dynamic state in request/graph contexts (e.g., LangGraph `State`, FastAPI `app.state`, or `ContextVar`).

#### Mandatory Linter Rule:
* Enable Ruff rule `PLW0603` (`global-statement`) in `pyproject.toml`. All generated code must pass this check.

## 🧩 Project Management Expectations
- Maintain a single active task at a time unless explicitly instructed otherwise.
- Prefer small, reviewable changes and make task status updates in `.docs/TASKS.md` alongside the implementation.
- If a task requires external clarification or blocked dependencies, record the blocker in the task notes and continue only with explicit approval when necessary.
- Keep architecture, implementation, and tasks aligned with `.docs/TECH_SPEC.md` and `.docs/PRD.md`.

