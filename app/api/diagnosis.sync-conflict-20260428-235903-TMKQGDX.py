"""诊断 API 路由。

提供诊断记录查询、手动触发诊断、日志导出、规则管理等功能。
"""

from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.diagnosis.similar import SimilarCaseService
from app.executors.adb_executor import ADBExecutor
from app.models.diagnostic import (
    DiagnosticResult,
    NormalizedEvent,
    RuleHit,
    SimilarCaseIndex,
)
from app.models.diagnostic import (
    DiagnosticRule as DiagnosticRuleModel,
)
from app.models.run import RunSession
from app.services.diagnosis_service import DiagnosisService
from app.services.log_export_service import LogExportService

router = APIRouter(prefix="/api/v1/diagnosis", tags=["diagnosis"])


# === Pydantic 响应模型 ===


class NormalizedEventResponse(BaseModel):
    """标准化事件响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    source_type: str
    stage: str
    event_type: str
    severity: str
    normalized_code: str
    raw_line: Optional[str] = None
    line_no: Optional[int] = None
    timestamp: Optional[datetime] = None
    kv_payload: Optional[dict[str, Any]] = None
    created_at: datetime


class RuleHitResponse(BaseModel):
    """规则命中记录响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    result_id: int
    rule_id: str
    rule_name: str
    matched_codes: List[str] = []
    priority: int
    base_confidence: float
    created_at: datetime


class DiagnosticResultResponse(BaseModel):
    """诊断结果响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    device_serial: str
    stage: str
    category: str
    root_cause: str
    confidence: float
    result_status: str
    key_evidence: List[dict[str, Any]] = []
    next_action: Optional[str] = None
    similar_cases: List[dict[str, Any]] = []
    created_at: datetime


class DiagnosisDetailResponse(BaseModel):
    """诊断详情响应模型。"""

    result: DiagnosticResultResponse
    events: List[NormalizedEventResponse] = []
    rule_hits: List[RuleHitResponse] = []


class DiagnosticResultListItem(BaseModel):
    """诊断结果列表项模型。"""

    id: int
    run_id: int
    device_serial: str
    category: str
    root_cause: str
    confidence: float
    result_status: str
    created_at: datetime


class PaginatedDiagnosisResponse(BaseModel):
    """分页诊断结果响应模型。"""

    items: List[DiagnosticResultListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class DiagnosticRuleResponse(BaseModel):
    """诊断规则响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: str
    name: str
    priority: int
    enabled: bool
    match_all: List[str] = []
    match_any: List[str] = []
    exclude_any: List[str] = []
    match_stage: List[str] = []
    category: str
    root_cause: Optional[str] = None
    base_confidence: float
    next_action: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DiagnosticRuleCreate(BaseModel):
    """创建诊断规则请求模型。"""

    rule_id: str
    name: str
    priority: int = 50
    enabled: bool = True
    match_all: List[str] = []
    match_any: List[str] = []
    exclude_any: List[str] = []
    match_stage: List[str] = []
    category: str
    root_cause: Optional[str] = None
    base_confidence: float = 0.8
    next_action: Optional[str] = None


class DiagnosticRuleUpdate(BaseModel):
    """更新诊断规则请求模型。"""

    name: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    match_all: Optional[List[str]] = None
    match_any: Optional[List[str]] = None
    exclude_any: Optional[List[str]] = None
    match_stage: Optional[List[str]] = None
    category: Optional[str] = None
    root_cause: Optional[str] = None
    base_confidence: Optional[float] = None
    next_action: Optional[str] = None


class SimilarCaseResponse(BaseModel):
    """相似案例响应模型。"""

    run_id: int
    device_serial: str
    category: str
    root_cause: str
    similarity: float
    created_at: datetime


# === API 端点 ===


