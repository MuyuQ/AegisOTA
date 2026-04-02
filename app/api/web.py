"""Web 页面路由。"""

from typing import Optional
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.models.device import Device, DeviceStatus
from app.models.run import RunSession, RunStatus
from app.models.diagnostic import DiagnosticResult, RuleHit, NormalizedEvent
from app.services.pool_service import PoolService
from app.services.diagnosis_service import DiagnosisService

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
# 禁用 Jinja2 缓存以避免版本兼容性问题
templates.env.cache = None


def get_csrf_token(request: Request) -> str:
    """从请求中获取 CSRF token。"""
    import secrets
    token = request.cookies.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
    return token


def get_template_context(request: Request, **kwargs) -> dict:
    """获取模板上下文，包含 CSRF token。"""
    context = {"request": request, "csrf_token": get_csrf_token(request)}
    context.update(kwargs)
    return context


# ============ 诊断相关辅助函数 ============

# 故障分类中文映射
CATEGORY_DISPLAY_MAP = {
    "device_env_issue": "设备环境问题",
    "boot_failure": "启动失败",
    "package_issue": "升级包问题",
    "validation_failure": "验证失败",
    "monkey_instability": "Monkey 不稳定",
    "adb_transport_issue": "ADB 传输问题",
    "unknown": "未知",
}


def _get_confidence_level(confidence: float) -> str:
    """根据置信度返回级别。"""
    if confidence >= 0.8:
        return "high"
    elif confidence >= 0.5:
        return "medium"
    else:
        return "low"


def _format_datetime(dt: datetime) -> str:
    """格式化日期时间。"""
    if not dt:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ============ 页面路由 ============


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """仪表盘首页。"""
    # 统计数据
    total_devices = db.query(Device).count()
    idle_devices = db.query(Device).filter(Device.status == DeviceStatus.IDLE).count()
    busy_devices = db.query(Device).filter(Device.status == DeviceStatus.BUSY).count()
    offline_devices = db.query(Device).filter(Device.status == DeviceStatus.OFFLINE).count()
    quarantined_devices = db.query(Device).filter(Device.status == DeviceStatus.QUARANTINED).count()

    running_tasks = db.query(RunSession).filter(
        RunSession.status.in_([RunStatus.RUNNING, RunStatus.VALIDATING])
    ).count()

    # 今日任务
    today = datetime.now(timezone.utc).date()
    today_tasks = db.query(RunSession).filter(
        func.date(RunSession.created_at) == today
    ).count()

    # 最近任务（按创建时间倒序，ID倒序作为第二排序）
    recent_runs = db.query(RunSession).order_by(
        RunSession.created_at.desc().nullslast(),
        RunSession.id.desc()
    ).limit(5).all()

    stats = {
        "total_devices": total_devices,
        "idle_devices": idle_devices,
        "busy_devices": busy_devices,
        "offline_devices": offline_devices,
        "quarantined_devices": quarantined_devices,
        "running_tasks": running_tasks,
        "today_tasks": today_tasks,
    }

    # 格式化最近任务
    runs_data = [
        {
            "id": r.id,
            "device_serial": r.device.serial if r.device else "-",
            "status": r.status.value if hasattr(r.status, 'value') else r.status,
            "result": r.result,
        }
        for r in recent_runs
    ]

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        get_template_context(request, stats=stats, recent_runs=runs_data)
    )


@router.get("/devices", response_class=HTMLResponse)
async def devices_page(request: Request, db: Session = Depends(get_db)):
    """设备列表页面。"""
    devices = db.query(Device).order_by(Device.last_seen_at.desc()).all()

    devices_data = [
        {
            "id": d.id,
            "serial": d.serial,
            "brand": d.brand or "-",
            "model": d.model or "-",
            "system_version": d.system_version or "-",
            "status": d.status.value if hasattr(d.status, 'value') else d.status,
            "battery_level": d.battery_level or "-",
            "health_score": d.health_score or "-",
            "tags": d.get_tags(),
            "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else "-",
            "pool_id": d.pool_id,
            "pool_name": d.pool.name if d.pool else None,
            "location": d.location,
        }
        for d in devices
    ]

    return templates.TemplateResponse(
        request,
        "devices.html",
        get_template_context(request, devices=devices_data)
    )


