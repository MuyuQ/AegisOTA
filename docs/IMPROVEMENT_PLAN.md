# AegisOTA 项目综合改进方案

> 审查日期: 2026-03-28
> 审查范围: 全项目模块、流程、代码质量

---

## 一、执行摘要

本次审查覆盖 AegisOTA 项目的全部核心模块，共发现 **89 个问题**，按优先级分类：

| 优先级 | 数量 | 模块分布 |
|--------|------|----------|
| **Critical (关键)** | 15 | Models(3), Services(4), API(3), Executors(3), Security(2) |
| **High (高)** | 28 | 分布于所有模块 |
| **Medium (中)** | 32 | 分布于所有模块 |
| **Low (低)** | 14 | 代码质量、文档完善 |

---

## 二、关键问题汇总

### 2.1 安全问题 (Security)

| 问题 | 位置 | 影响 |
|------|------|------|
| **无认证机制** | `main.py`, 所有API | 所有接口公开可访问，设置修改、设备隔离等敏感操作无保护 |
| **无CSRF保护** | `devices.html`, `runs.html`, `settings.html` | HTMX POST表单易受跨站请求伪造攻击 |
| **命令注入风险** | `adb_executor.py:34,48` | `shlex.quote()` 缺失，路径含空格时命令会失败或异常 |
| **数据库相对路径** | `config.py:14` | `sqlite:///./aegisota.db` 依赖CWD，可能导致路径遍历 |

**改进措施:**
1. 添加API Key认证中间件
2. 实现Session管理用于Web界面
3. 所有POST表单添加CSRF Token
4. 使用 `shlex.quote()` 或 `subprocess.run(args_list)` 处理命令参数
5. 使用绝对路径配置数据库和目录

---

### 2.2 数据模型问题 (Models)

| 问题 | 位置 | 影响 |
|------|------|------|
| **Report模型缺失** | 全模块 | 规划中的Report模型未实现，报告无法持久化查询 |
| **current_run_id无外键** | `device.py:75` | 数据完整性缺失，无法JOIN查询 |
| **validation_profile_id孤儿字段** | `run.py:103` | ValidationProfile模型不存在 |
| **状态转换验证缺失** | 所有状态模型 | 无 `can_transition_to()` 方法，允许非法状态跳转 |
| **StepName与规划不符** | `run.py:46-55` | `PACKAGE_PREPARE` 应为 `push_package` |

**改进措施:**
1. 创建 `Report` ORM模型持久化报告
2. 添加 `ForeignKey("run_sessions.id")` 到 `current_run_id`
3. 创建 `ValidationProfile` 模型或移除该字段
4. 为所有状态枚举添加转换验证方法
5. 统一 StepName 与规划文档

---

### 2.3 服务层问题 (Services)

| 问题 | 位置 | 影响 |
|------|------|------|
| **设备租约竞态条件** | `scheduler_service.py:23-64` | TOCTOU漏洞，多Worker可同时获取同一设备 |
| **无事务回滚** | `device_service.py`, `run_service.py` | 异常时部分数据可能提交或事务悬挂 |
| **状态转换无验证** | `run_service.py:89-106` | `update_run_status` 允许任意状态更改 |
| **租约争用无重试** | `scheduler_service.py:136-160` | 高并发下任务可能反复失败 |

**改进措施:**
1. 使用 `SELECT FOR UPDATE` 或数据库锁解决竞态
2. 所有服务方法添加 `try/except/rollback` 模式
3. 实现状态机转换验证方法
4. 添加租约获取重试+指数退避机制
5. CLI必须调用服务层方法，禁止直接操作数据库

---

### 2.4 API问题 (API)

| 问题 | 位置 | 影响 |
|------|------|------|
| **无效参数静默忽略** | `devices.py:60-61`, `runs.py:116-118` | 无效状态参数返回200而非400 |
| **KeyError Bug** | `devices.py:235,281,297` | `android_version` vs `system_version` 字段名不一致 |
| **无分页封装** | 所有列表接口 | 大数据量性能问题 |
| **无速率限制** | 所有接口 | 易被滥用攻击 |
| **内联HTML生成** | `devices.py:144-187` | 维护困难，应使用模板 |

