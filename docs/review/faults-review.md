# Fault Injection Module Review Report

## Overview

The fault injection module implements a plugin-based system for simulating various fault scenarios during OTA upgrade testing.

---

## STRENGTHS

1. **Clean lifecycle pattern** - `prepare/inject/cleanup` three-stage pattern
2. **Flexible default implementations** - Base class provides sensible defaults
3. **Good result abstraction** - `FaultResult` dataclass with consistent fields
4. **Event recording integration** - Proper `RunContext.timeline` integration
5. **Parameter system** - `set_parameters()` and `validate_parameters()` for configuration

---

## CRITICAL ISSUES

### 1. Base Class - Missing Stage Validation
**File:** `base.py:35-37`

No validation that `fault_stage` matches valid `FaultStage` enum values.

---

### 2. Download Interrupted - Identical Implementation for Different Points
**File:** `download_interrupted.py:86-114`

All three interrupt points (`before_download`, `during_download`, `after_download`) execute identical operations - just deleting the file.

**Expected:**
- `during_download`: Create partial file
- `after_download`: Corrupt/truncate file

---

### 3. Reboot Interrupted - Disconnect Simulation Does Not Work
**File:** `reboot_interrupted.py:98-102`

```python
if self.interrupt_type == "disconnect":
    disconnect_result = self.executor.shell("exit", ...)  # Does NOT disconnect ADB
```

The "disconnect" simulation is ineffective. `shell("exit")` only exits shell session, doesn't disconnect ADB.

---

### 4. Reboot Interrupted - Timeout Type Not Implemented
**File:** `reboot_interrupted.py:46, 22`

The `timeout` interrupt type is validated but never implemented in `inject()`.

---

### 5. Storage Pressure - Cleanup State Corruption
**File:** `storage_pressure.py:189, 206`

```python
self._fill_file_path = None  # Set to None
# ...
data={"removed_file": self._fill_file_path},  # Always None!
```

The cleanup result always reports `removed_file: None`.

---

### 6. Storage Pressure - Incorrect Fill Size Calculation
**File:** `storage_pressure.py:121-122`

Fill size calculation is mathematically incorrect for the intended behavior.

---

## MODERATE ISSUES

### 7. Unused Result Variables
**Files:** Multiple

Shell command results assigned but never checked for errors.

### 8. No Plugin Registry or Factory
**File:** `__init__.py`

No mechanism to dynamically create plugins by type.

### 9. Monkey Plugin - No File Write Error Handling
**File:** `monkey_after_upgrade.py:94-96`

File write operation has no try/except.

### 10. Hardcoded Remote Path
**File:** `download_interrupted.py:65`

`/data/local/tmp/update.zip` is hardcoded instead of using `context.package_path`.

---

## MISSING FAULT SCENARIOS

The `FaultType` enum defines these **NOT implemented** types:

| Fault Type | Stage | Status |
|------------|-------|--------|
| `PACKAGE_CORRUPTED` | precheck | **MISSING** |
| `LOW_BATTERY` | precheck | **MISSING** |
| `POST_BOOT_WATCHDOG_FAILURE` | post_validate | **MISSING** |
| `PERFORMANCE_REGRESSION` | post_validate | **MISSING** |

---

## RECOMMENDATIONS

### Priority 1 (Critical)

1. **Fix download interrupt implementations:**
   - `during_download`: Create partial file with `dd`
   - `after_download`: Corrupt file by modifying bytes

2. **Fix reboot disconnect simulation:**
   - Use actual `adb disconnect <device>` command
   - Or implement timeout by blocking wait_for_device

3. **Fix storage pressure cleanup state bug:**
   - Save path to local variable before setting to `None`

### Priority 2 (Important)

4. **Add plugin factory/registry:**
   ```python
   FAULT_PLUGINS = {
       "storage_pressure": StoragePressureFault,
       ...
   }
   def create_fault_plugin(fault_type: str, **kwargs) -> FaultPlugin:
       return FAULT_PLUGINS.get(fault_type)(**kwargs)
   ```

5. Use `context.package_path` for package location
6. Add error handling for file operations

### Priority 3 (Enhancement)

7. Implement missing fault types (PACKAGE_CORRUPTED, LOW_BATTERY, WATCHDOG_FAILURE, PERFORMANCE_REGRESSION)
8. Add cleanup retry mechanism