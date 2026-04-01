# AegisOTA 整合 LabSentinel 和 TraceLens 设计文档

## 概述

将 LabSentinel（测试机房应急调度与演练平台）和 TraceLens（升级诊断分析工作台）的核心能力整合到 AegisOTA（OTA 升级异常注入测试平台）。

### 整合目标

- **项目定位**：保持 AegisOTA 名称，扩展为"OTA 升级异常注入 + 调度演练 + 诊断分析"平台
- **整合方式**：代码迁移合并，统一维护
- **数据模型**：统一到 AegisOTA 模型框架
- **整合顺序**：先 LabSentinel（设备池化+演练），后 TraceLens（诊断+案例召回）

### 整合能力清单

| 来源 | 能力 | 描述 |
|------|------|------|
| LabSentinel | 设备池化与调度 | 设备池管理、优先级调度、应急容量保留、应急抢占 |
| LabSentinel | 演练引擎 | 演练场景定义、演练执行、演练报告生成 |
| TraceLens | 日志解析与诊断 | recovery/update_engine/logcat 解析、事件标准化、规则引擎匹配 |
| TraceLens | 相似案例召回 | 案例索引构建、相似度计算、召回相似案例 |

## 数据模型设计

### 设备模型扩展

```python
class DeviceStatus(str, Enum):
    """设备状态（扩展为 6 状态）"""
    IDLE = "idle"               # 可用
    RESERVED = "reserved"       # 已分配但任务未开始（新增）
    BUSY = "busy"               # 正在执行任务
    OFFLINE = "offline"         # 离线
    QUARANTINED = "quarantined" # 隔离
    RECOVERING = "recovering"   # 恢复中

class Device(Base):
    """设备实体（扩展字段）"""
    # 现有字段保持不变
    pool_id: Optional[int]          # 新增：所属设备池
    health_score: int               # 统一为 int (0-100)
    sync_failure_count: int         # 新增：同步失败计数

class DevicePool(Base):
    """设备池（新增模型）"""
    id: int
    name: str
    purpose: PoolPurpose            # stable/stress/emergency
    reserved_ratio: float           # 应急容量保留比例
    max_parallel: int               # 最大并行任务数
    tag_selector: dict              # 标签选择器
    devices: List[Device]

class DeviceLease(Base):
    """设备租约（扩展字段）"""
    preemptible: bool               # 新增：是否可被抢占
    preempted_at: Optional[datetime]  # 新增：被抢占时间
    preempted_by_run_id: Optional[int]  # 新增：抢占者任务ID
```

### 任务模型扩展

```python
class RunPriority(str, Enum):
    """任务优先级（新增枚举）"""
    NORMAL = "normal"
    HIGH = "high"
    EMERGENCY = "emergency"

class RunStatus(str, Enum):
    """任务状态（整合为 9 状态）"""
    QUEUED = "queued"           # 排队等待调度
    ALLOCATING = "allocating"   # 正在从设备池分配设备（新增）
    RESERVED = "reserved"       # 设备已预留，等待执行
    RUNNING = "running"         # 执行升级步骤
    VALIDATING = "validating"   # 协议验证阶段（OTA 特有）
    PASSED = "passed"           # 验证通过
    FAILED = "failed"           # 验证失败（含设备隔离导致的失败）
    ABORTED = "aborted"         # 人工终止
    PREEMPTED = "preempted"     # 被应急任务抢占（新增）

class RunSession(Base):
    """任务会话（扩展字段）"""
    priority: RunPriority           # 新增：任务优先级
    pool_id: Optional[int]          # 新增：目标设备池
    preemptible: bool               # 新增：是否可抢占
    drill_id: Optional[int]         # 新增：关联演练 ID
```

**状态流转设计**：

- 设备状态：`IDLE → RESERVED → BUSY → IDLE`（正常流程），`BUSY → QUARANTINED → RECOVERING → IDLE`（异常处理）
- 任务状态：`QUEUED → ALLOCATING → RESERVED → RUNNING → VALIDATING → PASSED/FAILED`

### 演练模型新增

