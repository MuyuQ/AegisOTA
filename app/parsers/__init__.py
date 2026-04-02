"""解析器模块。

提供多种日志解析器，用于从 recovery.log、update_engine.log、logcat、monkey 等日志中提取标准化事件。
"""

from app.parsers.base import BaseParser, Stage, SourceType, EventType, Severity
from app.parsers.recovery_parser import RecoveryParser
from app.parsers.update_engine_parser import UpdateEngineParser
from app.parsers.logcat_parser import LogcatParser
from app.parsers.monkey_parser import MonkeyParser

__all__ = [
    "BaseParser",
    "Stage",
    "SourceType",
    "EventType",
    "Severity",
    "RecoveryParser",
    "UpdateEngineParser",
    "LogcatParser",
    "MonkeyParser",
]
