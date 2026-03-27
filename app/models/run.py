"""任务相关数据模型。"""

import json
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.fault import FaultProfile

if TYPE_CHECKING:
    from app.models.artifact import Artifact


class RunStatus(str, Enum):
    """任务运行状态枚举。"""

    QUEUED = "queued"
    RESERVED = "reserved"
    RUNNING = "running"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"
    ABORTED = "aborted"
    QUARANTINED = "quarantined"


class UpgradeType(str, Enum):
    """升级类型枚举。"""

    FULL = "full"
    INCREMENTAL = "incremental"
    ROLLBACK = "rollback"


class StepName(str, Enum):
    """执行步骤名称枚举。"""

    PRECHECK = "precheck"
    PACKAGE_PREPARE = "package_prepare"
    APPLY_UPDATE = "apply_update"
    REBOOT_WAIT = "reboot_wait"
    POST_VALIDATE = "post_validate"
    REPORT_FINALIZE = "report_finalize"


class StepStatus(str, Enum):
    """步骤状态枚举。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class FailureCategory(str, Enum):
    """失败分类枚举。"""

    PACKAGE_ISSUE = "package_issue"
    DEVICE_ENV_ISSUE = "device_env_issue"
    BOOT_FAILURE = "boot_failure"
    VALIDATION_FAILURE = "validation_failure"
    MONKEY_INSTABILITY = "monkey_instability"
    PERFORMANCE_SUSPECT = "performance_suspect"
    ADB_TRANSPORT_ISSUE = "adb_transport_issue"
    UNKNOWN = "unknown"


class UpgradePlan(Base):
    """升级计划实体。

    定义升级任务的模板，包含升级配置和故障注入配置。
    """

    __tablename__ = "upgrade_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # 升级配置
    upgrade_type: Mapped[UpgradeType] = mapped_column(
        String(32), default=UpgradeType.FULL, nullable=False
    )
    package_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    target_build: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # 配置关联
    fault_profile_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("fault_profiles.id", ondelete="SET NULL"), nullable=True
    )
    validation_profile_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 设备选择器（JSON 存储）
    device_selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 执行配置
    parallelism: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # 创建者
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    run_sessions: Mapped[list["RunSession"]] = relationship(
        "RunSession", back_populates="plan", cascade="all, delete-orphan"
    )
    fault_profile: Mapped[Optional["FaultProfile"]] = relationship(
        "FaultProfile", back_populates="upgrade_plans"
    )

    def get_device_selector(self) -> dict[str, Any]:
        """获取设备选择器配置。"""
        if not self.device_selector:
            return {}
        try:
            return json.loads(self.device_selector)
        except json.JSONDecodeError:
            return {}

    def set_device_selector(self, selector: dict[str, Any]) -> None:
        """设置设备选择器配置。"""
        self.device_selector = json.dumps(selector) if selector else None


class RunSession(Base):
    """任务运行会话实体。

    记录单次升级任务的执行过程和结果。
    """

    __tablename__ = "run_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("upgrade_plans.id", ondelete="SET NULL"), nullable=True, index=True
    )
    device_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # 状态与结果
    status: Mapped[RunStatus] = mapped_column(
        String(32), default=RunStatus.QUEUED, nullable=False, index=True
    )
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_category: Mapped[Optional[FailureCategory]] = mapped_column(
        String(32), nullable=True
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间戳
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    plan: Mapped[Optional["UpgradePlan"]] = relationship(
        "UpgradePlan", back_populates="run_sessions"
    )
    device: Mapped[Optional["Device"]] = relationship(
        "Device", back_populates="run_sessions"
    )
    steps: Mapped[list["RunStep"]] = relationship(
        "RunStep", back_populates="run_session", cascade="all, delete-orphan"
    )
    lease: Mapped[Optional["DeviceLease"]] = relationship(
        "DeviceLease", back_populates="run_session", uselist=False
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact", back_populates="run_session", cascade="all, delete-orphan"
    )

    def get_duration_seconds(self) -> Optional[float]:
        """计算任务持续时间（秒）。"""
        if self.started_at and self.ended_at:
            delta = self.ended_at - self.started_at
            return delta.total_seconds()
        return None

    def is_terminal_state(self) -> bool:
        """检查是否处于终态。"""
        return self.status in (
            RunStatus.PASSED,
            RunStatus.FAILED,
            RunStatus.ABORTED,
            RunStatus.QUARANTINED,
        )


class RunStep(Base):
    """任务执行步骤实体。

    记录单个执行步骤的详细信息和输出。
    """

    __tablename__ = "run_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("run_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_name: Mapped[StepName] = mapped_column(String(32), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 状态与输出
    status: Mapped[StepStatus] = mapped_column(
        String(32), default=StepStatus.PENDING, nullable=False
    )
    command: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stdout_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    stderr_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    step_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间戳
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    run_session: Mapped["RunSession"] = relationship(
        "RunSession", back_populates="steps"
    )

    def get_result(self) -> dict[str, Any]:
        """获取步骤结果。"""
        if not self.step_result:
            return {}
        try:
            return json.loads(self.step_result)
        except json.JSONDecodeError:
            return {}

    def set_result(self, result: dict[str, Any]) -> None:
        """设置步骤结果。"""
        self.step_result = json.dumps(result) if result else None

    def get_duration_seconds(self) -> Optional[float]:
        """计算步骤持续时间（秒）。"""
        if self.started_at and self.ended_at:
            delta = self.ended_at - self.started_at
            return delta.total_seconds()
        return None