@router.get("", response_model=PaginatedDiagnosisResponse)
async def list_diagnosis(
    serial: Optional[str] = Query(None, description="设备序列号过滤"),
    category: Optional[str] = Query(None, description="故障分类过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
):
    """获取诊断记录列表。

    支持按设备序列号和故障分类过滤，分页返回。
    """
    # 构建查询
    stmt = select(DiagnosticResult).order_by(DiagnosticResult.created_at.desc())

    # 应用过滤条件
    if serial:
        stmt = stmt.where(DiagnosticResult.device_serial == serial)
    if category:
        stmt = stmt.where(DiagnosticResult.category == category)

    # 执行查询获取总数
    total_stmt = select(DiagnosticResult)
    if serial:
        total_stmt = total_stmt.where(DiagnosticResult.device_serial == serial)
    if category:
        total_stmt = total_stmt.where(DiagnosticResult.category == category)
    total = len(list(db.execute(total_stmt).scalars().all()))

    # 分页
    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)

    results = list(db.execute(stmt).scalars().all())

    # 计算总页数
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    # 构建响应
    items = [
        DiagnosticResultListItem(
            id=r.id,
            run_id=r.run_id,
            device_serial=r.device_serial,
            category=r.category,
            root_cause=r.root_cause,
            confidence=r.confidence,
            result_status=r.result_status,
            created_at=r.created_at,
        )
        for r in results
    ]

    return PaginatedDiagnosisResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{run_id}", response_model=DiagnosisDetailResponse)
async def get_diagnosis_detail(
    run_id: int,
    db: Session = Depends(get_db),
):
    """获取诊断详情。

    返回诊断结果、标准化事件列表和规则命中记录。
    """
    service = DiagnosisService(db)

    # 获取诊断结果
    result = service.get_diagnosis_for_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Diagnosis result not found")

    # 获取标准化事件
    events = service.get_events_for_run(run_id)

    # 获取规则命中记录
    rule_hits = service.get_rule_hits_for_run(run_id)

    # 构建响应
    result_response = DiagnosticResultResponse(
        id=result.id,
        run_id=result.run_id,
        device_serial=result.device_serial,
        stage=result.stage,
        category=result.category,
        root_cause=result.root_cause,
        confidence=result.confidence,
        result_status=result.result_status,
        key_evidence=result.get_key_evidence(),
        next_action=result.next_action,
        similar_cases=result.get_similar_cases(),
        created_at=result.created_at,
    )

    event_responses = [
        NormalizedEventResponse(
            id=e.id,
            run_id=e.run_id,
            source_type=e.source_type,
            stage=e.stage,
            event_type=e.event_type,
            severity=e.severity,
            normalized_code=e.normalized_code,
            raw_line=e.raw_line,
            line_no=e.line_no,
            timestamp=e.timestamp,
            kv_payload=e.get_kv_payload(),
            created_at=e.created_at,
        )
        for e in events
    ]

    rule_hit_responses = [
        RuleHitResponse(
            id=rh.id,
            run_id=rh.run_id,
            result_id=rh.result_id,
            rule_id=rh.rule_id,
            rule_name=rh.rule_name,
            matched_codes=rh.get_matched_codes(),
            priority=rh.priority,
            base_confidence=rh.base_confidence,
            created_at=rh.created_at,
        )
        for rh in rule_hits
    ]

    return DiagnosisDetailResponse(
        result=result_response,
        events=event_responses,
        rule_hits=rule_hit_responses,
    )


@router.post("/{run_id}/run")
async def trigger_diagnosis(
    run_id: int,
    db: Session = Depends(get_db),
):
    """手动触发诊断。

    对指定任务执行诊断流程，包括日志解析、规则匹配和结果生成。
    """
    # 检查任务是否存在
    run_session = db.execute(select(RunSession).where(RunSession.id == run_id)).scalar_one_or_none()

    if not run_session:
        raise HTTPException(status_code=404, detail="Run session not found")

    # 执行诊断
    service = DiagnosisService(db)
    result = service.run_diagnosis(run_id)

    if not result:
        return {
            "status": "failed",
            "message": "Diagnosis could not be completed (no logs or task not in terminal state)",
        }

    return {
        "status": "completed",
        "run_id": run_id,
        "result_id": result.id,
        "category": result.category,
        "root_cause": result.root_cause,
        "confidence": result.confidence,
    }


