"""诊断相关数据模型。"""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.run import RunSession


class NormalizedEvent(Base):
    """标准化事件。

    解析后的日志事件，统一格式存储。
    """

    __tablename__ = "normalized_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("run_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 来源信息
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # recovery_log/update_engine/logcat/monkey

    # 事件属性
    stage: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # precheck/apply_update/reboot_wait/post_validate
    event_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # error_signal/status_transition/progress_signal
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # info/warning/error/critical
    normalized_code: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # 标准化错误码

    # 原始数据
    raw_line: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 扩展数据（JSON 存储额外键值对）
    kv_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # 关系
    run_session: Mapped["RunSession"] = relationship("RunSession")

    def get_kv_payload(self) -> dict[str, Any]:
        """获取键值对载荷。"""
        if not self.kv_payload:
            return {}
        try:
            return json.loads(self.kv_payload)
        except json.JSONDecodeError:
            return {}

    def set_kv_payload(self, payload: dict[str, Any]) -> None:
        """设置键值对载荷。"""
        self.kv_payload = json.dumps(payload) if payload else None


# 复合索引：按任务和阶段查询事件
Index("ix_normalized_events_run_id_stage", NormalizedEvent.run_id, NormalizedEvent.stage)
Index("ix_normalized_events_run_id_severity", NormalizedEvent.run_id, NormalizedEvent.severity)


class DiagnosticResult(Base):
    """诊断结果。

    诊断执行的最终结果，每个任务只有一条诊断结果。
    """

    __tablename__ = "diagnostic_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("run_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    device_serial: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # 诊断结论
    stage: Mapped[str] = mapped_column(String(32), nullable=False)  # 失败阶段
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # 故障分类
    root_cause: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # 根因标识
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 置信度 0.0-1.0
    result_status: Mapped[str] = mapped_column(
        String(16), nullable=False
    )  # passed/failed/transient_failure

    # 关键信息（JSON 数组，关键日志行）
    key_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 相似案例（JSON 数组）
    similar_cases: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # 关系
    run_session: Mapped["RunSession"] = relationship("RunSession")
    rule_hits: Mapped[list["RuleHit"]] = relationship(
        "RuleHit", back_populates="result", cascade="all, delete-orphan"
    )

    def get_key_evidence(self) -> list[dict[str, Any]]:
        """获取关键证据列表。"""
        if not self.key_evidence:
            return []
        try:
            return json.loads(self.key_evidence)
        except json.JSONDecodeError:
            return []

    def set_key_evidence(self, evidence: list[dict[str, Any]]) -> None:
        """设置关键证据列表。"""
        self.key_evidence = json.dumps(evidence) if evidence else None

    def get_similar_cases(self) -> list[dict[str, Any]]:
        """获取相似案例列表。"""
        if not self.similar_cases:
            return []
        try:
            return json.loads(self.similar_cases)
        except json.JSONDecodeError:
            return []

    def set_similar_cases(self, cases: list[dict[str, Any]]) -> None:
        """设置相似案例列表。"""
        self.similar_cases = json.dumps(cases) if cases else None


# 复合索引：按分类和根因查询
Index(
    "ix_diagnostic_results_category_root_cause",
    DiagnosticResult.category,
    DiagnosticResult.root_cause,
)


class RuleHit(Base):
    """规则命中记录。

    记录哪些规则被匹配，用于追溯诊断依据。
    """

    __tablename__ = "rule_hits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("run_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    result_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("diagnostic_results.id", ondelete="CASCADE"), nullable=False, index=True
    )

    rule_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(64), nullable=False)

    # 匹配的事件码（JSON 数组）
    matched_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    base_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # 关系
    result: Mapped["DiagnosticResult"] = relationship(
        "DiagnosticResult", back_populates="rule_hits"
    )

    def get_matched_codes(self) -> list[str]:
        """获取匹配的事件码列表。"""
        if not self.matched_codes:
            return []
        try:
            return json.loads(self.matched_codes)
        except json.JSONDecodeError:
            return []

    def set_matched_codes(self, codes: list[str]) -> None:
        """设置匹配的事件码列表。"""
        self.matched_codes = json.dumps(codes) if codes else None


# 复合索引：按规则 ID 查询命中记录
Index("ix_rule_hits_rule_id_priority", RuleHit.rule_id, RuleHit.priority)


class DiagnosticRule(Base):
    """诊断规则。

    可编辑的诊断规则定义，支持从 YAML 导入。
    """

    __tablename__ = "diagnostic_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 匹配条件（JSON 数组）
    match_all: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 全部匹配
    match_any: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 任一匹配
    exclude_any: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 排除条件
    match_stage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 阶段匹配

    # 结论
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    root_cause: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    base_confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def get_match_all(self) -> list[str]:
        """获取全部匹配条件列表。"""
        if not self.match_all:
            return []
        try:
            return json.loads(self.match_all)
        except json.JSONDecodeError:
            return []

    def set_match_all(self, codes: list[str]) -> None:
        """设置全部匹配条件列表。"""
        self.match_all = json.dumps(codes) if codes else None

    def get_match_any(self) -> list[str]:
        """获取任一匹配条件列表。"""
        if not self.match_any:
            return []
        try:
            return json.loads(self.match_any)
        except json.JSONDecodeError:
            return []

    def set_match_any(self, codes: list[str]) -> None:
        """设置任一匹配条件列表。"""
        self.match_any = json.dumps(codes) if codes else None

    def get_exclude_any(self) -> list[str]:
        """获取排除条件列表。"""
        if not self.exclude_any:
            return []
        try:
            return json.loads(self.exclude_any)
        except json.JSONDecodeError:
            return []

    def set_exclude_any(self, codes: list[str]) -> None:
        """设置排除条件列表。"""
        self.exclude_any = json.dumps(codes) if codes else None

    def get_match_stage(self) -> list[str]:
        """获取阶段匹配条件列表。"""
        if not self.match_stage:
            return []
        try:
            return json.loads(self.match_stage)
        except json.JSONDecodeError:
            return []

    def set_match_stage(self, stages: list[str]) -> None:
        """设置阶段匹配条件列表。"""
        self.match_stage = json.dumps(stages) if stages else None


# 复合索引：按优先级和启用状态查询
Index("ix_diagnostic_rules_priority_enabled", DiagnosticRule.priority, DiagnosticRule.enabled)


class SimilarCaseIndex(Base):
    """相似案例索引。

    用于快速检索历史相似案例。
    """

    __tablename__ = "similar_case_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("run_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    device_serial: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # 索引字段
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    root_cause: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key_evidence_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # MD5 哈希

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # 关系
    run_session: Mapped["RunSession"] = relationship("RunSession")


# 复合索引：按分类和根因检索相似案例
Index(
    "ix_similar_case_index_category_root_cause_hash",
    SimilarCaseIndex.category,
    SimilarCaseIndex.root_cause,
    SimilarCaseIndex.key_evidence_hash,
)
