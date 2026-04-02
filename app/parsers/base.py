"""解析器基础抽象类。

定义所有解析器的公共接口和辅助方法。
"""

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional


# 阶段常量
class Stage:
    """诊断阶段常量。"""

    PRECHECK = "precheck"
    PACKAGE_PREPARE = "package_prepare"
    APPLY_UPDATE = "apply_update"
    REBOOT_WAIT = "reboot_wait"
    POST_REBOOT = "post_reboot"
    POST_VALIDATE = "post_validate"


# 来源类型常量
class SourceType:
    """日志来源常量。"""

    RECOVERY_LOG = "recovery_log"
    LAST_INSTALL = "last_install"
    UPDATE_ENGINE_LOG = "update_engine_log"
    DEVICE_RUNTIME_LOG = "device_runtime_log"
    LOGCAT = "logcat"
    MONKEY_OUTPUT = "monkey_output"


# 事件类型常量
class EventType:
    """事件类型常量。"""

    STATUS_TRANSITION = "status_transition"
    ERROR_SIGNAL = "error_signal"
    PROGRESS_SIGNAL = "progress_signal"
    VALIDATION_RESULT = "validation_result"
    ENVIRONMENT_CHECK = "environment_check"
    SUMMARY_SIGNAL = "summary_signal"


# 严重级别常量
class Severity:
    """严重级别常量。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class BaseParser(ABC):
    """解析器抽象基类。

    所有日志解析器必须继承此类并实现 parse() 方法。
    """

    source_type: str
    default_stage: str = Stage.PRECHECK
    default_event_type: str = EventType.STATUS_TRANSITION
    default_severity: str = Severity.INFO

    @abstractmethod
    def parse(self, content: str, run_id: str) -> list[dict]:
        """
        解析日志内容，返回事件字典列表。

        Args:
            content: 日志文件内容
            run_id: 任务ID

        Returns:
            事件字典列表，每个字典包含以下字段：
            - source_type: 来源类型
            - stage: 阶段
            - event_type: 事件类型
            - severity: 严重级别
            - normalized_code: 标准化代码
            - raw_line: 原始行内容
            - line_no: 行号
            - timestamp: 时间戳（可选）
            - message: 消息（可选）
            - kv_payload: 键值数据（可选）
        """
        pass

    def parse_file(self, file_path: str, run_id: str) -> list[dict]:
        """
        解析文件。

        Args:
            file_path: 文件路径
            run_id: 任务ID

        Returns:
            事件字典列表
        """
        content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        return self.parse(content, run_id)

    def create_event(
        self,
        run_id: str,
        normalized_code: str,
        message: Optional[str] = None,
        stage: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        timestamp: Optional[str] = None,
        line_no: Optional[int] = None,
        raw_line: Optional[str] = None,
        kv_payload: Optional[dict] = None,
        source_type_override: Optional[str] = None,
    ) -> dict:
        """
        创建事件字典的辅助方法。

        Args:
            run_id: 任务ID
            normalized_code: 标准化代码
            message: 消息
            stage: 阶段
            event_type: 事件类型
            severity: 严重级别
            timestamp: 时间戳字符串
            line_no: 行号
            raw_line: 原始行
            kv_payload: 键值数据
            source_type_override: 覆盖的来源类型

        Returns:
            事件字典
        """
        parsed_timestamp = None
        if timestamp:
            try:
                # 尝试多种时间格式
                for fmt in ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        parsed_timestamp = datetime.strptime(timestamp, fmt)
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

        return {
            "run_id": run_id,
            "source_type": source_type_override or self.source_type,
            "timestamp": parsed_timestamp,
            "line_no": line_no,
            "raw_line": raw_line,
            "stage": stage or self.default_stage,
            "event_type": event_type or self.default_event_type,
            "severity": severity or self.default_severity,
            "normalized_code": normalized_code,
            "message": message,
            "kv_payload": kv_payload,
        }