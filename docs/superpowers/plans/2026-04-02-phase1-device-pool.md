# Phase 1: Device Pool Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement device pool management, priority scheduling, and emergency preemption for AegisOTA.

**Architecture:** Extend existing Device model with pool_id and health_score (int). Add DevicePool model with pool management capabilities. Extend RunSession with priority and pool_id. Implement pool_service, preemption_service, and extend scheduler_service.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Typer, pytest

---

## File Structure

```
app/
├── models/
│   ├── device.py          # Extend: add pool_id, sync_failure_count, change health_score to int
│   ├── run.py             # Extend: add priority, pool_id, preemptible, drill_id
│   └── enums.py           # New: PoolPurpose, RunPriority (extend DeviceStatus, RunStatus)
├── services/
│   ├── pool_service.py    # New: DevicePoolService
│   ├── preemption_service.py  # New: PreemptionService
│   └── scheduler_service.py   # Extend: priority scheduling, pool-based allocation
├── api/
│   └── pools.py           # New: /api/pools endpoints
├── cli/
│   └── pool.py            # New: labctl pool commands
└── templates/
    └── pools.html         # New: pool management page

tests/
├── test_models/
│   ├── test_device.py     # Extend: test new fields and DevicePool
│   └── test_run.py        # Extend: test new fields
├── test_services/
│   ├── test_pool_service.py       # New
│   └── test_preemption_service.py # New
└── test_api/
    └── test_pools.py      # New
```

---

## Task 1: Extend Enums - Add PoolPurpose, RunPriority, Extend DeviceStatus, RunStatus

**Files:**
- Create: `app/models/enums.py`
- Test: `tests/test_models/test_enums.py`

- [ ] **Step 1: Write the failing test for new enums**

```python
# tests/test_models/test_enums.py
"""枚举定义测试。"""

import pytest
from app.models.enums import (
    DeviceStatus, LeaseStatus, PoolPurpose, RunPriority, RunStatus
)


class TestDeviceStatus:
    """DeviceStatus 枚举测试。"""

    def test_existing_values(self):
        """测试现有枚举值。"""
        assert DeviceStatus.IDLE == "idle"
        assert DeviceStatus.BUSY == "busy"
        assert DeviceStatus.OFFLINE == "offline"
        assert DeviceStatus.QUARANTINED == "quarantined"
        assert DeviceStatus.RECOVERING == "recovering"

    def test_new_reserved_status(self):
        """测试新增的 RESERVED 状态。"""
        assert DeviceStatus.RESERVED == "reserved"

    def test_status_count(self):
        """测试枚举值数量。"""
        assert len(DeviceStatus) == 6


class TestPoolPurpose:
    """PoolPurpose 枚举测试。"""

    def test_pool_purpose_values(self):
        """测试设备池用途枚举值。"""
        assert PoolPurpose.STABLE == "stable"
        assert PoolPurpose.STRESS == "stress"
        assert PoolPurpose.EMERGENCY == "emergency"

    def test_pool_purpose_count(self):
        """测试枚举值数量。"""
        assert len(PoolPurpose) == 3


class TestRunPriority:
    """RunPriority 枚举测试。"""

    def test_priority_values(self):
        """测试任务优先级枚举值。"""
        assert RunPriority.NORMAL == "normal"
        assert RunPriority.HIGH == "high"
        assert RunPriority.EMERGENCY == "emergency"

    def test_priority_count(self):
        """测试枚举值数量。"""
        assert len(RunPriority) == 3


class TestRunStatus:
    """RunStatus 枚举测试。"""

    def test_existing_values(self):
        """测试现有枚举值。"""
        assert RunStatus.QUEUED == "queued"
        assert RunStatus.RESERVED == "reserved"
        assert RunStatus.RUNNING == "running"
        assert RunStatus.VALIDATING == "validating"
        assert RunStatus.PASSED == "passed"
        assert RunStatus.FAILED == "failed"
        assert RunStatus.ABORTED == "aborted"

    def test_new_statuses(self):
        """测试新增状态。"""
        assert RunStatus.ALLOCATING == "allocating"
        assert RunStatus.PREEMPTED == "preempted"

    def test_removed_quarantined(self):
        """测试已移除的 quarantined 状态。"""
        # RunStatus 不应包含 quarantined
        assert not hasattr(RunStatus, 'QUARANTINED')

    def test_status_count(self):
        """测试枚举值数量。"""
        assert len(RunStatus) == 9


class TestLeaseStatus:
    """LeaseStatus 枚举测试。"""

    def test_existing_values(self):
        """测试现有枚举值。"""
        assert LeaseStatus.ACTIVE == "active"
        assert LeaseStatus.EXPIRED == "expired"
        assert LeaseStatus.RELEASED == "released"

    def test_new_preempted_status(self):
        """测试新增的 PREEMPTED 状态。"""
        assert LeaseStatus.PREEMPTED == "preempted"

    def test_status_count(self):
        """测试枚举值数量。"""
        assert len(LeaseStatus) == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_models/test_enums.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.models.enums'"

- [ ] **Step 3: Write the implementation**

```python
# app/models/enums.py
"""统一枚举定义。"""

from enum import Enum


class DeviceStatus(str, Enum):
    """设备状态枚举。"""

    IDLE = "idle"
    RESERVED = "reserved"       # 新增：已分配但任务未开始
    BUSY = "busy"
    OFFLINE = "offline"
    QUARANTINED = "quarantined"
    RECOVERING = "recovering"


class LeaseStatus(str, Enum):
    """租约状态枚举。"""

    ACTIVE = "active"
    RELEASED = "released"
    PREEMPTED = "preempted"     # 新增：被抢占
    EXPIRED = "expired"


class PoolPurpose(str, Enum):
    """设备池用途枚举。"""

    STABLE = "stable"           # 稳定测试池
    STRESS = "stress"           # 压力测试池
    EMERGENCY = "emergency"     # 应急池


class RunPriority(str, Enum):
    """任务优先级枚举。"""

    NORMAL = "normal"
    HIGH = "high"
    EMERGENCY = "emergency"


class RunStatus(str, Enum):
    """任务状态枚举。"""

    QUEUED = "queued"
    ALLOCATING = "allocating"   # 新增：正在分配设备
    RESERVED = "reserved"
    RUNNING = "running"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"
    ABORTED = "aborted"
    PREEMPTED = "preempted"     # 新增：被抢占
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_models/test_enums.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
cd E:/git_repositories/AegisOTA
git add app/models/enums.py tests/test_models/test_enums.py
git commit -m "feat: add enums for device pool and priority scheduling"
```

---

## Task 2: Add DevicePool Model and Extend Device Model

**Files:**
- Modify: `app/models/device.py`
- Modify: `tests/test_models/test_device.py`

- [ ] **Step 1: Write the failing test for DevicePool**

Add to `tests/test_models/test_device.py`:

```python
# Add to end of tests/test_models/test_device.py

class TestDevicePool:
    """DevicePool 模型测试。"""

    def test_create_pool_minimal(self, db_session):
        """测试创建最小设备池。"""
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        pool = DevicePool(name="test_pool", purpose=PoolPurpose.STABLE)
        db_session.add(pool)
        db_session.commit()

        assert pool.id is not None
        assert pool.name == "test_pool"
        assert pool.purpose == PoolPurpose.STABLE
        assert pool.reserved_ratio == 0.2  # 默认值
        assert pool.max_parallel == 5      # 默认值
        assert pool.enabled is True

    def test_create_pool_full(self, db_session):
        """测试创建完整设备池。"""
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        pool = DevicePool(
            name="emergency_pool",
            purpose=PoolPurpose.EMERGENCY,
            reserved_ratio=0.5,
            max_parallel=2,
            tag_selector={"tags": ["critical"]},
            enabled=True,
        )
        db_session.add(pool)
        db_session.commit()

        assert pool.reserved_ratio == 0.5
        assert pool.max_parallel == 2
        assert pool.get_tag_selector() == {"tags": ["critical"]}

    def test_pool_unique_name(self, db_session):
        """测试设备池名称唯一约束。"""
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        pool1 = DevicePool(name="unique_pool", purpose=PoolPurpose.STABLE)
        pool2 = DevicePool(name="unique_pool", purpose=PoolPurpose.STRESS)
        db_session.add(pool1)
        db_session.commit()

        db_session.add(pool2)
        with pytest.raises(Exception):
            db_session.commit()

    def test_pool_device_relationship(self, db_session):
        """测试设备池与设备的关联。"""
        from app.models.device import DevicePool, Device
        from app.models.enums import PoolPurpose

        pool = DevicePool(name="device_pool", purpose=PoolPurpose.STABLE)
        db_session.add(pool)
        db_session.commit()

        device1 = Device(serial="POOL001", pool_id=pool.id)
        device2 = Device(serial="POOL002", pool_id=pool.id)
        db_session.add_all([device1, device2])
        db_session.commit()

        db_session.refresh(pool)
        assert len(pool.devices) == 2
        assert device1.pool == pool

    def test_pool_tag_selector_methods(self, db_session):
        """测试设备池标签选择器方法。"""
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        pool = DevicePool(name="tag_pool", purpose=PoolPurpose.STABLE)
        pool.set_tag_selector({"tags": ["samsung", "stable"], "brand": "Samsung"})
        db_session.add(pool)
        db_session.commit()

        assert pool.get_tag_selector() == {"tags": ["samsung", "stable"], "brand": "Samsung"}

    def test_pool_available_capacity(self, db_session):
        """测试设备池可用容量计算。"""
        from app.models.device import DevicePool, Device
        from app.models.enums import PoolPurpose

        pool = DevicePool(name="capacity_pool", purpose=PoolPurpose.STABLE, max_parallel=10)
        db_session.add(pool)
        db_session.commit()

        # 添加设备
        devices = [
            Device(serial=f"CAP{i:03d}", pool_id=pool.id, status=DeviceStatus.IDLE)
            for i in range(8)
        ]
        db_session.add_all(devices)
        db_session.commit()

        db_session.refresh(pool)
        assert pool.get_available_count() == 8
        assert pool.get_capacity() == 10


class TestDeviceExtensions:
    """Device 模型扩展测试。"""

    def test_device_pool_id(self, db_session):
        """测试设备池 ID 字段。"""
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        pool = DevicePool(name="ext_pool", purpose=PoolPurpose.STABLE)
        db_session.add(pool)
        db_session.commit()

        device = Device(serial="EXT001", pool_id=pool.id)
        db_session.add(device)
        db_session.commit()

        assert device.pool_id == pool.id
        assert device.pool.name == "ext_pool"

    def test_device_sync_failure_count(self, db_session):
        """测试同步失败计数字段。"""
        device = Device(serial="SYNC001", sync_failure_count=3)
        db_session.add(device)
        db_session.commit()

        assert device.sync_failure_count == 3
        # 默认值为 0
        device2 = Device(serial="SYNC002")
        db_session.add(device2)
        db_session.commit()
        assert device2.sync_failure_count == 0

    def test_device_health_score_int(self, db_session):
        """测试健康评分为整数类型。"""
        device = Device(serial="HEALTH001", health_score=85)
        db_session.add(device)
        db_session.commit()

        assert device.health_score == 85
        assert isinstance(device.health_score, int)

    def test_device_reserved_status(self, db_session):
        """测试设备 RESERVED 状态。"""
        from app.models.enums import DeviceStatus

        device = Device(serial="RESERVED001", status=DeviceStatus.RESERVED)
        db_session.add(device)
        db_session.commit()

        assert device.status == DeviceStatus.RESERVED
        # RESERVED 状态的设备不可用
        assert device.is_available() is False


