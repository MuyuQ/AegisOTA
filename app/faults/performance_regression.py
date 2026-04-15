"""性能退化注入插件。"""

from typing import Any, Dict, Optional

from app.executors.adb_executor import ADBExecutor
from app.executors.run_context import RunContext
from app.faults.base import FaultPlugin, FaultResult


class PerformanceRegressionFault(FaultPlugin):
    """性能退化注入插件。

    通过 CPU/内存压力模拟升级后性能问题。
    """

    fault_type = "performance_regression"
    fault_stage = "post_validate"
    description = "模拟性能退化场景"

    DEFAULT_PRESSURE_TYPE = "cpu"  # cpu, memory, io
    DEFAULT_DURATION_SECONDS = 60

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        pressure_type: Optional[str] = None,
        duration_seconds: Optional[int] = None,
    ):
        super().__init__(executor)
        self.pressure_type = pressure_type or self.DEFAULT_PRESSURE_TYPE
        self.duration_seconds = duration_seconds or self.DEFAULT_DURATION_SECONDS

    def set_parameters(self, params: Dict[str, Any]):
        """设置参数。"""
        super().set_parameters(params)
        if "pressure_type" in params:
            self.pressure_type = params["pressure_type"]
        if "duration_seconds" in params:
            self.duration_seconds = params["duration_seconds"]

    def validate_parameters(self) -> bool:
        """验证参数。"""
        if self.pressure_type not in ["cpu", "memory", "io"]:
            return False
        if self.duration_seconds < 0:
            return False
        return True

    def prepare(self, context: RunContext) -> FaultResult:
        """准备阶段：获取当前性能指标。"""
        self.record_event(context, "检查当前性能状态")

        metrics = {}

        # CPU 使用率
        cpu_result = self.executor.shell(
            "top -n 1 | grep 'CPU'",
            device=context.device_serial,
        )
        if cpu_result.success:
            metrics["cpu_info"] = cpu_result.stdout.strip()

        # 内存使用
        mem_result = self.executor.shell(
            "cat /proc/meminfo | grep -E 'MemTotal|MemAvailable'",
            device=context.device_serial,
        )
        if mem_result.success:
            metrics["mem_info"] = mem_result.stdout.strip()

        self.record_event(
            context,
            "性能基线获取完成",
            metrics,
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="性能基线检查完成",
            data=metrics,
        )

    def inject(self, context: RunContext) -> FaultResult:
        """注入阶段：施加性能压力。"""
        self.record_event(
            context,
            f"注入性能压力（{self.pressure_type}，持续 {self.duration_seconds}s）",
        )

        if self.pressure_type == "cpu":
            # CPU 压力：启动多个计算进程
            self.executor.shell(
                f"""
                for i in 1 2 3 4; do
                    (while true; do echo $i > /dev/null; done) &
                done
                sleep {self.duration_seconds}
                pkill -f 'echo.*>/dev/null'
                """,
                device=context.device_serial,
                timeout=self.duration_seconds + 30,
            )

        elif self.pressure_type == "memory":
            # 内存压力：创建大文件占用内存（通过 ashmem 或 tmpfs）
            self.executor.shell(
                f"""
                dd if=/dev/zero of=/dev/ashmem/dummy bs=1M count=100 2>/dev/null || \
                dd if=/dev/zero of=/data/local/tmp/stress_mem bs=1M count=100
                sleep {self.duration_seconds}
                rm -f /data/local/tmp/stress_mem
                """,
                device=context.device_serial,
                timeout=self.duration_seconds + 30,
            )

        elif self.pressure_type == "io":
            # IO 压力：持续读写
            self.executor.shell(
                f"""
                while true; do
                    dd if=/dev/zero of=/data/local/tmp/io_stress bs=1M count=10
                    rm -f /data/local/tmp/io_stress
                done &
                IO_PID=$!
                sleep {self.duration_seconds}
                kill $IO_PID 2>/dev/null
                """,
                device=context.device_serial,
                timeout=self.duration_seconds + 30,
            )

        else:
            return FaultResult(
                success=False,
                fault_type=self.fault_type,
                message="未知压力类型",
                data={},
                error=f"Invalid pressure_type: {self.pressure_type}",
            )

        self.record_event(
            context,
            f"性能压力注入完成（{self.pressure_type}）",
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message=f"性能压力注入完成（{self.pressure_type}，持续 {self.duration_seconds}s）",
            data={
                "pressure_type": self.pressure_type,
                "duration_seconds": self.duration_seconds,
            },
        )

    def cleanup(self, context: RunContext) -> FaultResult:
        """清理阶段：停止所有压力进程。"""
        self.record_event(context, "性能压力注入清理")

        # 清理可能残留的压力进程和文件
        self.executor.shell(
            (
                "pkill -f 'echo.*>/dev/null' 2>/dev/null; "
                "rm -f /data/local/tmp/io_stress "
                "/data/local/tmp/stress_mem 2>/dev/null"
            ),
            device=context.device_serial,
        )

        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="性能压力清理完成",
            data={},
        )
