"""置信度计算模块。

提供诊断置信度的多因素评分计算。
"""

from typing import TYPE_CHECKING

from app.models.enums import Stage

if TYPE_CHECKING:
    from app.diagnosis.loader import DiagnosticRule
    from app.models.event import NormalizedEvent


# 置信度配置常量
CONFIDENCE_STAGE_SPAN_THRESHOLD = 3  # 阶段跨度加分阈值
CONFIDENCE_STAGE_SPAN_BONUS = 0.05  # 阶段跨度加分值
CONFIDENCE_MULTI_SOURCE_THRESHOLD = 2  # 多来源加分阈值
CONFIDENCE_MULTI_SOURCE_BONUS = 0.03  # 多来源加分值
CONFIDENCE_EVIDENCE_COUNT_THRESHOLD = 3  # 关键证据数量加分阈值
CONFIDENCE_EVIDENCE_COUNT_BONUS = 0.02  # 关键证据数量加分值
CONFIDENCE_CONFlict_PENALTY = 0.05  # 多规则冲突扣分系数


def calculate_confidence(
    rule: "DiagnosticRule",
    events: list["NormalizedEvent"],
    matched_rules_count: int = 1,
) -> float:
    """计算诊断置信度。

    评分因素：
    1. 基础置信度（规则定义）
    2. 加分项：
       - 阶段连续性：事件跨越多个连续阶段
       - 多来源事件：来自不同日志源的事件
       - 关键证据数量充足
    3. 扣分项：
       - 多规则冲突

    Args:
        rule: 匹配的诊断规则
        events: 标准化事件列表
        matched_rules_count: 匹配的规则数量

    Returns:
        置信度值（0.0 - 1.0）
    """
    confidence = rule.base_confidence

    # 加分项1：阶段连续性（事件覆盖连续阶段）
    stage_order = [
        Stage.PRECHECK,
        Stage.PACKAGE_PREPARE,
        Stage.APPLY_UPDATE,
        Stage.REBOOT_WAIT,
        Stage.POST_REBOOT,
        Stage.POST_VALIDATE,
    ]

    event_stages = sorted(
        [event.stage for event in events],
        key=lambda s: stage_order.index(s) if s in stage_order else 0,
    )

    # 计算阶段跨度（连续阶段数）
    if event_stages:
        unique_stages = list(dict.fromkeys(event_stages))  # 保持顺序去重
        stage_span = len(unique_stages)
        if stage_span >= CONFIDENCE_STAGE_SPAN_THRESHOLD:
            confidence = min(1.0, confidence + CONFIDENCE_STAGE_SPAN_BONUS)

    # 加分项2：多来源事件（来自不同日志源）
    event_sources = {event.source_type for event in events}
    if len(event_sources) >= CONFIDENCE_MULTI_SOURCE_THRESHOLD:
        confidence = min(1.0, confidence + CONFIDENCE_MULTI_SOURCE_BONUS)

    # 加分项3：关键证据数量充足
    matched_codes = set(rule.match_all + rule.match_any)
    matched_events = [e for e in events if e.normalized_code in matched_codes]
    if len(matched_events) >= CONFIDENCE_EVIDENCE_COUNT_THRESHOLD:
        confidence = min(1.0, confidence + CONFIDENCE_EVIDENCE_COUNT_BONUS)

    # 扣分项：多规则冲突（存在竞争规则）
    if matched_rules_count > 1:
        confidence = max(
            0.0,
            confidence - CONFIDENCE_CONFlict_PENALTY * (matched_rules_count - 1)
        )

    return round(confidence, 2)


def get_stage_order(stage: Stage) -> int:
    """获取阶段的顺序值。

    Args:
        stage: 阶段枚举值

    Returns:
        阶段顺序值（越大越靠后）
    """
    stage_order_map = {
        Stage.PRECHECK: 0,
        Stage.PACKAGE_PREPARE: 1,
        Stage.APPLY_UPDATE: 2,
        Stage.REBOOT_WAIT: 3,
        Stage.POST_REBOOT: 4,
        Stage.POST_VALIDATE: 5,
    }
    return stage_order_map.get(stage, 0)


def calculate_evidence_completeness(
    rule: "DiagnosticRule",
    events: list["NormalizedEvent"],
) -> float:
    """计算规则的证据完整度。

    Args:
        rule: 诊断规则
        events: 事件列表

    Returns:
        证据完整度（match_all 匹配比例，0.0 - 1.0）
    """
    if not rule.match_all:
        return 1.0  # 无 match_all 约束，视为完整匹配

    # 计算已匹配的唯一代码数量
    matched_codes = {
        e.normalized_code for e in events
        if e.normalized_code in rule.match_all
    }
    return len(matched_codes) / len(rule.match_all)