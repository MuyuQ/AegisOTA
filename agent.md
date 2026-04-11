# agent.md

This file provides guidance to a coding agent working in this repository.

## Project Summary

AegisOTA is an Android OTA upgrade exception injection and multi-device verification platform.

The repository combines:

- A FastAPI control plane for API and web pages
- A Typer-based CLI entrypoint exposed as `labctl`
- A worker/executor layer for OTA task orchestration
- Fault injection plugins, validators, parsers, diagnosis, and reporting

## Tech Stack

- Python 3.10+
- FastAPI
- SQLAlchemy 2.0
- SQLite
- Typer
- Jinja2 + HTMX
- Pytest
- Ruff
- uv

## Repo Map

```text
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

## Core Domain Concepts

- Run status flow: `queued -> allocating -> reserved -> running -> validating -> passed|failed|aborted`
- Execution stages: `precheck -> package_prepare -> apply_update -> reboot_wait -> post_validate`
- Device pools: `stable`, `stress`, `emergency`
- Fault plugins typically implement `prepare()`, `inject()`, `cleanup()`
- Diagnosis is rule-driven and uses parsers plus similarity lookup

## Important Files

- `app/main.py`: app wiring, middleware, router registration, static/templates
- `app/config.py`: environment-driven settings with `AEGISOTA_` prefix
- `app/executors/run_executor.py`: main OTA execution flow
- `app/executors/step_handlers.py`: per-stage logic
- `app/services/run_service.py`: run lifecycle orchestration
- `app/services/scheduler_service.py`: queueing and scheduling behavior
- `app/services/preemption_service.py`: device preemption logic
- `app/diagnosis/engine.py`: diagnosis rule engine
- `app/reporting/generator.py`: report generation
- `app/rules/core_rules.yaml`: built-in diagnosis rules

## Local Commands

```bash
# Install
uv pip install -e ".[dev]"

# Run app
uvicorn app.main:app --reload

# CLI help
labctl --help

# Tests
pytest
pytest --cov=app

# Lint / format
ruff check app tests
ruff format app tests

# Database migration
alembic upgrade head
```

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

## Read First For Common Tasks

- New API or page flow: `app/main.py`, `app/api/`, `app/services/`
- OTA execution changes: `app/executors/`, `app/faults/`, `app/validators/`
- Diagnosis changes: `app/parsers/`, `app/diagnosis/`, `app/rules/core_rules.yaml`
- Report/export changes: `app/reporting/`, `app/services/report_service.py`, `app/services/log_export_service.py`
