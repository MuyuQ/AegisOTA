# Phase 3: 状态机与任务执行

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现升级任务状态机执行器，完成从任务创建到执行的完整流程。

**Architecture:** 状态机采用阶段驱动模式，每个阶段独立 handler，支持超时、异常注入和产物记录。

**Tech Stack:** Python, SQLAlchemy, ADB Executor

---

## 文件结构

```
app/executors/
├── step_handlers.py            # 各阶段执行 handler
├── run_executor.py             # 状态机驱动器

app/validators/
├── __init__.py
├── boot_check.py               # 开机检测
├── version_check.py            # 版本确认

tests/test_executors/
├── test_step_handlers.py
├── test_run_executor.py
```

---

## Task 3.1: 阶段执行 Handler

**Files:**
- Create: `app/executors/step_handlers.py`
- Create: `tests/test_executors/test_step_handlers.py`

- [ ] **Step 1: 写阶段 Handler 测试**

```python
# tests/test_executors/test_step_handlers.py
"""阶段执行 Handler 测试。"""

import pytest
from pathlib import Path

from app.executors.step_handlers import (
    PrecheckHandler, PushPackageHandler,
    ApplyUpdateHandler, RebootWaitHandler,
    PostValidateHandler,
)
from app.executors.run_context import RunContext, DeviceSnapshot
from app.executors.mock_executor import MockExecutor
from app.models.run import StepName


@pytest.fixture
def mock_executor():
    """创建 Mock 执行器。"""
    return MockExecutor.upgrade_success_responses()


@pytest.fixture
def run_context(tmp_path):
    """创建执行上下文。"""
    return RunContext(
        run_id=1,
        device_serial="ABC123",
        plan_id=1,
        upgrade_type="full",
        package_path="/tmp/update.zip",
        artifact_dir=tmp_path / "artifacts" / "1",
    )


def test_precheck_handler_interface():
    """测试 Precheck Handler 接口。"""
    handler = PrecheckHandler()
    assert handler.step_name == StepName.PRECHECK
    assert hasattr(handler, 'execute')


def test_precheck_handler_success(mock_executor, run_context):
    """测试 Precheck 成功执行。"""
    handler = PrecheckHandler(executor=mock_executor)
    result = handler.execute(run_context)

    assert result.success is True
    assert "device_online" in result.data


def test_push_package_handler_success(mock_executor, run_context):
    """测试推送包成功。"""
    handler = PushPackageHandler(executor=mock_executor)
    result = handler.execute(run_context)

    assert result.success is True
    assert "push_time" in result.data


def test_apply_update_handler_interface():
    """测试 ApplyUpdate Handler 接口。"""
    handler = ApplyUpdateHandler()
    assert handler.step_name == StepName.APPLY_UPDATE


def test_reboot_wait_handler_timeout(mock_executor, run_context):
    """测试重启等待。"""
    handler = RebootWaitHandler(executor=mock_executor, timeout=60)
    result = handler.execute(run_context)

    assert result.success is True


def test_post_validate_handler_success(mock_executor, run_context):
    """测试升级后验证。"""
    handler = PostValidateHandler(executor=mock_executor)
    result = handler.execute(run_context)

    assert result.success is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_executors/test_step_handlers.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现阶段 Handler**

```python
# app/executors/step_handlers.py
"""任务执行阶段 Handler。"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import get_settings
from app.executors.command_runner import CommandResult
from app.executors.adb_executor import ADBExecutor
from app.executors.run_context import RunContext
from app.models.run import StepName


@dataclass
class StepHandlerResult:
    """阶段执行结果。"""

    success: bool
    step_name: StepName
    message: str
    data: Dict[str, Any]
    duration_ms: int
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "success": self.success,
            "step_name": self.step_name.value,
            "message": self.message,
            "data": self.data,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class StepHandler(ABC):
    """阶段执行 Handler 抽象基类。"""

    step_name: StepName = None
    timeout: int = 300

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        timeout: Optional[int] = None,
    ):
        self.settings = get_settings()
        self.timeout = timeout or self.settings.DEFAULT_TIMEOUT
        self.executor = executor or ADBExecutor()

    @abstractmethod
    def execute(self, context: RunContext) -> StepHandlerResult:
        """执行阶段逻辑。"""
        pass

    def _save_artifact(
        self,
        context: RunContext,
        name: str,
        content: str,
    ) -> Path:
        """保存产物文件。"""
        artifact_path = context.artifact_dir / name
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        with open(artifact_path, "w") as f:
            f.write(content)

        return artifact_path

    def _record_command(
        self,
        context: RunContext,
        command: str,
        result: CommandResult,
    ) -> None:
        """记录命令执行结果。"""
        context.record_event(
            "command",
            command,
            {
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
            }
        )


class PrecheckHandler(StepHandler):
    """升级前检查 Handler。"""

    step_name = StepName.PRECHECK

    def execute(self, context: RunContext) -> StepHandlerResult:
        """执行升级前检查。"""
        start_time = time.time()

        context.record_event("step_start", "precheck")
        context.current_step = "precheck"

        # 检查设备在线
        devices = self.executor.devices()
        device_online = any(
            d["serial"] == context.device_serial
            for d in devices
        )

        if not device_online:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="设备离线",
                data={"device_online": False},
                duration_ms=int((time.time() - start_time) * 1000),
                error="Device not found in adb devices",
            )

        # 获取设备属性
        props = self.executor.getprop(device=context.device_serial)

        # 检查电量
        battery_level = None
        battery_result = self.executor.shell(
            "dumpsys battery | grep level",
            device=context.device_serial,
        )
        if battery_result.success:
            import re
            match = re.search(r"level: (\d+)", battery_result.stdout)
            if match:
                battery_level = int(match.group(1))

        if battery_level and battery_level < 20:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="电量不足",
                data={"battery_level": battery_level},
                duration_ms=int((time.time() - start_time) * 1000),
                error=f"Battery level too low: {battery_level}%",
            )

        # 更新上下文
        context.device = DeviceSnapshot(
            serial=context.device_serial,
            brand=props.get("ro.product.brand"),
            model=props.get("ro.product.model"),
            android_version=props.get("ro.build.version.release"),
            battery_level=battery_level,
            build_fingerprint=props.get("ro.build.fingerprint"),
            boot_completed=props.get("sys.boot_completed") == "1",
        )

        # 保存设备信息
        self._save_artifact(
            context,
            "precheck_device_info.json",
            str(props),
        )

        context.record_event("step_end", "precheck", {"success": True})

        return StepHandlerResult(
            success=True,
            step_name=self.step_name,
            message="升级前检查通过",
            data={
                "device_online": True,
                "battery_level": battery_level,
                "android_version": props.get("ro.build.version.release"),
            },
            duration_ms=int((time.time() - start_time) * 1000),
        )


class PushPackageHandler(StepHandler):
    """推送升级包 Handler。"""

    step_name = StepName.PACKAGE_PREPARE

    def execute(self, context: RunContext) -> StepHandlerResult:
        """推送升级包到设备。"""
        start_time = time.time()

        context.record_event("step_start", "push_package")

        if not context.package_path:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="未指定升级包路径",
                data={},
                duration_ms=int((time.time() - start_time) * 1000),
                error="No package_path in context",
            )

        # 推送升级包
        remote_path = "/data/local/tmp/update.zip"
        result = self.executor.push(
            context.package_path,
            remote_path,
            device=context.device_serial,
            timeout=self.timeout,
        )

        self._record_command(context, f"push {context.package_path}", result)

        if not result.success:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="推送升级包失败",
                data={"stderr": result.stderr},
                duration_ms=int((time.time() - start_time) * 1000),
                error=result.stderr,
            )

        # 保存命令输出
        self._save_artifact(context, "push_stdout.txt", result.stdout)

        context.record_event("step_end", "push_package", {"success": True})

        return StepHandlerResult(
            success=True,
            step_name=self.step_name,
            message="升级包推送成功",
            data={
                "push_time": result.duration_ms,
                "remote_path": remote_path,
            },
            duration_ms=int((time.time() - start_time) * 1000),
        )


class ApplyUpdateHandler(StepHandler):
    """应用升级 Handler。"""

    step_name = StepName.APPLY_UPDATE
    timeout = 180

    def execute(self, context: RunContext) -> StepHandlerResult:
        """执行升级命令。"""
        start_time = time.time()

        context.record_event("step_start", "apply_update")

        # 执行升级命令（使用系统升级机制）
        # 实际命令取决于设备和升级类型
        upgrade_command = self._build_upgrade_command(context)
        result = self.executor.shell(
            upgrade_command,
            device=context.device_serial,
            timeout=self.timeout,
        )

        self._record_command(context, upgrade_command, result)
        self._save_artifact(context, "apply_update_stdout.txt", result.stdout)

        if not result.success:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="升级命令执行失败",
                data={"stderr": result.stderr},
                duration_ms=int((time.time() - start_time) * 1000),
                error=result.stderr,
            )

        context.record_event("step_end", "apply_update", {"success": True})

        return StepHandlerResult(
            success=True,
            step_name=self.step_name,
            message="升级命令执行成功",
            data={"upgrade_command": upgrade_command},
            duration_ms=int((time.time() - start_time) * 1000),
        )

    def _build_upgrade_command(self, context: RunContext) -> str:
        """构建升级命令。"""
        # 模拟升级命令（实际实现需要根据设备类型调整）
        if context.upgrade_type == "full":
            return "am broadcast -a android.intent.action.UPDATE_SYSTEM"
        elif context.upgrade_type == "incremental":
            return "am broadcast -a android.intent.action.APPLY_PATCH"
        else:
            return "echo 'Upgrade command placeholder'"


class RebootWaitHandler(StepHandler):
    """重启等待 Handler。"""

    step_name = StepName.REBOOT_WAIT
    timeout = 120

    def execute(self, context: RunContext) -> StepHandlerResult:
        """重启设备并等待启动完成。"""
        start_time = time.time()

        context.record_event("step_start", "reboot_wait")

        # 发送重启命令
        reboot_result = self.executor.reboot(device=context.device_serial)
        self._record_command(context, "reboot", reboot_result)

        # 等待设备重启完成
        boot_timeout = self.timeout
        wait_start = time.time()

        # 等待设备离线
        time.sleep(5)

        # 等待设备重新上线
        while time.time() - wait_start < boot_timeout:
            props = self.executor.getprop(device=context.device_serial)

            if props.get("sys.boot_completed") == "1":
                break

            time.sleep(2)

        # 检查是否启动完成
        final_props = self.executor.getprop(device=context.device_serial)
        boot_completed = final_props.get("sys.boot_completed") == "1"

        if not boot_completed:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="重启等待超时",
                data={"timeout": boot_timeout},
                duration_ms=int((time.time() - start_time) * 1000),
                error=f"Device did not boot within {boot_timeout} seconds",
            )

        context.record_event("step_end", "reboot_wait", {"success": True})

        return StepHandlerResult(
            success=True,
            step_name=self.step_name,
            message="设备重启完成",
            data={
                "boot_time": int((time.time() - wait_start) * 1000),
                "boot_completed": True,
            },
            duration_ms=int((time.time() - start_time) * 1000),
        )


class PostValidateHandler(StepHandler):
    """升级后验证 Handler。"""

    step_name = StepName.POST_VALIDATE

    def execute(self, context: RunContext) -> StepHandlerResult:
        """执行升级后验证。"""
        start_time = time.time()

        context.record_event("step_start", "post_validate")

        # 检查版本
        props = self.executor.getprop(device=context.device_serial)
        current_version = props.get("ro.build.fingerprint")

        # 检查开机完成
        boot_completed = props.get("sys.boot_completed") == "1"

        if not boot_completed:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="系统未完成启动",
                data={"boot_completed": False},
                duration_ms=int((time.time() - start_time) * 1000),
                error="sys.boot_completed != 1",
            )

        # 保存验证结果
        validation_data = {
            "current_version": current_version,
            "boot_completed": boot_completed,
            "validation_time": datetime.utcnow().isoformat(),
        }

        self._save_artifact(
            context,
            "post_validate_result.json",
            str(validation_data),
        )

        context.record_event("step_end", "post_validate", {"success": True})

        return StepHandlerResult(
            success=True,
            step_name=self.step_name,
            message="升级后验证通过",
            data=validation_data,
            duration_ms=int((time.time() - start_time) * 1000),
        )
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_executors/test_step_handlers.py -v`
Expected: PASS - 6 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/executors/step_handlers.py tests/test_executors/test_step_handlers.py
git commit -m "feat: add step handlers for upgrade state machine"
```

---

## Task 3.2: 状态机驱动器

**Files:**
- Create: `app/executors/run_executor.py`
- Create: `tests/test_executors/test_run_executor.py`

- [ ] **Step 1: 写状态机驱动器测试**

```python
# tests/test_executors/test_run_executor.py
"""状态机驱动器测试。"""

import pytest
from pathlib import Path

from app.executors.run_executor import RunExecutor
from app.executors.run_context import RunContext
from app.executors.mock_executor import MockExecutor
from app.models.run import StepName


@pytest.fixture
def mock_executor():
    """创建 Mock 执行器。"""
    return MockExecutor.upgrade_success_responses()


@pytest.fixture
def run_context(tmp_path):
    """创建执行上下文。"""
    return RunContext(
        run_id=1,
        device_serial="ABC123",
        plan_id=1,
        upgrade_type="full",
        package_path="/tmp/update.zip",
        artifact_dir=tmp_path / "artifacts" / "1",
    )


def test_run_executor_init():
    """测试状态机初始化。"""
    executor = RunExecutor()
    assert len(executor.handlers) > 0


def test_run_executor_steps():
    """测试状态机步骤顺序。"""
    executor = RunExecutor()
    steps = executor.get_step_names()

    assert StepName.PRECHECK in steps
    assert StepName.APPLY_UPDATE in steps
    assert StepName.REBOOT_WAIT in steps


def test_run_executor_execute_full(mock_executor, run_context):
    """测试完整执行流程。"""
    executor = RunExecutor(mock_executor)
    result = executor.execute(run_context)

    assert result.success is True
    assert len(result.step_results) == len(executor.handlers)


def test_run_executor_stop_on_failure():
    """测试失败时停止执行。"""
    # 创建会失败的 Mock 执行器
    fail_executor = MockExecutor()
    fail_executor.set_response("adb devices", stdout="")  # 无设备

    executor = RunExecutor(fail_executor)

    context = RunContext(
        run_id=1,
        device_serial="ABC123",
        plan_id=1,
        upgrade_type="full",
    )

    result = executor.execute(context)

    assert result.success is False
    # 应该在 precheck 就停止
    assert len(result.step_results) == 1


def test_run_executor_record_timeline(mock_executor, run_context):
    """测试时间线记录。"""
    executor = RunExecutor(mock_executor)
    executor.execute(run_context)

    assert len(run_context.timeline) > 0
    # 应包含步骤开始和结束事件
    events = [e["event_type"] for e in run_context.timeline]
    assert "step_start" in events or "step_end" in events
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_executors/test_run_executor.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现状态机驱动器**

```python
# app/executors/run_executor.py
"""任务执行状态机驱动器。"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.config import get_settings
from app.executors.command_runner import CommandRunner
from app.executors.adb_executor import ADBExecutor
from app.executors.mock_executor import MockExecutor
from app.executors.run_context import RunContext
from app.executors.step_handlers import (
    StepHandler, StepHandlerResult,
    PrecheckHandler, PushPackageHandler,
    ApplyUpdateHandler, RebootWaitHandler,
    PostValidateHandler,
)
from app.models.run import StepName


