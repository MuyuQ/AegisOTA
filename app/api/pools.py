"""设备池 API 路由。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device, DevicePool, DeviceStatus
from app.models.enums import PoolPurpose
from app.services.pool_service import PoolService


router = APIRouter(prefix="/api/pools", tags=["pools"])


class PoolCreate(BaseModel):
    """设备池创建请求。"""

    name: str
    purpose: str
    reserved_ratio: float = 0.2
    max_parallel: int = 5
    tag_selector: Optional[dict] = None
    enabled: bool = True


class PoolUpdate(BaseModel):
    """设备池更新请求。"""

    reserved_ratio: Optional[float] = None
    max_parallel: Optional[int] = None
    tag_selector: Optional[dict] = None
    enabled: Optional[bool] = None


class DeviceAssign(BaseModel):
    """设备分配请求。"""

    device_id: int


class PoolResponse(BaseModel):
    """设备池响应。"""

    id: int
    name: str
    purpose: str
    reserved_ratio: float
    max_parallel: int
    tag_selector: Optional[dict] = None
    enabled: bool

    class Config:
        from_attributes = True


class DeviceResponse(BaseModel):
    """设备响应。"""

    id: int
    serial: str
    status: str
    pool_id: Optional[int] = None

    class Config:
        from_attributes = True


class CapacityResponse(BaseModel):
    """容量响应。"""

    total: int
    available: int
    busy: int
    offline: int
    quarantined: int
    max_parallel: int
    reserved: int
    usable: int


@router.get("", response_model=List[PoolResponse])
async def list_pools(
    purpose: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """获取设备池列表。"""
    service = PoolService(db)
    purpose_enum = PoolPurpose(purpose) if purpose else None
    pools = service.list_pools(purpose=purpose_enum)

    return [
        PoolResponse(
            id=p.id,
            name=p.name,
            purpose=p.purpose.value if hasattr(p.purpose, "value") else str(p.purpose),
            reserved_ratio=p.reserved_ratio,
            max_parallel=p.max_parallel,
            tag_selector=p.get_tag_selector(),
            enabled=p.enabled,
        )
        for p in pools
    ]


@router.post("", response_model=PoolResponse)
async def create_pool(
    request: PoolCreate,
    db: Session = Depends(get_db),
):
    """创建设备池。"""
    service = PoolService(db)

    try:
        purpose = PoolPurpose(request.purpose)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid purpose '{request.purpose}'. Valid values: stable, stress, emergency"
        )

    try:
        pool = service.create_pool(
            name=request.name,
            purpose=purpose,
            reserved_ratio=request.reserved_ratio,
            max_parallel=request.max_parallel,
            tag_selector=request.tag_selector,
            enabled=request.enabled,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PoolResponse(
        id=pool.id,
        name=pool.name,
        purpose=pool.purpose.value if hasattr(pool.purpose, "value") else pool.purpose,
        reserved_ratio=pool.reserved_ratio,
        max_parallel=pool.max_parallel,
        tag_selector=pool.get_tag_selector(),
        enabled=pool.enabled,
    )


@router.get("/{pool_id}", response_model=PoolResponse)
async def get_pool(
    pool_id: int,
    db: Session = Depends(get_db),
):
    """获取设备池详情。"""
    service = PoolService(db)
    pool = service.get_pool_by_id(pool_id)

    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    return PoolResponse(
        id=pool.id,
        name=pool.name,
        purpose=pool.purpose.value if hasattr(pool.purpose, "value") else pool.purpose,
        reserved_ratio=pool.reserved_ratio,
        max_parallel=pool.max_parallel,
        tag_selector=pool.get_tag_selector(),
        enabled=pool.enabled,
    )


@router.put("/{pool_id}", response_model=PoolResponse)
async def update_pool(
    pool_id: int,
    request: PoolUpdate,
    db: Session = Depends(get_db),
):
    """更新设备池配置。"""
    service = PoolService(db)

    update_data = {}
    if request.reserved_ratio is not None:
        update_data["reserved_ratio"] = request.reserved_ratio
    if request.max_parallel is not None:
        update_data["max_parallel"] = request.max_parallel
    if request.tag_selector is not None:
        update_data["tag_selector"] = request.tag_selector
    if request.enabled is not None:
        update_data["enabled"] = request.enabled

    pool = service.update_pool(pool_id, **update_data)

    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    return PoolResponse(
        id=pool.id,
        name=pool.name,
        purpose=pool.purpose.value if hasattr(pool.purpose, "value") else pool.purpose,
        reserved_ratio=pool.reserved_ratio,
        max_parallel=pool.max_parallel,
        tag_selector=pool.get_tag_selector(),
        enabled=pool.enabled,
    )


@router.delete("/{pool_id}")
async def delete_pool(
    pool_id: int,
    db: Session = Depends(get_db),
):
    """删除设备池。"""
    service = PoolService(db)
    success = service.delete_pool(pool_id)

    if not success:
        raise HTTPException(status_code=404, detail="Pool not found")

    return {"status": "deleted", "id": pool_id}


@router.post("/{pool_id}/assign", response_model=DeviceResponse)
async def assign_device(
    pool_id: int,
    request: DeviceAssign,
    db: Session = Depends(get_db),
):
    """分配设备到池。"""
    service = PoolService(db)
    device = service.assign_device_to_pool(request.device_id, pool_id)

    if not device:
        raise HTTPException(status_code=404, detail="Device or pool not found")

    return DeviceResponse(
        id=device.id,
        serial=device.serial,
        status=device.status.value if hasattr(device.status, "value") else str(device.status),
        pool_id=device.pool_id,
    )


@router.get("/{pool_id}/devices", response_model=List[DeviceResponse])
async def get_pool_devices(
    pool_id: int,
    db: Session = Depends(get_db),
):
    """获取池内设备列表。"""
    devices = db.query(Device).filter_by(pool_id=pool_id).all()

    return [
        DeviceResponse(
            id=d.id,
            serial=d.serial,
            status=d.status.value if hasattr(d.status, "value") else str(d.status),
            pool_id=d.pool_id,
        )
        for d in devices
    ]


@router.get("/{pool_id}/capacity", response_model=CapacityResponse)
async def get_pool_capacity(
    pool_id: int,
    db: Session = Depends(get_db),
):
    """获取池容量。"""
    service = PoolService(db)
    capacity = service.get_pool_capacity(pool_id)

    if not capacity:
        raise HTTPException(status_code=404, detail="Pool not found")

    return CapacityResponse(**capacity)