@router.post("/export-logs/{run_id}")
async def export_logs_from_device(
    run_id: int,
    db: Session = Depends(get_db),
):
    """从设备导出日志。

    使用 ADB 从设备拉取 recovery、update_engine、logcat 等日志文件。
    """
    # 检查任务是否存在
    run_session = db.execute(select(RunSession).where(RunSession.id == run_id)).scalar_one_or_none()

    if not run_session:
        raise HTTPException(status_code=404, detail="Run session not found")

    # 获取设备序列号
    device_serial = None
    if run_session.device:
        device_serial = run_session.device.serial
    elif run_session.assigned_device_serial:
        device_serial = run_session.assigned_device_serial

    if not device_serial:
        raise HTTPException(status_code=400, detail="No device associated with this run session")

    # 执行日志导出
    service = LogExportService(db, ADBExecutor())
    exported_files = service.export_from_device(run_id, device_serial)

    if not exported_files:
        return {
            "status": "failed",
            "message": "No logs could be exported from device",
            "exported_files": [],
        }

    return {
        "status": "success",
        "run_id": run_id,
        "device_serial": device_serial,
        "exported_files": exported_files,
    }


@router.get("/{run_id}/export")
async def export_diagnosis_report(
    run_id: int,
    format: str = Query("md", description="导出格式 (md/html)"),
    db: Session = Depends(get_db),
):
    """导出诊断报告。

    生成 Markdown 或 HTML 格式的诊断报告文件供下载。
    """
    service = DiagnosisService(db)

    # 获取诊断结果
    result = service.get_diagnosis_for_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Diagnosis result not found")

    # 获取标准化事件
    events = service.get_events_for_run(run_id)

    # 获取规则命中记录
    rule_hits = service.get_rule_hits_for_run(run_id)

    # 生成报告内容
    if format == "html":
        content = _generate_html_report(result, events, rule_hits)
        filename = f"diagnosis_report_{run_id}.html"
        media_type = "text/html"
    else:
        content = _generate_markdown_report(result, events, rule_hits)
        filename = f"diagnosis_report_{run_id}.md"
        media_type = "text/markdown"

    # 保存临时文件
    from app.config import get_settings

    settings = get_settings()
    temp_dir = settings.ARTIFACTS_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    file_path = temp_dir / filename

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_type,
    )


def _generate_markdown_report(
    result: DiagnosticResult,
    events: List[NormalizedEvent],
    rule_hits: List[RuleHit],
) -> str:
    """生成 Markdown 格式的诊断报告。"""
    lines = [
        f"# 诊断报告 - 任务 #{result.run_id}",
        "",
        "## 基本信息",
        "",
        f"- **设备序列号**: {result.device_serial}",
        f"- **失败阶段**: {result.stage}",
        f"- **故障分类**: {result.category}",
        f"- **根因标识**: {result.root_cause}",
        f"- **置信度**: {result.confidence:.1%}",
        f"- **诊断状态**: {result.result_status}",
        f"- **诊断时间**: {result.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 诊断结论",
        "",
        f"**{result.category}** - {result.root_cause}",
        "",
        f"置信度: {result.confidence:.1%}",
        "",
    ]

    if result.next_action:
        lines.extend(
            [
                "## 建议操作",
                "",
                result.next_action,
                "",
            ]
        )

    # 关键证据
    key_evidence = result.get_key_evidence()
    if key_evidence:
        lines.extend(
            [
                "## 关键证据",
                "",
            ]
        )
        for i, evidence in enumerate(key_evidence, 1):
            raw_line = evidence.get("raw_line", "")
            lines.append(f"{i}. `{raw_line}`")
        lines.append("")

    # 规则命中记录
    if rule_hits:
        lines.extend(
            [
                "## 规则命中记录",
                "",
                "| 规则ID | 规则名称 | 优先级 | 匹配事件码 |",
                "|--------|----------|--------|------------|",
            ]
        )
        for rh in rule_hits:
            codes = ", ".join(rh.get_matched_codes())
            lines.append(f"| {rh.rule_id} | {rh.rule_name} | {rh.priority} | {codes} |")
        lines.append("")

    # 相似案例
    similar_cases = result.get_similar_cases()
    if similar_cases:
        lines.extend(
            [
                "## 相似历史案例",
                "",
                "| 任务ID | 设备SN | 分类 | 根因 | 相似度 |",
                "|--------|--------|------|------|--------|",
            ]
        )
        for case in similar_cases:
            lines.append(
                f"| {case['run_id']} | {case['device_serial']} | "
                f"{case['category']} | {case['root_cause']} | "
                f"{case['similarity']:.1%} |"
            )
        lines.append("")

    # 标准化事件
    if events:
        lines.extend(
            [
                "## 标准化事件",
                "",
                "| 来源 | 阶段 | 类型 | 严重性 | 事件码 |",
                "|------|------|------|--------|--------|",
            ]
        )
        for e in events[:20]:  # 限制显示数量
            lines.append(
                f"| {e.source_type} | {e.stage} | {e.event_type} | "
                f"{e.severity} | {e.normalized_code} |"
            )
        lines.append("")
        if len(events) > 20:
            lines.append(f"*共 {len(events)} 条事件，仅显示前 20 条*")
            lines.append("")

    return "\n".join(lines)


