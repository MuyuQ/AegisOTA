"""Web 页面路由。"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.models.device import Device, DeviceStatus
from app.models.run import RunSession, RunStatus
from app.services.pool_service import PoolService

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

    plans = db.query(UpgradePlan).all()
    devices = db.query(Device).filter(Device.status == DeviceStatus.IDLE).all()

    return templates.TemplateResponse(
        request,
        "create_run.html",
        get_template_context(request, plans=plans, devices=devices)
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

    return templates.TemplateResponse(
        request,
        "run_detail.html",
        get_template_context(request, run=run_data, steps=steps_data)
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
            "max_parallel": pool.max_parallel,
            "enabled": pool.enabled,
            "total_devices": capacity["total"],
            "available_devices": capacity["available"],
        })

    return templates.TemplateResponse(
        request,
        "pools.html",
        get_template_context(request, pools=pools_data)
    )