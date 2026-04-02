"""任务执行 CLI 命令。

提供任务提交、查看、中止和执行功能。
"""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from app.database import SessionLocal, init_db
from app.models import RunSession, RunStatus, UpgradePlan, Device, DeviceStatus
from app.services.run_service import RunService

app = typer.Typer(help="任务管理命令")
console = Console()


@app.command("submit")
def submit_run(
    plan_id: int = typer.Argument(..., help="升级计划 ID"),
    device_serial: Optional[str] = typer.Option(
        None, "--device", "-d", help="指定设备序列号"
    ),
):
    """提交升级任务。

    根据升级计划创建任务，可选择指定设备或自动分配。
    """
    init_db()
    db = SessionLocal()

    try:
        service = RunService(db)

        # 检查升级计划是否存在
        plan = service.get_upgrade_plan(plan_id)
        if not plan:
            typer.echo(f"升级计划不存在: {plan_id}", err=True)
            raise typer.Exit(1)

        # 查找可用设备
        device_id = None
        if device_serial:
            device = db.query(Device).filter(Device.serial == device_serial).first()
            if not device:
                typer.echo(f"设备不存在: {device_serial}", err=True)
                raise typer.Exit(1)
            if not device.is_available():
                typer.echo(f"设备 {device_serial} 当前不可用，状态: {device.status.value}")
                raise typer.Exit(1)
            device_id = device.id
        else:
            # 自动分配空闲设备
            device = db.query(Device).filter(Device.status == DeviceStatus.IDLE).first()
            if not device:
                typer.echo("没有可用设备", err=True)
                raise typer.Exit(1)
            device_id = device.id

        # 使用 RunService 创建任务
        run_session = service.create_run_session(
            plan_id=plan.id,
            device_id=device_id,
        )

        # 更新设备状态（服务层不处理这个，需要手动处理）
        device = db.query(Device).filter(Device.id == device_id).first()
        device.status = DeviceStatus.BUSY
        db.commit()

        typer.echo(f"任务已创建:")
        typer.echo(f"  任务 ID: {run_session.id}")
        typer.echo(f"  升级计划: {plan.name}")
        typer.echo(f"  设备: {device.serial}")
        typer.echo(f"  状态: {run_session.status.value if hasattr(run_session.status, 'value') else run_session.status}")

    finally:
        db.close()


@app.command("list")
def list_runs(
    status: Optional[str] = typer.Option(
        None, "--status", "-s", help="按状态筛选任务"
    ),
    limit: int = typer.Option(20, "--limit", "-l", help="显示数量限制"),
):
    """列出所有任务。

    显示任务列表及其状态、执行进度等信息。
    """
    init_db()
    db = SessionLocal()

    try:
        query = db.query(RunSession)

        # 按状态筛选
        if status:
            try:
                status_enum = RunStatus(status)
                query = query.filter(RunSession.status == status_enum)
            except ValueError:
                typer.echo(f"无效的状态值: {status}", err=True)
                typer.echo(f"有效状态: {', '.join([s.value for s in RunStatus])}")
                raise typer.Exit(1)

        # 按创建时间倒序排列
        query = query.order_by(RunSession.created_at.desc())

        runs = query.limit(limit).all()

        if not runs:
            typer.echo("没有找到任务")
            return

        table = Table(title="任务列表")
        table.add_column("ID", style="cyan")
        table.add_column("计划", style="green")
        table.add_column("设备", style="magenta")
        table.add_column("状态", style="yellow")
        table.add_column("创建时间", style="blue")
        table.add_column("持续时间", style="white")

        for run in runs:
            status_style = {
                RunStatus.QUEUED: "white",
                RunStatus.RESERVED: "blue",
                RunStatus.RUNNING: "yellow",
                RunStatus.VALIDATING: "cyan",
                RunStatus.PASSED: "green",
                RunStatus.FAILED: "red",
                RunStatus.ABORTED: "orange",
                RunStatus.QUARANTINED: "red",
            }.get(run.status, "white")

            plan_name = run.plan.name if run.plan else "-"
            device_serial = run.device.serial if run.device else "-"
            duration = run.get_duration_seconds()
            duration_str = f"{duration:.1f}s" if duration else "-"

            table.add_row(
                str(run.id),
                plan_name,
                device_serial,
                f"[{status_style}]{run.status.value}[/{status_style}]",
                str(run.created_at),
                duration_str,
            )

        console.print(table)
        typer.echo(f"\n共 {len(runs)} 个任务")

    finally:
        db.close()


@app.command("abort")
def abort_run(
    run_id: int = typer.Argument(..., help="任务 ID"),
):
    """中止任务。

    将运行中的任务标记为已中止状态。
    """
    init_db()
    db = SessionLocal()

    try:
        service = RunService(db)

        # 使用 RunService 中止任务
        run = service.abort_run_session(run_id, reason="用户手动中止")

        if not run:
            typer.echo(f"任务不存在或无法中止: {run_id}", err=True)
            raise typer.Exit(1)

        # 释放设备（服务层不处理这个，需要手动处理）
        if run.device:
            run.device.status = DeviceStatus.IDLE
            db.commit()

        typer.echo(f"任务 {run_id} 已中止")

    finally:
        db.close()


@app.command("execute")
def execute_run(
    run_id: int = typer.Argument(..., help="任务 ID"),
):
    """执行任务（Worker 模式）。

    在本地设备上执行指定的升级任务。实际执行时会调用 ADB/Fastboot 命令。
    """
    init_db()
    db = SessionLocal()

    try:
        run = db.query(RunSession).filter(RunSession.id == run_id).first()

        if not run:
            typer.echo(f"任务不存在: {run_id}", err=True)
            raise typer.Exit(1)

        if run.status not in (RunStatus.QUEUED, RunStatus.RESERVED):
            typer.echo(f"任务 {run_id} 状态不正确: {run.status.value}")
            typer.echo("任务必须是 queued 或 reserved 状态才能执行")
            raise typer.Exit(1)

        # 检查设备是否绑定
        if not run.device:
            typer.echo(f"任务 {run_id} 未绑定设备")
            raise typer.Exit(1)

        # 更新状态为运行中
        run.status = RunStatus.RUNNING
        db.commit()

        typer.echo(f"开始执行任务 {run_id}")
        typer.echo(f"设备: {run.device.serial}")

        if run.plan:
            typer.echo(f"升级计划: {run.plan.name}")
            typer.echo(f"升级类型: {run.plan.upgrade_type.value}")

        # 实际执行逻辑（占位实现）
        # 实际实现需要:
        # 1. 调用 app.executors.command_runner 执行 ADB/Fastboot 命令
        # 2. 调用 app.faults 插件进行故障注入
        # 3. 调用 app.validators 进行升级验证
        # 4. 记录 RunStep 和 Artifact

        typer.echo("\n当前为模拟执行模式，实际执行需要完整实现:")
        typer.echo("  - precheck: 预检查设备状态")
        typer.echo("  - package_prepare: 准备升级包")
        typer.echo("  - apply_update: 应用升级")
        typer.echo("  - reboot_wait: 等待重启完成")
        typer.echo("  - post_validate: 升级后验证")
        typer.echo("  - report_finalize: 生成报告")

        # 模拟执行完成
        run.status = RunStatus.PASSED
        run.device.status = DeviceStatus.IDLE
        db.commit()

        typer.echo(f"\n任务 {run_id} 执行完成（模拟）")

    finally:
        db.close()