# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
├── api/           # REST API routes
├── services/      # Business logic
├── executors/     # Task execution (RunExecutor, ADBExecutor)
├── faults/        # Fault injection plugins
├── validators/    # Post-upgrade validators
├── parsers/       # Log parsers (recovery, update_engine, logcat)
├── diagnosis/     # TraceLens diagnostic engine
├── reporting/     # Report generation
├── models/        # SQLAlchemy models
├── cli/           # Typer CLI commands
└── templates/     # Jinja2 templates
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

- `app/main.py` - FastAPI app entry
- `app/cli/main.py` - CLI entry point
- `app/executors/run_executor.py` - Main task executor
- `app/diagnosis/engine.py` - Diagnostic rule engine
- `app/rules/core_rules.yaml` - Diagnostic rules

## Testing

```bash
# All tests
pytest

# With coverage
pytest --cov=app

# Specific test file
pytest tests/test_executors/test_run_executor.py -v
```
