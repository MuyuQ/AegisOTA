"""设备数据模型。"""

import json
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DeviceStatus(str, Enum):
    """设备状态枚举。"""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    QUARANTINED = "quarantined"
    RECOVERING = "recovering"


class LeaseStatus(str, Enum):
    """租约状态枚举。"""

    ACTIVE = "active"
    EXPIRED = "expired"
    RELEASED = "released"


class Device(Base):
    """设备实体。"""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    serial: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # 设备信息
    brand: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    android_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    build_fingerprint: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # 状态与健康
    status: Mapped[DeviceStatus] = mapped_column(
        String(32), default=DeviceStatus.IDLE, nullable=False, index=True
    )
    health_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    battery_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 标签（JSON 存储）
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间戳
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 隔离与任务关联
    quarantine_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 关系
    leases: Mapped[list["DeviceLease"]] = relationship(
        "DeviceLease", back_populates="device", cascade="all, delete-orphan"
    )
    run_sessions: Mapped[list["RunSession"]] = relationship(
        "RunSession", back_populates="device", cascade="all, delete-orphan"
    )

    def get_tags(self) -> list[str]:
        """获取标签列表。"""
        if not self.tags:
            return []
        try:
            return json.loads(self.tags)
        except json.JSONDecodeError:
            return []

    def set_tags(self, tags: list[str]) -> None:
        """设置标签列表。"""
        self.tags = json.dumps(tags) if tags else None

    def is_available(self) -> bool:
        """检查设备是否可用（可被分配任务）。"""
        return self.status == DeviceStatus.IDLE


class DeviceLease(Base):
    """设备租约实体。"""

    __tablename__ = "device_leases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("run_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # 租约时间
    leased_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expired_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 租约状态
    lease_status: Mapped[LeaseStatus] = mapped_column(
        String(32), default=LeaseStatus.ACTIVE, nullable=False
    )

    # 关系
    device: Mapped["Device"] = relationship("Device", back_populates="leases")
    run_session: Mapped[Optional["RunSession"]] = relationship(
        "RunSession", back_populates="lease"
    )

    def is_active(self) -> bool:
        """检查租约是否有效。"""
        if self.lease_status != LeaseStatus.ACTIVE:
            return False
        if self.expired_at and datetime.utcnow() > self.expired_at:
            return False
        return True