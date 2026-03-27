"""设备 API 路由。"""

from fastapi import APIRouter

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("")
async def list_devices():
    """获取设备列表。"""
    return []