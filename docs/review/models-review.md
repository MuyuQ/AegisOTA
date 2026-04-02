# Models Module Review Report

## Overview

The Models module defines SQLAlchemy ORM models for the AegisOTA platform. Five files were reviewed: `device.py`, `run.py`, `fault.py`, `artifact.py`, and `__init__.py`.

---

## Strengths

### 1. Clean Enum-Based State Machines
All state enumerations inherit from `str, Enum` which provides:
- String serialization for database storage
- Type safety in Python code
- Clean API responses (JSON serialization works automatically)

**Files:** `device.py:22-38`, `run.py:25-77`, `fault.py:14-33`

### 2. Proper SQLAlchemy 2.0 Style
Models use modern SQLAlchemy 2.0 conventions:
- `Mapped[]` type annotations throughout
- `mapped_column()` instead of legacy `Column()`
- Consistent use of `server_default=func.now()` for timestamps

### 3. JSON Helper Methods
Models with JSON fields include well-designed accessor methods:
- `get_tags()` / `set_tags()` in `Device` (`device.py:85-96`)
- `get_parameters()` / `set_parameters()` in `FaultProfile` (`fault.py:74-85`)
- `get_metadata()` / `set_metadata()` in `Artifact` (`artifact.py:64-75`)
- All include proper `JSONDecodeError` handling returning empty dict

### 4. Appropriate Cascade Strategies
Relationship cascades are well-designed:
- `Device -> DeviceLease`: `cascade="all, delete-orphan"` (device deletion removes leases)
- `RunSession -> RunStep`: `cascade="all, delete-orphan"` (run deletion removes steps)
- `RunSession -> Artifact`: `cascade="all, delete-orphan"` (run deletion removes artifacts)
- `UpgradePlan -> RunSession`: `cascade="all, delete-orphan"` (plan deletion removes runs)

### 5. Proper Foreign Key onDelete Actions
- `DeviceLease.device_id`: `ondelete="CASCADE"` (`device.py:110`)
- `DeviceLease.run_id`: `ondelete="SET NULL"` (`device.py:113`) - allows orphaned leases
- `RunSession.plan_id`: `ondelete="SET NULL"` (`run.py:155`) - allows orphaned runs
- `Artifact.run_id`: `ondelete="CASCADE"` (`artifact.py:37`) - proper cleanup

### 6. Good Index Coverage
Critical fields are properly indexed:
- `Device.serial`: unique + index (`device.py:46`)
- `Device.status`: index (`device.py:56`)
- `DeviceLease.device_id`, `run_id`: indexed (`device.py:110, 113`)
- `RunSession.plan_id`, `device_id`: indexed (`run.py:155, 158`)
- `RunStep.run_id`: indexed (`run.py:250`)
- `Artifact.run_id`: indexed (`artifact.py:37`)
- `FaultProfile.name`, `fault_stage`, `fault_type`: indexed (`fault.py:44, 48, 51`)

### 7. Terminal State Detection Method
`RunSession.is_terminal_state()` (`run.py:217-224`) correctly identifies final states for workflow logic.

---

## Issues

### Critical Issues

#### 1. Missing `Report` Database Model
**Spec Reference:** CLAUDE.md line 67 lists `Report` as a core data model.

**Location:** Entire models module

**Problem:** The spec explicitly lists `Report` as a model ("Generated reports with failure attribution"), but no `Report` SQLAlchemy model exists. Only `ReportData` dataclass in `app/reporting/generator.py` which generates transient files without database persistence.

**Impact:**
- Reports cannot be queried via API (endpoint `/api/reports/{id}` would have no backing data)
- No historical report tracking
- No evidence chain persistence

#### 2. Orphaned Foreign Key Field
**Location:** `device.py:75`

```python
current_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
```

**Problem:** This is a plain `Integer` without `ForeignKey("run_sessions.id")`. It should be a proper foreign key relationship for:
- Data integrity
- Join queries
- Automatic nulling on run deletion

#### 3. Missing Foreign Key for validation_profile_id
**Location:** `run.py:103`

```python
validation_profile_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
```

**Problem:** No `ValidationProfile` model exists, and this field lacks a foreign key. Either:
- Create a `ValidationProfile` model
- Remove this field if validation is embedded elsewhere
- Document this as a placeholder

#### 4. StepName Enum Mismatch with Spec
**Spec Reference:** CLAUDE.md line 77: `precheck -> push_package -> apply_update -> reboot_wait -> post_validate`

**Location:** `run.py:46-55`

```python
class StepName(str, Enum):
    PRECHECK = "precheck"
    PACKAGE_PREPARE = "package_prepare"  # Spec says "push_package"
    APPLY_UPDATE = "apply_update"
    REBOOT_WAIT = "reboot_wait"
    POST_VALIDATE = "post_validate"
    REPORT_FINALIZE = "report_finalize"  # Not in spec
```

**Problem:** `PACKAGE_PREPARE` value differs from spec's `push_package`. Additionally, `REPORT_FINALIZE` is not documented in the spec's execution stages.

---

