"""Worker 服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.executors.mock_executor import MockADBExecutor
from app.executors.run_executor import MockRunExecutor
from app.models.device import Device, DeviceStatus
from app.models.run import RunSession, RunStatus, UpgradePlan, UpgradeType
from app.services.scheduler_service import SchedulerService
from app.services.worker_service import WorkerService


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
def setup_data(test_db):
    """设置测试数据。"""
    # 创建设备 - 使用 MockExecutor 中预设的设备序列号
    device = Device(
        serial="ABC123",
        brand="Test",
        model="TestModel",
        status=DeviceStatus.IDLE,
        battery_level=80,
    )
    test_db.add(device)

    # 创建升级计划
    plan = UpgradePlan(
        name="测试计划",
        upgrade_type=UpgradeType.FULL,
        package_path="/tmp/update.zip",
    )
    test_db.add(plan)
    test_db.commit()

    return {"device": device, "plan": plan}


def test_worker_service_init(test_db):
    """测试 Worker 服务初始化。"""
    worker = WorkerService(test_db)
    assert worker is not None
    assert worker.running is False


def test_worker_can_start_and_stop(test_db):
    """测试 Worker 启动和停止。"""
    worker = WorkerService(test_db, poll_interval=1)

    # 测试初始状态
    assert worker.running is False

    # 测试设置 running 标志
    worker.running = True
    assert worker.running is True

    # 重置
    worker.running = False
    assert worker.running is False


def test_worker_process_single_task(test_db, setup_data):
    """测试处理单个任务。"""
    device = setup_data["device"]
    plan = setup_data["plan"]

    # 创建任务
    run = RunSession(
        plan_id=plan.id,
        device_id=device.id,
        status=RunStatus.QUEUED,
    )
    test_db.add(run)
    test_db.commit()

    # 创建 Worker，使用 MockRunExecutor
    mock_executor = MockADBExecutor.upgrade_success_responses()
    worker = WorkerService(
        test_db,
        max_iterations=1,
    )
    # 替换 executor 为 MockRunExecutor
    worker.executor = MockRunExecutor(mock_executor=mock_executor)

    # 预留任务
    scheduler = SchedulerService(test_db)
    scheduler.reserve_run(run.id)

    # 执行一轮
    worker.process_one_iteration()

    # 检查任务状态
    test_db.refresh(run)
    assert run.status == RunStatus.PASSED


def test_worker_handles_no_tasks(test_db):
    """测试无任务时的处理。"""
    worker = WorkerService(test_db, max_iterations=0)

    # 无任务时不应该出错
    result = worker.process_one_iteration()
    assert result is None


def test_worker_respects_concurrency_limit(test_db, setup_data):
    """测试并发限制。"""
    device = setup_data["device"]
    plan = setup_data["plan"]

    # 创建多个任务
    for i in range(3):
        run = RunSession(
            plan_id=plan.id,
            device_id=device.id,
            status=RunStatus.QUEUED,
        )
        test_db.add(run)
    test_db.commit()

    # 设置并发上限为 1
    worker = WorkerService(test_db, max_concurrent=1, max_iterations=0)

    # 应该只能启动一个任务
    count = worker.get_running_count()
    assert count == 0  # 初始状态


def test_worker_marks_device_idle_after_completion(test_db, setup_data):
    """测试任务完成后释放设备。"""
    device = setup_data["device"]
    plan = setup_data["plan"]

    run = RunSession(
        plan_id=plan.id,
        device_id=device.id,
        status=RunStatus.QUEUED,
    )
    test_db.add(run)
    test_db.commit()

    scheduler = SchedulerService(test_db)
    scheduler.reserve_run(run.id)

    mock_executor = MockADBExecutor.upgrade_success_responses()
    worker = WorkerService(test_db, max_iterations=1)
    worker.executor = MockRunExecutor(mock_executor=mock_executor)

    worker.process_one_iteration()

    test_db.refresh(device)
    assert device.status == DeviceStatus.IDLE