@dataclass
class RunExecutionResult:
    """任务执行结果。"""

    success: bool
    run_id: int
    started_at: datetime
    ended_at: datetime
    step_results: Dict[str, StepHandlerResult] = field(default_factory=dict)
    failed_step: Optional[StepName] = None
    error: Optional[str] = None
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    def get_duration_seconds(self) -> int:
        """获取总执行时长。"""
        return int((self.ended_at - self.started_at).total_seconds())

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "success": self.success,
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "duration_seconds": self.get_duration_seconds(),
            "failed_step": self.failed_step.value if self.failed_step else None,
            "error": self.error,
            "steps": {
                name: result.to_dict()
                for name, result in self.step_results.items()
            },
        }


class RunExecutor:
    """任务执行状态机。"""

    # 默认执行步骤顺序
    DEFAULT_STEPS = [
        StepName.PRECHECK,
        StepName.PACKAGE_PREPARE,
        StepName.APPLY_UPDATE,
        StepName.REBOOT_WAIT,
        StepName.POST_VALIDATE,
    ]

    def __init__(
        self,
        runner: Optional[CommandRunner] = None,
        custom_handlers: Optional[Dict[StepName, StepHandler]] = None,
    ):
        self.settings = get_settings()
        self.runner = runner

        # 初始化 handler
        self.handlers: Dict[StepName, StepHandler] = custom_handlers or self._create_default_handlers()

    def _create_default_handlers(self) -> Dict[StepName, StepHandler]:
        """创建默认 handler 集合。"""
        executor = ADBExecutor(runner=self.runner) if self.runner else ADBExecutor()

        return {
            StepName.PRECHECK: PrecheckHandler(executor=executor),
            StepName.PACKAGE_PREPARE: PushPackageHandler(executor=executor),
            StepName.APPLY_UPDATE: ApplyUpdateHandler(executor=executor),
            StepName.REBOOT_WAIT: RebootWaitHandler(executor=executor),
            StepName.POST_VALIDATE: PostValidateHandler(executor=executor),
        }

    def get_step_names(self) -> List[StepName]:
        """获取执行步骤名称列表。"""
        return self.DEFAULT_STEPS

    def execute(self, context: RunContext) -> RunExecutionResult:
        """执行完整任务流程。"""
        started_at = datetime.utcnow()
        context.started_at = started_at

        context.record_event("run_start", f"Starting run {context.run_id}")

        step_results: Dict[str, StepHandlerResult] = {}
        failed_step: Optional[StepName] = None
        error: Optional[str] = None

        # 按顺序执行各阶段
        for step_name in self.DEFAULT_STEPS:
            handler = self.handlers.get(step_name)
            if not handler:
                continue

            # 执行阶段
            result = handler.execute(context)
            step_results[step_name.value] = result

            # 记录结果到上下文
            context.set_step_result(step_name.value, result.to_dict())

            # 检查是否失败
            if not result.success:
                failed_step = step_name
                error = result.error
                context.record_event(
                    "step_failure",
                    f"Step {step_name.value} failed: {result.message}",
                    {"error": result.error}
                )
                break

            context.record_event(
                "step_success",
                f"Step {step_name.value} completed",
            )

        ended_at = datetime.utcnow()

        # 保存时间线
        timeline_file = context.artifact_dir / "timeline.json"
        with open(timeline_file, "w") as f:
            import json
            json.dump(context.timeline, f, indent=2)

        context.record_event("run_end", f"Run {context.run_id} ended")

        return RunExecutionResult(
            success=(failed_step is None),
            run_id=context.run_id,
            started_at=started_at,
            ended_at=ended_at,
            step_results=step_results,
            failed_step=failed_step,
            error=error,
            timeline=context.timeline,
        )

    def execute_step(
        self,
        step_name: StepName,
        context: RunContext,
    ) -> StepHandlerResult:
        """执行单个阶段。"""
        handler = self.handlers.get(step_name)
        if not handler:
            return StepHandlerResult(
                success=False,
                step_name=step_name,
                message="Handler not found",
                data={},
                duration_ms=0,
                error=f"No handler for step {step_name}",
            )

        return handler.execute(context)


