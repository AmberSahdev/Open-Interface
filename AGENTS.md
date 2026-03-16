# AGENTS.md

This file gives coding agents the real commands, architecture boundaries, and conventions for this repository.
It is based on the checked-in files and the current implementation, not old assumptions.

## 1) Repo summary
- Project type: Python desktop automation app with Tk / ttkbootstrap UI, screenshot-driven visual prompting, local verification, and multiple LLM providers.
- Main entrypoint: `app/app.py`
- Build script: `build.py`
- Primary source root: `app/`
- Test directory: `tests/`
- Local Python version: `.python-version` -> `3.12.8`
- CI lint workflow: `.github/workflows/pylint.yml`
- Current architecture style: single-step visual agent loop with Prompt System v1

## 2) What the app does today
- Accepts a natural-language user goal in the desktop UI.
- Captures a screenshot with visible rulers / grid.
- Builds a structured prompt for the selected model provider.
- Receives a single next-step JSON action from the model.
- Executes the step locally through the interpreter.
- Optionally performs local post-action verification using before/after screenshots.
- Repeats until the model returns `done`, the request is interrupted, or the runtime stops on failure.

The current system is not a multi-step batch planner. It is a strict single-step closed loop.

## 3) Extra agent rule files found during scan
- `AGENTS.md` at repo root: present (this file)
- `.cursorrules`: not found
- `.cursor/rules/`: not found
- `.github/copilot-instructions.md`: not found
- Do not invent extra Cursor or Copilot rules for this repository.

## 4) Environment setup
From repository root:
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Optional lint dependency:
```bash
python -m pip install pylint
```

Windows activation:
```bash
.venv\Scripts\activate
```

## 5) Run / build / lint / test commands
Run the app:
```bash
python app/app.py
```

Build package:
```bash
python build.py
```

Lint all tracked Python files:
```bash
pylint $(git ls-files '*.py')
```

Lint a single file:
```bash
pylint app/core.py
```

Safe local regression checks commonly used in this repo:
```bash
python tests/prompt_system_regression_check.py
python tests/coordinate_mapping_test.py
python tests/request_runtime_control_check.py
python tests/session_context_red_check.py
python tests/verify_macos_doubleclick.py
python tests/verify_visual_agent_mvp.py
```

Legacy smoke test that boots the GUI:
```bash
python tests/simple_test.py
```

## 6) Command caveats
- `python app/app.py` launches a real GUI.
- The app may need screen recording, accessibility, keyboard, and mouse permissions.
- Do not assume GUI flows are headless-safe.
- `build.py` is an interactive PyInstaller script.
- `build.py` prompts for version confirmation and may prompt about macOS signing / notarization.
- `build.py` runs `pip install -r requirements.txt` inside `setup()`.
- Build output goes to `dist/`.
- Only run packaging verification when the task really requires it.
- There is no checked-in Ruff, Black, isort, mypy, pytest, or unittest config.
- The only checked-in lint workflow uses Pylint.

## 7) Test caveats
- `tests/simple_test.py` is a smoke-style GUI test, not a pure unit test.
- It boots the app and can trigger real UI automation behavior.
- Do not describe `tests/simple_test.py` as CI-safe headless unit coverage.
- The repository now also contains multiple safe local regression scripts for prompting, runtime control, settings, coordinate mapping, and verifier behavior.
- Prefer narrow targeted checks over broad GUI smoke runs.

## 8) Preferred verification strategy
- Docs-only changes: verify the edited markdown file content and structure.
- Prompting changes: run `tests/prompt_system_regression_check.py` and related narrow prompt/runtime checks.
- Coordinate / action execution changes: run `tests/coordinate_mapping_test.py` and related targeted checks.
- Runtime control / request boundary changes: run `tests/request_runtime_control_check.py` and `tests/session_context_red_check.py`.
- GUI/runtime changes: use careful smoke testing only when the task truly requires it, because the app can control the machine.
- Packaging changes: run `python build.py` only if the user explicitly wants packaging validation.
- New tests should avoid real mouse and keyboard control whenever possible.

