"""设备 API 路由。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device, DeviceStatus
from app.services.device_service import DeviceService
from app.executors.mock_executor import MockADBExecutor

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceResponse(BaseModel):
    """设备响应模型。"""

    id: int
    serial: str
    brand: Optional[str] = None
    model: Optional[str] = None
    android_version: Optional[str] = None
    status: str
    battery_level: Optional[int] = None
    health_score: Optional[float] = None
    tags: List[str] = []
    last_seen_at: Optional[str] = None

    class Config:
        from_attributes = True


class QuarantineRequest(BaseModel):
    """隔离请求模型。"""

    reason: str


class TagsUpdate(BaseModel):
    """标签更新模型。"""

    tags: List[str]


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取设备列表。"""
    service = DeviceService(db)

    device_status = None
    if status:
        try:
            device_status = DeviceStatus(status)
        except ValueError:
            pass

    devices = service.list_devices(status=device_status)

    return [
        DeviceResponse(
            id=d.id,
            serial=d.serial,
            brand=d.brand,
            model=d.model,
            android_version=d.android_version,
            status=d.status.value if hasattr(d.status, 'value') else str(d.status),
            battery_level=d.battery_level,
            health_score=d.health_score,
            tags=d.get_tags(),
            last_seen_at=d.last_seen_at.isoformat() if d.last_seen_at else None,
        )
        for d in devices
    ]


@router.get("/{serial}", response_model=DeviceResponse)
async def get_device(
    serial: str,
    db: Session = Depends(get_db),
):
    """获取单个设备详情。"""
    service = DeviceService(db)
    device = service.get_device_by_serial(serial)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return DeviceResponse(
        id=device.id,
        serial=device.serial,
        brand=device.brand,
        model=device.model,
        android_version=device.android_version,
        status=device.status.value if hasattr(device.status, 'value') else str(device.status),
        battery_level=device.battery_level,
        health_score=device.health_score,
        tags=device.get_tags(),
        last_seen_at=device.last_seen_at.isoformat() if device.last_seen_at else None,
    )


@router.post("/sync")
async def sync_devices(db: Session = Depends(get_db)):
    """同步设备状态。"""
    from app.executors.mock_executor import MockExecutor
    service = DeviceService(db, runner=MockExecutor.default_device_responses())
    devices = service.sync_devices()

    return {"synced": len(devices), "devices": [d.serial for d in devices]}


@router.post("/{serial}/quarantine")
async def quarantine_device(
    serial: str,
    request: QuarantineRequest,
    db: Session = Depends(get_db),
):
    """隔离异常设备。"""
    service = DeviceService(db)
    device = service.quarantine_device(serial, request.reason)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return {"status": "quarantined", "serial": serial, "reason": request.reason}


@router.post("/{serial}/recover")
async def recover_device(
    serial: str,
    db: Session = Depends(get_db),
):
    """恢复隔离设备。"""
    service = DeviceService(db)
    device = service.recover_device(serial)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return {
        "status": "recovered",
        "serial": serial,
        "new_status": device.status.value if hasattr(device.status, 'value') else str(device.status)
    }


@router.put("/{serial}/tags")
async def update_device_tags(
    serial: str,
    request: TagsUpdate,
    db: Session = Depends(get_db),
):
    """更新设备标签。"""
    service = DeviceService(db)
    device = service.update_device_tags(serial, request.tags)

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return {"status": "updated", "serial": serial, "tags": request.tags}