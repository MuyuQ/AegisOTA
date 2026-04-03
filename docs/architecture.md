# AegisOTA 系统架构

## 概述

AegisOTA 采用"控制面 + 执行面"的分层架构设计，实现任务调度与命令执行的解耦。

```
┌─────────────────────────────────────────────────────────────────┐
│                      Control Plane (控制面）                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │               FastAPI Web Service                         │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────┐  │  │
│  │  │ Devices │ │  Pools  │ │  Runs   │ │    Diagnosis    │  │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │          Web Console (Jinja2 + HTMX)                │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                               │                                   │
│                    ┌──────────▼──────────┐                       │
│                    │   Service Layer     │                       │
│                    │  (Business Logic)   │                       │
│                    └──────────┬──────────┘                       │
│                               │                                   │
│                    ┌──────────▼──────────┐                       │
│                    │   SQLite Database   │                       │
│                    │   (SQLAlchemy 2.0)  │                       │
│                    └─────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Execution Plane (执行面）                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                  Worker Process                           │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │    Run       │  │    Fault     │  │   Validation    │  │  │
│  │  │  Executor    │  │   Injector   │  │    Modules      │  │  │
│  │  └──────────────┘  └──────────────┘  └─────────────────┘  │  │
│  │  ┌───────────────────────────────────────────────────────┐ │  │
│  │  │        Command Runner (ADB/Fastboot)                  │ │  │
│  │  └───────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│                               │                                   │
│                    ┌──────────▼──────────┐                       │
│                    │  Android Devices    │                       │
│                    │   (via ADB/USB)     │                       │
│                    └─────────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 核心模块

### 1. API 层 (`app/api/`)

RESTful API 路由层，负责接收 HTTP 请求并调用服务层。

| 模块 | 职责 |
|------|------|
| `devices.py` | 设备 CRUD、同步、隔离、恢复 |
| `pools.py` | 设备池管理、容量查询 |
| `runs.py` | 任务创建、查询、终止 |
| `plans.py` | 升级计划管理 |
| `reports.py` | 报告生成与导出 |
| `diagnosis.py` | 日志诊断与规则管理 |
| `web.py` | Web 页面路由 |

### 2. 服务层 (`app/services/`)

业务逻辑层，API 和 CLI 共享。

| 服务 | 职责 |
|------|------|
| `DeviceService` | 设备生命周期管理 |
| `PoolService` | 设备池容量与分配 |
| `RunService` | 任务状态机与调度 |
| `WorkerService` | Worker 任务协调 |
| `LogExportService` | 设备日志导出 |
| `DiagnosisService` | 日志分析与诊断 |
| `ReportService` | 报告生成 |

### 3. 执行层 (`app/executors/`)

命令执行与任务编排。

| 模块 | 职责 |
|------|------|
| `RunExecutor` | 任务全流程编排 |
| `StepHandler` | 各阶段处理器 |
| `ADBExecutor` | ADB 命令封装 |
| `CommandRunner` | 通用命令执行 |
| `RunContext` | 执行上下文 |

### 4. 异常注入层 (`app/faults/`)

故障注入插件系统。

```
FaultPlugin (基类)
├── prepare()   - 准备异常条件
├── inject()    - 注入异常
└── cleanup()   - 清理恢复

内置插件:
├── low_battery.py          - 低电量
├── storage_pressure.py     - 存储压力
├── download_interrupted.py - 下载中断
├── reboot_interrupted.py   - 重启中断
├── package_corrupted.py    - 包损坏
├── monkey_after_upgrade.py - Monkey 压测
└── ...
```

### 5. 诊断层 (`app/diagnosis/` + `app/parsers/`)

TraceLens 日志分析引擎。

```
parsers/                    # 日志解析器
├── recovery_parser.py      # recovery.log
├── update_engine_parser.py # update_engine.log
├── logcat_parser.py        # logcat
└── monkey_parser.py        # monkey 输出

diagnosis/                  # 诊断引擎
├── engine.py               # 规则匹配
├── loader.py               # 规则加载
├── confidence.py           # 置信度计算
└── similar.py              # 相似案例召回
```

### 6. 验证器层 (`app/validators/`)

升级后验证模块。

| 验证器 | 职责 |
|--------|------|
| `BootCheck` | 启动完成检查 |
| `VersionCheck` | 版本号验证 |
| `PerfCheck` | 性能基准检查 |
| `MonkeyRunner` | Monkey 稳定性测试 |
| `StateMachine` | 状态转换验证 |

---

## 数据模型

### 核心实体关系

```
┌──────────────┐       ┌──────────────┐
│  DevicePool  │       │ UpgradePlan  │
└──────┬───────┘       └──────┬───────┘
       │                      │
       │ 1:N                  │ 1:N
       ▼                      ▼
