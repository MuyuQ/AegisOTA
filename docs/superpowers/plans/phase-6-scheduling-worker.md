# Phase 6: 多机调度与 Worker

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-step.

**Goal:** 实现多设备任务调度和后台 Worker 执行循环，完成从"脚本"到"平台"的转变。

**Architecture:** Worker 进程轮询数据库，获取预留任务并执行。支持并发上限控制、设备租约管理和自动隔离。

**Tech Stack:** Python, SQLAlchemy, Threading

---

## 文件结构

```
app/services/
├── worker_service.py            # Worker 服务

app/cli/
├── worker.py                    # Worker CLI 命令

tests/test_services/
├── test_worker_service.py
```

---

## Task 6.1: Worker 服务

**Files:**
- Create: `app/services/worker_service.py`
- Create: `tests/test_services/test_worker_service.py`

- [ ] **Step 1: 写 Worker 服务测试**

```python
# tests/test_services/test_worker_service.py
"""Worker 服务测试。"""

import pytest
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DeviceStatus
from app.models.run import UpgradePlan, RunSession, RunStatus, UpgradeType
from app.services.worker_service import WorkerService
from app.services.scheduler_service import SchedulerService
from app.executors.mock_executor import MockExecutor


@pytest.fixture
def test_db():
    """创建测试数据库。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def setup_data(test_db):
    """设置测试数据。"""
    # 创建设备
    device = Device(
        serial="TEST001",
        brand="Test",
        model="TestModel",
        status=DeviceStatus.IDLE,
        battery_level=80,
    )
    test_db.add(device)

    # 创建升级计划
    plan = UpgradePlan(
        name="测试计划",
        upgrade_type=UpgradeType.FULL,
        package_path="/tmp/update.zip",
    )
    test_db.add(plan)
    test_db.commit()

    return {"device": device, "plan": plan}


def test_worker_service_init(test_db):
    """测试 Worker 服务初始化。"""
    worker = WorkerService(test_db)
    assert worker is not None
    assert worker.running is False


def test_worker_can_start_and_stop(test_db):
    """测试 Worker 启动和停止。"""
    worker = WorkerService(test_db, poll_interval=1)

    worker.start()
    assert worker.running is True

    worker.stop()
    time.sleep(0.5)
    assert worker.running is False


def test_worker_process_single_task(test_db, setup_data):
    """测试处理单个任务。"""
    device = setup_data["device"]
    plan = setup_data["plan"]

    # 创建任务
    run = RunSession(
        plan_id=plan.id,
        device_id=device.id,
        status=RunStatus.QUEUED,
    )
    test_db.add(run)
    test_db.commit()

    # 创建 Worker
    executor = MockExecutor.upgrade_success_responses()
    worker = WorkerService(
        test_db,
        runner=executor,
        max_iterations=1,
    )

    # 预留任务
    scheduler = SchedulerService(test_db)
    scheduler.reserve_run(run.id)

    # 执行一轮
    worker.process_one_iteration()

    # 检查任务状态
    test_db.refresh(run)
    assert run.status == RunStatus.PASSED


def test_worker_handles_no_tasks(test_db):
    """测试无任务时的处理。"""
    worker = WorkerService(test_db, max_iterations=0)

    # 无任务时不应该出错
    result = worker.process_one_iteration()
    assert result is None


def test_worker_respects_concurrency_limit(test_db, setup_data):
    """测试并发限制。"""
    device = setup_data["device"]
    plan = setup_data["plan"]

    # 创建多个任务
    for i in range(3):
        run = RunSession(
            plan_id=plan.id,
            device_id=device.id,
            status=RunStatus.QUEUED,
        )
        test_db.add(run)
    test_db.commit()

    # 设置并发上限为 1
    worker = WorkerService(test_db, max_concurrent=1, max_iterations=0)

    # 应该只能启动一个任务
    count = worker.get_running_count()
    assert count == 0  # 初始状态


def test_worker_marks_device_idle_after_completion(test_db, setup_data):
    """测试任务完成后释放设备。"""
    device = setup_data["device"]
    plan = setup_data["plan"]

    run = RunSession(
        plan_id=plan.id,
        device_id=device.id,
        status=RunStatus.QUEUED,
    )
    test_db.add(run)
    test_db.commit()

    scheduler = SchedulerService(test_db)
    scheduler.reserve_run(run.id)

    executor = MockExecutor.upgrade_success_responses()
    worker = WorkerService(test_db, runner=executor, max_iterations=1)
    worker.process_one_iteration()

    test_db.refresh(device)
    assert device.status == DeviceStatus.IDLE
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_services/test_worker_service.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 Worker 服务**

```python
# app/services/worker_service.py
"""Worker 服务模块。"""

