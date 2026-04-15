"""诊断规则引擎。

执行规则匹配和诊断评估。
"""

from typing import Optional

from app.diagnosis.confidence import (
    calculate_confidence,
    calculate_evidence_completeness,
    get_stage_order,
)
from app.diagnosis.loader import DiagnosticRule, RuleLoader
from app.models.enums import ResultStatus, Stage
from app.models.event import NormalizedEvent


class DiagnosticResultData:
    """诊断结果数据结构。

    用于返回诊断结果，不依赖 SQLAlchemy 模型。
    """

    def __init__(
        self,
        run_id: int,
        stage: Stage,
        category: str,
        root_cause: str,
        confidence: float,
        result_status: ResultStatus,
        key_evidence: list[str] = [],
        next_action: Optional[str] = None,
        matched_rules: list[DiagnosticRule] = [],
    ):
        self.run_id = run_id
        self.stage = stage
        self.category = category
        self.root_cause = root_cause
        self.confidence = confidence
        self.result_status = result_status
        self.key_evidence = key_evidence
        self.next_action = next_action
        self.matched_rules = matched_rules


class RuleEngine:
    """诊断规则引擎。

    执行事件与规则的匹配，返回诊断结果。
    """

    def __init__(self, rules: Optional[list[DiagnosticRule]] = None):
        """初始化规则引擎。

        Args:
            rules: 规则列表，如果为 None 则从默认位置加载
        """
        if rules is None:
            loader = RuleLoader()
            self.rules = loader.load_all_rules()
        else:
            self.rules = rules

    def match(
        self,
        events: list[NormalizedEvent],
        rules: Optional[list[DiagnosticRule]] = None,
    ) -> Optional[DiagnosticResultData]:
        """匹配事件与规则，返回诊断结果。

        Args:
            events: 标准化事件列表
            rules: 规则列表（可选，默认使用引擎加载的规则）

        Returns:
            诊断结果，如果没有匹配规则则返回 None
        """
        if not events:
            return None

        use_rules = rules or self.rules

        # 提取事件代码集合
        event_codes = {event.normalized_code for event in events}

        # 定定最后阶段
        stage = self._determine_stage(events)

        # 查找所有匹配的规则
        matched_rules = []
        for rule in use_rules:
            # 阶段预筛选：检查是否有事件落在规则指定的阶段
            if rule.match_stage:
                rule_stages = {s.lower() for s in rule.match_stage}
                has_matching_stage = any(e.stage.value.lower() in rule_stages for e in events)
                if not has_matching_stage:
                    continue

            # 检查事件代码匹配
            if rule.matches(event_codes, stage=None):
                matched_rules.append(rule)

        # 如果没有匹配规则，返回 None
        if not matched_rules:
            return None

        # 选择最佳规则
        primary_rule = self._select_best_rule(matched_rules, events)

        # 定定结果阶段
        if primary_rule.match_stage:
            result_stage = Stage(primary_rule.match_stage[0])
        else:
            result_stage = stage or Stage.PRECHECK

        # 计算置信度
        confidence = calculate_confidence(
            primary_rule,
            events,
            len(matched_rules),
        )

        # 提取关键证据
        key_evidence = self._extract_key_evidence(primary_rule, events)

        # 确定结果状态
        result_status = self._determine_result_status(primary_rule)

        # 获取 run_id（从第一个事件）
        run_id = events[0].run_id

        result = DiagnosticResultData(
            run_id=run_id,
            stage=result_stage,
            category=primary_rule.category,
            root_cause=primary_rule.root_cause or "unknown",
            confidence=confidence,
            result_status=result_status,
            key_evidence=key_evidence,
            next_action=primary_rule.next_action,
            matched_rules=matched_rules,
        )

        return result

    def evaluate(
        self,
        run_id: int,
        events: list[NormalizedEvent],
    ) -> tuple[DiagnosticResultData, list[DiagnosticRule]]:
        """对事件集执行规则匹配和诊断评估。

        Args:
            run_id: 任务 ID
            events: 标准化事件列表

        Returns:
            (诊断结果, 匹配的规则列表)
        """
        if not events:
            # 返回证据不足结果
            result = DiagnosticResultData(
                run_id=run_id,
                stage=Stage.PRECHECK,
                category="unknown",
                root_cause="insufficient_evidence",
                confidence=0.0,
                result_status=ResultStatus.INSUFFICIENT_EVIDENCE,
                key_evidence=[],
                next_action="collect more diagnostic evidence",
            )
            return result, []

        # 提取事件代码集合
        event_codes = {event.normalized_code for event in events}

        # 定定最后阶段
        stage = self._determine_stage(events)

        # 查找所有匹配的规则
        matched_rules = []
        for rule in self.rules:
            # 阶段预筛选
            if rule.match_stage:
                rule_stages = {s.lower() for s in rule.match_stage}
                has_matching_stage = any(e.stage.value.lower() in rule_stages for e in events)
                if not has_matching_stage:
                    continue

            # 检查事件代码匹配
            if rule.matches(event_codes, stage=None):
                matched_rules.append(rule)

        # 如果没有匹配规则，返回证据不足
        if not matched_rules:
            result = DiagnosticResultData(
                run_id=run_id,
                stage=stage or Stage.PRECHECK,
                category="unknown",
                root_cause="insufficient_evidence",
                confidence=0.0,
                result_status=ResultStatus.INSUFFICIENT_EVIDENCE,
                key_evidence=[e.raw_line for e in events if e.raw_line][:5],
                next_action="collect more diagnostic evidence",
            )
            return result, []

        # 选择最佳规则
        primary_rule = self._select_best_rule(matched_rules, events)

        # 确定结果阶段
        if primary_rule.match_stage:
            result_stage = Stage(primary_rule.match_stage[0])
        else:
            result_stage = stage or Stage.PRECHECK

        # 计算置信度
        confidence = calculate_confidence(
            primary_rule,
            events,
            len(matched_rules),
        )

        # 提取关键证据
        key_evidence = self._extract_key_evidence(primary_rule, events)

        # 确定结果状态
        result_status = self._determine_result_status(primary_rule)

        result = DiagnosticResultData(
            run_id=run_id,
            stage=result_stage,
            category=primary_rule.category,
            root_cause=primary_rule.root_cause or "unknown",
            confidence=confidence,
            result_status=result_status,
            key_evidence=key_evidence,
            next_action=primary_rule.next_action,
            matched_rules=matched_rules,
        )

        return result, matched_rules

    def determine_stage(self, events: list[NormalizedEvent]) -> Optional[Stage]:
        """确定诊断阶段（取最晚的阶段）。

        Args:
            events: 标准化事件列表

        Returns:
            最晚的阶段，如果没有事件则返回 PRECHECK
        """
        return self._determine_stage(events)

    def _determine_stage(self, events: list[NormalizedEvent]) -> Optional[Stage]:
        """确定诊断阶段（取最晚的阶段）。"""
        if not events:
            return Stage.PRECHECK

        stage_order = [
            Stage.PRECHECK,
            Stage.PACKAGE_PREPARE,
            Stage.APPLY_UPDATE,
            Stage.REBOOT_WAIT,
            Stage.POST_REBOOT,
            Stage.POST_VALIDATE,
        ]

        event_stages = {event.stage for event in events}
        for stage in reversed(stage_order):
            if stage in event_stages:
                return stage

        return Stage.PRECHECK

    def _select_best_rule(
        self,
        matched_rules: list[DiagnosticRule],
        events: list[NormalizedEvent],
    ) -> DiagnosticRule:
        """从匹配的规则中选择最佳规则。

        冲突消解策略：
        1. 优先级高的优先（priority 越大越优先）
        2. 晚阶段优先（后发生的阶段更可能是根本原因）
        3. 证据完整度优先（match_all 匹配比例越高越优先）
        """
        if len(matched_rules) == 1:
            return matched_rules[0]

        def get_rule_stage_order(rule: DiagnosticRule) -> int:
            """获取规则的阶段顺序（取第一个定义的阶段）。"""
            if rule.match_stage:
                try:
                    stage_str = rule.match_stage[0].upper()
                    return get_stage_order(Stage(stage_str))
                except ValueError:
                    return 0
            return 0

        # 按 priority 降序 -> stage_order 降序 -> evidence_completeness 降序 排序
        return sorted(
            matched_rules,
            key=lambda r: (
                -r.priority,  # 优先级高的优先
                -get_rule_stage_order(r),  # 后阶段优先
                -calculate_evidence_completeness(r, events),  # 证据完整度优先
            ),
        )[0]

    def _extract_key_evidence(
        self,
        rule: DiagnosticRule,
        events: list[NormalizedEvent],
    ) -> list[str]:
        """提取关键证据。"""
        evidence = []

        # 收集匹配事件作为证据
        matched_codes = set(rule.match_all + rule.match_any)
        for event in events:
            if event.normalized_code in matched_codes and event.raw_line:
                evidence.append(event.raw_line)

        # 最多返回5条
        return evidence[:5]

    def _determine_result_status(
        self,
        rule: DiagnosticRule,
    ) -> ResultStatus:
        """确定诊断结果状态。"""
        if rule.category == "success":
            return ResultStatus.PASSED

        if rule.category == "retryable_install_error":
            return ResultStatus.TRANSIENT_FAILURE

        return ResultStatus.FAILED
