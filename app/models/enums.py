"""统一枚举定义。"""

from enum import Enum


class DeviceStatus(str, Enum):
    """设备状态枚举。"""

    IDLE = "idle"
    RESERVED = "reserved"  # 新增：已分配但任务未开始
    BUSY = "busy"
    OFFLINE = "offline"
    QUARANTINED = "quarantined"
    RECOVERING = "recovering"


class LeaseStatus(str, Enum):
    """租约状态枚举。"""

    ACTIVE = "active"
    RELEASED = "released"
    PREEMPTED = "preempted"  # 新增：被抢占
    EXPIRED = "expired"


class PoolPurpose(str, Enum):
    """设备池用途枚举。"""

    STABLE = "stable"  # 稳定测试池
    STRESS = "stress"  # 压力测试池
    EMERGENCY = "emergency"  # 应急池


class RunPriority(str, Enum):
    """任务优先级枚举。"""

    NORMAL = "normal"
    HIGH = "high"
    EMERGENCY = "emergency"


class RunStatus(str, Enum):
    """任务状态枚举。"""

    QUEUED = "queued"
    ALLOCATING = "allocating"  # 新增：正在分配设备
    RESERVED = "reserved"
    RUNNING = "running"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"
    ABORTED = "aborted"
    PREEMPTED = "preempted"  # 新增：被抢占


class Stage(str, Enum):
    """诊断阶段枚举。"""

    PRECHECK = "precheck"
    PACKAGE_PREPARE = "package_prepare"
    APPLY_UPDATE = "apply_update"
    REBOOT_WAIT = "reboot_wait"
    POST_REBOOT = "post_reboot"
    POST_VALIDATE = "post_validate"


class SourceType(str, Enum):
    """日志来源枚举。"""

    RECOVERY_LOG = "recovery_log"
    LAST_INSTALL = "last_install"
    UPDATE_ENGINE_LOG = "update_engine_log"
    DEVICE_RUNTIME_LOG = "device_runtime_log"
    ARTIFACT_SUMMARY = "artifact_summary"


class EventType(str, Enum):
    """事件类型枚举。"""

    STATUS_TRANSITION = "status_transition"
    ERROR_SIGNAL = "error_signal"
    PROGRESS_SIGNAL = "progress_signal"
    VALIDATION_RESULT = "validation_result"
    ENVIRONMENT_CHECK = "environment_check"
    SUMMARY_SIGNAL = "summary_signal"


class Severity(str, Enum):
    """严重级别枚举。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ResultStatus(str, Enum):
    """诊断结果状态枚举。"""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    TRANSIENT_FAILURE = "transient_failure"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
