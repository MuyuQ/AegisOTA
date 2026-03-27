"""执行上下文模块。"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.config import get_settings


@dataclass
class DeviceSnapshot:
    """设备状态快照。"""

    serial: str
    brand: Optional[str] = None
    model: Optional[str] = None
    android_version: Optional[str] = None
    battery_level: Optional[int] = None
    build_fingerprint: Optional[str] = None
    boot_completed: bool = False


@dataclass
class RunContext:
    """任务执行上下文。"""

    run_id: int
    device_serial: str
    plan_id: int
    upgrade_type: str

    # 设备信息
    device: Optional[DeviceSnapshot] = None

    # 执行配置
    package_path: Optional[str] = None
    target_build: Optional[str] = None
    timeout: int = 300

    # 当前状态
    current_step: Optional[str] = None
    step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # 产物路径
    artifact_dir: Optional[Path] = None

    # 异常注入
    fault_profile: Optional[Dict[str, Any]] = None

    # 时间记录
    started_at: Optional[datetime] = None
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        """初始化产物目录。"""
        settings = get_settings()
        if self.artifact_dir is None:
            self.artifact_dir = settings.ARTIFACTS_DIR / str(self.run_id)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def record_event(self, event_type: str, message: str, extra: Optional[Dict] = None):
        """记录事件。"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "message": message,
        }
        if extra:
            event["extra"] = extra
        self.timeline.append(event)

    def set_step_result(self, step_name: str, result: Dict[str, Any]):
        """设置步骤结果。"""
        self.step_results[step_name] = result

    def get_step_result(self, step_name: str) -> Optional[Dict[str, Any]]:
        """获取步骤结果。"""
        return self.step_results.get(step_name)