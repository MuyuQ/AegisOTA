# Phase 4: 异常注入插件

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现异常注入插件框架，支持在升级各阶段注入模拟故障场景。

**Architecture:** 异常注入采用插件模式，每个插件实现 prepare/inject/cleanup 三阶段，可在 precheck、apply_update、post_validate 三个时机触发。

**Tech Stack:** Python, ADB Executor

---

## 文件结构

```
app/faults/
├── __init__.py
├── base.py                      # FaultPlugin 抽象基类
├── storage_pressure.py          # 存储压力注入
├── reboot_interrupted.py        # 重启中断注入
├── download_interrupted.py      # 下载中断注入
├── monkey_after_upgrade.py      # 升级后 Monkey 测试

tests/test_faults/
├── test_base.py
├── test_storage_pressure.py
├── test_reboot_interrupted.py
├── test_download_interrupted.py
├── test_monkey_after_upgrade.py
```

---

## Task 4.1: 异常注入基类

**Files:**
- Create: `app/faults/base.py`
- Create: `tests/test_faults/test_base.py`

- [ ] **Step 1: 写异常注入基类测试**

```python
# tests/test_faults/test_base.py
"""异常注入基类测试。"""

import pytest

from app.faults.base import FaultPlugin, FaultResult
from app.executors.run_context import RunContext


def test_fault_result_creation():
    """测试异常注入结果创建。"""
    result = FaultResult(
        success=True,
        fault_type="storage_pressure",
        message="存储压力注入成功",
        data={"fill_percent": 90},
    )

    assert result.success is True
    assert result.fault_type == "storage_pressure"


def test_fault_result_failure():
    """测试异常注入失败结果。"""
    result = FaultResult(
        success=False,
        fault_type="test",
        message="注入失败",
        error="Device not ready",
    )

    assert result.success is False
    assert result.error == "Device not ready"


def test_fault_plugin_abstract():
    """测试 FaultPlugin 是抽象类。"""
    from abc import ABC
    assert FaultPlugin.__bases__[0] is ABC


def test_fault_plugin_interface():
    """测试 FaultPlugin 接口方法。"""
    import inspect
    abstract_methods = [
        name for name, method in inspect.getmembers(FaultPlugin, predicate=inspect.ismethod)
        if getattr(method, '__isabstractmethod__', False)
    ]
    assert 'inject' in abstract_methods


def test_fault_plugin_lifecycle():
    """测试异常插件生命周期。"""
    # 检查生命周期方法存在
    assert hasattr(FaultPlugin, 'prepare')
    assert hasattr(FaultPlugin, 'inject')
    assert hasattr(FaultPlugin, 'cleanup')


def test_fault_plugin_metadata():
    """测试异常插件元数据。"""
    class TestFault(FaultPlugin):
        fault_type = "test_fault"
        fault_stage = "precheck"
        description = "测试异常"

        def inject(self, context):
            return FaultResult(success=True, fault_type=self.fault_type, message="OK")

    plugin = TestFault()
    assert plugin.fault_type == "test_fault"
    assert plugin.fault_stage == "precheck"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_faults/test_base.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现异常注入基类**

```python
# app/faults/base.py
"""异常注入插件抽象基类。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any

from app.executors.run_context import RunContext
from app.executors.adb_executor import ADBExecutor


@dataclass
class FaultResult:
    """异常注入结果。"""

    success: bool
    fault_type: str
    message: str
    data: Dict[str, Any]
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "success": self.success,
            "fault_type": self.fault_type,
            "message": self.message,
            "data": self.data,
            "error": self.error,
        }


class FaultPlugin(ABC):
    """异常注入插件抽象基类。"""

    fault_type: str = ""
    fault_stage: str = ""
    description: str = ""

    def __init__(self, executor: Optional[ADBExecutor] = None):
        self.executor = executor or ADBExecutor()

    def prepare(self, context: RunContext) -> FaultResult:
        """准备阶段（可选实现）。"""
        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="准备完成",
            data={},
        )

    @abstractmethod
    def inject(self, context: RunContext) -> FaultResult:
        """注入异常。"""
        pass

    def cleanup(self, context: RunContext) -> FaultResult:
        """清理阶段（可选实现）。"""
        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="清理完成",
            data={},
        )

    def get_parameters(self) -> Dict[str, Any]:
        """获取插件参数（从 fault profile）。"""
        return {}

    def set_parameters(self, params: Dict[str, Any]):
        """设置插件参数。"""
        self._parameters = params

    def validate_parameters(self) -> bool:
        """验证参数有效性。"""
        return True

    def should_inject(self, context: RunContext) -> bool:
        """判断是否应该注入（可根据条件决定）。"""
        return True

    def record_event(self, context: RunContext, message: str, extra: Optional[Dict] = None):
        """记录异常注入事件。"""
        context.record_event(
            "fault_injection",
            message,
            {
                "fault_type": self.fault_type,
                "fault_stage": self.fault_stage,
                "extra": extra or {},
            }
        )
```

```python
# app/faults/__init__.py
"""异常注入模块。"""

from app.faults.base import FaultPlugin, FaultResult

__all__ = [
    "FaultPlugin",
    "FaultResult",
]
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_faults/test_base.py -v`
Expected: PASS - 6 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/faults/base.py app/faults/__init__.py tests/test_faults/test_base.py
git commit -m "feat: add fault injection plugin base class"
```

---

## Task 4.2: 存储压力注入插件

**Files:**
- Create: `app/faults/storage_pressure.py`
- Create: `tests/test_faults/test_storage_pressure.py`

- [ ] **Step 1: 写存储压力插件测试**

```python
# tests/test_faults/test_storage_pressure.py
"""存储压力注入测试。"""

import pytest

from app.faults.storage_pressure import StoragePressureFault
from app.executors.run_context import RunContext
from app.executors.mock_executor import MockExecutor


@pytest.fixture
def mock_executor():
    """创建 Mock 执行器。"""
    executor = MockExecutor()
    executor.set_response("adb shell df", stdout="64G 32G 32G 50% /data\n")
    executor.set_response("adb shell rm", stdout="")
    executor.set_response("adb shell dd", stdout="")
    return executor


@pytest.fixture
def run_context(tmp_path):
    """创建执行上下文。"""
    return RunContext(
        run_id=1,
        device_serial="ABC123",
        plan_id=1,
        upgrade_type="full",
        artifact_dir=tmp_path / "artifacts" / "1",
    )


def test_storage_pressure_plugin_init():
    """测试插件初始化。"""
    plugin = StoragePressureFault()
    assert plugin.fault_type == "storage_pressure"
    assert plugin.fault_stage == "precheck"


def test_storage_pressure_prepare(mock_executor, run_context):
    """测试准备阶段。"""
    plugin = StoragePressureFault(executor=mock_executor)
    plugin.set_parameters({"fill_percent": 90})

    result = plugin.prepare(run_context)

    assert result.success is True


def test_storage_pressure_inject(mock_executor, run_context):
    """测试注入阶段。"""
    plugin = StoragePressureFault(executor=mock_executor)
    plugin.set_parameters({"fill_percent": 90})

    result = plugin.inject(run_context)

    assert result.success is True
    assert "fill_percent" in result.data


def test_storage_pressure_cleanup(mock_executor, run_context):
    """测试清理阶段。"""
    plugin = StoragePressureFault(executor=mock_executor)
    plugin.set_parameters({"fill_percent": 90})

    # 先注入
    plugin.inject(run_context)

    # 再清理
    result = plugin.cleanup(run_context)

    assert result.success is True


def test_storage_pressure_validate_parameters():
    """测试参数验证。"""
    plugin = StoragePressureFault()

    # 有效参数
    plugin.set_parameters({"fill_percent": 50})
    assert plugin.validate_parameters() is True

    # 无效参数（超出范围）
    plugin.set_parameters({"fill_percent": 150})
    assert plugin.validate_parameters() is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_faults/test_storage_pressure.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现存储压力插件**

```python
# app/faults/storage_pressure.py
"""存储压力注入插件。"""

import re
from typing import Dict, Any, Optional

from app.faults.base import FaultPlugin, FaultResult
from app.executors.run_context import RunContext
from app.executors.adb_executor import ADBExecutor


class StoragePressureFault(FaultPlugin):
    """存储压力注入插件。

    通过填充设备存储空间模拟低存储场景。
    """

    fault_type = "storage_pressure"
    fault_stage = "precheck"
    description = "模拟存储空间不足场景"

    DEFAULT_FILL_PERCENT = 90
    DEFAULT_TARGET_PATH = "/data/local/tmp"
    FILL_FILE_NAME = "aegisota_fill_file"

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        fill_percent: Optional[int] = None,
        target_path: Optional[str] = None,
    ):
        super().__init__(executor)
        self.fill_percent = fill_percent or self.DEFAULT_FILL_PERCENT
        self.target_path = target_path or self.DEFAULT_TARGET_PATH
        self._fill_file_path = None
        self._original_storage_info = None

    def set_parameters(self, params: Dict[str, Any]):
        """设置参数。"""
        super().set_parameters(params)
        if "fill_percent" in params:
            self.fill_percent = params["fill_percent"]
        if "target_path" in params:
            self.target_path = params["target_path"]

    def validate_parameters(self) -> bool:
        """验证参数。"""
        if self.fill_percent < 0 or self.fill_percent > 100:
            return False
        return True

    def prepare(self, context: RunContext) -> FaultResult:
        """准备阶段：获取当前存储状态。"""
        self.record_event(context, "检查当前存储状态")

        # 获取存储信息
        storage_result = self.executor.shell(
            "df /data | tail -1",
            device=context.device_serial,
        )

        if storage_result.success:
            self._original_storage_info = storage_result.stdout
            self.record_event(
                context,
                "存储信息获取成功",
                {"storage_info": storage_result.stdout},
            )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="存储状态检查完成",
            data={"original_storage": storage_result.stdout},
        )

    def inject(self, context: RunContext) -> FaultResult:
        """注入阶段：填充存储空间。"""
        self.record_event(
            context,
            f"开始注入存储压力（目标：{self.fill_percent}%）",
        )

        # 获取当前存储使用率
        storage_result = self.executor.shell(
            "df /data | tail -1",
            device=context.device_serial,
        )

        current_usage = 0
        if storage_result.success:
            # 解析 df 输出
            match = re.search(r"(\d+)%", storage_result.stdout)
            if match:
                current_usage = int(match.group(1))

        # 计算需要填充的空间大小
        if current_usage >= self.fill_percent:
            return FaultResult(
                success=True,
                fault_type=self.fault_type,
                message=f"当前存储使用率 {current_usage}% 已超过目标",
                data={"current_usage": current_usage, "target": self.fill_percent},
            )

        # 获取存储总大小（简化处理）
        size_result = self.executor.shell(
            "df /data | head -2 | tail -1",
            device=context.device_serial,
        )

        total_size_kb = 0
        if size_result.success:
            parts = size_result.stdout.split()
            if len(parts) >= 2:
                try:
                    total_size_kb = int(parts[1])
                except ValueError:
                    pass

        # 计算需要填充的大小
        target_usage_kb = int(total_size_kb * self.fill_percent / 100)
        fill_size_kb = target_usage_kb - int(total_size_kb * current_usage / 100)

        if fill_size_kb <= 0:
            return FaultResult(
                success=True,
                fault_type=self.fault_type,
                message="无需填充",
                data={},
            )

        # 执行填充（使用 dd 创建大文件）
        fill_file = f"{self.target_path}/{self.FILL_FILE_NAME}"
        fill_size_mb = fill_size_kb // 1024

        # 使用 dd 创建填充文件
        dd_result = self.executor.shell(
            f"dd if=/dev/zero of={fill_file} bs=1M count={fill_size_mb}",
            device=context.device_serial,
            timeout=120,
        )

        self._fill_file_path = fill_file

        if not dd_result.success:
            return FaultResult(
                success=False,
                fault_type=self.fault_type,
                message="填充文件创建失败",
                data={},
                error=dd_result.stderr,
            )

        self.record_event(
            context,
            f"存储压力注入完成（填充 {fill_size_mb}MB）",
            {"fill_file": fill_file, "fill_size_mb": fill_size_mb},
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message=f"存储压力注入成功，填充 {fill_size_mb}MB",
            data={
                "fill_percent": self.fill_percent,
                "fill_file": fill_file,
                "fill_size_mb": fill_size_mb,
            },
        )

    def cleanup(self, context: RunContext) -> FaultResult:
        """清理阶段：删除填充文件。"""
        if not self._fill_file_path:
            return FaultResult(
                success=True,
                fault_type=self.fault_type,
                message="无需清理（未创建填充文件）",
                data={},
            )

        self.record_event(context, "清理存储压力注入")

        # 删除填充文件
        rm_result = self.executor.shell(
            f"rm -f {self._fill_file_path}",
            device=context.device_serial,
        )

        self._fill_file_path = None

        if not rm_result.success:
            return FaultResult(
                success=False,
                fault_type=self.fault_type,
                message="清理失败",
                data={},
                error=rm_result.stderr,
            )

        self.record_event(context, "存储压力注入清理完成")

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="存储压力注入已清理",
            data={"removed_file": self._fill_file_path},
        )
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_faults/test_storage_pressure.py -v`
Expected: PASS - 5 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/faults/storage_pressure.py tests/test_faults/test_storage_pressure.py
git commit -m "feat: add storage pressure fault injection plugin"
```

---

## Task 4.3: 重启中断注入插件

**Files:**
- Create: `app/faults/reboot_interrupted.py`
- Create: `tests/test_faults/test_reboot_interrupted.py`

- [ ] **Step 1: 写重启中断插件测试**

```python
# tests/test_faults/test_reboot_interrupted.py
"""重启中断注入测试。"""

import pytest

from app.faults.reboot_interrupted import RebootInterruptedFault
from app.executors.run_context import RunContext
from app.executors.mock_executor import MockExecutor


@pytest.fixture
def mock_executor():
    """创建 Mock 执行器。"""
    executor = MockExecutor()
    executor.set_response("adb reboot", stdout="")
    executor.set_response("adb disconnect", stdout="")
    return executor


@pytest.fixture
def run_context(tmp_path):
    """创建执行上下文。"""
    return RunContext(
        run_id=1,
        device_serial="ABC123",
        plan_id=1,
        upgrade_type="full",
        artifact_dir=tmp_path / "artifacts" / "1",
    )


def test_reboot_interrupted_plugin_init():
    """测试插件初始化。"""
    plugin = RebootInterruptedFault()
    assert plugin.fault_type == "reboot_interrupted"
    assert plugin.fault_stage == "apply_update"


def test_reboot_interrupted_prepare(mock_executor, run_context):
    """测试准备阶段。"""
    plugin = RebootInterruptedFault(executor=mock_executor)
    result = plugin.prepare(run_context)

    assert result.success is True


def test_reboot_interrupted_inject(mock_executor, run_context):
    """测试注入阶段。"""
    plugin = RebootInterruptedFault(executor=mock_executor)
    plugin.set_parameters({"interrupt_after_seconds": 5})

    result = plugin.inject(run_context)

    # Mock 执行器应该返回成功
    assert result.success is True


def test_reboot_interrupted_validate_parameters():
    """测试参数验证。"""
    plugin = RebootInterruptedFault()

    plugin.set_parameters({"interrupt_after_seconds": 10})
    assert plugin.validate_parameters() is True

    plugin.set_parameters({"interrupt_after_seconds": -1})
    assert plugin.validate_parameters() is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_faults/test_reboot_interrupted.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现重启中断插件**

```python
# app/faults/reboot_interrupted.py
"""重启中断注入插件。"""

import time
from typing import Dict, Any, Optional

from app.faults.base import FaultPlugin, FaultResult
from app.executors.run_context import RunContext
from app.executors.adb_executor import ADBExecutor


class RebootInterruptedFault(FaultPlugin):
    """重启中断注入插件。

    在重启等待期间模拟中断场景（断开连接或超时）。
    """

    fault_type = "reboot_interrupted"
    fault_stage = "apply_update"
    description = "模拟重启过程中的中断场景"

    DEFAULT_INTERRUPT_AFTER_SECONDS = 10
    DEFAULT_INTERRUPT_TYPE = "disconnect"  # disconnect 或 timeout

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        interrupt_after_seconds: Optional[int] = None,
        interrupt_type: Optional[str] = None,
    ):
        super().__init__(executor)
        self.interrupt_after_seconds = interrupt_after_seconds or self.DEFAULT_INTERRUPT_AFTER_SECONDS
        self.interrupt_type = interrupt_type or self.DEFAULT_INTERRUPT_TYPE

    def set_parameters(self, params: Dict[str, Any]):
        """设置参数。"""
        super().set_parameters(params)
        if "interrupt_after_seconds" in params:
            self.interrupt_after_seconds = params["interrupt_after_seconds"]
        if "interrupt_type" in params:
            self.interrupt_type = params["interrupt_type"]

    def validate_parameters(self) -> bool:
        """验证参数。"""
        if self.interrupt_after_seconds < 0:
            return False
        if self.interrupt_type not in ["disconnect", "timeout"]:
            return False
        return True

    def prepare(self, context: RunContext) -> FaultResult:
        """准备阶段。"""
        self.record_event(
            context,
            f"准备重启中断注入（{self.interrupt_after_seconds}秒后中断）",
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="重启中断准备完成",
            data={
                "interrupt_after_seconds": self.interrupt_after_seconds,
                "interrupt_type": self.interrupt_type,
            },
        )

    def inject(self, context: RunContext) -> FaultResult:
        """注入阶段：发送重启命令后中断连接。"""
        self.record_event(context, "发送重启命令")

        # 发送重启命令
        reboot_result = self.executor.reboot(
            device=context.device_serial,
            timeout=5,
        )

        if not reboot_result.success:
            return FaultResult(
                success=False,
                fault_type=self.fault_type,
                message="重启命令发送失败",
                data={},
                error=reboot_result.stderr,
            )

        # 等待指定时间后模拟中断
        time.sleep(self.interrupt_after_seconds)

        # 记录中断事件
        self.record_event(
            context,
            f"模拟中断（类型：{self.interrupt_type}）",
            {"interrupt_after_seconds": self.interrupt_after_seconds},
        )

        # 断开 ADB 连接（模拟）
        if self.interrupt_type == "disconnect":
            disconnect_result = self.executor.shell(
                "exit",  # 模拟断开
                device=context.device_serial,
            )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message=f"重启中断注入成功（{self.interrupt_after_seconds}秒后中断）",
            data={
                "interrupt_after_seconds": self.interrupt_after_seconds,
                "interrupt_type": self.interrupt_type,
            },
        )

    def cleanup(self, context: RunContext) -> FaultResult:
        """清理阶段。"""
        self.record_event(context, "重启中断注入清理")

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="重启中断清理完成",
            data={},
        )
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_faults/test_reboot_interrupted.py -v`
Expected: PASS - 4 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/faults/reboot_interrupted.py tests/test_faults/test_reboot_interrupted.py
git commit -m "feat: add reboot interrupted fault injection plugin"
```

---

## Task 4.4: Monkey 测试插件

**Files:**
- Create: `app/faults/monkey_after_upgrade.py`
- Create: `tests/test_faults/test_monkey_after_upgrade.py`

- [ ] **Step 1: 写 Monkey 插件测试**

```python
# tests/test_faults/test_monkey_after_upgrade.py
"""Monkey 测试插件测试。"""

import pytest

from app.faults.monkey_after_upgrade import MonkeyAfterUpgradeFault
from app.executors.run_context import RunContext
from app.executors.mock_executor import MockExecutor


@pytest.fixture
def mock_executor():
    """创建 Mock 执行器。"""
    executor = MockExecutor()
    executor.set_response(
        "adb shell monkey",
        stdout="Events injected: 1000\n:Dropped: 0\n:Crashed: 0\n"
    )
    return executor


@pytest.fixture
def run_context(tmp_path):
    """创建执行上下文。"""
    return RunContext(
        run_id=1,
        device_serial="ABC123",
        plan_id=1,
        upgrade_type="full",
        artifact_dir=tmp_path / "artifacts" / "1",
    )


def test_monkey_plugin_init():
    """测试插件初始化。"""
    plugin = MonkeyAfterUpgradeFault()
    assert plugin.fault_type == "monkey_after_upgrade"
    assert plugin.fault_stage == "post_validate"


def test_monkey_plugin_inject(mock_executor, run_context):
    """测试 Monkey 注入。"""
    plugin = MonkeyAfterUpgradeFault(executor=mock_executor)
    plugin.set_parameters({"event_count": 1000})

    result = plugin.inject(run_context)

    assert result.success is True
    assert "events_injected" in result.data


def test_monkey_plugin_parse_results(mock_executor, run_context):
    """测试解析 Monkey 结果。"""
    plugin = MonkeyAfterUpgradeFault(executor=mock_executor)

    result = plugin.inject(run_context)

    assert result.data["events_injected"] >= 0


def test_monkey_plugin_with_crash(mock_executor, run_context):
    """测试 Monkey 发现崩溃。"""
    executor = MockExecutor()
    executor.set_response(
        "adb shell monkey",
        stdout="Events injected: 500\n:Crashed: 1\n** Monkey aborted due to crash\n"
    )

    plugin = MonkeyAfterUpgradeFault(executor=executor)
    result = plugin.inject(run_context)

    # 有崩溃但插件仍应完成
    assert result.success is True
    assert result.data.get("crashed", 0) > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_faults/test_monkey_after_upgrade.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 Monkey 测试插件**

```python
# app/faults/monkey_after_upgrade.py
"""Monkey 稳定性测试插件。"""

import re
from typing import Dict, Any, Optional

from app.config import get_settings
from app.faults.base import FaultPlugin, FaultResult
from app.executors.run_context import RunContext
from app.executors.adb_executor import ADBExecutor


class MonkeyAfterUpgradeFault(FaultPlugin):
    """Monkey 稳定性测试插件。

    在升级后执行 Monkey 测试验证系统稳定性。
    """

    fault_type = "monkey_after_upgrade"
    fault_stage = "post_validate"
    description = "升级后 Monkey 稳定性测试"

    DEFAULT_EVENT_COUNT = 1000
    DEFAULT_THROTTLE = 50  # ms
    DEFAULT_SEED = None

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        event_count: Optional[int] = None,
        throttle: Optional[int] = None,
        seed: Optional[int] = None,
        packages: Optional[str] = None,
    ):
        super().__init__(executor)
        settings = get_settings()
        self.event_count = event_count or settings.MONKEY_DEFAULT_COUNT
        self.throttle = throttle or settings.MONKEY_THROTTLE
        self.seed = seed
        self.packages = packages or "--pct-sysevents 50 --pct-touch 30 --pct-motion 20"

    def set_parameters(self, params: Dict[str, Any]):
        """设置参数。"""
        super().set_parameters(params)
        if "event_count" in params:
            self.event_count = params["event_count"]
        if "throttle" in params:
            self.throttle = params["throttle"]
        if "seed" in params:
            self.seed = params["seed"]
        if "packages" in params:
            self.packages = params["packages"]

    def validate_parameters(self) -> bool:
        """验证参数。"""
        if self.event_count < 0:
            return False
        if self.throttle < 0:
            return False
        return True

    def prepare(self, context: RunContext) -> FaultResult:
        """准备阶段。"""
        self.record_event(
            context,
            f"准备 Monkey 测试（{self.event_count} 事件）",
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="Monkey 测试准备完成",
            data={
                "event_count": self.event_count,
                "throttle": self.throttle,
            },
        )

    def inject(self, context: RunContext) -> FaultResult:
        """注入阶段：执行 Monkey 测试。"""
        self.record_event(context, f"执行 Monkey 测试（{self.event_count} 事件）")

        # 构建 Monkey 命令
        monkey_cmd = self._build_monkey_command()

        # 执行 Monkey
        result = self.executor.shell(
            monkey_cmd,
            device=context.device_serial,
            timeout=self.event_count * self.throttle // 1000 + 60,  # 预估时间 + 缓冲
        )

        # 保存 Monkey 输出
        if context.artifact_dir:
            monkey_output_file = context.artifact_dir / "monkey_output.txt"
            with open(monkey_output_file, "w") as f:
                f.write(result.stdout)

        # 解析结果
        monkey_stats = self._parse_monkey_output(result.stdout)

        self.record_event(
            context,
            f"Monkey 测试完成",
            monkey_stats,
        )

        return FaultResult(
            success=result.success,
            fault_type=self.fault_type,
            message=f"Monkey 测试完成：注入 {monkey_stats.get('events_injected', 0)} 事件",
            data=monkey_stats,
            error=result.stderr if not result.success else None,
        )

    def cleanup(self, context: RunContext) -> FaultResult:
        """清理阶段。"""
        self.record_event(context, "Monkey 测试清理")

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="Monkey 测试清理完成",
            data={},
        )

    def _build_monkey_command(self) -> str:
        """构建 Monkey 命令。"""
        cmd_parts = [
            "monkey",
            "-v",  # 详细输出
            f"--throttle {self.throttle}",
            self.packages,
            f"-s {self.seed}" if self.seed else "",
            f"{self.event_count}",
        ]

        return " ".join(filter(None, cmd_parts))

    def _parse_monkey_output(self, output: str) -> Dict[str, Any]:
        """解析 Monkey 输出。"""
        stats = {
            "events_injected": 0,
            "dropped": 0,
            "crashed": 0,
            "timeout": 0,
            "network": 0,
        }

        # 解析事件数
        match = re.search(r"Events injected: (\d+)", output)
        if match:
            stats["events_injected"] = int(match.group(1))

        # 解析 dropped
        match = re.search(r":Dropped: (\d+)", output)
        if match:
            stats["dropped"] = int(match.group(1))

        # 解析 crashed
        match = re.search(r":Crashed: (\d+)", output)
        if match:
            stats["crashed"] = int(match.group(1))

        # 检查是否因崩溃中止
        if "Monkey aborted" in output:
            stats["aborted"] = True
            stats["abort_reason"] = "crash" if "crash" in output.lower() else "unknown"

        return stats
```

- [ ] **Step 4: 更新 faults/__init__.py**

```python
# app/faults/__init__.py
"""异常注入模块。"""

from app.faults.base import FaultPlugin, FaultResult
from app.faults.storage_pressure import StoragePressureFault
from app.faults.reboot_interrupted import RebootInterruptedFault
from app.faults.monkey_after_upgrade import MonkeyAfterUpgradeFault

__all__ = [
    "FaultPlugin",
    "FaultResult",
    "StoragePressureFault",
    "RebootInterruptedFault",
    "MonkeyAfterUpgradeFault",
]
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_faults/test_monkey_after_upgrade.py -v`
Expected: PASS - 4 tests passed

- [ ] **Step 6: 提交**

```bash
git add app/faults/monkey_after_upgrade.py app/faults/__init__.py tests/test_faults/test_monkey_after_upgrade.py
git commit -m "feat: add monkey stability test fault injection plugin"
```

---

## Task 4.5: 下载中断注入插件

**Files:**
- Create: `app/faults/download_interrupted.py`
- Create: `tests/test_faults/test_download_interrupted.py`

- [ ] **Step 1: 写下载中断插件测试**

```python
# tests/test_faults/test_download_interrupted.py
"""下载中断注入测试。"""

import pytest

from app.faults.download_interrupted import DownloadInterruptedFault
from app.executors.run_context import RunContext
from app.executors.mock_executor import MockExecutor


@pytest.fixture
def mock_executor():
    """创建 Mock 执行器。"""
    executor = MockExecutor()
    executor.set_response("adb shell rm", stdout="")
    executor.set_response("adb shell ls", stdout="")
    return executor


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


def test_download_interrupted_plugin_init():
    """测试插件初始化。"""
    plugin = DownloadInterruptedFault()
    assert plugin.fault_type == "download_interrupted"
    assert plugin.fault_stage == "precheck"


def test_download_interrupted_inject(mock_executor, run_context):
    """测试下载中断注入。"""
    plugin = DownloadInterruptedFault(executor=mock_executor)
    plugin.set_parameters({"interrupt_point": "before_download"})

    result = plugin.inject(run_context)

    assert result.success is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_faults/test_download_interrupted.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现下载中断插件**

```python
# app/faults/download_interrupted.py
"""下载中断注入插件。"""

from typing import Dict, Any, Optional

from app.faults.base import FaultPlugin, FaultResult
from app.executors.run_context import RunContext
from app.executors.adb_executor import ADBExecutor


class DownloadInterruptedFault(FaultPlugin):
    """下载中断注入插件。

    模拟升级包下载过程中的中断场景。
    """

    fault_type = "download_interrupted"
    fault_stage = "precheck"
    description = "模拟升级包下载中断场景"

    # 中断点选项
    INTERRUPT_POINTS = [
        "before_download",  # 下载前删除包
        "during_download",  # 下载过程中模拟中断
        "after_download",   # 下载后损坏包
    ]

    DEFAULT_INTERRUPT_POINT = "before_download"

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        interrupt_point: Optional[str] = None,
    ):
        super().__init__(executor)
        self.interrupt_point = interrupt_point or self.DEFAULT_INTERRUPT_POINT

    def set_parameters(self, params: Dict[str, Any]):
        """设置参数。"""
        super().set_parameters(params)
        if "interrupt_point" in params:
            self.interrupt_point = params["interrupt_point"]

    def validate_parameters(self) -> bool:
        """验证参数。"""
        return self.interrupt_point in self.INTERRUPT_POINTS

    def prepare(self, context: RunContext) -> FaultResult:
        """准备阶段。"""
        self.record_event(
            context,
            f"准备下载中断注入（中断点：{self.interrupt_point}）",
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="下载中断准备完成",
            data={"interrupt_point": self.interrupt_point},
        )

    def inject(self, context: RunContext) -> FaultResult:
        """注入阶段：根据中断点执行不同操作。"""
        self.record_event(context, f"执行下载中断（{self.interrupt_point}）")

        remote_path = "/data/local/tmp/update.zip"

        if self.interrupt_point == "before_download":
            # 在推送前确保没有现有包
            rm_result = self.executor.shell(
                f"rm -f {remote_path}",
                device=context.device_serial,
            )

            self.record_event(context, "删除现有升级包")

            return FaultResult(
                success=True,
                fault_type=self.fault_type,
                message="下载前中断：已删除现有包",
                data={
                    "interrupt_point": self.interrupt_point,
                    "remote_path": remote_path,
                },
            )

        elif self.interrupt_point == "during_download":
            # 在推送过程中模拟网络中断（实际实现需要更复杂的逻辑）
            # 这里简化为删除部分下载的包
            rm_result = self.executor.shell(
                f"rm -f {remote_path}",
                device=context.device_serial,
            )

            return FaultResult(
                success=True,
                fault_type=self.fault_type,
                message="下载过程中中断：已删除部分下载的包",
                data={"interrupt_point": self.interrupt_point},
            )

        elif self.interrupt_point == "after_download":
            # 下载完成后损坏包（通过删除部分内容模拟）
            # 简化处理：直接删除包
            rm_result = self.executor.shell(
                f"rm -f {remote_path}",
                device=context.device_serial,
            )

            return FaultResult(
                success=True,
                fault_type=self.fault_type,
                message="下载后中断：已损坏升级包",
                data={"interrupt_point": self.interrupt_point},
            )

        return FaultResult(
            success=False,
            fault_type=self.fault_type,
            message="未知中断点",
            data={},
            error=f"Invalid interrupt_point: {self.interrupt_point}",
        )

    def cleanup(self, context: RunContext) -> FaultResult:
        """清理阶段。"""
        self.record_event(context, "下载中断注入清理")

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="下载中断清理完成",
            data={},
        )
```

- [ ] **Step 4: 更新 faults/__init__.py 并运行测试**

```python
# app/faults/__init__.py
"""异常注入模块。"""

from app.faults.base import FaultPlugin, FaultResult
from app.faults.storage_pressure import StoragePressureFault
from app.faults.reboot_interrupted import RebootInterruptedFault
from app.faults.monkey_after_upgrade import MonkeyAfterUpgradeFault
from app.faults.download_interrupted import DownloadInterruptedFault

__all__ = [
    "FaultPlugin",
    "FaultResult",
    "StoragePressureFault",
    "RebootInterruptedFault",
    "MonkeyAfterUpgradeFault",
    "DownloadInterruptedFault",
]
```

Run: `pytest tests/test_faults/ -v`
Expected: PASS - all tests passed

- [ ] **Step 5: 提交**

```bash
git add app/faults/download_interrupted.py app/faults/__init__.py tests/test_faults/test_download_interrupted.py
git commit -m "feat: add download interrupted fault injection plugin"
```

---

## Phase 4 完成检查

Run: `pytest tests/test_faults/ -v --tb=short`
Expected: All tests passed