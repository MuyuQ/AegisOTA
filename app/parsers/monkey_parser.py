"""Monkey测试输出解析器。

解析 monkey 测试输出，提取崩溃、ANR 等稳定性事件。
"""

import re
from typing import Optional

from app.parsers.base import BaseParser, Stage, SourceType, EventType, Severity


class MonkeyParser(BaseParser):
    """Monkey 测试输出解析器。

    解析 monkey 测试输出中的关键事件，包括：
    - 应用崩溃 (CRASH)
    - ANR (Application Not Responding)
    - 安全异常 (SecurityException)
    - Monkey 中止事件
    """

    source_type = SourceType.MONKEY_OUTPUT
    default_stage = Stage.POST_VALIDATE
    default_event_type = EventType.VALIDATION_RESULT
    default_severity = Severity.INFO

    # 时间戳格式: [2026-03-28 15:12:44.310]
    TIMESTAMP_PATTERN = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\]")

    # 匹配规则定义: (pattern, normalized_code, stage, severity, event_type, package_extractor)
    PATTERNS = [
        # 崩溃事件
        (
            r"CRASH:\s*(\S+)",
            "MONKEY_CRASH",
            Stage.POST_VALIDATE,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            1,  # 提取包名
        ),
        (
            r"// CRASH:\s*(\S+)",
            "MONKEY_CRASH_COMMENT",
            Stage.POST_VALIDATE,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            1,  # 提取包名（注释格式）
        ),
        # ANR 事件
        (
            r"ANR in\s+(\S+)",
            "MONKEY_ANR",
            Stage.POST_VALIDATE,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            1,  # 提取包名
        ),
        (
            r"// ANR:\s*(\S+)",
            "MONKEY_ANR_COMMENT",
            Stage.POST_VALIDATE,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            1,  # 提取包名（注释格式）
        ),
        # 安全异常
        (
            r"SecurityException",
            "MONKEY_SECURITY_EXCEPTION",
            Stage.POST_VALIDATE,
            Severity.ERROR,
            EventType.ERROR_SIGNAL,
            None,
        ),
        # Monkey 中止
        (
            r"Monkey aborted",
            "MONKEY_ABORTED",
            Stage.POST_VALIDATE,
            Severity.ERROR,
            EventType.ERROR_SIGNAL,
            None,
        ),
        (
            r"System crash",
            "MONKEY_SYSTEM_CRASH",
            Stage.POST_VALIDATE,
            Severity.CRITICAL,
            EventType.ERROR_SIGNAL,
            None,
        ),
        # 执行统计
        (
            r"Events injected:\s*(\d+)",
            "MONKEY_EVENTS_INJECTED",
            Stage.POST_VALIDATE,
            Severity.INFO,
            EventType.PROGRESS_SIGNAL,
            1,  # 提取事件数量
        ),
        (
            r"Dropped:\s*(\d+)",
            "MONKEY_EVENTS_DROPPED",
            Stage.POST_VALIDATE,
            Severity.WARNING,
            EventType.PROGRESS_SIGNAL,
            1,  # 提取丢弃数量
        ),
        # 完成状态
        (
            r"Monkey finished",
            "MONKEY_FINISHED",
            Stage.POST_VALIDATE,
            Severity.INFO,
            EventType.VALIDATION_RESULT,
            None,
        ),
        (
            r"Monkey stopped",
            "MONKEY_STOPPED",
            Stage.POST_VALIDATE,
            Severity.INFO,
            EventType.VALIDATION_RESULT,
            None,
        ),
    ]

    def parse(self, content: str, run_id: str) -> list[dict]:
        """解析 monkey 测试输出内容，返回事件字典列表。

        Args:
            content: monkey 测试输出内容
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
                            kv_payload = {"package": extracted_value}

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
            return match.group(1)
        return None

    def get_summary(self, events: list[dict]) -> dict:
        """从解析的事件中生成测试摘要。

        Args:
            events: 解析的事件列表

        Returns:
            测试摘要字典，包含：
            - total_crashes: 崩溃总数
            - total_anrs: ANR 总数
            - events_injected: 注入事件数
            - events_dropped: 丢弃事件数
            - passed: 是否通过
            - crash_packages: 崩溃包名列表
            - anr_packages: ANR 包名列表
        """
        total_crashes = 0
        total_anrs = 0
        events_injected = 0
        events_dropped = 0
        crash_packages = []
        anr_packages = []

        for event in events:
            code = event.get("normalized_code", "")
            kv_payload = event.get("kv_payload", {})

            # 统计崩溃
            if code.startswith("MONKEY_CRASH"):
                total_crashes += 1
                if "package" in kv_payload:
                    crash_packages.append(kv_payload["package"])

            # 统计 ANR
            if code.startswith("MONKEY_ANR"):
                total_anrs += 1
                if "package" in kv_payload:
                    anr_packages.append(kv_payload["package"])

            # 统计注入事件
            if code == "MONKEY_EVENTS_INJECTED":
                if kv_payload and "package" in kv_payload:
                    try:
                        events_injected = int(kv_payload["package"])
                    except ValueError:
                        pass

            # 统计丢弃事件
            if code == "MONKEY_EVENTS_DROPPED":
                if kv_payload and "package" in kv_payload:
                    try:
                        events_dropped = int(kv_payload["package"])
                    except ValueError:
                        pass

        # 判断是否通过
        passed = total_crashes == 0 and total_anrs == 0

        return {
            "total_crashes": total_crashes,
            "total_anrs": total_anrs,
            "events_injected": events_injected,
            "events_dropped": events_dropped,
            "passed": passed,
            "crash_packages": crash_packages,
            "anr_packages": anr_packages,
        }