@router.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request, db: Session = Depends(get_db)):
    """任务列表页面。"""
    runs = db.query(RunSession).order_by(
        RunSession.created_at.desc().nullslast(),
        RunSession.id.desc()
    ).limit(50).all()

    runs_data = [
        {
            "id": r.id,
            "plan_name": r.plan.name if r.plan else "-",
            "device_serial": r.device.serial if r.device else "-",
            "status": r.status.value if hasattr(r.status, 'value') else r.status,
            "result": r.result or "-",
            "started_at": r.started_at.isoformat() if r.started_at else "-",
            "ended_at": r.ended_at.isoformat() if r.ended_at else "-",
            "duration": r.get_duration_seconds() or "-",
            "failure_category": r.failure_category.value if hasattr(r.failure_category, 'value') else (r.failure_category or "-"),
        }
        for r in runs
    ]

    return templates.TemplateResponse(
        request,
        "runs.html",
        get_template_context(request, runs=runs_data)
    )


@router.get("/runs/create", response_class=HTMLResponse)
async def create_run_page(request: Request, db: Session = Depends(get_db)):
    """创建任务页面。"""
    from app.models.run import UpgradePlan
    from collections import defaultdict

    plans = db.query(UpgradePlan).all()
    devices = db.query(Device).filter(Device.status == DeviceStatus.IDLE).all()

    # 按物理位置分组设备
    devices_by_location = defaultdict(list)
    for device in devices:
        location = device.location or "未设置位置"
        devices_by_location[location].append({
            "serial": device.serial,
            "brand": device.brand or "-",
            "model": device.model or "-",
            "status": device.status.value if hasattr(device.status, 'value') else str(device.status),
        })

    return templates.TemplateResponse(
        request,
        "create_run.html",
        get_template_context(request, plans=plans, devices_by_location=dict(devices_by_location))
    )


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail_page(
    request: Request,
    run_id: int,
    db: Session = Depends(get_db),
):
    """任务详情页面。"""
    from app.models.run import RunStep

    run = db.query(RunSession).filter_by(id=run_id).first()

    if not run:
        return templates.TemplateResponse(
            request,
            "base.html",
            get_template_context(request),
            status_code=404
        )

    # 获取执行步骤
    steps = db.query(RunStep).filter_by(run_id=run_id).order_by(RunStep.step_order).all()

    # 获取任务选项
    run_options = run.get_run_options()
    monkey_enabled = run_options.get("monkey_enabled", False)
    monkey_params = run_options.get("monkey_params", {})

    run_data = {
        "id": run.id,
        "plan_name": run.plan.name if run.plan else "-",
        "device_serial": run.device.serial if run.device else "-",
        "status": run.status.value if hasattr(run.status, 'value') else run.status,
        "result": run.result or "-",
        "started_at": run.started_at.isoformat() if run.started_at else "-",
        "ended_at": run.ended_at.isoformat() if run.ended_at else "-",
        "duration": run.get_duration_seconds() or "-",
        "failure_category": run.failure_category.value if hasattr(run.failure_category, 'value') else (run.failure_category or "-"),
        "summary": run.summary or "-",
        # 新增字段
        "total_iterations": run.total_iterations or 1,
        "current_iteration": run.current_iteration or 0,
        "monkey_enabled": monkey_enabled,
        "monkey_event_count": monkey_params.get("event_count", 1000) if monkey_enabled else None,
        "monkey_throttle": monkey_params.get("throttle", 50) if monkey_enabled else None,
        "stop_on_failure": run_options.get("stop_on_failure", True),
    }

    steps_data = [
        {
            "id": s.id,
            "step_name": s.step_name.value if hasattr(s.step_name, 'value') else s.step_name,
            "status": s.status.value if hasattr(s.status, 'value') else s.status,
            "started_at": s.started_at.isoformat() if s.started_at else "-",
            "ended_at": s.ended_at.isoformat() if s.ended_at else "-",
            "duration": s.get_duration_seconds() or "-",
        }
        for s in steps
    ]

    # 获取诊断结果
    diagnosis_service = DiagnosisService(db)
    diagnosis = diagnosis_service.get_diagnosis_for_run(run_id)

    diagnosis_data = None
    if diagnosis:
        diagnosis_data = {
            "category": diagnosis.category,
            "category_display": CATEGORY_DISPLAY_MAP.get(diagnosis.category, diagnosis.category),
            "root_cause": diagnosis.root_cause,
            "confidence": diagnosis.confidence,
            "confidence_level": _get_confidence_level(diagnosis.confidence),
            "next_action": diagnosis.next_action,
        }

    return templates.TemplateResponse(
        request,
        "run_detail.html",
        get_template_context(request, run=run_data, steps=steps_data, diagnosis=diagnosis_data)
    )