class MockRunExecutor(RunExecutor):
    """Mock 状态机执行器（用于测试）。"""

    def __init__(self, mock_executor: Optional[MockExecutor] = None):
        executor = mock_executor or MockExecutor.upgrade_success_responses()

        handlers = {
            StepName.PRECHECK: PrecheckHandler(executor=executor),
            StepName.PACKAGE_PREPARE: PushPackageHandler(executor=executor),
            StepName.APPLY_UPDATE: ApplyUpdateHandler(executor=executor),
            StepName.REBOOT_WAIT: RebootWaitHandler(executor=executor),
            StepName.POST_VALIDATE: PostValidateHandler(executor=executor),
        }

        super().__init__(custom_handlers=handlers)
```

- [ ] **Step 4: 更新 executors/__init__.py**

```python
# app/executors/__init__.py
"""执行器模块。"""

from app.executors.command_runner import CommandRunner, CommandResult, ShellCommandRunner
from app.executors.adb_executor import ADBExecutor
from app.executors.mock_executor import MockExecutor
from app.executors.run_context import RunContext, DeviceSnapshot
from app.executors.step_handlers import (
    StepHandler, StepHandlerResult,
    PrecheckHandler, PushPackageHandler,
    ApplyUpdateHandler, RebootWaitHandler,
    PostValidateHandler,
)
from app.executors.run_executor import RunExecutor, RunExecutionResult, MockRunExecutor

