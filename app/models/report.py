"""报告数据模型。"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.run import FailureCategory


class ReportFormat(str, Enum):
    """报告格式枚举。"""

    JSON = "json"
    HTML = "html"
    MARKDOWN = "markdown"


class ReportStatus(str, Enum):
    """报告状态枚举。"""

    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Report(Base):
    """报告实体。

    存储任务执行完成后生成的报告。
    """

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("run_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 报告信息
    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    format: Mapped[str] = mapped_column(String(16), nullable=False, default=ReportFormat.JSON)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ReportStatus.GENERATING
    )

    # 文件路径
    content_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # 失败分析
    failure_category: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    failure_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 统计信息
    total_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 执行时间
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)

    # 时间戳
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 关系
    run_session: Mapped["RunSession"] = relationship("RunSession", back_populates="reports")

    def is_complete(self) -> bool:
        """检查报告是否已完成。"""
        return self.status == ReportStatus.COMPLETED

    def get_success_rate(self) -> float:
        """计算步骤成功率。"""
        if self.total_steps == 0:
            return 0.0
        return self.passed_steps / self.total_steps * 100