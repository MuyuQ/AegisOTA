"""任务 API 路由。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.run import RunSession, RunStatus, UpgradeType
from app.models.device import Device
from app.services.run_service import RunService
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/api/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    """创建任务请求模型。"""

    plan_id: int
    device_serial: Optional[str] = None


class RunResponse(BaseModel):
    """任务响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    device_id: Optional[int] = None
    status: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    result: Optional[str] = None
    failure_category: Optional[str] = None
    summary: Optional[str] = None


class CreatePlanRequest(BaseModel):
    """创建计划请求模型。"""

    name: str
    upgrade_type: str
    package_path: str
    target_build: Optional[str] = None
    device_selector: Optional[dict] = None
    parallelism: int = 1


# 升级计划 API - 放在 /{run_id} 之前，避免路由冲突


@router.get("/plans")
async def list_plans(db: Session = Depends(get_db)):
    """列出升级计划。"""
    service = RunService(db)
    plans = service.list_upgrade_plans()

    return [
        {
            "id": p.id,
            "name": p.name,
            "upgrade_type": p.upgrade_type.value if hasattr(p.upgrade_type, 'value') else str(p.upgrade_type),
            "package_path": p.package_path,
            "target_build": p.target_build,
        }
        for p in plans
    ]


@router.post("/plans")
async def create_plan(
    request: CreatePlanRequest,
    db: Session = Depends(get_db),
):
    """创建升级计划。"""
    service = RunService(db)

    try:
        upgrade_type = UpgradeType(request.upgrade_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid upgrade_type")

    plan = service.create_upgrade_plan(
        name=request.name,
        upgrade_type=upgrade_type,
        package_path=request.package_path,
        target_build=request.target_build,
        device_selector=request.device_selector,
        parallelism=request.parallelism,
    )

    return {"plan_id": plan.id, "name": plan.name}


# 任务 API


@router.get("", response_model=List[RunResponse])
async def list_runs(
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """获取任务列表。"""
    service = RunService(db)

    run_status = None
    if status:
        try:
            run_status = RunStatus(status)
        except ValueError:
            valid_values = [s.value for s in RunStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {valid_values}"
            )

    runs = service.list_runs(status=run_status, limit=limit)

    return [
        RunResponse(
            id=r.id,
            plan_id=r.plan_id,
            device_id=r.device_id,
            status=r.status.value if hasattr(r.status, 'value') else str(r.status),
            started_at=r.started_at.isoformat() if r.started_at else None,
            ended_at=r.ended_at.isoformat() if r.ended_at else None,
            result=r.result,
            failure_category=r.failure_category,
            summary=r.summary,
        )
        for r in runs
    ]


@router.post("")
async def create_run(
    request: CreateRunRequest,
    db: Session = Depends(get_db),
):
    """创建升级任务（JSON API）。"""
    run_service = RunService(db)
    scheduler = SchedulerService(db)

    # 检查计划是否存在
    plan = run_service.get_upgrade_plan(request.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    # 选择设备
    device = None
    if request.device_serial:
        device = db.query(Device).filter_by(serial=request.device_serial).first()
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

    # 创建任务
    if device:
        run = run_service.create_run_session(
            plan_id=plan.id,
            device_id=device.id,
        )
    else:
        # 无设备，排队等待
        run = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
        db.add(run)
        db.commit()
        db.refresh(run)

    return {
        "run_id": run.id,
        "status": run.status.value if hasattr(run.status, 'value') else str(run.status)
    }


@router.post("/form", response_class=HTMLResponse)
async def create_run_form(
    request: Request,
    plan_id: int = Form(...),
    device_serial: Optional[str] = Form(None),
    # 新增参数
    monkey_enabled: bool = Form(False),
    monkey_event_count: Optional[int] = Form(None),
    monkey_throttle: Optional[int] = Form(None),
    upgrade_count: int = Form(1),
    stop_on_failure: bool = Form(True),
    enable_cycle_test: bool = Form(False),
    db: Session = Depends(get_db),
):
    """创建升级任务（表单提交，返回 HTML）。"""
    from fastapi.templating import Jinja2Templates
    from pathlib import Path

    templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

    run_service = RunService(db)

    # 检查计划是否存在
    plan = run_service.get_upgrade_plan(plan_id)
    if not plan:
        return HTMLResponse(content='<div class="alert alert-error">升级计划不存在</div>', status_code=400)

    # 选择设备
    device = None
    if device_serial:
        device = db.query(Device).filter_by(serial=device_serial).first()

    # 构建 run_options
    run_options = {
        "monkey_enabled": monkey_enabled,
        "upgrade_count": upgrade_count,
        "stop_on_failure": stop_on_failure,
        "enable_cycle_test": enable_cycle_test,
    }

    if monkey_enabled:
        run_options["monkey_params"] = {
            "event_count": monkey_event_count or 1000,
            "throttle": monkey_throttle or 50,
        }

    # 创建任务
    if device:
        run = run_service.create_run_session(
            plan_id=plan.id,
            device_id=device.id,
            run_options=run_options,
            total_iterations=upgrade_count,
        )
    else:
        # 无设备，排队等待
        run = RunSession(plan_id=plan.id, status=RunStatus.QUEUED, total_iterations=upgrade_count)
        run.set_run_options(run_options)
        db.add(run)
        db.commit()
        db.refresh(run)

    status_str = run.status.value if hasattr(run.status, 'value') else str(run.status)

    # 构建成功消息
    msg_parts = [
        "任务创建成功！",
        f"任务 ID: {run.id}",
        f"状态: {status_str}",
    ]
    if upgrade_count > 1:
        msg_parts.append(f"升级次数: {upgrade_count}")
    if enable_cycle_test:
        msg_parts.append("循环升级: 已启用 (A↔B)")
    if monkey_enabled:
        event_count = run_options.get("monkey_params", {}).get("event_count", 1000)
        msg_parts.append(f"Monkey 测试: 已启用 ({event_count} 事件)")

    return HTMLResponse(
        content=f'''<div class="alert alert-success">
            {'<br>'.join(msg_parts)}<br>
            <a href="/runs/{run.id}" class="btn btn-sm btn-primary" style="margin-top: 0.5rem;">查看详情</a>
        </div>'''
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    """获取任务详情。"""
    service = RunService(db)
    run = service.get_run_session(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return RunResponse(
        id=run.id,
        plan_id=run.plan_id,
        device_id=run.device_id,
        status=run.status.value if hasattr(run.status, 'value') else str(run.status),
        started_at=run.started_at.isoformat() if run.started_at else None,
        ended_at=run.ended_at.isoformat() if run.ended_at else None,
        result=run.result,
        failure_category=run.failure_category,
        summary=run.summary,
    )


@router.post("/{run_id}/abort")
async def abort_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    """终止任务。"""
    service = RunService(db)
    run = service.abort_run_session(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found or cannot abort")

    return {"status": "aborted", "run_id": run_id}


@router.post("/{run_id}/reserve")
async def reserve_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    """预留任务（分配设备）。"""
    scheduler = SchedulerService(db)
    success = scheduler.reserve_run(run_id)

    if not success:
        raise HTTPException(status_code=400, detail="Cannot reserve run")

    run = db.query(RunSession).filter_by(id=run_id).first()
    return {
        "status": "reserved",
        "run_id": run_id,
        "device_id": run.device_id
    }