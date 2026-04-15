"""数据模型模块。"""

from app.models.artifact import Artifact, ArtifactType
from app.models.device import Device, DeviceLease, DevicePool
from app.models.diagnostic import (
    DiagnosticResult,
    DiagnosticRule,
    NormalizedEvent,
    RuleHit,
    SimilarCaseIndex,
)
from app.models.enums import (
    DeviceStatus,
    EventType,
    LeaseStatus,
    PoolPurpose,
    RunPriority,
    RunStatus,
    Severity,
    SourceType,
    Stage,
)
from app.models.event import NormalizedEvent as NormalizedEventPydantic
from app.models.fault import FaultProfile, FaultStage, FaultType
from app.models.report import Report, ReportFormat, ReportStatus
from app.models.run import (
    FailureCategory,
    RunSession,
    RunStep,
    StepName,
    StepStatus,
    UpgradePlan,
    UpgradeType,
)

__all__ = [
    # Device models
    "Device",
    "DeviceLease",
    "DevicePool",
    "DeviceStatus",
    "LeaseStatus",
    "PoolPurpose",
    # Run models
    "UpgradePlan",
    "RunSession",
    "RunStep",
    "RunStatus",
    "RunPriority",
    "UpgradeType",
    "StepName",
    "StepStatus",
    "FailureCategory",
    # Fault models
    "FaultProfile",
    "FaultStage",
    "FaultType",
    # Artifact models
    "Artifact",
    "ArtifactType",
    # Report models
    "Report",
    "ReportFormat",
    "ReportStatus",
    # Diagnostic models
    "DiagnosticResult",
    "DiagnosticRule",
    "RuleHit",
    "SimilarCaseIndex",
    # Event models
    "NormalizedEvent",
    "NormalizedEventPydantic",
    "EventType",
    "Severity",
    "SourceType",
    "Stage",
]