```python
class DrillScenario(Base):
    """演练场景"""
    id: int
    name: str
    scenario_type: DrillType  # emergency_preemption/bulk_offline/capacity_drop
    target_pool_id: int
    config: dict
    enabled: bool

class DrillRun(Base):
    """演练执行"""
    id: int
    scenario_id: int
    status: DrillStatus
    started_at: datetime
    finished_at: datetime
    summary: dict
```

### 诊断模型新增

```python
class DiagnosticResult(Base):
    """诊断结果"""
    id: int
    run_id: int                    # 关联 RunSession
    stage: DiagnosticStage         # precheck/apply/reboot/post_validate
    category: FailureCategory      # 继承现有分类
    root_cause: str
    confidence: float
    key_evidence: List[str]
    next_action: str

class NormalizedEvent(Base):
    """标准化事件"""
    id: int
    run_id: int
    event_type: str
    source: str                    # recovery/update_engine/logcat
    timestamp: datetime
    content: str

class RuleHit(Base):
    """规则命中记录"""
    id: int
    run_id: int
    rule_id: str
    matched_events: List[str]
    priority: int

class SimilarCase(Base):
    """相似案例索引"""
    id: int
    run_id: int                    # 源任务
    similar_run_id: int            # 相似历史任务
    similarity_score: float
```

## 模块架构设计

### 目录结构

```
AegisOTA/
├── app/
│   ├── models/
│   │   ├── device.py         # + DevicePool, Device 扩展
│   │   ├── run.py            # + RunSession 扩展, RunPriority
│   │   ├── drill.py          # 新增：DrillScenario, DrillRun
│   │   ├── diagnostic.py     # 新增：DiagnosticResult, NormalizedEvent
│   │   ├── case.py           # 新增：SimilarCase, CaseLink
│   │   └── enums.py          # 统一枚举定义
│   │
│   ├── services/
│   │   ├── device_service.py     # 现有：设备管理
│   │   ├── run_service.py        # 现有：任务管理
│   │   ├── scheduler_service.py  # 扩展：+ 设备池调度、优先级调度
│   │   ├── pool_service.py       # 新增：设备池管理
│   │   ├── drill_service.py      # 新增：演练引擎
│   │   ├── preemption_service.py # 新增：应急抢占
│   │   ├── diagnose_service.py   # 新增：诊断协调
│   │   ├── rule_service.py       # 新增：规则管理
│   │   ├── case_service.py       # 新增：案例召回
│   │   ├── worker_service.py     # 现有：Worker 管理
│   │   └ recovery_service.py     # 现有：设备恢复
│   │
│   ├── parsers/
│   │   ├── base.py               # 解析器基类
│   │   ├── recovery_parser.py    # recovery.log 解析
│   │   ├── update_engine_parser.py
│   │   ├── logcat_parser.py
│   │   ├── monkey_parser.py
│   │   ├── normalizer.py         # 事件标准化
│   │   └── event_types.py        # 标准化事件类型
│   │
│   ├── rules/
│   │   ├── engine.py             # 规则匹配引擎
│   │   ├── loader.py             # 规则加载器
│   │   └── definitions/          # 规则定义 YAML 文件
│   │
│   ├── reporting/
│   │   ├── generator.py          # 现有：报告生成器（扩展）
│   │   ├── failure_classifier.py # 现有：失败分类器
│   │   ├── diagnostic_report.py  # 新增：诊断报告生成
│   │   └ drill_report.py         # 新增：演练报告生成
│   │
│   ├── executors/            # 现有：命令执行抽象
│   ├── faults/               # 现有：故障注入插件
│   ├── validators/           # 现有：后置验证器
│   │
│   ├── api/
│   │   ├── devices.py        # 现有
│   │   ├── runs.py           # 现有
│   │   ├── drills.py         # 新增
│   │   ├── pools.py          # 新增
│   │   ├── diagnostic.py     # 新增
│   │   └ web.py              # 现有
│   │
│   ├── cli/
│   │   ├── device.py         # 现有
│   │   ├── run.py            # 现有
│   │   ├── drill.py          # 新增
│   │   ├── pool.py           # 新增
│   │   └ diagnostic.py       # 新增
│   │
│   └── templates/
│       ├── devices.html      # 现有
│       ├── runs.html         # 现有
│       ├── drills.html       # 新增
│       ├── pools.html        # 新增
│       └ diagnostic.html     # 新增
│
├── tests/
│   ├── test_models/
│   ├── test_services/
│   ├── test_parsers/         # 新增
│   ├── test_rules/           # 新增
│   └ test_drills/            # 新增
│
└── docs/
```

