"""设备管理业务逻辑。"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.device import Device, DeviceLease, DeviceStatus
from app.executors.adb_executor import ADBExecutor
from app.executors.command_runner import CommandRunner


class DeviceService:
    """设备管理服务。"""

    def __init__(
        self,
        db: Session,
        runner: Optional[CommandRunner] = None,
    ):
        self.db = db
        settings = get_settings()
        self.runner = runner
        self.executor = ADBExecutor(runner=self.runner)

    def sync_devices(self) -> List[Device]:
        """扫描并同步在线设备。"""
        # 获取当前在线设备
        online_devices = self.executor.devices()
        online_serials = {d["serial"] for d in online_devices}

        # 获取数据库中的设备
        db_devices = self.db.query(Device).all()
        db_serials = {d.serial for d in db_devices}

        # 新设备入库
        for device_info in online_devices:
            serial = device_info["serial"]
            if serial not in db_serials:
                device = self._create_device_from_adb(serial)
                self.db.add(device)

        # 离线设备更新状态
        for device in db_devices:
            if device.serial not in online_serials:
                if device.status != DeviceStatus.QUARANTINED:
                    device.status = DeviceStatus.OFFLINE
            else:
                # 更新在线设备的属性
                self._update_device_info(device)
                if device.status == DeviceStatus.OFFLINE:
                    device.status = DeviceStatus.IDLE

        self.db.commit()
        return self.db.query(Device).all()

    def _create_device_from_adb(self, serial: str) -> Device:
        """从 ADB 信息创建设备实体。"""
        snapshot = self.executor.get_device_snapshot(device=serial)

        device = Device(
            serial=serial,
            brand=snapshot.get("brand"),
            model=snapshot.get("model"),
            android_version=snapshot.get("android_version"),
            build_fingerprint=snapshot.get("build_fingerprint"),
            battery_level=snapshot.get("battery_level"),
            status=DeviceStatus.IDLE,
            last_seen_at=datetime.utcnow(),
        )

        return device

    def _update_device_info(self, device: Device):
        """更新设备信息。"""
        snapshot = self.executor.get_device_snapshot(device=device.serial)

        device.brand = snapshot.get("brand")
        device.model = snapshot.get("model")
        device.android_version = snapshot.get("android_version")
        device.build_fingerprint = snapshot.get("build_fingerprint")
        device.battery_level = snapshot.get("battery_level")
        device.last_seen_at = datetime.utcnow()

        # 计算健康分数
        health_score = 100.0
        if device.battery_level and device.battery_level < 20:
            health_score -= 30
        if snapshot.get("boot_completed") is False:
            health_score -= 50
        device.health_score = health_score

    def get_device_by_serial(self, serial: str) -> Optional[Device]:
        """通过序列号获取设备。"""
        return self.db.query(Device).filter_by(serial=serial).first()

    def get_device_by_id(self, device_id: int) -> Optional[Device]:
        """通过 ID 获取设备。"""
        return self.db.query(Device).filter_by(id=device_id).first()

    def get_available_devices(
        self,
        tags: Optional[List[str]] = None,
        min_battery: int = 20,
        min_health: float = 50.0,
    ) -> List[Device]:
        """获取可用设备列表。"""
        query = self.db.query(Device).filter(
            Device.status == DeviceStatus.IDLE,
        )

        devices = query.all()

        # 过滤健康分数（None 值视为 100）
        filtered = []
        for device in devices:
            health = device.health_score if device.health_score is not None else 100.0
            if health >= min_health:
                if min_battery and device.battery_level is not None:
                    if device.battery_level >= min_battery:
                        filtered.append(device)
                elif min_battery and device.battery_level is None:
                    # 没有 battery_level 数据时跳过该设备
                    continue
                else:
                    filtered.append(device)
        devices = filtered

        # 标签过滤
        if tags:
            filtered = []
            for device in devices:
                device_tags = device.get_tags()
                if any(tag in device_tags for tag in tags):
                    filtered.append(device)
            devices = filtered

        return devices

    def quarantine_device(
        self,
        serial: str,
        reason: str,
        run_id: Optional[int] = None,
    ) -> Optional[Device]:
        """隔离异常设备。"""
        device = self.get_device_by_serial(serial)
        if not device:
            return None

        device.status = DeviceStatus.QUARANTINED
        device.quarantine_reason = reason

        # 释放租约
        if device.current_run_id:
            lease = self.db.query(DeviceLease).filter_by(
                device_id=device.id,
                run_id=device.current_run_id,
                lease_status="active"
            ).first()
            if lease:
                lease.lease_status = "released"
                lease.released_at = datetime.utcnow()

        device.current_run_id = run_id or device.current_run_id

        self.db.commit()
        return device

    def recover_device(self, serial: str) -> Optional[Device]:
        """恢复隔离设备。"""
        device = self.get_device_by_serial(serial)
        if not device:
            return None

        device.status = DeviceStatus.RECOVERING
        self.db.commit()

        # 执行健康检查
        self._update_device_info(device)

        # 检查是否恢复成功
        if device.health_score >= 50:
            device.status = DeviceStatus.IDLE
        else:
            device.status = DeviceStatus.QUARANTINED
            device.quarantine_reason = "Recovery failed: health check failed"

        device.quarantine_reason = None
        device.current_run_id = None

        self.db.commit()
        return device

    def update_device_tags(
        self,
        serial: str,
        tags: List[str],
    ) -> Optional[Device]:
        """更新设备标签。"""
        device = self.get_device_by_serial(serial)
        if not device:
            return None

        device.set_tags(tags)
        self.db.commit()
        return device

    def list_devices(
        self,
        status: Optional[DeviceStatus] = None,
    ) -> List[Device]:
        """列出设备。"""
        query = self.db.query(Device)

        if status:
            query = query.filter(Device.status == status)

        return query.order_by(Device.last_seen_at.desc()).all()