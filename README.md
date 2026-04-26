# AegisOTA

安卓 OTA 升级异常注入与多设备验证平台。

AegisOTA 面向测试开发和实验室设备管理场景，把 OTA 升级测试中的设备发现、设备池调度、升级任务执行、异常注入、日志采集、失败诊断和报告沉淀放到一套可追踪的平台里。它既可以通过网页控制台操作，也可以通过 REST 接口和 `labctl` 命令行接入自动化流程。

## 主要功能

### 设备管理

- 通过 ADB 同步已连接设备。
- 记录设备序列号、品牌、型号、系统版本、电量、健康分、标签和机位信息。
- 支持设备状态流转：`idle`、`reserved`、`busy`、`offline`、`quarantined`、`recovering`。
- 支持设备隔离与恢复，避免不稳定设备继续进入任务队列。
- 支持标签维护，用于后续按设备特征筛选任务。

### 设备池与调度

- 内置三类设备池用途：`stable`、`stress`、`emergency`。
- 设备池支持保留比例、最大并行数、标签选择器和启停配置。
- 调度服务按任务优先级和创建时间选择任务。
- 设备租约用于避免并发任务抢占同一台设备。
- 紧急任务可通过抢占服务释放低优先级任务占用的设备资源。

### 升级计划与任务

- 升级计划描述一类 OTA 测试模板，包括升级类型、升级包路径、目标版本、设备选择器、默认设备池和并行度。
- 当前升级类型：`full`、`incremental`、`rollback`。
- 任务会话记录单次执行，状态包括：

```text
queued -> allocating -> reserved -> running -> validating -> passed/failed/aborted/preempted
```

- 任务可绑定指定设备，也可进入队列后由调度器分配设备。
- 后台执行器从已预留任务中取出执行，并在结束后释放租约、保存产物和生成报告。

### OTA 执行流程

执行器按阶段编排 OTA 流程：

```text
precheck -> package_prepare -> apply_update -> reboot_wait -> post_validate -> report_finalize
```

各阶段由 `app/executors/step_handlers.py` 处理，执行上下文记录时间线、产物目录、任务选项和设备信息。底层命令通过 ADB/Fastboot 包装执行，测试中也提供模拟执行器，便于验证流程。

### 异常注入

故障以插件形式实现，插件提供 `prepare()`、`inject()`、`cleanup()` 生命周期。内置故障包括：

| 故障类型 | 默认阶段 | 作用 |
| --- | --- | --- |
| `low_battery` | `precheck` | 模拟低电量环境 |
| `storage_pressure` | `precheck` | 制造存储压力 |
| `package_corrupted` | `precheck` | 模拟升级包损坏或校验失败 |
| `download_interrupted` | `precheck` | 模拟下载/传输中断 |
| `reboot_interrupted` | `apply_update` | 模拟升级过程中的重启/连接中断 |
| `post_boot_watchdog_failure` | `post_validate` | 模拟升级后关键进程或看门狗异常 |
| `performance_regression` | `post_validate` | 检测升级后性能退化 |
| `monkey_after_upgrade` | `post_validate` | 升级后执行 Monkey 稳定性压测 |

### 诊断与报告

- 解析 recovery、update_engine、logcat、Monkey 等日志来源。
- 将日志归一化为结构化事件。
- 通过规则引擎匹配失败信号并给出置信度。
- 使用 RapidFuzz 做相似案例召回。
- 失败分类覆盖包问题、设备环境问题、启动失败、验证失败、Monkey 不稳定、性能疑似退化、ADB 传输异常和未知问题。
- 报告可生成 Markdown、HTML 或 JSON，并关联任务产物。

### 网页控制台

网页页面基于 Jinja2 + HTMX，提供：

- 仪表盘
- 设备列表
- 任务列表与任务详情
- 创建任务
- 升级计划
- 设备池列表与详情
- 诊断列表与诊断详情
- 设置页面

网页路由不走接口密钥中间件；写操作由 CSRF Token 保护。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 语言 | Python 3.10+ |
| 网页服务 | FastAPI |
| ORM/数据库 | SQLAlchemy 2.0 + SQLite |
| 迁移 | Alembic |
| 命令行 | Typer |
| 页面 | Jinja2 + HTMX |
| 诊断规则 | YAML |
| 相似案例 | RapidFuzz |
| 测试 | pytest / pytest-asyncio |
| 代码质量 | Ruff / mypy |
| 依赖管理 | uv |

## 快速开始

### 环境要求