import time
import threading
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.executors.command_runner import CommandRunner
from app.executors.run_executor import RunExecutor, MockRunExecutor
from app.executors.run_context import RunContext
from app.executors.mock_executor import MockExecutor
from app.models.device import Device, DeviceStatus
from app.models.run import RunSession, RunStatus, StepName
from app.models.artifact import Artifact, ArtifactType
from app.services.scheduler_service import SchedulerService
from app.services.run_service import RunService
from app.reporting.generator import ReportGenerator
from app.reporting.failure_classifier import FailureCategory


class WorkerService:
    """后台任务执行 Worker。"""

    def __init__(
        self,
        db: Session,
        runner: Optional[CommandRunner] = None,
        poll_interval: int = 5,
        max_concurrent: int = 5,
        max_iterations: int = -1,  # -1 表示无限循环
    ):
        self.db = db
        self.settings = get_settings()
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
        self.max_iterations = max_iterations
        self.running = False
        self._thread: Optional[threading.Thread] = None

        # 执行器
        self.executor = RunExecutor(runner=runner) if runner else RunExecutor()

        # 服务
        self.scheduler = SchedulerService(db)
        self.run_service = RunService(db)
        self.report_generator = ReportGenerator()

    def start(self):
        """启动 Worker。"""
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止 Worker。"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None

    def _run_loop(self):
        """主循环。"""
        iterations = 0

        while self.running:
            if self.max_iterations > 0 and iterations >= self.max_iterations:
                break

            try:
                self.process_one_iteration()
            except Exception as e:
                print(f"Worker iteration error: {e}")

            iterations += 1

            if self.running:
                time.sleep(self.poll_interval)

    def process_one_iteration(self) -> Optional[RunSession]:
        """处理一个任务。"""
        # 检查并发限制
        if not self.scheduler.can_start_new_run():
            return None

        # 获取下一个待执行任务
        next_run = self.scheduler.get_next_run_to_execute()

        if not next_run:
            return None

        # 执行任务
        return self.execute_run(next_run.id)

    def execute_run(self, run_id: int) -> Optional[RunSession]:
        """执行指定任务。"""
        run = self.run_service.get_run_session(run_id)
        if not run:
            return None

        # 获取设备和计划信息
        device = self.db.query(Device).filter_by(id=run.device_id).first()
        plan = run.plan

        if not device or not plan:
            return None

        # 更新状态为运行中
        self.run_service.update_run_status(run_id, RunStatus.RUNNING)

        # 创建执行上下文
        context = RunContext(
            run_id=run_id,
            device_serial=device.serial,
            plan_id=plan.id,
            upgrade_type=plan.upgrade_type.value,
            package_path=plan.package_path,
            target_build=plan.target_build,
        )

        # 执行任务
        execution_result = self.executor.execute(context)

        # 保存产物记录
        self._save_artifacts(run_id, context)

        # 更新任务状态
        if execution_result.success:
            self.run_service.complete_run_session(
                run_id,
                result="success",
                status=RunStatus.PASSED,
                summary=f"升级成功完成，耗时 {execution_result.get_duration_seconds()} 秒",
            )
        else:
            # 分类失败原因
            failure_category = self._classify_failure(
                execution_result.failed_step,
                execution_result.error,
            )

            self.run_service.complete_run_session(
                run_id,
                result="failure",
                status=RunStatus.FAILED,
                summary=f"升级失败：{execution_result.error}",
                failure_category=failure_category.value if failure_category else None,
            )

            # 设备隔离检查
            if failure_category in [
                FailureCategory.BOOT_FAILURE,
                FailureCategory.DEVICE_ENV_ISSUE,
            ]:
                self.scheduler.device_service.quarantine_device(
                    device.serial,
                    reason=f"Task {run_id} failed: {failure_category.value}",
                    run_id=run_id,
                )

        # 释放设备租约
        self.scheduler.release_device_lease(device.id, run_id)

        # 生成报告
        self._generate_report(run, execution_result, context.timeline)

        self.db.refresh(run)
        return run

    def get_running_count(self) -> int:
        """获取正在运行的任务数。"""
        return self.scheduler.get_concurrent_run_count()

    def _classify_failure(
        self,
        failed_step: Optional[StepName],
        error: Optional[str],
    ) -> Optional[FailureCategory]:
        """分类失败原因。"""
        if not failed_step:
            return FailureCategory.UNKNOWN

        from app.reporting.failure_classifier import FailureClassifier
        classifier = FailureClassifier()

        return classifier.classify(
            failed_step.value,
            error or "",
            {},
        )

    def _save_artifacts(self, run_id: int, context: RunContext):
        """保存产物记录到数据库。"""
        artifact_dir = context.artifact_dir

        if not artifact_dir or not artifact_dir.exists():
            return

        for file_path in artifact_dir.iterdir():
            if file_path.is_file():
                artifact_type = self._determine_artifact_type(file_path.name)

                artifact = Artifact(
                    run_id=run_id,
                    artifact_type=artifact_type,
                    path=str(file_path),
                    size=file_path.stat().st_size,
                )
                self.db.add(artifact)

        self.db.commit()

    def _determine_artifact_type(self, filename: str) -> ArtifactType:
        """判断产物类型。"""
        if "logcat" in filename.lower():
            return ArtifactType.LOGCAT
        elif "stdout" in filename.lower():
            return ArtifactType.STDOUT
        elif "stderr" in filename.lower():
            return ArtifactType.STDERR
        elif "monkey" in filename.lower():
            return ArtifactType.MONKEY_RESULT
        elif "timeline" in filename.lower():
            return ArtifactType.TIMELINE
        elif "report" in filename.lower():
            return ArtifactType.REPORT
        else:
            return ArtifactType.STDOUT

    def _generate_report(
        self,
        run: RunSession,
        execution_result,
        timeline: list,
    ):
        """生成任务报告。"""
        report_data = self.report_generator.generate(
            run_id=run.id,
            plan_name=run.plan.name,
            device_serial=run.device.serial,
            status=run.status,
            started_at=run.started_at,
            ended_at=run.ended_at,
            failed_step=execution_result.failed_step.value if execution_result.failed_step else None,
            failure_category=FailureCategory(run.failure_category) if run.failure_category else None,
            timeline=timeline,
            step_results=execution_result.step_results if hasattr(execution_result, 'step_results') else {},
        )

        # 保存报告
        settings = get_settings()
        output_dir = settings.ARTIFACTS_DIR / str(run.id)
        self.report_generator.save_report(report_data, output_dir)
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_services/test_worker_service.py -v`
Expected: PASS - 6 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/services/worker_service.py app/services/__init__.py tests/test_services/test_worker_service.py
git commit -m "feat: add worker service with task execution loop"
```

