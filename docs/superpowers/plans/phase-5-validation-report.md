# Phase 5: 升级后验证与报告生成

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现完整的升级后验证流程和结构化报告生成系统。

**Architecture:** 验证模块负责开机检测、版本确认、Monkey 测试、性能检查。报告模块负责失败分类、时间线整理、HTML/Markdown 输出。

**Tech Stack:** Python, Jinja2, SQLAlchemy

---

## 文件结构

```
app/validators/
├── monkey_runner.py            # Monkey 执行器
├── perf_check.py               # 性能检查

app/reporting/
├── __init__.py
├── generator.py                # 报告生成器
├── failure_classifier.py       # 失败分类器
├── templates/
│   ├── report.html             # HTML 报告模板
│   └── report.md               # Markdown 报告模板

tests/test_validators/
├── test_monkey_runner.py
├── test_perf_check.py

tests/test_reporting/
├── test_generator.py
├── test_failure_classifier.py
```

---

## Task 5.1: Monkey 执行器

**Files:**
- Create: `app/validators/monkey_runner.py`
- Create: `tests/test_validators/test_monkey_runner.py`

- [ ] **Step 1: 写 Monkey 执行器测试**

```python
# tests/test_validators/test_monkey_runner.py
"""Monkey 执行器测试。"""

import pytest

from app.validators.monkey_runner import MonkeyRunner, MonkeyResult
from app.executors.mock_executor import MockExecutor


def test_monkey_runner_init():
    """测试 Monkey 执行器初始化。"""
    runner = MonkeyRunner()
    assert runner.default_event_count == 1000


def test_monkey_runner_custom_config():
    """测试自定义配置。"""
    runner = MonkeyRunner(event_count=5000, throttle=100)
    assert runner.event_count == 5000
    assert runner.throttle == 100


def test_monkey_runner_execute_success():
    """测试 Monkey 执行成功。"""
    executor = MockExecutor()
    executor.set_response(
        "adb shell monkey",
        stdout="Events injected: 1000\n:Dropped: 0\n:Crashed: 0\n## Network stats: 0\n"
    )

    runner = MonkeyRunner(executor=executor)
    result = runner.run("ABC123")

    assert result.success is True
    assert result.events_injected == 1000


def test_monkey_runner_parse_output():
    """测试解析 Monkey 输出。"""
    runner = MonkeyRunner()

    output = """Events injected: 1000
:Dropped: 5
:Crashed: 0
## Network stats: elapsed time=10s
"""

    stats = runner.parse_output(output)
    assert stats["events_injected"] == 1000
    assert stats["dropped"] == 5
    assert stats["crashed"] == 0


def test_monkey_runner_with_crash():
    """测试 Monkey 发现崩溃。"""
    executor = MockExecutor()
    executor.set_response(
        "adb shell monkey",
        stdout="Events injected: 500\n:Crashed: 1\n** Monkey aborted **\n"
    )

    runner = MonkeyRunner(executor=executor)
    result = runner.run("ABC123")

    assert result.success is True  # 执行完成，但发现崩溃
    assert result.crashed == 1


def test_monkey_result_to_dict():
    """测试 Monkey 结果转换。"""
    result = MonkeyResult(
        success=True,
        events_injected=1000,
        dropped=0,
        crashed=0,
        duration_ms=5000,
        aborted=False,
    )

    data = result.to_dict()
    assert data["events_injected"] == 1000
    assert data["success"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_validators/test_monkey_runner.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现 Monkey 执行器**

```python
# app/validators/monkey_runner.py
"""Monkey 稳定性测试执行器。"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import get_settings
from app.executors.adb_executor import ADBExecutor


@dataclass
class MonkeyResult:
    """Monkey 测试结果。"""

    success: bool
    events_injected: int
    dropped: int
    crashed: int
    timeout: int
    network_errors: int
    duration_ms: int
    aborted: bool
    abort_reason: Optional[str] = None
    command: Optional[str] = None
    output: Optional[str] = None
    output_file: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "success": self.success,
            "events_injected": self.events_injected,
            "dropped": self.dropped,
            "crashed": self.crashed,
            "timeout": self.timeout,
            "network_errors": self.network_errors,
            "duration_ms": self.duration_ms,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
        }

    def is_stable(self) -> bool:
        """判断系统是否稳定。"""
        return self.success and self.crashed == 0 and not self.aborted


class MonkeyRunner:
    """Monkey 稳定性测试执行器。"""

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        event_count: Optional[int] = None,
        throttle: Optional[int] = None,
        seed: Optional[int] = None,
    ):
        settings = get_settings()
        self.executor = executor or ADBExecutor()
        self.default_event_count = event_count or settings.MONKEY_DEFAULT_COUNT
        self.default_throttle = throttle or settings.MONKEY_THROTTLE
        self.default_seed = seed

    def run(
        self,
        device_serial: str,
        event_count: Optional[int] = None,
        throttle: Optional[int] = None,
        seed: Optional[int] = None,
        packages: Optional[str] = None,
        output_file: Optional[Path] = None,
    ) -> MonkeyResult:
        """执行 Monkey 测试。"""
        import time

        start_time = time.time()

        # 构建命令参数
        count = event_count or self.default_event_count
        delay = throttle or self.default_throttle
        random_seed = seed or self.default_seed or int(time.time())

        # 构建 Monkey 命令
        cmd = self._build_command(count, delay, random_seed, packages)

        # 执行 Monkey
        result = self.executor.shell(
            cmd,
            device=device_serial,
            timeout=count * delay // 1000 + 120,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # 解析输出
        stats = self.parse_output(result.stdout)

        # 保存输出
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w") as f:
                f.write(result.stdout)
            stats["output_file"] = str(output_file)

        return MonkeyResult(
            success=result.success,
            events_injected=stats.get("events_injected", 0),
            dropped=stats.get("dropped", 0),
            crashed=stats.get("crashed", 0),
            timeout=stats.get("timeout", 0),
            network_errors=stats.get("network_errors", 0),
            duration_ms=duration_ms,
            aborted=stats.get("aborted", False),
            abort_reason=stats.get("abort_reason"),
            command=cmd,
            output=result.stdout,
            output_file=output_file,
        )

    def _build_command(
        self,
        count: int,
        throttle: int,
        seed: int,
        packages: Optional[str] = None,
    ) -> str:
        """构建 Monkey 命令。"""
        parts = [
            "monkey",
            "-v",
            f"--throttle {throttle}",
            f"-s {seed}",
        ]

        if packages:
            parts.append(packages)
        else:
            # 默认事件分布
            parts.append("--pct-sysevents 50 --pct-touch 30 --pct-motion 20")

        parts.append(str(count))

        return " ".join(parts)

    def parse_output(self, output: str) -> Dict[str, Any]:
        """解析 Monkey 输出。"""
        stats = {
            "events_injected": 0,
            "dropped": 0,
            "crashed": 0,
            "timeout": 0,
            "network_errors": 0,
            "aborted": False,
            "abort_reason": None,
        }

        # Events injected
        match = re.search(r"Events injected: (\d+)", output)
        if match:
            stats["events_injected"] = int(match.group(1))

        # Dropped
        match = re.search(r":Dropped: (\d+)", output)
        if match:
            stats["dropped"] = int(match.group(1))

        # Crashed
        match = re.search(r":Crashed: (\d+)", output)
        if match:
            stats["crashed"] = int(match.group(1))

        # Timeout
        match = re.search(r":Timeout: (\d+)", output)
        if match:
            stats["timeout"] = int(match.group(1))

        # Network errors
        match = re.search(r":Network errors: (\d+)", output)
        if match:
            stats["network_errors"] = int(match.group(1))

        # Check abort
        if "Monkey aborted" in output or "** Monkey aborted" in output:
            stats["aborted"] = True
            # 尝试找出 abort 原因
            if "crash" in output.lower():
                stats["abort_reason"] = "crash"
            elif "timeout" in output.lower():
                stats["abort_reason"] = "timeout"
            else:
                stats["abort_reason"] = "unknown"

        return stats
```

- [ ] **Step 4: 更新 validators/__init__.py**

```python
# app/validators/__init__.py
"""验证器模块。"""

from app.validators.boot_check import BootChecker, BootCheckResult
from app.validators.version_check import VersionChecker, VersionCheckResult
from app.validators.monkey_runner import MonkeyRunner, MonkeyResult

__all__ = [
    "BootChecker",
    "BootCheckResult",
    "VersionChecker",
    "VersionCheckResult",
    "MonkeyRunner",
    "MonkeyResult",
]
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_validators/test_monkey_runner.py -v`
Expected: PASS - 6 tests passed

- [ ] **Step 6: 提交**

```bash
git add app/validators/monkey_runner.py app/validators/__init__.py tests/test_validators/test_monkey_runner.py
git commit -m "feat: add monkey runner for stability testing"
```

---

## Task 5.2: 性能检查器

**Files:**
- Create: `app/validators/perf_check.py`
- Create: `tests/test_validators/test_perf_check.py`

- [ ] **Step 1: 写性能检查器测试**

```python
# tests/test_validators/test_perf_check.py
"""性能检查器测试。"""

import pytest

from app.validators.perf_check import PerfChecker, PerfCheckResult
from app.executors.mock_executor import MockExecutor


def test_perf_checker_init():
    """测试性能检查器初始化。"""
    checker = PerfChecker()
    assert checker is not None


def test_perf_checker_collect_metrics():
    """测试收集性能指标。"""
    executor = MockExecutor()
    executor.set_response("adb shell cat /proc/meminfo", stdout="MemTotal: 8192000 kB\nMemFree: 4000000 kB\n")
    executor.set_response("adb shell dumpsys cpuinfo", stdout="CPU usage: 5%\n")

    checker = PerfChecker(executor=executor)
    metrics = checker.collect_metrics("ABC123")

    assert "memory" in metrics
    assert "cpu" in metrics


def test_perf_checker_get_boot_time():
    """测试获取启动时间。"""
    executor = MockExecutor()
    executor.set_response(
        "adb shell getprop",
        stdout="[sys.boot_time]: [30000]\n"
    )

    checker = PerfChecker(executor=executor)
    boot_time = checker.get_boot_time("ABC123")

    assert boot_time >= 0


def test_perf_check_result_creation():
    """测试性能检查结果创建。"""
    result = PerfCheckResult(
        passed=True,
        memory_usage_percent=50.0,
        cpu_usage_percent=10.0,
        boot_time_ms=30000,
        message="性能指标正常",
    )

    assert result.passed is True
    assert result.memory_usage_percent == 50.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_validators/test_perf_check.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现性能检查器**

```python
# app/validators/perf_check.py
"""性能检查验证器。"""

import re
from dataclasses import dataclass
from typing import Dict, Any, Optional

from app.executors.adb_executor import ADBExecutor


@dataclass
class PerfCheckResult:
    """性能检查结果。"""

    passed: bool
    memory_usage_percent: float
    cpu_usage_percent: float
    boot_time_ms: int
    message: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "passed": self.passed,
            "memory_usage_percent": self.memory_usage_percent,
            "cpu_usage_percent": self.cpu_usage_percent,
            "boot_time_ms": self.boot_time_ms,
            "message": self.message,
            "details": self.details,
        }


class PerfChecker:
    """性能检查器。"""

    # 性能阈值
    DEFAULT_MEMORY_THRESHOLD = 80.0  # 内存使用率上限
    DEFAULT_CPU_THRESHOLD = 50.0    # CPU 使用率上限
    DEFAULT_BOOT_TIME_THRESHOLD = 60000  # 启动时间上限（ms）

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        memory_threshold: Optional[float] = None,
        cpu_threshold: Optional[float] = None,
        boot_time_threshold: Optional[int] = None,
    ):
        self.executor = executor or ADBExecutor()
        self.memory_threshold = memory_threshold or self.DEFAULT_MEMORY_THRESHOLD
        self.cpu_threshold = cpu_threshold or self.DEFAULT_CPU_THRESHOLD
        self.boot_time_threshold = boot_time_threshold or self.DEFAULT_BOOT_TIME_THRESHOLD

    def check(self, device_serial: str) -> PerfCheckResult:
        """执行性能检查。"""
        metrics = self.collect_metrics(device_serial)

        # 解析指标
        memory_usage = metrics.get("memory_usage_percent", 0.0)
        cpu_usage = metrics.get("cpu_usage_percent", 0.0)
        boot_time = metrics.get("boot_time_ms", 0)

        # 判断是否通过
        passed = (
            memory_usage < self.memory_threshold and
            cpu_usage < self.cpu_threshold and
            boot_time < self.boot_time_threshold
        )

        # 构建消息
        issues = []
        if memory_usage >= self.memory_threshold:
            issues.append(f"内存使用率过高 ({memory_usage:.1f}%)")
        if cpu_usage >= self.cpu_threshold:
            issues.append(f"CPU 使用率过高 ({cpu_usage:.1f}%)")
        if boot_time >= self.boot_time_threshold:
            issues.append(f"启动时间过长 ({boot_time}ms)")

        message = "性能检查通过" if passed else "; ".join(issues)

        return PerfCheckResult(
            passed=passed,
            memory_usage_percent=memory_usage,
            cpu_usage_percent=cpu_usage,
            boot_time_ms=boot_time,
            message=message,
            details=metrics,
        )

    def collect_metrics(self, device_serial: str) -> Dict[str, Any]:
        """收集性能指标。"""
        metrics = {}

        # 内存信息
        mem_result = self.executor.shell(
            "cat /proc/meminfo | head -5",
            device=device_serial,
        )
        if mem_result.success:
            metrics["memory"] = self._parse_memory(mem_result.stdout)

        # CPU 信息
        cpu_result = self.executor.shell(
            "dumpsys cpuinfo | head -10",
            device=device_serial,
        )
        if cpu_result.success:
            metrics["cpu"] = self._parse_cpu(cpu_result.stdout)

        # 启动时间
        metrics["boot_time_ms"] = self.get_boot_time(device_serial)

        # 计算使用率
        mem_info = metrics.get("memory", {})
        if mem_info:
            total = mem_info.get("total_kb", 0)
            free = mem_info.get("free_kb", 0)
            if total > 0:
                metrics["memory_usage_percent"] = (total - free) / total * 100

        cpu_info = metrics.get("cpu", {})
        if cpu_info:
            metrics["cpu_usage_percent"] = cpu_info.get("usage_percent", 0.0)

        return metrics

    def get_boot_time(self, device_serial: str) -> int:
        """获取启动时间。"""
        props = self.executor.getprop(device=device_serial)

        # 尝试获取 boot_time 属性
        boot_time_str = props.get("sys.boot_time", "0")
        try:
            return int(boot_time_str)
        except ValueError:
            return 0

    def _parse_memory(self, output: str) -> Dict[str, int]:
        """解析内存信息。"""
        mem_info = {}

        match = re.search(r"MemTotal:\s+(\d+)", output)
        if match:
            mem_info["total_kb"] = int(match.group(1))

        match = re.search(r"MemFree:\s+(\d+)", output)
        if match:
            mem_info["free_kb"] = int(match.group(1))

        match = re.search(r"MemAvailable:\s+(\d+)", output)
        if match:
            mem_info["available_kb"] = int(match.group(1))

        return mem_info

    def _parse_cpu(self, output: str) -> Dict[str, Any]:
        """解析 CPU 信息。"""
        cpu_info = {}

        # 尝试解析 CPU 使用率
        match = re.search(r"CPU usage:\s+(\d+\.?\d*)%", output)
        if match:
            cpu_info["usage_percent"] = float(match.group(1))

        return cpu_info
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_validators/test_perf_check.py -v`
Expected: PASS - 4 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/validators/perf_check.py tests/test_validators/test_perf_check.py
git commit -m "feat: add performance checker for post-upgrade validation"
```

---

## Task 5.3: 失败分类器

**Files:**
- Create: `app/reporting/__init__.py`
- Create: `app/reporting/failure_classifier.py`
- Create: `tests/test_reporting/test_failure_classifier.py`

- [ ] **Step 1: 写失败分类器测试**

```python
# tests/test_reporting/test_failure_classifier.py
"""失败分类器测试。"""

import pytest

from app.reporting.failure_classifier import FailureClassifier, FailureCategory


def test_failure_category_values():
    """测试失败分类枚举值。"""
    assert FailureCategory.PACKAGE_ISSUE.value == "package_issue"
    assert FailureCategory.DEVICE_ENV_ISSUE.value == "device_env_issue"
    assert FailureCategory.BOOT_FAILURE.value == "boot_failure"
    assert FailureCategory.UNKNOWN.value == "unknown"


def test_classifier_init():
    """测试分类器初始化。"""
    classifier = FailureClassifier()
    assert classifier is not None


def test_classify_precheck_failure():
    """测试分类升级前检查失败。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="precheck",
        error_message="Battery level too low",
        step_results={"precheck": {"battery_level": 10}},
    )

    assert result == FailureCategory.DEVICE_ENV_ISSUE