- Python 3.10+
- ADB/Fastboot 可用
- 至少一台 Android 测试设备
- 推荐使用 uv 管理虚拟环境

### 安装依赖

```bash
uv sync
```

也可以使用 pip 安装项目依赖：

```bash
pip install -e ".[dev]"
```

### 初始化数据库

应用启动时会自动初始化数据库表。需要使用迁移时可以执行：

```bash
alembic upgrade head
```

### 启动网页服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问：

- 网页控制台：`http://localhost:8000/`
- OpenAPI 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

### 启动后台执行器

```bash
labctl worker start
```

也可以只处理一次任务轮询：

```bash
labctl worker run-once
```

## 命令行用法

`labctl` 是平台的命令行入口：

```bash
labctl --help
labctl version
```

### 设备

```bash
labctl device sync
labctl device list
labctl device quarantine SERIAL --reason "启动循环"
labctl device recover SERIAL
```

### 设备池

```bash
labctl pool init
labctl pool list
labctl pool create --name stable --purpose stable --reserved-ratio 0.2 --max-parallel 5
labctl pool show 1
labctl pool update 1 --reserved-ratio 0.1 --max-parallel 10
labctl pool assign 1 DEVICE_ID
```

### 任务

```bash
labctl run submit PLAN_ID --device SERIAL
labctl run list
labctl run list --status queued --limit 20
labctl run abort RUN_ID
labctl run execute RUN_ID
```

说明：当前命令行不包含创建升级计划命令，计划创建主要通过网页表单或 REST 接口完成。

### 报告

```bash
labctl report export RUN_ID --format markdown --output report.md
labctl report export RUN_ID --format html --output report.html
labctl report export RUN_ID --format json --output report.json
```

## REST 接口

接口前缀为 `/api/v1`。当 `AEGISOTA_API_KEYS` 配置了有效密钥且接口密钥开关开启时，请求需要带上：

```text
X-API-Key: <你的接口密钥>
```

### 常用端点

| 模块 | 方法与路径 | 说明 |
| --- | --- | --- |
| 设备 | `GET /api/v1/devices` | 设备列表 |
| 设备 | `GET /api/v1/devices/{serial}` | 设备详情 |
| 设备 | `POST /api/v1/devices/sync` | 同步 ADB 设备 |
| 设备 | `POST /api/v1/devices/{serial}/quarantine` | 隔离设备 |
| 设备 | `POST /api/v1/devices/{serial}/recover` | 恢复设备 |
| 设备 | `PUT /api/v1/devices/{serial}/tags` | 更新设备标签 |
| 设备池 | `GET /api/v1/pools` | 设备池列表 |
| 设备池 | `POST /api/v1/pools` | 创建设备池 |
| 设备池 | `GET /api/v1/pools/{pool_id}` | 设备池详情 |
| 设备池 | `PUT /api/v1/pools/{pool_id}` | 更新设备池 |
| 设备池 | `POST /api/v1/pools/{pool_id}/assign` | 分配设备到池 |
| 设备池 | `GET /api/v1/pools/{pool_id}/capacity` | 查询池容量 |
| 计划 | `GET /api/v1/runs/plans` | 升级计划列表 |
| 计划 | `POST /api/v1/runs/plans` | 创建升级计划 |
| 计划 | `PUT /api/v1/runs/plans/{plan_id}` | 更新升级计划 |
| 计划 | `DELETE /api/v1/runs/plans/{plan_id}` | 删除升级计划 |
| 任务 | `GET /api/v1/runs` | 任务列表 |
| 任务 | `POST /api/v1/runs` | 创建任务 |
| 任务 | `GET /api/v1/runs/{run_id}` | 任务详情 |
| 任务 | `POST /api/v1/runs/{run_id}/reserve` | 预留任务设备 |
| 任务 | `POST /api/v1/runs/{run_id}/abort` | 中止任务 |
| 报告 | `GET /api/v1/reports/{run_id}` | 报告摘要 |
| 报告 | `GET /api/v1/reports/{run_id}/html` | HTML 报告 |
| 报告 | `GET /api/v1/reports/{run_id}/markdown` | Markdown 报告 |
| 报告 | `GET /api/v1/reports/{run_id}/artifacts` | 任务产物 |
| 诊断 | `GET /api/v1/diagnosis` | 诊断记录 |
| 诊断 | `GET /api/v1/diagnosis/{run_id}` | 诊断详情 |
| 诊断 | `POST /api/v1/diagnosis/{run_id}/run` | 手动触发诊断 |
| 诊断 | `POST /api/v1/diagnosis/export-logs/{run_id}` | 从设备导出日志 |
| 诊断 | `GET /api/v1/diagnosis/{run_id}/export` | 导出诊断报告 |

