# AegisOTA API 文档

完整的 RESTful API 参考文档。

## 基础信息

| 项目 | 值 |
|------|-----|
| **Base URL** | `http://localhost:8000` |
| **API 前缀** | `/api` |
| **交互式文档** | `/docs` (Swagger UI) |
| **认证方式** | API Key (通过 `X-API-Key` 请求头，可选) |

---

## 设备管理 API

### 获取设备列表

```http
GET /api/devices
```

**查询参数：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `status` | string | - | 按状态过滤 (idle/busy/offline/quarantined) |
| `pool_id` | int | - | 按设备池过滤 |
| `limit` | int | 100 | 返回数量限制 |
| `offset` | int | 0 | 分页偏移 |

**响应示例：**

```json
{
  "data": [
    {
      "id": 1,
      "serial": "ABC123",
      "brand": "Xiaomi",
      "model": "2201123G",
      "status": "idle",
      "health_score": 95,
      "battery_level": 85,
      "pool_id": 1,
      "tags": ["flagship", "android14"]
    }
  ],
  "pagination": {
    "total": 10,
    "limit": 100,
    "offset": 0
  }
}
```

### 获取设备详情

```http
GET /api/devices/{device_id}
```

### 同步设备

```http
POST /api/devices/sync
```

扫描 ADB 连接的设备并更新数据库。

### 隔离设备

```http
POST /api/devices/{device_id}/quarantine
```

**请求体：**

```json
{
  "reason": "升级失败 - 重启中断"
}
```

### 恢复设备

```http
POST /api/devices/{device_id}/recover
```

---

## 设备池 API

### 获取设备池列表

```http
GET /api/pools
```

**响应示例：**

```json
{
  "data": [
    {
      "id": 1,
      "name": "stable",
      "purpose": "stable",
      "description": "稳定测试设备池",
      "max_devices": 20,
      "reserved_ratio": 0.2,
      "device_count": 5
    }
  ]
}
```

### 创建设备池

```http
POST /api/pools
```

**请求体：**

```json
{
  "name": "stable-pool",
  "purpose": "stable",
  "description": "稳定测试设备池",
  "max_devices": 20,
  "reserved_ratio": 0.2
}
```

### 获取设备池详情

```http
GET /api/pools/{pool_id}
```

### 更新设备池

```http
PUT /api/pools/{pool_id}
```

### 删除设备池

```http
DELETE /api/pools/{pool_id}
```

### 分配设备到池

```http
POST /api/pools/{pool_id}/assign
```

**请求体：**

```json
{
  "device_id": 1
}
```

### 获取池内设备

```http
GET /api/pools/{pool_id}/devices
```

### 获取池容量

```http
GET /api/pools/{pool_id}/capacity
```

**响应示例：**

```json
{
  "pool_id": 1,
  "total": 10,
  "available": 6,
  "reserved": 2,
  "busy": 2,
  "utilization": 0.4
}
```

---

## 任务管理 API

### 获取任务列表

```http
GET /api/runs
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | string | 按状态过滤 |
| `device_id` | int | 按设备过滤 |
| `pool_id` | int | 按设备池过滤 |
| `limit` | int | 返回数量限制 |
| `offset` | int | 分页偏移 |

### 创建任务

```http
POST /api/runs
```

**请求体：**

```json
{
  "plan_id": 1,
  "device_id": 1,
  "priority": "normal"
}
```

### 获取任务详情

```http
GET /api/runs/{run_id}
```

**响应示例：**

```json
{
  "id": 1,
  "plan_id": 1,
  "device_id": 1,
  "status": "running",
  "priority": "normal",
  "stages": [
    {"name": "precheck", "status": "passed"},
    {"name": "apply_update", "status": "running"},
    {"name": "reboot_wait", "status": "pending"},
    {"name": "post_validate", "status": "pending"}
  ],
  "started_at": "2026-04-03T10:00:00"
}
```

### 终止任务

```http
POST /api/runs/{run_id}/abort
```

---

## 升级计划 API

### 获取计划列表

```http
GET /api/plans
```

### 创建升级计划

```http
POST /api/plans
```

**请求体：**

```json
{
  "name": "标准升级计划",
  "upgrade_type": "full",
  "fault_profile_id": null,
  "default_pool_id": 1,
  "description": "标准全量升级测试"
}
```

### 获取计划详情

```http
GET /api/plans/{plan_id}
```

### 更新计划

```http
PUT /api/plans/{plan_id}
```

### 删除计划

```http
DELETE /api/plans/{plan_id}
```

---

## 报告 API

### 获取任务报告

```http
GET /api/reports/{run_id}
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `format` | string | 报告格式 (json/html/markdown) |

### 导出报告

```http
GET /api/reports/{run_id}/export
```

---

## 诊断 API (TraceLens)

### 获取诊断记录列表

```http
GET /api/diagnosis
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `serial` | string | 按设备 SN 过滤 |
| `category` | string | 按故障分类过滤 |
| `page` | int | 页码 |
| `size` | int | 每页数量 |

### 获取诊断详情

```http
GET /api/diagnosis/{run_id}
```

### 手动触发诊断

```http
POST /api/diagnosis/{run_id}/run
```

### 导出诊断报告

```http
GET /api/diagnosis/{run_id}/export?format=md
```

### 管理诊断规则

```http
GET /api/rules          # 列出规则
POST /api/rules         # 创建规则
PUT /api/rules/{rule_id} # 更新规则
DELETE /api/rules/{rule_id} # 删除规则
```

---

## 错误响应

所有错误返回统一格式：

```json
{
  "detail": "错误描述信息",
  "code": "ERROR_CODE"
}
```

**常见错误码：**

| 状态码 | 说明 |
|--------|------|
| 400 | 请求参数无效 |
| 401 | API Key 无效或缺失 |
| 404 | 资源不存在 |
| 409 | 资源冲突（如设备已被占用） |
| 500 | 服务器内部错误 |

---

## 使用示例

### cURL 示例

```bash
# 获取设备列表
curl -s http://localhost:8000/api/devices | jq

# 创建设备池
curl -X POST http://localhost:8000/api/pools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "stable-pool",
    "purpose": "stable",
    "max_devices": 20
  }'

# 提交升级任务
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": 1,
    "device_id": 1
  }'

# 终止任务
curl -X POST http://localhost:8000/api/runs/1/abort
```

### Python 示例

```python
import httpx

BASE_URL = "http://localhost:8000"

# 获取设备列表
with httpx.Client() as client:
    resp = client.get(f"{BASE_URL}/api/devices")
    devices = resp.json()["data"]
    
# 创建任务
with httpx.Client() as client:
    resp = client.post(
        f"{BASE_URL}/api/runs",
        json={"plan_id": 1, "device_id": 1}
    )
    run = resp.json()
```