@router.get("/pools", response_class=HTMLResponse)
async def pools_page(request: Request, db: Session = Depends(get_db)):
    """设备池管理页面。"""
    service = PoolService(db)
    pools = service.list_pools()

    # 添加设备统计
    pools_data = []
    for pool in pools:
        capacity = service.get_pool_capacity(pool.id)
        pools_data.append({
            "id": pool.id,
            "name": pool.name,
            "purpose": pool.purpose.value if hasattr(pool.purpose, 'value') else str(pool.purpose),
            "reserved_ratio": pool.reserved_ratio,
            "enabled": pool.enabled,
            "total_devices": capacity["total"],
            "available_devices": capacity["available"],
        })

    return templates.TemplateResponse(
        request,
        "pools.html",
        get_template_context(request, pools=pools_data)
    )


@router.get("/pools/{pool_id}", response_class=HTMLResponse)
async def pool_detail_page(request: Request, pool_id: int, db: Session = Depends(get_db)):
    """设备池详情页面。"""
    service = PoolService(db)
    pool = service.get_pool_by_id(pool_id)

    if not pool:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="设备池不存在")

    # 获取容量信息
    capacity = service.get_pool_capacity(pool_id)

    # 获取池内设备
    devices = pool.devices  # 通过关系获取
    devices_data = []
    for device in devices:
        devices_data.append({
            "id": device.id,
            "serial": device.serial,
            "brand": device.brand,
            "model": device.model,
            "status": device.status.value if hasattr(device.status, 'value') else str(device.status),
            "health_score": device.health_score,
        })

    # 获取未分配设备（用于分配设备下拉框）
    unassigned_devices = db.query(Device).filter(Device.pool_id == None).all()
    unassigned_data = []
    for device in unassigned_devices:
        unassigned_data.append({
            "id": device.id,
            "serial": device.serial,
            "brand": device.brand,
            "model": device.model,
            "status": device.status.value if hasattr(device.status, 'value') else str(device.status),
        })

    pool_data = {
        "id": pool.id,
        "name": pool.name,
        "purpose": pool.purpose.value if hasattr(pool.purpose, 'value') else str(pool.purpose),
        "reserved_ratio": pool.reserved_ratio,
        "enabled": pool.enabled,
        "total_devices": capacity["total"],
        "available_devices": capacity["available"],
        "busy_devices": capacity["busy"],
        "offline_devices": capacity["offline"],
        "quarantined_devices": capacity["quarantined"],
    }

    return templates.TemplateResponse(
        request,
        "pool_detail.html",
        get_template_context(request, pool=pool_data, devices=devices_data, unassigned_devices=unassigned_data)
    )