### API 示例

创建设备池：

```bash
curl -X POST http://localhost:8000/api/v1/pools \
  -H "Content-Type: application/json" \
  -d '{
    "name": "stable",
    "purpose": "stable",
    "reserved_ratio": 0.2,
    "tag_selector": {"tags": ["android14"]},
    "enabled": true
  }'
```

创建升级计划：

```bash
curl -X POST http://localhost:8000/api/v1/runs/plans \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Android 15 全量包",
    "upgrade_type": "full",
    "package_path": "ota_packages/full/update.zip",
    "target_build": "android15-userdebug",
    "default_pool_id": 1,
    "parallelism": 1
  }'
```

创建任务：

```bash
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": 1,
    "device_serial": "ABC123"
  }'
```

## 配置

配置通过 `app.config.Settings` 管理，环境变量统一使用 `AEGISOTA_` 前缀。常用配置：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AEGISOTA_DATABASE_URL` | `sqlite:///./aegisota.db` | 数据库地址 |
| `AEGISOTA_ARTIFACTS_DIR` | `artifacts` | 执行产物目录 |
| `AEGISOTA_OTA_PACKAGES_DIR` | `ota_packages` | OTA 包目录 |
| `AEGISOTA_MAX_CONCURRENT_RUNS` | `5` | 最大并发任务数 |
| `AEGISOTA_LEASE_DEFAULT_DURATION` | `3600` | 默认设备租约时长 |
| `AEGISOTA_API_KEY_ENABLED` | `true` | 接口密钥开关 |
| `AEGISOTA_API_KEYS` | 空 | 逗号分隔的接口密钥列表 |
| `AEGISOTA_LOG_LEVEL` | `INFO` | 日志级别 |

初始化配置时会自动创建 `artifacts/`、`ota_packages/full/` 和 `ota_packages/incremental/`。

## 代码结构

```text
app/
├── api/            # REST 接口与网页路由
├── cli/            # labctl 命令
├── services/       # 业务服务、调度、抢占、后台执行器
├── executors/      # OTA 执行器、ADB 包装、阶段处理
├── faults/         # 故障注入插件
├── validators/     # 启动、版本、性能、Monkey 验证
├── parsers/        # 日志解析与事件归一化
├── diagnosis/      # 规则加载、匹配、置信度、相似案例
├── reporting/      # 报告生成与失败分类
├── models/         # SQLAlchemy 模型和枚举
├── templates/      # Jinja2 页面
├── static/         # CSS 与静态资源
├── rules/          # 内置诊断规则
├── utils/          # 日志与事务工具
├── config.py       # 配置
├── database.py     # 数据库初始化
└── main.py         # FastAPI 入口

tests/
├── test_api/
├── test_cli/
├── test_executors/
├── test_faults/
├── test_models/
├── test_reporting/
├── test_services/
├── test_utils/
└── test_validators/
```

## 开发

运行测试：

```bash
pytest
```

按模块运行：

```bash
pytest tests/test_api/
pytest tests/test_services/
pytest tests/test_executors/
pytest tests/test_faults/
pytest tests/test_validators/
```

格式化与检查：

```bash
ruff format app tests
ruff check app tests
mypy app tests
```

数据库迁移：

```bash
alembic revision --autogenerate -m "描述变更"
alembic upgrade head
```

## 适合扩展的方向

- 新增故障插件：放在 `app/faults/`，实现 `FaultPlugin` 生命周期。
- 新增验证器：放在 `app/validators/`，返回结构化验证结果。
- 新增日志解析器：放在 `app/parsers/`，输出可诊断的归一化事件。
- 调整调度策略：优先查看 `run_service`、`scheduler_service`、`worker_service` 和 `preemption_service`。
- 调整诊断能力：同步维护 `app/rules/core_rules.yaml`、解析器、诊断服务和报告模板。

## 端到端使用示例

以下示例演示从设备连接到任务执行、故障注入、报告生成的完整流程。

### 1. 连接设备并同步

```bash
# 确认 ADB 已识别设备
adb devices

# 同步设备到平台
labctl device sync

# 查看设备列表
labctl device list
```

### 2. 初始化设备池

