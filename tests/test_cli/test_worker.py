"""Worker CLI 测试。"""

from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


def test_worker_help():
    """测试 Worker 帮助信息。"""
    result = runner.invoke(app, ["worker", "--help"])
    assert result.exit_code == 0


def test_worker_start_command():
    """测试 Worker 启动命令。"""
    # 使用 --max-iterations 限制执行次数
    result = runner.invoke(app, ["worker", "start", "--max-iterations", "0"])
    assert result.exit_code == 0


def test_worker_status_command():
    """测试 Worker 状态命令。"""
    result = runner.invoke(app, ["worker", "status"])
    assert result.exit_code == 0


def test_worker_run_once_command():
    """测试 Worker 执行一次命令。"""
    result = runner.invoke(app, ["worker", "run-once"])
    assert result.exit_code == 0
