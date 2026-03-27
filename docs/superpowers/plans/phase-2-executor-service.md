# Phase 2: 命令执行器与服务层

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现命令执行抽象层和核心业务服务，打通最短主链路。

**Architecture:** 命令执行器封装所有 shell 命令调用，提供 Mock 和真实执行器两种实现。服务层封装业务逻辑，供 CLI 和 API 共享使用。

**Tech Stack:** Python subprocess, SQLAlchemy, Pydantic

---

## 文件结构

```
app/executors/
├── command_runner.py          # 命令执行抽象基类
├── adb_executor.py            # ADB/Fastboot 执行器
├── mock_executor.py           # Mock 执行器（测试用）
└── run_context.py             # 执行上下文

app/services/
├── device_service.py          # 设备管理服务
├── run_service.py             # 任务管理服务
└── scheduler_service.py       # 调度服务
```

---

## Task 2.1: 命令执行抽象基类

**Files:**
- Create: `app/executors/command_runner.py`
- Create: `app/executors/run_context.py`
- Create: `tests/test_executors/test_command_runner.py`

- [ ] **Step 1: 写命令执行器测试**

```python
# tests/test_executors/test_command_runner.py
"""命令执行器测试。"""

import pytest
from dataclasses import dataclass

from app.executors.command_runner import CommandRunner, CommandResult


def test_command_result_creation():
    """测试命令结果创建。"""
    result = CommandResult(
        command="echo test",
        exit_code=0,
        stdout="test\n",
        stderr="",
        duration_ms=50
    )

    assert result.exit_code == 0
    assert result.stdout == "test\n"
    assert result.success is True


def test_command_result_failure():
    """测试命令失败结果。"""
    result = CommandResult(
        command="false",
        exit_code=1,
        stdout="",
        stderr="",
        duration_ms=10
    )

    assert result.exit_code == 1
    assert result.success is False


def test_command_runner_abstract():
    """测试 CommandRunner 是抽象类。"""
    # 不能直接实例化抽象类
    from abc import ABC
    assert CommandRunner.__bases__[0] is ABC


def test_command_runner_interface():
    """测试 CommandRunner 接口方法。"""
    # 检查抽象方法存在
    import inspect
    methods = inspect.getmembers(CommandRunner, predicate=inspect.ismethod)
    abstract_methods = [
        name for name, method in methods
        if getattr(method, '__isabstractmethod__', False)
    ]
    assert 'run' in abstract_methods or 'execute' in abstract_methods
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_executors/test_command_runner.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现命令执行抽象层**

```python
# app/executors/command_runner.py
"""命令执行抽象模块。"""

import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class CommandResult:
    """命令执行结果。"""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int

    @property
    def success(self) -> bool:
        """判断命令是否成功。"""
        return self.exit_code == 0

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "success": self.success,
        }


class CommandRunner(ABC):
    """命令执行器抽象基类。"""

    @abstractmethod
    def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> CommandResult:
        """执行命令并返回结果。

        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            cwd: 工作目录
            env: 环境变量

        Returns:
            CommandResult: 命令执行结果
        """
        pass

    def run_with_retry(
        self,
        command: str,
        max_retries: int = 3,
        retry_delay: int = 1,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """带重试的命令执行。"""
        for attempt in range(max_retries):
            result = self.run(command, timeout=timeout)
            if result.success:
                return result
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        return result


class ShellCommandRunner(CommandRunner):
    """真实 shell 命令执行器。"""

    def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> CommandResult:
        """执行 shell 命令。"""
        start_time = time.time()

        try:
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return CommandResult(
                command=command,
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return CommandResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
            )
```

```python
# app/executors/run_context.py
"""执行上下文模块。"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.config import get_settings


@dataclass
class DeviceSnapshot:
    """设备状态快照。"""

    serial: str
    brand: Optional[str] = None
    model: Optional[str] = None
    android_version: Optional[str] = None
    battery_level: Optional[int] = None
    build_fingerprint: Optional[str] = None
    boot_completed: bool = False


@dataclass
class RunContext:
    """任务执行上下文。"""

    run_id: int
    device_serial: str
    plan_id: int
    upgrade_type: str

    # 设备信息
    device: Optional[DeviceSnapshot] = None

    # 执行配置
    package_path: Optional[str] = None
    target_build: Optional[str] = None
    timeout: int = 300

    # 当前状态
    current_step: Optional[str] = None
    step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 产物路径
    artifact_dir: Optional[Path] = None

    # 异常注入
    fault_profile: Optional[Dict[str, Any]] = None

    # 时间记录
    started_at: Optional[datetime] = None
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        """初始化产物目录。"""
        settings = get_settings()
        if self.artifact_dir is None:
            self.artifact_dir = settings.ARTIFACTS_DIR / str(self.run_id)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def record_event(self, event_type: str, message: str, extra: Optional[Dict] = None):
        """记录事件。"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "message": message,
        }
        if extra:
            event["extra"] = extra
        self.timeline.append(event)

    def set_step_result(self, step_name: str, result: Dict[str, Any]):
        """设置步骤结果。"""
        self.step_results[step_name] = result

    def get_step_result(self, step_name: str) -> Optional[Dict[str, Any]]:
        """获取步骤结果。"""
        return self.step_results.get(step_name)
```

```python
# app/executors/__init__.py
"""执行器模块。"""

from app.executors.command_runner import CommandRunner, CommandResult, ShellCommandRunner
from app.executors.run_context import RunContext, DeviceSnapshot

__all__ = [
    "CommandRunner",
    "CommandResult",
    "ShellCommandRunner",
    "RunContext",
    "DeviceSnapshot",
]
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_executors/test_command_runner.py -v`
Expected: PASS - 4 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/executors/command_runner.py app/executors/run_context.py app/executors/__init__.py tests/test_executors/test_command_runner.py
git commit -m "feat: add command runner abstraction and run context"
```

---

## Task 2.2: ADB 执行器

