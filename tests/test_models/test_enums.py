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
        assert DeviceStatus.RESERVED == "reserved"
        assert DeviceStatus.BUSY == "busy"
        assert DeviceStatus.OFFLINE == "offline"
        assert DeviceStatus.QUARANTINED == "quarantined"
        assert DeviceStatus.RECOVERING == "recovering"

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
        assert RunStatus.ALLOCATING == "allocating"
        assert RunStatus.RESERVED == "reserved"
        assert RunStatus.RUNNING == "running"
        assert RunStatus.VALIDATING == "validating"
        assert RunStatus.PASSED == "passed"
        assert RunStatus.FAILED == "failed"
        assert RunStatus.ABORTED == "aborted"
        assert RunStatus.PREEMPTED == "preempted"
        assert RunStatus.QUARANTINED == "quarantined"

    def test_status_count(self):
        """测试枚举值数量。"""
        assert len(RunStatus) == 10


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
