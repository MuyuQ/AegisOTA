"""结构化日志测试。"""

import json
import logging

from app.utils.logging import (
    ContextLogger,
    DebugFormatter,
    RunLogger,
    StructuredFormatter,
    get_logger,
    setup_logging,
)


class TestStructuredFormatter:
    """结构化格式化器测试。"""

    def test_format_basic_record(self):
        """测试基本日志记录格式化。"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Test message"
        assert data["module"] == "test"
        assert "timestamp" in data

    def test_format_with_extra(self):
        """测试带额外字段的格式化。"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra = {"run_id": 1, "device": "ABC123"}

        output = formatter.format(record)
        data = json.loads(output)

        assert data["extra"]["run_id"] == 1
        assert data["extra"]["device"] == "ABC123"


class TestDebugFormatter:
    """开发模式格式化器测试。"""

    def test_format_contains_level(self):
        """测试格式包含级别。"""
        formatter = DebugFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=42,
            msg="Warning message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        assert "WARNING" in output
        assert "Warning message" in output

    def test_format_with_extra(self):
        """测试带额外字段的格式化。"""
        formatter = DebugFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra = {"key": "value"}

        output = formatter.format(record)
        assert "key=value" in output


class TestContextLogger:
    """上下文日志器测试。"""

    def test_get_logger(self):
        """测试获取日志器。"""
        logger = get_logger("test.module")
        assert isinstance(logger, ContextLogger)

    def test_info_with_kwargs(self, caplog):
        """测试带参数的 INFO 日志。"""
        caplog.set_level(logging.INFO)
        logger = get_logger("test.info")

        logger.info("Test message", run_id=1, device="ABC123")

        # 检查日志记录
        assert len(caplog.records) > 0
        record = caplog.records[-1]
        assert record.levelno == logging.INFO
        assert "Test message" in record.getMessage()


class TestRunLogger:
    """任务执行日志器测试。"""

    def test_step_start(self, caplog):
        """测试步骤开始日志。"""
        caplog.set_level(logging.INFO)
        logger = RunLogger(run_id=1, device_serial="ABC123")

        logger.step_start("precheck")

        assert len(caplog.records) > 0
        record = caplog.records[-1]
        assert "started" in record.getMessage()

    def test_step_end_success(self, caplog):
        """测试步骤成功结束日志。"""
        caplog.set_level(logging.INFO)
        logger = RunLogger(run_id=1, device_serial="ABC123")

        logger.step_end("precheck", success=True, duration_ms=100)

        assert len(caplog.records) > 0
        record = caplog.records[-1]
        assert "success" in record.getMessage()

    def test_step_end_failure(self, caplog):
        """测试步骤失败结束日志。"""
        caplog.set_level(logging.ERROR)
        logger = RunLogger(run_id=1, device_serial="ABC123")

        logger.step_end("precheck", success=False, duration_ms=100)

        assert len(caplog.records) > 0
        record = caplog.records[-1]
        assert "failed" in record.getMessage()

    def test_fault_inject(self, caplog):
        """测试故障注入日志。"""
        caplog.set_level(logging.INFO)
        logger = RunLogger(run_id=1, device_serial="ABC123")

        logger.fault_inject("storage_pressure", "precheck")

        assert len(caplog.records) > 0
        record = caplog.records[-1]
        assert "storage_pressure" in record.getMessage()

    def test_state_change(self, caplog):
        """测试状态变更日志。"""
        caplog.set_level(logging.INFO)
        logger = RunLogger(run_id=1, device_serial="ABC123")

        logger.state_change("queued", "running")

        assert len(caplog.records) > 0
        record = caplog.records[-1]
        assert "queued" in record.getMessage()
        assert "running" in record.getMessage()


class TestSetupLogging:
    """日志配置测试。"""

    def test_setup_logging_creates_handler(self):
        """测试日志配置创建处理器。"""
        # 清除现有处理器
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        setup_logging()

        assert len(root_logger.handlers) > 0

    def test_setup_logging_level(self):
        """测试日志级别设置。"""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        setup_logging()

        # 默认级别应该是 INFO
        assert root_logger.level == logging.INFO
