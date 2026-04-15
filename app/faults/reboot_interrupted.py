"""重启中断注入插件。"""

import time
from typing import Any, Dict, Optional

from app.executors.adb_executor import ADBExecutor
from app.executors.run_context import RunContext
from app.faults.base import FaultPlugin, FaultResult


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
        self.interrupt_after_seconds = (
            interrupt_after_seconds or self.DEFAULT_INTERRUPT_AFTER_SECONDS
        )
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
        if self.interrupt_after_seconds > 0:
            time.sleep(self.interrupt_after_seconds)

        # 记录中断事件
        self.record_event(
            context,
            f"模拟中断（类型：{self.interrupt_type}）",
            {"interrupt_after_seconds": self.interrupt_after_seconds},
        )

        # 根据中断类型执行不同操作
        if self.interrupt_type == "disconnect":
            # 使用 runner 直接执行 adb disconnect 命令
            disconnect_cmd = ["adb", "disconnect", context.device_serial]
            disconnect_result = self.executor.runner.run(disconnect_cmd)
            self.record_event(
                context,
                f"ADB 断开连接: {disconnect_result.stdout}",
            )

        elif self.interrupt_type == "timeout":
            # timeout 类型：等待超时，不执行额外操作
            # 只需要等待足够长的时间让系统检测到超时
            self.record_event(
                context,
                "等待超时检测",
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
