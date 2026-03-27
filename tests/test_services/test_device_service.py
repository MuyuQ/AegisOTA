"""设备管理服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DeviceStatus
from app.services.device_service import DeviceService
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
def device_service(test_db):
    """创建设备服务。"""
    return DeviceService(test_db, MockExecutor.default_device_responses())


def test_sync_devices(device_service):
    """测试设备同步。"""
    devices = device_service.sync_devices()

    assert len(devices) >= 1
    assert devices[0].serial == "ABC123"


def test_get_device_by_serial(device_service, test_db):
    """测试通过序列号获取设备。"""
    # 先同步
    device_service.sync_devices()

    device = device_service.get_device_by_serial("ABC123")
    assert device is not None
    assert device.serial == "ABC123"


def test_get_available_devices(device_service, test_db):
    """测试获取可用设备列表。"""
    # 先同步
    device_service.sync_devices()

    # 设置一个设备为忙碌
    device = test_db.query(Device).filter_by(serial="ABC123").first()
    device.status = DeviceStatus.BUSY
    test_db.commit()

    available = device_service.get_available_devices()
    assert len(available) == 1  # 只有 XYZ789 可用


def test_quarantine_device(device_service, test_db):
    """测试设备隔离。"""
    device_service.sync_devices()

    device_service.quarantine_device("ABC123", "Test quarantine")

    device = test_db.query(Device).filter_by(serial="ABC123").first()
    assert device.status == DeviceStatus.QUARANTINED
    assert device.quarantine_reason == "Test quarantine"


def test_recover_device(device_service, test_db):
    """测试设备恢复。"""
    device_service.sync_devices()
    device_service.quarantine_device("ABC123", "Test")

    device_service.recover_device("ABC123")

    device = test_db.query(Device).filter_by(serial="ABC123").first()
    assert device.status == DeviceStatus.IDLE
    assert device.quarantine_reason is None


def test_update_device_tags(device_service, test_db):
    """测试更新设备标签。"""
    device_service.sync_devices()

    device_service.update_device_tags("ABC123", ["主力机型", "Android14"])

    device = test_db.query(Device).filter_by(serial="ABC123").first()
    assert device.get_tags() == ["主力机型", "Android14"]