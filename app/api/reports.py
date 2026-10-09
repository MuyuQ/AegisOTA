"""报告 API 路由。"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.artifact import Artifact
from app.models.run import RunSession
from app.reporting.generator import ReportGenerator

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/{run_id}")
async def get_report(
    run_id: int,
    db: Session = Depends(get_db),
):
    """获取报告摘要。"""
    run = db.query(RunSession).filter_by(id=run_id).first()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    generator = ReportGenerator()

    report = generator.generate(
        run_id=run.id,
        plan_name=run.plan.name if run.plan else "Unknown",
        device_serial=run.device.serial if run.device else "Unknown",
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        started_at=run.started_at,
        ended_at=run.ended_at,
        failure_category=run.failure_category,
        timeline=[],
        step_results={},
    )

    return report


@router.get("/{run_id}/html", response_class=HTMLResponse)
async def get_report_html(
    run_id: int,
    db: Session = Depends(get_db),
):
    """获取 HTML 格式报告。"""
    run = db.query(RunSession).filter_by(id=run_id).first()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    generator = ReportGenerator()

    html = generator.generate_html(
        run_id=run.id,
        plan_name=run.plan.name if run.plan else "Unknown",
        device_serial=run.device.serial if run.device else "Unknown",
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        timeline=[],
    )

    return html


@router.get("/{run_id}/markdown", response_class=PlainTextResponse)
async def get_report_markdown(
    run_id: int,
    db: Session = Depends(get_db),
):
    """获取 Markdown 格式报告。"""
    run = db.query(RunSession).filter_by(id=run_id).first()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    generator = ReportGenerator()

    md = generator.generate_markdown(
        run_id=run.id,
        plan_name=run.plan.name if run.plan else "Unknown",
        device_serial=run.device.serial if run.device else "Unknown",
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        timeline=[],
    )

    return md


@router.get("/{run_id}/artifacts")
async def list_artifacts(
    run_id: int,
    db: Session = Depends(get_db),
):
    """列出任务产物。"""
    artifacts = db.query(Artifact).filter_by(run_id=run_id).all()

    return [
        {
            "id": a.id,
            "type": a.artifact_type,
            "path": a.file_path,
            "size": a.file_size,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in artifacts
    ]