### 核心服务职责

| 服务 | 职责 |
|-----|-----|
| `scheduler_service` | 扩展为统一调度中心：优先级排序、设备池分配、应急抢占触发 |
| `pool_service` | 设备池 CRUD、容量计算、标签选择器匹配 |
| `drill_service` | 演练场景管理、演练执行、演练结果汇总 |
| `diagnose_service` | 协调诊断流程：解析日志 → 标准化事件 → 规则匹配 → 生成诊断结果 |
| `rule_service` | 规则 CRUD、规则匹配、冲突消解 |
| `case_service` | 案例索引构建、相似度计算、召回相似案例 |

## API 和 CLI 整合设计

### API 端点清单

```python
# === 设备 ===
GET    /api/devices                    # 设备列表
GET    /api/devices/{id}               # 设备详情
POST   /api/devices/sync               # 同步设备状态
POST   /api/devices/{id}/quarantine    # 隔离设备
POST   /api/devices/{id}/recover       # 恢复设备

# === 设备池 ===
GET    /api/pools                      # 设备池列表
GET    /api/pools/{id}                 # 设备池详情
POST   /api/pools                      # 创建设备池
PUT    /api/pools/{id}                 # 更新设备池
DELETE /api/pools/{id}                 # 删除设备池（可选）
POST   /api/pools/{id}/assign          # 分配设备到池
GET    /api/pools/{id}/devices         # 池内设备列表

# === 任务 ===
GET    /api/runs                       # 任务列表
GET    /api/runs/{id}                  # 任务详情
POST   /api/runs                       # 创建任务
POST   /api/runs/{id}/abort            # 终止任务
POST   /api/runs/{id}/diagnostic       # 执行诊断
POST   /api/runs/schedule              # 手动触发调度

# === 诊断 ===
GET    /api/diagnostic/{id}            # 获取诊断结果
GET    /api/diagnostic/events/{run_id} # 获取任务标准化事件
GET    /api/rules                      # 规则列表（只读）

# === 案例召回 ===
GET    /api/cases/similar              # 相似案例（查询参数 run_id）
POST   /api/cases/rebuild-index        # 重建案例索引

# === 演练 ===
GET    /api/drills/scenarios           # 演练场景列表
GET    /api/drills/scenarios/{id}      # 演练场景详情
POST   /api/drills/scenarios           # 创建演练场景
GET    /api/drills                     # 演练执行列表
GET    /api/drills/{id}                # 演练执行详情
POST   /api/drills/start               # 启动演练
POST   /api/drills/{id}/report         # 生成演练报告

# === Web 页面 ===
GET    /                               # 首页 Dashboard
GET    /devices                        # 设备列表页面
GET    /pools                          # 设备池页面
GET    /runs                           # 任务列表页面
GET    /runs/{id}                      # 任务详情页面
GET    /diagnostic                     # 诊断工作台页面
GET    /drills                         # 演练列表页面
```

### CLI 命令清单

```bash
# === 设备 ===
labctl device sync                    # 同步设备
labctl device list [--status STATUS]  # 列出设备
labctl device recover --serial SERIAL # 恢复设备
labctl device quarantine              # 集中隔离异常设备
labctl device pools                   # 快捷查看设备池

# === 设备池 ===
labctl pool list                      # 设备池列表
labctl pool create --name NAME        # 创建设备池
labctl pool update --id ID            # 更新设备池配置
labctl pool show --id ID              # 设备池详情
labctl pool assign --pool-id ID --device-id DEVICE_ID  # 分配设备

# === 任务 ===
labctl run submit --plan PLAN_NAME    # 提交任务
labctl run list [--status STATUS]     # 列出任务
labctl run execute --id ID            # 执行任务
labctl run abort --id ID              # 终止任务
labctl run schedule                   # 手动触发调度
labctl run diagnose --id ID           # 执行诊断

# === 演练 ===
labctl drill scenarios                # 演练场景列表
labctl drill start --scenario SCENARIO_NAME  # 启动演练
labctl drill list                     # 演练执行列表
labctl drill report --id ID           # 生成演练报告

# === 案例召回 ===
labctl cases rebuild-index            # 重建案例索引
labctl cases similar --run-id ID      # 查找相似案例
```

