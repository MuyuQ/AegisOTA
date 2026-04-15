"""报告生成服务测试。"""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DeviceStatus
from app.models.report import Report, ReportStatus
from app.models.run import RunSession, RunStatus, RunStep, StepName, StepStatus, UpgradePlan
from app.services.report_service import ReportService


@pytest.fixture
def test_db():
    """创建测试数据库。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def test_device(test_db):
    """创建测试设备。"""
    device = Device(
        serial="TEST001",
        brand="TestBrand",
        model="TestModel",
        status=DeviceStatus.IDLE,
    )
    test_db.add(device)
    test_db.commit()
    return device


@pytest.fixture
def test_plan(test_db):
    """创建测试计划。"""
    plan = UpgradePlan(name="Test Plan")
    test_db.add(plan)
    test_db.commit()
    return plan


@pytest.fixture
def test_run(test_db, test_device, test_plan):
    """创建测试任务。"""
    run = RunSession(
        plan_id=test_plan.id,
        device_id=test_device.id,
        status=RunStatus.PASSED,
        started_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        ended_at=datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc),
    )
    test_db.add(run)
    test_db.commit()
    return run


class TestReportService:
    """报告服务测试类。"""

    def test_generate_report_passed(self, test_db, test_run, test_device, test_plan):
        """测试生成成功的报告。"""
        # 添加步骤
        step1 = RunStep(
            run_id=test_run.id,
            step_name=StepName.PRECHECK,
            step_order=1,
            status=StepStatus.SUCCESS,
        )
        step2 = RunStep(
            run_id=test_run.id,
            step_name=StepName.APPLY_UPDATE,
            step_order=2,
            status=StepStatus.SUCCESS,
        )
        test_db.add_all([step1, step2])
        test_db.commit()

        service = ReportService(test_db)
        # 禁用文件保存，因为测试环境可能没有目录权限
        report = service.generate_report(test_run, save_files=False)

        assert report.id is not None
        assert report.run_id == test_run.id
        assert report.status == ReportStatus.COMPLETED
        assert report.total_steps == 2
        assert report.passed_steps == 2
        assert report.failed_steps == 0
        assert report.duration_seconds == 1800.0  # 30 minutes

    def test_generate_report_failed(self, test_db, test_device, test_plan):
        """测试生成失败的报告。"""
        # 创建失败的任务
        run = RunSession(
            plan_id=test_plan.id,
            device_id=test_device.id,
            status=RunStatus.FAILED,
            started_at=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            ended_at=datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc),
        )
        test_db.add(run)
        test_db.commit()

        # 添加步骤
        step1 = RunStep(
            run_id=run.id,
            step_name=StepName.PRECHECK,
            step_order=1,
            status=StepStatus.SUCCESS,
        )
        step2 = RunStep(
            run_id=run.id,
            step_name=StepName.APPLY_UPDATE,
            step_order=2,
            status=StepStatus.FAILED,
        )
        step2.set_result({"error": "boot timeout"})
        test_db.add_all([step1, step2])
        test_db.commit()

        service = ReportService(test_db)
        report = service.generate_report(run, save_files=False)

        assert report.status == ReportStatus.COMPLETED
        assert report.total_steps == 2
        assert report.passed_steps == 1
        assert report.failed_steps == 1
        assert report.failure_category == "boot_failure"

    def test_get_report(self, test_db, test_run):
        """测试获取报告。"""
        # 创建报告
        report = Report(
            run_id=test_run.id,
            title="Test Report",
            status=ReportStatus.COMPLETED,
        )
        test_db.add(report)
        test_db.commit()

        service = ReportService(test_db)
        found = service.get_report(report.id)

        assert found is not None
        assert found.id == report.id
        assert found.title == "Test Report"

    def test_get_report_not_found(self, test_db):
        """测试获取不存在的报告。"""
        service = ReportService(test_db)
        found = service.get_report(99999)

        assert found is None

    def test_get_report_by_run_id(self, test_db, test_run):
        """测试根据任务 ID 获取报告。"""
        report = Report(
            run_id=test_run.id,
            title="Test Report",
            status=ReportStatus.COMPLETED,
        )
        test_db.add(report)
        test_db.commit()

        service = ReportService(test_db)
        found = service.get_report_by_run_id(test_run.id)

        assert found is not None
        assert found.run_id == test_run.id

    def test_list_reports(self, test_db, test_run):
        """测试列出报告。"""
        # 创建多个报告
        for i in range(3):
            report = Report(
                run_id=test_run.id,
                title=f"Report {i}",
                status=ReportStatus.COMPLETED,
            )
            test_db.add(report)
        test_db.commit()

        service = ReportService(test_db)
        reports = service.list_reports()

        assert len(reports) == 3

    def test_list_reports_with_status_filter(self, test_db, test_run):
        """测试按状态过滤报告。"""
        report1 = Report(
            run_id=test_run.id,
            title="Completed",
            status=ReportStatus.COMPLETED,
        )
        report2 = Report(
            run_id=test_run.id,
            title="Generating",
            status=ReportStatus.GENERATING,
        )
        test_db.add_all([report1, report2])
        test_db.commit()

        service = ReportService(test_db)
        completed = service.list_reports(status=ReportStatus.COMPLETED)

        assert len(completed) == 1
        assert completed[0].title == "Completed"

    def test_report_title_generation(self, test_db, test_run, test_device, test_plan):
        """测试报告标题生成。"""
        service = ReportService(test_db)
        report = service.generate_report(test_run, save_files=False)

        assert "Test Plan" in report.title
        assert "TEST001" in report.title
        assert "成功" in report.title

    def test_report_skipped_steps(self, test_db, test_device, test_plan):
        """测试报告跳过步骤统计。"""
        run = RunSession(
            plan_id=test_plan.id,
            device_id=test_device.id,
            status=RunStatus.PASSED,
        )
        test_db.add(run)
        test_db.commit()

        step1 = RunStep(
            run_id=run.id,
            step_name=StepName.PRECHECK,
            step_order=1,
            status=StepStatus.SUCCESS,
        )
        step2 = RunStep(
            run_id=run.id,
            step_name=StepName.APPLY_UPDATE,
            step_order=2,
            status=StepStatus.SKIPPED,
        )
        test_db.add_all([step1, step2])
        test_db.commit()

        service = ReportService(test_db)
        report = service.generate_report(run, save_files=False)

        assert report.total_steps == 2
        assert report.passed_steps == 1
        assert report.skipped_steps == 1

    def test_report_failure_classification(self, test_db, test_device, test_plan):
        """测试失败分类。"""
        run = RunSession(
            plan_id=test_plan.id,
            device_id=test_device.id,
            status=RunStatus.FAILED,
        )
        test_db.add(run)
        test_db.commit()

        step = RunStep(
            run_id=run.id,
            step_name=StepName.PRECHECK,
            step_order=1,
            status=StepStatus.FAILED,
        )
        step.set_result({"error": "battery low"})
        test_db.add(step)
        test_db.commit()

        service = ReportService(test_db)
        report = service.generate_report(run, save_files=False)

        assert report.failure_category == "device_env_issue"
        assert report.recommendation is not None


class TestReportServiceFileOperations:
    """报告服务文件操作测试。"""

    def test_save_report_files(self, test_db, test_run, tmp_path):
        """测试保存报告文件。"""
        service = ReportService(test_db)
        service.settings.ARTIFACTS_DIR = tmp_path

        report = Report(
            run_id=test_run.id,
            status=ReportStatus.GENERATING,
        )
        test_db.add(report)
        test_db.commit()

        report_data = {
            "run_id": test_run.id,
            "plan_name": "Test Plan",
            "device_serial": "TEST001",
            "status": "passed",
            "timeline": [],
        }

        content_path = service._save_report_files(report, report_data)

        assert content_path.exists()
        assert content_path.name == "report.json"

        # 验证文件内容
        with open(content_path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
        assert saved_data["run_id"] == test_run.id

        # 验证其他格式文件
        report_dir = content_path.parent
        assert (report_dir / "report.md").exists()
        assert (report_dir / "report.html").exists()

    def test_load_report_content_json(self, test_db, test_run, tmp_path):
        """测试加载 JSON 报告内容。"""
        service = ReportService(test_db)
        service.settings.ARTIFACTS_DIR = tmp_path

        # 创建报告文件
        report = Report(
            run_id=test_run.id,
            status=ReportStatus.COMPLETED,
        )
        test_db.add(report)
        test_db.commit()

        report_data = {
            "run_id": test_run.id,
            "status": "passed",
            "plan_name": "Test Plan",
            "device_serial": "TEST001",
            "timeline": [],
        }
        content_path = service._save_report_files(report, report_data)
        report.content_path = str(content_path)
        test_db.commit()

        # 加载内容
        loaded = service.load_report_content(report)
        assert loaded is not None
        assert loaded["run_id"] == test_run.id

    def test_load_report_content_not_found(self, test_db, test_run):
        """测试加载不存在的报告内容。"""
        report = Report(
            run_id=test_run.id,
            status=ReportStatus.COMPLETED,
            content_path="/nonexistent/path/report.json",
        )
        test_db.add(report)
        test_db.commit()

        service = ReportService(test_db)
        loaded = service.load_report_content(report)

        assert loaded is None
