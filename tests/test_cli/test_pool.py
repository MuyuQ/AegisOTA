"""Pool CLI 测试。"""

import pytest
from typer.testing import CliRunner

from app.cli.main import app
from app.database import SessionLocal, init_db, engine
from app.models.device import DevicePool

runner = CliRunner()


@pytest.fixture
def setup_db():
    """设置测试数据库。"""
    # 确保数据库表已创建
    init_db(engine)

    db = SessionLocal()
    yield db
    # 清理测试数据
    db.query(DevicePool).delete()
    db.commit()
    db.close()


class TestPoolCLI:
    """Pool CLI 测试。"""

    def test_pool_help_displays_correctly(self):
        """测试 pool 命令帮助显示正确。"""
        result = runner.invoke(app, ["pool", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "create" in result.output
        assert "show" in result.output
        assert "init" in result.output

    def test_pool_list_empty(self, setup_db):
        """测试空池列表。"""
        result = runner.invoke(app, ["pool", "list"])
        assert result.exit_code == 0
        assert "No pools" in result.output or "run 'pool init'" in result.output.lower()

    def test_pool_create(self, setup_db):
        """测试创建设备池。"""
        result = runner.invoke(app, [
            "pool", "create",
            "--name", "cli_pool",
            "--purpose", "stable",
        ])
        assert result.exit_code == 0
        assert "cli_pool" in result.output

    def test_pool_create_duplicate(self, setup_db):
        """测试创建重复名称设备池。"""
        runner.invoke(app, [
            "pool", "create",
            "--name", "duplicate_pool",
            "--purpose", "stable",
        ])
        result = runner.invoke(app, [
            "pool", "create",
            "--name", "duplicate_pool",
            "--purpose", "stress",
        ])
        assert result.exit_code == 1

    def test_pool_show(self, setup_db):
        """测试显示设备池详情。"""
        # 先创建
        runner.invoke(app, [
            "pool", "create",
            "--name", "show_pool",
            "--purpose", "stable",
        ])

        result = runner.invoke(app, ["pool", "show", "--name", "show_pool"])
        assert result.exit_code == 0
        assert "show_pool" in result.output

    def test_pool_show_not_found(self, setup_db):
        """测试显示不存在的设备池。"""
        result = runner.invoke(app, ["pool", "show", "--name", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_pool_update(self, setup_db):
        """测试更新设备池。"""
        runner.invoke(app, [
            "pool", "create",
            "--name", "update_pool",
            "--purpose", "stable",
        ])

        result = runner.invoke(app, [
            "pool", "update",
            "--name", "update_pool",
            "--reserved-ratio", "0.3",
        ])
        assert result.exit_code == 0

    def test_pool_init_defaults(self, setup_db):
        """测试初始化默认池。"""
        result = runner.invoke(app, ["pool", "init"])
        assert result.exit_code == 0
        assert "stable_pool" in result.output
        assert "stress_pool" in result.output
        assert "emergency_pool" in result.output