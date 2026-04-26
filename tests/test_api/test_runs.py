"""任务 API 测试。"""

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.device import Device, DeviceStatus
from app.models.run import RunSession, RunStatus, UpgradePlan, UpgradeType


@pytest.fixture
def client():
    """创建测试客户端。"""
    return TestClient(app)


@pytest.fixture
def setup_data():
    """设置测试数据。"""
    db = SessionLocal()

    device = Device(serial="RUN001", status=DeviceStatus.IDLE, battery_level=80)
    db.add(device)

    plan = UpgradePlan(
        name="测试计划",
        upgrade_type=UpgradeType.FULL,
        package_path="/tmp/update.zip",
    )
    db.add(plan)
    db.commit()

    yield {"db": db, "device": device, "plan": plan}

    db.query(RunSession).delete()
    db.query(UpgradePlan).delete()
    db.query(Device).delete()
    db.commit()
    db.close()


def test_list_runs(client, setup_data):
    """测试列出任务。"""
    response = client.get("/api/v1/runs")
    assert response.status_code == 200


def test_create_run(client, setup_data):
    """测试创建任务。"""
    plan = setup_data["plan"]

    response = client.post(
        "/api/v1/runs",
        json={
            "plan_id": plan.id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data


def test_create_run_with_device(client, setup_data):
    """测试创建任务（指定设备）。"""
    plan = setup_data["plan"]
    device = setup_data["device"]

    response = client.post(
        "/api/v1/runs",
        json={
            "plan_id": plan.id,
            "device_serial": device.serial,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data


def test_create_run_invalid_plan(client):
    """测试创建任务（无效计划）。"""
    response = client.post(
        "/api/v1/runs",
        json={
            "plan_id": 99999,
        },
    )
    assert response.status_code == 404


def test_get_run(client, setup_data):
    """测试获取任务详情。"""
    db = setup_data["db"]
    plan = setup_data["plan"]
    device = setup_data["device"]

    run = RunSession(plan_id=plan.id, device_id=device.id)
    db.add(run)
    db.commit()

    response = client.get(f"/api/v1/runs/{run.id}")
    assert response.status_code == 200


def test_get_run_not_found(client):
    """测试获取不存在的任务。"""
    response = client.get("/api/v1/runs/99999")
    assert response.status_code == 404


def test_abort_run(client, setup_data):
    """测试终止任务。"""
    db = setup_data["db"]
    plan = setup_data["plan"]
    device = setup_data["device"]

    run = RunSession(plan_id=plan.id, device_id=device.id, status=RunStatus.QUEUED)
    db.add(run)
    db.commit()

    response = client.post(f"/api/v1/runs/{run.id}/abort")
    assert response.status_code == 200


def test_list_plans(client, setup_data):
    """测试列出计划。"""
    response = client.get("/api/v1/runs/plans")
    assert response.status_code == 200


def test_create_plan(client):
    """测试创建计划。"""
    response = client.post(
        "/api/v1/runs/plans",
        json={
            "name": "新计划",
            "upgrade_type": "full",
            "package_path": "/tmp/new.zip",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "plan_id" in data


def test_create_plan_invalid_type(client):
    """测试创建计划（无效类型）。"""
    response = client.post(
        "/api/v1/runs/plans",
        json={
            "name": "新计划",
            "upgrade_type": "invalid_type",
            "package_path": "/tmp/new.zip",
        },
    )
    assert response.status_code == 400
