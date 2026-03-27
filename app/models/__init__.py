"""数据模型模块。"""

from app.models.artifact import Artifact, ArtifactType
from app.models.device import Device, DeviceLease, DeviceStatus, LeaseStatus
from app.models.fault import FaultProfile, FaultStage, FaultType
from app.models.run import (
    FailureCategory,
    RunSession,
    RunStatus,
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
    "DeviceStatus",
    "LeaseStatus",
    # Run models
    "UpgradePlan",
    "RunSession",
    "RunStep",
    "RunStatus",
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
]