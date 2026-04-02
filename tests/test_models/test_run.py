"""任务模型测试。"""

import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.artifact import Artifact
from app.models.device import Device, DeviceLease, DeviceStatus
from app.models.fault import FaultProfile, FaultStage, FaultType
from app.models.run import (
    FailureCategory,
    RunSession,
    RunStatus,
    RunStep,
    StepName,
    StepStatus,
    UpgradePlan,
    UpgradeType,
)


@pytest.fixture
def db_engine():
    """创建测试数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """创建测试数据库会话。"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_device(db_session):
    """创建示例设备。"""
    device = Device(serial="TEST001", brand="Google", model="Pixel 7")
    db_session.add(device)
    db_session.commit()
    return device


@pytest.fixture
def sample_plan(db_session):
    """创建示例升级计划。"""
    plan = UpgradePlan(name="测试升级计划", upgrade_type=UpgradeType.FULL)
    db_session.add(plan)
    db_session.commit()
    return plan


class TestRunStatus:
    """RunStatus 枚举测试。"""

    def test_status_values(self):
        """测试枚举值正确。"""
        assert RunStatus.QUEUED == "queued"
        assert RunStatus.ALLOCATING == "allocating"
        assert RunStatus.RESERVED == "reserved"
        assert RunStatus.RUNNING == "running"
        assert RunStatus.VALIDATING == "validating"
        assert RunStatus.PASSED == "passed"
        assert RunStatus.FAILED == "failed"
        assert RunStatus.ABORTED == "aborted"
        assert RunStatus.PREEMPTED == "preempted"
        assert RunStatus.QUARANTINED == "quarantined"

    def test_status_count(self):
        """测试枚举值数量。"""
        assert len(RunStatus) == 10

    def test_status_is_string_enum(self):
        """测试枚举是字符串枚举。"""
        assert isinstance(RunStatus.QUEUED.value, str)


class TestUpgradeType:
    """UpgradeType 枚举测试。"""

    def test_type_values(self):
        """测试枚举值正确。"""
        assert UpgradeType.FULL == "full"
        assert UpgradeType.INCREMENTAL == "incremental"
        assert UpgradeType.ROLLBACK == "rollback"

    def test_type_count(self):
        """测试枚举值数量。"""
        assert len(UpgradeType) == 3


class TestStepName:
    """StepName 枚举测试。"""

    def test_step_values(self):
        """测试枚举值正确。"""
        assert StepName.PRECHECK == "precheck"
        assert StepName.PACKAGE_PREPARE == "package_prepare"
        assert StepName.APPLY_UPDATE == "apply_update"
        assert StepName.REBOOT_WAIT == "reboot_wait"
        assert StepName.POST_VALIDATE == "post_validate"
        assert StepName.REPORT_FINALIZE == "report_finalize"

    def test_step_count(self):
        """测试枚举值数量。"""
        assert len(StepName) == 6


class TestUpgradePlanCreation:
    """UpgradePlan 创建测试。"""

    def test_create_plan_minimal(self, db_session):
        """测试创建最小升级计划。"""
        plan = UpgradePlan(name="基础计划")
        db_session.add(plan)
        db_session.commit()

        assert plan.id is not None
        assert plan.name == "基础计划"
        assert plan.upgrade_type == UpgradeType.FULL
        assert plan.parallelism == 1
        assert plan.created_at is not None
        assert plan.updated_at is not None

    def test_create_plan_full(self, db_session):
        """测试创建完整升级计划。"""
        plan = UpgradePlan(
            name="完整计划",
            upgrade_type=UpgradeType.INCREMENTAL,
            package_path="/data/ota/update.zip",
            target_build="AP2A.240305.004",
            fault_profile_id=1,
            validation_profile_id=2,
            parallelism=4,
            created_by="admin",
        )
        plan.set_device_selector({"brand": "Google", "model": "Pixel 7"})
        db_session.add(plan)
        db_session.commit()

        assert plan.id is not None
        assert plan.upgrade_type == UpgradeType.INCREMENTAL
        assert plan.parallelism == 4
        assert plan.get_device_selector() == {"brand": "Google", "model": "Pixel 7"}

    def test_plan_device_selector_methods(self, db_session):
        """测试设备选择器方法。"""
        plan = UpgradePlan(name="选择器测试")

        # 测试空选择器
        assert plan.get_device_selector() == {}

        # 测试设置选择器
        selector = {"tags": ["stable"], "android_version": "14"}
        plan.set_device_selector(selector)
        db_session.add(plan)
        db_session.commit()

        assert plan.get_device_selector() == selector

    def test_plan_device_selector_empty(self, db_session):
        """测试空设备选择器。"""
        plan = UpgradePlan(name="空选择器")
        plan.set_device_selector({})
        db_session.add(plan)
        db_session.commit()

        assert plan.device_selector is None
        assert plan.get_device_selector() == {}


