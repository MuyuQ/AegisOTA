# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

AegisOTA is an Android OTA upgrade exception injection and multi-device verification platform.

## Technology Stack

- **Language:** Python 3.10+
- **Web Framework:** FastAPI
- **Database:** SQLite + SQLAlchemy 2.0
- **CLI:** Typer
- **Frontend:** Jinja2 + HTMX
- **Package Manager:** uv

## Quick Commands

```bash
# Run tests
pytest

# Format code
ruff format app/

# Lint code
ruff check app/

# Start dev server
uvicorn app.main:app --reload

# CLI
labctl --help
```

## Architecture

```
app/
├── api/            # REST API and web routes
├── cli/            # labctl CLI commands
├── services/       # business logic
├── executors/      # run execution, ADB wrapper, command runners
├── faults/         # fault injection plugins
├── validators/     # post-upgrade validators and state checks
├── parsers/        # log parsers
├── diagnosis/      # rule engine, confidence, similar-case lookup
├── reporting/      # report generation and failure classification
├── models/         # SQLAlchemy models and enums
├── templates/      # Jinja2 pages
├── static/         # CSS/static assets
├── rules/          # diagnosis rules
├── utils/          # logging and transaction helpers
├── config.py       # settings, env loading, directory bootstrapping
├── database.py     # DB init/session setup
└── main.py         # FastAPI app entry
tests/
docs/
artifacts/
ota_packages/
```

## Core Concepts

### State Machines

**Task States:** `queued -> allocating -> reserved -> running -> validating -> passed/failed/aborted`

**Execution Stages:** `precheck -> package_prepare -> apply_update -> reboot_wait -> post_validate`

### Device Pools

- **stable**: Stable testing pool
- **stress**: Stress testing pool  
- **emergency**: Emergency pool with preemption capability

### Fault Injection

Plugins implement `prepare()`, `inject()`, `cleanup()` methods.

Built-in faults: `low_battery`, `storage_pressure`, `download_interrupted`, `reboot_interrupted`, `monkey_after_upgrade`, etc.

### Diagnosis (TraceLens)

- Log parsers: `recovery`, `update_engine`, `logcat`, `monkey`
- Rule-based diagnostic engine
- Similar case retrieval using RapidFuzz

## Key Files

- `app/main.py` - app wiring, middleware, router registration, static/templates
- `app/config.py` - environment-driven settings with `AEGISOTA_` prefix
- `app/executors/run_executor.py` - main OTA execution flow
- `app/executors/step_handlers.py` - per-stage logic
- `app/services/run_service.py` - run lifecycle orchestration
- `app/services/scheduler_service.py` - queueing and scheduling behavior
- `app/services/preemption_service.py` - device preemption logic
- `app/diagnosis/engine.py` - diagnosis rule engine
- `app/reporting/generator.py` - report generation
- `app/rules/core_rules.yaml` - built-in diagnosis rules

## Working Rules

- Default to small, local changes that preserve the existing layering: `api -> services -> executors/models/utils`.
- Prefer modifying service logic before pushing business rules into route handlers.
- Keep naming consistent with the repo: `snake_case` for modules/functions, `PascalCase` for classes.
- Use type hints for new Python code.
- Prefer Chinese docstrings and user-facing text to match the existing codebase and docs.
- Do not bypass `app.config.Settings`; new runtime config should usually be added there with the `AEGISOTA_` prefix model.
- Do not write task outputs to arbitrary paths; use `artifacts/` and existing report/log export flows.
- When changing models or persistence behavior, check whether migrations and tests need to be updated together.
- When changing web write actions, keep CSRF behavior in mind.
- When changing `/api/*` behavior, keep API key middleware expectations in mind.

## Change-Specific Guidance

### Adding an API endpoint

- Put request/response models in `app/api/schemas.py` when appropriate.
- Keep route handlers thin and push logic into a service.
- Add or update API tests under `tests/test_api/`.

### Adding a fault plugin

- Add the implementation in `app/faults/`.
- Register it in `app/faults/__init__.py` if registration is required there.
- Add focused tests under `tests/test_faults/`.
- If the plugin affects execution stages, verify the executor/state-machine tests still reflect the flow.

### Adding a validator or parser

- Place it under `app/validators/` or `app/parsers/`.
- Keep return types and failure messages structured and testable.
- Add focused tests under `tests/test_validators/` or adjacent suites.

### Changing scheduling or worker behavior

- Review `run_service`, `scheduler_service`, `worker_service`, and `preemption_service` together.
- Be careful with state transitions and lease lifecycle consistency.
- Prefer adding regression tests before or alongside the change.

### Changing diagnosis/reporting

- Keep rule files, parser output, classifier logic, and report rendering aligned.
- Update fixtures/tests for realistic logs when behavior changes.

## Testing

```bash
# All tests
pytest

# With coverage
pytest --cov=app

# Specific test file
pytest tests/test_executors/test_run_executor.py -v
```

## Validation Checklist

Before finishing a change, run the smallest relevant test set first, then broaden if needed.

- `pytest tests/test_api/` for API changes
- `pytest tests/test_services/` for service/scheduling changes
- `pytest tests/test_executors/` for OTA flow changes
- `pytest tests/test_faults/` for fault plugin changes
- `pytest tests/test_validators/` for validator/state changes
- `ruff check app tests`

Run full `pytest` when the change crosses module boundaries.

## Practical Notes

- `app/config.py` creates `artifacts/` and OTA package directories on settings initialization; avoid duplicating that setup elsewhere.
- API key auth is only applied to `/api/*` and depends on configured keys; web routes are intentionally looser.
- The repo may contain a local SQLite database file (`aegisota.db`); do not rely on committed DB state for correctness.
- There are user changes in the worktree at times; avoid reverting unrelated files.