**改进措施:**
1. 无效参数返回400 + 明确错误信息
2. **立即修复**字段名不一致Bug
3. 创建 `PaginatedResponse[T]` 分页封装
4. 添加速率限制中间件
5. 将内联HTML迁移到Jinja2模板

---

### 2.5 执行器问题 (Executors)

| 问题 | 位置 | 影响 |
|------|------|------|
| **无幂等性支持** | `step_handlers.py` | 步骤失败后无法从断点恢复 |
| **状态未持久化** | `run_executor.py:99-159` | 执行过程不更新RunSession/RunStep |
| **硬编码远程路径** | `step_handlers.py:201` | `/data/local/tmp/update.zip` 不可配置 |
| **重启等待逻辑简陋** | `step_handlers.py:313-323` | 固定延时而非检测设备离线状态 |

**改进措施:**
1. 实现 `can_resume()` 和 checkpoint机制
2. 每步执行后更新数据库RunStep状态
3. 从RunContext或Settings读取远程路径
4. 重启等待改为：检测设备消失 → wait_for_device → 检测boot_completed

---

### 2.6 故障注入问题 (Faults)

| 问题 | 位置 | 影响 |
|------|------|------|
| **下载中断逻辑错误** | `download_interrupted.py:86-114` | 三种中断点执行相同操作(删除文件) |
| **重启断开模拟无效** | `reboot_interrupted.py:98-102` | `shell("exit")` 不断开ADB连接 |
| **timeout类型未实现** | `reboot_interrupted.py:46,22` | 验证接受但inject不执行 |
| **清理状态Bug** | `storage_pressure.py:189,206` | `_fill_file_path=None` 后返回数据 |
| **4种故障类型缺失** | `FaultType枚举` | PACKAGE_CORRUPTED, LOW_BATTERY, WATCHDOG_FAILURE, PERFORMANCE_REGRESSION |

**改进措施:**
1. `during_download` 创建部分文件，`after_download` 损坏文件
2. 使用 `adb disconnect` 或阻塞wait实现断开模拟
3. 实现timeout类型处理
4. 清理前保存路径到临时变量
5. 实现缺失的4种故障类型

---

## 三、按模块详细改进方案

### 3.1 Models 模块改进

**文件:** `app/models/device.py`, `run.py`, `fault.py`, `artifact.py`

#### 高优先级改进

```python
# 1. 创建 Report 模型 (新文件 app/models/report.py)
class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("run_sessions.id", ondelete="CASCADE"))
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    format: Mapped[str] = mapped_column(String(16))  # json/html/markdown
    content_path: Mapped[str] = mapped_column(String(512))  # 文件路径
    failure_category: Mapped[FailureCategory] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)

# 2. 修复 Device.current_run_id (device.py:75)
current_run_id: Mapped[Optional[int]] = mapped_column(
    Integer, ForeignKey("run_sessions.id", ondelete="SET NULL"), nullable=True
)

# 3. 状态转换验证 (run.py RunSession类)
def can_transition_to(self, new_status: RunStatus) -> bool:
    VALID_TRANSITIONS = {
        RunStatus.QUEUED: [RunStatus.RESERVED, RunStatus.ABORTED],
        RunStatus.RESERVED: [RunStatus.RUNNING, RunStatus.ABORTED],
        RunStatus.RUNNING: [RunStatus.VALIDATING, RunStatus.FAILED, RunStatus.ABORTED],
        RunStatus.VALIDATING: [RunStatus.PASSED, RunStatus.FAILED],
        RunStatus.FAILED: [],  # 终态
        RunStatus.PASSED: [],  # 终态
        RunStatus.ABORTED: [],  # 终态
        RunStatus.QUARANTINED: [RunStatus.QUEUED],  # 恢复后重新排队
    }
    return new_status in VALID_TRANSITIONS.get(self.status, [])
```

#### 中优先级改进