__all__ = [
    "CommandRunner",
    "CommandResult",
    "ShellCommandRunner",
    "ADBExecutor",
    "MockExecutor",
    "RunContext",
    "DeviceSnapshot",
    "StepHandler",
    "StepHandlerResult",
    "PrecheckHandler",
    "PushPackageHandler",
    "ApplyUpdateHandler",
    "RebootWaitHandler",
    "PostValidateHandler",
    "RunExecutor",
    "RunExecutionResult",
    "MockRunExecutor",
]
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_executors/test_run_executor.py -v`
Expected: PASS - 5 tests passed

- [ ] **Step 6: 提交**

```bash
git add app/executors/run_executor.py app/executors/__init__.py tests/test_executors/test_run_executor.py
git commit -m "feat: add run executor state machine with full pipeline support"
```

---

## Task 3.3: 升级后验证器

**Files:**
- Create: `app/validators/__init__.py`
- Create: `app/validators/boot_check.py`
- Create: `app/validators/version_check.py`
- Create: `tests/test_validators/test_boot_check.py`
- Create: `tests/test_validators/test_version_check.py`

- [ ] **Step 1: 写验证器测试**

```python
# tests/test_validators/test_boot_check.py
"""开机检测测试。"""

import pytest

from app.validators.boot_check import BootChecker
from app.executors.mock_executor import MockExecutor