## 整合流程和里程碑

### 阶段划分

```
阶段 1: 设备池化基础（核心基础）
    │
    ├──────────────────┬──────────────────┐
    │                  │                  │
阶段 2: 演练引擎    阶段 3: 日志解析与诊断  ← 可并行
    │                  │                  │
    │                  │                  │
    └──────────────────┴──────────────────┤
                       │
                  阶段 4: 相似案例召回
```

### 阶段 1：设备池化基础（2-3 周）

| 任务 | 描述 | 验收标准 |
|-----|------|---------|
| 数据模型扩展 | Device + DevicePool 模型 | 模型定义通过类型检查 |
| Alembic 迁移脚本 | 设备池表、设备字段迁移 | 迁移脚本可执行，数据完整 |
| pool_service 实现 | 设备池 CRUD | CRUD API 测试通过率 100% |
| scheduler_service 扩展 | 优先级调度 | emergency 任务成功抢占 normal 任务 |
| preemption_service 实现 | 应急抢占逻辑 | 抢占事件正确记录 |
| pools API 实现 | `/api/pools` 端点 | API 文档更新完成 |
| pools CLI 实现 | `labctl pool` 命令 | CLI 测试通过 |
| pools Web 页面 | 设备池管理页面 | 页面可访问、交互正常 |
| 回归测试 | 现有功能不受影响 | 现有测试套件通过率 100% |
| 文档更新 | CLAUDE.md、README | 文档反映新功能 |

### 阶段 2：演练引擎集成（1-2 周，可与阶段 3 并行）

| 任务 | 描述 | 验收标准 |
|-----|------|---------|
| DrillScenario/DrillRun 模型 | 演练数据模型 | 模型定义通过类型检查 |
| drill_service 实现 | 演练场景管理、演练执行 | 三类演练场景可执行 |
| 演练场景定义 | emergency_preemption/bulk_offline/capacity_drop | 场景配置正确加载 |
| drills API 实现 | `/api/drills` 端点 | API 文档更新完成 |
| drills CLI 实现 | `labctl drill` 命令 | CLI 测试通过 |
| drills Web 页面 | 演练管理页面 | 页面可访问、交互正常 |
| drill_report 生成 | 演练报告生成 | 报告可导出 Markdown/HTML |
| 回归测试 | 现有功能不受影响 | 现有测试套件通过率 100% |

### 阶段 3：日志解析与诊断（2-3 周，可与阶段 2 并行）

| 任务 | 描述 | 验收标准 |
|-----|------|---------|
| DiagnosticResult/NormalizedEvent 模型 | 诊断数据模型 | 模型定义通过类型检查 |
| parsers 目录创建 | 解析器基类和具体解析器 | recovery/update_engine/logcat 可解析 |
| normalizer 实现 | 事件标准化逻辑 | 标准化事件正确生成 |
| rules 目录创建 | 规则引擎和规则加载 | 规则可加载、可匹配 |
| 规则定义文件 | OTA 升级故障诊断规则 | 规则覆盖：低电量、bootreason黑名单、存储空间不足、动态分区空间不足、安装中断、下载失败、boot未完成、启动超时、launcher未就绪、monkey崩溃/ANR |
| diagnose_service 实现 | 诊断协调服务 | 诊断流程完整可执行 |
| rule_service 实现 | 规则管理服务 | 规则匹配正确率 ≥ 90% |
| diagnostic API 实现 | `/api/diagnostic` 端点 | API 文档更新完成 |
| diagnostic CLI 实现 | `labctl run diagnose` 命令 | CLI 测试通过 |
| diagnostic Web 页面 | 诊断工作台页面 | 页面可访问、交互正常 |
| reporting 扩展 | diagnostic_report 生成 | 诊断报告可导出 |
| 回归测试 | 现有功能不受影响 | 现有测试套件通过率 100% |

