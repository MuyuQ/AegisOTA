"""异常注入相关数据模型。"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FaultStage(str, Enum):
    """故障注入阶段枚举。"""

    PRECHECK = "precheck"
    APPLY_UPDATE = "apply_update"
    POST_VALIDATE = "post_validate"


class FaultType(str, Enum):
    """故障类型枚举。"""

    STORAGE_PRESSURE = "storage_pressure"
    DOWNLOAD_INTERRUPTED = "download_interrupted"
    PACKAGE_CORRUPTED = "package_corrupted"
    LOW_BATTERY = "low_battery"
    REBOOT_INTERRUPTED = "reboot_interrupted"
    POST_BOOT_WATCHDOG_FAILURE = "post_boot_watchdog_failure"
    MONKEY_AFTER_UPGRADE = "monkey_after_upgrade"
    PERFORMANCE_REGRESSION = "performance_regression"


class FaultProfile(Base):
    """故障注入配置实体。

    定义故障注入的类型、阶段和参数。
    """

    __tablename__ = "fault_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # 故障配置
    fault_stage: Mapped[FaultStage] = mapped_column(
        String(32), nullable=False, index=True
    )
    fault_type: Mapped[FaultType] = mapped_column(
        String(64), nullable=False, index=True
    )

    # 参数配置（JSON 存储）
    parameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 状态与描述
    enabled: Mapped[bool] = mapped_column(Integer, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    upgrade_plans: Mapped[list["UpgradePlan"]] = relationship(
        "UpgradePlan", back_populates="fault_profile"
    )

    def get_parameters(self) -> dict[str, Any]:
        """获取故障参数配置。"""
        if not self.parameters:
            return {}
        try:
            return json.loads(self.parameters)
        except json.JSONDecodeError:
            return {}

    def set_parameters(self, params: dict[str, Any]) -> None:
        """设置故障参数配置。"""
        self.parameters = json.dumps(params) if params else None