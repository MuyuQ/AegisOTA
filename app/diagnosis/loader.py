"""规则加载器。

从 YAML 文件和数据库加载诊断规则。
"""

import json
from pathlib import Path
from typing import Optional

import yaml
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.diagnostic import DiagnosticRule as DiagnosticRuleModel


class DiagnosticRule:
    """诊断规则 Pydantic 模型。

    用于规则匹配逻辑的规则表示。
    """

    def __init__(
        self,
        rule_id: str,
        name: str,
        category: str,
        priority: int = 50,
        enabled: bool = True,
        match_all: list[str] = [],
        match_any: list[str] = [],
        exclude_any: list[str] = [],
        match_stage: list[str] = [],
        root_cause: Optional[str] = None,
        base_confidence: float = 0.9,
        next_action: Optional[str] = None,
    ):
        self.rule_id = rule_id
        self.name = name
        self.priority = priority
        self.enabled = enabled
        self.match_all = match_all
        self.match_any = match_any
        self.exclude_any = exclude_any
        self.match_stage = match_stage
        self.category = category
        self.root_cause = root_cause
        self.base_confidence = base_confidence
        self.next_action = next_action

    def matches(
        self,
        event_codes: set[str],
        stage: Optional[str] = None,
    ) -> bool:
        """检查规则是否匹配给定的事件集合。

        Args:
            event_codes: 标准化代码集合
            stage: 当前阶段

        Returns:
            是否匹配
        """
        # 检查 match_all：所有代码都必须存在
        if self.match_all:
            if not all(code in event_codes for code in self.match_all):
                return False

        # 检查 match_any：至少一个代码存在（如果定义了 match_any）
        if self.match_any:
            if not any(code in event_codes for code in self.match_any):
                return False

        # 检查 exclude_any：所有代码都不应该存在
        if self.exclude_any:
            if any(code in event_codes for code in self.exclude_any):
                return False

        # 检查阶段匹配（如果定义了 match_stage）
        if self.match_stage and stage:
            if stage.lower() not in [s.lower() for s in self.match_stage]:
                return False

        # 如果没有定义任何匹配条件，默认不匹配
        if not self.match_all and not self.match_any:
            return False

        return True

    @classmethod
    def from_db_model(cls, db_rule: DiagnosticRuleModel) -> "DiagnosticRule":
        """从数据库模型创建 DiagnosticRule 实例。

        Args:
            db_rule: 数据库中的规则模型

        Returns:
            DiagnosticRule 实例
        """
        return cls(
            rule_id=db_rule.rule_id,
            name=db_rule.name,
            priority=db_rule.priority,
            enabled=db_rule.enabled,
            match_all=db_rule.get_match_all(),
            match_any=db_rule.get_match_any(),
            exclude_any=db_rule.get_exclude_any(),
            match_stage=db_rule.get_match_stage(),
            category=db_rule.category,
            root_cause=db_rule.root_cause,
            base_confidence=db_rule.base_confidence,
            next_action=db_rule.next_action,
        )