class TestDeviceLeaseExtensions:
    """DeviceLease 模型扩展测试。"""

    def test_lease_preemptible(self, db_session):
        """测试租约可抢占字段。"""
        device = Device(serial="PREEMPT001")
        db_session.add(device)
        db_session.commit()

        lease = DeviceLease(device_id=device.id, preemptible=True)
        db_session.add(lease)
        db_session.commit()

        assert lease.preemptible is True
        # 默认值为 False
        lease2 = DeviceLease(device_id=device.id)
        db_session.add(lease2)
        db_session.commit()
        assert lease2.preemptible is False

    def test_lease_preemption_info(self, db_session):
        """测试租约抢占信息。"""
        from datetime import datetime, timezone

        device = Device(serial="PREEMPT002")
        db_session.add(device)
        db_session.commit()

        lease = DeviceLease(
            device_id=device.id,
            preempted_at=datetime.now(timezone.utc),
            preempted_by_run_id=123,
        )
        db_session.add(lease)
        db_session.commit()

        assert lease.preempted_at is not None
        assert lease.preempted_by_run_id == 123
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_models/test_device.py::TestDevicePool -v`
Expected: FAIL with "ImportError: cannot import name 'DevicePool' from 'app.models.device'"

- [ ] **Step 3: Write the implementation**

Update `app/models/device.py`:

```python
"""设备相关数据模型。"""

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    JSON,
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
    devices: Mapped[List["Device"]] = relationship(
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
        """获取可用设备数量。"""
        return sum(1 for d in self.devices if d.status == DeviceStatus.IDLE)

    def get_capacity(self) -> int:
        """获取池容量。"""
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

    # 设备池关联
    pool_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("device_pools.id", ondelete="SET NULL"), nullable=True
    )

    # 标签（JSON 存储）
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 同步失败计数
    sync_failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

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
    leases: Mapped[List["DeviceLease"]] = relationship(
        "DeviceLease", back_populates="device", cascade="all, delete-orphan"
    )
    run_sessions: Mapped[List["RunSession"]] = relationship(
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
            expired = self.expired_at
            if expired.tzinfo is None:
                expired = expired.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expired:
                return False
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_models/test_device.py -v`
Expected: PASS (all tests including new ones)

- [ ] **Step 5: Commit**

```bash
cd E:/git_repositories/AegisOTA
git add app/models/device.py tests/test_models/test_device.py
git commit -m "feat: add DevicePool model and extend Device with pool_id, sync_failure_count"
```

---

## Task 3: Extend RunSession Model with Priority and Pool

**Files:**
- Modify: `app/models/run.py`
- Modify: `tests/test_models/test_run.py`

- [ ] **Step 1: Write the failing test for RunSession extensions**

Add to `tests/test_models/test_run.py`:

```python
# Add to end of tests/test_models/test_run.py

class TestRunSessionExtensions:
    """RunSession 模型扩展测试。"""

    def test_run_priority(self, db_session):
        """测试任务优先级字段。"""
        from app.models.run import RunSession
        from app.models.enums import RunPriority

        run = RunSession(priority=RunPriority.HIGH)
        db_session.add(run)
        db_session.commit()

        assert run.priority == RunPriority.HIGH
        # 默认值为 NORMAL
        run2 = RunSession()
        db_session.add(run2)
        db_session.commit()
        assert run2.priority == RunPriority.NORMAL

    def test_run_pool_id(self, db_session):
        """测试任务设备池字段。"""
        from app.models.run import RunSession
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        pool = DevicePool(name="run_pool", purpose=PoolPurpose.STABLE)
        db_session.add(pool)
        db_session.commit()

        run = RunSession(pool_id=pool.id)
        db_session.add(run)
        db_session.commit()

        assert run.pool_id == pool.id

    def test_run_preemptible(self, db_session):
        """测试任务可抢占字段。"""
        from app.models.run import RunSession

        run = RunSession(preemptible=True)
        db_session.add(run)
        db_session.commit()

        assert run.preemptible is True
        # 默认值为 True（可被抢占）
        run2 = RunSession()
        db_session.add(run2)
        db_session.commit()
        assert run2.preemptible is True

    def test_run_drill_id(self, db_session):
        """测试任务关联演练字段。"""
        from app.models.run import RunSession

        run = RunSession(drill_id=42)
        db_session.add(run)
        db_session.commit()

        assert run.drill_id == 42

    def test_run_status_new_states(self, db_session):
        """测试任务新状态。"""
        from app.models.run import RunSession, RunStatus
        from app.models.enums import RunStatus as RS

        # 测试 ALLOCATING 状态
        run1 = RunSession(status=RS.ALLOCATING)
        db_session.add(run1)
        db_session.commit()
        assert run1.status == RS.ALLOCATING

        # 测试 PREEMPTED 状态
        run2 = RunSession(status=RS.PREEMPTED)
        db_session.add(run2)
        db_session.commit()
        assert run2.status == RS.PREEMPTED


class TestRunStatusExtensions:
    """RunStatus 枚举扩展测试。"""

    def test_allocating_status(self):
        """测试 ALLOCATING 状态。"""
        from app.models.enums import RunStatus

        assert RunStatus.ALLOCATING == "allocating"

    def test_preempted_status(self):
        """测试 PREEMPTED 状态。"""
        from app.models.enums import RunStatus

        assert RunStatus.PREEMPTED == "preempted"

    def test_no_quarantined_status(self):
        """测试没有 QUARANTINED 状态。"""
        from app.models.enums import RunStatus

        assert not hasattr(RunStatus, 'QUARANTINED')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_models/test_run.py::TestRunSessionExtensions -v`
Expected: FAIL with "AttributeError: type object 'RunSession' has no attribute 'priority'"

- [ ] **Step 3: Write the implementation**

Update `app/models/run.py` to add new fields and import enums from the new location:

```python
# Update imports at top of app/models/run.py
# Change:
# class RunStatus(str, Enum):
#     ...
# To import from enums:
from app.models.enums import RunPriority, RunStatus as RS

# Also need to keep RunStatus for backward compatibility, so rename the import:
```

Full update for `app/models/run.py`:

```python
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
    Boolean,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RunPriority, RunStatus
from app.models.fault import FaultProfile

if TYPE_CHECKING:
    from app.models.artifact import Artifact


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
    source_build: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    target_build: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # 配置关联
    fault_profile_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("fault_profiles.id", ondelete="SET NULL"), nullable=True
    )
    validation_profile_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 默认设备池
    default_pool_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 设备选择器（JSON 存储）
    device_selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 执行配置
    parallelism: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enable_cycle_test: Mapped[bool] = mapped_column(default=False, nullable=False)

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

    # 优先级和设备池
    priority: Mapped[RunPriority] = mapped_column(
        String(16), default=RunPriority.NORMAL, nullable=False, index=True
    )
    pool_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    preemptible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    drill_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 状态与结果
    status: Mapped[RunStatus] = mapped_column(
        String(32), default=RunStatus.QUEUED, nullable=False, index=True
    )
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_category: Mapped[Optional[FailureCategory]] = mapped_column(
        String(32), nullable=True
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 任务选项（JSON 存储）
    run_options: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 压力测试追踪
    current_iteration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_iterations: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # 父任务关联（用于压力测试子任务）
    parent_run_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("run_sessions.id", ondelete="SET NULL"), nullable=True
    )

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
            RunStatus.PREEMPTED,
        )

    def get_run_options(self) -> dict[str, Any]:
        """获取任务选项配置。"""
        if not self.run_options:
            return {}
        try:
            return json.loads(self.run_options)
        except json.JSONDecodeError:
            return {}

    def set_run_options(self, options: dict[str, Any]) -> None:
        """设置任务选项配置。"""
        self.run_options = json.dumps(options) if options else None


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_models/test_run.py -v`
Expected: PASS (all tests including new ones)

- [ ] **Step 5: Commit**

```bash
cd E:/git_repositories/AegisOTA
git add app/models/run.py tests/test_models/test_run.py
git commit -m "feat: extend RunSession with priority, pool_id, preemptible, drill_id"
```

---

## Task 4: Update Config with Pool Settings

**Files:**
- Modify: `app/config.py`
- Modify: `tests/test_models/test_config.py`

- [ ] **Step 1: Write the failing test for new config**

Add to `tests/test_models/test_config.py`:

```python
# Add to end of tests/test_models/test_config.py

class TestPoolConfig:
    """设备池配置测试。"""

    def test_pool_config_defaults(self):
        """测试设备池配置默认值。"""
        from app.config import Settings

        settings = Settings()

        assert settings.MAX_DEVICES_PER_POOL == 100
        assert settings.DEFAULT_POOL_RESERVED_RATIO == 0.2
        assert settings.SCHEDULER_INTERVAL_SEC == 5
        assert settings.MAX_QUEUED_RUNS == 1000
        assert settings.PREEMPTION_CHECK_INTERVAL == 10
        assert settings.ENABLE_DEVICE_POOL is True

    def test_pool_config_from_env(self, monkeypatch):
        """测试从环境变量读取配置。"""
        monkeypatch.setenv("AEGISOTA_MAX_DEVICES_PER_POOL", "200")
        monkeypatch.setenv("AEGISOTA_ENABLE_DEVICE_POOL", "false")

        from app.config import Settings, clear_settings_cache
        clear_settings_cache()
        settings = Settings()

        assert settings.MAX_DEVICES_PER_POOL == 200
        assert settings.ENABLE_DEVICE_POOL is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_models/test_config.py::TestPoolConfig -v`
Expected: FAIL with "AttributeError: 'Settings' object has no attribute 'MAX_DEVICES_PER_POOL'"

- [ ] **Step 3: Write the implementation**

Update `app/config.py`:

```python
"""配置管理模块。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    APP_NAME: str = "AegisOTA"
    DEBUG: bool = False
    DATABASE_URL: str = "sqlite:///./aegisota.db"
    ARTIFACTS_DIR: Path = Path("artifacts")

    # 设备管理配置
    DEVICE_SYNC_INTERVAL: int = 60
    DEVICE_HEALTH_CHECK_INTERVAL: int = 30

    # 任务执行配置
    DEFAULT_TIMEOUT: int = 300
    REBOOT_WAIT_TIMEOUT: int = 120
    BOOT_COMPLETE_TIMEOUT: int = 90

    # Monkey 配置
    MONKEY_DEFAULT_COUNT: int = 1000
    MONKEY_THROTTLE: int = 50

    # 调度配置
    MAX_CONCURRENT_RUNS: int = 5
    LEASE_DEFAULT_DURATION: int = 3600
    SCHEDULER_INTERVAL_SEC: int = 5
    MAX_QUEUED_RUNS: int = 1000
    PREEMPTION_CHECK_INTERVAL: int = 10

    # 设备池配置
    ENABLE_DEVICE_POOL: bool = True
    MAX_DEVICES_PER_POOL: int = 100
    DEFAULT_POOL_RESERVED_RATIO: float = 0.2

    # 升级包配置
    OTA_PACKAGES_DIR: Path = Path("ota_packages")
    FULL_PACKAGE_SUBDIR: str = "full"
    INCREMENTAL_PACKAGE_SUBDIR: str = "incremental"

    model_config = SettingsConfigDict(
        env_prefix="AEGISOTA_",
        env_file=".env",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        self.OTA_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
        (self.OTA_PACKAGES_DIR / self.FULL_PACKAGE_SUBDIR).mkdir(parents=True, exist_ok=True)
        (self.OTA_PACKAGES_DIR / self.INCREMENTAL_PACKAGE_SUBDIR).mkdir(parents=True, exist_ok=True)

    def get_full_package_path(self) -> Path:
        """获取全量包目录路径。"""
        return self.OTA_PACKAGES_DIR / self.FULL_PACKAGE_SUBDIR

    def get_incremental_package_path(self) -> Path:
        """获取差分包目录路径。"""
        return self.OTA_PACKAGES_DIR / self.INCREMENTAL_PACKAGE_SUBDIR


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（缓存）。"""
    return Settings()


def clear_settings_cache() -> None:
    """清除配置缓存。"""
    get_settings.cache_clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_models/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd E:/git_repositories/AegisOTA
git add app/config.py tests/test_models/test_config.py
git commit -m "feat: add device pool configuration parameters"
```

---

## Task 5: Implement PoolService

**Files:**
- Create: `app/services/pool_service.py`
- Create: `tests/test_services/test_pool_service.py`

- [ ] **Step 1: Write the failing test for PoolService**

```python
# tests/test_services/test_pool_service.py
"""设备池服务测试。"""

import pytest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DevicePool, DeviceStatus, DeviceLease
from app.models.enums import PoolPurpose
from app.services.pool_service import PoolService


@pytest.fixture
def db_engine():
    """创建测试数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """创建测试数据库会话。"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


