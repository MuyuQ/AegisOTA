"""Worker CLI 命令。"""

import signal

import typer

from app.database import SessionLocal
from app.services.worker_service import WorkerService

worker_app = typer.Typer(help="后台任务执行 Worker")

# 全局 Worker 实例
_worker: WorkerService = None


def signal_handler(signum, frame):
    """信号处理器。"""
    global _worker
    if _worker:
        typer.echo("\n停止 Worker...")
        _worker.stop()
        typer.echo("Worker 已停止")


@worker_app.command("start")
def worker_start(
    poll_interval: int = typer.Option(5, "--poll", "-p", help="轮询间隔（秒）"),
    max_concurrent: int = typer.Option(5, "--concurrent", "-c", help="最大并发任务数"),
    max_iterations: int = typer.Option(
        -1, "--max-iterations", "-n", help="最大迭代次数（-1 为无限）"
    ),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="守护进程模式"),
):
    """启动任务执行 Worker。"""
    global _worker

    typer.echo(f"启动 Worker（轮询间隔: {poll_interval}s, 最大并发: {max_concurrent}）")

    db = SessionLocal()
    _worker = WorkerService(
        db=db,
        poll_interval=poll_interval,
        max_concurrent=max_concurrent,
        max_iterations=max_iterations,
    )

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if max_iterations >= 0:
        # 有限次执行（0 次表示只启动不执行任何迭代）
        for i in range(max_iterations):
            _worker.process_one_iteration()
        if max_iterations > 0:
            typer.echo(f"完成 {max_iterations} 次迭代")
        else:
            typer.echo("Worker 已初始化（max-iterations=0）")
    else:
        # 无限循环
        _worker.start()
        typer.echo("Worker 运行中，按 Ctrl+C 停止")

        # 等待停止信号
        try:
            while _worker.running:
                import time

                time.sleep(1)
        except KeyboardInterrupt:
            _worker.stop()

    db.close()


@worker_app.command("status")
def worker_status():
    """查看 Worker 状态。"""
    db = SessionLocal()
    worker = WorkerService(db=db, max_iterations=0)

    running_count = worker.get_running_count()

    typer.echo("Worker 状态:")
    typer.echo(f"  正在运行任务: {running_count}")
    typer.echo(f"  最大并发: {worker.max_concurrent}")

    db.close()


@worker_app.command("run-once")
def worker_run_once():
    """执行一次任务轮询。"""
    db = SessionLocal()
    worker = WorkerService(db=db, max_iterations=1)

    typer.echo("执行一次任务轮询...")
    result = worker.process_one_iteration()

    if result:
        typer.echo(f"执行任务 #{result.id}: {result.status}")
    else:
        typer.echo("没有待执行的任务")

    db.close()
