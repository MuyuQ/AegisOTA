"""设备管理 CLI 命令。

提供设备同步、列表查看、隔离和恢复功能。
"""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from app.database import SessionLocal, init_db
from app.models import Device, DeviceStatus
from app.services.device_service import DeviceService
from app.executors.mock_executor import MockExecutor

app = typer.Typer(help="设备管理命令")
console = Console()


@app.command("sync")
def sync_devices():
    """扫描并同步在线设备。

    通过 ADB 扫描当前连接的设备，并更新数据库中的设备状态。
    """
    init_db()  # 确保数据库表已创建
    db = SessionLocal()

    try:
        typer.echo("正在扫描 ADB 设备...")

        # 使用 DeviceService 进行同步
        service = DeviceService(db, runner=MockExecutor.default_device_responses())
        devices = service.sync_devices()

        typer.echo(f"设备扫描完成，已同步 {len(devices)} 台设备")

        # 显示当前设备状态
        if devices:
            table = Table(title="设备状态")
            table.add_column("序列号", style="cyan")
            table.add_column("品牌", style="green")
            table.add_column("型号", style="green")
            table.add_column("状态", style="yellow")
            table.add_column("最后在线", style="magenta")

            for device in devices:
                # 获取状态值（处理枚举或字符串）
                status_value = device.status.value if hasattr(device.status, 'value') else str(device.status)
                status_style = {
                    DeviceStatus.IDLE: "green",
                    DeviceStatus.BUSY: "yellow",
                    DeviceStatus.OFFLINE: "red",
                    DeviceStatus.QUARANTINED: "red",
                    DeviceStatus.RECOVERING: "blue",
                }.get(device.status if isinstance(device.status, DeviceStatus) else DeviceStatus(device.status), "white")

                table.add_row(
                    device.serial,
                    device.brand or "-",
                    device.model or "-",
                    f"[{status_style}]{status_value}[/{status_style}]",
                    str(device.last_seen_at or "-"),
                )

            console.print(table)
        else:
            typer.echo("数据库中没有设备记录")

    finally:
        db.close()


@app.command("list")
def list_devices(
    status: Optional[str] = typer.Option(
        None, "--status", "-s", help="按状态筛选设备"
    ),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="按标签筛选设备"),
):
    """列出所有设备。

    显示设备列表及其状态、健康评分等信息。
    """
    init_db()
    db = SessionLocal()

    try:
        query = db.query(Device)

        # 按状态筛选
        if status:
            try:
                status_enum = DeviceStatus(status)
                query = query.filter(Device.status == status_enum)
            except ValueError:
                typer.echo(f"无效的状态值: {status}", err=True)
                typer.echo(f"有效状态: {', '.join([s.value for s in DeviceStatus])}")
                raise typer.Exit(1)

        # 按标签筛选（简单字符串匹配）
        if tag:
            query = query.filter(Device.tags.contains(tag))

        devices = query.all()

        if not devices:
            typer.echo("没有找到设备")
            return

        table = Table(title="设备列表")
        table.add_column("ID", style="cyan")
        table.add_column("序列号", style="cyan")
        table.add_column("品牌", style="green")
        table.add_column("型号", style="green")
        table.add_column("Android版本", style="blue")
        table.add_column("状态", style="yellow")
        table.add_column("健康评分", style="magenta")
        table.add_column("电池", style="magenta")
        table.add_column("标签", style="white")

        for device in devices:
            # 获取状态值（处理枚举或字符串）
            status_value = device.status.value if hasattr(device.status, 'value') else str(device.status)
            status_style = {
                DeviceStatus.IDLE: "green",
                DeviceStatus.BUSY: "yellow",
                DeviceStatus.OFFLINE: "red",
                DeviceStatus.QUARANTINED: "red",
                DeviceStatus.RECOVERING: "blue",
            }.get(device.status if isinstance(device.status, DeviceStatus) else DeviceStatus(device.status), "white")

            table.add_row(
                str(device.id),
                device.serial,
                device.brand or "-",
                device.model or "-",
                device.system_version or "-",
                f"[{status_style}]{status_value}[/{status_style}]",
                str(device.health_score or "-"),
                f"{device.battery_level or '-'}%",
                ",".join(device.get_tags()) or "-",
            )

        console.print(table)
        typer.echo(f"\n共 {len(devices)} 台设备")

    finally:
        db.close()


@app.command("quarantine")
def quarantine_device(
    serial: str = typer.Argument(..., help="设备序列号"),
    reason: str = typer.Option(
        "手动隔离", "--reason", "-r", help="隔离原因"
    ),
):
    """隔离设备。

    将设备标记为隔离状态，阻止其参与后续任务。
    """
    init_db()
    db = SessionLocal()

    try:
        # 使用 DeviceService 进行隔离
        service = DeviceService(db)
        device = service.quarantine_device(serial, reason)

        if not device:
            typer.echo(f"设备不存在: {serial}", err=True)
            raise typer.Exit(1)

        typer.echo(f"设备 {serial} 已隔离，原因: {reason}")

    finally:
        db.close()


@app.command("recover")
def recover_device(
    serial: str = typer.Argument(..., help="设备序列号"),
):
    """恢复隔离设备。

    将设备从隔离状态恢复为空闲状态，允许其重新参与任务。
    """
    init_db()
    db = SessionLocal()

    try:
        # 使用 DeviceService 进行恢复
        service = DeviceService(db)
        device = service.recover_device(serial)

        if not device:
            typer.echo(f"设备不存在: {serial}", err=True)
            raise typer.Exit(1)

        status_value = device.status.value if hasattr(device.status, 'value') else str(device.status)
        typer.echo(f"设备 {serial} 已恢复，当前状态: {status_value}")

    finally:
        db.close()