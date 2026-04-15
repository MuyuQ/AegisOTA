"""设备池 CLI 命令。"""

import typer
from rich.console import Console
from rich.table import Table

from app.database import SessionLocal
from app.models.enums import PoolPurpose
from app.services.pool_service import PoolService

app = typer.Typer(name="pool", help="设备池管理命令")
console = Console()


@app.command("list")
def list_pools():
    """列出所有设备池。"""
    db = SessionLocal()
    try:
        service = PoolService(db)
        pools = service.list_pools()

        if not pools:
            console.print(
                "[yellow]No pools found. Run 'pool init' to create default pools.[/yellow]"
            )
            return

        table = Table(title="Device Pools")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Purpose", style="blue")
        table.add_column("Reserved", style="yellow")
        table.add_column("Max Parallel", style="magenta")
        table.add_column("Enabled", style="white")

        for pool in pools:
            table.add_row(
                str(pool.id),
                pool.name,
                pool.purpose.value if hasattr(pool.purpose, "value") else str(pool.purpose),
                f"{pool.reserved_ratio:.0%}",
                str(pool.max_parallel),
                "✓" if pool.enabled else "✗",
            )

        console.print(table)
    finally:
        db.close()


@app.command("create")
def create_pool(
    name: str = typer.Option(..., "--name", "-n", help="设备池名称"),
    purpose: str = typer.Option(
        "stable", "--purpose", "-p", help="设备池用途: stable, stress, emergency"
    ),
    reserved_ratio: float = typer.Option(0.2, "--reserved-ratio", "-r", help="保留比例"),
    max_parallel: int = typer.Option(5, "--max-parallel", "-m", help="最大并行数"),
):
    """创建设备池。"""
    db = SessionLocal()
    try:
        service = PoolService(db)
        try:
            purpose_enum = PoolPurpose(purpose)
        except ValueError:
            console.print(
                f"[red]Invalid purpose '{purpose}'. Valid values: stable, stress, emergency[/red]"
            )
            raise typer.Exit(1)

        try:
            pool = service.create_pool(
                name=name,
                purpose=purpose_enum,
                reserved_ratio=reserved_ratio,
                max_parallel=max_parallel,
            )
            console.print(f"[green]Created pool '{pool.name}' (ID: {pool.id})[/green]")
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)
    finally:
        db.close()


@app.command("show")
def show_pool(
    name: str = typer.Option(None, "--name", "-n", help="设备池名称"),
    pool_id: int = typer.Option(None, "--id", help="设备池 ID"),
):
    """显示设备池详情。"""
    db = SessionLocal()
    try:
        service = PoolService(db)

        if pool_id:
            pool = service.get_pool_by_id(pool_id)
        elif name:
            pool = service.get_pool_by_name(name)
        else:
            console.print("[red]Please specify --name or --id[/red]")
            raise typer.Exit(1)

        if not pool:
            console.print("[red]Pool not found[/red]")
            raise typer.Exit(1)

        # 显示详情
        capacity = service.get_pool_capacity(pool.id)

        console.print(f"\n[bold cyan]Pool: {pool.name}[/bold cyan]")
        console.print(f"  ID: {pool.id}")
        console.print(
            f"  Purpose: {pool.purpose.value if hasattr(pool.purpose, 'value') else pool.purpose}"
        )
        console.print(f"  Reserved Ratio: {pool.reserved_ratio:.0%}")
        console.print(f"  Max Parallel: {pool.max_parallel}")
        console.print(f"  Enabled: {'Yes' if pool.enabled else 'No'}")

        console.print("\n[bold]Capacity:[/bold]")
        console.print(f"  Total Devices: {capacity['total']}")
        console.print(f"  Available: {capacity['available']}")
        console.print(f"  Busy: {capacity['busy']}")
        console.print(f"  Reserved: {capacity['reserved']}")
    finally:
        db.close()


@app.command("update")
def update_pool(
    name: str = typer.Option(None, "--name", "-n", help="设备池名称"),
    pool_id: int = typer.Option(None, "--id", help="设备池 ID"),
    reserved_ratio: float = typer.Option(None, "--reserved-ratio", "-r", help="保留比例"),
    max_parallel: int = typer.Option(None, "--max-parallel", "-m", help="最大并行数"),
    enabled: bool = typer.Option(None, "--enabled/--disabled", help="启用/禁用"),
):
    """更新设备池配置。"""
    db = SessionLocal()
    try:
        service = PoolService(db)

        if pool_id:
            target_id = pool_id
        elif name:
            pool = service.get_pool_by_name(name)
            if not pool:
                console.print("[red]Pool not found[/red]")
                raise typer.Exit(1)
            target_id = pool.id
        else:
            console.print("[red]Please specify --name or --id[/red]")
            raise typer.Exit(1)

        update_data = {}
        if reserved_ratio is not None:
            update_data["reserved_ratio"] = reserved_ratio
        if max_parallel is not None:
            update_data["max_parallel"] = max_parallel
        if enabled is not None:
            update_data["enabled"] = enabled

        if not update_data:
            console.print("[yellow]No updates specified[/yellow]")
            return

        pool = service.update_pool(target_id, **update_data)
        console.print(f"[green]Updated pool '{pool.name}'[/green]")
    finally:
        db.close()


@app.command("init")
def init_pools():
    """初始化默认设备池。"""
    db = SessionLocal()
    try:
        service = PoolService(db)
        pools = service.create_default_pools()

        console.print("[green]Created default pools:[/green]")
        for pool in pools:
            console.print(
                f"  - {pool.name} ("
                f"{pool.purpose.value if hasattr(pool.purpose, 'value') else pool.purpose}"
                f")"
            )
    finally:
        db.close()


@app.command("assign")
def assign_device(
    device_id: int = typer.Option(..., "--device-id", "-d", help="设备 ID"),
    pool_name: str = typer.Option(..., "--pool-name", "-p", help="设备池名称"),
):
    """分配设备到池。"""
    db = SessionLocal()
    try:
        service = PoolService(db)
        pool = service.get_pool_by_name(pool_name)

        if not pool:
            console.print(f"[red]Pool '{pool_name}' not found[/red]")
            raise typer.Exit(1)

        device = service.assign_device_to_pool(device_id, pool.id)

        if not device:
            console.print(f"[red]Device {device_id} not found[/red]")
            raise typer.Exit(1)

        console.print(f"[green]Assigned device {device_id} to pool '{pool_name}'[/green]")
    finally:
        db.close()
