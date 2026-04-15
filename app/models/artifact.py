"""执行产物数据模型。"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from app.models.run import RunSession, RunStep

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ArtifactType(str, Enum):
    """产物类型枚举。"""

    LOGCAT = "logcat"
    STDOUT = "stdout"
    STDERR = "stderr"
    SCREENSHOT = "screenshot"
    MONKEY_RESULT = "monkey_result"
    PERF_DATA = "perf_data"
    REPORT = "report"
    TIMELINE = "timeline"


class Artifact(Base):
    """执行产物实体。

    存储任务执行过程中产生的日志、截图等文件。
    """

    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("run_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("run_steps.id", ondelete="SET NULL"), nullable=True
    )

    # 文件信息
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # 元数据（JSON 存储）
    artifact_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # 关系
    run_session: Mapped["RunSession"] = relationship("RunSession", back_populates="artifacts")
    step: Mapped[Optional["RunStep"]] = relationship("RunStep")

    def get_metadata(self) -> dict[str, Any]:
        """获取产物元数据。"""
        if not self.artifact_metadata:
            return {}
        try:
            return json.loads(self.artifact_metadata)
        except json.JSONDecodeError:
            return {}

    def set_metadata(self, meta: dict[str, Any]) -> None:
        """设置产物元数据。"""
        self.artifact_metadata = json.dumps(meta) if meta else None
