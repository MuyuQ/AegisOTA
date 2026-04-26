"""Typer CLI 主入口。

labctl 命令行工具，提供设备管理、任务执行和报告导出功能。
"""

import typer

from app.cli.device import app as device_app
from app.cli.pool import app as pool_app
from app.cli.report import app as report_app
from app.cli.run import app as run_app
from app.cli.seed import app as seed_app
from app.cli.worker import worker_app

app = typer.Typer(
    name="labctl",
    help="AegisOTA 命令行工具 - Android OTA 升级异常注入与多设备验证平台",
    no_args_is_help=True,
)

# 注册子命令组
app.add_typer(device_app, name="device")
app.add_typer(run_app, name="run")
app.add_typer(report_app, name="report")
app.add_typer(worker_app, name="worker", help="后台任务执行 Worker")
app.add_typer(pool_app, name="pool", help="设备池管理")
app.add_typer(seed_app, name="seed", help="数据库种子数据管理")


@app.command()
def version():
    """显示版本信息。"""
    from app import __version__

    typer.echo(f"AegisOTA v{__version__}")


if __name__ == "__main__":
    app()
