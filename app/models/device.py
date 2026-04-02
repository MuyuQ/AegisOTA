"""设备数据模型。"""

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
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
from app.models.enums import DeviceStatus, LeaseStatus, PoolPurpose

if TYPE_CHECKING:
    from app.models.run import RunSession


class DevicePool(Base):
    """设备池实体。"""

    __tablename__ = "device_pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    purpose: Mapped[PoolPurpose] = mapped_column(String(32), nullable=False)

    # 池配置
    reserved_ratio: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    max_parallel: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    tag_selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    devices: Mapped[list["Device"]] = relationship(
        "Device", back_populates="pool", cascade="all, delete-orphan"
    )

    def get_tag_selector(self) -> dict[str, Any]:
        """获取标签选择器配置。"""
        if not self.tag_selector:
            return {}
        try:
            return json.loads(self.tag_selector)
        except json.JSONDecodeError:
            return {}

    def set_tag_selector(self, selector: dict[str, Any]) -> None:
        """设置标签选择器配置。"""
        self.tag_selector = json.dumps(selector) if selector else None

    def get_available_count(self) -> int:
        """获取池中可用设备数量。"""
        from app.models.enums import DeviceStatus
        return len([d for d in self.devices if d.status == DeviceStatus.IDLE])

    def get_capacity(self) -> int:
        """获取池的最大并行容量。"""
        return self.max_parallel


class Device(Base):
    """设备实体。"""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    serial: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # 设备信息
    brand: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    system_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    build_fingerprint: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # 状态与健康
    status: Mapped[DeviceStatus] = mapped_column(
        String(32), default=DeviceStatus.IDLE, nullable=False, index=True
    )
    health_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    battery_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sync_failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 设备池关联
    pool_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("device_pools.id", ondelete="SET NULL"), nullable=True, index=True
    )

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
    pool: Mapped[Optional["DevicePool"]] = relationship("DevicePool", back_populates="devices")
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

    # 抢占相关
    preemptible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preempted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    preempted_by_run_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 关系
    device: Mapped["Device"] = relationship("Device", back_populates="leases")
    run_session: Mapped[Optional["RunSession"]] = relationship(
        "RunSession", back_populates="lease"
    )

    def is_active(self) -> bool:
        """检查租约是否有效。"""
        if self.lease_status != LeaseStatus.ACTIVE:
            return False
        if self.expired_at:
            # 确保 expired_at 有时区信息进行比较
            expired = self.expired_at
            if expired.tzinfo is None:
                # 如果没有时区信息，假设为 UTC
                expired = expired.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expired:
                return False
        return True