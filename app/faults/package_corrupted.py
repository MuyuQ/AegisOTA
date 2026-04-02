"""升级包损坏注入插件。"""

from typing import Dict, Any, Optional

from app.faults.base import FaultPlugin, FaultResult
from app.executors.run_context import RunContext
from app.executors.adb_executor import ADBExecutor


class PackageCorruptedFault(FaultPlugin):
    """升级包损坏注入插件。

    在推送后损坏升级包，模拟包校验失败场景。
    """

    fault_type = "package_corrupted"
    fault_stage = "precheck"
    description = "模拟升级包损坏场景"

    DEFAULT_CORRUPTION_TYPE = "header"  # header, truncate, append

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        corruption_type: Optional[str] = None,
    ):
        super().__init__(executor)
        self.corruption_type = corruption_type or self.DEFAULT_CORRUPTION_TYPE

    def set_parameters(self, params: Dict[str, Any]):
        """设置参数。"""
        super().set_parameters(params)
        if "corruption_type" in params:
            self.corruption_type = params["corruption_type"]

    def validate_parameters(self) -> bool:
        """验证参数。"""
        return self.corruption_type in ["header", "truncate", "append"]

    def prepare(self, context: RunContext) -> FaultResult:
        """准备阶段。"""
        self.record_event(
            context,
            f"准备包损坏注入（类型：{self.corruption_type}）",
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="包损坏准备完成",
            data={"corruption_type": self.corruption_type},
        )

    def inject(self, context: RunContext) -> FaultResult:
        """注入阶段：损坏升级包。"""
        self.record_event(context, f"损坏升级包（{self.corruption_type}）")

        remote_path = "/data/local/tmp/update.zip"

        if self.corruption_type == "header":
            # 损坏 ZIP 头部（ZIP 签名是 PK\x03\x04）
            result = self.executor.shell(
                f"dd if=/dev/zero of={remote_path} bs=1 count=4 conv=notrunc",
                device=context.device_serial,
            )

        elif self.corruption_type == "truncate":
            # 截断文件到 1KB
            result = self.executor.shell(
                f"truncate -s 1024 {remote_path}",
                device=context.device_serial,
            )

        elif self.corruption_type == "append":
            # 追加垃圾数据
            result = self.executor.shell(
                f"echo 'CORRUPTED_DATA appended by fault injection' >> {remote_path}",
                device=context.device_serial,
            )

        else:
            return FaultResult(
                success=False,
                fault_type=self.fault_type,
                message="未知损坏类型",
                data={},
                error=f"Invalid corruption_type: {self.corruption_type}",
            )

        if not result.success:
            return FaultResult(
                success=False,
                fault_type=self.fault_type,
                message="包损坏操作失败",
                data={},
                error=result.stderr,
            )

        self.record_event(
            context,
            f"包损坏完成（{self.corruption_type}）",
            {"remote_path": remote_path},
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message=f"包损坏注入成功（{self.corruption_type}）",
            data={
                "corruption_type": self.corruption_type,
                "remote_path": remote_path,
            },
        )

    def cleanup(self, context: RunContext) -> FaultResult:
        """清理阶段：删除损坏的包。"""
        self.record_event(context, "包损坏注入清理")

        remote_path = "/data/local/tmp/update.zip"

        # 删除损坏的包
        rm_result = self.executor.shell(
            f"rm -f {remote_path}",
            device=context.device_serial,
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="包损坏清理完成",
            data={"removed_path": remote_path},
        )