**Files:**
- Create: `app/executors/adb_executor.py`
- Create: `tests/test_executors/test_adb_executor.py`

- [ ] **Step 1: 写 ADB 执行器测试**

```python
# tests/test_executors/test_adb_executor.py
"""ADB 执行器测试。"""

import pytest

from app.executors.adb_executor import ADBExecutor
from app.executors.command_runner import CommandResult


def test_adb_executor_init():
    """测试 ADB 执行器初始化。"""
    executor = ADBExecutor()
    assert executor.adb_path == "adb"
    assert executor.fastboot_path == "fastboot"


def test_adb_executor_init_custom_path():
    """测试自定义 ADB 路径。"""
    executor = ADBExecutor(adb_path="/custom/adb")
    assert executor.adb_path == "/custom/adb"


def test_adb_devices_command_format():
    """测试 adb devices 命令格式。"""
    executor = ADBExecutor()
    cmd = executor._build_adb_command("devices")
    assert cmd == "adb devices"


def test_adb_shell_command_format():
    """测试 adb shell 命令格式。"""
    executor = ADBExecutor()
    cmd = executor._build_adb_command("shell", "getprop", device="ABC123")
    assert cmd == "adb -s ABC123 shell getprop"


def test_adb_push_command_format():
    """测试 adb push 命令格式。"""
    executor = ADBExecutor()
    cmd = executor._build_adb_command("push", "/local/file", "/remote/path", device="ABC123")
    assert cmd == "adb -s ABC123 push /local/file /remote/path"


def test_adb_executor_interface():
    """测试 ADB 执行器接口方法。"""
    executor = ADBExecutor()
    assert hasattr(executor, 'devices')
    assert hasattr(executor, 'shell')
    assert hasattr(executor, 'push')
    assert hasattr(executor, 'reboot')
    assert hasattr(executor, 'getprop')
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_executors/test_adb_executor.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 ADB 执行器**

```python
# app/executors/adb_executor.py
"""ADB/Fastboot 命令执行器。"""

import re
from typing import Optional, List, Dict, Any

from app.executors.command_runner import CommandRunner, CommandResult, ShellCommandRunner