def test_boot_checker_success():
    """测试开机检测成功。"""
    executor = MockExecutor()
    executor.set_response(
        "adb shell getprop sys.boot_completed",
        stdout="1\n"
    )

    checker = BootChecker(executor)
    result = checker.check("ABC123")

    assert result.passed is True


def test_boot_checker_failure():
    """测试开机检测失败。"""
    executor = MockExecutor()
    executor.set_response(
        "adb shell getprop sys.boot_completed",
        stdout="0\n"
    )

    checker = BootChecker(executor)
    result = checker.check("ABC123")

    assert result.passed is False


def test_boot_checker_timeout():
    """测试开机检测超时。"""
    executor = MockExecutor()
    # 返回空响应模拟超时
    executor.set_response("adb shell getprop", stdout="")

    checker = BootChecker(executor, timeout=30)
    result = checker.check("ABC123")

    assert result.passed is False


def test_boot_checker_with_wait():
    """测试等待开机完成。"""
    executor = MockExecutor()
    # 先返回未完成，再返回完成
    executor.set_response("adb shell getprop sys.boot_completed", stdout="1\n")

    checker = BootChecker(executor)
    result = checker.wait_for_boot("ABC123", timeout=60)

    assert result.passed is True
```

```python
# tests/test_validators/test_version_check.py
"""版本确认测试。"""