---

## Task 6.2: Worker CLI 命令

**Files:**
- Create: `app/cli/worker.py`
- Create: `tests/test_cli/test_worker.py`

- [ ] **Step 1: 写 Worker CLI 测试**

```python
# tests/test_cli/test_worker.py
"""Worker CLI 测试。"""

import pytest
from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


def test_worker_help():
    """测试 Worker 帮助信息。"""
    result = runner.invoke(app, ["worker", "--help"])
    assert result.exit_code == 0


def test_worker_start_command():
    """测试 Worker 启动命令。"""
    # 使用 --max-iterations 限制执行次数
    result = runner.invoke(app, ["worker", "start", "--max-iterations", "0"])
    assert result.exit_code == 0


def test_worker_status_command():
    """测试 Worker 状态命令。"""
    result = runner.invoke(app, ["worker", "status"])
    assert result.exit_code == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_cli/test_worker.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 Worker CLI**

```python
# app/cli/worker.py
"""Worker CLI 命令。"""

import signal
import typer

from app.database import SessionLocal
from app.services.worker_service import WorkerService

worker_app = typer.Typer(help="后台任务执行 Worker")

# 全局 Worker 实例
_worker: WorkerService = None


def signal_handler(signum, frame):
    """信号处理器。"""
    global _worker
    if _worker:
        typer.echo("\n停止 Worker...")
        _worker.stop()
        typer.echo("Worker 已停止")


