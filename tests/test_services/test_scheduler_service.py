"""调度服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DeviceLease, DeviceStatus
from app.models.run import UpgradePlan, RunSession, RunStatus, UpgradeType
from app.services.scheduler_service import SchedulerService
from app.services.device_service import DeviceService
from app.services.run_service import RunService
from app.executors.mock_executor import MockExecutor


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
def scheduler(test_db):
    """创建调度服务。"""
    return SchedulerService(test_db)


@pytest.fixture
def setup_data(test_db):
    """设置测试数据。"""
    # 创建设备
    devices = [
        Device(serial="DEV001", status=DeviceStatus.IDLE, battery_level=80),
        Device(serial="DEV002", status=DeviceStatus.IDLE, battery_level=75),
        Device(serial="DEV003", status=DeviceStatus.BUSY, battery_level=90),
    ]
    for d in devices:
        test_db.add(d)

    # 创建计划
    plan = UpgradePlan(
        name="测试计划",
        upgrade_type=UpgradeType.FULL,
        package_path="/tmp/update.zip",
    )
    test_db.add(plan)
    test_db.commit()

    return {"devices": devices, "plan": plan}


def test_acquire_device_lease(scheduler, test_db, setup_data):
    """测试获取设备租约。"""
    device = setup_data["devices"][0]
    plan = setup_data["plan"]

    run = RunSession(plan_id=plan.id, device_id=device.id, status=RunStatus.QUEUED)
    test_db.add(run)
    test_db.commit()

    lease = scheduler.acquire_device_lease(device.id, run.id)

    assert lease is not None
    assert lease.lease_status == "active"

    # 设备状态应该变为 busy
    test_db.refresh(device)
    assert device.status == DeviceStatus.BUSY


def test_acquire_lease_for_busy_device(scheduler, test_db, setup_data):
    """测试无法获取忙碌设备的租约。"""
    device = setup_data["devices"][2]  # BUSY 设备
    plan = setup_data["plan"]

    run = RunSession(plan_id=plan.id, device_id=device.id, status=RunStatus.QUEUED)
    test_db.add(run)
    test_db.commit()

    lease = scheduler.acquire_device_lease(device.id, run.id)

    assert lease is None


def test_release_device_lease(scheduler, test_db, setup_data):
    """测试释放设备租约。"""
    device = setup_data["devices"][0]
    plan = setup_data["plan"]

    run = RunSession(plan_id=plan.id, device_id=device.id, status=RunStatus.RUNNING)
    test_db.add(run)
    test_db.commit()

    # 先获取租约
    lease = scheduler.acquire_device_lease(device.id, run.id)

    # 释放租约
    scheduler.release_device_lease(device.id, run.id)

    test_db.refresh(lease)
    assert lease.lease_status == "released"

    test_db.refresh(device)
    assert device.status == DeviceStatus.IDLE


def test_select_device_for_run(scheduler, test_db, setup_data):
    """测试为任务选择设备。"""
    plan = setup_data["plan"]

    run = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
    test_db.add(run)
    test_db.commit()

    device = scheduler.select_device_for_run(run.id)

    assert device is not None
    assert device.status == DeviceStatus.IDLE


def test_select_device_with_selector(scheduler, test_db, setup_data):
    """测试使用选择器选择设备。"""
    plan = setup_data["plan"]
    plan.set_device_selector({"serial": "DEV002"})
    test_db.commit()

    run = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
    test_db.add(run)
    test_db.commit()

    device = scheduler.select_device_for_run(run.id)

    assert device.serial == "DEV002"


def test_reserve_run(scheduler, test_db, setup_data):
    """测试预留任务。"""
    plan = setup_data["plan"]

    run = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
    test_db.add(run)
    test_db.commit()

    success = scheduler.reserve_run(run.id)

    assert success is True
    test_db.refresh(run)
    assert run.status == RunStatus.RESERVED


def test_get_next_run_to_execute(scheduler, test_db, setup_data):
    """测试获取下一个待执行任务。"""
    plan = setup_data["plan"]

    # 创建多个任务
    run1 = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
    run2 = RunSession(plan_id=plan.id, status=RunStatus.QUEUED)
    test_db.add_all([run1, run2])
    test_db.commit()

    # 预留第一个
    scheduler.reserve_run(run1.id)

    next_run = scheduler.get_next_run_to_execute()
    assert next_run.id == run1.id