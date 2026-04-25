"""调度与并发控制服务。"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.device import Device, DeviceLease, DevicePool, DeviceStatus, LeaseStatus
from app.models.enums import RunPriority
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
        preemptible: bool = True,
    ) -> Optional[DeviceLease]:
        """获取设备租约（使用 SELECT FOR UPDATE 防止竞态条件）。"""
        try:
            # 使用 SELECT FOR UPDATE 锁定设备行，防止并发竞态
            device = self.db.execute(
                select(Device).where(Device.id == device_id).with_for_update()
            ).scalar_one_or_none()

            if device is None:
                return None

            # 检查设备状态（在锁定状态下）
            if device.status != DeviceStatus.IDLE:
                return None

            # 检查是否有活跃租约（在锁定状态下）
            active_lease = self.db.execute(
                select(DeviceLease)
                .where(
                    DeviceLease.device_id == device_id,
                    DeviceLease.lease_status == LeaseStatus.ACTIVE,
                )
                .with_for_update()
            ).scalar_one_or_none()

            if active_lease:
                return None

            # 创建租约
            lease_duration = duration or self.settings.LEASE_DEFAULT_DURATION
            lease = DeviceLease(
                device_id=device_id,
                run_id=run_id,
                lease_status=LeaseStatus.ACTIVE,
                expired_at=datetime.now(timezone.utc) + timedelta(seconds=lease_duration),
                preemptible=preemptible,
            )

            # 更新设备状态
            device.status = DeviceStatus.RESERVED
            device.current_run_id = run_id

            self.db.add(lease)
            self.db.commit()

            return lease

        except Exception:
            self.db.rollback()
            raise

    def release_device_lease(
        self,
        device_id: int,
        run_id: int,
    ) -> bool:
        """释放设备租约（使用 SELECT FOR UPDATE 防止竞态条件）。"""
        try:
            # 使用 SELECT FOR UPDATE 锁定租约行
            lease = self.db.execute(
                select(DeviceLease)
                .where(
                    DeviceLease.device_id == device_id,
                    DeviceLease.run_id == run_id,
                    DeviceLease.lease_status == LeaseStatus.ACTIVE,
                )
                .with_for_update()
            ).scalar_one_or_none()

            if not lease:
                return False

            lease.lease_status = LeaseStatus.RELEASED
            lease.released_at = datetime.now(timezone.utc)

            # 锁定并更新设备状态
            device = self.db.execute(
                select(Device).where(Device.id == device_id).with_for_update()
            ).scalar_one_or_none()

            if device:
                device.status = DeviceStatus.IDLE
                device.current_run_id = None

            self.db.commit()
            return True

        except Exception:
            self.db.rollback()
            raise

    def select_device_for_run(
        self,
        run_id: int,
        min_battery: int = 20,
        pool_id: Optional[int] = None,
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

        # 如果指定了 pool_id，只从该池中选择设备
        if pool_id is not None:
            available_devices = [d for d in available_devices if d.pool_id == pool_id]
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

    def get_next_run_to_schedule(self, pool_id: Optional[int] = None) -> Optional[RunSession]:
        """获取下一个待调度的任务（按优先级和 FIFO 排序）。"""
        query = self.db.query(RunSession).filter(RunSession.status == RunStatus.QUEUED)

        # 如果指定了池 ID，只查询该池的任务
        if pool_id is not None:
            query = query.filter(RunSession.pool_id == pool_id)

        # 按优先级排序（EMERGENCY > HIGH > NORMAL），同优先级按创建时间 FIFO
        # 由于 Enum 在 SQLite 中存储为字符串，需要按优先级值排序
        # 我们使用 case 语句来定义优先级顺序
        from sqlalchemy import case

        priority_order = case(
            (RunSession.priority == RunPriority.EMERGENCY, 1),
            (RunSession.priority == RunPriority.HIGH, 2),
            (RunSession.priority == RunPriority.NORMAL, 3),
            else_=4,
        )

        query = query.order_by(priority_order, RunSession.created_at)

        return query.first()

    def get_pool_available_capacity(self, pool_id: int) -> int:
        """获取设备池的可用容量（考虑保留容量）。"""
        pool = self.db.query(DevicePool).filter_by(id=pool_id).first()
        if not pool:
            return 0

        # 获取池中所有设备
        devices = self.db.query(Device).filter_by(pool_id=pool_id).all()

        # 计算可用设备数（只有 IDLE 状态的设备）
        available_devices = len([d for d in devices if d.status == DeviceStatus.IDLE])

        # 计算保留容量
        reserved_count = int(pool.max_parallel * pool.reserved_ratio)
        usable_count = pool.max_parallel - reserved_count

        # 计算当前正在使用的设备数（BUSY 或 RESERVED 状态）
        used_count = len(
            [d for d in devices if d.status in (DeviceStatus.BUSY, DeviceStatus.RESERVED)]
        )

        # 返回可用容量（不能超过保留后可用的数量）
        remaining = usable_count - used_count
        return max(0, min(remaining, available_devices))

    def allocate_device_for_run(
        self,
        run_id: int,
        min_battery: int = 20,
    ) -> Optional[Device]:
        """为任务分配设备（考虑池容量限制）。"""
        run = self.db.query(RunSession).filter_by(id=run_id).first()
        if not run:
            return None

        if run.status not in (RunStatus.QUEUED,):
            return None

        # 如果没有指定 pool_id，尝试从计划中获取
        pool_id = run.pool_id
        if not pool_id:
            plan = self.db.query(UpgradePlan).filter_by(id=run.plan_id).first()
            if plan:
                pool_id = plan.default_pool_id

        # 如果有池，检查容量
        if pool_id:
            pool = self.db.query(DevicePool).filter_by(id=pool_id).first()
            if pool:
                available_capacity = self.get_pool_available_capacity(pool_id)
                if available_capacity <= 0:
                    return None

        # 选择设备 - 直接从数据库查询，绕过 device_service 的限制
        device = self._select_device_from_pool_direct(pool_id, min_battery)
        if not device:
            return None

        # 更新设备状态为 RESERVED
        device.status = DeviceStatus.RESERVED
        device.current_run_id = run.id

        # 更新任务状态为 ALLOCATING
        run.status = RunStatus.ALLOCATING

        self.db.commit()
        return device

    def _select_device_from_pool_direct(
        self,
        pool_id: Optional[int],
        min_battery: int = 20,
    ) -> Optional[Device]:
        """直接从设备池选择设备（绕过 device_service）。"""
        if not pool_id:
            return None

        query = self.db.query(Device).filter(
            Device.pool_id == pool_id,
            Device.status == DeviceStatus.IDLE,
        )

        if min_battery:
            query = query.filter(Device.battery_level >= min_battery)

        return query.first()

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
        run = (
            self.db.query(RunSession)
            .filter(RunSession.status == RunStatus.RESERVED)
            .order_by(RunSession.created_at)
            .first()
        )

        return run

    def get_concurrent_run_count(self) -> int:
        """获取当前并发运行的任务数。"""
        return (
            self.db.query(RunSession)
            .filter(
                RunSession.status.in_(
                    [
                        RunStatus.RUNNING,
                        RunStatus.VALIDATING,
                    ]
                )
            )
            .count()
        )

    def can_start_new_run(self) -> bool:
        """检查是否可以启动新任务。"""
        current_count = self.get_concurrent_run_count()
        return current_count < self.settings.MAX_CONCURRENT_RUNS