class RuleLoader:
    """规则加载器。

    支持从 YAML 文件和数据库加载诊断规则。
    """

    def __init__(
        self,
        rules_path: Optional[Path] = None,
        db_session: Optional[Session] = None,
    ):
        """初始化规则加载器。

        Args:
            rules_path: 规则 YAML 文件目录路径
            db_session: 数据库会话（可选）
        """
        settings = get_settings()
        self.rules_path = rules_path or settings.ARTIFACTS_DIR / "rules"
        self.db_session = db_session

    def load_from_yaml(self, path: str) -> list[dict]:
        """从 YAML 文件加载规则数据。

        Args:
            path: YAML 文件路径

        Returns:
            规则数据字典列表
        """
        file_path = self.rules_path / path

        if not file_path.exists():
            return []

        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "rules" not in data:
            return []

        return data["rules"]

    def load_rules(self, file_name: str = "core_rules.yaml") -> list[DiagnosticRule]:
        """从 YAML 文件加载规则。

        Args:
            file_name: 规则文件名

        Returns:
            规则列表
        """
        rule_data_list = self.load_from_yaml(file_name)

        rules = []
        for rule_data in rule_data_list:
            try:
                rule = DiagnosticRule(**rule_data)
                if rule.enabled:
                    rules.append(rule)
            except Exception:
                continue

        # 按优先级排序（高优先级在前）
        rules.sort(key=lambda r: r.priority, reverse=True)
        return rules

    def load_from_db(self) -> list[DiagnosticRule]:
        """从数据库加载规则。

        Returns:
            规则列表
        """
        if not self.db_session:
            return []

        db_rules = self.db_session.query(DiagnosticRuleModel).filter(
            DiagnosticRuleModel.enabled == True
        ).all()

        rules = [DiagnosticRule.from_db_model(db_rule) for db_rule in db_rules]

        # 按优先级排序
        rules.sort(key=lambda r: r.priority, reverse=True)
        return rules

    def load_all_rules(self) -> list[DiagnosticRule]:
        """加载所有规则（YAML 文件 + 数据库）。

        Returns:
            合并后的规则列表
        """
        all_rules = []

        # 从 YAML 文件加载
        if self.rules_path.exists():
            for yaml_file in self.rules_path.glob("*.yaml"):
                rules = self.load_rules(yaml_file.name)
                all_rules.extend(rules)

        # 从数据库加载
        db_rules = self.load_from_db()
        all_rules.extend(db_rules)

        # 去重：相同 rule_id 的规则，优先保留高优先级的
        rule_map: dict[str, DiagnosticRule] = {}
        for rule in all_rules:
            if rule.rule_id in rule_map:
                # 如果已存在，比较优先级
                existing = rule_map[rule.rule_id]
                if rule.priority > existing.priority:
                    rule_map[rule.rule_id] = rule
            else:
                rule_map[rule.rule_id] = rule

        # 按优先级排序
        result = list(rule_map.values())
        result.sort(key=lambda r: r.priority, reverse=True)
        return result

    def sync_yaml_to_db(self, file_name: str = "core_rules.yaml") -> int:
        """将 YAML 规则同步到数据库。

        Args:
            file_name: YAML 文件名

        Returns:
            同步的规则数量
        """
        if not self.db_session:
            return 0

        rule_data_list = self.load_from_yaml(file_name)
        synced_count = 0

        for rule_data in rule_data_list:
            try:
                # 查找现有规则
                existing = self.db_session.query(DiagnosticRuleModel).filter(
                    DiagnosticRuleModel.rule_id == rule_data["rule_id"]
                ).first()

                if existing:
                    # 更新现有规则
                    existing.name = rule_data["name"]
                    existing.priority = rule_data.get("priority", 50)
                    existing.enabled = rule_data.get("enabled", True)
                    existing.set_match_all(rule_data.get("match_all", []))
                    existing.set_match_any(rule_data.get("match_any", []))
                    existing.set_exclude_any(rule_data.get("exclude_any", []))
                    existing.set_match_stage(rule_data.get("match_stage", []))
                    existing.category = rule_data["category"]
                    existing.root_cause = rule_data.get("root_cause")
                    existing.base_confidence = rule_data.get("base_confidence", 0.9)
                    existing.next_action = rule_data.get("next_action")
                else:
                    # 创建新规则
                    new_rule = DiagnosticRuleModel(
                        rule_id=rule_data["rule_id"],
                        name=rule_data["name"],
                        priority=rule_data.get("priority", 50),
                        enabled=rule_data.get("enabled", True),
                        category=rule_data["category"],
                        root_cause=rule_data.get("root_cause"),
                        base_confidence=rule_data.get("base_confidence", 0.9),
                        next_action=rule_data.get("next_action"),
                    )
                    new_rule.set_match_all(rule_data.get("match_all", []))
                    new_rule.set_match_any(rule_data.get("match_any", []))
                    new_rule.set_exclude_any(rule_data.get("exclude_any", []))
                    new_rule.set_match_stage(rule_data.get("match_stage", []))
                    self.db_session.add(new_rule)

                synced_count += 1
            except Exception:
                continue

        self.db_session.commit()
        return synced_count