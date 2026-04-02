"""诊断规则引擎模块。

提供故障诊断的核心功能：
- 规则加载 (loader)
- 规则匹配 (engine)
- 置信度计算 (confidence)
- 相似案例召回 (similar)
"""

from app.diagnosis.confidence import calculate_confidence
from app.diagnosis.engine import DiagnosticResultData, RuleEngine
from app.diagnosis.loader import DiagnosticRule, RuleLoader
from app.diagnosis.similar import SimilarCaseService

__all__ = [
    "RuleEngine",
    "RuleLoader",
    "DiagnosticRule",
    "DiagnosticResultData",
    "calculate_confidence",
    "SimilarCaseService",
]