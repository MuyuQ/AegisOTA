"""调度与并发控制服务。"""

from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.config import get_settings
from app.models.device import Device, DeviceLease, DeviceStatus
from app.models.run import RunSession, RunStatus, UpgradePlan
from app.services.device_service import DeviceService


class SchedulerService:
    """调度服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.device_service = DeviceService(db)

    def acquire_device_lease(
        self,
        device_id: int,
        run_id: int,
        duration: Optional[int] = None,
    ) -> Optional[DeviceLease]:
        """获取设备租约。"""
        device = self.db.query(Device).filter_by(id=device_id).first()

        if not device:
            return None

        # 检查设备状态
        if device.status != DeviceStatus.IDLE:
            return None

        # 检查是否有活跃租约
        active_lease = self.db.query(DeviceLease).filter(
            DeviceLease.device_id == device_id,
            DeviceLease.lease_status == "active"
        ).first()

        if active_lease:
            return None

        # 创建租约
        lease_duration = duration or self.settings.LEASE_DEFAULT_DURATION
        lease = DeviceLease(
            device_id=device_id,
            run_id=run_id,
            lease_status="active",
            expired_at=datetime.utcnow() + timedelta(seconds=lease_duration),
        )

        # 更新设备状态
        device.status = DeviceStatus.BUSY
        device.current_run_id = run_id

        self.db.add(lease)
        self.db.commit()

        return lease

    def release_device_lease(
        self,
        device_id: int,
        run_id: int,
    ) -> bool:
        """释放设备租约。"""
        lease = self.db.query(DeviceLease).filter(
            DeviceLease.device_id == device_id,
            DeviceLease.run_id == run_id,
            DeviceLease.lease_status == "active"
        ).first()

        if not lease:
            return False

        lease.lease_status = "released"
        lease.released_at = datetime.utcnow()

        # 更新设备状态
        device = self.db.query(Device).filter_by(id=device_id).first()
        if device:
            device.status = DeviceStatus.IDLE
            device.current_run_id = None

        self.db.commit()
        return True

    def select_device_for_run(
        self,
        run_id: int,
        min_battery: int = 20,
    ) -> Optional[Device]:
        """为任务选择合适的设备。"""
        run = self.db.query(RunSession).filter_by(id=run_id).first()
        if not run:
            return None

        plan = self.db.query(UpgradePlan).filter_by(id=run.plan_id).first()
        if not plan:
            return None

        # 获取选择条件
        selector = plan.get_device_selector()

        # 获取可用设备
        available_devices = self.device_service.get_available_devices(
            tags=selector.get("tags"),
            min_battery=min_battery,
        )

        if not available_devices:
            return None

        # 根据选择器过滤
        for device in available_devices:
            match = True
            for key, value in selector.items():
                if key == "tags":
                    continue
                device_value = getattr(device, key, None)
                if device_value != value:
                    match = False
                    break

            if match:
                return device

        # 如果没有精确匹配，返回第一个可用设备
        return available_devices[0] if available_devices else None

    def reserve_run(self, run_id: int) -> bool:
        """预留任务（分配设备并获取租约）。"""
        run = self.db.query(RunSession).filter_by(id=run_id).first()
        if not run:
            return False

        if run.status != RunStatus.QUEUED:
            return False

        # 选择设备
        device = self.select_device_for_run(run_id)
        if not device:
            return False

        # 获取租约
        lease = self.acquire_device_lease(device.id, run_id)
        if not lease:
            return False

        # 更新任务状态
        run.status = RunStatus.RESERVED
        run.device_id = device.id

        self.db.commit()
        return True

    def get_next_run_to_execute(self) -> Optional[RunSession]:
        """获取下一个待执行的任务。"""
        run = self.db.query(RunSession).filter(
            RunSession.status == RunStatus.RESERVED
        ).order_by(RunSession.created_at).first()

        return run

    def cleanup_expired_leases(self) -> List[DeviceLease]:
        """清理过期租约。"""
        expired_leases = self.db.query(DeviceLease).filter(
            and_(
                DeviceLease.lease_status == "active",
                DeviceLease.expired_at < datetime.utcnow()
            )
        ).all()

        for lease in expired_leases:
            lease.lease_status = "expired"

            # 设备进入恢复状态
            device = self.db.query(Device).filter_by(id=lease.device_id).first()
            if device:
                device.status = DeviceStatus.RECOVERING
                device.current_run_id = None

            # 任务进入隔离状态
            run = self.db.query(RunSession).filter_by(id=lease.run_id).first()
            if run:
                run.status = RunStatus.QUARANTINED
                run.failure_category = "lease_expired"

        self.db.commit()
        return expired_leases

    def get_concurrent_run_count(self) -> int:
        """获取当前并发运行的任务数。"""
        return self.db.query(RunSession).filter(
            RunSession.status.in_([
                RunStatus.RUNNING,
                RunStatus.VALIDATING,
            ])
        ).count()

    def can_start_new_run(self) -> bool:
        """检查是否可以启动新任务。"""
        current_count = self.get_concurrent_run_count()
        return current_count < self.settings.MAX_CONCURRENT_RUNS