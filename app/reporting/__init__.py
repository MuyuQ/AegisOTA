"""报告模块。"""

from app.reporting.failure_classifier import FailureCategory, FailureClassifier
from app.reporting.generator import ReportData, ReportGenerator

__all__ = [
    "FailureClassifier",
    "FailureCategory",
    "ReportGenerator",
    "ReportData",
]