@worker_app.command("start")
def worker_start(
    poll_interval: int = typer.Option(5, "--poll", "-p", help="轮询间隔（秒）"),
    max_concurrent: int = typer.Option(5, "--concurrent", "-c", help="最大并发任务数"),
    max_iterations: int = typer.Option(-1, "--max-iterations", "-n", help="最大迭代次数（-1 为无限）"),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="守护进程模式"),
):
    """启动任务执行 Worker。"""
    global _worker

    typer.echo(f"启动 Worker（轮询间隔: {poll_interval}s, 最大并发: {max_concurrent}）")

    db = SessionLocal()
    _worker = WorkerService(
        db=db,
        poll_interval=poll_interval,
        max_concurrent=max_concurrent,
        max_iterations=max_iterations,
    )

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if max_iterations > 0:
        # 有限次执行
        for _ in range(max_iterations):
            _worker.process_one_iteration()
        typer.echo(f"完成 {max_iterations} 次迭代")
    else:
        # 无限循环
        _worker.start()
        typer.echo("Worker 运行中，按 Ctrl+C 停止")

        # 等待停止信号
        try:
            while _worker.running:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            _worker.stop()


@worker_app.command("status")
def worker_status():
    """查看 Worker 状态。"""
    db = SessionLocal()
    worker = WorkerService(db=db, max_iterations=0)

    running_count = worker.get_running_count()
    pending_count = len(worker.scheduler.list_pending_runs()) if hasattr(worker.scheduler, 'list_pending_runs') else 0

    typer.echo("Worker 状态:")
    typer.echo(f"  正在运行任务: {running_count}")
    typer.echo(f"  待执行任务: {pending_count}")
    typer.echo(f"  最大并发: {worker.max_concurrent}")

    db.close()


@worker_app.command("run-once")
def worker_run_once():
    """执行一次任务轮询。"""
    db = SessionLocal()
    worker = WorkerService(db=db, max_iterations=1)

    typer.echo("执行一次任务轮询...")
    result = worker.process_one_iteration()

    if result:
        typer.echo(f"执行任务 #{result.id}: {result.status}")
    else:
        typer.echo("没有待执行的任务")

    db.close()
```

- [ ] **Step 4: 更新 CLI main.py 添加 worker 命令**

```python
# 更新 app/cli/main.py，添加导入

from app.cli.worker import worker_app

app.add_typer(worker_app, name="worker", help="后台任务执行 Worker")
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_cli/test_worker.py -v`
Expected: PASS - 3 tests passed

- [ ] **Step 6: 提交**

```bash
git add app/cli/worker.py app/cli/main.py tests/test_cli/test_worker.py
git commit -m "feat: add worker CLI commands for task execution"
```

---

## Task 6.3: 完善 API 端点

**Files:**
- Modify: `app/api/devices.py`
- Modify: `app/api/runs.py`
- Modify: `app/api/reports.py`
- Create: `tests/test_api/test_devices.py`
- Create: `tests/test_api/test_runs.py`

- [ ] **Step 1: 写 API 测试**

```python
# tests/test_api/test_devices.py
"""设备 API 测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, SessionLocal
from app.models.device import Device, DeviceStatus


@pytest.fixture
def client():
    """创建测试客户端。"""
    return TestClient(app)


@pytest.fixture
def setup_db():
    """设置测试数据库。"""
    db = SessionLocal()
    device = Device(
        serial="API001",
        brand="Test",
        model="TestModel",
        status=DeviceStatus.IDLE,
        battery_level=80,
    )
    db.add(device)
    db.commit()
    yield db
    db.query(Device).delete()
    db.commit()
    db.close()


def test_list_devices(client, setup_db):
    """测试列出设备。"""
    response = client.get("/api/devices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_device(client, setup_db):
    """测试获取单个设备。"""
    response = client.get("/api/devices/API001")
    assert response.status_code == 200


def test_quarantine_device(client, setup_db):
    """测试隔离设备。"""
    response = client.post("/api/devices/API001/quarantine", json={"reason": "Test"})
    assert response.status_code == 200


def test_recover_device(client, setup_db):
    """测试恢复设备。"""
    # 先隔离
    client.post("/api/devices/API001/quarantine", json={"reason": "Test"})

    response = client.post("/api/devices/API001/recover")
    assert response.status_code == 200
```

```python
# tests/test_api/test_runs.py
"""任务 API 测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.device import Device, DeviceStatus
from app.models.run import UpgradePlan, RunSession, UpgradeType