- 添加复合索引: `RunStep(run_id, step_name)`, `DeviceLease(device_id, lease_status)`
- 添加 `LeaseStatus` 枚举使用一致性 (scheduler_service.py:42)
- 修复 `datetime.utcnow()` → `datetime.now(timezone.utc)`
- 添加 `FaultProfile.name` unique约束
- 添加 `RunStep.artifacts` 双向关系

---

### 3.2 Services 模块改进

**文件:** `app/services/scheduler_service.py`, `device_service.py`, `run_service.py`, `worker_service.py`

#### 关键改进: 设备租约竞态修复

```python
# scheduler_service.py - acquire_device_lease 改进
def acquire_device_lease(self, device_id: int, run_id: int) -> Optional[DeviceLease]:
    """使用数据库锁避免竞态"""
    try:
        # 使用 SELECT FOR UPDATE 锁定设备行
        device = self.db.execute(
            select(Device).where(Device.id == device_id).with_for_update()
        ).scalar_one_or_none()

        if device is None or device.status != DeviceStatus.IDLE:
            return None

        # 检查现有租约 (已锁定，不会有新租约插入)
        active_lease = self.db.query(DeviceLease).filter(
            DeviceLease.device_id == device_id,
            DeviceLease.lease_status == LeaseStatus.ACTIVE
        ).first()

        if active_lease:
            return None

        # 创建租约并更新设备
        lease = DeviceLease(
            device_id=device_id,
            run_id=run_id,
            lease_status=LeaseStatus.ACTIVE,
            leased_at=datetime.now(timezone.utc),
            expired_at=datetime.now(timezone.utc) + timedelta(seconds=self.settings.LEASE_TIMEOUT)
        )
        device.status = DeviceStatus.BUSY
        self.db.add(lease)
        self.db.commit()
        return lease
    except Exception:
        self.db.rollback()
        raise
```

#### 服务方法事务模式

```python
# 所有服务方法应遵循此模式
def some_service_method(self, ...):
    try:
        # 业务逻辑
        self.db.commit()
    except Exception as e:
        self.db.rollback()
        logger.error(f"Service error: {e}")
        raise
```

#### CLI服务层集成

| CLI命令 | 当前实现 | 应改为 |
|---------|----------|--------|
| `device sync` | 占位实现 | `DeviceService.sync_devices()` |
| `device quarantine` | 直接修改状态 | `DeviceService.quarantine_device()` |
| `device recover` | 直接修改状态 | `DeviceService.recover_device()` |
| `run submit` | 直接创建RunSession | `RunService.create_run_session()` |
| `run abort` | 直接修改状态 | `RunService.abort_run_session()` |

---

### 3.3 API 模块改进

**文件:** `app/api/devices.py`, `runs.py`, `reports.py`, `settings.py`, `web.py`

#### 紧急Bug修复

```python
# devices.py:224 修复字段名不一致
d = {
    "serial": device.serial,
    "status": device.status.value if hasattr(device.status, 'value') else device.status,
    "health_score": device.health_score,
    "system_version": device.android_version or "-",  # 改为 system_version
    ...
}
```

#### 参数验证改进

```python
# runs.py - 添加参数约束
from pydantic import Field

@router.get("/api/runs")
def list_runs(
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500, description="返回数量上限"),
    offset: int = Query(0, ge=0, description="分页偏移"),
):
    # 无效状态返回400
    if status:
        try:
            run_status = RunStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Valid values: {[s.value for s in RunStatus]}"
            )
```

#### 分页封装

```python
# 新建 app/api/schemas.py
from typing import Generic, TypeVar, List

T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    pagination: dict

    @classmethod
    def create(cls, data: List[T], total: int, limit: int, offset: int):
        return cls(
            data=data,
            pagination={
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(data) < total
            }
        )
```

#### 安全中间件

```python
# main.py - 添加认证中间件
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

# 受保护路由添加依赖
@router.post("/api/devices/sync", dependencies=[Depends(verify_api_key)])
```

---

### 3.4 Executors 模块改进

**文件:** `app/executors/step_handlers.py`, `run_executor.py`, `adb_executor.py`

#### 幂等性实现