## 9) Source layout
- `app/app.py` -> top-level app wiring and queue orchestration
- `app/core.py` -> request lifecycle, recursive loop, interruption, local verification integration
- `app/interpreter.py` -> turns model steps into local desktop actions
- `app/verifier.py` -> before/after screenshot-based local step verification
- `app/ui.py` -> Tk / ttkbootstrap UI and settings windows
- `app/llm.py` -> LLM runtime settings sync and stable system context assembly
- `app/models/` -> provider-specific model adapters and model factory
- `app/prompting/` -> Prompt System v1 builders and schema text generation
- `app/agent_memory.py` -> compact action / failure memory used for next-step guidance
- `app/session_store.py` -> SQLite-backed message and execution log persistence
- `app/utils/settings.py` -> settings validation, defaults, persistence helpers
- `app/utils/screen.py` -> screenshot capture, grid prompt image creation, prompt image archival
- `app/resources/context.txt` -> stable non-dynamic system rules
- `tests/` -> targeted regression scripts plus legacy GUI smoke test

## 10) Prompt System v1
The project now has a unified prompt architecture under `app/prompting/`.

The key rule is:
- Model providers must share the same prompt semantics.
- Provider adapters should only differ in message formatting and transport.
- Do not reintroduce provider-specific prompt meaning unless the task explicitly requires it.

Core prompt layers:
- `PromptSystemContext`
- `PromptToolSchema`
- `PromptTaskContext`
- `PromptExecutionTimeline`
- `PromptRecentDetails`
- `PromptVisualContext`
- `PromptOutputContract`

Prompt composition entrypoint:
- `app/prompting/builder.py`

Stable prompt rules source:
- `app/resources/context.txt`

Important prompt boundary:
- Dynamic runtime state must not be pushed back into `context.txt`.
- Do not revert to `context.txt + raw request_data JSON` style prompting.

## 11) Tool schema contract
The model-facing tool contract is now registry-driven.

Source:
- `app/prompting/tool_schema.py`

Key classes:
- `ToolParameterDefinition`
- `ToolDefinition`
- `ToolRegistry`

Rules:
- Register each model-visible tool in the registry.
- Generate the model-visible tool schema from the registry.
- Do not hand-maintain a second free-text list of allowed tools elsewhere.
- If you add a new tool, update both:
  - the tool registry entry
  - the runtime execution path that actually supports the tool

Current default tools include:
- `click`
- `moveTo`
- `dragTo`
- `write`
- `press`
- `scroll`
- `sleep`

## 12) Coordinate contract
This repository now uses a strict ruler-aligned coordinate contract.

Model-facing rule:
- `x_percent` and `y_percent` use the same `0-100` ruler scale shown on the prompt image.
- The model should return ruler values directly, such as `31.5` and `44.2`.
- The model should not divide by `100` itself.

Runtime rule:
- The interpreter converts model `0-100` ruler values into internal `0.0-1.0` normalized values and then maps them to logical screen pixels.

Related files:
- `app/resources/context.txt`
- `app/prompting/tool_schema.py`
- `app/prompting/visual_context.py`
- `app/prompting/output_contract.py`
- `app/interpreter.py`

Important warning:
- Do not reintroduce a mixed `0-1` vs `0-100` prompt contract.
- If you change coordinate behavior, update prompt text, interpreter logic, and coordinate tests together.

## 13) Model / interpreter contract
The app depends on a JSON contract between model adapters and the interpreter.

Do not casually change these keys:
- `steps`
- `done`
- `function`
- `parameters`
- `human_readable_justification`
- `expected_outcome`

Current output rules:
- The runtime is single-step; at most one executable step should be used.
- `done` remains `null` until the request is complete or should stop safely.
- If a task is complete, blocked, or unsafe, return `steps: []` and a short `done` message.

If you edit `interpreter.py`, `model.py`, `openai_computer_use.py`, or prompt output contract code, review the whole chain.

## 14) Request state and history boundaries
Current request-state architecture lives primarily in `app/core.py`.