@router.put("/pools/{pool_id}/form", response_class=HTMLResponse)
async def update_pool_form(
    request: Request,
    pool_id: int,
    reserved_ratio: Optional[float] = Form(None),
    enabled: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """设备池配置更新（表单提交）。"""
    service = PoolService(db)
    pool = service.get_pool_by_id(pool_id)

    if not pool:
        return HTMLResponse(content="设备池不存在", status_code=404)

    update_data = {}
    if reserved_ratio is not None:
        # 表单输入的是百分比，需要转换为比例
        update_data["reserved_ratio"] = reserved_ratio / 100.0
    if enabled is not None:
        update_data["enabled"] = enabled.lower() == "true"

    if update_data:
        service.update_pool(pool_id, **update_data)

    # 返回成功消息，页面会通过 onsubmit 自动刷新
    return HTMLResponse(content="<div class='alert alert-success'>配置已保存</div>")


@router.post("/pools/{pool_id}/assign", response_class=HTMLResponse)
async def assign_device_form(
    request: Request,
    pool_id: int,
    db: Session = Depends(get_db),
):
    """分配设备到池（表单提交）。"""
    # 先读取表单数据
    form_data = await request.form()
    device_id_str = form_data.get("device_id")

    if not device_id_str:
        return HTMLResponse(content="<div class='alert alert-danger'>请选择设备</div>", status_code=400)

    try:
        device_id = int(device_id_str)
    except ValueError:
        return HTMLResponse(content="<div class='alert alert-danger'>设备 ID 格式错误</div>", status_code=400)

    service = PoolService(db)
    device = service.assign_device_to_pool(device_id, pool_id)

    if not device:
        return HTMLResponse(content="<div class='alert alert-danger'>设备或池不存在</div>", status_code=404)

    # 获取更新后的池和设备列表
    pool = service.get_pool_by_id(pool_id)
    devices = pool.devices if pool else []

    # 渲染更新后的设备列表
    devices_html = _render_device_list_html(pool_id, devices)

    return HTMLResponse(content=devices_html)


def _render_device_list_html(pool_id: int, devices: list) -> str:
    """渲染设备列表 HTML。"""
    if not devices:
        return '<p style="color: var(--text-muted); text-align: center; padding: 2rem;">暂无设备分配到此池</p>'

    rows = []
    for d in devices:
        status_val = d.status.value if hasattr(d.status, 'value') else str(d.status)
        status_text = {
            'idle': '空闲', 'busy': '忙碌', 'offline': '离线', 'quarantined': '隔离'
        }.get(status_val, status_val)

        health_display = "-"
        if d.health_score:
            health_class = "health-high" if d.health_score >= 90 else ("health-medium" if d.health_score >= 70 else "health-low")
            health_display = f'<span class="{health_class}">{round(d.health_score, 1)}%</span>'

        rows.append(f'''
        <tr id="device-row-{d.id}">
            <td><code>{d.serial}</code></td>
            <td>{d.brand or "-"}</td>
            <td>{d.model or "-"}</td>
            <td><span class="status-badge status-{status_val.lower()}">{status_text}</span></td>
            <td>{health_display}</td>
            <td>
                <a href="/devices/{d.serial}" class="btn btn-sm btn-secondary">详情</a>
                <button class="btn btn-sm btn-danger"
                        hx-delete="/api/pools/{pool_id}/devices/{d.id}"
                        hx-confirm="确定要从池中移除设备 {d.serial} 吗？"
                        hx-target="#device-row-{d.id}"
                        hx-swap="outerHTML swap:0.5s">
                    移除
                </button>
            </td>
        </tr>''')

    return f'''
    <div class="table-responsive">
        <table class="table">
            <thead>
                <tr>
                    <th>序列号</th>
                    <th>品牌</th>
                    <th>型号</th>
                    <th>状态</th>
                    <th>健康度</th>
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>'''


@router.put("/pools/{pool_id}/status", response_class=HTMLResponse)
async def update_pool_status(
    request: Request,
    pool_id: int,
    db: Session = Depends(get_db),
):
    """更新设备池启用状态（JSON请求）。"""
    import json
    body = await request.body()
    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        data = {}

    enabled = data.get("enabled", False)

    service = PoolService(db)
    pool = service.update_pool(pool_id, enabled=enabled)

    if not pool:
        return HTMLResponse(content="设备池不存在", status_code=404)

    # 返回更新后的状态 HTML
    if pool.enabled:
        return HTMLResponse(content='<span style="color: var(--success-color);">● 已启用</span>')
    else:
        return HTMLResponse(content='<span style="color: var(--text-muted);">○ 已禁用</span>')


# ============ 诊断页面路由 ============

@router.get("/diagnosis", response_class=HTMLResponse)
async def diagnosis_list_page(
    request: Request,
    db: Session = Depends(get_db),
    serial: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """诊断列表页面。"""
    # 构建查询
    query = db.query(DiagnosticResult)

    # 应用筛选条件
    if serial:
        query = query.filter(DiagnosticResult.device_serial.ilike(f"%{serial}%"))
    if category:
        query = query.filter(DiagnosticResult.category == category)

    # 计算总数
    total_count = query.count()

    # 计算分页
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1
    offset = (page - 1) * page_size

    # 获取诊断记录（按诊断时间倒序）
    diagnoses = query.order_by(
        DiagnosticResult.created_at.desc().nullslast()
    ).offset(offset).limit(page_size).all()

    # 格式化诊断数据
    diagnoses_data = []
    for diag in diagnoses:
        diagnoses_data.append({
            "run_id": diag.run_id,
            "device_serial": diag.device_serial,
            "category": diag.category,
            "category_display": CATEGORY_DISPLAY_MAP.get(diag.category, diag.category),
            "root_cause": diag.root_cause,
            "confidence": diag.confidence,
            "confidence_level": _get_confidence_level(diag.confidence),
            "result_status": diag.result_status,
            "created_at": diag.created_at,
            "created_at_display": _format_datetime(diag.created_at),
        })

    return templates.TemplateResponse(
        request,
        "diagnosis.html",
        get_template_context(
            request,
            diagnoses=diagnoses_data,
            total_count=total_count,
            page=page,
            total_pages=total_pages,
            serial=serial,
            category=category,
        )
    )


@router.get("/diagnosis/{run_id}", response_class=HTMLResponse)
async def diagnosis_detail_page(
    request: Request,
    run_id: int,
    db: Session = Depends(get_db),
):
    """诊断详情页面。"""
    service = DiagnosisService(db)

    # 获取诊断结果
    diagnosis = service.get_diagnosis_for_run(run_id)

    if not diagnosis:
        return templates.TemplateResponse(
            request,
            "base.html",
            get_template_context(request),
            status_code=404
        )

    # 获取规则命中记录
    rule_hits = service.get_rule_hits_for_run(run_id)
    rule_hits_data = []
    for hit in rule_hits:
        rule_hits_data.append({
            "rule_id": hit.rule_id,
            "rule_name": hit.rule_name,
            "priority": hit.priority,
            "base_confidence": hit.base_confidence,
            "matched_codes": hit.get_matched_codes(),
        })

    # 获取关键证据
    key_evidence = diagnosis.get_key_evidence()

    # 获取相似案例
    similar_cases = diagnosis.get_similar_cases()

    # 获取标准化事件（按日志源分组）
    events = service.get_events_for_run(run_id)

    # 定义日志源类型及显示名称
    source_type_map = {
        "recovery_log": "Recovery 日志",
        "update_engine_log": "Update Engine 日志",
        "logcat": "Logcat 日志",
        "monkey_output": "Monkey 输出",
    }

    # 按日志源分组事件
    events_by_source = {}
    for event in events:
        source_type = event.source_type
        if source_type not in events_by_source:
            events_by_source[source_type] = []
        events_by_source[source_type].append({
            "severity": event.severity,
            "normalized_code": event.normalized_code,
            "raw_line": event.raw_line or "",
        })

    # 构建日志源列表
    log_sources = []
    for source_type, display_name in source_type_map.items():
        log_sources.append({
            "type": source_type,
            "name": display_name,
            "count": len(events_by_source.get(source_type, [])),
            "events": events_by_source.get(source_type, []),
        })

    # 添加其他日志源（如果有）
    for source_type in events_by_source:
        if source_type not in source_type_map:
            log_sources.append({
                "type": source_type,
                "name": source_type,
                "count": len(events_by_source[source_type]),
                "events": events_by_source[source_type],
            })

    # 格式化诊断数据
    diagnosis_data = {
        "run_id": diagnosis.run_id,
        "device_serial": diagnosis.device_serial,
        "stage": diagnosis.stage,
        "category": diagnosis.category,
        "category_display": CATEGORY_DISPLAY_MAP.get(diagnosis.category, diagnosis.category),
        "root_cause": diagnosis.root_cause,
        "confidence": diagnosis.confidence,
        "confidence_level": _get_confidence_level(diagnosis.confidence),
        "result_status": diagnosis.result_status,
        "next_action": diagnosis.next_action,
        "created_at": diagnosis.created_at,
        "created_at_display": _format_datetime(diagnosis.created_at),
    }

    return templates.TemplateResponse(
        request,
        "diagnosis_detail.html",
        get_template_context(
            request,
            diagnosis=diagnosis_data,
            key_evidence=key_evidence,
            rule_hits=rule_hits_data,
            similar_cases=similar_cases,
            log_sources=log_sources,
        )
    )