def _generate_html_report(
    result: DiagnosticResult,
    events: List[NormalizedEvent],
    rule_hits: List[RuleHit],
) -> str:
    """生成 HTML 格式的诊断报告。"""
    # 关键证据 HTML
    key_evidence_html = ""
    key_evidence = result.get_key_evidence()
    if key_evidence:
        evidence_items = []
        for evidence in key_evidence:
            raw_line = evidence.get("raw_line", "")
            evidence_items.append(f"<li><code>{raw_line}</code></li>")
        key_evidence_html = f"""
        <h2>关键证据</h2>
        <ul>
            {"".join(evidence_items)}
        </ul>
        """

    # 规则命中 HTML
    rule_hits_html = ""
    if rule_hits:
        rows = []
        for rh in rule_hits:
            codes = ", ".join(rh.get_matched_codes())
            rows.append(
                f"<tr><td>{rh.rule_id}</td><td>{rh.rule_name}</td>"
                f"<td>{rh.priority}</td><td>{codes}</td></tr>"
            )
        rule_hits_html = f"""
        <h2>规则命中记录</h2>
        <table border="1">
            <tr><th>规则ID</th><th>规则名称</th><th>优先级</th><th>匹配事件码</th></tr>
            {"".join(rows)}
        </table>
        """

    # 相似案例 HTML
    similar_cases_html = ""
    similar_cases = result.get_similar_cases()
    if similar_cases:
        rows = []
        for case in similar_cases:
            rows.append(
                f"<tr><td>{case['run_id']}</td><td>{case['device_serial']}</td>"
                f"<td>{case['category']}</td><td>{case['root_cause']}</td>"
                f"<td>{case['similarity']:.1%}</td></tr>"
            )
        similar_cases_html = f"""
        <h2>相似历史案例</h2>
        <table border="1">
            <tr><th>任务ID</th><th>设备SN</th><th>分类</th><th>根因</th><th>相似度</th></tr>
            {"".join(rows)}
        </table>
        """

    # 事件 HTML
    events_html = ""
    if events:
        rows = []
        for e in events[:20]:
            rows.append(
                f"<tr><td>{e.source_type}</td><td>{e.stage}</td>"
                f"<td>{e.event_type}</td><td>{e.severity}</td>"
                f"<td>{e.normalized_code}</td></tr>"
            )
        events_html = f"""
        <h2>标准化事件</h2>
        <table border="1">
            <tr><th>来源</th><th>阶段</th><th>类型</th><th>严重性</th><th>事件码</th></tr>
            {"".join(rows)}
        </table>
        {f"<p>共 {len(events)} 条事件，仅显示前 20 条</p>" if len(events) > 20 else ""}
        """

    html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>诊断报告 - 任务 #{result.run_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; margin-top: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
        th, td {{ padding: 8px; text-align: left; border: 1px solid #ddd; }}
        th {{ background-color: #f4f4f4; }}
        code {{ background-color: #f8f8f8; padding: 2px 4px; }}
        .info {{ background-color: #e7f3ff; padding: 10px; border-radius: 4px; }}
    </style>
</head>
<body>
    <h1>诊断报告 - 任务 #{result.run_id}</h1>

    <div class="info">
        <h2>基本信息</h2>
        <p><strong>设备序列号:</strong> {result.device_serial}</p>
        <p><strong>失败阶段:</strong> {result.stage}</p>
        <p><strong>故障分类:</strong> {result.category}</p>
        <p><strong>根因标识:</strong> {result.root_cause}</p>
        <p><strong>置信度:</strong> {result.confidence:.1%}</p>
        <p><strong>诊断状态:</strong> {result.result_status}</p>
        <p><strong>诊断时间:</strong> {result.created_at.strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>

    <h2>诊断结论</h2>
    <p><strong>{result.category}</strong> - {result.root_cause}</p>
    <p>置信度: {result.confidence:.1%}</p>

    {f"<h2>建议操作</h2><p>{result.next_action}</p>" if result.next_action else ""}

    {key_evidence_html}
    {rule_hits_html}
    {similar_cases_html}
    {events_html}
</body>
</html>
    """

    return html.strip()


# === 规则管理 API ===


@router.get("/rules", response_model=List[DiagnosticRuleResponse])
async def list_rules(
    enabled: Optional[bool] = Query(None, description="启用状态过滤"),
    category: Optional[str] = Query(None, description="故障分类过滤"),
    db: Session = Depends(get_db),
):
    """获取诊断规则列表。

    支持按启用状态和故障分类过滤。
    """
    stmt = select(DiagnosticRuleModel).order_by(DiagnosticRuleModel.priority.desc())

    if enabled is not None:
        stmt = stmt.where(DiagnosticRuleModel.enabled == enabled)
    if category:
        stmt = stmt.where(DiagnosticRuleModel.category == category)

    rules = list(db.execute(stmt).scalars().all())

    return [
        DiagnosticRuleResponse(
            id=r.id,
            rule_id=r.rule_id,
            name=r.name,
            priority=r.priority,
            enabled=r.enabled,
            match_all=r.get_match_all(),
            match_any=r.get_match_any(),
            exclude_any=r.get_exclude_any(),
            match_stage=r.get_match_stage(),
            category=r.category,
            root_cause=r.root_cause,
            base_confidence=r.base_confidence,
            next_action=r.next_action,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in rules
    ]


@router.post("/rules", response_model=DiagnosticRuleResponse)
async def create_rule(
    request: DiagnosticRuleCreate,
    db: Session = Depends(get_db),
):
    """创建诊断规则。"""
    # 检查 rule_id 是否已存在
    existing = db.execute(
        select(DiagnosticRuleModel).where(DiagnosticRuleModel.rule_id == request.rule_id)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400, detail=f"Rule with rule_id '{request.rule_id}' already exists"
        )

    # 创建新规则
    rule = DiagnosticRuleModel(
        rule_id=request.rule_id,
        name=request.name,
        priority=request.priority,
        enabled=request.enabled,
        category=request.category,
        root_cause=request.root_cause,
        base_confidence=request.base_confidence,
        next_action=request.next_action,
    )
    rule.set_match_all(request.match_all)
    rule.set_match_any(request.match_any)
    rule.set_exclude_any(request.exclude_any)
    rule.set_match_stage(request.match_stage)

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return DiagnosticRuleResponse(
        id=rule.id,
        rule_id=rule.rule_id,
        name=rule.name,
        priority=rule.priority,
        enabled=rule.enabled,
        match_all=rule.get_match_all(),
        match_any=rule.get_match_any(),
        exclude_any=rule.get_exclude_any(),
        match_stage=rule.get_match_stage(),
        category=rule.category,
        root_cause=rule.root_cause,
        base_confidence=rule.base_confidence,
        next_action=rule.next_action,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.put("/rules/{rule_id}", response_model=DiagnosticRuleResponse)
async def update_rule(
    rule_id: str,
    request: DiagnosticRuleUpdate,
    db: Session = Depends(get_db),
):
    """更新诊断规则。"""
    # 查找规则
    rule = db.execute(
        select(DiagnosticRuleModel).where(DiagnosticRuleModel.rule_id == rule_id)
    ).scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # 更新字段
    if request.name is not None:
        rule.name = request.name
    if request.priority is not None:
        rule.priority = request.priority
    if request.enabled is not None:
        rule.enabled = request.enabled
    if request.match_all is not None:
        rule.set_match_all(request.match_all)
    if request.match_any is not None:
        rule.set_match_any(request.match_any)
    if request.exclude_any is not None:
        rule.set_exclude_any(request.exclude_any)
    if request.match_stage is not None:
        rule.set_match_stage(request.match_stage)
    if request.category is not None:
        rule.category = request.category
    if request.root_cause is not None:
        rule.root_cause = request.root_cause
    if request.base_confidence is not None:
        rule.base_confidence = request.base_confidence
    if request.next_action is not None:
        rule.next_action = request.next_action

    db.commit()
    db.refresh(rule)

    return DiagnosticRuleResponse(
        id=rule.id,
        rule_id=rule.rule_id,
        name=rule.name,
        priority=rule.priority,
        enabled=rule.enabled,
        match_all=rule.get_match_all(),
        match_any=rule.get_match_any(),
        exclude_any=rule.get_exclude_any(),
        match_stage=rule.get_match_stage(),
        category=rule.category,
        root_cause=rule.root_cause,
        base_confidence=rule.base_confidence,
        next_action=rule.next_action,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: Session = Depends(get_db),
):
    """删除诊断规则。"""
    # 查找规则
    rule = db.execute(
        select(DiagnosticRuleModel).where(DiagnosticRuleModel.rule_id == rule_id)
    ).scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.delete(rule)
    db.commit()

    return {"status": "deleted", "rule_id": rule_id}


# === 相似案例搜索 API ===


@router.get("/cases/search", response_model=List[SimilarCaseResponse])
async def search_similar_cases(
    category: Optional[str] = Query(None, description="故障分类"),
    root_cause: Optional[str] = Query(None, description="根因标识"),
    keywords: Optional[str] = Query(None, description="关键词搜索"),
    limit: int = Query(10, ge=1, le=50, description="返回数量限制"),
    db: Session = Depends(get_db),
):
    """搜索相似案例。

    根据分类、根因或关键词检索历史相似案例。
    """
    service = SimilarCaseService(db)

    # 如果有分类和根因，使用精确搜索
    if category and root_cause:
        cases = service.find_similar(
            category=category,
            root_cause=root_cause,
            limit=limit,
        )
        return [
            SimilarCaseResponse(
                run_id=c["run_id"],
                device_serial=c["device_serial"],
                category=c["category"],
                root_cause=c["root_cause"],
                similarity=c["similarity"],
                created_at=c["created_at"],
            )
            for c in cases
        ]

    # 否则使用数据库查询搜索
    stmt = select(SimilarCaseIndex).order_by(SimilarCaseIndex.created_at.desc())

    if category:
        stmt = stmt.where(SimilarCaseIndex.category == category)
    if root_cause:
        stmt = stmt.where(SimilarCaseIndex.root_cause == root_cause)

    stmt = stmt.limit(limit)
    indices = list(db.execute(stmt).scalars().all())

    # 如果有关键词，尝试在关联的诊断结果中搜索
    if keywords:
        # 获取所有匹配的 run_id
        run_ids = [idx.run_id for idx in indices]

        # 搜索诊断结果的关键证据
        if run_ids:
            results = (
                db.execute(select(DiagnosticResult).where(DiagnosticResult.run_id.in_(run_ids)))
                .scalars()
                .all()
            )

            # 过滤包含关键词的结果
            filtered_indices = []
            for idx in indices:
                result = next((r for r in results if r.run_id == idx.run_id), None)
                if result:
                    key_evidence = result.get_key_evidence()
                    evidence_text = " ".join(e.get("raw_line", "") for e in key_evidence)
                    if keywords.lower() in evidence_text.lower():
                        filtered_indices.append(idx)

            indices = filtered_indices[:limit]

    return [
        SimilarCaseResponse(
            run_id=idx.run_id,
            device_serial=idx.device_serial,
            category=idx.category,
            root_cause=idx.root_cause,
            similarity=1.0,  # 数据库搜索返回的案例默认相似度为 1.0
            created_at=idx.created_at,
        )
        for idx in indices
    ]