class TestPoolServiceCreation:
    """PoolService 创建测试。"""

    def test_create_pool_minimal(self, db_session):
        """测试创建最小设备池。"""
        service = PoolService(db_session)
        pool = service.create_pool(name="test_pool", purpose=PoolPurpose.STABLE)

        assert pool.id is not None
        assert pool.name == "test_pool"
        assert pool.purpose == PoolPurpose.STABLE
        assert pool.reserved_ratio == 0.2
        assert pool.enabled is True

    def test_create_pool_full(self, db_session):
        """测试创建完整设备池。"""
        service = PoolService(db_session)
        pool = service.create_pool(
            name="emergency_pool",
            purpose=PoolPurpose.EMERGENCY,
            reserved_ratio=0.5,
            max_parallel=2,
            tag_selector={"tags": ["critical"]},
        )

        assert pool.reserved_ratio == 0.5
        assert pool.max_parallel == 2
        assert pool.get_tag_selector() == {"tags": ["critical"]}

    def test_create_pool_duplicate_name(self, db_session):
        """测试创建重复名称设备池。"""
        service = PoolService(db_session)
        service.create_pool(name="duplicate", purpose=PoolPurpose.STABLE)

        with pytest.raises(ValueError, match="already exists"):
            service.create_pool(name="duplicate", purpose=PoolPurpose.STRESS)


class TestPoolServiceQuery:
    """PoolService 查询测试。"""

    def test_get_pool_by_id(self, db_session):
        """测试通过 ID 获取设备池。"""
        service = PoolService(db_session)
        created = service.create_pool(name="query_pool", purpose=PoolPurpose.STABLE)

        pool = service.get_pool_by_id(created.id)
        assert pool is not None
        assert pool.name == "query_pool"

    def test_get_pool_by_name(self, db_session):
        """测试通过名称获取设备池。"""
        service = PoolService(db_session)
        service.create_pool(name="name_pool", purpose=PoolPurpose.STABLE)

        pool = service.get_pool_by_name("name_pool")
        assert pool is not None
        assert pool.name == "name_pool"

    def test_get_pool_by_name_not_found(self, db_session):
        """测试获取不存在的设备池。"""
        service = PoolService(db_session)
        pool = service.get_pool_by_name("nonexistent")
        assert pool is None

    def test_list_pools(self, db_session):
        """测试列出设备池。"""
        service = PoolService(db_session)
        service.create_pool(name="pool1", purpose=PoolPurpose.STABLE)
        service.create_pool(name="pool2", purpose=PoolPurpose.STRESS)
        service.create_pool(name="pool3", purpose=PoolPurpose.EMERGENCY)

        pools = service.list_pools()
        assert len(pools) == 3

    def test_list_pools_by_purpose(self, db_session):
        """测试按用途列出设备池。"""
        service = PoolService(db_session)
        service.create_pool(name="stable1", purpose=PoolPurpose.STABLE)
        service.create_pool(name="stable2", purpose=PoolPurpose.STABLE)
        service.create_pool(name="stress1", purpose=PoolPurpose.STRESS)

        pools = service.list_pools(purpose=PoolPurpose.STABLE)
        assert len(pools) == 2


class TestPoolServiceUpdate:
    """PoolService 更新测试。"""

    def test_update_pool_config(self, db_session):
        """测试更新设备池配置。"""
        service = PoolService(db_session)
        pool = service.create_pool(name="update_pool", purpose=PoolPurpose.STABLE)

        updated = service.update_pool(pool.id, reserved_ratio=0.3, max_parallel=10)
        assert updated.reserved_ratio == 0.3
        assert updated.max_parallel == 10

    def test_update_pool_tag_selector(self, db_session):
        """测试更新设备池标签选择器。"""
        service = PoolService(db_session)
        pool = service.create_pool(name="tag_pool", purpose=PoolPurpose.STABLE)

        updated = service.update_pool(pool.id, tag_selector={"brand": "Samsung"})
        assert updated.get_tag_selector() == {"brand": "Samsung"}

    def test_update_pool_enable_disable(self, db_session):
        """测试启用/禁用设备池。"""
        service = PoolService(db_session)
        pool = service.create_pool(name="toggle_pool", purpose=PoolPurpose.STABLE)

        disabled = service.update_pool(pool.id, enabled=False)
        assert disabled.enabled is False

        enabled = service.update_pool(pool.id, enabled=True)
        assert enabled.enabled is True


class TestPoolServiceDeviceAssignment:
    """PoolService 设备分配测试。"""

    def test_assign_device_to_pool(self, db_session):
        """测试分配设备到池。"""
        service = PoolService(db_session)
        pool = service.create_pool(name="assign_pool", purpose=PoolPurpose.STABLE)

        device = Device(serial="ASSIGN001", status=DeviceStatus.IDLE)
        db_session.add(device)
        db_session.commit()

        service.assign_device_to_pool(device.id, pool.id)
        db_session.refresh(device)

        assert device.pool_id == pool.id
        assert device in pool.devices

    def test_assign_device_change_pool(self, db_session):
        """测试更改设备的池。"""
        service = PoolService(db_session)
        pool1 = service.create_pool(name="pool1", purpose=PoolPurpose.STABLE)
        pool2 = service.create_pool(name="pool2", purpose=PoolPurpose.STRESS)

        device = Device(serial="CHANGE001", pool_id=pool1.id)
        db_session.add(device)
        db_session.commit()

        service.assign_device_to_pool(device.id, pool2.id)
        db_session.refresh(device)

        assert device.pool_id == pool2.id

    def test_remove_device_from_pool(self, db_session):
        """测试从池中移除设备。"""
        service = PoolService(db_session)
        pool = service.create_pool(name="remove_pool", purpose=PoolPurpose.STABLE)

        device = Device(serial="REMOVE001", pool_id=pool.id)
        db_session.add(device)
        db_session.commit()

        service.remove_device_from_pool(device.id)
        db_session.refresh(device)

        assert device.pool_id is None


class TestPoolServiceCapacity:
    """PoolService 容量计算测试。"""

    def test_get_pool_capacity(self, db_session):
        """测试获取池容量。"""
        service = PoolService(db_session)
        pool = service.create_pool(
            name="capacity_pool",
            purpose=PoolPurpose.STABLE,
            max_parallel=10,
        )

        # 添加设备
        for i in range(8):
            device = Device(serial=f"CAP{i:03d}", pool_id=pool.id, status=DeviceStatus.IDLE)
            db_session.add(device)
        db_session.commit()

        capacity = service.get_pool_capacity(pool.id)
        assert capacity["total"] == 8
        assert capacity["max_parallel"] == 10
        assert capacity["available"] == 8

    def test_get_pool_capacity_with_busy_devices(self, db_session):
        """测试包含忙碌设备的池容量。"""
        service = PoolService(db_session)
        pool = service.create_pool(
            name="busy_pool",
            purpose=PoolPurpose.STABLE,
            max_parallel=10,
        )

        # 添加不同状态的设备
        for i in range(5):
            device = Device(serial=f"IDLE{i:03d}", pool_id=pool.id, status=DeviceStatus.IDLE)
            db_session.add(device)
        for i in range(3):
            device = Device(serial=f"BUSY{i:03d}", pool_id=pool.id, status=DeviceStatus.BUSY)
            db_session.add(device)
        db_session.commit()

        capacity = service.get_pool_capacity(pool.id)
        assert capacity["total"] == 8
        assert capacity["available"] == 5
        assert capacity["busy"] == 3

    def test_get_pool_reserved_capacity(self, db_session):
        """测试获取池保留容量。"""
        service = PoolService(db_session)
        pool = service.create_pool(
            name="reserved_pool",
            purpose=PoolPurpose.EMERGENCY,
            reserved_ratio=0.5,
            max_parallel=10,
        )

        # 添加 10 台设备
        for i in range(10):
            device = Device(serial=f"RES{i:03d}", pool_id=pool.id, status=DeviceStatus.IDLE)
            db_session.add(device)
        db_session.commit()

        capacity = service.get_pool_capacity(pool.id)
        # 保留 50%，即 5 台
        assert capacity["reserved"] == 5
        assert capacity["usable"] == 5


class TestPoolServiceTagMatching:
    """PoolService 标签匹配测试。"""

    def test_match_device_by_pool_tags(self, db_session):
        """测试通过池标签匹配设备。"""
        service = PoolService(db_session)
        pool = service.create_pool(
            name="tag_match_pool",
            purpose=PoolPurpose.STABLE,
            tag_selector={"tags": ["samsung"]},
        )

        # 添加设备
        device1 = Device(serial="SAM001", status=DeviceStatus.IDLE)
        device1.set_tags(["samsung", "stable"])
        device2 = Device(serial="XIAO001", status=DeviceStatus.IDLE)
        device2.set_tags(["xiaomi", "stable"])
        db_session.add_all([device1, device2])
        db_session.commit()

        matched = service.match_devices_for_pool(pool.id)
        assert len(matched) == 1
        assert matched[0].serial == "SAM001"

    def test_match_device_by_brand(self, db_session):
        """测试通过品牌匹配设备。"""
        service = PoolService(db_session)
        pool = service.create_pool(
            name="brand_pool",
            purpose=PoolPurpose.STABLE,
            tag_selector={"brand": "Samsung"},
        )

        device1 = Device(serial="BRAND001", brand="Samsung", status=DeviceStatus.IDLE)
        device2 = Device(serial="BRAND002", brand="Xiaomi", status=DeviceStatus.IDLE)
        db_session.add_all([device1, device2])
        db_session.commit()

        matched = service.match_devices_for_pool(pool.id)
        assert len(matched) == 1
        assert matched[0].serial == "BRAND001"


class TestPoolServiceDefaultPools:
    """PoolService 默认池测试。"""

    def test_create_default_pools(self, db_session):
        """测试创建默认设备池。"""
        service = PoolService(db_session)
        pools = service.create_default_pools()

        assert len(pools) == 3
        names = [p.name for p in pools]
        assert "stable_pool" in names
        assert "stress_pool" in names
        assert "emergency_pool" in names

        # 验证配置
        stable = service.get_pool_by_name("stable_pool")
        assert stable.purpose == PoolPurpose.STABLE
        assert stable.reserved_ratio == 0.1

        emergency = service.get_pool_by_name("emergency_pool")
        assert emergency.purpose == PoolPurpose.EMERGENCY
        assert emergency.reserved_ratio == 0.5

    def test_create_default_pools_idempotent(self, db_session):
        """测试创建默认池是幂等的。"""
        service = PoolService(db_session)

        # 第一次创建
        pools1 = service.create_default_pools()
        assert len(pools1) == 3

        # 第二次创建应该不产生新池
        pools2 = service.create_default_pools()
        assert len(pools2) == 3  # 返回已存在的池

        all_pools = service.list_pools()
        assert len(all_pools) == 3  # 没有重复
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_services/test_pool_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.pool_service'"

- [ ] **Step 3: Write the implementation**