def test_classify_push_failure():
    """测试分类推送失败。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="push_package",
        error_message="No space left on device",
        step_results={},
    )

    assert result == FailureCategory.DEVICE_ENV_ISSUE


def test_classify_reboot_failure():
    """测试分类重启失败。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="reboot_wait",
        error_message="Device did not boot within timeout",
        step_results={},
    )

    assert result == FailureCategory.BOOT_FAILURE


def test_classify_validation_failure():
    """测试分类验证失败。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="post_validate",
        error_message="Version mismatch",
        step_results={"post_validate": {"version_mismatch": True}},
    )

    assert result == FailureCategory.VALIDATION_FAILURE


def test_classify_unknown():
    """测试分类未知错误。"""
    classifier = FailureClassifier()

    result = classifier.classify(
        failed_step="unknown",
        error_message="Some unknown error",
        step_results={},
    )

    assert result == FailureCategory.UNKNOWN


def test_get_recommendation():
    """测试获取建议。"""
    classifier = FailureClassifier()

    rec = classifier.get_recommendation(FailureCategory.DEVICE_ENV_ISSUE)
    assert "检查设备状态" in rec or "设备" in rec
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_reporting/test_failure_classifier.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 实现失败分类器**

```python
# app/reporting/failure_classifier.py
"""失败分类器模块。"""

import re
from enum import Enum
from typing import Dict, Any, Optional

from app.models.run import StepName


class FailureCategory(str, Enum):
    """失败分类枚举。"""

    PACKAGE_ISSUE = "package_issue"
    DEVICE_ENV_ISSUE = "device_env_issue"
    BOOT_FAILURE = "boot_failure"
    VALIDATION_FAILURE = "validation_failure"
    MONKEY_INSTABILITY = "monkey_instability"
    PERFORMANCE_SUSPECT = "performance_suspect"
    ADB_TRANSPORT_ISSUE = "adb_transport_issue"
    UNKNOWN = "unknown"


# 分类规则
CLASSIFICATION_RULES = {
    StepName.PRECHECK: {
        "battery": FailureCategory.DEVICE_ENV_ISSUE,
        "storage": FailureCategory.DEVICE_ENV_ISSUE,
        "offline": FailureCategory.ADB_TRANSPORT_ISSUE,
        "health": FailureCategory.DEVICE_ENV_ISSUE,
    },
    StepName.PACKAGE_PREPARE: {
        "space": FailureCategory.DEVICE_ENV_ISSUE,
        "permission": FailureCategory.DEVICE_ENV_ISSUE,
        "corrupted": FailureCategory.PACKAGE_ISSUE,
        "download": FailureCategory.PACKAGE_ISSUE,
        "transport": FailureCategory.ADB_TRANSPORT_ISSUE,
    },
    StepName.APPLY_UPDATE: {
        "package": FailureCategory.PACKAGE_ISSUE,
        "version": FailureCategory.PACKAGE_ISSUE,
        "apply": FailureCategory.PACKAGE_ISSUE,
        "timeout": FailureCategory.BOOT_FAILURE,
    },
    StepName.REBOOT_WAIT: {
        "boot": FailureCategory.BOOT_FAILURE,
        "timeout": FailureCategory.BOOT_FAILURE,
        "watchdog": FailureCategory.BOOT_FAILURE,
        "restart": FailureCategory.BOOT_FAILURE,
    },
    StepName.POST_VALIDATE: {
        "version": FailureCategory.VALIDATION_FAILURE,
        "boot": FailureCategory.BOOT_FAILURE,
        "crash": FailureCategory.MONKEY_INSTABILITY,
        "monkey": FailureCategory.MONKEY_INSTABILITY,
        "perf": FailureCategory.PERFORMANCE_SUSPECT,
        "memory": FailureCategory.PERFORMANCE_SUSPECT,
    },
}

# 建议模板
RECOMMENDATIONS = {
    FailureCategory.PACKAGE_ISSUE: "检查升级包是否完整，验证包签名和版本信息。建议重新生成或下载升级包。",
    FailureCategory.DEVICE_ENV_ISSUE: "检查设备状态：电量、存储空间、网络连接。建议恢复设备环境后重试。",
    FailureCategory.BOOT_FAILURE: "检查设备启动日志（logcat），确认是否存在 watchdog 重启或关键进程异常。建议隔离设备进行人工排查。",
    FailureCategory.VALIDATION_FAILURE: "检查升级后版本信息，确认升级是否正确完成。可能需要重新执行升级或回滚。",
    FailureCategory.MONKEY_INSTABILITY: "Monkey 测试发现系统不稳定，检查崩溃日志和应用异常。建议进行更深入的系统稳定性测试。",
    FailureCategory.PERFORMANCE_SUSPECT: "性能指标异常，检查内存泄漏或 CPU 占用过高的问题。建议进行性能分析。",
    FailureCategory.ADB_TRANSPORT_ISSUE: "ADB 连接异常，检查 USB 连接或网络 adb 配置。建议检查设备连接状态。",
    FailureCategory.UNKNOWN: "未知错误，建议查看详细日志进行人工分析。",
}


class FailureClassifier:
    """失败分类器。"""

    def __init__(self):
        self.rules = CLASSIFICATION_RULES
        self.recommendations = RECOMMENDATIONS

    def classify(
        self,
        failed_step: str,
        error_message: str,
        step_results: Dict[str, Any],
    ) -> FailureCategory:
        """根据失败信息进行分类。"""

        # 转换步骤名称
        try:
            step_name = StepName(failed_step)
        except ValueError:
            step_name = None

        # 获取该步骤的规则
        if step_name and step_name in self.rules:
            step_rules = self.rules[step_name]

            # 匹配错误消息中的关键词
            for keyword, category in step_rules.items():
                if keyword.lower() in error_message.lower():
                    return category

            # 检查步骤结果中的特定标志
            step_result = step_results.get(failed_step, {})
            for keyword, category in step_rules.items():
                if step_result.get(keyword) or step_result.get(f"{keyword}_issue"):
                    return category

        # 默认返回 UNKNOWN
        return FailureCategory.UNKNOWN

    def classify_from_context(
        self,
        failed_step: StepName,
        error: str,
        context_data: Dict[str, Any],
    ) -> FailureCategory:
        """从执行上下文数据进行分类。"""
        return self.classify(
            failed_step.value,
            error,
            context_data.get("step_results", {}),
        )

    def get_recommendation(self, category: FailureCategory) -> str:
        """获取处理建议。"""
        return self.recommendations.get(category, self.recommendations[FailureCategory.UNKNOWN])

    def get_next_actions(self, category: FailureCategory) -> list:
        """获取下一步行动建议。"""
        actions = []

        if category == FailureCategory.PACKAGE_ISSUE:
            actions = [
                "验证升级包完整性",
                "检查包签名",
                "重新下载或生成升级包",
            ]
        elif category == FailureCategory.DEVICE_ENV_ISSUE:
            actions = [
                "检查设备电量",
                "清理存储空间",
                "重启设备后重试",
            ]
        elif category == FailureCategory.BOOT_FAILURE:
            actions = [
                "收集 logcat 日志",
                "检查 watchdog 重启记录",
                "隔离设备进行人工排查",
            ]
        elif category == FailureCategory.VALIDATION_FAILURE:
            actions = [
                "确认升级版本",
                "检查升级日志",
                "考虑执行回滚",
            ]
        elif category == FailureCategory.MONKEY_INSTABILITY:
            actions = [
                "分析崩溃日志",
                "定位问题应用",
                "增加 Monkey 测试时长",
            ]
        elif category == FailureCategory.ADB_TRANSPORT_ISSUE:
            actions = [
                "检查 USB 连接",
                "重启 adb server",
                "检查网络 adb 配置",
            ]
        else:
            actions = [
                "查看详细日志",
                "人工分析失败原因",
            ]

        return actions
```

```python
# app/reporting/__init__.py
"""报告模块。"""

from app.reporting.failure_classifier import FailureClassifier, FailureCategory

__all__ = [
    "FailureClassifier",
    "FailureCategory",
]
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_reporting/test_failure_classifier.py -v`
Expected: PASS - 7 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/reporting/__init__.py app/reporting/failure_classifier.py tests/test_reporting/test_failure_classifier.py
git commit -m "feat: add failure classifier with category detection"
```

---

## Task 5.4: 报告生成器

**Files:**
- Create: `app/reporting/generator.py`
- Create: `app/reporting/templates/report.html`
- Create: `app/reporting/templates/report.md`
- Create: `tests/test_reporting/test_generator.py`

- [ ] **Step 1: 写报告生成器测试**

```python
# tests/test_reporting/test_generator.py
"""报告生成器测试。"""

import pytest
from pathlib import Path

from app.reporting.generator import ReportGenerator
from app.reporting.failure_classifier import FailureCategory
from app.models.run import RunSession, RunStatus


def test_report_generator_init():
    """测试报告生成器初始化。"""
    generator = ReportGenerator()
    assert generator is not None


def test_generate_summary():
    """测试生成摘要。"""
    generator = ReportGenerator()

    summary = generator.generate_summary(
        run_id=1,
        status="passed",
        duration_seconds=300,
        steps_count=5,
    )

    assert "run_id" in summary
    assert summary["status"] == "passed"


def test_generate_failure_report():
    """测试生成失败报告。"""
    generator = ReportGenerator()

    report = generator.generate(
        run_id=1,
        plan_name="测试升级计划",
        device_serial="ABC123",
        status=RunStatus.FAILED,
        failed_step="reboot_wait",
        failure_category=FailureCategory.BOOT_FAILURE,
        timeline=[],
        step_results={},
    )

    assert report["status"] == "failed"
    assert report["failure_category"] == "boot_failure"


def test_generate_markdown():
    """测试生成 Markdown 格式。"""
    generator = ReportGenerator()

    md_content = generator.generate_markdown(
        run_id=1,
        plan_name="测试计划",
        device_serial="ABC123",
        status="passed",
        timeline=[],
    )

    assert "# Run Report" in md_content or "报告" in md_content


def test_generate_html():
    """测试生成 HTML 格式。"""
    generator = ReportGenerator()

    html_content = generator.generate_html(
        run_id=1,
        plan_name="测试计划",
        device_serial="ABC123",
        status="passed",
        timeline=[],
    )

    assert "<html" in html_content.lower() or "<!doctype" in html_content.lower()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_reporting/test_generator.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 3: 创建报告模板目录**

Run: `mkdir -p app/reporting/templates`

- [ ] **Step 4: 创建模板文件**

```html
<!-- app/reporting/templates/report.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>AegisOTA Run Report - Run {{ run_id }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .header { background: #f0f0f0; padding: 20px; border-radius: 5px; }
        .status-passed { color: green; }
        .status-failed { color: red; }
        .timeline { margin-top: 20px; }
        .step { margin: 10px 0; padding: 10px; border: 1px solid #ddd; }
        .step-success { background: #e8f5e9; }
        .step-failure { background: #ffebee; }
        .recommendations { background: #fff3e0; padding: 15px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Run Report #{{ run_id }}</h1>
        <p><strong>Plan:</strong> {{ plan_name }}</p>
        <p><strong>Device:</strong> {{ device_serial }}</p>
        <p><strong>Status:</strong> <span class="status-{{ status }}">{{ status }}</span></p>
        <p><strong>Duration:</strong> {{ duration_seconds }}s</p>
        {% if failure_category %}
        <p><strong>Failure Category:</strong> {{ failure_category }}</p>
        {% endif %}
    </div>

    <div class="timeline">
        <h2>Execution Timeline</h2>
        {% for event in timeline %}
        <div class="step {% if event.success %}step-success{% else %}step-failure{% endif %}">
            <p><strong>{{ event.timestamp }}</strong> - {{ event.event_type }}</p>
            <p>{{ event.message }}</p>
        </div>
        {% endfor %}
    </div>

    {% if recommendations %}
    <div class="recommendations">
        <h2>Recommendations</h2>
        <p>{{ recommendation_text }}</p>
        <ul>
        {% for action in next_actions %}
            <li>{{ action }}</li>
        {% endfor %}
        </ul>
    </div>
    {% endif %}
</body>
</html>
```

```markdown
<!-- app/reporting/templates/report.md -->
# Run Report #{{ run_id }}

## 基本信息

- **升级计划**: {{ plan_name }}
- **设备序列号**: {{ device_serial }}
- **执行状态**: {{ status }}
- **执行时长**: {{ duration_seconds }}秒
{% if failure_category %}
- **失败分类**: {{ failure_category }}
{% endif %}

## 执行时间线

{% for event in timeline %}
### {{ event.timestamp }} - {{ event.event_type }}

{{ event.message }}

{% endfor %}

{% if recommendations %}
## 失败分析与建议

**分类**: {{ failure_category }}

**建议**: {{ recommendation_text }}

**下一步行动**:
{% for action in next_actions %}
- {{ action }}
{% endfor %}
{% endif %}

## 产物链接

- 执行日志: `artifacts/{{ run_id }}/`
- 时间线: `artifacts/{{ run_id }}/timeline.json`
```

- [ ] **Step 5: 实现报告生成器**

```python
# app/reporting/generator.py
"""报告生成器模块。"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.models.run import RunStatus
from app.reporting.failure_classifier import FailureClassifier, FailureCategory


