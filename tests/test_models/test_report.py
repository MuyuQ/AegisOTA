"""Report 模型测试。"""

from app.models.report import Report, ReportFormat, ReportStatus
from app.models.run import RunSession, RunStatus


class TestReportModel:
    """Report 模型测试类。"""

    def test_report_creation(self, test_session):
        """测试报告基本创建。"""
        # 先创建 RunSession
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        report = Report(
            run_id=run.id,
            title="Test Report",
            format=ReportFormat.JSON,
        )
        test_session.add(report)
        test_session.commit()

        assert report.id is not None
        assert report.run_id == run.id
        assert report.title == "Test Report"
        assert report.format == ReportFormat.JSON
        assert report.status == ReportStatus.GENERATING

    def test_report_default_values(self, test_session):
        """测试报告默认值。"""
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        report = Report(run_id=run.id)
        test_session.add(report)
        test_session.commit()

        assert report.format == ReportFormat.JSON
        assert report.status == ReportStatus.GENERATING
        assert report.total_steps == 0
        assert report.passed_steps == 0
        assert report.failed_steps == 0
        assert report.skipped_steps == 0

    def test_report_format_enum(self):
        """测试报告格式枚举值。"""
        assert ReportFormat.JSON == "json"
        assert ReportFormat.HTML == "html"
        assert ReportFormat.MARKDOWN == "markdown"

    def test_report_status_enum(self):
        """测试报告状态枚举值。"""
        assert ReportStatus.GENERATING == "generating"
        assert ReportStatus.COMPLETED == "completed"
        assert ReportStatus.FAILED == "failed"

    def test_report_is_complete(self, test_session):
        """测试报告完成状态检查。"""
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        report = Report(run_id=run.id, status=ReportStatus.GENERATING)
        test_session.add(report)
        test_session.commit()

        assert not report.is_complete()

        report.status = ReportStatus.COMPLETED
        test_session.commit()

        assert report.is_complete()

    def test_report_success_rate(self, test_session):
        """测试步骤成功率计算。"""
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        report = Report(
            run_id=run.id,
            total_steps=10,
            passed_steps=8,
            failed_steps=2,
        )
        test_session.add(report)
        test_session.commit()

        assert report.get_success_rate() == 80.0

    def test_report_success_rate_zero_steps(self, test_session):
        """测试零步骤时的成功率。"""
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        report = Report(run_id=run.id, total_steps=0)
        test_session.add(report)
        test_session.commit()

        assert report.get_success_rate() == 0.0

    def test_report_failure_analysis_fields(self, test_session):
        """测试失败分析字段。"""
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        report = Report(
            run_id=run.id,
            failure_category="boot_failure",
            failure_summary="设备启动失败",
            root_cause="内核崩溃",
            recommendation="检查内核日志",
        )
        test_session.add(report)
        test_session.commit()

        assert report.failure_category == "boot_failure"
        assert report.failure_summary == "设备启动失败"
        assert report.root_cause == "内核崩溃"
        assert report.recommendation == "检查内核日志"

    def test_report_duration_field(self, test_session):
        """测试执行时间字段。"""
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        report = Report(
            run_id=run.id,
            duration_seconds=120.5,
        )
        test_session.add(report)
        test_session.commit()

        assert report.duration_seconds == 120.5

    def test_report_run_relationship(self, test_session):
        """测试报告与任务的关系。"""
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        report = Report(run_id=run.id)
        test_session.add(report)
        test_session.commit()

        # 刷新以加载关系
        test_session.refresh(report)
        test_session.refresh(run)

        assert report.run_session.id == run.id
        assert len(run.reports) == 1
        assert run.reports[0].id == report.id

    def test_report_cascade_delete(self, test_session):
        """测试任务删除时报告级联删除。"""
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        report = Report(run_id=run.id)
        test_session.add(report)
        test_session.commit()

        report_id = report.id

        # 删除任务
        test_session.delete(run)
        test_session.commit()

        # 验证报告也被删除
        deleted_report = test_session.query(Report).filter_by(id=report_id).first()
        assert deleted_report is None

    def test_report_timestamps(self, test_session):
        """测试报告时间戳。"""
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        report = Report(run_id=run.id)
        test_session.add(report)
        test_session.commit()

        assert report.generated_at is not None
        assert report.updated_at is not None

    def test_report_content_path(self, test_session):
        """测试报告内容路径。"""
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        report = Report(
            run_id=run.id,
            content_path="/reports/run_1/report.json",
        )
        test_session.add(report)
        test_session.commit()

        assert report.content_path == "/reports/run_1/report.json"

    def test_report_multiple_formats(self, test_session):
        """测试多种报告格式。"""
        run = RunSession(status=RunStatus.QUEUED)
        test_session.add(run)
        test_session.commit()

        formats = [ReportFormat.JSON, ReportFormat.HTML, ReportFormat.MARKDOWN]

        for fmt in formats:
            report = Report(run_id=run.id, format=fmt)
            test_session.add(report)

        test_session.commit()

        reports = test_session.query(Report).filter_by(run_id=run.id).all()
        assert len(reports) == 3

        report_formats = [r.format for r in reports]
        assert ReportFormat.JSON in report_formats
        assert ReportFormat.HTML in report_formats
        assert ReportFormat.MARKDOWN in report_formats
