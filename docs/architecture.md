# AegisOTA 系统架构

## 概述

AegisOTA 采用"控制面 + 执行面"架构:

- **控制面**: FastAPI 服务，负责设备管理、任务调度、报告生成、Web 展示
- **执行面**: Worker 进程 + Typer CLI，负责调用 ADB/Fastboot、执行升级、采集日志

## 核心模块

### 1. 设备管理模块

负责设备生命周期管理:

- 设备发现与注册
- 状态跟踪 (idle/busy/offline/quarantined)
- 健康检查 (电量、存储、启动状态)
- 标签管理
- 租约机制

### 2. 任务编排模块

负责任务状态机驱动:

- 任务创建与排队
- 设备分配与预留
- 阶段执行 (precheck -> apply -> reboot -> validate)
- 超时处理与人工终止

### 3. 异常注入模块

负责模拟故障场景:

- 插件模式设计
- 三阶段生命周期 (prepare/inject/cleanup)
- 支持多触发点 (precheck/apply_update/post_validate)

### 4. 报告模块

负责任务归因:

- 失败分类 (package_issue/device_env_issue/boot_failure 等)
- 时间线生成
- HTML/Markdown 报告输出

## 数据模型

```
Device (设备)
├── id, serial, brand, model
├── status, health_score, battery_level
└── tags, last_seen_at

DeviceLease (设备租约)
├── device_id, run_id
└── leased_at, expired_at, lease_status

UpgradePlan (升级计划)
├── name, upgrade_type, package_path
├── fault_profile_id
└── device_selector, parallelism

RunSession (任务会话)
├── plan_id, device_id, status
├── started_at, ended_at
└── result, failure_category

RunStep (执行步骤)
├── run_id, step_name, step_order
├── status, command
└── stdout_path, stderr_path

Artifact (产物)
├── run_id, artifact_type
└── path, size, metadata
```

## 接口设计

### REST API

- `POST /api/runs` - 创建任务
- `GET /api/runs/{id}` - 查询任务
- `POST /api/runs/{id}/abort` - 终止任务
- `GET /api/devices` - 列出设备
- `POST /api/devices/{id}/quarantine` - 隔离设备
- `GET /api/reports/{id}` - 获取报告

### CLI 命令

- `labctl device sync/list/quarantine/recover`
- `labctl run submit/list/abort`
- `labctl report export`
- `labctl worker start/status`

## 设计决策

1. **SQLite 而非 PostgreSQL**: 项目重点是平台设计和流程编排，不是数据库高并发
2. **Jinja2 + HTMX 而非 SPA**: Web 只是展示层，不引入前后端分离复杂度
3. **单机 Worker 而非 Celery**: 单机调度足以证明设计，不需要分布式复杂度
4. **插件模式异常注入**: 灵活扩展，每个异常独立封装