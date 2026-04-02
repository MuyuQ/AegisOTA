"""版本确认验证器。"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

from app.executors.adb_executor import ADBExecutor


@dataclass
class VersionCheckResult:
    """版本确认结果。"""

    passed: bool
    device_serial: str
    current_version: str
    message: str
    expected_version: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "passed": self.passed,
            "device_serial": self.device_serial,
            "current_version": self.current_version,
            "expected_version": self.expected_version,
            "message": self.message,
        }


class VersionChecker:
    """版本确认器。"""

    def __init__(self, executor: Optional[ADBExecutor] = None):
        self.executor = executor or ADBExecutor()

    def check(
        self,
        device_serial: str,
        expected: Optional[str] = None,
    ) -> VersionCheckResult:
        """检查设备版本。"""
        props = self.executor.getprop(device=device_serial)
        current_fingerprint = props.get("ro.build.fingerprint", "")

        if expected:
            # 检查是否包含预期版本号
            if expected in current_fingerprint:
                return VersionCheckResult(
                    passed=True,
                    device_serial=device_serial,
                    current_version=current_fingerprint,
                    expected_version=expected,
                    message="版本确认通过",
                )
            else:
                return VersionCheckResult(
                    passed=False,
                    device_serial=device_serial,
                    current_version=current_fingerprint,
                    expected_version=expected,
                    message=f"版本不匹配：期望包含 {expected}，实际为 {current_fingerprint}",
                )

        # 无预期版本，只获取当前版本
        return VersionCheckResult(
            passed=True,
            device_serial=device_serial,
            current_version=current_fingerprint,
            message="版本信息获取成功",
        )

    def get_version_info(self, device_serial: str) -> Dict[str, Any]:
        """获取完整版本信息。"""
        props = self.executor.getprop(device=device_serial)

        return {
            "system_version": props.get("ro.build.version.release", ""),
            "build_fingerprint": props.get("ro.build.fingerprint", ""),
            "build_id": props.get("ro.build.id", ""),
            "build_type": props.get("ro.build.type", ""),
            "security_patch": props.get("ro.build.version.security_patch", ""),
        }