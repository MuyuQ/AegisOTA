"""Monkey 稳定性测试执行器。"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

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
        self.event_count = event_count or settings.MONKEY_DEFAULT_COUNT
        self.default_throttle = throttle or settings.MONKEY_THROTTLE
        self.throttle = throttle or settings.MONKEY_THROTTLE
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
        stats: Dict[str, Any] = {
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
