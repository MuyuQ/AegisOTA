"""异常注入插件抽象基类。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app.executors.adb_executor import ADBExecutor
from app.executors.run_context import RunContext


@dataclass
class FaultResult:
    """异常注入结果。"""

    success: bool
    fault_type: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "success": self.success,
            "fault_type": self.fault_type,
            "message": self.message,
            "data": self.data,
            "error": self.error,
        }


class FaultPlugin(ABC):
    """异常注入插件抽象基类。"""

    fault_type: str = ""
    fault_stage: str = ""
    description: str = ""

    def __init__(self, executor: Optional[ADBExecutor] = None):
        self.executor = executor or ADBExecutor()

    def prepare(self, context: RunContext) -> FaultResult:
        """准备阶段（可选实现）。"""
        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="准备完成",
            data={},
        )

    @abstractmethod
    def inject(self, context: RunContext) -> FaultResult:
        """注入异常。"""
        pass

    def cleanup(self, context: RunContext) -> FaultResult:
        """清理阶段（可选实现）。"""
        return FaultResult(
            success=True,
            fault_type=self.fault_type,
            message="清理完成",
            data={},
        )

    def get_parameters(self) -> Dict[str, Any]:
        """获取插件参数（从 fault profile）。"""
        return getattr(self, "_parameters", {})

    def set_parameters(self, params: Dict[str, Any]):
        """设置插件参数。"""
        self._parameters = params

    def validate_parameters(self) -> bool:
        """验证参数有效性。"""
        return True

    def should_inject(self, context: RunContext) -> bool:
        """判断是否应该注入（可根据条件决定）。"""
        return True

    def record_event(self, context: RunContext, message: str, extra: Optional[Dict] = None):
        """记录异常注入事件。"""
        context.record_event(
            "fault_injection",
            message,
            {
                "fault_type": self.fault_type,
                "fault_stage": self.fault_stage,
                "extra": extra or {},
            },
        )
