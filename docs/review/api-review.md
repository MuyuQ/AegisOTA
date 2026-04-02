# API Module Review Report

## Executive Summary

The API module implements a FastAPI-based REST API with HTMX-powered web interface. The codebase follows a service-layer architecture pattern but has several areas requiring improvement.

---

## Summary Score

| Category | Score | Notes |
|----------|-------|-------|
| RESTful Compliance | 6/10 | Basic patterns followed, but inconsistent prefixes |
| Error Handling | 4/10 | Missing validation errors, inconsistent |
| Request Validation | 5/10 | Pydantic used but missing bounds |
| Response Structure | 5/10 | Consistent models but no pagination |
| Authentication | 0/10 | **Not implemented - critical** |
| Service Integration | 7/10 | Good pattern but some bypass |
| HTMX/Web Patterns | 5/10 | **Has critical bug** |
| Spec Compliance | 7/10 | Core endpoints present |

---

## Critical Issues

### 1. No Authentication Implemented
**Files:** All API files

All endpoints are publicly accessible. Settings modification, quarantine/recovery operations have no authorization check.

### 2. KeyError Bug - Field Name Mismatch
**File:** `devices.py:235, 281, 297`

```python
# Dict uses 'android_version':
d = {"android_version": device.android_version or "-"}

# Template references 'system_version':
<td>{d['system_version']}</td>  # KeyError!
```

### 3. Invalid Parameters Silently Ignored
**Files:** `devices.py:60-61`, `runs.py:116-118`

```python
try:
    device_status = DeviceStatus(status)
except ValueError:
    pass  # Should raise HTTPException(400, "Invalid status")
```

---

## High Priority Issues

### 4. Missing CSRF Protection
**Files:** `devices.html`, `runs.html`, `settings.html`

All HTMX POST forms lack CSRF tokens.

### 5. No Bounds Validation on Numeric Parameters
**File:** `runs.py:52, 107`

```python
parallelism: int = 1  # Could be 0 or negative
limit: int = 100  # Could request 1000000
```

### 6. No Pagination Envelope
**Files:** All list endpoints

Returns full list with only `limit`, no `offset` or total count metadata.

### 7. Inline HTML Construction
**File:** `devices.py:144-187`

Complex inline HTML instead of using templates.

### 8. Missing CORS Configuration
**File:** `main.py`

No CORS middleware - will block cross-origin requests.

---

## Medium Priority Issues

### 9. Reports as Separate Resource
**File:** `reports.py:12`

Router prefix `/api/reports` but reports are sub-resources of runs. Should be `/api/runs/{run_id}/reports`.

### 10. Service Layer Bypass
**File:** `runs.py:166-170`

Direct DB manipulation instead of using RunService.

### 11. Missing Input Validation
- `CreatePlanRequest.device_selector: Optional[dict]` lacks schema validation
- File paths not validated for existence

---

## Missing Endpoints from Spec

1. `GET /api/runs/{id}/steps` - Phase status query
2. `GET /api/plans/{id}` - Single plan detail
3. `PUT /api/plans/{id}` - Plan update
4. `DELETE /api/plans/{id}` - Plan deletion
5. `GET /api/devices/{serial}/leases` - Lease history
6. `GET /api/system/status` - Worker/concurrency status

---

## Priority Action Items

### Critical (Fix Immediately)

1. **Fix KeyError bug** in `devices.py:235, 281, 297`
2. **Add authentication** - at minimum API key
3. **Fix validation errors** - return 400 for invalid filters

### High Priority

4. Add CSRF protection to HTMX forms
5. Add bounds validation to numeric parameters
6. Implement pagination envelope
7. Add CORS middleware
8. Move inline HTML to templates

### Medium Priority

9. Restructure reports as nested resources
10. Complete plan CRUD endpoints
11. Add run steps endpoint