class ADBExecutor:
    """ADB/Fastboot 命令执行器。"""

    def __init__(
        self,
        adb_path: str = "adb",
        fastboot_path: str = "fastboot",
        runner: Optional[CommandRunner] = None,
    ):
        self.adb_path = adb_path
        self.fastboot_path = fastboot_path
        self.runner = runner or ShellCommandRunner()

    def _build_adb_command(
        self,
        action: str,
        *args: str,
        device: Optional[str] = None,
    ) -> str:
        """构建 ADB 命令。"""
        parts = [self.adb_path]
        if device:
            parts.extend(["-s", device])
        parts.append(action)
        parts.extend(args)
        return " ".join(parts)

    def _build_fastboot_command(
        self,
        action: str,
        *args: str,
        device: Optional[str] = None,
    ) -> str:
        """构建 Fastboot 命令。"""
        parts = [self.fastboot_path]
        if device:
            parts.extend(["-s", device])
        parts.append(action)
        parts.extend(args)
        return " ".join(parts)

    def devices(self) -> List[Dict[str, str]]:
        """获取设备列表。"""
        result = self.runner.run(f"{self.adb_path} devices")

        if not result.success:
            return []

        devices = []
        for line in result.stdout.strip().split("\n"):
            if line and not line.startswith("List of devices"):
                parts = line.split("\t")
                if len(parts) >= 2:
                    devices.append({
                        "serial": parts[0],
                        "status": parts[1],
                    })

        return devices

    def shell(
        self,
        command: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """执行 shell 命令。"""
        cmd = self._build_adb_command("shell", command, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def push(
        self,
        local_path: str,
        remote_path: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """推送文件到设备。"""
        cmd = self._build_adb_command("push", local_path, remote_path, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def pull(
        self,
        remote_path: str,
        local_path: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """从设备拉取文件。"""
        cmd = self._build_adb_command("pull", remote_path, local_path, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def reboot(
        self,
        mode: Optional[str] = None,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """重启设备。"""
        if mode:
            cmd = self._build_adb_command("reboot", mode, device=device)
        else:
            cmd = self._build_adb_command("reboot", device=device)
        return self.runner.run(cmd, timeout=timeout)

    def getprop(
        self,
        prop: Optional[str] = None,
        device: Optional[str] = None,
    ) -> Dict[str, str]:
        """获取设备属性。"""
        if prop:
            result = self.shell(f"getprop {prop}", device=device)
            if result.success:
                return {prop: result.stdout.strip()}
            return {}

        result = self.shell("getprop", device=device, timeout=30)
        if not result.success:
            return {}

        props = {}
        for line in result.stdout.strip().split("\n"):
            match = re.match(r"\[([^\]]+)\]: \[([^\]]+)\]", line)
            if match:
                props[match.group(1)] = match.group(2)

        return props

    def wait_for_device(
        self,
        device: Optional[str] = None,
        timeout: int = 60,
        state: str = "device",
    ) -> CommandResult:
        """等待设备就绪。"""
        cmd = self._build_adb_command("wait-for-device", device=device)
        return self.runner.run(cmd, timeout=timeout)

    def install(
        self,
        package_path: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """安装 APK。"""
        cmd = self._build_adb_command("install", "-r", package_path, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def logcat(
        self,
        device: Optional[str] = None,
        output_path: Optional[str] = None,
        timeout: Optional[int] = None,
        clear: bool = False,
    ) -> CommandResult:
        """获取 logcat 日志。"""
        if clear:
            self.shell("logcat -c", device=device)

        cmd = self._build_adb_command("logcat", "-d", device=device)
        result = self.runner.run(cmd, timeout=timeout)

        if output_path and result.success:
            with open(output_path, "w") as f:
                f.write(result.stdout)

        return result

    def fastboot_reboot(
        self,
        device: Optional[str] = None,
    ) -> CommandResult:
        """Fastboot 模式重启。"""
        cmd = self._build_fastboot_command("reboot", device=device)
        return self.runner.run(cmd)

    def fastboot_flash(
        self,
        partition: str,
        image_path: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """Fastboot 刷写分区。"""
        cmd = self._build_fastboot_command("flash", partition, image_path, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def get_device_snapshot(
        self,
        device: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取设备完整快照。"""
        props = self.getprop(device=device)

        # 获取电量
        battery_result = self.shell(
            "dumpsys battery | grep level",
            device=device
        )
        battery_level = None
        if battery_result.success:
            match = re.search(r"level: (\d+)", battery_result.stdout)
            if match:
                battery_level = int(match.group(1))

        # 获取存储信息
        storage_result = self.shell(
            "df /data | tail -1",
            device=device
        )

        return {
            "serial": device,
            "brand": props.get("ro.product.brand", ""),
            "model": props.get("ro.product.model", ""),
            "android_version": props.get("ro.build.version.release", ""),
            "build_fingerprint": props.get("ro.build.fingerprint", ""),
            "battery_level": battery_level,
            "boot_completed": props.get("sys.boot_completed", "0") == "1",
            "storage": storage_result.stdout.strip() if storage_result.success else "",
        }
```

- [ ] **Step 4: 更新 executors/__init__.py**

```python
# app/executors/__init__.py
"""执行器模块。"""

from app.executors.command_runner import CommandRunner, CommandResult, ShellCommandRunner
from app.executors.adb_executor import ADBExecutor
from app.executors.run_context import RunContext, DeviceSnapshot

__all__ = [
    "CommandRunner",
    "CommandResult",
    "ShellCommandRunner",
    "ADBExecutor",
    "RunContext",
    "DeviceSnapshot",
]
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_executors/test_adb_executor.py -v`
Expected: PASS - 6 tests passed

- [ ] **Step 6: 提交**

```bash
git add app/executors/adb_executor.py app/executors/__init__.py tests/test_executors/test_adb_executor.py
git commit -m "feat: add ADB/Fastboot executor with device commands"
```

---

## Task 2.3: Mock 执行器

**Files:**
- Create: `app/executors/mock_executor.py`
- Create: `tests/test_executors/test_mock_executor.py`

- [ ] **Step 1: 写 Mock 执行器测试**

```python
# tests/test_executors/test_mock_executor.py
"""Mock 执行器测试。"""

import pytest

from app.executors.mock_executor import MockExecutor
from app.executors.command_runner import CommandResult


def test_mock_executor_returns_success():
    """测试 Mock 执行器返回成功。"""
    executor = MockExecutor()
    result = executor.run("echo test")

    assert result.success is True
    assert result.exit_code == 0


def test_mock_executor_custom_response():
    """测试自定义 Mock 响应。"""
    executor = MockExecutor()
    executor.set_response("adb devices", stdout="ABC123\tdevice\n")

    result = executor.run("adb devices")
    assert result.stdout == "ABC123\tdevice\n"


def test_mock_executor_failure_response():
    """测试失败响应。"""
    executor = MockExecutor()
    executor.set_response("false", exit_code=1, stderr="command failed")

    result = executor.run("false")
    assert result.success is False
    assert result.exit_code == 1


def test_mock_executor_records_commands():
    """测试记录执行的命令。"""
    executor = MockExecutor()
    executor.run("adb devices")
    executor.run("adb shell getprop")

    assert len(executor.executed_commands) == 2
    assert "adb devices" in executor.executed_commands


def test_mock_executor_default_device_response():
    """测试默认设备响应。"""
    executor = MockExecutor.default_device_responses()

    result = executor.run("adb devices")
    assert "device" in result.stdout

    result = executor.run("adb -s ABC123 shell getprop ro.product.model")
    assert result.success
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_executors/test_mock_executor.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 Mock 执行器**

```python
# app/executors/mock_executor.py
"""Mock 命令执行器（用于测试）。"""

from typing import Optional, Dict, Tuple, List
from app.executors.command_runner import CommandRunner, CommandResult


class MockExecutor(CommandRunner):
    """Mock 命令执行器，用于测试场景。"""

    def __init__(self):
        self.responses: Dict[str, Tuple[int, str, str]] = {}
        self.executed_commands: List[str] = []
        self.default_exit_code: int = 0
        self.default_stdout: str = ""
        self.default_stderr: str = ""

    def set_response(
        self,
        command: str,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ):
        """设置特定命令的响应。"""
        self.responses[command] = (exit_code, stdout, stderr)

    def set_default_response(
        self,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
    ):
        """设置默认响应。"""
        self.default_exit_code = exit_code
        self.default_stdout = stdout
        self.default_stderr = stderr

    def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> CommandResult:
        """执行 Mock 命令。"""
        self.executed_commands.append(command)

        # 检查是否有预设响应
        for cmd_pattern, (exit_code, stdout, stderr) in self.responses.items():
            if command.startswith(cmd_pattern) or command == cmd_pattern:
                return CommandResult(
                    command=command,
                    exit_code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                    duration_ms=10,
                )

        # 返回默认响应
        return CommandResult(
            command=command,
            exit_code=self.default_exit_code,
            stdout=self.default_stdout,
            stderr=self.default_stderr,
            duration_ms=10,
        )

    def clear(self):
        """清除所有记录。"""
        self.responses.clear()
        self.executed_commands.clear()

    @classmethod
    def default_device_responses(cls) -> "MockExecutor":
        """创建带有默认设备响应的 Mock 执行器。"""
        executor = cls()

        # 设备列表响应
        executor.set_response("adb devices", stdout="ABC123\tdevice\nXYZ789\tdevice\n")

        # getprop 响应
        executor.set_response(
            "adb shell getprop",
            stdout="""[ro.product.brand]: [Google]
[ro.product.model]: [Pixel 6]
[ro.build.version.release]: [14]
[ro.build.fingerprint]: [Google/oriole/oriole:14/AP1A.240305.019]
[sys.boot_completed]: [1]
"""
        )

        # 电量响应
        executor.set_response(
            "adb shell dumpsys battery",
            stdout="Current Battery Service state:\n  level: 85\n"
        )

        # 存储响应
        executor.set_response(
            "adb shell df /data",
            stdout="Filesystem      Size  Used Avail Use% Mounted on\n/dev/block/dm-0  64G   32G   32G  50% /data\n"
        )

        return executor

    @classmethod
    def upgrade_success_responses(cls) -> "MockExecutor":
        """创建升级成功场景的 Mock 响应。"""
        executor = cls.default_device_responses()

        # push 成功
        executor.set_response("adb push", stdout="push success\n")

        # 升级命令成功
        executor.set_response(
            "adb shell am broadcast",
            stdout="Broadcast completed: result=0\n"
        )

        return executor

    @classmethod
    def upgrade_failure_responses(cls) -> "MockExecutor":
        """创建升级失败场景的 Mock 响应。"""
        executor = cls.default_device_responses()

        # push 失败
        executor.set_response("adb push", exit_code=1, stderr="No space left on device\n")

        return executor
```

- [ ] **Step 4: 更新 executors/__init__.py**

```python
# app/executors/__init__.py
"""执行器模块。"""

from app.executors.command_runner import CommandRunner, CommandResult, ShellCommandRunner
from app.executors.adb_executor import ADBExecutor
from app.executors.mock_executor import MockExecutor
from app.executors.run_context import RunContext, DeviceSnapshot

__all__ = [
    "CommandRunner",
    "CommandResult",
    "ShellCommandRunner",
    "ADBExecutor",
    "MockExecutor",
    "RunContext",
    "DeviceSnapshot",
]
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_executors/test_mock_executor.py -v`
Expected: PASS - 5 tests passed

- [ ] **Step 6: 提交**

```bash
git add app/executors/mock_executor.py app/executors/__init__.py tests/test_executors/test_mock_executor.py
git commit -m "feat: add Mock executor for testing scenarios"
```

---

## Task 2.4: 设备管理服务

**Files:**
- Create: `app/services/device_service.py`
- Create: `tests/test_services/test_device_service.py`

- [ ] **Step 1: 写设备服务测试**

```python
# tests/test_services/test_device_service.py
"""设备管理服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DeviceStatus
from app.services.device_service import DeviceService
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
def device_service(test_db):
    """创建设备服务。"""
    return DeviceService(test_db, MockExecutor.default_device_responses())


def test_sync_devices(device_service):
    """测试设备同步。"""
    devices = device_service.sync_devices()

    assert len(devices) >= 1
    assert devices[0].serial == "ABC123"


def test_get_device_by_serial(device_service, test_db):
    """测试通过序列号获取设备。"""
    # 先同步
    device_service.sync_devices()

    device = device_service.get_device_by_serial("ABC123")
    assert device is not None
    assert device.serial == "ABC123"


def test_get_available_devices(device_service, test_db):
    """测试获取可用设备列表。"""
    # 先同步
    device_service.sync_devices()

    # 设置一个设备为忙碌
    device = test_db.query(Device).filter_by(serial="ABC123").first()
    device.status = DeviceStatus.BUSY
    test_db.commit()

    available = device_service.get_available_devices()
    assert len(available) == 1  # 只有 XYZ789 可用


def test_quarantine_device(device_service, test_db):
    """测试设备隔离。"""
    device_service.sync_devices()

    device_service.quarantine_device("ABC123", "Test quarantine")

    device = test_db.query(Device).filter_by(serial="ABC123").first()
    assert device.status == DeviceStatus.QUARANTINED
    assert device.quarantine_reason == "Test quarantine"


def test_recover_device(device_service, test_db):
    """测试设备恢复。"""
    device_service.sync_devices()
    device_service.quarantine_device("ABC123", "Test")

    device_service.recover_device("ABC123")

    device = test_db.query(Device).filter_by(serial="ABC123").first()
    assert device.status == DeviceStatus.IDLE
    assert device.quarantine_reason is None


def test_update_device_tags(device_service, test_db):
    """测试更新设备标签。"""
    device_service.sync_devices()

    device_service.update_device_tags("ABC123", ["主力机型", "Android14"])

    device = test_db.query(Device).filter_by(serial="ABC123").first()
    assert device.get_tags() == ["主力机型", "Android14"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_services/test_device_service.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现设备服务**

```python
# app/services/device_service.py
"""设备管理业务逻辑。"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.device import Device, DeviceLease, DeviceStatus
from app.executors.adb_executor import ADBExecutor
from app.executors.command_runner import CommandRunner


class DeviceService:
    """设备管理服务。"""

    def __init__(
        self,
        db: Session,
        runner: Optional[CommandRunner] = None,
    ):
        self.db = db
        settings = get_settings()
        self.runner = runner
        self.executor = ADBExecutor(runner=self.runner)

    def sync_devices(self) -> List[Device]:
        """扫描并同步在线设备。"""
        # 获取当前在线设备
        online_devices = self.executor.devices()
        online_serials = {d["serial"] for d in online_devices}

        # 获取数据库中的设备
        db_devices = self.db.query(Device).all()
        db_serials = {d.serial for d in db_devices}

        # 新设备入库
        for device_info in online_devices:
            serial = device_info["serial"]
            if serial not in db_serials:
                device = self._create_device_from_adb(serial)
                self.db.add(device)

        # 离线设备更新状态
        for device in db_devices:
            if device.serial not in online_serials:
                if device.status != DeviceStatus.QUARANTINED:
                    device.status = DeviceStatus.OFFLINE
            else:
                # 更新在线设备的属性
                self._update_device_info(device)
                if device.status == DeviceStatus.OFFLINE:
                    device.status = DeviceStatus.IDLE

        self.db.commit()
        return self.db.query(Device).all()

    def _create_device_from_adb(self, serial: str) -> Device:
        """从 ADB 信息创建设备实体。"""
        snapshot = self.executor.get_device_snapshot(device=serial)

        device = Device(
            serial=serial,
            brand=snapshot.get("brand"),
            model=snapshot.get("model"),
            android_version=snapshot.get("android_version"),
            build_fingerprint=snapshot.get("build_fingerprint"),
            battery_level=snapshot.get("battery_level"),
            status=DeviceStatus.IDLE,
            last_seen_at=datetime.utcnow(),
        )

        return device

    def _update_device_info(self, device: Device):
        """更新设备信息。"""
        snapshot = self.executor.get_device_snapshot(device=device.serial)

        device.brand = snapshot.get("brand")
        device.model = snapshot.get("model")
        device.android_version = snapshot.get("android_version")
        device.build_fingerprint = snapshot.get("build_fingerprint")
        device.battery_level = snapshot.get("battery_level")
        device.last_seen_at = datetime.utcnow()

        # 计算健康分数
        health_score = 100.0
        if device.battery_level and device.battery_level < 20:
            health_score -= 30
        if snapshot.get("boot_completed") is False:
            health_score -= 50
        device.health_score = health_score

    def get_device_by_serial(self, serial: str) -> Optional[Device]:
        """通过序列号获取设备。"""
        return self.db.query(Device).filter_by(serial=serial).first()

    def get_device_by_id(self, device_id: int) -> Optional[Device]:
        """通过 ID 获取设备。"""
        return self.db.query(Device).filter_by(id=device_id).first()

    def get_available_devices(
        self,
        tags: Optional[List[str]] = None,
        min_battery: int = 20,
        min_health: float = 50.0,
    ) -> List[Device]:
        """获取可用设备列表。"""
        query = self.db.query(Device).filter(
            Device.status == DeviceStatus.IDLE,
            Device.health_score >= min_health,
        )

        if min_battery:
            query = query.filter(Device.battery_level >= min_battery)

        devices = query.all()

        # 标签过滤
        if tags:
            filtered = []
            for device in devices:
                device_tags = device.get_tags()
                if any(tag in device_tags for tag in tags):
                    filtered.append(device)
            devices = filtered

        return devices

    def quarantine_device(
        self,
        serial: str,
        reason: str,
        run_id: Optional[int] = None,
    ) -> Optional[Device]:
        """隔离异常设备。"""
        device = self.get_device_by_serial(serial)
        if not device:
            return None

        device.status = DeviceStatus.QUARANTINED
        device.quarantine_reason = reason

        # 释放租约
        if device.current_run_id:
            lease = self.db.query(DeviceLease).filter_by(
                device_id=device.id,
                run_id=device.current_run_id,
                lease_status="active"
            ).first()
            if lease:
                lease.lease_status = "released"
                lease.released_at = datetime.utcnow()

        device.current_run_id = run_id or device.current_run_id

        self.db.commit()
        return device

    def recover_device(self, serial: str) -> Optional[Device]:
        """恢复隔离设备。"""
        device = self.get_device_by_serial(serial)
        if not device:
            return None

        device.status = DeviceStatus.RECOVERING
        self.db.commit()

        # 执行健康检查
        self._update_device_info(device)

        # 检查是否恢复成功
        if device.health_score >= 50:
            device.status = DeviceStatus.IDLE
        else:
            device.status = DeviceStatus.QUARANTINED
            device.quarantine_reason = "Recovery failed: health check failed"

        device.quarantine_reason = None
        device.current_run_id = None

        self.db.commit()
        return device

    def update_device_tags(
        self,
        serial: str,
        tags: List[str],
    ) -> Optional[Device]:
        """更新设备标签。"""
        device = self.get_device_by_serial(serial)
        if not device:
            return None

        device.set_tags(tags)
        self.db.commit()
        return device

    def list_devices(
        self,
        status: Optional[DeviceStatus] = None,
    ) -> List[Device]:
        """列出设备。"""
        query = self.db.query(Device)

        if status:
            query = query.filter(Device.status == status)

        return query.order_by(Device.last_seen_at.desc()).all()
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_services/test_device_service.py -v`
Expected: PASS - 6 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/services/device_service.py app/services/__init__.py tests/test_services/test_device_service.py
git commit -m "feat: add device management service"
```

---

## Task 2.5: 任务管理服务

**Files:**
- Create: `app/services/run_service.py`
- Create: `tests/test_services/test_run_service.py`

- [ ] **Step 1: 写任务服务测试**

```python
# tests/test_services/test_run_service.py
"""任务管理服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DeviceStatus
from app.models.run import UpgradePlan, RunSession, RunStatus, UpgradeType
from app.models.fault import FaultProfile, FaultType, FaultStage
from app.services.run_service import RunService


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
def sample_plan(test_db):
    """创建示例升级计划。"""
    plan = UpgradePlan(
        name="测试升级计划",
        upgrade_type=UpgradeType.FULL,
        package_path="/tmp/update.zip",
        target_build="TARGET.001",
        parallelism=2,
    )
    test_db.add(plan)
    test_db.commit()
    return plan


@pytest.fixture
def sample_device(test_db):
    """创建示例设备。"""
    device = Device(
        serial="TEST001",
        brand="Test",
        model="TestModel",
        status=DeviceStatus.IDLE,
        battery_level=80,
    )
    device.set_tags(["主力机型"])
    test_db.add(device)
    test_db.commit()
    return device


@pytest.fixture
def run_service(test_db):
    """创建任务服务。"""
    return RunService(test_db)


def test_create_run_session(run_service, sample_plan, sample_device):
    """测试创建任务会话。"""
    session = run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    assert session is not None
    assert session.status == RunStatus.QUEUED
    assert session.plan_id == sample_plan.id
    assert session.device_id == sample_device.id


def test_get_run_session(run_service, test_db, sample_plan, sample_device):
    """测试获取任务会话。"""
    session = run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    retrieved = run_service.get_run_session(session.id)
    assert retrieved.id == session.id


def test_update_run_status(run_service, test_db, sample_plan, sample_device):
    """测试更新任务状态。"""
    session = run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    run_service.update_run_status(session.id, RunStatus.RUNNING)

    updated = test_db.query(RunSession).filter_by(id=session.id).first()
    assert updated.status == RunStatus.RUNNING
    assert updated.started_at is not None


def test_complete_run_session(run_service, test_db, sample_plan, sample_device):
    """测试完成任务。"""
    session = run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    run_service.complete_run_session(
        session.id,
        result="success",
        summary="升级成功完成",
    )

    completed = test_db.query(RunSession).filter_by(id=session.id).first()
    assert completed.status == RunStatus.PASSED
    assert completed.result == "success"
    assert completed.ended_at is not None


def test_abort_run_session(run_service, test_db, sample_plan, sample_device):
    """测试终止任务。"""
    session = run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    run_service.abort_run_session(session.id, "User requested abort")

    aborted = test_db.query(RunSession).filter_by(id=session.id).first()
    assert aborted.status == RunStatus.ABORTED


def test_list_pending_runs(run_service, test_db, sample_plan, sample_device):
    """测试列出待执行任务。"""
    # 创建多个任务
    run_service.create_run_session(plan_id=sample_plan.id, device_id=sample_device.id)
    run_service.create_run_session(plan_id=sample_plan.id, device_id=sample_device.id)

    pending = run_service.list_pending_runs()
    assert len(pending) == 2


def test_create_upgrade_plan(run_service, test_db):
    """测试创建升级计划。"""
    plan = run_service.create_upgrade_plan(
        name="新升级计划",
        upgrade_type=UpgradeType.INCREMENTAL,
        package_path="/tmp/patch.zip",
        device_selector={"brand": "Google"},
    )

    assert plan is not None
    assert plan.name == "新升级计划"
    assert plan.upgrade_type == UpgradeType.INCREMENTAL


def test_list_runs(run_service, test_db, sample_plan, sample_device):
    """测试列出任务。"""
    run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    runs = run_service.list_runs()
    assert len(runs) >= 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_services/test_run_service.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现任务服务**

```python
# app/services/run_service.py
"""任务管理业务逻辑。"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.run import (
    UpgradePlan, RunSession, RunStep,
    RunStatus, UpgradeType, StepName
)
from app.models.device import Device, DeviceLease, DeviceStatus


class RunService:
    """任务管理服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def create_upgrade_plan(
        self,
        name: str,
        upgrade_type: UpgradeType,
        package_path: str,
        target_build: Optional[str] = None,
        device_selector: Optional[Dict[str, Any]] = None,
        fault_profile_id: Optional[int] = None,
        parallelism: int = 1,
        created_by: Optional[str] = None,
    ) -> UpgradePlan:
        """创建升级计划。"""
        plan = UpgradePlan(
            name=name,
            upgrade_type=upgrade_type,
            package_path=package_path,
            target_build=target_build,
            fault_profile_id=fault_profile_id,
            parallelism=parallelism,
            created_by=created_by,
        )

        if device_selector:
            plan.set_device_selector(device_selector)

        self.db.add(plan)
        self.db.commit()
        return plan

    def get_upgrade_plan(self, plan_id: int) -> Optional[UpgradePlan]:
        """获取升级计划。"""
        return self.db.query(UpgradePlan).filter_by(id=plan_id).first()

    def list_upgrade_plans(self) -> List[UpgradePlan]:
        """列出所有升级计划。"""
        return self.db.query(UpgradePlan).order_by(
            UpgradePlan.created_at.desc()
        ).all()

    def create_run_session(
        self,
        plan_id: int,
        device_id: int,
    ) -> RunSession:
        """创建任务执行会话。"""
        session = RunSession(
            plan_id=plan_id,
            device_id=device_id,
            status=RunStatus.QUEUED,
        )

        self.db.add(session)
        self.db.commit()
        return session

    def get_run_session(self, run_id: int) -> Optional[RunSession]:
        """获取任务会话。"""
        return self.db.query(RunSession).filter_by(id=run_id).first()

    def update_run_status(
        self,
        run_id: int,
        status: RunStatus,
        started_at: Optional[datetime] = None,
    ) -> Optional[RunSession]:
        """更新任务状态。"""
        session = self.get_run_session(run_id)
        if not session:
            return None

        session.status = status

        if status == RunStatus.RUNNING and not session.started_at:
            session.started_at = started_at or datetime.utcnow()

        self.db.commit()
        return session

    def complete_run_session(
        self,
        run_id: int,
        result: str,
        status: RunStatus = RunStatus.PASSED,
        summary: Optional[str] = None,
        failure_category: Optional[str] = None,
    ) -> Optional[RunSession]:
        """完成任务会话。"""
        session = self.get_run_session(run_id)
        if not session:
            return None

        session.status = status
        session.result = result
        session.ended_at = datetime.utcnow()
        session.summary = summary
        session.failure_category = failure_category

        self.db.commit()
        return session

    def abort_run_session(
        self,
        run_id: int,
        reason: Optional[str] = None,
    ) -> Optional[RunSession]:
        """终止任务会话。"""
        session = self.get_run_session(run_id)
        if not session:
            return None

        # 只有排队和运行中的任务可以终止
        if session.status not in [RunStatus.QUEUED, RunStatus.RESERVED, RunStatus.RUNNING]:
            return None

        session.status = RunStatus.ABORTED
        session.result = "aborted"
        session.ended_at = datetime.utcnow()
        session.summary = reason

        self.db.commit()
        return session

    def list_runs(
        self,
        status: Optional[RunStatus] = None,
        limit: int = 100,
    ) -> List[RunSession]:
        """列出任务。"""
        query = self.db.query(RunSession)

        if status:
            query = query.filter(RunSession.status == status)

        return query.order_by(RunSession.created_at.desc()).limit(limit).all()

    def list_pending_runs(self) -> List[RunSession]:
        """列出待执行任务（排队状态）。"""
        return self.db.query(RunSession).filter(
            RunSession.status == RunStatus.QUEUED
        ).order_by(RunSession.created_at).all()

    def create_run_step(
        self,
        run_id: int,
        step_name: StepName,
        step_order: int,
        command: Optional[str] = None,
    ) -> RunStep:
        """创建执行步骤。"""
        step = RunStep(
            run_id=run_id,
            step_name=step_name,
            step_order=step_order,
            command=command,
            status="pending",
        )

        self.db.add(step)
        self.db.commit()
        return step

    def update_run_step(
        self,
        step_id: int,
        status: str,
        stdout_path: Optional[str] = None,
        stderr_path: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> Optional[RunStep]:
        """更新执行步骤状态。"""
        step = self.db.query(RunStep).filter_by(id=step_id).first()
        if not step:
            return None

        step.status = status

        if status == "running":
            step.started_at = datetime.utcnow()
        elif status in ["success", "failure"]:
            step.ended_at = datetime.utcnow()

        if stdout_path:
            step.stdout_path = stdout_path
        if stderr_path:
            step.stderr_path = stderr_path
        if result:
            step.set_result(result)

        self.db.commit()
        return step

    def get_run_steps(self, run_id: int) -> List[RunStep]:
        """获取任务的所有执行步骤。"""
        return self.db.query(RunStep).filter_by(
            run_id=run_id
        ).order_by(RunStep.step_order).all()
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_services/test_run_service.py -v`
Expected: PASS - 8 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/services/run_service.py tests/test_services/test_run_service.py
git commit -m "feat: add run management service"
```

---

## Task 2.6: 调度服务

**Files:**
- Create: `app/services/scheduler_service.py`
- Create: `tests/test_services/test_scheduler_service.py`

- [ ] **Step 1: 写调度服务测试**

```python
# tests/test_services/test_scheduler_service.py
"""调度服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DeviceLease, DeviceStatus
from app.models.run import UpgradePlan, RunSession, RunStatus, UpgradeType
from app.services.scheduler_service import SchedulerService
from app.services.device_service import DeviceService
from app.services.run_service import RunService
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
def scheduler(test_db):
    """创建调度服务。"""
    return SchedulerService(test_db)


@pytest.fixture
def setup_data(test_db):
    """设置测试数据。"""
    # 创建设备
    devices = [
        Device(serial="DEV001", status=DeviceStatus.IDLE, battery_level=80),
        Device(serial="DEV002", status=DeviceStatus.IDLE, battery_level=75),
        Device(serial="DEV003", status=DeviceStatus.BUSY, battery_level=90),
    ]
    for d in devices:
        test_db.add(d)

    # 创建计划
    plan = UpgradePlan(
        name="测试计划",
        upgrade_type=UpgradeType.FULL,
        package_path="/tmp/update.zip",
    )
    test_db.add(plan)
    test_db.commit()

    return {"devices": devices, "plan": plan}


def test_acquire_device_lease(scheduler, test_db, setup_data):
    """测试获取设备租约。"""
    device = setup_data["devices"][0]
    plan = setup_data["plan"]

    run = RunSession(plan_id=plan.id, device_id=device.id, status=RunStatus.QUEUED)
    test_db.add(run)
    test_db.commit()

    lease = scheduler.acquire_device_lease(device.id, run.id)

    assert lease is not None
    assert lease.lease_status == "active"

    # 设备状态应该变为 busy
    test_db.refresh(device)
    assert device.status == DeviceStatus.BUSY


def test_acquire_lease_for_busy_device(scheduler, test_db, setup_data):
    """测试无法获取忙碌设备的租约。"""
    device = setup_data["devices"][2]  # BUSY 设备
    plan = setup_data["plan"]

    run = RunSession(plan_id=plan.id, device_id=device.id, status=RunStatus.QUEUED)
    test_db.add(run)
    test_db.commit()

    lease = scheduler.acquire_device_lease(device.id, run.id)

    assert lease is None


def test_release_device_lease(scheduler, test_db, setup_data):
    """测试释放设备租约。"""
    device = setup_data["devices"][0]
    plan = setup_data["plan"]

    run = RunSession(plan_id=plan.id, device_id=device.id, status=RunStatus.RUNNING)
    test_db.add(run)
    test_db.commit()

    # 先获取租约
    lease = scheduler.acquire_device_lease(device.id, run.id)

    # 释放租约
    scheduler.release_device_lease(device.id, run.id)

    test_db.refresh(lease)
    assert lease.lease_status == "released"

    test_db.refresh(device)
    assert device.status == DeviceStatus.IDLE


def test_select_device_for_run(scheduler, test_db, setup_data):
    """测试为任务选择设备。"""
    plan = setup_data["plan"]

    run = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
    test_db.add(run)
    test_db.commit()

    device = scheduler.select_device_for_run(run.id)

    assert device is not None
    assert device.status == DeviceStatus.IDLE


def test_select_device_with_selector(scheduler, test_db, setup_data):
    """测试使用选择器选择设备。"""
    plan = setup_data["plan"]
    plan.set_device_selector({"serial": "DEV002"})
    test_db.commit()

    run = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
    test_db.add(run)
    test_db.commit()

    device = scheduler.select_device_for_run(run.id)

    assert device.serial == "DEV002"


def test_reserve_run(scheduler, test_db, setup_data):
    """测试预留任务。"""
    plan = setup_data["plan"]

    run = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
    test_db.add(run)
    test_db.commit()

    success = scheduler.reserve_run(run.id)

    assert success is True
    test_db.refresh(run)
    assert run.status == RunStatus.RESERVED


def test_get_next_run_to_execute(scheduler, test_db, setup_data):
    """测试获取下一个待执行任务。"""
    plan = setup_data["plan"]

    # 创建多个任务
    run1 = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
    run2 = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
    test_db.add_all([run1, run2])
    test_db.commit()

    # 预留第一个
    scheduler.reserve_run(run1.id)

    next_run = scheduler.get_next_run_to_execute()
    assert next_run.id == run1.id
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_services/test_scheduler_service.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现调度服务**

```python
# app/services/scheduler_service.py
"""调度与并发控制服务。"""

from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.config import get_settings
from app.models.device import Device, DeviceLease, DeviceStatus
from app.models.run import RunSession, RunStatus, UpgradePlan
from app.services.device_service import DeviceService


class SchedulerService:
    """调度服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.device_service = DeviceService(db)

    def acquire_device_lease(
        self,
        device_id: int,
        run_id: int,
        duration: Optional[int] = None,
    ) -> Optional[DeviceLease]:
        """获取设备租约。"""
        device = self.db.query(Device).filter_by(id=device_id).first()

        if not device:
            return None

        # 检查设备状态
        if device.status != DeviceStatus.IDLE:
            return None

        # 检查是否有活跃租约
        active_lease = self.db.query(DeviceLease).filter(
            DeviceLease.device_id == device_id,
            DeviceLease.lease_status == "active"
        ).first()

        if active_lease:
            return None

        # 创建租约
        lease_duration = duration or self.settings.LEASE_DEFAULT_DURATION
        lease = DeviceLease(
            device_id=device_id,
            run_id=run_id,
            lease_status="active",
            expired_at=datetime.utcnow() + timedelta(seconds=lease_duration),
        )

        # 更新设备状态
        device.status = DeviceStatus.BUSY
        device.current_run_id = run_id

        self.db.add(lease)
        self.db.commit()

        return lease

    def release_device_lease(
        self,
        device_id: int,
        run_id: int,
    ) -> bool:
        """释放设备租约。"""
        lease = self.db.query(DeviceLease).filter(
            DeviceLease.device_id == device_id,
            DeviceLease.run_id == run_id,
            DeviceLease.lease_status == "active"
        ).first()

        if not lease:
            return False

        lease.lease_status = "released"
        lease.released_at = datetime.utcnow()

        # 更新设备状态
        device = self.db.query(Device).filter_by(id=device_id).first()
        if device:
            device.status = DeviceStatus.IDLE
            device.current_run_id = None

        self.db.commit()
        return True

    def select_device_for_run(
        self,
        run_id: int,
        min_battery: int = 20,
    ) -> Optional[Device]:
        """为任务选择合适的设备。"""
        run = self.db.query(RunSession).filter_by(id=run_id).first()
        if not run:
            return None

        plan = self.db.query(UpgradePlan).filter_by(id=run.plan_id).first()
        if not plan:
            return None

        # 获取选择条件
        selector = plan.get_device_selector()

        # 获取可用设备
        available_devices = self.device_service.get_available_devices(
            tags=selector.get("tags"),
            min_battery=min_battery,
        )

        if not available_devices:
            return None

        # 根据选择器过滤
        for device in available_devices:
            match = True
            for key, value in selector.items():
                if key == "tags":
                    continue
                device_value = getattr(device, key, None)
                if device_value != value:
                    match = False
                    break

            if match:
                return device

        # 如果没有精确匹配，返回第一个可用设备
        return available_devices[0] if available_devices else None

    def reserve_run(self, run_id: int) -> bool:
        """预留任务（分配设备并获取租约）。"""
        run = self.db.query(RunSession).filter_by(id=run_id).first()
        if not run:
            return False

        if run.status != RunStatus.QUEUED:
            return False

        # 选择设备
        device = self.select_device_for_run(run_id)
        if not device:
            return False

        # 获取租约
        lease = self.acquire_device_lease(device.id, run_id)
        if not lease:
            return False

        # 更新任务状态
        run.status = RunStatus.RESERVED
        run.device_id = device.id

        self.db.commit()
        return True

    def get_next_run_to_execute(self) -> Optional[RunSession]:
        """获取下一个待执行的任务。"""
        run = self.db.query(RunSession).filter(
            RunSession.status == RunStatus.RESERVED
        ).order_by(RunSession.created_at).first()

        return run

    def cleanup_expired_leases(self) -> List[DeviceLease]:
        """清理过期租约。"""
        expired_leases = self.db.query(DeviceLease).filter(
            and_(
                DeviceLease.lease_status == "active",
                DeviceLease.expired_at < datetime.utcnow()
            )
        ).all()

        for lease in expired_leases:
            lease.lease_status = "expired"

            # 设备进入恢复状态
            device = self.db.query(Device).filter_by(id=lease.device_id).first()
            if device:
                device.status = DeviceStatus.RECOVERING
                device.current_run_id = None

            # 任务进入隔离状态
            run = self.db.query(RunSession).filter_by(id=lease.run_id).first()
            if run:
                run.status = RunStatus.QUARANTINED
                run.failure_category = "lease_expired"

        self.db.commit()
        return expired_leases

    def get_concurrent_run_count(self) -> int:
        """获取当前并发运行的任务数。"""
        return self.db.query(RunSession).filter(
            RunSession.status.in_([
                RunStatus.RUNNING,
                RunStatus.VALIDATING,
            ])
        ).count()

    def can_start_new_run(self) -> bool:
        """检查是否可以启动新任务。"""
        current_count = self.get_concurrent_run_count()
        return current_count < self.settings.MAX_CONCURRENT_RUNS
```

- [ ] **Step 4: 更新 services/__init__.py**

```python
# app/services/__init__.py
"""服务层模块。"""

from app.services.device_service import DeviceService
from app.services.run_service import RunService
from app.services.scheduler_service import SchedulerService

__all__ = [
    "DeviceService",
    "RunService",
    "SchedulerService",
]
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_services/test_scheduler_service.py -v`
Expected: PASS - 7 tests passed

- [ ] **Step 6: 提交**

```bash
git add app/services/scheduler_service.py app/services/__init__.py tests/test_services/test_scheduler_service.py
git commit -m "feat: add scheduler service with device lease management"
```

---

## Phase 2 完成检查

验证所有服务层测试：

Run: `pytest tests/test_executors/ tests/test_services/ -v --tb=short`
Expected: All tests pass