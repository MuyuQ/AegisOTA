"""标准化事件模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.enums import EventType, Severity, SourceType, Stage


class NormalizedEvent(BaseModel):
    """标准化事件Pydantic模型。

    用于表示从各种日志源解析并标准化后的事件。
    """

    id: Optional[int] = None
    run_id: int
    device_serial: Optional[str] = None
    source_type: SourceType
    timestamp: Optional[datetime] = None
    line_no: Optional[int] = None
    raw_line: Optional[str] = None
    stage: Stage
    event_type: EventType
    severity: Severity
    normalized_code: str
    message: Optional[str] = None
    kv_payload: Optional[dict] = None
