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