```python
# app/services/pool_service.py
"""设备池管理服务。"""

from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.device import Device, DevicePool, DeviceStatus
from app.models.enums import PoolPurpose


class PoolService:
    """设备池管理服务。"""

    def __init__(self, db: Session):
        self.db = db

    def create_pool(
        self,
        name: str,
        purpose: PoolPurpose,
        reserved_ratio: float = 0.2,
        max_parallel: int = 5,
        tag_selector: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ) -> DevicePool:
        """创建设备池。"""
        # 检查名称是否已存在
        existing = self.get_pool_by_name(name)
        if existing:
            raise ValueError(f"Pool with name '{name}' already exists")

        pool = DevicePool(
            name=name,
            purpose=purpose,
            reserved_ratio=reserved_ratio,
            max_parallel=max_parallel,
            enabled=enabled,
        )
        if tag_selector:
            pool.set_tag_selector(tag_selector)

        self.db.add(pool)
        self.db.commit()
        self.db.refresh(pool)
        return pool

    def get_pool_by_id(self, pool_id: int) -> Optional[DevicePool]:
        """通过 ID 获取设备池。"""
        return self.db.query(DevicePool).filter_by(id=pool_id).first()

    def get_pool_by_name(self, name: str) -> Optional[DevicePool]:
        """通过名称获取设备池。"""
        return self.db.query(DevicePool).filter_by(name=name).first()

    def list_pools(
        self,
        purpose: Optional[PoolPurpose] = None,
        enabled_only: bool = False,
    ) -> List[DevicePool]:
        """列出设备池。"""
        query = self.db.query(DevicePool)

        if purpose:
            query = query.filter(DevicePool.purpose == purpose)

        if enabled_only:
            query = query.filter(DevicePool.enabled == True)

        return query.all()

    def update_pool(
        self,
        pool_id: int,
        **kwargs,
    ) -> Optional[DevicePool]:
        """更新设备池配置。"""
        pool = self.get_pool_by_id(pool_id)
        if not pool:
            return None

        # 允许更新的字段
        updatable_fields = [
            "reserved_ratio",
            "max_parallel",
            "tag_selector",
            "enabled",
        ]

        for key, value in kwargs.items():
            if key in updatable_fields:
                if key == "tag_selector":
                    pool.set_tag_selector(value)
                else:
                    setattr(pool, key, value)

        self.db.commit()
        self.db.refresh(pool)
        return pool

    def delete_pool(self, pool_id: int) -> bool:
        """删除设备池。"""
        pool = self.get_pool_by_id(pool_id)
        if not pool:
            return False

        # 解除设备关联
        devices = self.db.query(Device).filter_by(pool_id=pool_id).all()
        for device in devices:
            device.pool_id = None

        self.db.delete(pool)
        self.db.commit()
        return True

    def assign_device_to_pool(self, device_id: int, pool_id: int) -> Optional[Device]:
        """分配设备到池。"""
        device = self.db.query(Device).filter_by(id=device_id).first()
        if not device:
            return None

        pool = self.get_pool_by_id(pool_id)
        if not pool:
            return None

        device.pool_id = pool_id
        self.db.commit()
        self.db.refresh(device)
        return device

    def remove_device_from_pool(self, device_id: int) -> Optional[Device]:
        """从池中移除设备。"""
        device = self.db.query(Device).filter_by(id=device_id).first()
        if not device:
            return None

        device.pool_id = None
        self.db.commit()
        self.db.refresh(device)
        return device

    def get_pool_capacity(self, pool_id: int) -> Dict[str, int]:
        """获取池容量信息。"""
        pool = self.get_pool_by_id(pool_id)
        if not pool:
            return {}

        devices = self.db.query(Device).filter_by(pool_id=pool_id).all()

        total = len(devices)
        available = sum(1 for d in devices if d.status == DeviceStatus.IDLE)
        busy = sum(1 for d in devices if d.status == DeviceStatus.BUSY)
        offline = sum(1 for d in devices if d.status == DeviceStatus.OFFLINE)
        quarantined = sum(1 for d in devices if d.status == DeviceStatus.QUARANTINED)

        # 计算保留容量
        reserved = int(pool.max_parallel * pool.reserved_ratio)
        usable = max(0, pool.max_parallel - reserved)

        return {
            "total": total,
            "available": available,
            "busy": busy,
            "offline": offline,
            "quarantined": quarantined,
            "max_parallel": pool.max_parallel,
            "reserved": reserved,
            "usable": usable,
        }

    def match_devices_for_pool(self, pool_id: int) -> List[Device]:
        """匹配适合该池的设备。"""
        pool = self.get_pool_by_id(pool_id)
        if not pool:
            return []

        selector = pool.get_tag_selector()
        if not selector:
            return []

        query = self.db.query(Device).filter(Device.status == DeviceStatus.IDLE)

        # 按标签匹配
        if "tags" in selector:
            required_tags = selector["tags"]
            devices = query.all()
            matched = []
            for device in devices:
                device_tags = device.get_tags()
                if any(tag in device_tags for tag in required_tags):
                    matched.append(device)
            return matched

        # 按品牌匹配
        if "brand" in selector:
            return query.filter(Device.brand == selector["brand"]).all()

        return query.all()

    def create_default_pools(self) -> List[DevicePool]:
        """创建默认设备池。"""
        default_configs = [
            {
                "name": "stable_pool",
                "purpose": PoolPurpose.STABLE,
                "reserved_ratio": 0.1,
                "max_parallel": 5,
            },
            {
                "name": "stress_pool",
                "purpose": PoolPurpose.STRESS,
                "reserved_ratio": 0.2,
                "max_parallel": 3,
            },
            {
                "name": "emergency_pool",
                "purpose": PoolPurpose.EMERGENCY,
                "reserved_ratio": 0.5,
                "max_parallel": 2,
            },
        ]

        pools = []
        for config in default_configs:
            existing = self.get_pool_by_name(config["name"])
            if existing:
                pools.append(existing)
            else:
                pool = self.create_pool(**config)
                pools.append(pool)

        return pools
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_services/test_pool_service.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
cd E:/git_repositories/AegisOTA
git add app/services/pool_service.py tests/test_services/test_pool_service.py
git commit -m "feat: implement PoolService with CRUD, capacity, and tag matching"
```

---

## Task 6: Extend SchedulerService with Priority Scheduling

**Files:**
- Modify: `app/services/scheduler_service.py`
- Modify: `tests/test_services/test_scheduler_service.py`

- [ ] **Step 1: Write the failing test for priority scheduling**

Add to `tests/test_services/test_scheduler_service.py`:

```python
# Add to end of tests/test_services/test_scheduler_service.py

class TestPriorityScheduling:
    """优先级调度测试。"""

    def test_schedule_highest_priority_first(self, db_session):
        """测试高优先级任务优先调度。"""
        from app.models.run import RunSession, UpgradePlan
        from app.models.enums import RunPriority, RunStatus
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        # 创建设备池和设备
        pool = DevicePool(name="priority_pool", purpose=PoolPurpose.STABLE)
        db_session.add(pool)
        device = Device(serial="PRIO001", status=DeviceStatus.IDLE, pool_id=pool.id)
        db_session.add(device)

        # 创建升级计划
        plan = UpgradePlan(name="Priority Test Plan")
        db_session.add(plan)
        db_session.commit()

        # 创建不同优先级的任务
        run_normal = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
        run_high = RunSession(plan_id=plan.id, priority=RunPriority.HIGH, pool_id=pool.id)
        run_emergency = RunSession(plan_id=plan.id, priority=RunPriority.EMERGENCY, pool_id=pool.id)
        db_session.add_all([run_normal, run_high, run_emergency])
        db_session.commit()

        # 调度任务
        service = SchedulerService(db_session)
        next_run = service.get_next_run_to_schedule(pool_id=pool.id)

        assert next_run is not None
        assert next_run.priority == RunPriority.EMERGENCY

    def test_schedule_fifo_same_priority(self, db_session):
        """测试相同优先级按 FIFO 调度。"""
        from app.models.run import RunSession, UpgradePlan
        from app.models.enums import RunPriority
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        pool = DevicePool(name="fifo_pool", purpose=PoolPurpose.STABLE)
        db_session.add(pool)
        device = Device(serial="FIFO001", status=DeviceStatus.IDLE, pool_id=pool.id)
        db_session.add(device)

        plan = UpgradePlan(name="FIFO Test Plan")
        db_session.add(plan)
        db_session.commit()

        # 创建相同优先级的任务
        run1 = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
        run2 = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
        run3 = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
        db_session.add_all([run1, run2, run3])
        db_session.commit()

        service = SchedulerService(db_session)
        next_run = service.get_next_run_to_schedule(pool_id=pool.id)

        assert next_run.id == run1.id

    def test_allocate_from_pool(self, db_session):
        """测试从设备池分配设备。"""
        from app.models.run import RunSession, UpgradePlan
        from app.models.enums import RunPriority, RunStatus
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        pool = DevicePool(name="alloc_pool", purpose=PoolPurpose.STABLE, max_parallel=5)
        db_session.add(pool)

        # 添加设备
        for i in range(3):
            device = Device(serial=f"ALLOC{i:03d}", status=DeviceStatus.IDLE, pool_id=pool.id)
            db_session.add(device)
        db_session.commit()

        plan = UpgradePlan(name="Alloc Test Plan")
        db_session.add(plan)
        db_session.commit()

        run = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
        db_session.add(run)
        db_session.commit()

        service = SchedulerService(db_session)
        allocated = service.allocate_device_for_run(run.id)

        assert allocated is not None
        assert allocated.pool_id == pool.id

        # 检查任务状态变为 ALLOCATING
        db_session.refresh(run)
        assert run.status == RunStatus.ALLOCATING

    def test_allocate_respects_reserved_capacity(self, db_session):
        """测试分配设备时保留容量。"""
        from app.models.run import RunSession, UpgradePlan
        from app.models.enums import RunPriority
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        # 创建保留 50% 的池
        pool = DevicePool(
            name="reserved_pool",
            purpose=PoolPurpose.EMERGENCY,
            reserved_ratio=0.5,
            max_parallel=4,
        )
        db_session.add(pool)

        # 添加 4 台设备
        for i in range(4):
            device = Device(serial=f"RES{i:03d}", status=DeviceStatus.IDLE, pool_id=pool.id)
            db_session.add(device)
        db_session.commit()

        plan = UpgradePlan(name="Reserved Test Plan")
        db_session.add(plan)
        db_session.commit()

        service = SchedulerService(db_session)

        # 普通 priority 任务只能用 2 台（50%）
        runs = []
        for i in range(3):
            run = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
            db_session.add(run)
            runs.append(run)
        db_session.commit()

        # 前两个应该成功分配
        allocated1 = service.allocate_device_for_run(runs[0].id)
        allocated2 = service.allocate_device_for_run(runs[1].id)

        assert allocated1 is not None
        assert allocated2 is not None

        # 第三个普通任务不应该分配（保留容量）
        allocated3 = service.allocate_device_for_run(runs[2].id)
        assert allocated3 is None  # 被保留容量限制


class TestPoolBasedAllocation:
    """基于池的设备分配测试。"""

    def test_select_device_from_pool(self, db_session):
        """测试从指定池选择设备。"""
        from app.models.run import RunSession, UpgradePlan
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        pool = DevicePool(name="select_pool", purpose=PoolPurpose.STABLE)
        db_session.add(pool)

        device = Device(serial="SELECT001", status=DeviceStatus.IDLE, pool_id=pool.id)
        db_session.add(device)
        db_session.commit()

        plan = UpgradePlan(name="Select Test Plan", default_pool_id=pool.id)
        db_session.add(plan)
        db_session.commit()

        run = RunSession(plan_id=plan.id, pool_id=pool.id)
        db_session.add(run)
        db_session.commit()

        service = SchedulerService(db_session)
        selected = service.select_device_for_run(run.id, pool_id=pool.id)

        assert selected is not None
        assert selected.pool_id == pool.id
        assert selected.serial == "SELECT001"

    def test_select_device_respects_pool_boundary(self, db_session):
        """测试设备选择遵守池边界。"""
        from app.models.run import RunSession, UpgradePlan
        from app.models.device import DevicePool
        from app.models.enums import PoolPurpose

        pool1 = DevicePool(name="boundary1", purpose=PoolPurpose.STABLE)
        pool2 = DevicePool(name="boundary2", purpose=PoolPurpose.STRESS)
        db_session.add_all([pool1, pool2])

        # pool1 没有可用设备
        device1 = Device(serial="BOUNDARY001", status=DeviceStatus.BUSY, pool_id=pool1.id)
        # pool2 有可用设备
        device2 = Device(serial="BOUNDARY002", status=DeviceStatus.IDLE, pool_id=pool2.id)
        db_session.add_all([device1, device2])
        db_session.commit()

        plan = UpgradePlan(name="Boundary Test Plan", default_pool_id=pool1.id)
        db_session.add(plan)
        db_session.commit()

        run = RunSession(plan_id=plan.id, pool_id=pool1.id)
        db_session.add(run)
        db_session.commit()

        service = SchedulerService(db_session)
        # 从 pool1 选择设备，应该失败
        selected = service.select_device_for_run(run.id, pool_id=pool1.id)
        assert selected is None  # pool1 没有可用设备

        # 从 pool2 选择设备
        run2 = RunSession(plan_id=plan.id, pool_id=pool2.id)
        db_session.add(run2)
        db_session.commit()

        selected2 = service.select_device_for_run(run2.id, pool_id=pool2.id)
        assert selected2 is not None
        assert selected2.pool_id == pool2.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_services/test_scheduler_service.py::TestPriorityScheduling -v`
Expected: FAIL with "AttributeError: 'SchedulerService' object has no attribute 'get_next_run_to_schedule'"

- [ ] **Step 3: Write the implementation**

Update `app/services/scheduler_service.py`:

