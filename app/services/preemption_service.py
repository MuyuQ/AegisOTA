"""抢占服务。"""

from datetime import datetime, timezone
from typing import List

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models.device import Device, DeviceLease, DeviceStatus, LeaseStatus
from app.models.enums import RunPriority
from app.models.run import RunSession, RunStatus


class PreemptionService:
    """抢占服务。

    用于紧急任务抢占低优先级任务的设备资源。
    """

    def __init__(self, db: Session):
        self.db = db

    def find_preemptible_runs(
        self,
        pool_id: int,
        allow_preempt_high: bool = False,
    ) -> List[RunSession]:
        """查找可被抢占的任务。

        Args:
            pool_id: 设备池 ID
            allow_preempt_high: 是否允许抢占 HIGH 优先级任务（默认只抢占 NORMAL）

        Returns:
            可被抢占的任务列表，按优先级（NORMAL 优先）和运行时间排序
        """
        # 构建查询
        query = self.db.query(RunSession).filter(
            RunSession.pool_id == pool_id,
            RunSession.preemptible,
            RunSession.status.in_([RunStatus.RESERVED, RunStatus.RUNNING]),
        )

        # 如果不允许抢占 HIGH，只返回 NORMAL 优先级
        if not allow_preempt_high:
            query = query.filter(RunSession.priority == RunPriority.NORMAL)

        # 使用 case 语句定义优先级顺序（NORMAL 优先被抢占）
        priority_order = case(
            (RunSession.priority == RunPriority.NORMAL, 1),
            (RunSession.priority == RunPriority.HIGH, 2),
            else_=3,
        )

        # 按优先级和创建时间排序（先抢占运行时间长的）
        query = query.order_by(priority_order, RunSession.created_at)

        return query.all()

    def preempt_run(
        self,
        victim_run_id: int,
        preemptor_run_id: int,
    ) -> bool:
        """抢占任务。

        Args:
            victim_run_id: 受害者任务 ID
            preemptor_run_id: 抢占者任务 ID

        Returns:
            抢占是否成功
        """
        try:
            # 获取受害者任务
            victim_run = self.db.query(RunSession).filter_by(id=victim_run_id).first()
            if not victim_run:
                return False

            # 检查任务是否可被抢占
            if not victim_run.preemptible:
                return False

            # 获取抢占者任务
            preemptor_run = self.db.query(RunSession).filter_by(id=preemptor_run_id).first()
            if not preemptor_run:
                return False

            # 使用 SELECT FOR UPDATE 锁定租约行，防止并发竞态
            lease = self.db.execute(
                select(DeviceLease)
                .where(
                    DeviceLease.run_id == victim_run_id,
                    DeviceLease.lease_status == LeaseStatus.ACTIVE,
                )
                .with_for_update()
            ).scalar_one_or_none()

            if not lease:
                return False

            device_id = lease.device_id

            # 更新租约状态
            lease.lease_status = LeaseStatus.PREEMPTED
            lease.preempted_at = datetime.now(timezone.utc)
            lease.preempted_by_run_id = preemptor_run_id

            # 更新受害者任务状态
            victim_run.status = RunStatus.PREEMPTED
            victim_run.ended_at = datetime.now(timezone.utc)

            # 使用 SELECT FOR UPDATE 锁定设备行，防止并发竞态
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

    def check_and_execute_preemption(
        self,
        emergency_run_id: int,
        allow_preempt_high: bool = False,
    ) -> bool:
        """检查并执行抢占。

        Args:
            emergency_run_id: 紧急任务 ID
            allow_preempt_high: 是否允许抢占 HIGH 优先级任务

        Returns:
            是否执行了抢占
        """
        # 获取紧急任务
        emergency_run = self.db.query(RunSession).filter_by(id=emergency_run_id).first()
        if not emergency_run:
            return False

        # 只有 EMERGENCY 优先级可以抢占
        if emergency_run.priority != RunPriority.EMERGENCY:
            return False

        # 获取任务所在的池
        pool_id = emergency_run.pool_id
        if not pool_id:
            return False

        # 查找可抢占的任务
        preemptible_runs = self.find_preemptible_runs(pool_id, allow_preempt_high)

        if not preemptible_runs:
            return False

        # 抢占第一个（优先级最低、运行时间最长）的任务
        victim_run = preemptible_runs[0]

        # 执行抢占
        return self.preempt_run(victim_run.id, emergency_run_id)