class TestRunSessionCreation:
    """RunSession 创建测试。"""

    def test_create_session_minimal(self, db_session, sample_device, sample_plan):
        """测试创建最小运行会话。"""
        session = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(session)
        db_session.commit()

        assert session.id is not None
        assert session.status == RunStatus.QUEUED
        assert session.device_id == sample_device.id
        assert session.plan_id == sample_plan.id

    def test_create_session_full(self, db_session, sample_device, sample_plan):
        """测试创建完整运行会话。"""
        now = datetime.now(timezone.utc)
        session = RunSession(
            device_id=sample_device.id,
            plan_id=sample_plan.id,
            status=RunStatus.RUNNING,
            started_at=now,
            result="执行中",
        )
        db_session.add(session)
        db_session.commit()

        assert session.status == RunStatus.RUNNING
        assert session.started_at is not None

    def test_session_duration(self, db_session, sample_device, sample_plan):
        """测试持续时间计算。"""
        start = datetime.now(timezone.utc)
        end = start + timedelta(minutes=30)

        session = RunSession(
            device_id=sample_device.id,
            plan_id=sample_plan.id,
            status=RunStatus.PASSED,
            started_at=start,
            ended_at=end,
        )
        db_session.add(session)
        db_session.commit()

        duration = session.get_duration_seconds()
        assert duration is not None
        assert abs(duration - 1800.0) < 1.0  # 30分钟 = 1800秒

    def test_session_duration_not_ended(self, db_session, sample_device, sample_plan):
        """测试未结束会话的持续时间。"""
        session = RunSession(
            device_id=sample_device.id,
            plan_id=sample_plan.id,
            status=RunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(session)
        db_session.commit()

        assert session.get_duration_seconds() is None

    def test_session_is_terminal_state(self, db_session, sample_device, sample_plan):
        """测试终态判断。"""
        terminal_states = [RunStatus.PASSED, RunStatus.FAILED, RunStatus.ABORTED, RunStatus.QUARANTINED]
        non_terminal_states = [RunStatus.QUEUED, RunStatus.RESERVED, RunStatus.RUNNING, RunStatus.VALIDATING]

        for status in terminal_states:
            session = RunSession(device_id=sample_device.id, plan_id=sample_plan.id, status=status)
            assert session.is_terminal_state() is True, f"{status} 应该是终态"

        for status in non_terminal_states:
            session = RunSession(device_id=sample_device.id, plan_id=sample_plan.id, status=status)
            assert session.is_terminal_state() is False, f"{status} 不应该是终态"


class TestRunSessionRelationships:
    """RunSession 关系测试。"""

    def test_session_plan_relationship(self, db_session, sample_device, sample_plan):
        """测试会话与计划的关联。"""
        session = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(session)
        db_session.commit()

        db_session.refresh(session)
        assert session.plan is not None
        assert session.plan.name == "测试升级计划"

    def test_session_device_relationship(self, db_session, sample_device, sample_plan):
        """测试会话与设备的关联。"""
        session = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(session)
        db_session.commit()

        db_session.refresh(session)
        assert session.device is not None
        assert session.device.serial == "TEST001"

    def test_session_steps_relationship(self, db_session, sample_device, sample_plan):
        """测试会话与步骤的关联。"""
        session = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(session)
        db_session.commit()

        step1 = RunStep(run_id=session.id, step_name=StepName.PRECHECK, step_order=1)
        step2 = RunStep(run_id=session.id, step_name=StepName.APPLY_UPDATE, step_order=2)
        db_session.add_all([step1, step2])
        db_session.commit()

        db_session.refresh(session)
        assert len(session.steps) == 2


class TestRunStepCreation:
    """RunStep 创建测试。"""

    def test_create_step_minimal(self, db_session, sample_device, sample_plan):
        """测试创建最小步骤。"""
        run = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(run)
        db_session.commit()

        step = RunStep(run_id=run.id, step_name=StepName.PRECHECK, step_order=1)
        db_session.add(step)
        db_session.commit()

        assert step.id is not None
        assert step.step_name == StepName.PRECHECK
        assert step.status == StepStatus.PENDING
        assert step.step_order == 1

    def test_create_step_full(self, db_session, sample_device, sample_plan):
        """测试创建完整步骤。"""
        run = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(run)
        db_session.commit()

        step = RunStep(
            run_id=run.id,
            step_name=StepName.APPLY_UPDATE,
            step_order=2,
            status=StepStatus.RUNNING,
            command="adb sideload update.zip",
            stdout_path="/logs/run_1_step_2_stdout.log",
            stderr_path="/logs/run_1_step_2_stderr.log",
        )
        step.set_result({"progress": 50, "total": 100})
        db_session.add(step)
        db_session.commit()

        assert step.status == StepStatus.RUNNING
        assert step.command == "adb sideload update.zip"
        assert step.get_result() == {"progress": 50, "total": 100}

    def test_step_result_methods(self, db_session, sample_device, sample_plan):
        """测试步骤结果方法。"""
        run = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(run)
        db_session.commit()

        step = RunStep(run_id=run.id, step_name=StepName.POST_VALIDATE, step_order=3)
        db_session.add(step)
        db_session.commit()

        # 测试空结果
        assert step.get_result() == {}

        # 测试设置结果
        result = {
            "checks": ["boot_complete", "network_available"],
            "passed": True,
            "failures": [],
        }
        step.set_result(result)
        db_session.commit()

        assert step.get_result() == result

    def test_step_duration(self, db_session, sample_device, sample_plan):
        """测试步骤持续时间计算。"""
        run = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(run)
        db_session.commit()

        start = datetime.now(timezone.utc)
        end = start + timedelta(seconds=45)

        step = RunStep(
            run_id=run.id,
            step_name=StepName.REBOOT_WAIT,
            step_order=4,
            started_at=start,
            ended_at=end,
        )
        db_session.add(step)
        db_session.commit()

        duration = step.get_duration_seconds()
        assert duration is not None
        assert abs(duration - 45.0) < 1.0


class TestArtifactCreation:
    """Artifact 创建测试。"""

    def test_create_artifact(self, db_session, sample_device, sample_plan):
        """测试创建产物。"""
        run = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(run)
        db_session.commit()

        artifact = Artifact(
            run_id=run.id,
            artifact_type="log",
            file_path="/artifacts/run_1/dmesg.log",
            file_size=1024,
            mime_type="text/plain",
            description="内核日志",
        )
        db_session.add(artifact)
        db_session.commit()

        assert artifact.id is not None
        assert artifact.artifact_type == "log"
        assert artifact.file_path == "/artifacts/run_1/dmesg.log"
        assert artifact.file_size == 1024

    def test_artifact_run_relationship(self, db_session, sample_device, sample_plan):
        """测试产物与会话的关联。"""
        run = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(run)
        db_session.commit()

        artifact = Artifact(
            run_id=run.id,
            artifact_type="screenshot",
            file_path="/artifacts/run_1/screenshot.png",
        )
        db_session.add(artifact)
        db_session.commit()

        db_session.refresh(artifact)
        assert artifact.run_session is not None
        assert artifact.run_session.id == run.id


class TestFailureCategory:
    """FailureCategory 枚举测试。"""

    def test_category_values(self):
        """测试枚举值正确。"""
        assert FailureCategory.PACKAGE_ISSUE == "package_issue"
        assert FailureCategory.DEVICE_ENV_ISSUE == "device_env_issue"
        assert FailureCategory.BOOT_FAILURE == "boot_failure"
        assert FailureCategory.VALIDATION_FAILURE == "validation_failure"
        assert FailureCategory.MONKEY_INSTABILITY == "monkey_instability"
        assert FailureCategory.PERFORMANCE_SUSPECT == "performance_suspect"
        assert FailureCategory.ADB_TRANSPORT_ISSUE == "adb_transport_issue"
        assert FailureCategory.UNKNOWN == "unknown"

    def test_category_count(self):
        """测试枚举值数量。"""
        assert len(FailureCategory) == 8


class TestRunSessionFailure:
    """RunSession 失败分类测试。"""

    def test_session_with_failure(self, db_session, sample_device, sample_plan):
        """测试失败会话。"""
        session = RunSession(
            device_id=sample_device.id,
            plan_id=sample_plan.id,
            status=RunStatus.FAILED,
            failure_category=FailureCategory.BOOT_FAILURE,
            summary="设备启动超时",
        )
        db_session.add(session)
        db_session.commit()

        assert session.status == RunStatus.FAILED
        assert session.failure_category == FailureCategory.BOOT_FAILURE
        assert session.summary == "设备启动超时"

    def test_session_quarantined(self, db_session, sample_device, sample_plan):
        """测试隔离会话。"""
        session = RunSession(
            device_id=sample_device.id,
            plan_id=sample_plan.id,
            status=RunStatus.QUARANTINED,
            failure_category=FailureCategory.DEVICE_ENV_ISSUE,
            summary="设备环境异常，已隔离",
        )
        db_session.add(session)
        db_session.commit()

        assert session.status == RunStatus.QUARANTINED
        assert session.is_terminal_state() is True


class TestDeviceLeaseWithRunSession:
    """DeviceLease 与 RunSession 关联测试。"""

    def test_lease_run_relationship(self, db_session, sample_device, sample_plan):
        """测试租约与会话的关联。"""
        # 创建会话
        run = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(run)
        db_session.commit()

        # 创建租约关联到会话
        lease = DeviceLease(device_id=sample_device.id, run_id=run.id)
        db_session.add(lease)
        db_session.commit()

        # 验证关系
        db_session.refresh(lease)
        assert lease.run_session is not None
        assert lease.run_session.id == run.id

        db_session.refresh(run)
        assert run.lease is not None
        assert run.lease.id == lease.id


class TestCascadeDelete:
    """级联删除测试。"""

    def test_plan_delete_cascades_sessions(self, db_session, sample_device):
        """测试删除计划级联删除会话。"""
        plan = UpgradePlan(name="待删除计划")
        db_session.add(plan)
        db_session.commit()

        session = RunSession(device_id=sample_device.id, plan_id=plan.id)
        db_session.add(session)
        db_session.commit()

        session_id = session.id
        plan_id = plan.id

        # 删除计划
        db_session.delete(plan)
        db_session.commit()

        # 会话应该被级联删除
        from sqlalchemy.orm import object_session
        assert object_session(session) is None

    def test_run_delete_cascades_steps(self, db_session, sample_device, sample_plan):
        """测试删除会话级联删除步骤。"""
        run = RunSession(device_id=sample_device.id, plan_id=sample_plan.id)
        db_session.add(run)
        db_session.commit()

        step = RunStep(run_id=run.id, step_name=StepName.PRECHECK, step_order=1)
        db_session.add(step)
        db_session.commit()

        step_id = step.id
        run_id = run.id

        # 删除会话
        db_session.delete(run)
        db_session.commit()

        # 步骤应该被级联删除
        from sqlalchemy.orm import object_session
        assert object_session(step) is None