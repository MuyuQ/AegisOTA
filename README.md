# AegisOTA

**Android OTA Upgrade Exception Injection and Multi-Device Verification Platform**

安卓 OTA 升级异常注入与多机验证平台 - 面向测试开发场景的系统升级测试平台

---

## 目录

- [项目简介](#项目简介)
- [核心特性](#核心特性)
- [架构设计](#架构设计)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [核心概念](#核心概念)
- [异常注入场景](#异常注入场景)
- [API 参考](#api-参考)
- [CLI 命令](#cli-命令)
- [项目结构](#项目结构)
- [开发指南](#开发指南)
- [许可证](#许可证)

---

## 项目简介

AegisOTA 是一个将原本分散在脚本、人工经验、机房操作中的升级测试流程，收敛为一套**可配置、可执行、可追踪、可复盘**的自动化测试平台。

### 解决的问题

- 升级测试依赖人工经验，操作不可复现
- 异常场景难以模拟，测试覆盖不全
- 多设备并行测试时资源冲突
- 失败归因困难，缺乏系统性分析
- 测试结果无法有效沉淀和对比

### 核心价值

| 价值 | 说明 |
|------|------|
| **可配置** | 通过升级计划模板，灵活定义升级类型、异常注入、验证策略 |
| **可执行** | 自动编排升级全流程，支持单机/批量执行 |
| **可追踪** | 全链路状态机驱动，每个阶段都有结构化记录 |
| **可复盘** | 自动生成测试报告，包含失败分类、证据链、相似案例 |

---

## 核心特性

### 1. 升级流程编排

支持四种任务模板：

```
┌─────────────────────────────────────────────────────────────┐
│  任务类型          │  适用场景                               │
├─────────────────────────────────────────────────────────────┤
│  全量升级 (full)   │  完整系统包升级测试                      │
│  增量升级 (delta)  │  Patch 差分包升级测试                    │
│  失败回滚 (rollback)│  升级失败自动回滚验证                   │
│  升级后验证 (post) │  升级完成后功能/稳定性验证               │
└─────────────────────────────────────────────────────────────┘
```

### 2. 异常注入系统

采用插件化设计，支持在升级的不同阶段注入故障：

```
执行阶段：precheck → package_prepare → apply_update → reboot_wait → post_validate
              ↓              ↓              ↓             ↓            ↓
        异常注入点       异常注入点    异常注入点    异常注入点   异常注入点
```

### 3. 设备池管理

```
┌─────────────────────────────────────────────────────────────┐
│                      设备池 (DevicePool)                     │
├─────────────────┬─────────────────┬─────────────────────────┤
│   stable 池     │   stress 池     │   emergency 池          │
│   (稳定测试)    │   (压力测试)    │   (应急/抢占)            │
│   max: 20       │   max: 30       │   max: 10               │
│   reserved: 20% │   reserved: 10% │   reserved: 50%         │
└─────────────────┴─────────────────┴─────────────────────────┘
```

### 4. 智能诊断 (TraceLens 集成)

- 自动从设备导出日志 (recovery.log, update_engine.log, logcat)
- 规则驱动的故障分类引擎
- 相似历史案例召回
- 置信度评估与建议操作

---

## 架构设计

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Control Plane (控制面)                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    FastAPI Web Service                       │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐    │    │
│  │  │  Devices  │ │   Pools   │ │   Runs    │ │  Reports  │    │    │
│  │  │    API    │ │    API    │ │    API    │ │    API    │    │    │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘    │    │
│  │  ┌───────────────────────────────────────────────────────┐  │    │
│  │  │              Web Console (Jinja2 + HTMX)              │  │    │
│  │  └───────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                    │                                  │
│                          ┌─────────▼─────────┐                       │
│                          │   Service Layer   │                       │
│                          │  (Business Logic) │                       │
│                          └─────────┬─────────┘                       │
│                                    │                                  │
│                          ┌─────────▼─────────┐                       │
│                          │   SQLite Database │                       │
│                          │   (SQLAlchemy)    │                       │
│                          └───────────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Execution Plane (执行面)                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Worker Process                            │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │    │
│  │  │   Run        │  │   Fault      │  │  Validation  │       │    │
│  │  │  Executor    │  │   Injector   │  │   Modules    │       │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │    │
│  │  ┌──────────────────────────────────────────────────────┐    │    │
│  │  │              Command Runner (ADB/Fastboot)           │    │    │
│  │  └──────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                    │                                  │
│                          ┌─────────▼─────────┐                       │
│                          │  Android Devices  │                       │
│                          │   (via ADB/USB)   │                       │
│                          └───────────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 任务状态机

```
                    ┌─────────────┐
                    │   QUEUED    │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  ALLOCATING │──────┐
                    └──────┬──────┘      │
                           │             │ 分配失败
                           ▼             │
                    ┌─────────────┐      │
                    │   RESERVED  │◄─────┘
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   RUNNING   │──────┐
                    └──────┬──────┘      │
                           │             │ 异常/超时
                           ▼             │
                    ┌─────────────┐      │
                    │  VALIDATING │      │
                    └──────┬──────┘      │
                           │             │
           ┌───────────────┼─────────────┤
           ▼               ▼             ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │  PASSED  │   │  FAILED  │   │  ABORTED │
    └──────────┘   └──────────┘   └──────────┘
```

### 执行阶段流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Run Execution Flow                          │
└─────────────────────────────────────────────────────────────────────┘

  ┌─────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐    ┌───────────────┐
  │ PRECHECK│───▶│PACKAGE_PREPARE│───▶│APPLY_UPDATE │───▶│REBOOT_WAIT│───▶│POST_VALIDATE │
  └────┬────┘    └──────┬───────┘    └──────┬───────┘    └─────┬─────┘    └───────┬───────┘
       │                │                   │                 │                   │
       ▼                ▼                   ▼                 ▼                   ▼
  ┌─────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐    ┌───────────────┐
  │设备检查  │    │推送升级包     │    │触发升级      │    │等待重启    │    │升级后验证     │
  │电量/存储 │    │校验签名      │    │recovery 模式 │    │boot 完成   │    │版本/功能检查 │
  └─────────┘    └──────────────┘    └──────────────┘    └───────────┘    └───────────────┘
```

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **语言** | Python 3.10+ | 类型注解、async/await |
| **Web 框架** | FastAPI | 高性能异步 API |
| **数据库** | SQLite + SQLAlchemy 2.0 | ORM、迁移管理 |
| **CLI** | Typer | 类型安全的命令行 |
| **前端** | Jinja2 + HTMX | 轻量级服务端渲染 |
| **测试** | Pytest + pytest-asyncio | 异步测试支持 |
| **代码质量** | Ruff | 快速 lint |
| **依赖管理** | uv | 快速包管理 |

---

## 快速开始

### 环境要求

- Python 3.10+
- ADB (Android Debug Bridge) 已安装并配置
- 至少一台 Android 测试设备

### 安装

```bash
# 克隆仓库
git clone https://github.com/MuyuQ/AegisOTA.git
cd AegisOTA

# 安装依赖
pip install -e ".[dev]"

# 或使用 uv (推荐)
uv pip install -e ".[dev]"
```

### 初始化数据库

```bash
# 数据库会在首次运行时自动创建
# 或手动执行迁移
alembic upgrade head
```

### 启动服务

```bash
# 终端 1: 启动 Web 服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2: 启动 Worker (可选，用于后台任务执行)
labctl worker start
```

### 验证安装

```bash
# 访问 API 文档
open http://localhost:8000/docs

# 检查 CLI
labctl --help
```

---

## 使用指南

### 1. 设备管理

```bash
# 同步 ADB 连接的设备
labctl device sync

# 列出所有设备
labctl device list

# 输出示例：
# ID  SERIAL       STATUS   HEALTH  POOL      TAGS
# 1   ABC123       idle     95%     stable    flagship,android14
# 2   DEF456       busy     88%     stress    mid-range,android13
```

### 2. 创建设备池

```bash
# 创建稳定测试池
labctl pool create --name stable --purpose stable --max-devices 20

# 创建压力测试池
labctl pool create --name stress --purpose stress --max-devices 30

# 初始化默认池
labctl pool init
```

### 3. 创建升级计划

升级计划是任务执行的模板：

```bash
# 创建标准升级计划
labctl run create-plan \
  --name "Android 15 全量升级" \
  --type full \
  --package /path/to/update.zip \
  --pool stable
```

### 4. 提交任务

```bash
# 提交任务到指定设备
labctl run submit --plan-id 1 --device-serial ABC123

# 提交任务到设备池（自动分配）
labctl run submit --plan-id 1 --pool stable --priority high
```

### 5. 查看任务状态

```bash
# 列出所有任务
labctl run list

# 查看任务详情
labctl run show --run-id 1

# 终止任务
labctl run abort --run-id 1
```

### 6. 导出报告

```bash
# 导出 HTML 报告
labctl report export --run-id 1 --format html --output report.html

# 导出 Markdown 报告
labctl report export --run-id 1 --format md --output report.md
```

---

## 核心概念

### Device (设备)

```python
Device {
    id: int
    serial: str           # ADB 序列号
    brand: str            # 品牌 (e.g., "Xiaomi")
    model: str            # 型号 (e.g., "2201123G")
    status: DeviceStatus  # idle/busy/offline/quarantined
    health_score: int     # 0-100
    battery_level: int    # 电量百分比
    pool_id: Optional[int]
    tags: List[str]       # 标签用于筛选
}
```

### DevicePool (设备池)

```python
DevicePool {
    id: int
    name: str             # 池名称
    purpose: PoolPurpose  # stable/stress/emergency
    max_devices: int      # 最大容量
    reserved_ratio: float # 预留比例
    description: str
}
```

### UpgradePlan (升级计划)

```python
UpgradePlan {
    id: int
    name: str
    upgrade_type: str     # full/delta/rollback
    package_path: str     # 升级包路径
    fault_profile_id: Optional[int]  # 关联的异常配置
    default_pool_id: Optional[int]   # 默认执行池
}
```

### RunSession (任务会话)

```python
RunSession {
    id: int
    plan_id: int
    device_id: Optional[int]
    pool_id: Optional[int]
    status: RunStatus     # queued/running/passed/failed
    priority: RunPriority # normal/high/emergency
    result: Optional[str] # passed/failed
    failure_category: Optional[str]
    started_at: datetime
    ended_at: datetime
}
```

### DeviceLease (设备租约)

```python
DeviceLease {
    id: int
    device_id: int
    run_id: int
    status: LeaseStatus   # active/released/preempted
    leased_at: datetime
    expired_at: datetime
}
```

---

## 异常注入场景

### 内置异常类型

| 异常名称 | 触发阶段 | 描述 |
|---------|---------|------|
| `low_battery` | precheck | 模拟电量不足 (低于阈值) |
| `storage_pressure` | precheck | `/data/local/tmp` 存储空间不足 |
| `download_interrupted` | apply_update | 下载升级包时网络中断 |
| `package_corrupted` | package_prepare | 升级包校验失败 |
| `reboot_interrupted` | reboot_wait | 重启过程中断开连接 |
| `post_boot_watchdog_failure` | post_reboot | 关键进程崩溃导致看门狗重启 |
| `performance_regression` | post_validate | 升级后性能下降检测 |
| `monkey_after_upgrade` | post_validate | 升级后稳定性压测 |

### 创建异常配置文件

```yaml
# faults/low_battery.yaml
name: low_battery_test
description: 模拟电量不足场景
trigger_stage: precheck
config:
  threshold: 20  # 电量阈值 (%)
  action: set_battery_level
```

### 使用异常注入

```bash
# 创建带异常注入的升级计划
labctl run create-plan \
  --name "低电量异常测试" \
  --type full \
  --fault-profile low_battery
```

---

## API 参考

### 基础信息

- **Base URL**: `http://localhost:8000`
- **API Docs**: `http://localhost:8000/docs`
- **认证**: API Key (通过 `X-API-Key` 请求头)

### 设备管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/devices` | 获取设备列表 |
| GET | `/api/devices/{id}` | 获取设备详情 |
| POST | `/api/devices/sync` | 同步设备 |
| POST | `/api/devices/{id}/quarantine` | 隔离设备 |
| POST | `/api/devices/{id}/recover` | 恢复设备 |

### 设备池管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/pools` | 获取设备池列表 |
| POST | `/api/pools` | 创建设备池 |
| GET | `/api/pools/{id}` | 获取设备池详情 |
| PUT | `/api/pools/{id}` | 更新设备池 |
| DELETE | `/api/pools/{id}` | 删除设备池 |
| POST | `/api/pools/{id}/assign` | 分配设备到池 |
| GET | `/api/pools/{id}/devices` | 获取池内设备 |
| GET | `/api/pools/{id}/capacity` | 获取池容量信息 |

### 任务管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/runs` | 获取任务列表 |
| POST | `/api/runs` | 创建任务 |
| GET | `/api/runs/{id}` | 获取任务详情 |
| POST | `/api/runs/{id}/abort` | 终止任务 |

### 升级计划

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/plans` | 获取计划列表 |
| POST | `/api/plans` | 创建升级计划 |
| GET | `/api/plans/{id}` | 获取计划详情 |
| PUT | `/api/plans/{id}` | 更新计划 |
| DELETE | `/api/plans/{id}` | 删除计划 |

### 诊断 (TraceLens)

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/diagnosis` | 诊断记录列表 |
| GET | `/api/diagnosis/{run_id}` | 获取诊断详情 |
| POST | `/api/diagnosis/{run_id}/run` | 手动触发诊断 |
| GET | `/api/diagnosis/{run_id}/export` | 导出诊断报告 |
| GET | `/api/rules` | 列出诊断规则 |
| POST | `/api/rules` | 创建诊断规则 |

### API 使用示例

```bash
# 获取设备列表
curl -s http://localhost:8000/api/devices | jq

# 创建设备池
curl -X POST http://localhost:8000/api/pools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "stable-pool",
    "purpose": "stable",
    "description": "稳定测试设备池",
    "max_devices": 20,
    "reserved_ratio": 0.2
  }'

# 提交升级任务
curl -X POST http://localhost:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": 1,
    "device_id": 1,
    "priority": "normal"
  }'
```

---

## CLI 命令

### 完整命令树

```
labctl
├── device                      # 设备管理
│   ├── sync                    # 同步 ADB 设备
│   ├── list                    # 列出设备
│   ├── quarantine              # 隔离设备
│   └── recover                 # 恢复设备
│
├── pool                        # 设备池管理
│   ├── list                    # 列出设备池
│   ├── create                  # 创建设备池
│   ├── show                    # 查看设备池详情
│   ├── update                  # 更新设备池配置
│   ├── assign                  # 分配设备到池
│   └── init                    # 初始化默认池
│
├── run                         # 任务管理
│   ├── submit                  # 提交任务
│   ├── list                    # 列出任务
│   ├── show                    # 查看任务详情
│   ├── abort                   # 终止任务
│   ├── create-plan             # 创建升级计划
│   └── execute                 # 执行任务 (Worker 模式)
│
├── report                      # 报告管理
│   └── export                  # 导出报告
│
└── worker                      # Worker 管理
    ├── start                   # 启动 Worker
    └── status                  # 查看 Worker 状态
```

---

## 项目结构

```
AegisOTA/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置管理
│   ├── database.py             # 数据库连接
│   │
│   ├── api/                    # API 路由层
│   │   ├── devices.py          # 设备管理 API
│   │   ├── pools.py            # 设备池 API
│   │   ├── runs.py             # 任务管理 API
│   │   ├── plans.py            # 升级计划 API
│   │   ├── reports.py          # 报告 API
│   │   ├── diagnosis.py        # 诊断 API
│   │   └── web.py              # Web 页面路由
│   │
│   ├── models/                 # 数据模型层
│   │   ├── device.py           # Device 模型
│   │   ├── run.py              # RunSession 模型
│   │   ├── fault.py            # FaultProfile 模型
│   │   ├── artifact.py         # Artifact 模型
│   │   ├── diagnostic.py       # 诊断相关模型
│   │   ├── enums.py            # 枚举定义
│   │   └── __init__.py
│   │
│   ├── services/               # 业务逻辑层
│   │   ├── device_service.py   # 设备服务
│   │   ├── pool_service.py     # 设备池服务
│   │   ├── run_service.py      # 任务服务
│   │   ├── worker_service.py   # Worker 服务
│   │   ├── log_export_service.py # 日志导出服务
│   │   └── diagnosis_service.py # 诊断服务
│   │
│   ├── executors/              # 执行器层
│   │   ├── run_executor.py     # 任务执行器
│   │   ├── adb_executor.py     # ADB 命令执行
│   │   ├── command_runner.py   # 通用命令运行器
│   │   └── step_handlers.py    # 阶段处理器
│   │
│   ├── faults/                 # 异常注入插件
│   │   ├── base.py             # 基类定义
│   │   ├── low_battery.py      # 低电量异常
│   │   ├── storage_pressure.py # 存储压力异常
│   │   ├── download_interrupted.py # 下载中断
│   │   ├── reboot_interrupted.py # 重启中断
│   │   └── monkey_after_upgrade.py # Monkey 测试
│   │
│   ├── validators/             # 验证器模块
│   │   ├── boot_check.py       # 启动验证
│   │   ├── version_check.py    # 版本验证
│   │   ├── perf_check.py       # 性能验证
│   │   └── monkey_runner.py    # Monkey 测试运行
│   │
│   ├── parsers/                # 日志解析器
│   │   ├── base.py             # 解析器基类
│   │   ├── recovery_parser.py  # Recovery 日志解析
│   │   ├── update_engine_parser.py # UpdateEngine 日志解析
│   │   ├── logcat_parser.py    # Logcat 解析
│   │   └── monkey_parser.py    # Monkey 输出解析
│   │
│   ├── diagnosis/              # 诊断引擎
│   │   ├── engine.py           # 规则匹配引擎
│   │   ├── loader.py           # 规则加载器
│   │   ├── confidence.py       # 置信度计算
│   │   └── similar.py          # 相似案例召回
│   │
│   ├── reporting/              # 报告生成
│   │   ├── generator.py        # 报告生成器
│   │   └── failure_classifier.py # 失败分类器
│   │
│   ├── cli/                    # CLI 命令
│   │   ├── main.py             # CLI 入口
│   │   ├── device.py           # 设备命令
│   │   ├── pool.py             # 设备池命令
│   │   ├── run.py              # 任务命令
│   │   ├── report.py           # 报告命令
│   │   └── worker.py           # Worker 命令
│   │
│   ├── templates/              # Jinja2 模板
│   │   ├── dashboard.html      # 仪表盘
│   │   ├── devices.html        # 设备列表
│   │   ├── pools.html          # 设备池列表
│   │   ├── plans.html          # 升级计划
│   │   ├── create_run.html     # 创建任务
│   │   └── diagnosis.html      # 诊断页面
│   │
│   └── static/                 # 静态资源
│       └── css/
│           └── style.css
│
├── tests/                      # 测试用例
│   ├── test_api/               # API 测试
│   ├── test_services/          # 服务层测试
│   └── test_executors/         # 执行器测试
│
├── artifacts/                  # 执行产物
│   └── {run_id}/               # 按任务 ID 组织
│       ├── logs/               # 日志文件
│       ├── screenshots/        # 截图
│       └── reports/            # 报告
│
├── docs/                       # 文档
│   ├── architecture.md         # 架构文档
│   ├── API.md                  # API 文档
│   └── CONTRIBUTING.md         # 贡献指南
│
├── pyproject.toml              # 项目配置
├── uv.lock                     # 依赖锁定
└── README.md                   # 本文档
```

---

## 开发指南

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行覆盖率测试
pytest tests/ --cov=app --cov-report=html

# 运行特定测试文件
pytest tests/test_api/test_devices.py -v
```

### 代码质量检查

```bash
# 代码格式化检查
ruff check app/

# 自动修复
ruff check app/ --fix
```

### 添加新的异常注入插件

1. 继承 `FaultPlugin` 基类：

```python
# app/faults/custom_fault.py
from app.faults.base import FaultPlugin
from app.executors.run_context import RunContext

class CustomFaultPlugin(FaultPlugin):
    """自定义异常注入插件。"""

    def prepare(self, context: RunContext) -> None:
        """准备阶段：设置异常条件。"""
        # 例如：修改设备配置
        pass

    def inject(self, context: RunContext) -> None:
        """注入阶段：触发异常。"""
        # 例如：断开网络连接
        pass

    def cleanup(self, context: RunContext) -> None:
        """清理阶段：恢复设备状态。"""
        # 例如：恢复网络连接
        pass
```

2. 在 `app/faults/__init__.py` 中注册插件

3. 在升级计划中引用

### 添加新的验证器

```python
# app/validators/custom_check.py
from app.validators.base import BaseValidator
from app.executors.run_context import RunContext

class CustomCheck(BaseValidator):
    """自定义验证器。"""

    def validate(self, context: RunContext) -> tuple[bool, str]:
        """
        执行验证。

        Returns:
            (success: bool, message: str)
        """
        # 执行验证逻辑
        return True, "验证通过"
```

---

## 许可证

MIT License

```
Copyright (c) 2026 AegisOTA Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