@pytest.fixture
def client():
    """创建测试客户端。"""
    return TestClient(app)


@pytest.fixture
def setup_data():
    """设置测试数据。"""
    db = SessionLocal()

    device = Device(serial="RUN001", status=DeviceStatus.IDLE, battery_level=80)
    db.add(device)

    plan = UpgradePlan(
        name="测试计划",
        upgrade_type=UpgradeType.FULL,
        package_path="/tmp/update.zip",
    )
    db.add(plan)
    db.commit()

    yield {"db": db, "device": device, "plan": plan}

    db.query(RunSession).delete()
    db.query(UpgradePlan).delete()
    db.query(Device).delete()
    db.commit()
    db.close()


def test_list_runs(client, setup_data):
    """测试列出任务。"""
    response = client.get("/api/runs")
    assert response.status_code == 200


def test_create_run(client, setup_data):
    """测试创建任务。"""
    plan = setup_data["plan"]

    response = client.post("/api/runs", json={
        "plan_id": plan.id,
    })
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data


def test_get_run(client, setup_data):
    """测试获取任务详情。"""
    db = setup_data["db"]
    plan = setup_data["plan"]
    device = setup_data["device"]

    run = RunSession(plan_id=plan.id, device_id=device.id)
    db.add(run)
    db.commit()

    response = client.get(f"/api/runs/{run.id}")
    assert response.status_code == 200


def test_abort_run(client, setup_data):
    """测试终止任务。"""
    db = setup_data["db"]
    plan = setup_data["plan"]
    device = setup_data["device"]

    run = RunSession(plan_id=plan.id, device_id=device.id)
    db.add(run)
    db.commit()

    response = client.post(f"/api/runs/{run.id}/abort")
    assert response.status_code == 200
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_api/ -v`
Expected: FAIL - 多个测试失败，API 未实现

- [ ] **Step 3: 完善设备 API**

```python
# app/api/devices.py
"""设备 API 路由。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device, DeviceStatus
from app.services.device_service import DeviceService
from app.executors.mock_executor import MockExecutor

router = APIRouter()


class DeviceResponse(BaseModel):
    id: int
    serial: str
    brand: Optional[str] = None
    model: Optional[str] = None
    android_version: Optional[str] = None
    status: str
    battery_level: Optional[int] = None
    health_score: float
    tags: List[str] = []
    last_seen_at: Optional[str] = None

    class Config:
        from_attributes = True


class QuarantineRequest(BaseModel):
    reason: str


class TagsUpdate(BaseModel):
    tags: List[str]


@router.get("/devices", response_model=List[DeviceResponse])
async def list_devices(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取设备列表。"""
    service = DeviceService(db)

    device_status = None
    if status:
        try:
            device_status = DeviceStatus(status)
        except ValueError:
            pass

    devices = service.list_devices(status=device_status)

    return [
        DeviceResponse(
            id=d.id,
            serial=d.serial,
            brand=d.brand,
            model=d.model,
            android_version=d.android_version,
            status=d.status.value,
            battery_level=d.battery_level,
            health_score=d.health_score,
            tags=d.get_tags(),
            last_seen_at=d.last_seen_at.isoformat() if d.last_seen_at else None,
        )
        for d in devices
    ]


@router.get("/devices/{serial}", response_model=DeviceResponse)
async def get_device(
    serial: str,
    db: Session = Depends(get_db),
):
    """获取单个设备详情。"""
    service = DeviceService(db)
    device = service.get_device_by_serial(serial)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return DeviceResponse(
        id=device.id,
        serial=device.serial,
        brand=device.brand,
        model=device.model,
        android_version=device.android_version,
        status=device.status.value,
        battery_level=device.battery_level,
        health_score=device.health_score,
        tags=device.get_tags(),
        last_seen_at=device.last_seen_at.isoformat() if device.last_seen_at else None,
    )


