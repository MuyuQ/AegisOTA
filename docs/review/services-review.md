# Services Module Review Report

## Overview

The Services module contains four service classes that handle core business logic for device management, run/task execution, scheduling, and worker orchestration.

---

## Strengths

1. **Clean Service Architecture Pattern** - Services correctly encapsulate business logic and accept `Session` dependency injection
2. **Proper Separation from API Layer** - API routes correctly delegate to services
3. **Well-Defined State Enums** - `DeviceStatus` and `RunStatus` enums provide clear state definitions
4. **Device Health Score Logic** - Reasonable health scoring with battery and boot status factors
5. **Lease Expiration Cleanup** - Properly handles stale leases with cascading state updates

---

## Issues

### Critical Issues

#### 1. Race Condition in Device Lease Acquisition
**File:** `scheduler_service.py:23-64`

The `acquire_device_lease` method has a classic TOCTOU race condition:
```python
# Lines 36-37: Check device status
if device.status != DeviceStatus.IDLE:
    return None

# Lines 40-46: Check active lease (separate query)
active_lease = self.db.query(DeviceLease).filter(...)

# Lines 57-62: Update device and add lease (no locking)
device.status = DeviceStatus.BUSY
self.db.add(lease)
self.db.commit()
```

**Impact:** Multiple workers could pass the status check simultaneously, leading to:
- Two runs acquiring the same device
- Device state corruption

**Recommendation:** Use SELECT FOR UPDATE or database-level advisory locks.

---

#### 2. Missing Transaction Rollback on Errors
**Files:** `device_service.py`, `run_service.py`, `scheduler_service.py`

No service methods use try/except with rollback patterns. If an exception occurs mid-operation, partial state may be committed or transaction may hang.

**Recommendation:** Wrap multi-operation methods in try/except blocks with explicit rollback.

---

#### 3. Inconsistent State Transition Enforcement
**File:** `run_service.py:130-150`

`abort_run_session` has partial state validation but `update_run_status` (lines 89-106) has NO state transition validation - allows arbitrary status changes like QUEUED -> PASSED.

**Recommendation:** Implement a state transition validation method.

---

#### 4. Lease Contention Not Handled with Retry/Backoff
**File:** `scheduler_service.py:136-160`

`reserve_run` simply returns False on lease failure without retry or alternative device selection.

**Recommendation:** Implement retry with exponential backoff.

---

### Medium Issues

#### 5. No Exception Handling in Worker Loop
**File:** `worker_service.py:76-84`
- Uses `print()` instead of proper logging
- Exception details are lost
- No distinction between transient vs permanent failures

#### 6. Database Session Not Scoped Per Operation in Worker
**File:** `worker_service.py:101-184`

Single shared `self.db` session spans too many operations. If any operation fails and partially commits, subsequent operations may work with stale/inconsistent data.

#### 7. String Literals for Lease Status Instead of Enum
**File:** `scheduler_service.py:42, 75, 174`

Uses `"active"` string instead of `LeaseStatus.ACTIVE` enum.

#### 8. Device Status Check After Lease Release
**File:** `scheduler_service.py:84-91`

If device was quarantined during the run, releasing the lease incorrectly sets it back to IDLE, bypassing quarantine.

#### 9. Missing Validation in create_run_session
**File:** `run_service.py:62-83`

No check that `plan_id` references an existing `UpgradePlan`.

---

### CLI vs Service Layer Duplication

| CLI File | Line | Issue |
|----------|------|-------|
| `cli/device.py` | 169-181 | `quarantine_device` CLI directly modifies status |
| `cli/device.py` | 201-213 | `recover_device` CLI bypasses health checks |
| `cli/run.py` | 57-68 | `submit_run` CLI creates RunSession directly |
| `cli/run.py` | 180-186 | `abort_run` CLI modifies status directly |

**Impact:** CLI recovery skips health checks that API performs. Business logic drift between CLI and API paths.

---

## Missing Functionality

1. No Device Lease Renewal mechanism
2. No Run Priority Queue support
3. No Concurrent Execution Per Device check (beyond leases)
4. No Audit Trail for state transitions
5. No Bulk Operations support
6. No Run Retry Logic
7. Missing Heartbeat Mechanism for stuck execution detection

---

## Recommendations Summary

| Priority | Issue | Recommendation |
|----------|-------|----------------|
| Critical | Race condition in lease acquisition | Use database locking (SELECT FOR UPDATE) |
| Critical | Missing transaction rollback | Add try/except/rollback patterns |
| Critical | State transition validation missing | Implement state machine validation |
| Critical | Lease contention without retry | Add retry with backoff |
| Medium | Worker exception handling | Use structured logging |
| Medium | Session scope in Worker | Use scoped sessions per operation |
| Medium | String vs enum inconsistency | Use enum values consistently |
| Medium | Device status on lease release | Check before resetting to IDLE |
| High | CLI bypassing services | Refactor CLI to use service methods |

---

## File References

| File | Absolute Path |
|------|---------------|
| device_service.py | `E:\git_repositories\AegisOTA\app\services\device_service.py` |
| run_service.py | `E:\git_repositories\AegisOTA\app\services\run_service.py` |
| scheduler_service.py | `E:\git_repositories\AegisOTA\app\services\scheduler_service.py` |
| worker_service.py | `E:\git_repositories\AegisOTA\app\services\worker_service.py` |