class ReportGenerator:
    """报告生成器。"""

    def __init__(self, template_dir: Optional[Path] = None):
        settings = get_settings()
        self.template_dir = template_dir or Path(__file__).parent / "templates"
        self.classifier = FailureClassifier()

        # 初始化 Jinja2 环境
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
        )

    def generate(
        self,
        run_id: int,
        plan_name: str,
        device_serial: str,
        status: RunStatus,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
        failed_step: Optional[str] = None,
        failure_category: Optional[FailureCategory] = None,
        timeline: List[Dict[str, Any]] = [],
        step_results: Dict[str, Any] = {},
        artifacts: List[Dict[str, Any]] = [],
    ) -> Dict[str, Any]:
        """生成报告数据结构。"""
        # 计算时长
        duration_seconds = 0
        if started_at and ended_at:
            duration_seconds = int((ended_at - started_at).total_seconds())

        # 状态转换
        status_str = status.value if isinstance(status, RunStatus) else str(status)

        # 失败分析与建议
        recommendations = None
        recommendation_text = None
        next_actions = []

        if status == RunStatus.FAILED and failure_category:
            recommendations = True
            recommendation_text = self.classifier.get_recommendation(failure_category)
            next_actions = self.classifier.get_next_actions(failure_category)

        return {
            "run_id": run_id,
            "plan_name": plan_name,
            "device_serial": device_serial,
            "status": status_str,
            "started_at": started_at.isoformat() if started_at else None,
            "ended_at": ended_at.isoformat() if ended_at else None,
            "duration_seconds": duration_seconds,
            "failed_step": failed_step,
            "failure_category": failure_category.value if failure_category else None,
            "timeline": timeline,
            "step_results": step_results,
            "artifacts": artifacts,
            "recommendations": recommendations,
            "recommendation_text": recommendation_text,
            "next_actions": next_actions,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def generate_summary(
        self,
        run_id: int,
        status: str,
        duration_seconds: int,
        steps_count: int,
    ) -> Dict[str, Any]:
        """生成简要摘要。"""
        return {
            "run_id": run_id,
            "status": status,
            "duration_seconds": duration_seconds,
            "steps_count": steps_count,
            "summary": f"任务 #{run_id} 执行{'成功' if status == 'passed' else '失败'}，耗时 {duration_seconds}秒",
        }

    def generate_markdown(
        self,
        run_id: int,
        plan_name: str,
        device_serial: str,
        status: str,
        timeline: List[Dict[str, Any]],
        **kwargs,
    ) -> str:
        """生成 Markdown 格式报告。"""
        report_data = self.generate(
            run_id=run_id,
            plan_name=plan_name,
            device_serial=device_serial,
            status=RunStatus(status) if status in [s.value for s in RunStatus] else RunStatus.PASSED,
            timeline=timeline,
            **kwargs,
        )

        template = self.env.get_template("report.md")
        return template.render(**report_data)

    def generate_html(
        self,
        run_id: int,
        plan_name: str,
        device_serial: str,
        status: str,
        timeline: List[Dict[str, Any]],
        **kwargs,
    ) -> str:
        """生成 HTML 格式报告。"""
        report_data = self.generate(
            run_id=run_id,
            plan_name=plan_name,
            device_serial=device_serial,
            status=RunStatus(status) if status in [s.value for s in RunStatus] else RunStatus.PASSED,
            timeline=timeline,
            **kwargs,
        )

        template = self.env.get_template("report.html")
        return template.render(**report_data)

    def save_report(
        self,
        report_data: Dict[str, Any],
        output_dir: Path,
        formats: List[str] = ["json", "md", "html"],
    ) -> Dict[str, Path]:
        """保存报告到文件。"""
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_files = {}

        run_id = report_data["run_id"]

        # JSON 格式
        if "json" in formats:
            import json
            json_path = output_dir / f"report_{run_id}.json"
            with open(json_path, "w") as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            saved_files["json"] = json_path

        # Markdown 格式
        if "md" in formats:
            md_content = self.generate_markdown(
                run_id=run_id,
                plan_name=report_data["plan_name"],
                device_serial=report_data["device_serial"],
                status=report_data["status"],
                timeline=report_data["timeline"],
                **report_data,
            )
            md_path = output_dir / f"report_{run_id}.md"
            with open(md_path, "w") as f:
                f.write(md_content)
            saved_files["md"] = md_path

        # HTML 格式
        if "html" in formats:
            html_content = self.generate_html(
                run_id=run_id,
                plan_name=report_data["plan_name"],
                device_serial=report_data["device_serial"],
                status=report_data["status"],
                timeline=report_data["timeline"],
                **report_data,
            )
            html_path = output_dir / f"report_{run_id}.html"
            with open(html_path, "w") as f:
                f.write(html_content)
            saved_files["html"] = html_path

        return saved_files
```

- [ ] **Step 6: 更新 reporting/__init__.py**

```python
# app/reporting/__init__.py
"""报告模块。"""

from app.reporting.failure_classifier import FailureClassifier, FailureCategory
from app.reporting.generator import ReportGenerator

__all__ = [
    "FailureClassifier",
    "FailureCategory",
    "ReportGenerator",
]
```

- [ ] **Step 7: 运行测试**

Run: `pytest tests/test_reporting/test_generator.py -v`
Expected: PASS - 5 tests passed

- [ ] **Step 8: 提交**

```bash
git add app/reporting/generator.py app/reporting/templates/report.html app/reporting/templates/report.md tests/test_reporting/test_generator.py
git commit -m "feat: add report generator with HTML and Markdown templates"
```

---

## Phase 5 完成检查

Run: `pytest tests/test_validators/ tests/test_reporting/ -v --tb=short`
Expected: All tests pass