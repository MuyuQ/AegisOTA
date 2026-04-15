"""启动后 Watchdog 故障注入插件。"""

import time
from typing import Any, Dict, Optional

from app.executors.adb_executor import ADBExecutor
from app.executors.run_context import RunContext
from app.faults.base import FaultPlugin, FaultResult


class PostBootWatchdogFailureFault(FaultPlugin):
    """启动后 Watchdog 故障注入插件。

    模拟系统启动后的关键进程崩溃或 Watchdog 触发场景。
    """

    fault_type = "post_boot_watchdog_failure"
    fault_stage = "post_validate"
    description = "模拟启动后 Watchdog 故障"

    DEFAULT_FAILURE_TYPE = "system_server_crash"  # system_server_crash, boot_loop, anr
    DEFAULT_DELAY_SECONDS = 30

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        failure_type: Optional[str] = None,
        delay_seconds: Optional[int] = None,
    ):
        super().__init__(executor)
        self.failure_type = failure_type or self.DEFAULT_FAILURE_TYPE
        self.delay_seconds = delay_seconds or self.DEFAULT_DELAY_SECONDS

    def set_parameters(self, params: Dict[str, Any]):
        """设置参数。"""
        super().set_parameters(params)
        if "failure_type" in params:
            self.failure_type = params["failure_type"]
        if "delay_seconds" in params:
            self.delay_seconds = params["delay_seconds"]

    def validate_parameters(self) -> bool:
        """验证参数。"""
        if self.failure_type not in ["system_server_crash", "boot_loop", "anr"]:
            return False
        if self.delay_seconds < 0:
            return False
        return True

    def prepare(self, context: RunContext) -> FaultResult:
        """准备阶段。"""
        self.record_event(
            context,
            f"准备 Watchdog 故障注入（类型：{self.failure_type}）",
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="Watchdog 故障准备完成",
            data={
                "failure_type": self.failure_type,
                "delay_seconds": self.delay_seconds,
            },
        )

    def inject(self, context: RunContext) -> FaultResult:
        """注入阶段：等待后触发故障。"""
        self.record_event(
            context,
            f"等待 {self.delay_seconds} 秒后注入故障",
        )

        # 等待指定时间让系统完全启动
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)

        if self.failure_type == "system_server_crash":
            # 强制停止 system_server 触发 Watchdog
            self.executor.shell(
                "pkill -9 system_server",
                device=context.device_serial,
            )
            # system_server 崩溃会导致系统重启
            message = "system_server 崩溃注入成功，系统将重启"

        elif self.failure_type == "boot_loop":
            # 通过破坏 boot_complete 标志模拟启动循环
            # 这会阻止系统认为启动完成
            self.executor.shell(
                "setprop sys.boot_completed 0",
                device=context.device_serial,
            )
            message = "启动循环注入成功，boot_completed 标志已清除"

        elif self.failure_type == "anr":
            # 发送 SIGSTOP 到 system_server 触发 ANR
            self.executor.shell(
                "pkill -STOP system_server",
                device=context.device_serial,
            )
            message = "ANR 注入成功，system_server 已暂停"

            # 等待一段时间让 ANR 被检测到
            time.sleep(10)

            # 恢复进程（否则会一直卡住）
            self.executor.shell(
                "pkill -CONT system_server",
                device=context.device_serial,
            )

        else:
            return FaultResult(
                success=False,
                fault_type=self.fault_type,
                message="未知故障类型",
                data={},
                error=f"Invalid failure_type: {self.failure_type}",
            )

        self.record_event(
            context,
            f"Watchdog 故障注入完成（{self.failure_type}）",
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message=message,
            data={
                "failure_type": self.failure_type,
                "delay_seconds": self.delay_seconds,
            },
        )

    def cleanup(self, context: RunContext) -> FaultResult:
        """清理阶段。"""
        self.record_event(context, "Watchdog 故障注入清理")

        # 对于 boot_loop 类型，恢复 boot_completed 标志
        if self.failure_type == "boot_loop":
            self.executor.shell(
                "setprop sys.boot_completed 1",
                device=context.device_serial,
            )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="Watchdog 故障清理完成",
            data={},
        )
