"""抢占服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DeviceLease, DevicePool, DeviceStatus, LeaseStatus
from app.models.enums import PoolPurpose, RunPriority
from app.models.run import RunSession, RunStatus, UpgradePlan, UpgradeType
from app.services.preemption_service import PreemptionService


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
def preemption_service(test_db):
    """创建抢占服务。"""
    return PreemptionService(test_db)


@pytest.fixture
def setup_pool_and_devices(test_db):
    """创建设备池和设备。"""
    pool = DevicePool(name="test_pool", purpose=PoolPurpose.STABLE)
    test_db.add(pool)

    devices = [
        Device(serial="DEV001", status=DeviceStatus.IDLE, battery_level=80, pool_id=pool.id),
        Device(serial="DEV002", status=DeviceStatus.IDLE, battery_level=75, pool_id=pool.id),
        Device(serial="DEV003", status=DeviceStatus.IDLE, battery_level=90, pool_id=pool.id),
    ]
    for d in devices:
        test_db.add(d)

    test_db.commit()
    return {"pool": pool, "devices": devices}


@pytest.fixture
def setup_plan(test_db):
    """创建升级计划。"""
    plan = UpgradePlan(
        name="测试计划",
        upgrade_type=UpgradeType.FULL,
        package_path="/tmp/update.zip",
    )
    test_db.add(plan)
    test_db.commit()
    return plan


def test_find_preemptible_runs(preemption_service, test_db, setup_pool_and_devices, setup_plan):
    """测试查找可被抢占的任务。"""
    pool = setup_pool_and_devices["pool"]
    plan = setup_plan

    # 创建两个可抢占的 NORMAL 优先级任务
    run1 = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.NORMAL,
        preemptible=True,
        status=RunStatus.RUNNING,
    )
    run2 = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.NORMAL,
        preemptible=True,
        status=RunStatus.RESERVED,
    )
    test_db.add_all([run1, run2])

    # 创建活跃租约
    lease1 = DeviceLease(
        device_id=setup_pool_and_devices["devices"][0].id,
        run_id=run1.id,
        lease_status=LeaseStatus.ACTIVE,
        preemptible=True,
    )
    lease2 = DeviceLease(
        device_id=setup_pool_and_devices["devices"][1].id,
        run_id=run2.id,
        lease_status=LeaseStatus.ACTIVE,
        preemptible=True,
    )
    test_db.add_all([lease1, lease2])
    test_db.commit()

    # 查找可抢占任务
    preemptible_runs = preemption_service.find_preemptible_runs(pool.id)

    assert len(preemptible_runs) == 2
    run_ids = [r.id for r in preemptible_runs]
    assert run1.id in run_ids
    assert run2.id in run_ids


def test_find_preemptible_runs_excludes_non_preemptible(
    preemption_service, test_db, setup_pool_and_devices, setup_plan
):
    """测试不可抢占的任务不会被返回。"""
    pool = setup_pool_and_devices["pool"]
    plan = setup_plan

    # 创建可抢占任务
    run1 = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.NORMAL,
        preemptible=True,
        status=RunStatus.RUNNING,
    )
    # 创建不可抢占任务
    run2 = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.NORMAL,
        preemptible=False,
        status=RunStatus.RUNNING,
    )
    # 创建已完成任务（终态）
    run3 = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.NORMAL,
        preemptible=True,
        status=RunStatus.PASSED,
    )
    test_db.add_all([run1, run2, run3])
    test_db.commit()

    # 查找可抢占任务
    preemptible_runs = preemption_service.find_preemptible_runs(pool.id)

    # 只应该返回 run1
    assert len(preemptible_runs) == 1
    assert preemptible_runs[0].id == run1.id


def test_preempt_run_success(preemption_service, test_db, setup_pool_and_devices, setup_plan):
    """测试成功抢占任务。"""
    pool = setup_pool_and_devices["pool"]
    plan = setup_plan
    device = setup_pool_and_devices["devices"][0]

    # 创建受害者任务（NORMAL 优先级）
    victim_run = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.NORMAL,
        preemptible=True,
        status=RunStatus.RUNNING,
        device_id=device.id,
    )
    test_db.add(victim_run)
    test_db.commit()

    # 创建活跃租约
    lease = DeviceLease(
        device_id=device.id,
        run_id=victim_run.id,
        lease_status=LeaseStatus.ACTIVE,
        preemptible=True,
    )
    test_db.add(lease)
    test_db.commit()

    # 创建抢占者任务（EMERGENCY 优先级）
    emergency_run = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.EMERGENCY,
        preemptible=True,
        status=RunStatus.QUEUED,
    )
    test_db.add(emergency_run)
    test_db.commit()

    # 执行抢占
    result = preemption_service.preempt_run(victim_run.id, emergency_run.id)

    assert result is True

    # 验证受害者任务状态
    test_db.refresh(victim_run)
    assert victim_run.status == RunStatus.PREEMPTED
    assert victim_run.ended_at is not None

    # 验证租约状态
    test_db.refresh(lease)
    assert lease.lease_status == LeaseStatus.PREEMPTED
    assert lease.preempted_at is not None
    assert lease.preempted_by_run_id == emergency_run.id

    # 验证设备状态
    test_db.refresh(device)
    assert device.status == DeviceStatus.IDLE
    assert device.current_run_id is None


def test_preempt_run_only_normal_priority(
    preemption_service, test_db, setup_pool_and_devices, setup_plan
):
    """测试只抢占 NORMAL 优先级任务（allow_preempt_high=False）。"""
    pool = setup_pool_and_devices["pool"]
    plan = setup_plan
    device1 = setup_pool_and_devices["devices"][0]
    device2 = setup_pool_and_devices["devices"][1]

    # 创建 NORMAL 优先级任务
    normal_run = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.NORMAL,
        preemptible=True,
        status=RunStatus.RUNNING,
        device_id=device1.id,
    )
    # 创建 HIGH 优先级任务
    high_run = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.HIGH,
        preemptible=True,
        status=RunStatus.RUNNING,
        device_id=device2.id,
    )
    test_db.add_all([normal_run, high_run])

    # 创建活跃租约
    lease_normal = DeviceLease(
        device_id=device1.id,
        run_id=normal_run.id,
        lease_status=LeaseStatus.ACTIVE,
        preemptible=True,
    )
    lease_high = DeviceLease(
        device_id=device2.id,
        run_id=high_run.id,
        lease_status=LeaseStatus.ACTIVE,
        preemptible=True,
    )
    test_db.add_all([lease_normal, lease_high])
    test_db.commit()

    # 查找可抢占任务（不允许抢占 HIGH）
    preemptible_runs = preemption_service.find_preemptible_runs(pool.id, allow_preempt_high=False)

    # 只应该返回 NORMAL 优先级任务
    assert len(preemptible_runs) == 1
    assert preemptible_runs[0].id == normal_run.id
    assert preemptible_runs[0].priority == RunPriority.NORMAL


def test_check_and_execute_preemption_success(
    preemption_service, test_db, setup_pool_and_devices, setup_plan
):
    """测试完整的抢占检查和执行流程。"""
    pool = setup_pool_and_devices["pool"]
    plan = setup_plan
    device = setup_pool_and_devices["devices"][0]

    # 创建受害者任务（NORMAL 优先级）
    victim_run = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.NORMAL,
        preemptible=True,
        status=RunStatus.RUNNING,
        device_id=device.id,
    )
    test_db.add(victim_run)
    test_db.commit()

    # 创建活跃租约
    lease = DeviceLease(
        device_id=device.id,
        run_id=victim_run.id,
        lease_status=LeaseStatus.ACTIVE,
        preemptible=True,
    )
    test_db.add(lease)
    test_db.commit()

    # 创建 EMERGENCY 优先级任务
    emergency_run = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.EMERGENCY,
        preemptible=True,
        status=RunStatus.QUEUED,
    )
    test_db.add(emergency_run)
    test_db.commit()

    # 执行抢占检查和执行
    result = preemption_service.check_and_execute_preemption(emergency_run.id)

    assert result is True

    # 验证受害者任务被抢占
    test_db.refresh(victim_run)
    assert victim_run.status == RunStatus.PREEMPTED

    # 验证租约被抢占
    test_db.refresh(lease)
    assert lease.lease_status == LeaseStatus.PREEMPTED
    assert lease.preempted_by_run_id == emergency_run.id


def test_check_and_execute_preemption_not_emergency(
    preemption_service, test_db, setup_pool_and_devices, setup_plan
):
    """测试非 EMERGENCY 优先级任务不能触发抢占。"""
    pool = setup_pool_and_devices["pool"]
    plan = setup_plan
    device = setup_pool_and_devices["devices"][0]

    # 创建受害者任务
    victim_run = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.NORMAL,
        preemptible=True,
        status=RunStatus.RUNNING,
        device_id=device.id,
    )
    test_db.add(victim_run)
    test_db.commit()

    # 创建活跃租约
    lease = DeviceLease(
        device_id=device.id,
        run_id=victim_run.id,
        lease_status=LeaseStatus.ACTIVE,
        preemptible=True,
    )
    test_db.add(lease)
    test_db.commit()

    # 创建 NORMAL 优先级任务（不是 EMERGENCY）
    normal_run = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.NORMAL,
        preemptible=True,
        status=RunStatus.QUEUED,
    )
    test_db.add(normal_run)
    test_db.commit()

    # 执行抢占检查（应该失败，因为不是 EMERGENCY）
    result = preemption_service.check_and_execute_preemption(normal_run.id)

    assert result is False

    # 验证受害者任务没有被抢占
    test_db.refresh(victim_run)
    assert victim_run.status == RunStatus.RUNNING


def test_check_and_execute_preemption_no_victims(
    preemption_service, test_db, setup_pool_and_devices, setup_plan
):
    """测试没有可抢占任务时返回 False。"""
    pool = setup_pool_and_devices["pool"]
    plan = setup_plan

    # 创建 EMERGENCY 优先级任务
    emergency_run = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.EMERGENCY,
        preemptible=True,
        status=RunStatus.QUEUED,
    )
    test_db.add(emergency_run)
    test_db.commit()

    # 执行抢占检查（没有可抢占任务）
    result = preemption_service.check_and_execute_preemption(emergency_run.id)

    assert result is False


def test_check_and_execute_preemption_with_high_priority(
    preemption_service, test_db, setup_pool_and_devices, setup_plan
):
    """测试 allow_preempt_high=True 时可以抢占 HIGH 优先级任务。"""
    pool = setup_pool_and_devices["pool"]
    plan = setup_plan
    device = setup_pool_and_devices["devices"][0]

    # 创建 HIGH 优先级任务
    high_run = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.HIGH,
        preemptible=True,
        status=RunStatus.RUNNING,
        device_id=device.id,
    )
    test_db.add(high_run)
    test_db.commit()

    # 创建活跃租约
    lease = DeviceLease(
        device_id=device.id,
        run_id=high_run.id,
        lease_status=LeaseStatus.ACTIVE,
        preemptible=True,
    )
    test_db.add(lease)
    test_db.commit()

    # 创建 EMERGENCY 优先级任务
    emergency_run = RunSession(
        plan_id=plan.id,
        pool_id=pool.id,
        priority=RunPriority.EMERGENCY,
        preemptible=True,
        status=RunStatus.QUEUED,
    )
    test_db.add(emergency_run)
    test_db.commit()

    # 执行抢占检查和执行（允许抢占 HIGH）
    result = preemption_service.check_and_execute_preemption(
        emergency_run.id, allow_preempt_high=True
    )

    assert result is True

    # 验证 HIGH 优先级任务被抢占
    test_db.refresh(high_run)
    assert high_run.status == RunStatus.PREEMPTED

    # 验证租约被抢占
    test_db.refresh(lease)
    assert lease.lease_status == LeaseStatus.PREEMPTED
    assert lease.preempted_by_run_id == emergency_run.id