┌──────────────┐       ┌──────────────┐
│    Device    │       │  RunSession  │
└──────┬───────┘       └──────┬───────┘
       │                      │
       │ N:M (Lease)          │ 1:N
       └──────────────────────┼──────────────┐
                              │              │
                              ▼              ▼
                       ┌────────────┐  ┌────────────┐
                       │  RunStep   │  │  Artifact  │
                       └────────────┘  └────────────┘
```

### 主要数据表

| 表名 | 说明 |
|------|------|
| `devices` | 设备信息（序列号、状态、健康度） |
| `device_pools` | 设备池配置 |
| `device_leases` | 设备租约记录 |
| `upgrade_plans` | 升级计划模板 |
| `fault_profiles` | 异常注入配置 |
| `run_sessions` | 任务执行记录 |
| `run_steps` | 步骤执行详情 |
| `artifacts` | 产物文件记录 |
| `reports` | 报告记录 |
| `diagnostic_results` | 诊断结果 |
| `normalized_events` | 标准化日志事件 |
| `rule_hits` | 规则命中记录 |
| `diagnostic_rules` | 诊断规则定义 |

---

## 状态机设计

### 任务状态转换

```
                ┌─────────────┐
                │   QUEUED    │
                └──────┬──────┘
                       │ scheduler
                       ▼
                ┌─────────────┐
                │  ALLOCATING │──┐
                └──────┬──────┘  │ allocation fail
                       │         │
                       ▼         │
                ┌─────────────┐  │
                │   RESERVED  │◄─┘
                └──────┬──────┘
                       │ worker start
                       ▼
                ┌─────────────┐
                │   RUNNING   │──┐
                └──────┬──────┘  │ error/timeout
                       │         │
                       ▼         │
                ┌─────────────┐  │
                │  VALIDATING │◄─┘
                └──────┬──────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │  PASSED  │  │  FAILED  │  │  ABORTED │
  └──────────┘  └──────────┘  └──────────┘
```

### 设备状态转换

```
         ┌──────────────┐
         │    OFFLINE   │
         └──────┬───────┘
                │ sync
                ▼
         ┌──────────────┐◄─────┐
         │     IDLE     │─────┤
         └──────┬───────┘     │ lease release
                │ lease      │
                ▼            │
         ┌──────────────┐    │
         │   RESERVED   │────┘
         └──────┬───────┘
                │ task start
                ▼
         ┌──────────────┐
         │     BUSY     │
         └──────┬───────┘
                │ task end
                ▼
         ┌──────────────┐
         │  QUARANTINED │ (if failed)
         └──────────────┘
```

---

## 执行流程

### 任务执行时序

```
User      API          Service        Worker        Executor       Device
  │         │             │             │              │              │
  │───┐     │             │             │              │              │
  │ P │     │             │             │              │              │
  │ O │────>│             │             │              │              │
  │ S │     │────────────>│             │              │              │
  │ T │     │             │ poll        │              │              │
  │   │     │             │──────┐      │              │              │
  │   │     │             │      │      │              │              │
  │   │     │             │<─────┘      │              │              │
  │   │     │             │             │              │              │
  │   │     │             │             │ execute      │              │
  │   │     │             │────────────>│              │              │
  │   │     │             │             │─────────────>│              │
  │   │     │             │             │  precheck    │              │
  │   │     │             │             │<─────────────│              │
  │   │     │             │             │─────────────>│              │
  │   │     │             │             │  apply       │              │
  │   │     │             │             │<─────────────│              │
  │   │     │             │             │─────────────>│              │
  │   │     │             │             │  reboot      │              │
  │   │     │             │             │<─────────────│              │
  │   │     │             │             │─────────────>│              │
  │   │     │             │             │  validate    │              │
  │   │     │             │             │<─────────────│              │
  │   │     │             │             │              │              │
  │   │     │             │<────────────│              │              │
  │   │     │<────────────│             │              │              │
  │<───────│─│─│─│─│─│─│─│─│              │              │              │
  │         │             │             │              │              │
```

---

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| **数据库** | SQLite | 单机部署足够，零运维成本 |
| **Web 框架** | FastAPI | 高性能、类型安全、自动文档 |
| **前端** | Jinja2 + HTMX | 轻量级，无需构建流程 |
| **Worker** | 单机进程 | 避免 Celery 复杂度 |
| **异常注入** | 插件化 | 易扩展，独立封装 |
| **命令执行** | CommandRunner | 统一抽象，易于测试 |

---

## 扩展性

### 添加新 API

```python
# app/api/my_feature.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

@router.get("/")
def list_items():
    return {"items": []}

# app/main.py
from app.api import my_feature
app.include_router(my_feature.router)
```

### 添加新异常插件

```python
# app/faults/my_fault.py
from app.faults.base import FaultPlugin

class MyFault(FaultPlugin):
    def prepare(self, context): ...
    def inject(self, context): ...
    def cleanup(self, context): ...
```

### 添加新验证器

```python
# app/validators/my_check.py
from app.validators.base import BaseValidator

class MyCheck(BaseValidator):
    def validate(self, context) -> tuple[bool, str]:
        ...
```