import pytest

from app.validators.version_check import VersionChecker
from app.executors.mock_executor import MockExecutor


def test_version_checker_success():
    """测试版本确认成功。"""
    executor = MockExecutor()
    executor.set_response(
        "adb shell getprop ro.build.fingerprint",
        stdout="Google/oriole/oriole:14/AP1A.240305.019\n"
    )

    checker = VersionChecker(executor)
    result = checker.check("ABC123", expected="AP1A.240305.019")

    assert result.passed is True
    assert result.current_version == "Google/oriole/oriole:14/AP1A.240305.019"


def test_version_checker_mismatch():
    """测试版本不匹配。"""
    executor = MockExecutor()
    executor.set_response(
        "adb shell getprop ro.build.fingerprint",
        stdout="Google/oriole/oriole:13/OLD_VERSION\n"
    )

    checker = VersionChecker(executor)
    result = checker.check("ABC123", expected="AP1A.240305.019")

    assert result.passed is False
    assert "mismatch" in result.message.lower()


def test_version_checker_get_version():
    """测试获取版本信息。"""
    executor = MockExecutor()
    executor.set_response(
        "adb shell getprop",
        stdout="[ro.build.version.release]: [14]\n[ro.build.fingerprint]: [TEST_FP]\n"
    )

    checker = VersionChecker(executor)
    version_info = checker.get_version_info("ABC123")

    assert version_info["android_version"] == "14"
    assert version_info["fingerprint"] == "TEST_FP"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_validators/ -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现验证器**

```python
# app/validators/__init__.py
"""验证器模块。"""

from app.validators.boot_check import BootChecker, BootCheckResult
from app.validators.version_check import VersionChecker, VersionCheckResult

__all__ = [
    "BootChecker",
    "BootCheckResult",
    "VersionChecker",
    "VersionCheckResult",
]
```

