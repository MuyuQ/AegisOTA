"""结构化日志模块。

提供统一的日志记录接口，支持结构化输出和上下文信息。
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import get_settings


def setup_logging() -> None:
    """配置应用日志。

    根据配置设置日志级别、格式和处理器。
    """
    settings = get_settings()

    # 获取根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)

    # 清除现有处理器
    root_logger.handlers.clear()

    # 创建处理器
    if settings.DEBUG:
        # 开发模式：使用彩色控制台输出
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(DebugFormatter())
    else:
        # 生产模式：使用结构化 JSON 输出
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())

    root_logger.addHandler(handler)

    # 配置第三方库日志级别
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)


class StructuredFormatter(logging.Formatter):
    """结构化 JSON 格式化器。"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为 JSON。"""
        import json

        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加额外字段
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class DebugFormatter(logging.Formatter):
    """开发模式彩色格式化器。"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为彩色文本。"""
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        base_msg = (
            f"{timestamp} {color}{record.levelname}{self.RESET} "
            f"[{record.name}] {record.getMessage()}"
        )

        # 添加额外字段
        if hasattr(record, "extra") and record.extra:
            extra_str = " | " + " ".join(f"{k}={v}" for k, v in record.extra.items())
            base_msg += extra_str

        # 添加异常信息
        if record.exc_info:
            base_msg += f"\n{self.formatException(record.exc_info)}"

        return base_msg


class ContextLogger:
    """上下文日志器。

    提供带上下文信息的日志记录方法。
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(
        self,
        level: int,
        message: str,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        """记录带额外信息的日志。"""
        # 创建带有 extra 属性的 LogRecord
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            None,  # fn
            0,  # lno
            message,
            (),  # args
            None,  # exc_info
        )
        if extra:
            record.extra = extra
        self._logger.handle(record)

    def debug(self, message: str, **kwargs: Any) -> None:
        """记录 DEBUG 级别日志。"""
        self._log(logging.DEBUG, message, kwargs if kwargs else None)

    def info(self, message: str, **kwargs: Any) -> None:
        """记录 INFO 级别日志。"""
        self._log(logging.INFO, message, kwargs if kwargs else None)

    def warning(self, message: str, **kwargs: Any) -> None:
        """记录 WARNING 级别日志。"""
        self._log(logging.WARNING, message, kwargs if kwargs else None)

    def error(self, message: str, **kwargs: Any) -> None:
        """记录 ERROR 级别日志。"""
        self._log(logging.ERROR, message, kwargs if kwargs else None)

    def critical(self, message: str, **kwargs: Any) -> None:
        """记录 CRITICAL 级别日志。"""
        self._log(logging.CRITICAL, message, kwargs if kwargs else None)

    def exception(self, message: str, **kwargs: Any) -> None:
        """记录异常日志。"""
        self._logger.exception(message, extra=kwargs if kwargs else None)


def get_logger(name: str) -> ContextLogger:
    """获取上下文日志器。"""
    return ContextLogger(name)


# 预定义的日志器
logger = get_logger("aegisota")


# 任务执行日志器
class RunLogger:
    """任务执行专用日志器。"""

    def __init__(self, run_id: int, device_serial: str):
        self.run_id = run_id
        self.device_serial = device_serial
        self._logger = get_logger(f"aegisota.run.{run_id}")

    def step_start(self, step_name: str) -> None:
        """记录步骤开始。"""
        self._logger.info(
            f"Step {step_name} started",
            run_id=self.run_id,
            device=self.device_serial,
            step=step_name,
            event="step_start",
        )

    def step_end(self, step_name: str, success: bool, duration_ms: int) -> None:
        """记录步骤结束。"""
        level = "info" if success else "error"
        getattr(self._logger, level)(
            f"Step {step_name} ended ({'success' if success else 'failed'})",
            run_id=self.run_id,
            device=self.device_serial,
            step=step_name,
            success=success,
            duration_ms=duration_ms,
            event="step_end",
        )

    def command(self, command: str, exit_code: int, duration_ms: int) -> None:
        """记录命令执行。"""
        self._logger.debug(
            f"Command executed: {command}",
            run_id=self.run_id,
            device=self.device_serial,
            command=command,
            exit_code=exit_code,
            duration_ms=duration_ms,
            event="command",
        )

    def fault_inject(self, fault_type: str, stage: str) -> None:
        """记录故障注入。"""
        self._logger.info(
            f"Fault injected: {fault_type}",
            run_id=self.run_id,
            device=self.device_serial,
            fault_type=fault_type,
            stage=stage,
            event="fault_inject",
        )

    def state_change(self, old_state: str, new_state: str) -> None:
        """记录状态变更。"""
        self._logger.info(
            f"State changed: {old_state} -> {new_state}",
            run_id=self.run_id,
            device=self.device_serial,
            old_state=old_state,
            new_state=new_state,
            event="state_change",
        )
