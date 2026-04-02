"""设备池工作流集成测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, get_db, init_db, engine
from app.models.device import Device, DevicePool, DeviceStatus, DeviceLease
from app.models.run import RunSession, UpgradePlan
from app.models.enums import PoolPurpose, RunPriority, RunStatus, LeaseStatus
from app.services.pool_service import PoolService
from app.services.preemption_service import PreemptionService


@pytest.fixture
def test_db():
    """创建测试数据库。"""
    # 确保数据库表已创建
    init_db(engine)

    db = SessionLocal()
    yield db
    # 清理测试数据
    db.query(DeviceLease).delete()
    db.query(RunSession).delete()
    db.query(UpgradePlan).delete()
    db.query(Device).delete()
    db.query(DevicePool).delete()
    db.commit()
    db.close()


@pytest.fixture
def client(test_db):
    return TestClient(app)


class TestPoolWorkflow:
    """设备池完整工作流测试。"""

    def test_full_pool_workflow(self, client, test_db):
        """测试完整的设备池工作流。"""
        # 1. 创建默认设备池
        response = client.post("/api/pools", json={
            "name": "workflow_pool",
            "purpose": "stable",
            "reserved_ratio": 0.2,
            "max_parallel": 5,
        })
        assert response.status_code == 200
        pool_id = response.json()["id"]

        # 2. 创建设备并分配到池
        device = Device(serial="WORKFLOW001", status=DeviceStatus.IDLE, pool_id=pool_id)
        test_db.add(device)
        test_db.commit()

        # 3. 验证池容量
        response = client.get(f"/api/pools/{pool_id}/capacity")
        assert response.status_code == 200
        assert response.json()["available"] == 1

        # 4. 创建升级计划
        plan = UpgradePlan(name="Workflow Test Plan", default_pool_id=pool_id)
        test_db.add(plan)
        test_db.commit()

        # 5. 验证设备在池中
        response = client.get(f"/api/pools/{pool_id}/devices")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["serial"] == "WORKFLOW001"


class TestPriorityPreemptionWorkflow:
    """优先级抢占工作流测试。"""

    def test_emergency_preemption(self, test_db):
        """测试 emergency 任务抢占流程。"""
        # 1. 创建设备池和设备
        pool_service = PoolService(test_db)
        pool = pool_service.create_pool(name="preempt_workflow", purpose=PoolPurpose.STABLE, max_parallel=1)

        device = Device(serial="PREEMPT_W001", status=DeviceStatus.BUSY, pool_id=pool.id)
        test_db.add(device)
        test_db.commit()

        # 2. 创建升级计划
        plan = UpgradePlan(name="Preempt Workflow Plan")
        test_db.add(plan)
        test_db.commit()

        # 3. 创建正在运行的 normal 任务
        normal_run = RunSession(
            plan_id=plan.id,
            device_id=device.id,
            priority=RunPriority.NORMAL,
            status=RunStatus.RUNNING,
            preemptible=True,
            pool_id=pool.id,
        )
        test_db.add(normal_run)
        test_db.commit()

        lease = DeviceLease(
            device_id=device.id,
            run_id=normal_run.id,
            lease_status=LeaseStatus.ACTIVE,
            preemptible=True,
        )
        test_db.add(lease)
        test_db.commit()

        # 4. 创建 emergency 任务
        emergency_run = RunSession(
            plan_id=plan.id,
            priority=RunPriority.EMERGENCY,
            status=RunStatus.QUEUED,
            pool_id=pool.id,
        )
        test_db.add(emergency_run)
        test_db.commit()

        # 5. 执行抢占
        preemption_service = PreemptionService(test_db)
        result = preemption_service.check_and_execute_preemption(emergency_run.id)

        assert result is True

        # 6. 验证状态
        test_db.refresh(normal_run)
        test_db.refresh(device)

        assert normal_run.status == RunStatus.PREEMPTED
        assert device.status == DeviceStatus.IDLE

    def test_pool_capacity_calculation(self, test_db):
        """测试池容量计算。"""
        pool_service = PoolService(test_db)
        pool = pool_service.create_pool(name="capacity_test", purpose=PoolPurpose.STABLE, max_parallel=10)

        # 添加不同状态的设备
        for i in range(5):
            device = Device(serial=f"IDLE_{i:03d}", status=DeviceStatus.IDLE, pool_id=pool.id)
            test_db.add(device)

        for i in range(3):
            device = Device(serial=f"BUSY_{i:03d}", status=DeviceStatus.BUSY, pool_id=pool.id)
            test_db.add(device)

        for i in range(2):
            device = Device(serial=f"OFFLINE_{i:03d}", status=DeviceStatus.OFFLINE, pool_id=pool.id)
            test_db.add(device)

        test_db.commit()

        # 验证容量
        capacity = pool_service.get_pool_capacity(pool.id)
        assert capacity["total"] == 10
        assert capacity["available"] == 5
        assert capacity["busy"] == 3
        assert capacity["offline"] == 2

    def test_default_pool_creation(self, test_db):
        """测试默认设备池创建。"""
        pool_service = PoolService(test_db)
        pools = pool_service.create_default_pools()

        assert len(pools) == 3

        pool_names = [p.name for p in pools]
        assert "stable_pool" in pool_names
        assert "stress_pool" in pool_names
        assert "emergency_pool" in pool_names

        # 验证每个池的用途
        for pool in pools:
            if pool.name == "stable_pool":
                assert pool.purpose == PoolPurpose.STABLE
            elif pool.name == "stress_pool":
                assert pool.purpose == PoolPurpose.STRESS
            elif pool.name == "emergency_pool":
                assert pool.purpose == PoolPurpose.EMERGENCY