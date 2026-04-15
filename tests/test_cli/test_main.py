"""CLI 命令测试。"""

from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


class TestMainCLI:
    """主 CLI 入口测试。"""

    def test_help_displays_correctly(self):
        """测试主命令帮助显示正确。"""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "AegisOTA" in result.output
        assert "device" in result.output
        assert "run" in result.output
        assert "report" in result.output
        assert "version" in result.output

    def test_version_command(self):
        """测试 version 命令显示版本信息。"""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "AegisOTA" in result.output
        assert "0.1.0" in result.output

    def test_no_args_shows_help(self):
        """测试无参数时显示帮助。"""
        result = runner.invoke(app)
        # Typer no_args_is_help 返回 exit code 2 但显示帮助内容
        assert "AegisOTA" in result.output
        assert "device" in result.output


class TestDeviceCLI:
    """设备管理命令测试。"""

    def test_device_help_displays_correctly(self):
        """测试设备命令帮助显示正确。"""
        result = runner.invoke(app, ["device", "--help"])
        assert result.exit_code == 0
        assert "sync" in result.output
        assert "list" in result.output
        assert "quarantine" in result.output
        assert "recover" in result.output

    def test_device_sync_help(self):
        """测试 device sync 帮助显示正确。"""
        result = runner.invoke(app, ["device", "sync", "--help"])
        assert result.exit_code == 0
        assert "扫描" in result.output or "ADB" in result.output

    def test_device_list_help(self):
        """测试 device list 帮助显示正确。"""
        result = runner.invoke(app, ["device", "list", "--help"])
        assert result.exit_code == 0
        assert "列出" in result.output or "status" in result.output

    def test_device_list_empty(self):
        """测试设备列表为空时的输出。"""
        result = runner.invoke(app, ["device", "list"])
        assert result.exit_code == 0
        assert "没有找到设备" in result.output or "设备列表" in result.output

    def test_device_quarantine_help(self):
        """测试 device quarantine 帮助显示正确。"""
        result = runner.invoke(app, ["device", "quarantine", "--help"])
        assert result.exit_code == 0
        assert "隔离" in result.output or "serial" in result.output

    def test_device_quarantine_missing_device(self):
        """测试隔离不存在的设备。"""
        result = runner.invoke(app, ["device", "quarantine", "nonexistent"])
        assert result.exit_code == 1
        assert "不存在" in result.output

    def test_device_recover_help(self):
        """测试 device recover 命令帮助。"""
        result = runner.invoke(app, ["device", "recover", "--help"])
        assert result.exit_code == 0
        assert "恢复" in result.output or "serial" in result.output

    def test_device_recover_missing_device(self):
        """测试恢复不存在的设备。"""
        result = runner.invoke(app, ["device", "recover", "nonexistent"])
        assert result.exit_code == 1
        assert "不存在" in result.output


class TestRunCLI:
    """任务管理命令测试。"""

    def test_run_help_displays_correctly(self):
        """测试任务命令帮助显示正确。"""
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "submit" in result.output
        assert "list" in result.output
        assert "abort" in result.output
        assert "execute" in result.output

    def test_run_submit_help(self):
        """测试 run submit 命令帮助。"""
        result = runner.invoke(app, ["run", "submit", "--help"])
        assert result.exit_code == 0
        assert "提交" in result.output or "plan" in result.output

    def test_run_submit_missing_plan(self):
        """测试提交任务时升级计划不存在。"""
        result = runner.invoke(app, ["run", "submit", "999"])
        assert result.exit_code == 1
        assert "不存在" in result.output

    def test_run_list_help(self):
        """测试 run list 命令帮助。"""
        result = runner.invoke(app, ["run", "list", "--help"])
        assert result.exit_code == 0
        assert "列出" in result.output or "status" in result.output

    def test_run_list_empty(self):
        """测试任务列表为空时的输出。"""
        result = runner.invoke(app, ["run", "list"])
        assert result.exit_code == 0
        assert "没有找到任务" in result.output or "任务列表" in result.output

    def test_run_abort_help(self):
        """测试 run abort 命令帮助。"""
        result = runner.invoke(app, ["run", "abort", "--help"])
        assert result.exit_code == 0
        assert "中止" in result.output or "run_id" in result.output

    def test_run_abort_missing_run(self):
        """测试中止不存在的任务。"""
        result = runner.invoke(app, ["run", "abort", "999"])
        assert result.exit_code == 1
        assert "不存在" in result.output

    def test_run_execute_help(self):
        """测试 run execute 命令帮助。"""
        result = runner.invoke(app, ["run", "execute", "--help"])
        assert result.exit_code == 0
        assert "执行" in result.output or "Worker" in result.output

    def test_run_execute_missing_run(self):
        """测试执行不存在的任务。"""
        result = runner.invoke(app, ["run", "execute", "999"])
        assert result.exit_code == 1
        assert "不存在" in result.output


class TestReportCLI:
    """报告管理命令测试。"""

    def test_report_help_displays_correctly(self):
        """测试报告命令帮助显示正确。"""
        result = runner.invoke(app, ["report", "--help"])
        assert result.exit_code == 0
        assert "export" in result.output

    def test_report_export_help(self):
        """测试 report export 命令帮助。"""
        result = runner.invoke(app, ["report", "export", "--help"])
        assert result.exit_code == 0
        assert "导出" in result.output or "format" in result.output

    def test_report_export_missing_run(self):
        """测试导出不存在的任务报告。"""
        result = runner.invoke(app, ["report", "export", "999"])
        assert result.exit_code == 1
        assert "不存在" in result.output