```python
# step_handlers.py - 幂等检查模式
class PushPackageHandler(StepHandler):
    step_name = StepName.PACKAGE_PREPARE

    def execute(self, context: RunContext) -> StepHandlerResult:
        # 检查是否已完成
        prev_result = context.step_results.get(self.step_name.value)
        if prev_result and prev_result.get("success"):
            # 验证文件仍存在
            check = self.executor.shell(
                f"ls {prev_result['remote_path']}",
                device=context.device_serial
            )
            if check.success:
                return StepHandlerResult(
                    success=True,
                    message="Package already pushed (skipped)",
                    data=prev_result
                )

        # 正常执行推送
        ...
```

#### 状态持久化

```python
# run_executor.py - 每步更新数据库
def execute(self, context: RunContext) -> RunExecutionResult:
    for step_name in self.steps:
        handler = self._get_handler(step_name)
        # 创建/更新 RunStep 记录
        run_step = self._update_step_status(context.run_id, step_name, StepStatus.RUNNING)

        result = handler.execute(context)

        # 更新步骤状态到数据库
        self._update_step_status(
            context.run_id,
            step_name,
            StepStatus.SUCCESS if result.success else StepStatus.FAILURE,
            result.data
        )

        context.step_results[step_name.value] = result.to_dict()

        if not result.success:
            break
    ...
```

#### 命令安全

```python
# adb_executor.py - 命令参数安全处理
import shlex

def _build_adb_command(self, args: List[str], device: Optional[str] = None) -> List[str]:
    """返回参数列表而非字符串，避免shell解析"""
    cmd = ["adb"]
    if device:
        cmd.extend(["-s", device])
    cmd.extend(args)
    return cmd  # subprocess.run(cmd) 而非 shell=True
```

---

### 3.5 Faults 模块改进

**文件:** `app/faults/download_interrupted.py`, `reboot_interrupted.py`, `storage_pressure.py`

#### 下载中断正确实现

```python
# download_interrupted.py - 各中断点实现
def inject(self, context: RunContext) -> FaultResult:
    remote_path = context.package_path or "/data/local/tmp/update.zip"

    if self.interrupt_point == "before_download":
        # 确保文件不存在
        self.executor.shell(f"rm -f {remote_path}", device=context.device_serial)

    elif self.interrupt_point == "during_download":
        # 创建部分文件模拟下载中断
        partial_size = 1024 * 1024  # 1MB
        self.executor.shell(
            f"dd if=/dev/zero of={remote_path} bs=1024 count={partial_size//1024}",
            device=context.device_serial
        )

    elif self.interrupt_point == "after_download":
        # 损坏已下载文件
        self.executor.shell(
            f"echo 'CORRUPT' >> {remote_path}",
            device=context.device_serial
        )
    ...
```

#### 新增故障类型

```python
# 新文件 app/faults/package_corrupted.py
class PackageCorruptedFault(FaultPlugin):
    fault_type = FaultType.PACKAGE_CORRUPTED
    fault_stage = FaultStage.PRECHECK

    def inject(self, context: RunContext) -> FaultResult:
        # 修改ZIP头部使其损坏
        package_path = context.package_path
        with open(package_path, "r+b") as f:
            f.seek(0)
            f.write(b'\x00\x00')  # 损坏ZIP签名
        ...

# 新文件 app/faults/low_battery.py
class LowBatteryFault(FaultPlugin):
    fault_type = FaultType.LOW_BATTERY
    fault_stage = FaultStage.PRECHECK

    def inject(self, context: RunContext) -> FaultResult:
        # 通过ADB模拟低电量
        self.executor.shell(
            "dumpsys battery set level 5",
            device=context.device_serial
        )
        ...
```

---

### 3.6 Validators 模块改进

**文件:** `app/validators/perf_check.py`, `boot_check.py`, `monkey_runner.py`

#### 内存计算修复

