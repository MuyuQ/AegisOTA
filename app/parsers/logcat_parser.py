"""Logcat日志解析器。

解析 logcat 输出，提取崩溃、ANR、致命错误等事件。
"""

import re
from typing import Optional

from app.parsers.base import BaseParser, Stage, SourceType, EventType, Severity


class LogcatParser(BaseParser):
    """Logcat 日志解析器。

    解析 logcat 输出中的关键事件，包括：
    - 应用崩溃 (CRASH)
    - ANR (Application Not Responding)
    - 系统致命错误 (FATAL EXCEPTION)
    - Java 异常
    - Native 崩溃
    - ADB 传输错误
    """

    source_type = SourceType.LOGCAT
    default_stage = Stage.POST_REBOOT
    default_event_type = EventType.ERROR_SIGNAL
    default_severity = Severity.INFO

    # 时间戳格式: 03-28 15:12:44.310 或 2026-03-28 15:12:44.310
    TIMESTAMP_PATTERN = re.compile(
        r"(?:\d{4}-)?(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})"
    )

    # 匹配规则定义: (pattern, normalized_code, stage, severity, event_type, package_extractor)
    PATTERNS = [
        # Java 崩溃
        (
            r"FATAL EXCEPTION:\s*(.*)",
            "LOGCAT_FATAL_EXCEPTION",
            Stage.POST_REBOOT,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            1,  # 提取异常类型
        ),
        (
            r"Process:\s*(\S+),\s*PID:\s*(\d+)",
            "LOGCAT_PROCESS_CRASH",
            Stage.POST_REBOOT,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            1,  # 提取进程名
        ),
        # ANR 事件
        (
            r"ANR in\s+(\S+)",
            "LOGCAT_ANR",
            Stage.POST_REBOOT,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            1,  # 提取包名
        ),
        (
            r"ANRManager:\s+ANR in\s+(\S+)",
            "LOGCAT_ANR_DETECTED",
            Stage.POST_REBOOT,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            1,  # 提取包名
        ),
        # Native 崩溃
        (
            r"DEBUG\s*:\s*Abort message:\s*'(.*)'",
            "LOGCAT_NATIVE_ABORT",
            Stage.POST_REBOOT,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            1,  # 提取 abort 消息
        ),
        (
            r"signal\s+(\d+)\s+\(SIGSEGV|SIGABRT|SIGBUS|SIGFPE\)",
            "LOGCAT_NATIVE_CRASH",
            Stage.POST_REBOOT,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            None,
        ),
        # 系统服务崩溃
        (
            r"System.exit\(.*\)|system_server.*crashed",
            "LOGCAT_SYSTEM_CRASH",
            Stage.POST_REBOOT,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            None,
        ),
        # ADB 传输错误
        (
            r"ADB_TRANSPORT_ERROR|adb.*transport.*error",
            "ADB_TRANSPORT_ERROR",
            Stage.APPLY_UPDATE,
            Severity.ERROR,
            EventType.ERROR_SIGNAL,
            None,
        ),
        (
            r"device offline|DEVICE_OFFLINE",
            "DEVICE_OFFLINE_DURING_UPDATE",
            Stage.APPLY_UPDATE,
            Severity.ERROR,
            EventType.ERROR_SIGNAL,
            None,
        ),
        (
            r"connection refused.*adb|adb.*connection refused",
            "ADB_TRANSPORT_ERROR",
            Stage.APPLY_UPDATE,
            Severity.ERROR,
            EventType.ERROR_SIGNAL,
            None,
        ),
        (
            r"device disconnected|DEVICE_DISCONNECTED",
            "DEVICE_OFFLINE_DURING_UPDATE",
            Stage.APPLY_UPDATE,
            Severity.ERROR,
            EventType.ERROR_SIGNAL,
            None,
        ),
        # Watchdog 相关
        (
            r"Watchdog\s*!\s*Kill\s*(\S+)",
            "LOGCAT_WATCHDOG_KILL",
            Stage.POST_REBOOT,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            1,  # 提取被 kill 的进程名
        ),
        (
            r"watchdog.*timeout",
            "LOGCAT_WATCHDOG_TIMEOUT",
            Stage.POST_REBOOT,
            Severity.ERROR,
            EventType.ERROR_SIGNAL,
            None,
        ),
        # 启动完成
        (
            r"sys\.boot_completed=1",
            "LOGCAT_BOOT_COMPLETED",
            Stage.POST_REBOOT,
            Severity.INFO,
            EventType.VALIDATION_RESULT,
            None,
        ),
        # 启动失败相关
        (
            r"sys\.boot_completed not set within",
            "LOGCAT_BOOT_NOT_COMPLETED",
            Stage.POST_REBOOT,
            Severity.ERROR,
            EventType.VALIDATION_RESULT,
            None,
        ),
        (
            r"launcher not ready",
            "LOGCAT_LAUNCHER_NOT_READY",
            Stage.POST_REBOOT,
            Severity.ERROR,
            EventType.VALIDATION_RESULT,
            None,
        ),
    ]

    def parse(self, content: str, run_id: str) -> list[dict]:
        """解析 logcat 内容，返回事件字典列表。

        Args:
            content: logcat 输出内容
            run_id: 任务ID

        Returns:
            事件字典列表
        """
        events = []
        lines = content.splitlines()

        for line_no, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue

            # 尝试提取时间戳
            timestamp = self._extract_timestamp(line)

            # 遍历所有匹配规则
            for pattern_data in self.PATTERNS:
                pattern, normalized_code, stage, severity, event_type, pkg_group = pattern_data

                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    kv_payload = None

                    # 如果有提取器，提取相关信息
                    if pkg_group is not None and pkg_group <= len(match.groups()):
                        extracted_value = match.group(pkg_group)
                        if extracted_value:
                            kv_payload = {"extracted_info": extracted_value}

                    event = self.create_event(
                        run_id=run_id,
                        normalized_code=normalized_code,
                        message=line,
                        stage=stage,
                        event_type=event_type,
                        severity=severity,
                        timestamp=timestamp,
                        line_no=line_no,
                        raw_line=line,
                        kv_payload=kv_payload,
                    )
                    events.append(event)
                    break  # 每行只匹配一个规则

        return events

    def _extract_timestamp(self, line: str) -> Optional[str]:
        """从行中提取时间戳。

        Args:
            line: 日志行

        Returns:
            时间戳字符串或 None
        """
        match = self.TIMESTAMP_PATTERN.search(line)
        if match:
            # 返回完整匹配的时间戳部分
            return match.group(0)
        return None