```python
"""调度与并发控制服务。"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_, select, desc

from app.config import get_settings
from app.models.device import Device, DeviceLease, DeviceStatus, LeaseStatus
from app.models.run import RunSession, RunStatus, UpgradePlan
from app.models.enums import RunPriority
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
            device = self.db.execute(
                select(Device).where(Device.id == device_id).with_for_update()
            ).scalar_one_or_none()

            if device is None:
                return None

            if device.status != DeviceStatus.IDLE:
                return None

            active_lease = self.db.execute(
                select(DeviceLease).where(
                    DeviceLease.device_id == device_id,
                    DeviceLease.lease_status == LeaseStatus.ACTIVE,
                ).with_for_update()
            ).scalar_one_or_none()

            if active_lease:
                return None

            lease_duration = duration or self.settings.LEASE_DEFAULT_DURATION
            lease = DeviceLease(
                device_id=device_id,
                run_id=run_id,
                lease_status=LeaseStatus.ACTIVE,
                preemptible=preemptible,
                expired_at=datetime.now(timezone.utc) + timedelta(seconds=lease_duration),
            )

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
        """释放设备租约。"""
        try:
            lease = self.db.execute(
                select(DeviceLease).where(
                    DeviceLease.device_id == device_id,
                    DeviceLease.run_id == run_id,
                    DeviceLease.lease_status == LeaseStatus.ACTIVE,
                ).with_for_update()
            ).scalar_one_or_none()

            if not lease:
                return False

            lease.lease_status = LeaseStatus.RELEASED
            lease.released_at = datetime.now(timezone.utc)

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

        # 确定目标池
        target_pool_id = pool_id or run.pool_id or plan.default_pool_id

        # 获取选择条件
        selector = plan.get_device_selector()

        # 构建查询
        query = self.db.query(Device).filter(
            Device.status == DeviceStatus.IDLE,
        )

        # 如果指定了池，只从该池选择
        if target_pool_id:
            query = query.filter(Device.pool_id == target_pool_id)

        devices = query.all()

        # 过滤电量和健康分
        filtered = []
        for device in devices:
            if device.battery_level is not None and device.battery_level < min_battery:
                continue
            if device.health_score < 50:
                continue
            filtered.append(device)

        devices = filtered

        if not devices:
            return None

        # 标签匹配
        if selector.get("tags"):
            tagged = []
            for device in devices:
                device_tags = device.get_tags()
                if any(tag in device_tags for tag in selector["tags"]):
                    tagged.append(device)
            if tagged:
                devices = tagged

        # 品牌匹配
        if selector.get("brand"):
            branded = [d for d in devices if d.brand == selector["brand"]]
            if branded:
                devices = branded

        # 返回健康分最高的设备
        devices.sort(key=lambda d: d.health_score, reverse=True)
        return devices[0] if devices else None

    def get_next_run_to_schedule(
        self,
        pool_id: Optional[int] = None,
    ) -> Optional[RunSession]:
        """获取下一个待调度的任务（按优先级排序）。"""
        query = self.db.query(RunSession).filter(
            RunSession.status == RunStatus.QUEUED,
        )

        if pool_id:
            query = query.filter(RunSession.pool_id == pool_id)

        # 优先级排序：EMERGENCY > HIGH > NORMAL
        priority_order = {
            RunPriority.EMERGENCY: 0,
            RunPriority.HIGH: 1,
            RunPriority.NORMAL: 2,
        }

        runs = query.all()
        if not runs:
            return None

        # 按优先级和创建时间排序
        runs.sort(key=lambda r: (priority_order.get(r.priority, 99), r.created_at))
        return runs[0]

    def allocate_device_for_run(
        self,
        run_id: int,
        min_battery: int = 20,
    ) -> Optional[Device]:
        """为任务分配设备。"""
        run = self.db.query(RunSession).filter_by(id=run_id).first()
        if not run:
            return None

        if run.status != RunStatus.QUEUED:
            return None

        # 检查池容量限制
        if run.pool_id:
            pool_capacity = self.get_pool_available_capacity(run.pool_id)
            if pool_capacity <= 0:
                return None

            # 检查保留容量
            pool = self.db.query(Device).filter_by(id=run.pool_id).first()
            from app.models.device import DevicePool
            pool_obj = self.db.query(DevicePool).filter_by(id=run.pool_id).first()

            if pool_obj and run.priority != RunPriority.EMERGENCY:
                # 非 emergency 任务需要检查保留容量
                used = self.get_pool_used_capacity(run.pool_id)
                usable = int(pool_obj.max_parallel * (1 - pool_obj.reserved_ratio))
                if used >= usable:
                    return None  # 被保留容量限制

        # 选择设备
        device = self.select_device_for_run(run_id, min_battery=min_battery)
        if not device:
            return None

        # 获取租约
        lease = self.acquire_device_lease(
            device.id,
            run_id,
            preemptible=run.preemptible,
        )
        if not lease:
            return None

        # 更新任务状态
        run.status = RunStatus.ALLOCATING
        run.device_id = device.id

        self.db.commit()
        return device

    def get_pool_available_capacity(self, pool_id: int) -> int:
        """获取池可用容量。"""
        from app.models.device import DevicePool

        pool = self.db.query(DevicePool).filter_by(id=pool_id).first()
        if not pool:
            return 0

        available = self.db.query(Device).filter(
            Device.pool_id == pool_id,
            Device.status == DeviceStatus.IDLE,
        ).count()

        return min(available, pool.max_parallel)

    def get_pool_used_capacity(self, pool_id: int) -> int:
        """获取池已用容量。"""
        return self.db.query(Device).filter(
            Device.pool_id == pool_id,
            Device.status.in_([DeviceStatus.RESERVED, DeviceStatus.BUSY]),
        ).count()

    def reserve_run(self, run_id: int) -> bool:
        """预留任务（分配设备并获取租约）。"""
        run = self.db.query(RunSession).filter_by(id=run_id).first()
        if not run:
            return False

        if run.status != RunStatus.QUEUED:
            return False

        # 分配设备
        device = self.allocate_device_for_run(run_id)
        if not device:
            return False

        # 更新任务状态
        run.status = RunStatus.RESERVED

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
                DeviceLease.lease_status == LeaseStatus.ACTIVE,
                DeviceLease.expired_at < datetime.now(timezone.utc)
            )
        ).all()

        for lease in expired_leases:
            lease.lease_status = LeaseStatus.EXPIRED

            device = self.db.query(Device).filter_by(id=lease.device_id).first()
            if device:
                device.status = DeviceStatus.RECOVERING
                device.current_run_id = None

            run = self.db.query(RunSession).filter_by(id=lease.run_id).first()
            if run:
                run.status = RunStatus.FAILED
                run.failure_category = "device_env_issue"

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_services/test_scheduler_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd E:/git_repositories/AegisOTA
git add app/services/scheduler_service.py tests/test_services/test_scheduler_service.py
git commit -m "feat: extend SchedulerService with priority scheduling and pool-based allocation"
```

---

## Task 7: Implement PreemptionService

**Files:**
- Create: `app/services/preemption_service.py`
- Create: `tests/test_services/test_preemption_service.py`

- [ ] **Step 1: Write the failing test for PreemptionService**