```python
# perf_check.py - 使用正确指标
def _collect_memory_metrics(self, device: str) -> Dict[str, float]:
    output = self.executor.shell("cat /proc/meminfo", device=device).stdout

    # 使用 MemAvailable 而非 MemFree
    mem_available = self._parse_meminfo(output, "MemAvailable")
    mem_total = self._parse_meminfo(output, "MemTotal")

    if mem_total > 0:
        # 实际可用内存百分比
        metrics["memory_available_percent"] = mem_available / mem_total * 100
```

#### ANR检测

```python
# monkey_runner.py - 添加ANR解析
def parse_output(self, output: str) -> Dict[str, int]:
    stats = {"events": 0, "crashes": 0, "anrs": 0, "drops": 0}

    # ANR检测
    anr_match = re.search(r":ANR: (\d+)", output)
    if anr_match:
        stats["anrs"] = int(anr_match.group(1))

    # 或从 dropbox 检查
    anr_check = re.search(r"// ANR:", output)
    ...
```

---

### 3.7 Reporting 模块改进

**文件:** `app/reporting/generator.py`, `failure_classifier.py`

#### Jinja2模板实现

```python
# 新建 app/reporting/templates/report.html
<!DOCTYPE html>
<html>
<head><title>OTA Report - {{ run_id }}</title></head>
<body>
<h1>升级任务报告</h1>
<section class="task-info">
    <p>任务ID: {{ run_id }}</p>
    <p>设备: {{ device_serial }}</p>
    <p>升级类型: {{ upgrade_type }}</p>
    <p>故障配置: {{ fault_profile }}</p>
</section>
<section class="timeline">
    {% for event in timeline %}
    <div class="event">{{ event.timestamp }} - {{ event.step }}</div>
    {% endfor %}
</section>
<section class="artifacts">
    {% for artifact in artifacts %}
    <a href="{{ artifact.path }}">{{ artifact.type }}</a>
    {% endfor %}
</section>
</body>
</html>

# generator.py - 使用模板
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("app/reporting/templates"))

def generate_html(self, data: ReportData) -> str:
    template = env.get_template("report.html")
    return template.render(**data.to_dict())
```

#### 证据链集成

```python
# generator.py - 添加artifacts参数
def generate(
    self,
    run: RunSession,
    step_results: Dict[str, Any],
    timeline: List[Dict[str, Any]],
    artifacts: List[Artifact] = [],  # 新增
) -> ReportData:
    ...
    # 证据链链接
    artifact_chain = [
        {
            "type": a.artifact_type,
            "path": a.file_path,
            "step": a.step_id,
            "created_at": a.created_at.isoformat()
        }
        for a in artifacts
    ]
```

---

### 3.8 Tests 模块改进

**文件:** `tests/test_*.py`

#### 缺失测试补充

| 测试类型 | 新文件位置 | 内容 |
|----------|-----------|------|
| 回滚测试 | `tests/test_rollback.py` | 失败后设备状态恢复、包清理 |
| 状态转换 | `tests/test_models/test_state_transitions.py` | 所有有效/无效转换验证 |
| 租约竞态 | `tests/test_services/test_lease_contention.py` | 并发获取、超时释放 |
| API隔离 | `tests/test_api/*.py` | 使用 `override_get_db` 而非 `SessionLocal()` |

#### API测试隔离修复

```python
# test_devices.py - 正确使用测试数据库
from app.database import get_db
from tests.conftest import override_get_db

# 使用依赖覆盖
app.dependency_overrides[get_db] = override_get_db

@fixture
def client():
    return TestClient(app)
```

---

### 3.9 Web Frontend 改进

**文件:** `app/templates/*.html`, `app/static/css/style.css`

#### 无障碍改进

```html
<!-- devices.html - Modal无障碍 -->
<div id="health-modal"
     role="dialog"
     aria-modal="true"
     aria-labelledby="modal-title">
    <h2 id="modal-title">设备健康详情</h2>
    ...
</div>

<!-- 关联表单标签 -->
<label for="plan-select">升级方案</label>
<select id="plan-select" name="plan_id" required>
```

#### CSRF保护

```html
<!-- base.html - CSRF Token -->
<form hx-post="/api/devices/sync/html">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    ...
</form>
```

#### 响应式表格