```bash
# 初始化默认设备池
labctl pool init

# 创建设备池
labctl pool create --name stable --purpose stable --reserved-ratio 0.2 --max-parallel 5
```

### 3. 创建升级计划并下发任务

```bash
# 通过 REST 接口创建升级计划
curl -X POST http://localhost:8000/api/v1/runs/plans \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Android 15 全量升级",
    "upgrade_type": "full",
    "package_path": "ota_packages/full/update.zip",
    "target_build": "android15-userdebug",
    "default_pool_id": 1,
    "parallelism": 1
  }'

# 创建任务（指定设备序列号）
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": 1,
    "device_serial": "ABC123XYZ"
  }'
```

### 4. 启动后台执行器

```bash
# 启动持续监听任务的 worker
labctl worker start
```

### 5. 注入故障（可选）

在升级计划中指定故障类型，例如在升级后执行 Monkey 压测：

```json
{
  "plan_id": 1,
  "device_serial": "ABC123XYZ",
  "options": {
    "fault_plugins": ["monkey_after_upgrade", "storage_pressure"]
  }
}
```

### 6. 查看任务状态与报告

```bash
# 查看任务列表
labctl run list

# 导出 Markdown 报告
labctl report export 1 --format markdown --output report.md

# 导出 HTML 报告
labctl report export 1 --format html --output report.html
```

## 环境变量配置示例

在项目根目录创建 `.env` 文件，填入以下配置：

```env
# 数据库配置
AEGISOTA_DATABASE_URL=sqlite:///./aegisota.db

# 产物与 OTA 包存储路径
AEGISOTA_ARTIFACTS_DIR=artifacts
AEGISOTA_OTA_PACKAGES_DIR=ota_packages

# 任务并发与租约
AEGISOTA_MAX_CONCURRENT_RUNS=5
AEGISOTA_LEASE_DEFAULT_DURATION=3600

# API 密钥配置
AEGISOTA_API_KEY_ENABLED=true
AEGISOTA_API_KEYS=your-secret-key-here,another-key-if-needed

# 日志级别
AEGISOTA_LOG_LEVEL=INFO

# 可选：ADB 路径（如未加入系统 PATH）
# AEGISOTA_ADB_PATH=/path/to/adb

# 可选：设备标签过滤
# AEGISOTA_DEVICE_TAG_FILTER=android14,pixel

# 可选：任务轮询间隔（秒）
# AEGISOTA_WORKER_POLL_INTERVAL=5
```

应用启动时会自动加载 `.env` 文件，所有配置均通过 `app.config.Settings` 管理。

## ADB 验证步骤

在执行 OTA 任务之前，请确保 ADB 连接正常：

### 1. 检查设备连接

```bash
adb devices
```

预期输出：

```text
List of devices attached
ABC123XYZ    device
DEF456UVW    device
```

### 2. 验证设备信息

```bash
# 查看设备型号
adb -s ABC123XYZ shell getprop ro.product.model

# 查看系统版本
adb -s ABC123XYZ shell getprop ro.build.version.release

# 查看电量状态
adb -s ABC123XYZ dumpsys battery

# 查看存储使用情况
adb -s ABC123XYZ shell df /data
```

### 3. 验证 USB 调试授权

如果设备显示 `unauthorized`，请在设备屏幕上点击允许 USB 调试：

```bash
adb devices
# 状态应从 unauthorized 变为 device
```

### 4. 同步设备到平台

```bash
labctl device sync
labctl device list
```

确认设备状态为 `idle` 后即可参与任务调度。

### 5. 常见问题排查

| 问题 | 解决方法 |
| --- | --- |
| 设备未显示 | 检查 USB 连接、开发者选项、USB 调试开关 |
| `no permissions` | 执行 `adb kill-server && adb start-server` |
| `offline` 状态 | 重新插拔 USB 或在设备上撤销并重新授权调试 |
| 多设备命令混淆 | 使用 `-s <serial>` 指定目标设备 |

## 系统架构