```python
# tests/test_services/test_preemption_service.py
"""抢占服务测试。"""

import pytest
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DevicePool, DeviceStatus, DeviceLease
from app.models.run import RunSession, UpgradePlan
from app.models.enums import PoolPurpose, RunPriority, RunStatus, LeaseStatus
from app.services.preemption_service import PreemptionService
from app.services.pool_service import PoolService


@pytest.fixture
def db_engine():
    """创建测试数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """创建测试数据库会话。"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


class TestPreemptionService:
    """抢占服务测试。"""

    def test_find_preemptible_runs(self, db_session):
        """测试查找可抢占的任务。"""
        # 创建设备池和设备
        pool_service = PoolService(db_session)
        pool = pool_service.create_pool(name="preempt_pool", purpose=PoolPurpose.STABLE)

        device = Device(serial="PREEMPT001", status=DeviceStatus.BUSY, pool_id=pool.id)
        db_session.add(device)
        db_session.commit()

        # 创建升级计划
        plan = UpgradePlan(name="Preempt Test Plan")
        db_session.add(plan)
        db_session.commit()

        # 创建被抢占的任务
        normal_run = RunSession(
            plan_id=plan.id,
            device_id=device.id,
            priority=RunPriority.NORMAL,
            status=RunStatus.RUNNING,
            preemptible=True,
        )
        db_session.add(normal_run)
        db_session.commit()

        # 创建租约
        lease = DeviceLease(
            device_id=device.id,
            run_id=normal_run.id,
            lease_status=LeaseStatus.ACTIVE,
            preemptible=True,
        )
        db_session.add(lease)
        db_session.commit()

        # 查找可抢占任务
        service = PreemptionService(db_session)
        preemptible = service.find_preemptible_runs(pool.id)

        assert len(preemptible) == 1
        assert preemptible[0].id == normal_run.id

    def test_find_preemptible_runs_excludes_non_preemptible(self, db_session):
        """测试不可抢占的任务不会被选中。"""
        pool_service = PoolService(db_session)
        pool = pool_service.create_pool(name="no_preempt_pool", purpose=PoolPurpose.STABLE)

        device = Device(serial="NOPREEMPT001", status=DeviceStatus.BUSY, pool_id=pool.id)
        db_session.add(device)
        db_session.commit()

        plan = UpgradePlan(name="No Preempt Test Plan")
        db_session.add(plan)
        db_session.commit()

        # 创建不可抢占的任务
        run = RunSession(
            plan_id=plan.id,
            device_id=device.id,
            priority=RunPriority.NORMAL,
            status=RunStatus.RUNNING,
            preemptible=False,  # 不可抢占
        )
        db_session.add(run)
        db_session.commit()

        lease = DeviceLease(
            device_id=device.id,
            run_id=run.id,
            lease_status=LeaseStatus.ACTIVE,
            preemptible=False,
        )
        db_session.add(lease)
        db_session.commit()

        service = PreemptionService(db_session)
        preemptible = service.find_preemptible_runs(pool.id)

        assert len(preemptible) == 0

    def test_preempt_run_success(self, db_session):
        """测试成功抢占任务。"""
        pool_service = PoolService(db_session)
        pool = pool_service.create_pool(name="success_pool", purpose=PoolPurpose.STABLE)

        device = Device(serial="SUCCESS001", status=DeviceStatus.BUSY, pool_id=pool.id)
        db_session.add(device)
        db_session.commit()

        plan = UpgradePlan(name="Success Preempt Plan")
        db_session.add(plan)
        db_session.commit()

        # 被抢占的任务
        victim_run = RunSession(
            plan_id=plan.id,
            device_id=device.id,
            priority=RunPriority.NORMAL,
            status=RunStatus.RUNNING,
            preemptible=True,
        )
        db_session.add(victim_run)
        db_session.commit()

        lease = DeviceLease(
            device_id=device.id,
            run_id=victim_run.id,
            lease_status=LeaseStatus.ACTIVE,
            preemptible=True,
        )
        db_session.add(lease)
        db_session.commit()

        # 抢占者任务
        emergency_run = RunSession(
            plan_id=plan.id,
            priority=RunPriority.EMERGENCY,
            status=RunStatus.QUEUED,
        )
        db_session.add(emergency_run)
        db_session.commit()

        service = PreemptionService(db_session)
        result = service.preempt_run(victim_run.id, emergency_run.id)

        assert result is True

        # 验证被抢占任务状态
        db_session.refresh(victim_run)
        assert victim_run.status == RunStatus.PREEMPTED

        # 验证租约状态
        db_session.refresh(lease)
        assert lease.lease_status == LeaseStatus.PREEMPTED
        assert lease.preempted_by_run_id == emergency_run.id

        # 验证设备状态
        db_session.refresh(device)
        assert device.status == DeviceStatus.IDLE

    def test_preempt_run_only_normal_priority(self, db_session):
        """测试只能抢占 normal 优先级任务。"""
        pool_service = PoolService(db_session)
        pool = pool_service.create_pool(name="priority_pool", purpose=PoolPurpose.STABLE)

        device = Device(serial="PRIORITY001", status=DeviceStatus.BUSY, pool_id=pool.id)
        db_session.add(device)
        db_session.commit()

        plan = UpgradePlan(name="Priority Preempt Plan")
        db_session.add(plan)
        db_session.commit()

        # high 优先级任务
        high_run = RunSession(
            plan_id=plan.id,
            device_id=device.id,
            priority=RunPriority.HIGH,
            status=RunStatus.RUNNING,
            preemptible=True,
        )
        db_session.add(high_run)
        db_session.commit()

        lease = DeviceLease(
            device_id=device.id,
            run_id=high_run.id,
            lease_status=LeaseStatus.ACTIVE,
            preemptible=True,
        )
        db_session.add(lease)
        db_session.commit()

        emergency_run = RunSession(
            plan_id=plan.id,
            priority=RunPriority.EMERGENCY,
            status=RunStatus.QUEUED,
        )
        db_session.add(emergency_run)
        db_session.commit()

        service = PreemptionService(db_session)
        # 默认配置不允许抢占 high 优先级
        preemptible = service.find_preemptible_runs(pool.id, allow_preempt_high=False)
        assert len(preemptible) == 0

    def test_check_and_execute_preemption(self, db_session):
        """测试检查并执行抢占流程。"""
        pool_service = PoolService(db_session)
        pool = pool_service.create_pool(name="check_pool", purpose=PoolPurpose.STABLE, max_parallel=1)

        device = Device(serial="CHECK001", status=DeviceStatus.BUSY, pool_id=pool.id)
        db_session.add(device)
        db_session.commit()

        plan = UpgradePlan(name="Check Preempt Plan")
        db_session.add(plan)
        db_session.commit()

        # 正在运行的任务
        running_run = RunSession(
            plan_id=plan.id,
            device_id=device.id,
            priority=RunPriority.NORMAL,
            status=RunStatus.RUNNING,
            preemptible=True,
            pool_id=pool.id,
        )
        db_session.add(running_run)
        db_session.commit()

        lease = DeviceLease(
            device_id=device.id,
            run_id=running_run.id,
            lease_status=LeaseStatus.ACTIVE,
            preemptible=True,
        )
        db_session.add(lease)
        db_session.commit()

        # emergency 任务等待调度
        emergency_run = RunSession(
            plan_id=plan.id,
            priority=RunPriority.EMERGENCY,
            status=RunStatus.QUEUED,
            pool_id=pool.id,
        )
        db_session.add(emergency_run)
        db_session.commit()

        service = PreemptionService(db_session)
        result = service.check_and_execute_preemption(emergency_run.id)

        assert result is True
        db_session.refresh(running_run)
        assert running_run.status == RunStatus.PREEMPTED
        db_session.refresh(device)
        assert device.status == DeviceStatus.IDLE
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_services/test_preemption_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.preemption_service'"

- [ ] **Step 3: Write the implementation**

```python
# app/services/preemption_service.py
"""应急抢占服务。"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.device import Device, DeviceStatus, DeviceLease
from app.models.run import RunSession, RunStatus
from app.models.enums import RunPriority, LeaseStatus


class PreemptionService:
    """应急抢占服务。"""

    def __init__(self, db: Session):
        self.db = db

    def find_preemptible_runs(
        self,
        pool_id: int,
        allow_preempt_high: bool = False,
    ) -> List[RunSession]:
        """查找可抢占的任务。

        Args:
            pool_id: 设备池 ID
            allow_preempt_high: 是否允许抢占 high 优先级任务

        Returns:
            可抢占的任务列表，按优先级和运行时间排序
        """
        # 查找该池内运行中且可抢占的任务
        query = self.db.query(RunSession).join(
            Device, RunSession.device_id == Device.id
        ).filter(
            Device.pool_id == pool_id,
            RunSession.status.in_([RunStatus.RESERVED, RunStatus.RUNNING]),
            RunSession.preemptible == True,
        )

        if not allow_preempt_high:
            query = query.filter(RunSession.priority == RunPriority.NORMAL)

        runs = query.all()

        # 按优先级排序（NORMAL 优先）和运行时间（运行时间短的优先）
        priority_order = {
            RunPriority.HIGH: 0,
            RunPriority.NORMAL: 1,
        }

        runs.sort(key=lambda r: (
            priority_order.get(r.priority, 99),
            r.started_at or r.created_at,
        ))

        return runs

    def preempt_run(
        self,
        victim_run_id: int,
        preemptor_run_id: int,
    ) -> bool:
        """抢占指定任务。

        Args:
            victim_run_id: 被抢占的任务 ID
            preemptor_run_id: 抢占者的任务 ID

        Returns:
            是否成功抢占
        """
        victim_run = self.db.query(RunSession).filter_by(id=victim_run_id).first()
        if not victim_run:
            return False

        # 检查任务状态是否可抢占
        if victim_run.status not in [RunStatus.RESERVED, RunStatus.RUNNING]:
            return False

        if not victim_run.preemptible:
            return False

        # 获取租约
        lease = self.db.query(DeviceLease).filter(
            DeviceLease.run_id == victim_run_id,
            DeviceLease.lease_status == LeaseStatus.ACTIVE,
        ).first()

        if not lease:
            return False

        # 更新租约状态
        lease.lease_status = LeaseStatus.PREEMPTED
        lease.preempted_at = datetime.now(timezone.utc)
        lease.preempted_by_run_id = preemptor_run_id

        # 更新被抢占任务状态
        victim_run.status = RunStatus.PREEMPTED
        victim_run.ended_at = datetime.now(timezone.utc)

        # 释放设备
        device = self.db.query(Device).filter_by(id=victim_run.device_id).first()
        if device:
            device.status = DeviceStatus.IDLE
            device.current_run_id = None

        self.db.commit()
        return True

    def check_and_execute_preemption(
        self,
        emergency_run_id: int,
        allow_preempt_high: bool = False,
    ) -> bool:
        """检查并执行抢占。

        检查 emergency 任务是否需要抢占，如果需要则执行抢占。

        Args:
            emergency_run_id: emergency 任务 ID
            allow_preempt_high: 是否允许抢占 high 优先级任务

        Returns:
            是否成功抢占
        """
        emergency_run = self.db.query(RunSession).filter_by(id=emergency_run_id).first()
        if not emergency_run:
            return False

        # 只有 emergency 任务才能抢占
        if emergency_run.priority != RunPriority.EMERGENCY:
            return False

        # 检查是否有可用的设备
        if emergency_run.pool_id is None:
            return False

        # 检查池内是否有可用设备
        available_device = self.db.query(Device).filter(
            Device.pool_id == emergency_run.pool_id,
            Device.status == DeviceStatus.IDLE,
        ).first()

        if available_device:
            # 有可用设备，不需要抢占
            return False

        # 查找可抢占的任务
        preemptible_runs = self.find_preemptible_runs(
            emergency_run.pool_id,
            allow_preempt_high=allow_preempt_high,
        )

        if not preemptible_runs:
            return False

        # 抢占第一个可抢占的任务
        victim = preemptible_runs[0]
        return self.preempt_run(victim.id, emergency_run_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_services/test_preemption_service.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
cd E:/git_repositories/AegisOTA
git add app/services/preemption_service.py tests/test_services/test_preemption_service.py
git commit -m "feat: implement PreemptionService for emergency task preemption"
```

---

## Task 8: Create Pools API Endpoints

**Files:**
- Create: `app/api/pools.py`
- Create: `tests/test_api/test_pools.py`

- [ ] **Step 1: Write the failing test for Pools API**

```python
# tests/test_api/test_pools.py
"""设备池 API 测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_db():
    """创建测试数据库。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db):
    """创建测试客户端。"""
    return TestClient(app)


class TestPoolsAPI:
    """设备池 API 测试。"""

    def test_list_pools_empty(self, client):
        """测试空池列表。"""
        response = client.get("/api/pools")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_pool(self, client):
        """测试创建设备池。"""
        response = client.post("/api/pools", json={
            "name": "test_pool",
            "purpose": "stable",
            "reserved_ratio": 0.2,
            "max_parallel": 5,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_pool"
        assert data["purpose"] == "stable"
        assert data["reserved_ratio"] == 0.2

    def test_create_pool_duplicate_name(self, client):
        """测试创建重复名称设备池。"""
        client.post("/api/pools", json={
            "name": "duplicate",
            "purpose": "stable",
        })
        response = client.post("/api/pools", json={
            "name": "duplicate",
            "purpose": "stress",
        })
        assert response.status_code == 400

    def test_get_pool_by_id(self, client):
        """测试获取设备池详情。"""
        create_response = client.post("/api/pools", json={
            "name": "detail_pool",
            "purpose": "stable",
        })
        pool_id = create_response.json()["id"]

        response = client.get(f"/api/pools/{pool_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "detail_pool"

    def test_get_pool_not_found(self, client):
        """测试获取不存在的设备池。"""
        response = client.get("/api/pools/9999")
        assert response.status_code == 404

    def test_update_pool(self, client):
        """测试更新设备池。"""
        create_response = client.post("/api/pools", json={
            "name": "update_pool",
            "purpose": "stable",
        })
        pool_id = create_response.json()["id"]

        response = client.put(f"/api/pools/{pool_id}", json={
            "reserved_ratio": 0.3,
            "max_parallel": 10,
        })
        assert response.status_code == 200
        assert response.json()["reserved_ratio"] == 0.3
        assert response.json()["max_parallel"] == 10

    def test_delete_pool(self, client):
        """测试删除设备池。"""
        create_response = client.post("/api/pools", json={
            "name": "delete_pool",
            "purpose": "stable",
        })
        pool_id = create_response.json()["id"]

        response = client.delete(f"/api/pools/{pool_id}")
        assert response.status_code == 200

        # 确认已删除
        get_response = client.get(f"/api/pools/{pool_id}")
        assert get_response.status_code == 404

    def test_assign_device_to_pool(self, client, test_db):
        """测试分配设备到池。"""
        from app.models.device import Device

        # 创建设备池
        pool_response = client.post("/api/pools", json={
            "name": "assign_pool",
            "purpose": "stable",
        })
        pool_id = pool_response.json()["id"]

        # 创建设备
        device = Device(serial="ASSIGN_API001")
        test_db.add(device)
        test_db.commit()

        response = client.post(f"/api/pools/{pool_id}/assign", json={
            "device_id": device.id,
        })
        assert response.status_code == 200
        assert response.json()["pool_id"] == pool_id

    def test_get_pool_devices(self, client, test_db):
        """测试获取池内设备列表。"""
        from app.models.device import Device

        # 创建设备池
        pool_response = client.post("/api/pools", json={
            "name": "devices_pool",
            "purpose": "stable",
        })
        pool_id = pool_response.json()["id"]

        # 创建设备并分配到池
        for i in range(3):
            device = Device(serial=f"DEVICES{i:03d}", pool_id=pool_id)
            test_db.add(device)
        test_db.commit()

        response = client.get(f"/api/pools/{pool_id}/devices")
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_get_pool_capacity(self, client, test_db):
        """测试获取池容量。"""
        from app.models.device import Device, DeviceStatus

        pool_response = client.post("/api/pools", json={
            "name": "capacity_pool",
            "purpose": "stable",
            "max_parallel": 10,
        })
        pool_id = pool_response.json()["id"]

        # 添加设备
        for i in range(5):
            device = Device(
                serial=f"CAP_API{i:03d}",
                pool_id=pool_id,
                status=DeviceStatus.IDLE,
            )
            test_db.add(device)
        for i in range(3):
            device = Device(
                serial=f"CAP_BUSY{i:03d}",
                pool_id=pool_id,
                status=DeviceStatus.BUSY,
            )
            test_db.add(device)
        test_db.commit()

        response = client.get(f"/api/pools/{pool_id}/capacity")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 8
        assert data["available"] == 5
        assert data["busy"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_api/test_pools.py -v`
Expected: FAIL with "404 Not Found" (no route)

- [ ] **Step 3: Write the implementation**

```python
# app/api/pools.py
"""设备池 API 路由。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device, DevicePool, DeviceStatus
from app.models.enums import PoolPurpose
from app.services.pool_service import PoolService


router = APIRouter(prefix="/api/pools", tags=["pools"])


class PoolCreate(BaseModel):
    """设备池创建请求。"""
    name: str
    purpose: str
    reserved_ratio: float = 0.2
    max_parallel: int = 5
    tag_selector: Optional[dict] = None
    enabled: bool = True


class PoolUpdate(BaseModel):
    """设备池更新请求。"""
    reserved_ratio: Optional[float] = None
    max_parallel: Optional[int] = None
    tag_selector: Optional[dict] = None
    enabled: Optional[bool] = None


class DeviceAssign(BaseModel):
    """设备分配请求。"""
    device_id: int


class PoolResponse(BaseModel):
    """设备池响应。"""
    id: int
    name: str
    purpose: str
    reserved_ratio: float
    max_parallel: int
    tag_selector: Optional[dict] = None
    enabled: bool

    class Config:
        from_attributes = True


class DeviceResponse(BaseModel):
    """设备响应。"""
    id: int
    serial: str
    status: str
    pool_id: Optional[int] = None

    class Config:
        from_attributes = True