@router.post("/devices/sync")
async def sync_devices(db: Session = Depends(get_db)):
    """同步设备状态。"""
    service = DeviceService(db, runner=MockExecutor.default_device_responses())
    devices = service.sync_devices()

    return {"synced": len(devices), "devices": [d.serial for d in devices]}


@router.post("/devices/{serial}/quarantine")
async def quarantine_device(
    serial: str,
    request: QuarantineRequest,
    db: Session = Depends(get_db),
):
    """隔离异常设备。"""
    service = DeviceService(db)
    device = service.quarantine_device(serial, request.reason)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return {"status": "quarantined", "serial": serial, "reason": request.reason}


@router.post("/devices/{serial}/recover")
async def recover_device(
    serial: str,
    db: Session = Depends(get_db),
):
    """恢复隔离设备。"""
    service = DeviceService(db)
    device = service.recover_device(serial)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return {"status": "recovered", "serial": serial, "new_status": device.status.value}


@router.put("/devices/{serial}/tags")
async def update_device_tags(
    serial: str,
    request: TagsUpdate,
    db: Session = Depends(get_db),
):
    """更新设备标签。"""
    service = DeviceService(db)
    device = service.update_device_tags(serial, request.tags)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return {"status": "updated", "serial": serial, "tags": request.tags}
```

- [ ] **Step 4: 完善任务 API**

```python
# app/api/runs.py
"""任务 API 路由。"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.run import RunSession, RunStatus, UpgradePlan, UpgradeType
from app.models.device import Device, DeviceStatus
from app.services.run_service import RunService
from app.services.scheduler_service import SchedulerService

router = APIRouter()


class CreateRunRequest(BaseModel):
    plan_id: int
    device_serial: Optional[str] = None


class RunResponse(BaseModel):
    id: int
    plan_id: int
    device_id: Optional[int] = None
    status: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    result: Optional[str] = None
    failure_category: Optional[str] = None
    summary: Optional[str] = None

    class Config:
        from_attributes = True


class CreatePlanRequest(BaseModel):
    name: str
    upgrade_type: str
    package_path: str
    target_build: Optional[str] = None
    device_selector: Optional[dict] = None
    parallelism: int = 1


@router.get("/runs", response_model=List[RunResponse])
async def list_runs(
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """获取任务列表。"""
    service = RunService(db)

    run_status = None
    if status:
        try:
            run_status = RunStatus(status)
        except ValueError:
            pass

    runs = service.list_runs(status=run_status, limit=limit)

    return [
        RunResponse(
            id=r.id,
            plan_id=r.plan_id,
            device_id=r.device_id,
            status=r.status.value,
            started_at=r.started_at.isoformat() if r.started_at else None,
            ended_at=r.ended_at.isoformat() if r.ended_at else None,
            result=r.result,
            failure_category=r.failure_category,
            summary=r.summary,
        )
        for r in runs
    ]


@router.post("/runs")
async def create_run(
    request: CreateRunRequest,
    db: Session = Depends(get_db),
):
    """创建升级任务。"""
    run_service = RunService(db)
    scheduler = SchedulerService(db)

    # 检查计划是否存在
    plan = run_service.get_upgrade_plan(request.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # 选择设备
    device = None
    if request.device_serial:
        device = db.query(Device).filter_by(serial=request.device_serial).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
    else:
        # 自动选择设备（需要先预留）
        pass

    # 创建任务
    if device:
        run = run_service.create_run_session(
            plan_id=plan.id,
            device_id=device.id,
        )
    else:
        # 无设备，排队等待
        run = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
        db.add(run)
        db.commit()
        db.refresh(run)

    return {"run_id": run.id, "status": run.status.value}


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    """获取任务详情。"""
    service = RunService(db)
    run = service.get_run_session(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunResponse(
        id=run.id,
        plan_id=run.plan_id,
        device_id=run.device_id,
        status=run.status.value,
        started_at=run.started_at.isoformat() if run.started_at else None,
        ended_at=run.ended_at.isoformat() if run.ended_at else None,
        result=run.result,
        failure_category=run.failure_category,
        summary=run.summary,
    )


@router.post("/runs/{run_id}/abort")
async def abort_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    """终止任务。"""
    service = RunService(db)
    run = service.abort_run_session(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found or cannot abort")

    return {"status": "aborted", "run_id": run_id}


@router.post("/runs/{run_id}/reserve")
async def reserve_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    """预留任务（分配设备）。"""
    scheduler = SchedulerService(db)
    success = scheduler.reserve_run(run_id)

    if not success:
        raise HTTPException(status_code=400, detail="Cannot reserve run")

    run = db.query(RunSession).filter_by(id=run_id).first()
    return {"status": "reserved", "run_id": run_id, "device_id": run.device_id}


# 升级计划 API

@router.get("/plans")
async def list_plans(db: Session = Depends(get_db)):
    """列出升级计划。"""
    service = RunService(db)
    plans = service.list_upgrade_plans()

    return [
        {
            "id": p.id,
            "name": p.name,
            "upgrade_type": p.upgrade_type.value,
            "package_path": p.package_path,
            "target_build": p.target_build,
        }
        for p in plans
    ]


@router.post("/plans")
async def create_plan(
    request: CreatePlanRequest,
    db: Session = Depends(get_db),
):
    """创建升级计划。"""
    service = RunService(db)

    try:
        upgrade_type = UpgradeType(request.upgrade_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid upgrade_type")

    plan = service.create_upgrade_plan(
        name=request.name,
        upgrade_type=upgrade_type,
        package_path=request.package_path,
        target_build=request.target_build,
        device_selector=request.device_selector,
        parallelism=request.parallelism,
    )

    return {"plan_id": plan.id, "name": plan.name}
```

- [ ] **Step 5: 完善报告 API**

```python
# app/api/reports.py
"""报告 API 路由。"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.run import RunSession
from app.models.artifact import Artifact
from app.reporting.generator import ReportGenerator

