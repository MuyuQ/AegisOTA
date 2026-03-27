"""开机检测验证器。"""

import time
from dataclasses import dataclass
from typing import Optional

from app.executors.adb_executor import ADBExecutor
from app.config import get_settings


@dataclass
class BootCheckResult:
    """开机检测结果。"""

    passed: bool
    device_serial: str
    boot_completed: bool
    message: str
    wait_time_ms: Optional[int] = None

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "passed": self.passed,
            "device_serial": self.device_serial,
            "boot_completed": self.boot_completed,
            "message": self.message,
            "wait_time_ms": self.wait_time_ms,
        }


class BootChecker:
    """开机检测器。"""

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        timeout: int = 90,
    ):
        self.executor = executor or ADBExecutor()
        self.timeout = timeout or get_settings().BOOT_COMPLETE_TIMEOUT

    def check(self, device_serial: str) -> BootCheckResult:
        """检查设备开机状态。"""
        props = self.executor.getprop(device=device_serial)
        boot_completed = props.get("sys.boot_completed", "0") == "1"

        if boot_completed:
            return BootCheckResult(
                passed=True,
                device_serial=device_serial,
                boot_completed=True,
                message="系统已完成启动",
            )
        else:
            return BootCheckResult(
                passed=False,
                device_serial=device_serial,
                boot_completed=False,
                message="系统未完成启动",
            )

    def wait_for_boot(
        self,
        device_serial: str,
        timeout: Optional[int] = None,
    ) -> BootCheckResult:
        """等待设备开机完成。"""
        wait_timeout = timeout or self.timeout
        start_time = time.time()

        while time.time() - start_time < wait_timeout:
            result = self.check(device_serial)

            if result.boot_completed:
                wait_time_ms = int((time.time() - start_time) * 1000)
                return BootCheckResult(
                    passed=True,
                    device_serial=device_serial,
                    boot_completed=True,
                    message=f"开机完成，等待 {wait_time_ms}ms",
                    wait_time_ms=wait_time_ms,
                )

            time.sleep(2)

        # 超时
        wait_time_ms = int((time.time() - start_time) * 1000)
        return BootCheckResult(
            passed=False,
            device_serial=device_serial,
            boot_completed=False,
            message=f"等待开机超时（{wait_timeout}秒）",
            wait_time_ms=wait_time_ms,
        )