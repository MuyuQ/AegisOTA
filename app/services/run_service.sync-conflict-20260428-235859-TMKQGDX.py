"""任务管理业务逻辑。"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models.run import RunSession, RunStatus, RunStep, StepName, UpgradePlan, UpgradeType


class RunService:
    """任务管理服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def create_upgrade_plan(
        self,
        name: str,
        upgrade_type: UpgradeType,
        package_path: str,
        target_build: Optional[str] = None,
        device_selector: Optional[Dict[str, Any]] = None,
        fault_profile_id: Optional[int] = None,
        parallelism: int = 1,
        created_by: Optional[str] = None,
    ) -> UpgradePlan:
        """创建升级计划。"""
        plan = UpgradePlan(
            name=name,
            upgrade_type=upgrade_type,
            package_path=package_path,
            target_build=target_build,
            fault_profile_id=fault_profile_id,
            parallelism=parallelism,
            created_by=created_by,
        )

        if device_selector:
            plan.set_device_selector(device_selector)

        self.db.add(plan)
        self.db.commit()
        return plan

    def get_upgrade_plan(self, plan_id: int) -> Optional[UpgradePlan]:
        """获取升级计划。"""
        return self.db.query(UpgradePlan).filter_by(id=plan_id).first()

    def list_upgrade_plans(self) -> List[UpgradePlan]:
        """列出所有升级计划。"""
        return self.db.query(UpgradePlan).order_by(UpgradePlan.created_at.desc()).all()

    def update_upgrade_plan(
        self,
        plan_id: int,
        name: Optional[str] = None,
        upgrade_type: Optional[UpgradeType] = None,
        package_path: Optional[str] = None,
        source_build: Optional[str] = None,
        target_build: Optional[str] = None,
        default_pool_id: Optional[int] = None,
        parallelism: Optional[int] = None,
    ) -> Optional[UpgradePlan]:
        """更新升级计划。"""
        plan = self.get_upgrade_plan(plan_id)
        if not plan:
            return None

        if name is not None:
            plan.name = name
        if upgrade_type is not None:
            plan.upgrade_type = upgrade_type
        if package_path is not None:
            plan.package_path = package_path
        if source_build is not None:
            plan.source_build = source_build
        if target_build is not None:
            plan.target_build = target_build
        if default_pool_id is not None:
            plan.default_pool_id = default_pool_id
        if parallelism is not None:
            plan.parallelism = parallelism

        self.db.commit()
        self.db.refresh(plan)
        return plan

    def delete_upgrade_plan(self, plan_id: int) -> bool:
        """删除升级计划。"""
        plan = self.get_upgrade_plan(plan_id)
        if not plan:
            return False

        self.db.delete(plan)
        self.db.commit()
        return True

    def create_run_session(
        self,
        plan_id: int,
        device_id: Optional[int] = None,
        run_options: Optional[Dict[str, Any]] = None,
        total_iterations: int = 1,
    ) -> RunSession:
        """创建任务执行会话。"""
        session = RunSession(
            plan_id=plan_id,
            device_id=device_id,
            status=RunStatus.QUEUED,
            total_iterations=total_iterations,
        )

        if run_options:
            session.set_run_options(run_options)

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_run_session(self, run_id: int) -> Optional[RunSession]:
        """获取任务会话。"""
        return self.db.query(RunSession).filter_by(id=run_id).first()

    def update_run_status(
        self,
        run_id: int,
        status: RunStatus,
        started_at: Optional[datetime] = None,
    ) -> Optional[RunSession]:
        """更新任务状态。"""
        session = self.get_run_session(run_id)
        if not session:
            return None

        session.status = status

        if status == RunStatus.RUNNING and not session.started_at:
            session.started_at = started_at or datetime.now(timezone.utc)

        self.db.commit()
        return session

    def complete_run_session(
        self,
        run_id: int,
        result: str,
        status: RunStatus = RunStatus.PASSED,
        summary: Optional[str] = None,
        failure_category: Optional[str] = None,
    ) -> Optional[RunSession]:
        """完成任务会话。"""
        session = self.get_run_session(run_id)
        if not session:
            return None

        session.status = status
        session.result = result
        session.ended_at = datetime.now(timezone.utc)
        session.summary = summary
        session.failure_category = failure_category

        self.db.commit()
        return session

    def abort_run_session(
        self,
        run_id: int,
        reason: Optional[str] = None,
    ) -> Optional[RunSession]:
        """终止任务会话。"""
        session = self.get_run_session(run_id)
        if not session:
            return None

        # 只有排队和运行中的任务可以终止
        if session.status not in [RunStatus.QUEUED, RunStatus.RESERVED, RunStatus.RUNNING]:
            return None

        session.status = RunStatus.ABORTED
        session.result = "aborted"
        session.ended_at = datetime.now(timezone.utc)
        session.summary = reason

        self.db.commit()
        return session

    def list_runs(
        self,
        status: Optional[RunStatus] = None,
        limit: int = 100,
    ) -> List[RunSession]:
        """列出任务。"""
        query = self.db.query(RunSession).options(
            joinedload(RunSession.device),
            joinedload(RunSession.plan),
        )

        if status:
            query = query.filter(RunSession.status == status)

        return query.order_by(RunSession.created_at.desc()).limit(limit).all()

    def list_pending_runs(self) -> List[RunSession]:
        """列出待执行任务（排队状态）。"""
        return (
            self.db.query(RunSession)
            .filter(RunSession.status == RunStatus.QUEUED)
            .order_by(RunSession.created_at)
            .all()
        )

    def create_run_step(
        self,
        run_id: int,
        step_name: StepName,
        step_order: int,
        command: Optional[str] = None,
    ) -> RunStep:
        """创建执行步骤。"""
        step = RunStep(
            run_id=run_id,
            step_name=step_name,
            step_order=step_order,
            command=command,
            status="pending",
        )

        self.db.add(step)
        self.db.commit()
        return step

    def update_run_step(
        self,
        step_id: int,
        status: str,
        stdout_path: Optional[str] = None,
        stderr_path: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> Optional[RunStep]:
        """更新执行步骤状态。"""
        step = self.db.query(RunStep).filter_by(id=step_id).first()
        if not step:
            return None

        step.status = status

        if status == "running":
            step.started_at = datetime.now(timezone.utc)
        elif status in ["success", "failure"]:
            step.ended_at = datetime.now(timezone.utc)

        if stdout_path:
            step.stdout_path = stdout_path
        if stderr_path:
            step.stderr_path = stderr_path
        if result:
            step.set_result(result)

        self.db.commit()
        return step

    def get_run_steps(self, run_id: int) -> List[RunStep]:
        """获取任务的所有执行步骤。"""
        return self.db.query(RunStep).filter_by(run_id=run_id).order_by(RunStep.step_order).all()
