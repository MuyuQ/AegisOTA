"""事件标准化器。

将原始解析事件转换为标准化的 NormalizedEvent 记录。
"""

from datetime import datetime
from typing import Any

from app.models.enums import EventType, Severity, SourceType, Stage
from app.models.event import NormalizedEvent


class EventNormalizer:
    """事件标准化器。

    负责将原始解析事件转换为标准化的 NormalizedEvent 记录，
    包括阶段映射、严重级别计算和载荷提取。
    """

    # 阶段映射表：原始阶段名 -> 标准阶段
    STAGE_MAPPING: dict[str, Stage] = {
        # Update Engine 状态映射
        "DOWNLOADING": Stage.APPLY_UPDATE,
        "VERIFYING": Stage.APPLY_UPDATE,
        "FINALIZING": Stage.APPLY_UPDATE,
        "UPDATED_NEED_REBOOT": Stage.REBOOT_WAIT,
        # Recovery 阶段映射
        "RECOVERY": Stage.APPLY_UPDATE,
        "INSTALLING": Stage.APPLY_UPDATE,
        # 启动后阶段
        "BOOT": Stage.POST_REBOOT,
        "POST_BOOT": Stage.POST_REBOOT,
        "MONKEY": Stage.POST_VALIDATE,
        "VALIDATION": Stage.POST_VALIDATE,
        # 预检查阶段
        "PRECHECK": Stage.PRECHECK,
        "ENVIRONMENT_CHECK": Stage.PRECHECK,
        "BATTERY_CHECK": Stage.PRECHECK,
        # 包准备阶段
        "PACKAGE_PREPARE": Stage.PACKAGE_PREPARE,
        "PUSH_PACKAGE": Stage.PACKAGE_PREPARE,
        "DP_PREPARE": Stage.PACKAGE_PREPARE,
    }

    # 严重级别映射表：原始严重级别 -> 标准严重级别
    SEVERITY_MAPPING: dict[str, Severity] = {
        "I": Severity.INFO,
        "INFO": Severity.INFO,
        "W": Severity.WARNING,
        "WARNING": Severity.WARNING,
        "WARN": Severity.WARNING,
        "E": Severity.ERROR,
        "ERROR": Severity.ERROR,
        "ERR": Severity.ERROR,
        "F": Severity.CRITICAL,
        "FATAL": Severity.CRITICAL,
        "CRITICAL": Severity.CRITICAL,
        "C": Severity.CRITICAL,
    }

    def normalize(
        self, run_id: int, source_type: str, events: list[dict[str, Any]]
    ) -> list[NormalizedEvent]:
        """
        对原始事件列表进行标准化处理。

        Args:
            run_id: 关联的任务运行ID
            source_type: 日志来源类型
            events: 原始事件字典列表

        Returns:
            标准化后的事件列表
        """
        source = SourceType(source_type) if source_type else None
        normalized_events = []

        for event in events:
            normalized = self._normalize_single(run_id, source, event)
            if normalized:
                # 二次调整：阶段和严重级别
                normalized = self._adjust_stage(normalized)
                normalized = self._adjust_severity(normalized)
                normalized_events.append(normalized)

        return normalized_events

    def _normalize_single(
        self, run_id: int, source: SourceType | None, event: dict[str, Any]
    ) -> NormalizedEvent | None:
        """
        标准化单个事件。

        Args:
            run_id: 任务运行ID
            source: 日志来源类型
            event: 原始事件字典

        Returns:
            标准化事件，如果事件无效则返回None
        """
        # 提取必要字段
        normalized_code = event.get("normalized_code") or event.get("code", "UNKNOWN")
        if not normalized_code:
            return None

        # 解析阶段
        raw_stage = event.get("stage", "precheck")
        stage = self.normalize_stage(raw_stage)

        # 解析事件类型
        raw_event_type = event.get("event_type", "status_transition")
        event_type = self._normalize_event_type(raw_event_type)

        # 解析严重级别
        raw_severity = event.get("severity", "info")
        severity = self.normalize_severity(raw_severity)

        # 解析时间戳
        timestamp = self._extract_timestamp(event)

        # 提取 kv_payload
        kv_payload = self.extract_kv_payload(event)

        return NormalizedEvent(
            run_id=run_id,
            device_serial=event.get("device_serial"),
            source_type=source or SourceType.DEVICE_RUNTIME_LOG,
            timestamp=timestamp,
            line_no=event.get("line_no"),
            raw_line=event.get("raw_line"),
            stage=stage,
            event_type=event_type,
            severity=severity,
            normalized_code=normalized_code,
            message=event.get("message"),
            kv_payload=kv_payload if kv_payload else None,
        )

    def normalize_stage(self, raw_stage: str) -> Stage:
        """
        将原始阶段名映射到标准阶段。

        Args:
            raw_stage: 原始阶段名

        Returns:
            标准阶段枚举值
        """
        if not raw_stage:
            return Stage.PRECHECK

        # 直接匹配
        if raw_stage.upper() in [s.value.upper() for s in Stage]:
            return Stage(raw_stage.lower())

        # 查找映射表
        upper_stage = raw_stage.upper()
        for key, stage in self.STAGE_MAPPING.items():
            if upper_stage.startswith(key) or key in upper_stage:
                return stage

        # 默认返回 PRECHECK
        return Stage.PRECHECK

    def normalize_severity(self, raw_severity: str) -> Severity:
        """
        将原始严重级别映射到标准严重级别。

        Args:
            raw_severity: 原始严重级别

        Returns:
            标准严重级别枚举值
        """
        if not raw_severity:
            return Severity.INFO

        # 直接匹配
        upper_severity = raw_severity.upper()
        if upper_severity in [s.value.upper() for s in Severity]:
            return Severity(raw_severity.lower())

        # 查找映射表
        for key, severity in self.SEVERITY_MAPPING.items():
            if upper_severity == key.upper() or upper_severity.startswith(key.upper()):
                return severity

        # 默认返回 INFO
        return Severity.INFO

    def extract_kv_payload(self, event: dict[str, Any]) -> dict[str, Any]:
        """
        从事件中提取键值对载荷。

        排除已知的标准字段，其余字段作为 kv_payload。

        Args:
            event: 原始事件字典

        Returns:
            键值对载荷字典
        """
        # 已知的标准字段，不应包含在 kv_payload 中
        standard_fields = {
            "normalized_code",
            "code",
            "stage",
            "event_type",
            "severity",
            "timestamp",
            "message",
            "device_serial",
            "line_no",
            "raw_line",
            "run_id",
            "source_type",
        }

        kv_payload = {}
        for key, value in event.items():
            if key not in standard_fields and value is not None:
                kv_payload[key] = value

        return kv_payload

    def _normalize_event_type(self, raw_event_type: str) -> EventType:
        """
        将原始事件类型映射到标准事件类型。

        Args:
            raw_event_type: 原始事件类型

        Returns:
            标准事件类型枚举值
        """
        if not raw_event_type:
            return EventType.STATUS_TRANSITION

        # 直接匹配
        lower_type = raw_event_type.lower()
        try:
            return EventType(lower_type)
        except ValueError:
            pass

        # 关键字匹配
        if "error" in lower_type or "fail" in lower_type:
            return EventType.ERROR_SIGNAL
        elif "progress" in lower_type or "status" in lower_type:
            return EventType.PROGRESS_SIGNAL
        elif "validation" in lower_type or "check" in lower_type:
            return EventType.VALIDATION_RESULT
        elif "summary" in lower_type:
            return EventType.SUMMARY_SIGNAL
        elif "environment" in lower_type:
            return EventType.ENVIRONMENT_CHECK

        return EventType.STATUS_TRANSITION

    def _extract_timestamp(self, event: dict[str, Any]) -> datetime | None:
        """
        从事件中提取时间戳。

        Args:
            event: 原始事件字典

        Returns:
            解析后的时间戳，如果无法解析则返回None
        """
        timestamp = event.get("timestamp")
        if timestamp is None:
            return None

        if isinstance(timestamp, datetime):
            return timestamp

        if isinstance(timestamp, str):
            # 尝试多种格式解析
            formats = [
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%m-%d %H:%M:%S.%f",
                "%m-%d %H:%M:%S",
                "%H:%M:%S.%f",
                "%H:%M:%S",
            ]
            for fmt in formats:
                try:
                    return datetime.strptime(timestamp, fmt)
                except ValueError:
                    continue

        if isinstance(timestamp, (int, float)):
            # Unix 时间戳
            try:
                return datetime.fromtimestamp(timestamp)
            except (OSError, OverflowError):
                pass

        return None

    def _adjust_stage(self, event: NormalizedEvent) -> NormalizedEvent:
        """
        根据事件代码调整阶段。

        使用 model_copy 创建新对象，保持函数式风格。

        Args:
            event: 原始事件

        Returns:
            调整阶段后的事件副本（如需调整），否则返回原事件
        """
        code = event.normalized_code
        new_stage: Stage | None = None

        # 根据normalized_code确定新阶段
        if code.startswith("UE_STATUS_DOWNLOADING") or code.startswith("UE_STATUS_VERIFYING"):
            new_stage = Stage.APPLY_UPDATE
        elif code.startswith("UE_STATUS_FINALIZING"):
            new_stage = Stage.APPLY_UPDATE
        elif code.startswith("UE_STATUS_UPDATED_NEED_REBOOT"):
            new_stage = Stage.REBOOT_WAIT
        elif code == "BOOT_NOT_COMPLETED" or code == "LAUNCHER_NOT_READY":
            new_stage = Stage.POST_REBOOT
        elif code == "MONKEY_FATAL_EVENT":
            new_stage = Stage.POST_VALIDATE
        elif code in ("RECOVERY_LOW_BATTERY", "RECOVERY_BOOTREASON_BLOCKED"):
            new_stage = Stage.PRECHECK
        elif code == "RECOVERY_INSTALL_ABORTED":
            new_stage = Stage.APPLY_UPDATE
        elif code == "DP_ALLOCATABLE_SPACE_EXCEEDED":
            new_stage = Stage.PACKAGE_PREPARE

        # 使用 model_copy 创建新对象
        if new_stage is not None:
            return event.model_copy(update={"stage": new_stage})
        return event

    def _adjust_severity(self, event: NormalizedEvent) -> NormalizedEvent:
        """
        根据事件代码调整严重级别。

        使用 model_copy 创建新对象，保持函数式风格。

        Args:
            event: 原始事件

        Returns:
            调整严重级别后的事件副本（如需调整），否则返回原事件
        """
        code = event.normalized_code
        new_severity: Severity | None = None

        # 根据normalized_code确定新严重级别
        if code in ("RECOVERY_LOW_BATTERY", "RECOVERY_BOOTREASON_BLOCKED"):
            new_severity = Severity.ERROR
        elif code == "RECOVERY_INSTALL_ABORTED":
            new_severity = Severity.ERROR
        elif code == "DP_ALLOCATABLE_SPACE_EXCEEDED":
            new_severity = Severity.ERROR
        elif code in ("BOOT_NOT_COMPLETED", "LAUNCHER_NOT_READY"):
            new_severity = Severity.ERROR
        elif code == "MONKEY_FATAL_EVENT":
            new_severity = Severity.CRITICAL

        # 使用 model_copy 创建新对象
        if new_severity is not None:
            return event.model_copy(update={"severity": new_severity})
        return event