```css
/* style.css - 表格响应式 */
.table-responsive {
    overflow-x: auto;
    width: 100%;
}

@media (max-width: 768px) {
    .device-table td:nth-child(4),
    .device-table th:nth-child(4) { display: none; }
}
```

---

### 3.10 Core Config/Database 改进

**文件:** `app/config.py`, `app/database.py`, `app/main.py`

#### 安全配置

```python
# config.py - 添加安全相关配置
class Settings(BaseSettings):
    # 新增安全配置
    SECRET_KEY: str = Field(default="change-me-in-production")
    API_KEY: str = Field(default="")
    CORS_ALLOWED_ORIGINS: List[str] = Field(default=["http://localhost:8000"])
    DEBUG: bool = Field(default=False)

    # 日志配置
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
```

#### 数据库改进

```python
# database.py - 延迟引擎创建
_engine: Optional[Engine] = None

def get_engine(settings: Settings = Depends(get_settings)) -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False}
        )
    return _engine
```

#### CORS和错误处理

```python
# main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request.state.request_id}
    )
```

---

## 四、实施路线图

### Phase 1: 关键问题修复 (Week 1-2)

| 任务 | 模块 | 估计工时 |
|------|------|----------|
| 安全认证中间件 | Core/API | 8h |
| CSRF保护 | Frontend | 4h |
| CLI服务层集成 | CLI/Services | 8h |
| 设备租约竞态修复 | Services | 6h |
| 字段名Bug修复 | API | 2h |
| 命令注入修复 | Executors | 4h |

### Phase 2: 高优先级改进 (Week 3-4)

| 任务 | 模块 | 估计工时 |
|------|------|----------|
| Report模型创建 | Models | 4h |
| 状态转换验证 | Models/Services | 6h |
| 幂等性实现 | Executors | 12h |
| 故障注入逻辑修复 | Faults | 8h |
| 分页封装 | API | 4h |
| 测试补充 | Tests | 16h |

### Phase 3: 中优先级改进 (Week 5-6)

| 任务 | 模块 | 估计工时 |
|------|------|----------|
| Jinja2模板迁移 | Reporting | 6h |
| 无障碍改进 | Frontend | 8h |
| 响应式设计 | Frontend | 8h |
| 缺失故障类型 | Faults | 8h |
| 日志系统 | Core | 4h |
| 复合索引 | Models | 2h |

### Phase 4: 低优先级完善 (Week 7-8)

| 任务 | 模块 | 估计工时 |
|------|------|----------|
| 文档完善 | All | 8h |
| 代码质量清理 | All | 8h |
| 暗黑模式 | Frontend | 4h |
| 国际化支持 | Reporting | 4h |
| 性能优化 | All | 8h |

---

## 五、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 认证添加可能破坏现有客户端 | High | 先添加可选认证，逐步强制 |
| CLI重构可能影响用户习惯 | Medium | 保持命令参数兼容 |
| 幂等性改变执行行为 | Medium | 可配置开关控制 |
| 模板迁移影响报告格式 | Low | 保持JSON格式不变 |

---

## 六、验收标准

### 安全验收

- [ ] 所有API接口需要认证（可配置白名单）
- [ ] 所有POST表单含CSRF Token
- [ ] 命令参数使用安全引用
- [ ] 无SQL注入风险

### 功能验收

- [ ] 状态转换验证100%覆盖
- [ ] 设备租约无竞态条件
- [ ] 步骤执行幂等性支持
- [ ] 报告持久化可查询

### 质量验收

- [ ] 测试覆盖率 > 80%
- [ ] 所有Critical/High问题解决
- [ ] 无障碍性A级标准
- [ ] 移动端基本可用

---

## 七、附录: 完整问题清单

详见各模块独立审查报告：
- `docs/review/models-review.md`
- `docs/review/services-review.md`
- `docs/review/api-review.md`
- `docs/review/executors-review.md`
- `docs/review/faults-review.md`
- `docs/review/validators-review.md`
- `docs/review/reporting-review.md`
- `docs/review/cli-review.md`
- `docs/review/tests-review.md`
- `docs/review/frontend-review.md`
- `docs/review/core-review.md`