```mermaid
graph TB
    subgraph "用户界面"
        Web[网页控制台<br/>Jinja2 + HTMX]
        CLI[labctl CLI<br/>Typer]
        API_Client[REST API 调用方]
    end

    subgraph "FastAPI 服务层"
        Router[路由层]
        Auth[API Key 中间件]
        CSRF[CSRF 保护]
    end

    subgraph "业务服务层"
        DeviceSvc[设备服务]
        PoolSvc[设备池服务]
        RunSvc[任务服务]
        Scheduler[调度服务]
        Preemption[抢占服务]
        Worker[后台执行器]
    end

    subgraph "OTA 执行引擎"
        Executor[RunExecutor]
        Precheck[Precheck]
        PkgPrep[Package Prepare]
        Apply[Apply Update]
        Reboot[Reboot Wait]
        PostVal[Post Validate]
        Report[Report Finalize]
    end

    subgraph "插件体系"
        Faults[故障注入插件]
        Validators[验证器]
        Parsers[日志解析器]
    end

    subgraph "诊断与报告"
        DiagEngine[诊断规则引擎]
        LogParser[日志解析]
        SimilarCase[相似案例召回]
        ReportGen[报告生成器]
    end

    subgraph "持久化"
        SQLite[(SQLite)]
        Artifacts[产物存储<br/>artifacts/]
        OtaPkgs[OTA 包存储]
    end

    subgraph "外部系统"
        ADB[ADB / Fastboot]
        AndroidDevice[Android 设备]
    end

    Web --> Router
    CLI --> Router
    API_Client --> Router
    Router --> Auth
    Router --> CSRF
    Auth --> DeviceSvc
    Auth --> PoolSvc
    Auth --> RunSvc
    Router --> Scheduler
    Scheduler --> Worker
    Worker --> Executor
    RunSvc --> Scheduler
    Preemption --> PoolSvc

    Executor --> Precheck
    Precheck --> PkgPrep
    PkgPrep --> Apply
    Apply --> Reboot
    Reboot --> PostVal
    PostVal --> Report

    Executor --> Faults
    PostVal --> Validators
    Executor --> Parsers

    Report --> DiagEngine
    DiagEngine --> LogParser
    DiagEngine --> SimilarCase
    DiagEngine --> ReportGen

    DeviceSvc --> SQLite
    PoolSvc --> SQLite
    RunSvc --> SQLite
    DiagEngine --> SQLite
    ReportGen --> Artifacts
    PkgPrep --> OtaPkgs

    Executor --> ADB
    ADB --> AndroidDevice
    Validators --> ADB
    Faults --> ADB
```

## 贡献指南

感谢你对 AegisOTA 的关注！我们欢迎各种形式的贡献。

### 开发环境搭建

1. **Fork 并克隆仓库**

```bash
git clone https://github.com/YOUR_USERNAME/AegisOTA.git
cd AegisOTA
```

2. **安装依赖**

```bash
uv sync
```

3. **运行测试确认环境正常**

```bash
pytest
```

### 提交类型

| 类型 | 说明 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `docs` | 文档更新 |
| `style` | 代码格式调整（不影响逻辑） |
| `refactor` | 代码重构 |
| `test` | 测试相关 |
| `chore` | 构建、配置、工具链等 |

### 代码规范

- 使用 `snake_case` 命名模块和函数，`PascalCase` 命名类。
- 新增 Python 代码需包含类型注解。
- 用户可见文本和文档使用中文。
- 保持分层清晰：`api → services → executors/models/utils`。
- 不要绕过 `app.config.Settings`，新配置项使用 `AEGISOTA_` 前缀。
- 任务产物输出到 `artifacts/` 目录，不写入其他路径。

### 提交前检查

```bash
# 格式化
ruff format app tests

# 静态检查
ruff check app tests

# 类型检查
mypy app tests

# 运行测试
pytest
```

### Pull Request 流程

1. 从 `main` 分支创建特性分支：`git checkout -b feat/your-feature`
2. 提交更改并编写清晰的 commit message
3. 确保所有测试通过且 lint 检查无误
4. 推送到你的 Fork 仓库并提交 Pull Request
5. 在 PR 中说明变更内容、动机和相关 issue 编号

### 添加新功能

- **故障插件**：在 `app/faults/` 下实现，遵循 `FaultPlugin` 生命周期，并在测试中添加用例。
- **验证器**：放在 `app/validators/`，返回结构化验证结果。
- **日志解析器**：放在 `app/parsers/`，输出可诊断的归一化事件。
- **API 端点**：请求/响应模型放在 `app/api/schemas.py`，路由保持简洁，业务逻辑放入服务层。
- **调度/执行器变更**：同时审查 `run_service`、`scheduler_service`、`worker_service`、`preemption_service`，注意状态机和租约生命周期。

###  issue 提交

提交 issue 时请包含：

- 问题描述和复现步骤
- 预期行为与实际行为
- 相关日志或截图
- 环境信息（Python 版本、OS、ADB 版本等）

## 许可证

MIT 许可证