### Moderate Issues

#### 5. Missing Unique Constraint on FaultProfile.name
**Location:** `fault.py:44`

```python
name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
```

**Problem:** Fault profile names should likely be unique to prevent confusion. Currently only indexed, not unique.

#### 6. Missing Index on lease_status
**Location:** `device.py:124-126`

```python
lease_status: Mapped[LeaseStatus] = mapped_column(
    String(32), default=LeaseStatus.ACTIVE, nullable=False
)
```

**Problem:** Queries filtering by lease status (e.g., find all active leases) would benefit from an index.

#### 7. Missing Index on RunStep.status
**Location:** `run.py:256-258`

```python
status: Mapped[StepStatus] = mapped_column(
    String(32), default=StepStatus.PENDING, nullable=False
)
```

**Problem:** Finding pending/failed steps across runs would benefit from an index.

#### 8. Boolean Field Stored as Integer
**Location:** `fault.py:58`

```python
enabled: Mapped[bool] = mapped_column(Integer, default=True, nullable=False)
```

**Problem:** SQLAlchemy `Boolean` type maps to `Integer` for SQLite automatically. Explicitly using `Integer` with `Mapped[bool]` is unconventional and could cause confusion. Should use `Boolean` type explicitly for clarity.

#### 9. Inconsistent Enum Type Annotation for ArtifactType
**Location:** `artifact.py:44`

```python
artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
```

**Problem:** `ArtifactType` enum exists but field is typed as `Mapped[str]` instead of `Mapped[ArtifactType]`. Should match pattern used elsewhere.

#### 10. Missing Back-Populates for RunStep -> Artifacts
**Location:** `run.py` and `artifact.py`

**Problem:** `Artifact` has `step_id` foreign key and relationship to `RunStep`, but `RunStep` model has no corresponding `artifacts` relationship with `back_populates`.

#### 11. Missing Self-Referential Relationship for parent_run_id
**Location:** `run.py:179-181`

**Problem:** Foreign key exists but no relationship defined for accessing child runs.

#### 12. Device.is_available() Missing Lease Check
**Location:** `device.py:98-100`

```python
def is_available(self) -> bool:
    return self.status == DeviceStatus.IDLE
```

**Problem:** Per spec principle "Single-device exclusivity", this method only checks status but doesn't verify there's no active lease.

#### 13. datetime.utcnow() Deprecated
**Location:** `device.py:138`

```python
if self.expired_at and datetime.utcnow() > self.expired_at:
```

**Problem:** `datetime.utcnow()` is deprecated in Python 3.12+. Should use `datetime.now(timezone.utc)`.

#### 14. Missing FailureCategory Index
**Location:** `run.py:166-168`

**Problem:** Queries grouping/counting failures by category would benefit from an index.

---

### Minor Issues

#### 15. Missing Composite Index for RunStep (run_id, step_name)
**Location:** `run.py:249-253`

**Problem:** A composite index `(run_id, step_name)` would be more efficient for looking up specific steps.

#### 16. Missing Composite Index for DeviceLease (device_id, lease_status)
**Location:** `device.py:109-126`

**Problem:** Finding active leases for a device would benefit from a composite index.

#### 17. No state_transition Validation Methods
**Location:** All state machine models

**Problem:** No methods to validate valid state transitions.

#### 18. Missing run_options Index Pattern Documentation
**Location:** `run.py:172`

**Problem:** `run_options` is JSON text but has no documented schema.

---

## Recommendations

### High Priority

1. **Create `Report` Model** - Add a persistent Report model
2. **Fix `Device.current_run_id`** - Add proper ForeignKey
3. **Add State Transition Validation** - Implement `can_transition_to()` methods
4. **Create `ValidationProfile` Model** or remove the orphaned field
5. **Align `StepName.PACKAGE_PREPARE` with spec** - Rename to `push_package`

### Medium Priority

6. Add `unique=True` to `FaultProfile.name`
7. Add `ArtifactType` enum type annotation to `artifact_type` field
8. Add bidirectional relationship for `RunStep.artifacts`
9. Add self-referential relationship for `RunSession.parent_run_id`
10. Enhance `Device.is_available()` to check for active leases
11. Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`
12. Add index on `DeviceLease.lease_status`
13. Add index on `RunStep.status`
14. Add index on `RunSession.failure_category`

### Low Priority

15. Add composite indexes for common query patterns
16. Use `Boolean` type explicitly in `FaultProfile.enabled`
17. Add `get_run_options()` / `set_run_options()` methods for consistency

---

## File Reference Summary

| File | Path | Lines |
|------|------|-------|
| device.py | `E:\git_repositories\AegisOTA\app\models\device.py` | 140 |
| run.py | `E:\git_repositories\AegisOTA\app\models\run.py` | 297 |
| fault.py | `E:\git_repositories\AegisOTA\app\models\fault.py` | 85 |
| artifact.py | `E:\git_repositories\AegisOTA\app\models\artifact.py` | 75 |
| __init__.py | `E:\git_repositories\AegisOTA\app\models\__init__.py` | 39 |