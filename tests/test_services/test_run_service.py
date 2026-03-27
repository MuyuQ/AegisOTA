"""任务管理服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DeviceStatus
from app.models.run import UpgradePlan, RunSession, RunStatus, UpgradeType
from app.models.fault import FaultProfile, FaultType, FaultStage
from app.services.run_service import RunService


@pytest.fixture
def test_db():
    """创建测试数据库。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_plan(test_db):
    """创建示例升级计划。"""
    plan = UpgradePlan(
        name="测试升级计划",
        upgrade_type=UpgradeType.FULL,
        package_path="/tmp/update.zip",
        target_build="TARGET.001",
        parallelism=2,
    )
    test_db.add(plan)
    test_db.commit()
    return plan


@pytest.fixture
def sample_device(test_db):
    """创建示例设备。"""
    device = Device(
        serial="TEST001",
        brand="Test",
        model="TestModel",
        status=DeviceStatus.IDLE,
        battery_level=80,
    )
    device.set_tags(["主力机型"])
    test_db.add(device)
    test_db.commit()
    return device


@pytest.fixture
def run_service(test_db):
    """创建任务服务。"""
    return RunService(test_db)


def test_create_run_session(run_service, sample_plan, sample_device):
    """测试创建任务会话。"""
    session = run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    assert session is not None
    assert session.status == RunStatus.QUEUED
    assert session.plan_id == sample_plan.id
    assert session.device_id == sample_device.id


def test_get_run_session(run_service, test_db, sample_plan, sample_device):
    """测试获取任务会话。"""
    session = run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    retrieved = run_service.get_run_session(session.id)
    assert retrieved.id == session.id


def test_update_run_status(run_service, test_db, sample_plan, sample_device):
    """测试更新任务状态。"""
    session = run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    run_service.update_run_status(session.id, RunStatus.RUNNING)

    updated = test_db.query(RunSession).filter_by(id=session.id).first()
    assert updated.status == RunStatus.RUNNING
    assert updated.started_at is not None


def test_complete_run_session(run_service, test_db, sample_plan, sample_device):
    """测试完成任务。"""
    session = run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    run_service.complete_run_session(
        session.id,
        result="success",
        summary="升级成功完成",
    )

    completed = test_db.query(RunSession).filter_by(id=session.id).first()
    assert completed.status == RunStatus.PASSED
    assert completed.result == "success"
    assert completed.ended_at is not None


def test_abort_run_session(run_service, test_db, sample_plan, sample_device):
    """测试终止任务。"""
    session = run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    run_service.abort_run_session(session.id, "User requested abort")

    aborted = test_db.query(RunSession).filter_by(id=session.id).first()
    assert aborted.status == RunStatus.ABORTED


def test_list_pending_runs(run_service, test_db, sample_plan, sample_device):
    """测试列出待执行任务。"""
    # 创建多个任务
    run_service.create_run_session(plan_id=sample_plan.id, device_id=sample_device.id)
    run_service.create_run_session(plan_id=sample_plan.id, device_id=sample_device.id)

    pending = run_service.list_pending_runs()
    assert len(pending) == 2


def test_create_upgrade_plan(run_service, test_db):
    """测试创建升级计划。"""
    plan = run_service.create_upgrade_plan(
        name="新升级计划",
        upgrade_type=UpgradeType.INCREMENTAL,
        package_path="/tmp/patch.zip",
        device_selector={"brand": "Google"},
    )

    assert plan is not None
    assert plan.name == "新升级计划"
    assert plan.upgrade_type == UpgradeType.INCREMENTAL


def test_list_runs(run_service, test_db, sample_plan, sample_device):
    """测试列出任务。"""
    run_service.create_run_session(
        plan_id=sample_plan.id,
        device_id=sample_device.id,
    )

    runs = run_service.list_runs()
    assert len(runs) >= 1