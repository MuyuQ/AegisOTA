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
