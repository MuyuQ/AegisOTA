"""Monkey 稳定性测试插件。"""

import re
from typing import Any, Dict, Optional

from app.config import get_settings
from app.executors.adb_executor import ADBExecutor
from app.executors.run_context import RunContext
from app.faults.base import FaultPlugin, FaultResult


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
            "Monkey 测试完成",
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