class CapacityResponse(BaseModel):
    """容量响应。"""
    total: int
    available: int
    busy: int
    offline: int
    quarantined: int
    max_parallel: int
    reserved: int
    usable: int


@router.get("", response_model=List[PoolResponse])
async def list_pools(
    purpose: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取设备池列表。"""
    service = PoolService(db)
    purpose_enum = PoolPurpose(purpose) if purpose else None
    pools = service.list_pools(purpose=purpose_enum)

    return [
        PoolResponse(
            id=p.id,
            name=p.name,
            purpose=p.purpose.value if hasattr(p.purpose, 'value') else str(p.purpose),
            reserved_ratio=p.reserved_ratio,
            max_parallel=p.max_parallel,
            tag_selector=p.get_tag_selector(),
            enabled=p.enabled,
        )
        for p in pools
    ]


@router.post("", response_model=PoolResponse)
async def create_pool(
    request: PoolCreate,
    db: Session = Depends(get_db),
):
    """创建设备池。"""
    service = PoolService(db)

    try:
        purpose = PoolPurpose(request.purpose)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid purpose '{request.purpose}'. Valid values: stable, stress, emergency"
        )

    try:
        pool = service.create_pool(
            name=request.name,
            purpose=purpose,
            reserved_ratio=request.reserved_ratio,
            max_parallel=request.max_parallel,
            tag_selector=request.tag_selector,
            enabled=request.enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PoolResponse(
        id=pool.id,
        name=pool.name,
        purpose=pool.purpose.value,
        reserved_ratio=pool.reserved_ratio,
        max_parallel=pool.max_parallel,
        tag_selector=pool.get_tag_selector(),
        enabled=pool.enabled,
    )


@router.get("/{pool_id}", response_model=PoolResponse)
async def get_pool(
    pool_id: int,
    db: Session = Depends(get_db),
):
    """获取设备池详情。"""
    service = PoolService(db)
    pool = service.get_pool_by_id(pool_id)

    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    return PoolResponse(
        id=pool.id,
        name=pool.name,
        purpose=pool.purpose.value,
        reserved_ratio=pool.reserved_ratio,
        max_parallel=pool.max_parallel,
        tag_selector=pool.get_tag_selector(),
        enabled=pool.enabled,
    )


@router.put("/{pool_id}", response_model=PoolResponse)
async def update_pool(
    pool_id: int,
    request: PoolUpdate,
    db: Session = Depends(get_db),
):
    """更新设备池配置。"""
    service = PoolService(db)

    update_data = {}
    if request.reserved_ratio is not None:
        update_data["reserved_ratio"] = request.reserved_ratio
    if request.max_parallel is not None:
        update_data["max_parallel"] = request.max_parallel
    if request.tag_selector is not None:
        update_data["tag_selector"] = request.tag_selector
    if request.enabled is not None:
        update_data["enabled"] = request.enabled

    pool = service.update_pool(pool_id, **update_data)

    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    return PoolResponse(
        id=pool.id,
        name=pool.name,
        purpose=pool.purpose.value,
        reserved_ratio=pool.reserved_ratio,
        max_parallel=pool.max_parallel,
        tag_selector=pool.get_tag_selector(),
        enabled=pool.enabled,
    )


@router.delete("/{pool_id}")
async def delete_pool(
    pool_id: int,
    db: Session = Depends(get_db),
):
    """删除设备池。"""
    service = PoolService(db)
    success = service.delete_pool(pool_id)

    if not success:
        raise HTTPException(status_code=404, detail="Pool not found")

    return {"status": "deleted", "id": pool_id}


@router.post("/{pool_id}/assign", response_model=DeviceResponse)
async def assign_device(
    pool_id: int,
    request: DeviceAssign,
    db: Session = Depends(get_db),
):
    """分配设备到池。"""
    service = PoolService(db)
    device = service.assign_device_to_pool(request.device_id, pool_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device or pool not found")

    return DeviceResponse(
        id=device.id,
        serial=device.serial,
        status=device.status.value if hasattr(device.status, 'value') else str(device.status),
        pool_id=device.pool_id,
    )


@router.get("/{pool_id}/devices", response_model=List[DeviceResponse])
async def get_pool_devices(
    pool_id: int,
    db: Session = Depends(get_db),
):
    """获取池内设备列表。"""
    devices = db.query(Device).filter_by(pool_id=pool_id).all()

    return [
        DeviceResponse(
            id=d.id,
            serial=d.serial,
            status=d.status.value if hasattr(d.status, 'value') else str(d.status),
            pool_id=d.pool_id,
        )
        for d in devices
    ]


@router.get("/{pool_id}/capacity", response_model=CapacityResponse)
async def get_pool_capacity(
    pool_id: int,
    db: Session = Depends(get_db),
):
    """获取池容量。"""
    service = PoolService(db)
    capacity = service.get_pool_capacity(pool_id)

    if not capacity:
        raise HTTPException(status_code=404, detail="Pool not found")

    return CapacityResponse(**capacity)
```

- [ ] **Step 4: Register router in main.py**

Update `app/main.py` to include the pools router:

```python
# Add import at top
from app.api import devices, reports, runs, web, settings, pools

# Add router registration (around line 117)
app.include_router(pools.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_api/test_pools.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd E:/git_repositories/AegisOTA
git add app/api/pools.py tests/test_api/test_pools.py app/main.py
git commit -m "feat: add /api/pools endpoints for device pool management"
```

---

## Task 9: Create Pool CLI Commands

**Files:**
- Create: `app/cli/pool.py`
- Create: `tests/test_cli/test_pool.py`

- [ ] **Step 1: Write the failing test for Pool CLI**

```python
# tests/test_cli/test_pool.py
"""Pool CLI 测试。"""

import pytest
from typer.testing import CliRunner

from app.cli.main import app
from app.database import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_db():
    """创建测试数据库。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()


runner = CliRunner()


class TestPoolCLI:
    """Pool CLI 测试。"""

    def test_pool_list_empty(self, test_db):
        """测试空池列表。"""
        result = runner.invoke(app, ["pool", "list"])
        assert result.exit_code == 0
        assert "No pools" in result.output or "[]" in result.output

    def test_pool_create(self, test_db):
        """测试创建设备池。"""
        result = runner.invoke(app, [
            "pool", "create",
            "--name", "cli_pool",
            "--purpose", "stable",
        ])
        assert result.exit_code == 0
        assert "cli_pool" in result.output

    def test_pool_show(self, test_db):
        """测试显示设备池详情。"""
        # 先创建
        runner.invoke(app, [
            "pool", "create",
            "--name", "show_pool",
            "--purpose", "stable",
        ])

        result = runner.invoke(app, ["pool", "show", "--name", "show_pool"])
        assert result.exit_code == 0
        assert "show_pool" in result.output

    def test_pool_update(self, test_db):
        """测试更新设备池。"""
        runner.invoke(app, [
            "pool", "create",
            "--name", "update_pool",
            "--purpose", "stable",
        ])

        result = runner.invoke(app, [
            "pool", "update",
            "--name", "update_pool",
            "--reserved-ratio", "0.3",
        ])
        assert result.exit_code == 0

    def test_pool_init_defaults(self, test_db):
        """测试初始化默认池。"""
        result = runner.invoke(app, ["pool", "init"])
        assert result.exit_code == 0
        assert "stable_pool" in result.output
        assert "stress_pool" in result.output
        assert "emergency_pool" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_cli/test_pool.py -v`
Expected: FAIL with "No such command 'pool'"

- [ ] **Step 3: Write the implementation**

```python
# app/cli/pool.py
"""设备池 CLI 命令。"""

import typer
from rich.console import Console
from rich.table import Table

from app.database import SessionLocal
from app.models.enums import PoolPurpose
from app.services.pool_service import PoolService

app = typer.Typer(name="pool", help="设备池管理命令")
console = Console()


@app.command("list")
def list_pools():
    """列出所有设备池。"""
    db = SessionLocal()
    try:
        service = PoolService(db)
        pools = service.list_pools()

        if not pools:
            console.print("[yellow]No pools found. Run 'pool init' to create default pools.[/yellow]")
            return

        table = Table(title="Device Pools")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Purpose", style="blue")
        table.add_column("Reserved", style="yellow")
        table.add_column("Max Parallel", style="magenta")
        table.add_column("Enabled", style="white")

        for pool in pools:
            table.add_row(
                str(pool.id),
                pool.name,
                pool.purpose.value if hasattr(pool.purpose, 'value') else str(pool.purpose),
                f"{pool.reserved_ratio:.0%}",
                str(pool.max_parallel),
                "✓" if pool.enabled else "✗",
            )

        console.print(table)
    finally:
        db.close()


@app.command("create")
def create_pool(
    name: str = typer.Option(..., "--name", "-n", help="设备池名称"),
    purpose: str = typer.Option("stable", "--purpose", "-p", help="设备池用途: stable, stress, emergency"),
    reserved_ratio: float = typer.Option(0.2, "--reserved-ratio", "-r", help="保留比例"),
    max_parallel: int = typer.Option(5, "--max-parallel", "-m", help="最大并行数"),
):
    """创建设备池。"""
    db = SessionLocal()
    try:
        service = PoolService(db)
        try:
            purpose_enum = PoolPurpose(purpose)
        except ValueError:
            console.print(f"[red]Invalid purpose '{purpose}'. Valid values: stable, stress, emergency[/red]")
            raise typer.Exit(1)

        try:
            pool = service.create_pool(
                name=name,
                purpose=purpose_enum,
                reserved_ratio=reserved_ratio,
                max_parallel=max_parallel,
            )
            console.print(f"[green]Created pool '{pool.name}' (ID: {pool.id})[/green]")
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    finally:
        db.close()


@app.command("show")
def show_pool(
    name: str = typer.Option(None, "--name", "-n", help="设备池名称"),
    pool_id: int = typer.Option(None, "--id", help="设备池 ID"),
):
    """显示设备池详情。"""
    db = SessionLocal()
    try:
        service = PoolService(db)

        if pool_id:
            pool = service.get_pool_by_id(pool_id)
        elif name:
            pool = service.get_pool_by_name(name)
        else:
            console.print("[red]Please specify --name or --id[/red]")
            raise typer.Exit(1)

        if not pool:
            console.print("[red]Pool not found[/red]")
            raise typer.Exit(1)

        # 显示详情
        capacity = service.get_pool_capacity(pool.id)

        console.print(f"\n[bold cyan]Pool: {pool.name}[/bold cyan]")
        console.print(f"  ID: {pool.id}")
        console.print(f"  Purpose: {pool.purpose.value}")
        console.print(f"  Reserved Ratio: {pool.reserved_ratio:.0%}")
        console.print(f"  Max Parallel: {pool.max_parallel}")
        console.print(f"  Enabled: {'Yes' if pool.enabled else 'No'}")

        console.print(f"\n[bold]Capacity:[/bold]")
        console.print(f"  Total Devices: {capacity['total']}")
        console.print(f"  Available: {capacity['available']}")
        console.print(f"  Busy: {capacity['busy']}")
        console.print(f"  Reserved: {capacity['reserved']}")
    finally:
        db.close()


@app.command("update")
def update_pool(
    name: str = typer.Option(None, "--name", "-n", help="设备池名称"),
    pool_id: int = typer.Option(None, "--id", help="设备池 ID"),
    reserved_ratio: float = typer.Option(None, "--reserved-ratio", "-r", help="保留比例"),
    max_parallel: int = typer.Option(None, "--max-parallel", "-m", help="最大并行数"),
    enabled: bool = typer.Option(None, "--enabled/--disabled", help="启用/禁用"),
):
    """更新设备池配置。"""
    db = SessionLocal()
    try:
        service = PoolService(db)

        if pool_id:
            target_id = pool_id
        elif name:
            pool = service.get_pool_by_name(name)
            if not pool:
                console.print("[red]Pool not found[/red]")
                raise typer.Exit(1)
            target_id = pool.id
        else:
            console.print("[red]Please specify --name or --id[/red]")
            raise typer.Exit(1)

        update_data = {}
        if reserved_ratio is not None:
            update_data["reserved_ratio"] = reserved_ratio
        if max_parallel is not None:
            update_data["max_parallel"] = max_parallel
        if enabled is not None:
            update_data["enabled"] = enabled

        if not update_data:
            console.print("[yellow]No updates specified[/yellow]")
            return

        pool = service.update_pool(target_id, **update_data)
        console.print(f"[green]Updated pool '{pool.name}'[/green]")
    finally:
        db.close()


@app.command("init")
def init_pools():
    """初始化默认设备池。"""
    db = SessionLocal()
    try:
        service = PoolService(db)
        pools = service.create_default_pools()

        console.print("[green]Created default pools:[/green]")
        for pool in pools:
            console.print(f"  - {pool.name} ({pool.purpose.value})")
    finally:
        db.close()


@app.command("assign")
def assign_device(
    device_id: int = typer.Option(..., "--device-id", "-d", help="设备 ID"),
    pool_name: str = typer.Option(..., "--pool-name", "-p", help="设备池名称"),
):
    """分配设备到池。"""
    db = SessionLocal()
    try:
        service = PoolService(db)
        pool = service.get_pool_by_name(pool_name)

        if not pool:
            console.print(f"[red]Pool '{pool_name}' not found[/red]")
            raise typer.Exit(1)

        device = service.assign_device_to_pool(device_id, pool.id)

        if not device:
            console.print(f"[red]Device {device_id} not found[/red]")
            raise typer.Exit(1)

        console.print(f"[green]Assigned device {device_id} to pool '{pool_name}'[/green]")
    finally:
        db.close()
```

- [ ] **Step 4: Register CLI in main.py**

Update `app/cli/main.py`:

```python
# Add import
from app.cli.pool import app as pool_app

# Register (around line 23)
app.add_typer(pool_app, name="pool", help="设备池管理")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd E:/git_repositories/AegisOTA && python -m pytest tests/test_cli/test_pool.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd E:/git_repositories/AegisOTA
git add app/cli/pool.py tests/test_cli/test_pool.py app/cli/main.py
git commit -m "feat: add labctl pool CLI commands"
```

---

## Task 10: Create Pools Web Page

**Files:**
- Create: `app/templates/pools.html`
- Modify: `app/api/web.py`

- [ ] **Step 1: Create the pools template**

```html
<!-- app/templates/pools.html -->
{% extends "base.html" %}

{% block title %}设备池管理 - AegisOTA{% endblock %}

{% block content %}
<div class="container">
    <div class="card">
        <div class="card-header">
            <span>设备池管理</span>
            <button class="btn btn-primary" onclick="showCreateModal()">创建设备池</button>
        </div>

        <div id="pools-list">
            <table class="table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>名称</th>
                        <th>用途</th>
                        <th>保留比例</th>
                        <th>最大并行</th>
                        <th>设备数</th>
                        <th>可用</th>
                        <th>状态</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
                    {% for pool in pools %}
                    <tr>
                        <td>{{ pool.id }}</td>
                        <td><strong>{{ pool.name }}</strong></td>
                        <td>
                            <span class="badge badge-{{ 'primary' if pool.purpose == 'stable' else 'warning' if pool.purpose == 'stress' else 'danger' }}">
                                {{ pool.purpose }}
                            </span>
                        </td>
                        <td>{{ (pool.reserved_ratio * 100)|int }}%</td>
                        <td>{{ pool.max_parallel }}</td>
                        <td>{{ pool.total_devices }}</td>
                        <td>{{ pool.available_devices }}</td>
                        <td>
                            <span class="status-badge status-{{ 'active' if pool.enabled else 'inactive' }}">
                                {{ '启用' if pool.enabled else '禁用' }}
                            </span>
                        </td>
                        <td>
                            <button class="btn btn-sm btn-secondary" onclick="showPoolDetail({{ pool.id }})">详情</button>
                            <button class="btn btn-sm btn-danger" onclick="deletePool({{ pool.id }})">删除</button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<script>
function showCreateModal() {
    // TODO: 实现创建模态框
    alert('创建设备池功能开发中');
}

function showPoolDetail(poolId) {
    window.location.href = '/pools/' + poolId;
}

function deletePool(poolId) {
    if (confirm('确定要删除这个设备池吗？')) {
        fetch('/api/pools/' + poolId, {
            method: 'DELETE',
        }).then(response => {
            if (response.ok) {
                location.reload();
            }
        });
    }
}
</script>
{% endblock %}
```

- [ ] **Step 2: Add web route for pools page**

Update `app/api/web.py` to add pools route:

```python
# Add import at top
from app.services.pool_service import PoolService

# Add route
@router.get("/pools", response_class=HTMLResponse)
async def pools_page(request: Request, db: Session = Depends(get_db)):
    """设备池管理页面。"""
    service = PoolService(db)
    pools = service.list_pools()

    # 添加设备统计
    pools_data = []
    for pool in pools:
        capacity = service.get_pool_capacity(pool.id)
        pools_data.append({
            "id": pool.id,
            "name": pool.name,
            "purpose": pool.purpose.value if hasattr(pool.purpose, 'value') else str(pool.purpose),
            "reserved_ratio": pool.reserved_ratio,
            "max_parallel": pool.max_parallel,
            "enabled": pool.enabled,
            "total_devices": capacity["total"],
            "available_devices": capacity["available"],
        })

    return templates.TemplateResponse(
        "pools.html",
        {"request": request, "pools": pools_data}
    )
```

- [ ] **Step 3: Add navigation link**

Update `app/templates/base.html` to add pools link in navigation:

```html
<!-- Add in navigation -->
<a href="/pools" class="nav-link">设备池</a>
```

- [ ] **Step 4: Commit**

```bash
cd E:/git_repositories/AegisOTA
git add app/templates/pools.html app/api/web.py app/templates/base.html
git commit -m "feat: add pools management web page"
```

---

## Task 11: Database Migration

**Files:**
- Create: Alembic migration script

- [ ] **Step 1: Generate migration**

Run:
```bash
cd E:/git_repositories/AegisOTA
alembic revision --autogenerate -m "add device pools and extend models"
```

- [ ] **Step 2: Review and edit migration**

Check generated migration file and ensure:
1. `device_pools` table is created
2. `devices` table gets `pool_id` and `sync_failure_count` columns
3. `run_sessions` table gets `priority`, `pool_id`, `preemptible`, `drill_id` columns
4. `device_leases` table gets `preemptible`, `preempted_at`, `preempted_by_run_id` columns

- [ ] **Step 3: Test migration**

Run:
```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

- [ ] **Step 4: Commit**

```bash
git add migrations/versions/*.py
git commit -m "feat: add alembic migration for device pools"
```

---

## Task 12: Integration Tests and Documentation

**Files:**
- Create: `tests/test_integration/test_pool_workflow.py`
- Update: `CLAUDE.md`
- Update: `README.md`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration/test_pool_workflow.py
"""设备池工作流集成测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db, SessionLocal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def test_db():
    """创建测试数据库。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()


@pytest.fixture
def client(test_db):
    return TestClient(app)


class TestPoolWorkflow:
    """设备池完整工作流测试。"""

    def test_full_pool_workflow(self, client, test_db):
        """测试完整的设备池工作流。"""
        from app.models.device import Device, DeviceStatus
        from app.models.run import UpgradePlan
        from app.models.enums import RunPriority

        # 1. 创建默认设备池
        response = client.post("/api/pools", json={
            "name": "workflow_pool",
            "purpose": "stable",
            "reserved_ratio": 0.2,
            "max_parallel": 5,
        })
        assert response.status_code == 200
        pool_id = response.json()["id"]

        # 2. 创建设备并分配到池
        device = Device(serial="WORKFLOW001", status=DeviceStatus.IDLE, pool_id=pool_id)
        test_db.add(device)
        test_db.commit()

        # 3. 验证池容量
        response = client.get(f"/api/pools/{pool_id}/capacity")
        assert response.status_code == 200
        assert response.json()["available"] == 1

        # 4. 创建升级计划
        plan = UpgradePlan(name="Workflow Test Plan", default_pool_id=pool_id)
        test_db.add(plan)
        test_db.commit()

        # 5. 创建任务并分配设备
        # (需要 run API 支持)

        print("Pool workflow test passed!")


class TestPriorityPreemptionWorkflow:
    """优先级抢占工作流测试。"""

    def test_emergency_preemption(self, test_db):
        """测试 emergency 任务抢占流程。"""
        from app.models.device import Device, DevicePool, DeviceStatus, DeviceLease
        from app.models.run import RunSession, UpgradePlan
        from app.models.enums import PoolPurpose, RunPriority, RunStatus, LeaseStatus
        from app.services.pool_service import PoolService
        from app.services.preemption_service import PreemptionService

        # 1. 创建设备池和设备
        pool_service = PoolService(test_db)
        pool = pool_service.create_pool(name="preempt_workflow", purpose=PoolPurpose.STABLE, max_parallel=1)

        device = Device(serial="PREEMPT_W001", status=DeviceStatus.BUSY, pool_id=pool.id)
        test_db.add(device)
        test_db.commit()

        # 2. 创建升级计划
        plan = UpgradePlan(name="Preempt Workflow Plan")
        test_db.add(plan)
        test_db.commit()

        # 3. 创建正在运行的 normal 任务
        normal_run = RunSession(
            plan_id=plan.id,
            device_id=device.id,
            priority=RunPriority.NORMAL,
            status=RunStatus.RUNNING,
            preemptible=True,
            pool_id=pool.id,
        )
        test_db.add(normal_run)
        test_db.commit()

        lease = DeviceLease(
            device_id=device.id,
            run_id=normal_run.id,
            lease_status=LeaseStatus.ACTIVE,
            preemptible=True,
        )
        test_db.add(lease)
        test_db.commit()

        # 4. 创建 emergency 任务
        emergency_run = RunSession(
            plan_id=plan.id,
            priority=RunPriority.EMERGENCY,
            status=RunStatus.QUEUED,
            pool_id=pool.id,
        )
        test_db.add(emergency_run)
        test_db.commit()

        # 5. 执行抢占
        preemption_service = PreemptionService(test_db)
        result = preemption_service.check_and_execute_preemption(emergency_run.id)

        assert result is True

        # 6. 验证状态
        test_db.refresh(normal_run)
        test_db.refresh(device)

        assert normal_run.status == RunStatus.PREEMPTED
        assert device.status == DeviceStatus.IDLE

        print("Emergency preemption workflow test passed!")
```

- [ ] **Step 2: Run integration tests**

Run:
```bash
cd E:/git_repositories/AegisOTA
python -m pytest tests/test_integration/test_pool_workflow.py -v
```

- [ ] **Step 3: Update documentation**

Update `CLAUDE.md` with new features:

```markdown
## 设备池管理

### 核心概念

- **DevicePool**: 设备池，用于管理和隔离设备资源
- **PoolPurpose**: 设备池用途 (stable/stress/emergency)
- **RunPriority**: 任务优先级 (normal/high/emergency)
- **Preemption**: 应急抢占，emergency 任务可以抢占 normal 任务

### API 端点

- `GET /api/pools` - 获取设备池列表
- `POST /api/pools` - 创建设备池
- `GET /api/pools/{id}` - 获取设备池详情
- `PUT /api/pools/{id}` - 更新设备池配置
- `DELETE /api/pools/{id}` - 删除设备池
- `POST /api/pools/{id}/assign` - 分配设备到池
- `GET /api/pools/{id}/devices` - 获取池内设备
- `GET /api/pools/{id}/capacity` - 获取池容量

### CLI 命令

```bash
labctl pool list                    # 列出设备池
labctl pool create --name NAME      # 创建设备池
labctl pool show --name NAME        # 显示设备池详情
labctl pool update --name NAME      # 更新设备池配置
labctl pool init                    # 初始化默认设备池
labctl pool assign --device-id ID --pool-name NAME  # 分配设备
```
```

- [ ] **Step 4: Commit**

```bash
cd E:/git_repositories/AegisOTA
git add tests/test_integration/test_pool_workflow.py CLAUDE.md
git commit -m "feat: add integration tests and update documentation for device pools"
```

---

## Summary

This plan implements Phase 1: Device Pool Foundation with the following components:

1. **Enums** - PoolPurpose, RunPriority, extended DeviceStatus and RunStatus
2. **Data Models** - DevicePool, extended Device and RunSession
3. **Services** - PoolService, PreemptionService, extended SchedulerService
4. **API** - REST endpoints for pool management
5. **CLI** - `labctl pool` commands
6. **Web UI** - Pools management page
7. **Migration** - Database schema changes
8. **Integration Tests** - End-to-end workflow tests

Each task follows TDD principles with complete test code and implementation code.