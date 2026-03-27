# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AegisOTA is an Android OTA upgrade exception injection and multi-device verification platform. It orchestrates upgrade testing workflows with fault injection capabilities, designed for test development scenarios.

## Technology Stack

- **Language:** Python
- **Web Framework:** FastAPI
- **Database:** SQLite + SQLAlchemy
- **CLI:** Typer
- **Frontend:** Jinja2 + HTMX (lightweight, no SPA framework)

## Architecture

The system uses a "Control Plane + Execution Plane" architecture:

```
Control Plane (FastAPI)
├── Device Management API
├── Task Management API
├── Report API
└── Web Console (Jinja2 + HTMX)

Execution Plane (Typer CLI + Worker)
├── ADB/Fastboot Commands
├── Monkey Testing
└── Log Collection

Data Layer (SQLite)
└── Core Entities
```

## Directory Structure (Planned)

```
app/
├── api/           # FastAPI endpoints
├── models/        # SQLAlchemy models
├── services/      # Business logic (shared by CLI and API)
├── executors/     # Command execution abstraction
├── faults/        # Fault injection plugins
├── validators/    # Post-upgrade validation
├── reporting/     # Report generation
├── templates/     # Jinja2 templates
├── static/        # Static files
├── cli/           # Typer CLI commands
tests/
artifacts/         # Execution outputs (logs, reports)
```

## Core Data Models

| Model | Description |
|-------|-------------|
| `Device` | Device inventory with status, health, tags |
| `DeviceLease` | Device reservation for exclusive task access |
| `UpgradePlan` | Task templates with upgrade type, fault profiles |
| `FaultProfile` | Exception injection configurations |
| `RunSession` | Task execution sessions |
| `RunStep` | Individual step execution records |
| `Artifact` | Logs, screenshots, evidence files |
| `Report` | Generated reports with failure attribution |

## State Machines

### Task States
`queued -> reserved -> running -> validating -> passed/failed/aborted/quarantined`

### Device States
`idle, busy, offline, quarantined, recovering`

### Execution Stages
`precheck -> push_package -> apply_update -> reboot_wait -> post_validate`

## Key Design Principles

1. **Single-device exclusivity:** One device can only run one task at a time
2. **State machine driven:** All tasks follow defined state transitions
3. **Structured evidence:** All execution outputs captured as structured data
4. **Fault injection as plugins:** Fault profiles inject at precheck, apply_update, post_validate stages
5. **Automatic quarantine:** Devices with failures automatically isolated
6. **CLI and API share logic:** Both use the same service layer, no duplication
7. **Command abstraction:** All shell commands use CommandRunner, never direct subprocess calls
8. **Idempotent transitions:** State changes must be safe to retry
9. **Timeout support:** All stages must support configurable timeouts

## API Endpoints

- `POST /api/runs` - Create upgrade task
- `GET /api/runs/{id}` - Query task details and stage status
- `POST /api/runs/{id}/abort` - Terminate task
- `GET /api/devices` - List devices with status, tags, health
- `POST /api/devices/{id}/quarantine` - Isolate abnormal device
- `POST /api/devices/{id}/recover` - Recover quarantined device
- `GET /api/reports/{id}` - Return report summary and evidence chain

## CLI Commands

- `labctl device sync` - Scan and update online devices
- `labctl device list` - List devices
- `labctl run submit` - Submit upgrade task
- `labctl run execute` - Execute task on specific device (worker mode)
- `labctl run abort` - Abort running task
- `labctl report export` - Export Markdown/HTML report
- `labctl device recover` - Handle failed device recovery

## Fault Injection Plugin Interface

```python
class FaultPlugin:
    def prepare(self, context: RunContext) -> None: ...
    def inject(self, context: RunContext) -> None: ...
    def cleanup(self, context: RunContext) -> None: ...
```

Trigger points: `precheck`, `apply_update`, `post_validate`

## Core Fault Scenarios

- `storage_pressure` - Fill `/data/local/tmp` to simulate low space
- `download_interrupted` - Simulate package fetch failure
- `reboot_interrupted` - Timeout or disconnect during reboot wait
- `post_boot_watchdog_like_failure` - Detect boot failures, key process issues
- `monkey_after_upgrade` - Stability stress test post-upgrade

## Failure Classification

`package_issue, device_env_issue, boot_failure, validation_failure, monkey_instability, performance_suspect, adb_transport_issue, unknown`

## Testing Requirements

- Unit tests: state machine transitions, fault profile validation, failure classification, device lease contention
- Integration tests: mock adb/fastboot/subprocess for full pipeline
- End-to-end: normal upgrade, rollback on failure, monkey post-upgrade, device quarantine

## Project Boundaries (Not Implemented)

- No Android kernel modifications
- No OTA package generation system
- No complex frontend (SPA framework)
- No distributed scheduling (Redis/Celery)
- No complex authentication/permissions