```python
# app/validators/boot_check.py
"""开机检测验证器。"""

import time
from dataclasses import dataclass
from typing import Optional

from app.executors.adb_executor import ADBExecutor
from app.config import get_settings


@dataclass
class BootCheckResult:
    """开机检测结果。"""

    passed: bool
    device_serial: str
    boot_completed: bool
    message: str
    wait_time_ms: Optional[int] = None

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "passed": self.passed,
            "device_serial": self.device_serial,
            "boot_completed": self.boot_completed,
            "message": self.message,
            "wait_time_ms": self.wait_time_ms,
        }


class BootChecker:
    """开机检测器。"""

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        timeout: int = 90,
    ):
        self.executor = executor or ADBExecutor()
        self.timeout = timeout or get_settings().BOOT_COMPLETE_TIMEOUT

    def check(self, device_serial: str) -> BootCheckResult:
        """检查设备开机状态。"""
        props = self.executor.getprop(device=device_serial)
        boot_completed = props.get("sys.boot_completed", "0") == "1"

        if boot_completed:
            return BootCheckResult(
                passed=True,
                device_serial=device_serial,
                boot_completed=True,
                message="系统已完成启动",
            )
        else:
            return BootCheckResult(
                passed=False,
                device_serial=device_serial,
                boot_completed=False,
                message="系统未完成启动",
            )

    def wait_for_boot(
        self,
        device_serial: str,
        timeout: Optional[int] = None,
    ) -> BootCheckResult:
        """等待设备开机完成。"""
        wait_timeout = timeout or self.timeout
        start_time = time.time()

        while time.time() - start_time < wait_timeout:
            result = self.check(device_serial)

            if result.boot_completed:
                wait_time_ms = int((time.time() - start_time) * 1000)
                return BootCheckResult(
                    passed=True,
                    device_serial=device_serial,
                    boot_completed=True,
                    message=f"开机完成，等待 {wait_time_ms}ms",
                    wait_time_ms=wait_time_ms,
                )

            time.sleep(2)

        # 超时
        wait_time_ms = int((time.time() - start_time) * 1000)
        return BootCheckResult(
            passed=False,
            device_serial=device_serial,
            boot_completed=False,
            message=f"等待开机超时（{wait_timeout}秒）",
            wait_time_ms=wait_time_ms,
        )
```

```python
# app/validators/version_check.py
"""版本确认验证器。"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

from app.executors.adb_executor import ADBExecutor


@dataclass
class VersionCheckResult:
    """版本确认结果。"""

    passed: bool
    device_serial: str
    current_version: str
    expected_version: Optional[str] = None
    message: str

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "passed": self.passed,
            "device_serial": self.device_serial,
            "current_version": self.current_version,
            "expected_version": self.expected_version,
            "message": self.message,
        }


class VersionChecker:
    """版本确认器。"""

    def __init__(self, executor: Optional[ADBExecutor] = None):
        self.executor = executor or ADBExecutor()

    def check(
        self,
        device_serial: str,
        expected: Optional[str] = None,
    ) -> VersionCheckResult:
        """检查设备版本。"""
        props = self.executor.getprop(device=device_serial)
        current_fingerprint = props.get("ro.build.fingerprint", "")

        if expected:
            # 检查是否包含预期版本号
            if expected in current_fingerprint:
                return VersionCheckResult(
                    passed=True,
                    device_serial=device_serial,
                    current_version=current_fingerprint,
                    expected_version=expected,
                    message="版本确认通过",
                )
            else:
                return VersionCheckResult(
                    passed=False,
                    device_serial=device_serial,
                    current_version=current_fingerprint,
                    expected_version=expected,
                    message=f"版本不匹配：期望包含 {expected}，实际为 {current_fingerprint}",
                )

        # 无预期版本，只获取当前版本
        return VersionCheckResult(
            passed=True,
            device_serial=device_serial,
            current_version=current_fingerprint,
            message="版本信息获取成功",
        )

    def get_version_info(self, device_serial: str) -> Dict[str, Any]:
        """获取完整版本信息。"""
        props = self.executor.getprop(device=device_serial)

        return {
            "android_version": props.get("ro.build.version.release", ""),
            "build_fingerprint": props.get("ro.build.fingerprint", ""),
            "build_id": props.get("ro.build.id", ""),
            "build_type": props.get("ro.build.type", ""),
            "security_patch": props.get("ro.build.version.security_patch", ""),
        }
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_validators/ -v`
Expected: PASS - 7 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/validators/__init__.py app/validators/boot_check.py app/validators/version_check.py tests/test_validators/
git commit -m "feat: add boot check and version check validators"
```

---

## Phase 3 完成检查

Run: `pytest tests/test_executors/test_step_handlers.py tests/test_executors/test_run_executor.py tests/test_validators/ -v --tb=short`
Expected: All tests pass