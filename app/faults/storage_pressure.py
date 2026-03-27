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