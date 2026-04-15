"""报告生成器测试。"""

from pathlib import Path

from app.reporting.failure_classifier import FailureCategory
from app.reporting.generator import ReportData, ReportGenerator


def test_report_generator_init():
    """测试报告生成器初始化。"""
    generator = ReportGenerator()
    assert generator is not None


def test_generate_summary():
    """测试生成摘要。"""
    generator = ReportGenerator()

    summary = generator.generate(
        run_id=1,
        plan_name="测试升级计划",
        device_serial="ABC123",
        status="passed",
        timeline=[],
        step_results={},
    )

    assert "run_id" in summary
    assert summary["status"] == "passed"


def test_generate_failure_report():
    """测试生成失败报告。"""
    generator = ReportGenerator()

    report = generator.generate(
        run_id=1,
        plan_name="测试升级计划",
        device_serial="ABC123",
        status="failed",
        failed_step="reboot_wait",
        failure_category=FailureCategory.BOOT_FAILURE,
        timeline=[],
        step_results={},
    )

    assert report["status"] == "failed"
    assert report["failure_category"] == "boot_failure"


def test_generate_markdown():
    """测试生成 Markdown 格式。"""
    generator = ReportGenerator()

    md_content = generator.generate_markdown(
        run_id=1,
        plan_name="测试计划",
        device_serial="ABC123",
        status="passed",
        timeline=[],
    )

    assert "# OTA升级报告" in md_content or "报告" in md_content
    assert "Run ID" in md_content or "run_id" in md_content.lower()


def test_generate_html():
    """测试生成 HTML 格式。"""
    generator = ReportGenerator()

    html_content = generator.generate_html(
        run_id=1,
        plan_name="测试计划",
        device_serial="ABC123",
        status="passed",
        timeline=[],
    )

    assert "<!DOCTYPE html>" in html_content or "<html" in html_content.lower()


def test_generate_html_with_timeline():
    """测试生成带时间线的 HTML。"""
    generator = ReportGenerator()

    timeline = [
        {"timestamp": "2024-01-01T10:00:00", "message": "开始升级"},
        {"timestamp": "2024-01-01T10:05:00", "message": "推送包完成"},
        {"timestamp": "2024-01-01T10:10:00", "message": "升级完成"},
    ]

    html_content = generator.generate_html(
        run_id=1,
        plan_name="测试计划",
        device_serial="ABC123",
        status="passed",
        timeline=timeline,
    )

    assert "开始升级" in html_content
    assert "推送包完成" in html_content


def test_generate_markdown_with_timeline():
    """测试生成带时间线的 Markdown。"""
    generator = ReportGenerator()

    timeline = [
        {"timestamp": "2024-01-01T10:00:00", "message": "开始升级"},
        {"timestamp": "2024-01-01T10:05:00", "message": "推送包完成"},
    ]

    md_content = generator.generate_markdown(
        run_id=1,
        plan_name="测试计划",
        device_serial="ABC123",
        status="passed",
        timeline=timeline,
    )

    assert "开始升级" in md_content
    assert "2024-01-01T10:00:00" in md_content


def test_save_report():
    """测试保存报告。"""
    import tempfile

    generator = ReportGenerator()

    report_data = generator.generate(
        run_id=1,
        plan_name="测试计划",
        device_serial="ABC123",
        status="passed",
        timeline=[],
        step_results={},
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        json_path = generator.save_report(report_data, output_dir)

        assert json_path.exists()
        assert (output_dir / "report.md").exists()
        assert (output_dir / "report.html").exists()

        # 检查 JSON 文件内容
        import json

        with open(json_path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data["run_id"] == 1
        assert saved_data["status"] == "passed"


def test_report_data_creation():
    """测试报告数据结构。"""
    report = ReportData(
        run_id=1,
        plan_name="测试计划",
        device_serial="ABC123",
        status="passed",
    )

    assert report.run_id == 1
    assert report.status == "passed"
    assert report.timeline == []  # 使用 default_factory
    assert report.step_results == {}  # 使用 default_factory


def test_calculate_duration():
    """测试计算时长。"""
    from datetime import datetime

    generator = ReportGenerator()

    started_at = datetime(2024, 1, 1, 10, 0, 0)
    ended_at = datetime(2024, 1, 1, 10, 5, 0)

    report = generator.generate(
        run_id=1,
        plan_name="测试计划",
        device_serial="ABC123",
        status="passed",
        started_at=started_at,
        ended_at=ended_at,
    )

    assert report["duration_seconds"] == 300.0


def test_generate_summary_text():
    """测试生成摘要文本。"""
    generator = ReportGenerator()

    # 成功摘要
    success_summary = generator._generate_summary("passed", None, None)
    assert "成功" in success_summary

    # 失败摘要
    failure_summary = generator._generate_summary(
        "failed",
        "reboot_wait",
        FailureCategory.BOOT_FAILURE,
    )
    assert "失败" in failure_summary
    assert "reboot_wait" in failure_summary
    assert "boot_failure" in failure_summary

    # 中止摘要
    aborted_summary = generator._generate_summary("aborted", None, None)
    assert "终止" in aborted_summary
