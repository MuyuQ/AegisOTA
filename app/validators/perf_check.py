"""性能检查验证器。"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.executors.adb_executor import ADBExecutor


@dataclass
class PerfCheckResult:
    """性能检查结果。"""

    passed: bool
    memory_usage_percent: float
    cpu_usage_percent: float
    boot_time_ms: int
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

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
    DEFAULT_CPU_THRESHOLD = 50.0  # CPU 使用率上限
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
            memory_usage < self.memory_threshold
            and cpu_usage < self.cpu_threshold
            and boot_time < self.boot_time_threshold
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
        metrics: Dict[str, Any] = {}

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
        mem_info: Dict[str, int] = {}

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
        cpu_info: Dict[str, Any] = {}

        # 尝试解析 CPU 使用率
        match = re.search(r"CPU usage:\s+(\d+\.?\d*)%", output)
        if match:
            cpu_info["usage_percent"] = float(match.group(1))

        return cpu_info
