"""设备 API 测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, SessionLocal, get_db
from app.models.device import Device, DeviceStatus


@pytest.fixture
def client():
    """创建测试客户端。"""
    return TestClient(app)


@pytest.fixture
def setup_db():
    """设置测试数据库。"""
    db = SessionLocal()
    device = Device(
        serial="API001",
        brand="Test",
        model="TestModel",
        status=DeviceStatus.IDLE,
        battery_level=80,
    )
    db.add(device)
    db.commit()
    yield db
    db.query(Device).delete()
    db.commit()
    db.close()


def test_list_devices(client, setup_db):
    """测试列出设备。"""
    response = client.get("/api/devices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_device(client, setup_db):
    """测试获取单个设备。"""
    response = client.get("/api/devices/API001")
    assert response.status_code == 200


def test_get_device_not_found(client):
    """测试获取不存在的设备。"""
    response = client.get("/api/devices/NOTEXIST")
    assert response.status_code == 404


def test_quarantine_device(client, setup_db):
    """测试隔离设备。"""
    response = client.post("/api/devices/API001/quarantine", json={"reason": "Test"})
    assert response.status_code == 200


def test_recover_device(client, setup_db):
    """测试恢复设备。"""
    # 先隔离
    client.post("/api/devices/API001/quarantine", json={"reason": "Test"})

    response = client.post("/api/devices/API001/recover")
    assert response.status_code == 200


def test_sync_devices(client):
    """测试同步设备。"""
    response = client.post("/api/devices/sync")
    assert response.status_code == 200