### 阶段 4：相似案例召回（1 周）

| 任务 | 描述 | 验收标准 |
|-----|------|---------|
| SimilarCase 模型 | 相似案例数据模型 | 模型定义通过类型检查 |
| case_service 实现 | 案例索引、相似度计算 | 索引可构建、相似案例可召回 |
| cases API 实现 | `/api/cases` 端点 | API 文档更新完成 |
| cases CLI 实现 | `labctl cases` 命令 | CLI 测试通过 |
| 回归测试 | 现有功能不受影响 | 现有测试套件通过率 100% |

### 总时间估计

| 阶段 | 时间 | 并行情况 |
|-----|------|---------|
| 阶段 1 | 2-3 周 | 独立 |
| 阶段 2 + 阶段 3 | 2-3 周 | 并行开发 |
| 阶段 4 | 1 周 | 独立 |
| **总计** | **5-7 周** | - |

## 默认配置和初始化

### 默认设备池配置

系统初始化时创建三个默认设备池：

```python
DEFAULT_POOLS = [
    {"name": "stable_pool", "purpose": "stable", "reserved_ratio": 0.1, "max_parallel": 5},
    {"name": "stress_pool", "purpose": "stress", "reserved_ratio": 0.2, "max_parallel": 3},
    {"name": "emergency_pool", "purpose": "emergency", "reserved_ratio": 0.5, "max_parallel": 2},
]
```

### 设备初始分配策略

迁移时现有设备默认分配到 `stable_pool`，用户可通过 CLI/API 重新分配。

### 规则定义文件位置

规则定义 YAML 文件存放在 `app/rules/definitions/*.yaml`，默认包含：
- `precheck_rules.yaml`：前置检查阶段规则
- `apply_rules.yaml`：升级执行阶段规则
- `reboot_rules.yaml`：重启等待阶段规则
- `post_validate_rules.yaml`：后置验证阶段规则

## 回滚策略

### 版本标记

每个阶段完成后创建 git tag：
- `v1.0-pool`：阶段 1 完成
- `v1.0-drill`：阶段 2 完成
- `v1.0-diagnostic`：阶段 3 完成
- `v1.0-case`：阶段 4 完成

### 数据库迁移回滚

每个 Alembic 迁移脚本包含 `downgrade()` 方法，支持回滚到上一版本。

### 功能开关

使用配置项控制新功能启用，便于问题排查：

```python
# app/config.py
ENABLE_DEVICE_POOL = True      # 设备池功能开关
ENABLE_DRILL_ENGINE = True     # 演练引擎开关
ENABLE_DIAGNOSTIC = True       # 诊断功能开关
ENABLE_CASE_RECALL = True      # 案例召回开关
```

## 风险评估

| 风险 | 影响 | 缓解措施 |
|-----|-----|---------|
| Device 模型变更影响现有数据 | 数据丢失 | 迁移脚本 + 数据备份 |
| 状态机扩展影响现有流程 | 流程中断 | 回归测试覆盖现有状态转换 |
| 规则定义文件格式错误 | 诊断失败 | 规则加载验证 + 单元测试 |
| 并行开发协调困难 | 代码冲突 | 明确模块边界 + 定期同步 |

## 设计决策记录

1. **移除 RunStatus.quarantined**：避免语义混淆，设备隔离导致的任务失败统一为 `failed` 状态，通过 `failure_category` 区分原因。

2. **保留 UpgradePlan 模型**：不与 JobTemplate 合并，UpgradePlan 是 OTA 升级核心概念，有专用字段（upgrade_type, package_path, fault_profile_id）。

3. **设备池独立 API 路径**：设备池是独立实体，使用 `/api/pools` 而不是 `/api/devices/pools`。

4. **统一诊断命令入口**：诊断作为任务的动作，使用 `labctl run diagnose` 而不是独立的 `labctl diagnose run`。

5. **阶段 2 和 3 并行开发**：演练引擎和诊断系统功能独立，可以并行开发提高效率。