"""设备 API 路由。"""

from datetime import timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.device import Device, DeviceStatus
from app.services.device_service import DeviceService

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


class DeviceResponse(BaseModel):
    """设备响应模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    serial: str
    brand: Optional[str] = None
    model: Optional[str] = None
    system_version: Optional[str] = None
    status: str
    battery_level: Optional[int] = None
    health_score: Optional[float] = None
    tags: List[str] = []
    last_seen_at: Optional[str] = None
    pool_id: Optional[int] = None
    pool_name: Optional[str] = None
    location: Optional[str] = None


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
            valid_values = [s.value for s in DeviceStatus]
            raise HTTPException(
                status_code=400, detail=f"Invalid status '{status}'. Valid values: {valid_values}"
            )

    devices = service.list_devices(status=device_status)

    return [
        DeviceResponse(
            id=d.id,
            serial=d.serial,
            brand=d.brand,
            model=d.model,
            system_version=d.system_version,
            status=d.status.value if hasattr(d.status, "value") else str(d.status),
            battery_level=d.battery_level,
            health_score=d.health_score,
            tags=d.get_tags(),
            last_seen_at=d.last_seen_at.isoformat() if d.last_seen_at else None,
            pool_id=d.pool_id,
            pool_name=d.pool.name if d.pool else None,
            location=d.location,
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
        system_version=device.system_version,
        status=device.status.value if hasattr(device.status, "value") else str(device.status),
        battery_level=device.battery_level,
        health_score=device.health_score,
        tags=device.get_tags(),
        last_seen_at=device.last_seen_at.isoformat() if device.last_seen_at else None,
        pool_id=device.pool_id,
        pool_name=device.pool.name if device.pool else None,
        location=device.location,
    )


@router.post("/sync")
async def sync_devices(db: Session = Depends(get_db)):
    """同步设备状态。"""
    from app.executors.mock_executor import MockExecutor

    service = DeviceService(db, runner=MockExecutor.default_device_responses())
    devices = service.sync_devices()

    return {"synced": len(devices), "devices": [d.serial for d in devices]}


@router.post("/sync/html", response_class=HTMLResponse)
async def sync_devices_html(request: Request, db: Session = Depends(get_db)):
    """同步设备状态并返回 HTML（用于 HTMX）。"""
    from app.executors.mock_executor import MockExecutor

    service = DeviceService(db, runner=MockExecutor.default_device_responses())
    service.sync_devices()

    # 获取更新后的设备列表
    all_devices = db.query(Device).order_by(Device.last_seen_at.desc()).all()

    devices_data = [
        {
            "id": d.id,
            "serial": d.serial,
            "brand": d.brand or "-",
            "model": d.model or "-",
            "system_version": d.system_version or "-",
            "pool_id": d.pool_id,
            "pool_name": d.pool.name if d.pool else None,
            "location": d.location or "-",
            "status": d.status.value if hasattr(d.status, "value") else d.status,
            "battery_level": d.battery_level or "-",
            "health_score": d.health_score or 0,
            "last_seen_at": d.last_seen_at.strftime("%Y-%m-%d %H:%M") if d.last_seen_at else "-",
        }
        for d in all_devices
    ]

    # 构建表格 HTML
    rows_html = ""
    for d in devices_data:
        status_class = f"status-{d['status']}"

        pool_html = (
            f'<a href="/pools/{d["pool_id"]}" style="text-decoration: none;">'
            f'<span class="status-badge" style="background: var(--primary-color); color: white;">'
            f"{d['pool_name']}</span></a>"
            if d["pool_name"]
            else '<span style="color: var(--text-muted);">-</span>'
        )

        health_class = (
            "health-high"
            if d["health_score"] >= 80
            else "health-medium"
            if d["health_score"] >= 50
            else "health-low"
        )

        action_btn = ""
        if d["status"] == "quarantined":
            action_btn = (
                f'<button class="btn btn-sm btn-primary" '
                f'hx-post="/api/v1/devices/{d["serial"]}/recover/html" '
                f'hx-swap="outerHTML" hx-target="closest tr">恢复</button>'
            )
        elif d["status"] == "idle":
            action_btn = (
                f'<button class="btn btn-sm btn-danger" '
                f'hx-post="/api/v1/devices/{d["serial"]}/quarantine/html" '
                f'hx-swap="outerHTML" hx-target="closest tr">隔离</button>'
            )

        rows_html += f'''
        <tr>
            <td><strong>{d["serial"]}</strong></td>
            <td>{d["brand"]} {d["model"]}</td>
            <td>{d["system_version"]}</td>
            <td>{pool_html}</td>
            <td>{d["location"]}</td>
            <td><span class="status-badge {status_class}">{d["status"]}</span></td>
            <td>{d["battery_level"]}%</td>
            <td>
                <a href="#" hx-get="/api/v1/devices/{d["serial"]}/health-detail"
                   hx-target="#modal-container" hx-swap="innerHTML"
                   onclick="document.getElementById('modal-container').style.display='flex'"
                   style="text-decoration: none; cursor: pointer;">
                    <span class="{health_class}" style="font-weight: 600;">
                        {d["health_score"]}%
                    </span>
                </a>
            </td>
            <td>{d["last_seen_at"]}</td>
            <td>{action_btn}</td>
        </tr>'''

    html = f"""
    <table class="table">
        <thead>
            <tr>
                <th>序列号</th>
                <th>品牌/型号</th>
                <th>系统版本</th>
                <th>设备池</th>
                <th>物理位置</th>
                <th>状态</th>
                <th>电量</th>
                <th>健康度</th>
                <th>最后在线</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
    <div class="alert alert-success">同步完成，已更新 {len(devices_data)} 台设备</div>
    """

    return HTMLResponse(content=html)


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


@router.post("/{serial}/quarantine/html", response_class=HTMLResponse)
async def quarantine_device_html(
    serial: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """隔离异常设备并返回 HTML 行（用于 HTMX）。"""
    service = DeviceService(db)
    device = service.quarantine_device(serial, "手动隔离")

    if not device:
        return HTMLResponse(content='<div class="alert alert-error">设备不存在</div>')

    d = {
        "id": device.id,
        "serial": device.serial,
        "brand": device.brand or "-",
        "model": device.model or "-",
        "system_version": device.system_version or "-",
        "pool_id": device.pool_id,
        "pool_name": device.pool.name if device.pool else None,
        "location": device.location or "-",
        "status": device.status.value if hasattr(device.status, "value") else device.status,
        "battery_level": device.battery_level or "-",
        "health_score": device.health_score or 0,
        "last_seen_at": device.last_seen_at.strftime("%Y-%m-%d %H:%M")
        if device.last_seen_at
        else "-",
    }

    pool_html = (
        f'<a href="/pools/{d["pool_id"]}" style="text-decoration: none;">'
        f'<span class="status-badge" style="background: var(--primary-color); color: white;">'
        f"{d['pool_name']}</span></a>"
        if d["pool_name"]
        else '<span style="color: var(--text-muted);">-</span>'
    )

    health_class = (
        "health-high"
        if d["health_score"] >= 80
        else "health-medium"
        if d["health_score"] >= 50
        else "health-low"
    )

    return HTMLResponse(
        content=f'''
    <tr>
        <td><strong>{d["serial"]}</strong></td>
        <td>{d["brand"]} {d["model"]}</td>
        <td>{d["system_version"]}</td>
        <td>{pool_html}</td>
        <td>{d["location"]}</td>
        <td><span class="status-badge status-quarantined">{d["status"]}</span></td>
        <td>{d["battery_level"]}%</td>
        <td>
            <a href="#" hx-get="/api/v1/devices/{d["serial"]}/health-detail"
               hx-target="#modal-container" hx-swap="innerHTML"
               onclick="document.getElementById('modal-container').style.display='flex'"
               style="text-decoration: none; cursor: pointer;">
                <span class="{health_class}" style="font-weight: 600;">
                    {d["health_score"]}%
                </span>
            </a>
        </td>
        <td>{d["last_seen_at"]}</td>
        <td>
            <button class="btn btn-sm btn-primary"
                    hx-post="/api/v1/devices/{d["serial"]}/recover/html"
                    hx-swap="outerHTML" hx-target="closest tr">恢复</button>
        </td>
    </tr>'''
    )


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
        "new_status": device.status.value
        if hasattr(device.status, "value")
        else str(device.status),
    }


@router.post("/{serial}/recover/html", response_class=HTMLResponse)
async def recover_device_html(
    serial: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """恢复隔离设备并返回 HTML 行（用于 HTMX）。"""
    service = DeviceService(db)
    device = service.recover_device(serial)

    if not device:
        return HTMLResponse(content='<div class="alert alert-error">设备不存在</div>')

    d = {
        "id": device.id,
        "serial": device.serial,
        "brand": device.brand or "-",
        "model": device.model or "-",
        "system_version": device.system_version or "-",
        "pool_id": device.pool_id,
        "pool_name": device.pool.name if device.pool else None,
        "location": device.location or "-",
        "status": device.status.value if hasattr(device.status, "value") else device.status,
        "battery_level": device.battery_level or "-",
        "health_score": device.health_score or 0,
        "last_seen_at": device.last_seen_at.strftime("%Y-%m-%d %H:%M")
        if device.last_seen_at
        else "-",
    }

    status_class = f"status-{d['status']}"
    pool_html = (
        f'<a href="/pools/{d["pool_id"]}" style="text-decoration: none;">'
        f'<span class="status-badge" style="background: var(--primary-color); color: white;">'
        f"{d['pool_name']}</span></a>"
        if d["pool_name"]
        else '<span style="color: var(--text-muted);">-</span>'
    )

    health_class = (
        "health-high"
        if d["health_score"] >= 80
        else "health-medium"
        if d["health_score"] >= 50
        else "health-low"
    )

    action_btn = ""
    if d["status"] == "idle":
        action_btn = (
            f'<button class="btn btn-sm btn-danger" '
            f'hx-post="/api/v1/devices/{d["serial"]}/quarantine/html" '
            f'hx-swap="outerHTML" hx-target="closest tr">隔离</button>'
        )

    return HTMLResponse(
        content=f'''
    <tr>
        <td><strong>{d["serial"]}</strong></td>
        <td>{d["brand"]} {d["model"]}</td>
        <td>{d["system_version"]}</td>
        <td>{pool_html}</td>
        <td>{d["location"]}</td>
        <td><span class="status-badge {status_class}">{d["status"]}</span></td>
        <td>{d["battery_level"]}%</td>
        <td>
            <a href="#" hx-get="/api/v1/devices/{d["serial"]}/health-detail"
               hx-target="#modal-container" hx-swap="innerHTML"
               onclick="document.getElementById('modal-container').style.display='flex'"
               style="text-decoration: none; cursor: pointer;">
                <span class="{health_class}" style="font-weight: 600;">
                    {d["health_score"]}%
                </span>
            </a>
        </td>
        <td>{d["last_seen_at"]}</td>
        <td>{action_btn}</td>
    </tr>'''
    )


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


@router.get("/{serial}/health-detail", response_class=HTMLResponse)
async def get_device_health_detail(
    serial: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """获取设备健康度详情（HTML 片段，用于模态框）。"""
    from datetime import datetime

    from app.models.run import RunSession

    device = db.query(Device).filter_by(serial=serial).first()

    if not device:
        return HTMLResponse(content='<div class="alert alert-error">设备不存在</div>')

    # 定义所有健康度因素
    health_factors = []

    # 1. 电池健康
    battery_impact = 0
    battery_value = f"{device.battery_level}%" if device.battery_level else "N/A"
    if device.battery_level is not None:
        if device.battery_level < 20:
            battery_impact = -30
        elif device.battery_level < 50:
            battery_impact = -10
    health_factors.append(
        {
            "label": "电池健康",
            "value": battery_value,
            "impact": battery_impact,
        }
    )

    # 2. 设备状态
    status_impact = 0
    status_value = device.status.value if hasattr(device.status, "value") else str(device.status)
    if device.status == DeviceStatus.OFFLINE:
        status_impact = -20
    elif device.status == DeviceStatus.QUARANTINED:
        status_impact = -50
    health_factors.append(
        {
            "label": "设备状态",
            "value": status_value,
            "impact": status_impact,
        }
    )

    # 3. 升级成功率 (优化: 使用聚合查询替代加载全部对象)
    run_stats = (
        db.query(
            func.count(RunSession.id),
            func.sum(func.case((RunSession.status.in_(["failed", "aborted"]), 1), else_=0)),
        )
        .filter(RunSession.device_id == device.id)
        .first()
    )

    total_runs = run_stats[0] if run_stats[0] else 0
    failed_runs = run_stats[1] if run_stats[1] else 0

    if total_runs > 0:
        success_rate = (total_runs - failed_runs) / total_runs * 100
        success_impact = 0
        if success_rate < 50:
            success_impact = -20
        elif success_rate < 80:
            success_impact = -10
        health_factors.append(
            {
                "label": "升级成功率",
                "value": f"{success_rate:.1f}% ({total_runs}次)",
                "impact": success_impact,
            }
        )
    else:
        health_factors.append(
            {
                "label": "升级成功率",
                "value": "N/A (无历史记录)",
                "impact": 0,
            }
        )

    # 4. 存储空间 (待采集)
    health_factors.append(
        {
            "label": "存储空间",
            "value": "N/A",
            "impact": 0,
        }
    )

    # 5. 设备温度 (待采集)
    health_factors.append(
        {
            "label": "设备温度",
            "value": "N/A",
            "impact": 0,
        }
    )

    # 6. 系统稳定性 (待采集)
    health_factors.append(
        {
            "label": "系统稳定性",
            "value": "N/A",
            "impact": 0,
        }
    )

    # 7. 最近同步时间
    sync_impact = 0
    if device.last_seen_at:
        hours_since = (datetime.now(timezone.utc) - device.last_seen_at).total_seconds() / 3600
        if hours_since > 24:
            sync_impact = -10
        sync_value = device.last_seen_at.strftime("%Y-%m-%d %H:%M")
    else:
        sync_value = "N/A"
    health_factors.append(
        {
            "label": "最近同步",
            "value": sync_value,
            "impact": sync_impact,
        }
    )

    # 计算总分（使用数据库中存储的健康度分数）
    total_score = device.health_score if device.health_score is not None else 100

    # 确定健康等级
    if total_score >= 80:
        health_level = "high"
        health_status = "优秀"
    elif total_score >= 50:
        health_level = "medium"
        health_status = "一般"
    else:
        health_level = "low"
        health_status = "较差"

    # 构建因素表格行（仅显示当前值，不显示影响分）
    factor_rows = ""
    for f in health_factors:
        value_class = "health-low" if f["impact"] < 0 else ""
        factor_rows += f'''
        <tr>
            <td>{f["label"]}</td>
            <td class="{value_class}">{f["value"]}</td>
        </tr>'''

    # 构建 HTML
    html = f"""
    <div class="modal-content" onclick="event.stopPropagation()">
        <div class="modal-header">
            <span class="modal-title">设备健康度详情</span>
            <button class="modal-close"
                    onclick="document.getElementById('modal-container').style.display='none'">
                &times;
            </button>
        </div>

        <div style="text-align: center; margin: 1.5rem 0;">
            <div style="font-size: 3rem; font-weight: bold;" class="health-{health_level}">
                {total_score}%
            </div>
            <div style="color: var(--text-muted);">健康状态：{health_status}</div>
        </div>

        <div style="margin: 1rem 0;">
            <div class="health-bar">
                <div class="health-bar-fill {health_level}" style="width: {total_score}%"></div>
            </div>
        </div>

        <div class="card-header" style="margin-top: 1rem;">设备信息</div>
        <table class="table" style="margin-top: 0.5rem;">
            <tr><td style="width: 120px;">序列号</td><td><code>{device.serial}</code></td></tr>
            <tr><td>品牌/型号</td><td>{device.brand or "-"} {device.model or "-"}</td></tr>
            <tr><td>系统版本</td><td>{device.system_version or "-"}</td></tr>
            <tr><td>物理位置</td><td>{device.location or "-"}</td></tr>
        </table>

        <div class="card-header" style="margin-top: 1rem;">状态指标</div>
        <table class="table" style="margin-top: 0.5rem;">
            <thead>
                <tr>
                    <th>指标</th>
                    <th>当前值</th>
                </tr>
            </thead>
            <tbody>
                {factor_rows}
            </tbody>
        </table>
    </div>
    """

    return HTMLResponse(content=html)
