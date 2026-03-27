"""报告模块。"""

from app.reporting.failure_classifier import FailureClassifier, FailureCategory
from app.reporting.generator import ReportGenerator, ReportData

__all__ = [
    "FailureClassifier",
    "FailureCategory",
    "ReportGenerator",
    "ReportData",
]