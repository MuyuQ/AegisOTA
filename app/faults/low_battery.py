"""低电量注入插件。"""

from typing import Dict, Any, Optional

from app.faults.base import FaultPlugin, FaultResult
from app.executors.run_context import RunContext
from app.executors.adb_executor import ADBExecutor


class LowBatteryFault(FaultPlugin):
    """低电量注入插件。

    通过 ADB dumpsys battery 命令模拟低电量场景。
    """

    fault_type = "low_battery"
    fault_stage = "precheck"
    description = "模拟低电量场景"

    DEFAULT_BATTERY_LEVEL = 5
    DEFAULT_RESTORE_LEVEL = 100

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        battery_level: Optional[int] = None,
    ):
        super().__init__(executor)
        self.battery_level = battery_level or self.DEFAULT_BATTERY_LEVEL
        self._original_level = None

    def set_parameters(self, params: Dict[str, Any]):
        """设置参数。"""
        super().set_parameters(params)
        if "battery_level" in params:
            self.battery_level = params["battery_level"]

    def validate_parameters(self) -> bool:
        """验证参数。"""
        return 0 <= self.battery_level <= 100

    def prepare(self, context: RunContext) -> FaultResult:
        """准备阶段：获取当前电量。"""
        self.record_event(context, "检查当前电量状态")

        # 获取当前电量
        result = self.executor.shell(
            "dumpsys battery | grep level",
            device=context.device_serial,
        )

        import re
        match = re.search(r"level: (\d+)", result.stdout)
        if match:
            self._original_level = int(match.group(1))
            self.record_event(
                context,
                f"当前电量：{self._original_level}%",
            )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="电量状态检查完成",
            data={"original_level": self._original_level},
        )

    def inject(self, context: RunContext) -> FaultResult:
        """注入阶段：设置低电量。"""
        self.record_event(
            context,
            f"注入低电量（{self.battery_level}%）",
        )

        # 使用 dumpsys battery set level 模拟低电量
        # 注意：需要先 unplug 才能生效
        result = self.executor.shell(
            f"dumpsys battery unplug && dumpsys battery set level {self.battery_level}",
            device=context.device_serial,
        )

        if not result.success:
            return FaultResult(
                success=False,
                fault_type=self.fault_type,
                message="低电量注入失败",
                data={},
                error=result.stderr,
            )

        self.record_event(
            context,
            f"低电量注入成功（{self.battery_level}%）",
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message=f"低电量注入成功，当前 {self.battery_level}%",
            data={
                "battery_level": self.battery_level,
                "original_level": self._original_level,
            },
        )

    def cleanup(self, context: RunContext) -> FaultResult:
        """清理阶段：恢复电量状态。"""
        self.record_event(context, "恢复电量状态")

        # 恢复原始电量状态
        restore_level = self._original_level or self.DEFAULT_RESTORE_LEVEL

        result = self.executor.shell(
            f"dumpsys battery reset && dumpsys battery set level {restore_level} && dumpsys battery plug",
            device=context.device_serial,
        )

        # 清除保存的原始值
        self._original_level = None

        if not result.success:
            return FaultResult(
                success=False,
                fault_type=self.fault_type,
                message="电量恢复失败",
                data={},
                error=result.stderr,
            )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message=f"电量已恢复至 {restore_level}%",
            data={"restored_level": restore_level},
        )