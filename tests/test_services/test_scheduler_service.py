"""调度服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DeviceStatus
from app.models.run import RunSession, RunStatus, UpgradePlan, UpgradeType
from app.services.scheduler_service import SchedulerService


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

    # 设备状态应该变为 reserved
    test_db.refresh(device)
    assert device.status == DeviceStatus.RESERVED


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


class TestPriorityScheduling:
    """优先级调度测试。"""

    def test_schedule_highest_priority_first(self, test_db):
        """测试高优先级任务优先调度。"""
        from app.models.device import DevicePool
        from app.models.enums import DeviceStatus, PoolPurpose, RunPriority

        pool = DevicePool(name="priority_pool", purpose=PoolPurpose.STABLE)
        test_db.add(pool)
        test_db.commit()

        device = Device(
            serial="PRIO001", status=DeviceStatus.IDLE, pool_id=pool.id, battery_level=80
        )
        test_db.add(device)

        plan = UpgradePlan(name="Priority Test Plan")
        test_db.add(plan)
        test_db.commit()

        run_normal = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
        run_high = RunSession(plan_id=plan.id, priority=RunPriority.HIGH, pool_id=pool.id)
        run_emergency = RunSession(plan_id=plan.id, priority=RunPriority.EMERGENCY, pool_id=pool.id)
        test_db.add_all([run_normal, run_high, run_emergency])
        test_db.commit()

        scheduler = SchedulerService(test_db)
        next_run = scheduler.get_next_run_to_schedule(pool_id=pool.id)

        assert next_run is not None
        assert next_run.priority == RunPriority.EMERGENCY

    def test_schedule_fifo_same_priority(self, test_db):
        """测试相同优先级按 FIFO 调度。"""
        from app.models.device import DevicePool
        from app.models.enums import DeviceStatus, PoolPurpose, RunPriority

        pool = DevicePool(name="fifo_pool", purpose=PoolPurpose.STABLE)
        test_db.add(pool)
        test_db.commit()

        device = Device(
            serial="FIFO001", status=DeviceStatus.IDLE, pool_id=pool.id, battery_level=80
        )
        test_db.add(device)

        plan = UpgradePlan(name="FIFO Test Plan")
        test_db.add(plan)
        test_db.commit()

        run1 = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
        run2 = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
        run3 = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
        test_db.add_all([run1, run2, run3])
        test_db.commit()

        scheduler = SchedulerService(test_db)
        next_run = scheduler.get_next_run_to_schedule(pool_id=pool.id)

        assert next_run.id == run1.id

    def test_allocate_from_pool(self, test_db):
        """测试从设备池分配设备。"""
        from app.models.device import DevicePool
        from app.models.enums import DeviceStatus, PoolPurpose, RunPriority

        pool = DevicePool(name="alloc_pool", purpose=PoolPurpose.STABLE, max_parallel=5)
        test_db.add(pool)
        test_db.commit()

        for i in range(3):
            device = Device(
                serial=f"ALLOC{i:03d}", status=DeviceStatus.IDLE, pool_id=pool.id, battery_level=80
            )
            test_db.add(device)
        test_db.commit()

        plan = UpgradePlan(name="Alloc Test Plan")
        test_db.add(plan)
        test_db.commit()

        run = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
        test_db.add(run)
        test_db.commit()

        scheduler = SchedulerService(test_db)
        allocated = scheduler.allocate_device_for_run(run.id)

        assert allocated is not None
        assert allocated.pool_id == pool.id

        test_db.refresh(run)
        assert run.status == RunStatus.RUNNING
        assert run.device_id == allocated.id

    def test_allocate_respects_reserved_capacity(self, test_db):
        """测试分配设备时保留容量。"""
        from app.models.device import DevicePool
        from app.models.enums import DeviceStatus, PoolPurpose, RunPriority

        pool = DevicePool(
            name="reserved_pool",
            purpose=PoolPurpose.EMERGENCY,
            reserved_ratio=0.5,
            max_parallel=4,
        )
        test_db.add(pool)
        test_db.commit()

        for i in range(4):
            device = Device(
                serial=f"RES{i:03d}", status=DeviceStatus.IDLE, pool_id=pool.id, battery_level=80
            )
            test_db.add(device)
        test_db.commit()

        plan = UpgradePlan(name="Reserved Test Plan")
        test_db.add(plan)
        test_db.commit()

        scheduler = SchedulerService(test_db)

        runs = []
        for i in range(3):
            run = RunSession(plan_id=plan.id, priority=RunPriority.NORMAL, pool_id=pool.id)
            test_db.add(run)
            runs.append(run)
        test_db.commit()

        allocated1 = scheduler.allocate_device_for_run(runs[0].id)
        allocated2 = scheduler.allocate_device_for_run(runs[1].id)

        assert allocated1 is not None
        assert allocated2 is not None

        allocated3 = scheduler.allocate_device_for_run(runs[2].id)
        assert allocated3 is None


class TestPoolBasedAllocation:
    """基于池的设备分配测试。"""

    def test_select_device_from_pool(self, test_db):
        """测试从指定池选择设备。"""
        from app.models.device import DevicePool
        from app.models.enums import DeviceStatus, PoolPurpose

        pool = DevicePool(name="select_pool", purpose=PoolPurpose.STABLE)
        test_db.add(pool)
        test_db.commit()

        device = Device(
            serial="SELECT001", status=DeviceStatus.IDLE, pool_id=pool.id, battery_level=80
        )
        test_db.add(device)
        test_db.commit()

        plan = UpgradePlan(name="Select Test Plan", default_pool_id=pool.id)
        test_db.add(plan)
        test_db.commit()

        run = RunSession(plan_id=plan.id, pool_id=pool.id)
        test_db.add(run)
        test_db.commit()

        scheduler = SchedulerService(test_db)
        selected = scheduler.select_device_for_run(run.id, pool_id=pool.id)

        assert selected is not None
        assert selected.pool_id == pool.id
        assert selected.serial == "SELECT001"

    def test_select_device_respects_pool_boundary(self, test_db):
        """测试设备选择遵守池边界。"""
        from app.models.device import DevicePool
        from app.models.enums import DeviceStatus, PoolPurpose

        pool1 = DevicePool(name="boundary1", purpose=PoolPurpose.STABLE)
        pool2 = DevicePool(name="boundary2", purpose=PoolPurpose.STRESS)
        test_db.add_all([pool1, pool2])
        test_db.commit()

        device1 = Device(
            serial="BOUNDARY001", status=DeviceStatus.BUSY, pool_id=pool1.id, battery_level=80
        )
        device2 = Device(
            serial="BOUNDARY002", status=DeviceStatus.IDLE, pool_id=pool2.id, battery_level=80
        )
        test_db.add_all([device1, device2])
        test_db.commit()

        plan = UpgradePlan(name="Boundary Test Plan", default_pool_id=pool1.id)
        test_db.add(plan)
        test_db.commit()

        run = RunSession(plan_id=plan.id, pool_id=pool1.id)
        test_db.add(run)
        test_db.commit()

        scheduler = SchedulerService(test_db)
        selected = scheduler.select_device_for_run(run.id, pool_id=pool1.id)
        assert selected is None

        run2 = RunSession(plan_id=plan.id, pool_id=pool2.id)
        test_db.add(run2)
        test_db.commit()

        selected2 = scheduler.select_device_for_run(run2.id, pool_id=pool2.id)
        assert selected2 is not None
        assert selected2.pool_id == pool2.id
