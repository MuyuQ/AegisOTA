"""报告 API 路由。"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/{run_id}")
async def get_report(run_id: int):
    """获取任务报告。"""
    return {"run_id": run_id, "status": "placeholder"}