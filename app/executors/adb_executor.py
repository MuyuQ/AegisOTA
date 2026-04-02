"""ADB/Fastboot 命令执行器。"""

import re
from typing import Optional, List, Dict, Any, Union

from app.executors.command_runner import CommandRunner, CommandResult, ShellCommandRunner


class ADBExecutor:
    """ADB/Fastboot 命令执行器。"""

    def __init__(
        self,
        adb_path: str = "adb",
        fastboot_path: str = "fastboot",
        runner: Optional[CommandRunner] = None,
    ):
        self.adb_path = adb_path
        self.fastboot_path = fastboot_path
        self.runner = runner or ShellCommandRunner()

    def _build_adb_command(
        self,
        action: str,
        *args: str,
        device: Optional[str] = None,
    ) -> List[str]:
        """构建 ADB 命令，返回列表形式以避免命令注入风险。"""
        parts = [self.adb_path]
        if device:
            parts.extend(["-s", device])
        parts.append(action)
        parts.extend(args)
        return parts

    def _build_fastboot_command(
        self,
        action: str,
        *args: str,
        device: Optional[str] = None,
    ) -> List[str]:
        """构建 Fastboot 命令，返回列表形式以避免命令注入风险。"""
        parts = [self.fastboot_path]
        if device:
            parts.extend(["-s", device])
        parts.append(action)
        parts.extend(args)
        return parts

    def devices(self) -> List[Dict[str, str]]:
        """获取设备列表。"""
        cmd = [self.adb_path, "devices"]
        result = self.runner.run(cmd)

        if not result.success:
            return []

        devices = []
        for line in result.stdout.strip().split("\n"):
            if line and not line.startswith("List of devices"):
                parts = line.split("\t")
                if len(parts) >= 2:
                    devices.append({
                        "serial": parts[0],
                        "status": parts[1],
                    })

        return devices

    def shell(
        self,
        command: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """执行 shell 命令。"""
        cmd = self._build_adb_command("shell", command, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def push(
        self,
        local_path: str,
        remote_path: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """推送文件到设备。"""
        cmd = self._build_adb_command("push", local_path, remote_path, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def pull(
        self,
        remote_path: str,
        local_path: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """从设备拉取文件。"""
        cmd = self._build_adb_command("pull", remote_path, local_path, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def reboot(
        self,
        mode: Optional[str] = None,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """重启设备。"""
        if mode:
            cmd = self._build_adb_command("reboot", mode, device=device)
        else:
            cmd = self._build_adb_command("reboot", device=device)
        return self.runner.run(cmd, timeout=timeout)

    def getprop(
        self,
        prop: Optional[str] = None,
        device: Optional[str] = None,
    ) -> Dict[str, str]:
        """获取设备属性。"""
        if prop:
            result = self.shell(f"getprop {prop}", device=device)
            if result.success:
                return {prop: result.stdout.strip()}
            return {}

        result = self.shell("getprop", device=device, timeout=30)
        if not result.success:
            return {}

        props = {}
        for line in result.stdout.strip().split("\n"):
            match = re.match(r"\[([^\]]+)\]: \[([^\]]+)\]", line)
            if match:
                props[match.group(1)] = match.group(2)

        return props

    def wait_for_device(
        self,
        device: Optional[str] = None,
        timeout: int = 60,
        state: str = "device",
    ) -> CommandResult:
        """等待设备就绪。"""
        cmd = self._build_adb_command("wait-for-device", device=device)
        return self.runner.run(cmd, timeout=timeout)

    def install(
        self,
        package_path: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """安装 APK。"""
        cmd = self._build_adb_command("install", "-r", package_path, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def logcat(
        self,
        device: Optional[str] = None,
        output_path: Optional[str] = None,
        timeout: Optional[int] = None,
        clear: bool = False,
    ) -> CommandResult:
        """获取 logcat 日志。"""
        if clear:
            self.shell("logcat -c", device=device)

        cmd = self._build_adb_command("logcat", "-d", device=device)
        result = self.runner.run(cmd, timeout=timeout)

        if output_path and result.success:
            with open(output_path, "w") as f:
                f.write(result.stdout)

        return result

    def fastboot_reboot(
        self,
        device: Optional[str] = None,
    ) -> CommandResult:
        """Fastboot 模式重启。"""
        cmd = self._build_fastboot_command("reboot", device=device)
        return self.runner.run(cmd)

    def fastboot_flash(
        self,
        partition: str,
        image_path: str,
        device: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """Fastboot 刷写分区。"""
        cmd = self._build_fastboot_command("flash", partition, image_path, device=device)
        return self.runner.run(cmd, timeout=timeout)

    def get_device_snapshot(
        self,
        device: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取设备完整快照。"""
        props = self.getprop(device=device)

        # 获取电量
        battery_result = self.shell(
            "dumpsys battery | grep level",
            device=device
        )
        battery_level = None
        if battery_result.success:
            match = re.search(r"level: (\d+)", battery_result.stdout)
            if match:
                battery_level = int(match.group(1))

        # 获取存储信息
        storage_result = self.shell(
            "df /data | tail -1",
            device=device
        )

        return {
            "serial": device,
            "brand": props.get("ro.product.brand", ""),
            "model": props.get("ro.product.model", ""),
            "system_version": props.get("ro.build.version.release", ""),
            "build_fingerprint": props.get("ro.build.fingerprint", ""),
            "battery_level": battery_level,
            "boot_completed": props.get("sys.boot_completed", "0") == "1",
            "storage": storage_result.stdout.strip() if storage_result.success else "",
        }