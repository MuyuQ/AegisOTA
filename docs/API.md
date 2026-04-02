# AegisOTA API 文档

## 概述

AegisOTA 提供 RESTful API 用于管理设备、任务和报告。

### 基础信息

- **Base URL**: `http://localhost:8000`
- **API 前缀**: `/api`
- **认证方式**: API Key（通过 `X-API-Key` 请求头）

### 认证

所有 `/api/*` 路由需要 API Key 认证（可配置白名单）。

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/devices
```

---

## 设备管理 API

### 获取设备列表

```
GET /api/devices
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | 按状态过滤（idle, busy, offline, quarantined） |
| pool_id | int | 按设备池过滤 |
| limit | int | 返回数量限制（默认 100） |
| offset | int | 分页偏移（默认 0） |

**响应示例：**

```json
{
  "data": [
    {
      "id": 1,
      "serial": "ABC123",
      "status": "idle",
      "health_score": 95,
      "pool_id": 1
    }
  ],
  "pagination": {
    "total": 10,
    "limit": 100,
    "offset": 0,
    "has_more": false
  }
}
```

### 获取设备详情

```
GET /api/devices/{device_id}
```

### 隔离设备

```
POST /api/devices/{device_id}/quarantine
```

**请求体：**

```json
{
  "reason": "设备异常"
}
```

### 恢复设备

```
POST /api/devices/{device_id}/recover
```

### 同步设备

```
POST /api/devices/sync
```

扫描 ADB 连接的设备并更新数据库。

---

## 设备池 API

### 获取设备池列表

```
GET /api/pools
```

### 创建设备池

```
POST /api/pools
```

**请求体：**

```json
{
  "name": "stable-pool",
  "purpose": "stable",
  "description": "稳定测试设备池",
  "max_devices": 50,
  "reserved_ratio": 0.2
}
```

### 获取设备池详情

```
GET /api/pools/{pool_id}
```

### 更新设备池

```
PUT /api/pools/{pool_id}
```

### 删除设备池

```
DELETE /api/pools/{pool_id}
```

### 分配设备到池

```
POST /api/pools/{pool_id}/assign
```

**请求体：**

```json
{
  "device_id": 1
}
```

### 获取池内设备

```
GET /api/pools/{pool_id}/devices
```

### 获取池容量

```
GET /api/pools/{pool_id}/capacity
```

---

## 任务管理 API

### 获取任务列表

```
GET /api/runs
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | 按状态过滤 |
| device_id | int | 按设备过滤 |
| limit | int | 返回数量限制 |
| offset | int | 分页偏移 |

### 创建任务

```
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

```
GET /api/runs/{run_id}
```

### 终止任务

```
POST /api/runs/{run_id}/abort
```

---

## 升级计划 API

### 获取计划列表

```
GET /api/plans
```

### 创建升级计划

```
POST /api/plans
```

**请求体：**

```json
{
  "name": "标准升级计划",
  "upgrade_type": "full",
  "fault_profile_id": 1,
  "description": "标准全量升级测试"
}
```

---

## 报告 API

### 获取任务报告

```
GET /api/reports/{run_id}
```

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| format | string | 报告格式（json, html, markdown） |

---

## 错误响应

所有错误响应遵循统一格式：

```json
{
  "detail": "错误描述",
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

## CLI 命令

### 设备管理

```bash
# 同步设备
labctl device sync

# 列出设备
labctl device list

# 隔离设备
labctl device quarantine --device-id 1 --reason "设备异常"

# 恢复设备
labctl device recover --device-id 1
```

### 设备池管理

```bash
# 列出设备池
labctl pool list

# 创建设备池
labctl pool create --name stable --purpose stable

# 查看设备池详情
labctl pool show --name stable

# 分配设备到池
labctl pool assign --device-id 1 --pool-name stable

# 初始化默认设备池
labctl pool init
```

### 任务管理

```bash
# 提交任务
labctl run submit --plan-id 1 --device-serial ABC123

# 列出任务
labctl run list

# 终止任务
labctl run abort --run-id 1

# 执行任务（Worker 模式）
labctl run execute --run-id 1
```

### 报告导出

```bash
# 导出报告
labctl report export --run-id 1 --format html --output report.html
```

---

## WebSocket 事件（规划中）

未来版本将支持 WebSocket 实时事件推送：

- `device.status_changed` - 设备状态变更
- `run.status_changed` - 任务状态变更
- `run.step_completed` - 步骤完成
- `run.step_failed` - 步骤失败