Important structures:
- `request_context` -> per-request runtime state
- `session_history_snapshot` -> structured session narrative summary at request start
- `step_history` -> authoritative per-request step history used for timeline and recent details
- `agent_memory` -> compact recent action / failure memory

Rules:
- Do not collapse `session_history_snapshot` and `step_history` back into one raw prompt blob.
- Preserve request boundary markers like `request_origin`.
- Keep interruption / restart behavior intact when editing request flow.

## 15) Prompt dump debugging
Prompt text dump support exists and is intentionally optional.

Settings key:
- `advanced.save_prompt_text_dumps`

Behavior:
- Default is `False`.
- When enabled, final prompt text is written under project-root `promptdump/`.
- Dumped text contains prompt content, not API credentials.

Related files:
- `app/prompting/debug.py`
- `app/utils/settings.py`
- `app/ui.py`

## 16) Import guidelines
- Match the existing import style.
- Prefer absolute imports rooted at the current app layout.
- Existing examples:
  - `from core import Core`
  - `from ui import UI`
  - `from utils.settings import Settings`
  - `from models.factory import ModelFactory`
- Do not introduce wildcard imports.
- Keep import groups ordered as: standard library, third-party, local project imports.
- Keep one import per line unless the surrounding file already uses a compact local pattern.

## 17) Formatting guidelines
- Use 4 spaces for indentation.
- Preserve the repository's current style; no formatter config is checked in.
- Keep code explicit and readable.
- Avoid clever one-liners and unnecessary abstraction.
- Prefer direct conditionals over dense expressions.
- Match surrounding quote style; default to single quotes when no nearby style dominates.
- Preserve helpful blank lines between logical sections.

## 18) Type guidelines
- New and modified code should continue the existing use of Python type hints.
- Add parameter and return annotations for new functions.
- Prefer simple concrete types such as `str`, `dict[str, Any]`, and `list[str]`.
- Use `Optional[...]` only when `None` is actually part of the contract.
- Avoid overly complex typing machinery.
- Mirror nearby annotation style when editing an existing module.

## 19) Naming guidelines
- Classes: `PascalCase`
- Functions and methods: `snake_case`
- Variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Use descriptive names; avoid vague names like `tmp`, `data2`, or `stuff`.
- Examples already in use: `App`, `Core`, `Interpreter`, `ModelFactory`, `PromptPackage`, `ToolRegistry`, `execute_user_request`.

## 20) Error handling guidelines
- Prefer specific exceptions when practical.
- Broad `except Exception as e` is acceptable only when useful context is logged or surfaced.
- Do not silently swallow failures.
- Include enough context to identify the failing step, file, JSON payload, or model response.
- For background/UI flows, favor reporting through status messages or logs.
- Existing patterns:
  - `core.py` sends startup/runtime failures to `status_queue`
  - `interpreter.py` prints failing command JSON and extracted parameters
  - `ui.py` guards cross-thread UI updates via queue-based messaging

## 21) Threading and UI safety
- Tk widget updates should stay on the main thread.
- Reuse the queue-based communication pattern already present in `UI.MainWindow`.
- Do not directly mutate Tk widgets from worker threads when the queue path already exists.
- Preserve daemon-thread behavior unless there is a strong reason to change shutdown semantics.

## 22) Settings, paths, and secrets
- Persistent settings live under `~/.open-interface/`.
- Use `Settings` from `app/utils/settings.py` instead of adding ad hoc config files.
- Prefer `Path(__file__).resolve().parent` for repo-local resources.
- Reuse the existing `resources/` lookup patterns.
- Never commit API keys or secrets.
- Respect `.gitignore` entries such as `secrets/`, `*/secret.py`, `dist/`, and build artifacts.
- Base64-encoded API keys are still secrets.

## 23) Dependency and change policy
- Prefer the current dependency set in `requirements.txt`.
- Do not add packages without a clear need.
- If a new dependency is necessary, document why and keep the change minimal.
- Prefer small, localized edits over broad refactors.
- Preserve backward-compatible behavior in desktop automation code unless the user explicitly approves a contract change.
- When unsure, optimize for safety, explicitness, reversibility, and verifiability.