router = APIRouter()


@router.get("/reports/{run_id}")
async def get_report(
    run_id: int,
    db: Session = Depends(get_db),
):
    """获取报告摘要。"""
    run = db.query(RunSession).filter_by(id=run_id).first()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    generator = ReportGenerator()

    report = generator.generate(
        run_id=run.id,
        plan_name=run.plan.name if run.plan else "Unknown",
        device_serial=run.device.serial if run.device else "Unknown",
        status=run.status,
        started_at=run.started_at,
        ended_at=run.ended_at,
        failure_category=run.failure_category,
        timeline=[],
        step_results={},
    )

    return report


@router.get("/reports/{run_id}/html", response_class=HTMLResponse)
async def get_report_html(
    run_id: int,
    db: Session = Depends(get_db),
):
    """获取 HTML 格式报告。"""
    run = db.query(RunSession).filter_by(id=run_id).first()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    generator = ReportGenerator()

    html = generator.generate_html(
        run_id=run.id,
        plan_name=run.plan.name if run.plan else "Unknown",
        device_serial=run.device.serial if run.device else "Unknown",
        status=run.status.value,
        timeline=[],
    )

    return html


@router.get("/reports/{run_id}/markdown", response_class=PlainTextResponse)
async def get_report_markdown(
    run_id: int,
    db: Session = Depends(get_db),
):
    """获取 Markdown 格式报告。"""
    run = db.query(RunSession).filter_by(id=run_id).first()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    generator = ReportGenerator()

    md = generator.generate_markdown(
        run_id=run.id,
        plan_name=run.plan.name if run.plan else "Unknown",
        device_serial=run.device.serial if run.device else "Unknown",
        status=run.status.value,
        timeline=[],
    )

    return md


@router.get("/reports/{run_id}/artifacts")
async def list_artifacts(
    run_id: int,
    db: Session = Depends(get_db),
):
    """列出任务产物。"""
    artifacts = db.query(Artifact).filter_by(run_id=run_id).all()

    return [
        {
            "id": a.id,
            "type": a.artifact_type.value,
            "path": a.path,
            "size": a.size,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in artifacts
    ]
```

- [ ] **Step 6: 运行测试**

Run: `pytest tests/test_api/ -v`
Expected: PASS - all tests passed

- [ ] **Step 7: 提交**

```bash
git add app/api/devices.py app/api/runs.py app/api/reports.py tests/test_api/
git commit -m "feat: complete API endpoints for devices, runs, and reports"
```

---

## Phase 6 完成检查

Run: `pytest tests/test_services/test_worker_service.py tests/test_api/ -v --tb=short`
Expected: All tests pass