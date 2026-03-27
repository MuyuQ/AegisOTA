"""任务 API 路由。"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.run import RunSession, RunStatus, UpgradePlan, UpgradeType
from app.models.device import Device, DeviceStatus
from app.services.run_service import RunService
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/api/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    """创建任务请求模型。"""

    plan_id: int
    device_serial: Optional[str] = None


class RunResponse(BaseModel):
    """任务响应模型。"""

    id: int
    plan_id: int
    device_id: Optional[int] = None
    status: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    result: Optional[str] = None
    failure_category: Optional[str] = None
    summary: Optional[str] = None

    class Config:
        from_attributes = True


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
            pass

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
    """创建升级任务。"""
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