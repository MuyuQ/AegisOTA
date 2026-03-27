"""任务执行阶段 Handler。"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import get_settings
from app.executors.command_runner import CommandResult
from app.executors.adb_executor import ADBExecutor
from app.executors.run_context import RunContext, DeviceSnapshot
from app.models.run import StepName


@dataclass
class StepHandlerResult:
    """阶段执行结果。"""

    success: bool
    step_name: StepName
    message: str
    data: Dict[str, Any]
    duration_ms: int
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "success": self.success,
            "step_name": self.step_name.value,
            "message": self.message,
            "data": self.data,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class StepHandler(ABC):
    """阶段执行 Handler 抽象基类。"""

    step_name: StepName = None
    timeout: int = 300

    def __init__(
        self,
        executor: Optional[ADBExecutor] = None,
        timeout: Optional[int] = None,
    ):
        self.settings = get_settings()
        self.timeout = timeout or self.settings.DEFAULT_TIMEOUT
        self.executor = executor or ADBExecutor()

    @abstractmethod
    def execute(self, context: RunContext) -> StepHandlerResult:
        """执行阶段逻辑。"""
        pass

    def _save_artifact(
        self,
        context: RunContext,
        name: str,
        content: str,
    ) -> Path:
        """保存产物文件。"""
        artifact_path = context.artifact_dir / name
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        with open(artifact_path, "w") as f:
            f.write(content)

        return artifact_path

    def _record_command(
        self,
        context: RunContext,
        command: str,
        result: CommandResult,
    ) -> None:
        """记录命令执行结果。"""
        context.record_event(
            "command",
            command,
            {
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
            }
        )


class PrecheckHandler(StepHandler):
    """升级前检查 Handler。"""

    step_name = StepName.PRECHECK

    def execute(self, context: RunContext) -> StepHandlerResult:
        """执行升级前检查。"""
        start_time = time.time()

        context.record_event("step_start", "precheck")
        context.current_step = "precheck"

        # 检查设备在线
        devices = self.executor.devices()
        device_online = any(
            d["serial"] == context.device_serial
            for d in devices
        )

        if not device_online:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="设备离线",
                data={"device_online": False},
                duration_ms=int((time.time() - start_time) * 1000),
                error="Device not found in adb devices",
            )

        # 获取设备属性
        props = self.executor.getprop(device=context.device_serial)

        # 检查电量
        battery_level = None
        battery_result = self.executor.shell(
            "dumpsys battery | grep level",
            device=context.device_serial,
        )
        if battery_result.success:
            import re
            match = re.search(r"level: (\d+)", battery_result.stdout)
            if match:
                battery_level = int(match.group(1))

        if battery_level and battery_level < 20:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="电量不足",
                data={"battery_level": battery_level},
                duration_ms=int((time.time() - start_time) * 1000),
                error=f"Battery level too low: {battery_level}%",
            )

        # 更新上下文
        context.device = DeviceSnapshot(
            serial=context.device_serial,
            brand=props.get("ro.product.brand"),
            model=props.get("ro.product.model"),
            android_version=props.get("ro.build.version.release"),
            battery_level=battery_level,
            build_fingerprint=props.get("ro.build.fingerprint"),
            boot_completed=props.get("sys.boot_completed") == "1",
        )

        # 保存设备信息
        self._save_artifact(
            context,
            "precheck_device_info.json",
            str(props),
        )

        context.record_event("step_end", "precheck", {"success": True})

        return StepHandlerResult(
            success=True,
            step_name=self.step_name,
            message="升级前检查通过",
            data={
                "device_online": True,
                "battery_level": battery_level,
                "android_version": props.get("ro.build.version.release"),
            },
            duration_ms=int((time.time() - start_time) * 1000),
        )


class PushPackageHandler(StepHandler):
    """推送升级包 Handler。"""

    step_name = StepName.PACKAGE_PREPARE

    def execute(self, context: RunContext) -> StepHandlerResult:
        """推送升级包到设备。"""
        start_time = time.time()

        context.record_event("step_start", "push_package")

        if not context.package_path:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="未指定升级包路径",
                data={},
                duration_ms=int((time.time() - start_time) * 1000),
                error="No package_path in context",
            )

        # 推送升级包
        remote_path = "/data/local/tmp/update.zip"
        result = self.executor.push(
            context.package_path,
            remote_path,
            device=context.device_serial,
            timeout=self.timeout,
        )

        self._record_command(context, f"push {context.package_path}", result)

        if not result.success:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="推送升级包失败",
                data={"stderr": result.stderr},
                duration_ms=int((time.time() - start_time) * 1000),
                error=result.stderr,
            )

        # 保存命令输出
        self._save_artifact(context, "push_stdout.txt", result.stdout)

        context.record_event("step_end", "push_package", {"success": True})

        return StepHandlerResult(
            success=True,
            step_name=self.step_name,
            message="升级包推送成功",
            data={
                "push_time": result.duration_ms,
                "remote_path": remote_path,
            },
            duration_ms=int((time.time() - start_time) * 1000),
        )


class ApplyUpdateHandler(StepHandler):
    """应用升级 Handler。"""

    step_name = StepName.APPLY_UPDATE
    timeout = 180

    def execute(self, context: RunContext) -> StepHandlerResult:
        """执行升级命令。"""
        start_time = time.time()

        context.record_event("step_start", "apply_update")

        # 执行升级命令（使用系统升级机制）
        # 实际命令取决于设备和升级类型
        upgrade_command = self._build_upgrade_command(context)
        result = self.executor.shell(
            upgrade_command,
            device=context.device_serial,
            timeout=self.timeout,
        )

        self._record_command(context, upgrade_command, result)
        self._save_artifact(context, "apply_update_stdout.txt", result.stdout)

        if not result.success:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="升级命令执行失败",
                data={"stderr": result.stderr},
                duration_ms=int((time.time() - start_time) * 1000),
                error=result.stderr,
            )

        context.record_event("step_end", "apply_update", {"success": True})

        return StepHandlerResult(
            success=True,
            step_name=self.step_name,
            message="升级命令执行成功",
            data={"upgrade_command": upgrade_command},
            duration_ms=int((time.time() - start_time) * 1000),
        )

    def _build_upgrade_command(self, context: RunContext) -> str:
        """构建升级命令。"""
        # 模拟升级命令（实际实现需要根据设备类型调整）
        if context.upgrade_type == "full":
            return "am broadcast -a android.intent.action.UPDATE_SYSTEM"
        elif context.upgrade_type == "incremental":
            return "am broadcast -a android.intent.action.APPLY_PATCH"
        else:
            return "echo 'Upgrade command placeholder'"


class RebootWaitHandler(StepHandler):
    """重启等待 Handler。"""

    step_name = StepName.REBOOT_WAIT
    timeout = 120

    def execute(self, context: RunContext) -> StepHandlerResult:
        """重启设备并等待启动完成。"""
        start_time = time.time()

        context.record_event("step_start", "reboot_wait")

        # 发送重启命令
        reboot_result = self.executor.reboot(device=context.device_serial)
        self._record_command(context, "reboot", reboot_result)

        # 等待设备重启完成
        boot_timeout = self.timeout
        wait_start = time.time()

        # 等待设备离线
        time.sleep(5)

        # 等待设备重新上线
        while time.time() - wait_start < boot_timeout:
            props = self.executor.getprop(device=context.device_serial)

            if props.get("sys.boot_completed") == "1":
                break

            time.sleep(2)

        # 检查是否启动完成
        final_props = self.executor.getprop(device=context.device_serial)
        boot_completed = final_props.get("sys.boot_completed") == "1"

        if not boot_completed:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="重启等待超时",
                data={"timeout": boot_timeout},
                duration_ms=int((time.time() - start_time) * 1000),
                error=f"Device did not boot within {boot_timeout} seconds",
            )

        context.record_event("step_end", "reboot_wait", {"success": True})

        return StepHandlerResult(
            success=True,
            step_name=self.step_name,
            message="设备重启完成",
            data={
                "boot_time": int((time.time() - wait_start) * 1000),
                "boot_completed": True,
            },
            duration_ms=int((time.time() - start_time) * 1000),
        )


class PostValidateHandler(StepHandler):
    """升级后验证 Handler。"""

    step_name = StepName.POST_VALIDATE

    def execute(self, context: RunContext) -> StepHandlerResult:
        """执行升级后验证。"""
        start_time = time.time()

        context.record_event("step_start", "post_validate")

        # 检查版本
        props = self.executor.getprop(device=context.device_serial)
        current_version = props.get("ro.build.fingerprint")

        # 检查开机完成
        boot_completed = props.get("sys.boot_completed") == "1"

        if not boot_completed:
            return StepHandlerResult(
                success=False,
                step_name=self.step_name,
                message="系统未完成启动",
                data={"boot_completed": False},
                duration_ms=int((time.time() - start_time) * 1000),
                error="sys.boot_completed != 1",
            )

        # 保存验证结果
        validation_data = {
            "current_version": current_version,
            "boot_completed": boot_completed,
            "validation_time": datetime.utcnow().isoformat(),
        }

        self._save_artifact(
            context,
            "post_validate_result.json",
            str(validation_data),
        )

        context.record_event("step_end", "post_validate", {"success": True})

        return StepHandlerResult(
            success=True,
            step_name=self.step_name,
            message="升级后验证通过",
            data=validation_data,
            duration_ms=int((time.time() - start_time) * 1000),
        )