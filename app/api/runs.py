"""任务 API 路由。"""

from fastapi import APIRouter

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("")
async def list_runs():
    """获取任务列表。"""
    return []