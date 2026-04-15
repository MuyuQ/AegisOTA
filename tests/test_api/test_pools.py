"""设备池 API 测试。"""

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.device import Device, DevicePool, DeviceStatus


@pytest.fixture
def client():
    """创建测试客户端。"""
    return TestClient(app)


@pytest.fixture
def setup_db():
    """设置测试数据库。"""
    from app.database import engine, init_db

    # 确保数据库表已创建
    init_db(engine)

    db = SessionLocal()
    yield db
    # 清理测试数据
    db.query(DevicePool).delete()
    db.query(Device).delete()
    db.commit()
    db.close()


class TestPoolsAPI:
    """设备池 API 测试。"""

    def test_list_pools_empty(self, client, setup_db):
        """测试池列表。"""
        response = client.get("/api/v1/pools")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_pool(self, client, setup_db):
        """测试创建设备池。"""
        response = client.post(
            "/api/v1/pools",
            json={
                "name": "test_pool",
                "purpose": "stable",
                "reserved_ratio": 0.2,
                "max_parallel": 5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_pool"
        assert data["purpose"] == "stable"
        assert data["reserved_ratio"] == 0.2

    def test_create_pool_duplicate_name(self, client, setup_db):
        """测试创建重复名称设备池。"""
        client.post(
            "/api/v1/pools",
            json={
                "name": "duplicate",
                "purpose": "stable",
            },
        )
        response = client.post(
            "/api/v1/pools",
            json={
                "name": "duplicate",
                "purpose": "stress",
            },
        )
        assert response.status_code == 400

    def test_get_pool_by_id(self, client, setup_db):
        """测试获取设备池详情。"""
        create_response = client.post(
            "/api/v1/pools",
            json={
                "name": "detail_pool",
                "purpose": "stable",
            },
        )
        pool_id = create_response.json()["id"]

        response = client.get(f"/api/v1/pools/{pool_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "detail_pool"

    def test_get_pool_not_found(self, client):
        """测试获取不存在的设备池。"""
        response = client.get("/api/v1/pools/9999")
        assert response.status_code == 404

    def test_update_pool(self, client, setup_db):
        """测试更新设备池。"""
        create_response = client.post(
            "/api/v1/pools",
            json={
                "name": "update_pool",
                "purpose": "stable",
            },
        )
        pool_id = create_response.json()["id"]

        response = client.put(
            f"/api/v1/pools/{pool_id}",
            json={
                "reserved_ratio": 0.3,
            },
        )
        assert response.status_code == 200
        assert response.json()["reserved_ratio"] == 0.3

    def test_delete_pool(self, client, setup_db):
        """测试删除设备池。"""
        create_response = client.post(
            "/api/v1/pools",
            json={
                "name": "delete_pool",
                "purpose": "stable",
            },
        )
        pool_id = create_response.json()["id"]

        response = client.delete(f"/api/v1/pools/{pool_id}")
        assert response.status_code == 200

        # 确认已删除
        get_response = client.get(f"/api/v1/pools/{pool_id}")
        assert get_response.status_code == 404

    def test_assign_device_to_pool(self, client, setup_db):
        """测试分配设备到池。"""
        db = setup_db
        # 创建设备
        device = Device(serial="ASSIGN_API001")
        db.add(device)
        db.commit()

        # 创建设备池
        pool_response = client.post(
            "/api/v1/pools",
            json={
                "name": "assign_pool",
                "purpose": "stable",
            },
        )
        pool_id = pool_response.json()["id"]

        response = client.post(
            f"/api/v1/pools/{pool_id}/assign",
            json={
                "device_id": device.id,
            },
        )
        assert response.status_code == 200
        assert response.json()["pool_id"] == pool_id

    def test_get_pool_devices(self, client, setup_db):
        """测试获取池内设备列表。"""
        db = setup_db
        # 创建设备池
        pool_response = client.post(
            "/api/v1/pools",
            json={
                "name": "devices_pool",
                "purpose": "stable",
            },
        )
        pool_id = pool_response.json()["id"]

        # 创建设备并分配到池
        for i in range(3):
            device = Device(serial=f"DEVICES{i:03d}", pool_id=pool_id)
            db.add(device)
        db.commit()

        response = client.get(f"/api/v1/pools/{pool_id}/devices")
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_get_pool_capacity(self, client, setup_db):
        """测试获取池容量。"""
        db = setup_db
        pool_response = client.post(
            "/api/v1/pools",
            json={
                "name": "capacity_pool",
                "purpose": "stable",
                "max_parallel": 10,
            },
        )
        pool_id = pool_response.json()["id"]

        # 添加设备
        for i in range(5):
            device = Device(
                serial=f"CAP_API{i:03d}",
                pool_id=pool_id,
                status=DeviceStatus.IDLE,
            )
            db.add(device)
        for i in range(3):
            device = Device(
                serial=f"CAP_BUSY{i:03d}",
                pool_id=pool_id,
                status=DeviceStatus.BUSY,
            )
            db.add(device)
        db.commit()

        response = client.get(f"/api/v1/pools/{pool_id}/capacity")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 8
        assert data["available"] == 5
        assert data["busy"] == 3
