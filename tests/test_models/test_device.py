"""设备模型测试。"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DeviceLease, DeviceStatus, LeaseStatus


@pytest.fixture
def db_engine():
    """创建测试数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    """创建测试数据库会话。"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


class TestDeviceStatus:
    """DeviceStatus 枚举测试。"""

    def test_status_values(self):
        """测试枚举值正确。"""
        assert DeviceStatus.IDLE == "idle"
        assert DeviceStatus.BUSY == "busy"
        assert DeviceStatus.OFFLINE == "offline"
        assert DeviceStatus.QUARANTINED == "quarantined"
        assert DeviceStatus.RECOVERING == "recovering"

    def test_status_count(self):
        """测试枚举值数量。"""
        assert len(DeviceStatus) == 5

    def test_status_is_string_enum(self):
        """测试枚举是字符串枚举。"""
        assert isinstance(DeviceStatus.IDLE.value, str)


class TestDeviceCreation:
    """Device 创建测试。"""

    def test_create_device_minimal(self, db_session):
        """测试创建最小设备。"""
        device = Device(serial="ABC123")
        db_session.add(device)
        db_session.commit()

        assert device.id is not None
        assert device.serial == "ABC123"
        assert device.status == DeviceStatus.IDLE
        assert device.created_at is not None
        assert device.updated_at is not None

    def test_create_device_full(self, db_session):
        """测试创建完整设备。"""
        device = Device(
            serial="XYZ789",
            brand="Google",
            model="Pixel 7",
            android_version="14",
            build_fingerprint="google/panther/panther:14/AP2A.240305.004/11948111:user/release-keys",
            status=DeviceStatus.BUSY,
            health_score=0.95,
            battery_level=85,
            last_seen_at=datetime.utcnow(),
        )
        device.set_tags(["test", "stable"])
        db_session.add(device)
        db_session.commit()

        assert device.id is not None
        assert device.brand == "Google"
        assert device.model == "Pixel 7"
        assert device.health_score == 0.95
        assert device.get_tags() == ["test", "stable"]

    def test_device_unique_serial(self, db_session):
        """测试设备序列号唯一约束。"""
        device1 = Device(serial="UNIQUE123")
        device2 = Device(serial="UNIQUE123")
        db_session.add(device1)
        db_session.commit()

        db_session.add(device2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()


class TestDeviceMethods:
    """Device 方法测试。"""

    def test_get_tags_empty(self, db_session):
        """测试空标签。"""
        device = Device(serial="TEST001")
        assert device.get_tags() == []

    def test_get_tags_with_values(self, db_session):
        """测试获取标签。"""
        device = Device(serial="TEST002")
        device.set_tags(["tag1", "tag2", "tag3"])
        db_session.add(device)
        db_session.commit()

        assert device.get_tags() == ["tag1", "tag2", "tag3"]

    def test_set_tags_empty_list(self, db_session):
        """测试设置空标签列表。"""
        device = Device(serial="TEST003")
        device.set_tags(["initial"])
        device.set_tags([])
        db_session.add(device)
        db_session.commit()

        assert device.tags is None
        assert device.get_tags() == []

    def test_is_available_idle(self, db_session):
        """测试空闲设备可用。"""
        device = Device(serial="AVAIL001", status=DeviceStatus.IDLE)
        db_session.add(device)
        db_session.commit()

        assert device.is_available() is True

    def test_is_available_busy(self, db_session):
        """测试忙碌设备不可用。"""
        device = Device(serial="BUSY001", status=DeviceStatus.BUSY)
        db_session.add(device)
        db_session.commit()

        assert device.is_available() is False

    def test_is_available_offline(self, db_session):
        """测试离线设备不可用。"""
        device = Device(serial="OFFLINE001", status=DeviceStatus.OFFLINE)
        db_session.add(device)
        db_session.commit()

        assert device.is_available() is False

    def test_is_available_quarantined(self, db_session):
        """测试隔离设备不可用。"""
        device = Device(serial="QUAR001", status=DeviceStatus.QUARANTINED)
        db_session.add(device)
        db_session.commit()

        assert device.is_available() is False


class TestDeviceDatabaseOperations:
    """Device 数据库操作测试。"""

    def test_update_device_status(self, db_session):
        """测试更新设备状态。"""
        device = Device(serial="UPDATE001", status=DeviceStatus.IDLE)
        db_session.add(device)
        db_session.commit()

        device.status = DeviceStatus.BUSY
        db_session.commit()

        db_session.refresh(device)
        assert device.status == DeviceStatus.BUSY

    def test_update_device_health(self, db_session):
        """测试更新设备健康信息。"""
        device = Device(serial="HEALTH001", health_score=0.8, battery_level=50)
        db_session.add(device)
        db_session.commit()

        device.health_score = 0.5
        device.battery_level = 25
        db_session.commit()

        db_session.refresh(device)
        assert device.health_score == 0.5
        assert device.battery_level == 25

    def test_quarantine_device(self, db_session):
        """测试隔离设备。"""
        device = Device(serial="QUAR_TEST", status=DeviceStatus.BUSY)
        db_session.add(device)
        db_session.commit()

        device.status = DeviceStatus.QUARANTINED
        device.quarantine_reason = "启动失败"
        device.current_run_id = None
        db_session.commit()

        db_session.refresh(device)
        assert device.status == DeviceStatus.QUARANTINED
        assert device.quarantine_reason == "启动失败"

    def test_query_device_by_serial(self, db_session):
        """测试通过序列号查询设备。"""
        device = Device(serial="QUERY001", brand="Samsung")
        db_session.add(device)
        db_session.commit()

        found = db_session.query(Device).filter_by(serial="QUERY001").first()
        assert found is not None
        assert found.brand == "Samsung"

    def test_query_available_devices(self, db_session):
        """测试查询可用设备。"""
        devices = [
            Device(serial="IDLE01", status=DeviceStatus.IDLE),
            Device(serial="BUSY01", status=DeviceStatus.BUSY),
            Device(serial="IDLE02", status=DeviceStatus.IDLE),
            Device(serial="OFFLINE01", status=DeviceStatus.OFFLINE),
        ]
        db_session.add_all(devices)
        db_session.commit()

        available = (
            db_session.query(Device)
            .filter(Device.status == DeviceStatus.IDLE)
            .all()
        )
        assert len(available) == 2
        assert all(d.status == DeviceStatus.IDLE for d in available)


class TestDeviceLeaseCreation:
    """DeviceLease 创建测试。"""

    def test_create_lease_minimal(self, db_session):
        """测试创建最小租约。"""
        device = Device(serial="LEASE001")
        db_session.add(device)
        db_session.commit()

        lease = DeviceLease(device_id=device.id)
        db_session.add(lease)
        db_session.commit()

        assert lease.id is not None
        assert lease.device_id == device.id
        assert lease.lease_status == LeaseStatus.ACTIVE
        assert lease.leased_at is not None

    def test_create_lease_with_expiry(self, db_session):
        """测试创建带过期时间的租约。"""
        device = Device(serial="LEASE002")
        db_session.add(device)
        db_session.commit()

        expired_at = datetime.utcnow() + timedelta(hours=1)
        lease = DeviceLease(device_id=device.id, expired_at=expired_at)
        db_session.add(lease)
        db_session.commit()

        assert lease.expired_at is not None

    def test_lease_device_relationship(self, db_session):
        """测试租约与设备的关联。"""
        device = Device(serial="LEASE003")
        db_session.add(device)
        db_session.commit()

        lease = DeviceLease(device_id=device.id)
        db_session.add(lease)
        db_session.commit()

        assert lease.device is not None
        assert lease.device.serial == "LEASE003"
        assert len(device.leases) == 1

    def test_lease_release(self, db_session):
        """测试释放租约。"""
        device = Device(serial="LEASE004")
        db_session.add(device)
        db_session.commit()

        lease = DeviceLease(device_id=device.id)
        db_session.add(lease)
        db_session.commit()

        lease.lease_status = LeaseStatus.RELEASED
        lease.released_at = datetime.utcnow()
        db_session.commit()

        db_session.refresh(lease)
        assert lease.lease_status == LeaseStatus.RELEASED
        assert lease.released_at is not None


class TestDeviceLeaseMethods:
    """DeviceLease 方法测试。"""

    def test_is_active_fresh_lease(self, db_session):
        """测试新租约是否有效。"""
        device = Device(serial="ACTIVE001")
        db_session.add(device)
        db_session.commit()

        lease = DeviceLease(device_id=device.id)
        db_session.add(lease)
        db_session.commit()

        assert lease.is_active() is True

    def test_is_active_expired_lease(self, db_session):
        """测试过期租约无效。"""
        device = Device(serial="EXPIRED001")
        db_session.add(device)
        db_session.commit()

        expired_at = datetime.utcnow() - timedelta(hours=1)
        lease = DeviceLease(device_id=device.id, expired_at=expired_at)
        db_session.add(lease)
        db_session.commit()

        assert lease.is_active() is False

    def test_is_active_released_lease(self, db_session):
        """测试已释放租约无效。"""
        device = Device(serial="RELEASED001")
        db_session.add(device)
        db_session.commit()

        lease = DeviceLease(device_id=device.id, lease_status=LeaseStatus.RELEASED)
        db_session.add(lease)
        db_session.commit()

        assert lease.is_active() is False

    def test_is_active_future_expiry(self, db_session):
        """测试未过期租约有效。"""
        device = Device(serial="FUTURE001")
        db_session.add(device)
        db_session.commit()

        expired_at = datetime.utcnow() + timedelta(hours=1)
        lease = DeviceLease(device_id=device.id, expired_at=expired_at)
        db_session.add(lease)
        db_session.commit()

        assert lease.is_active() is True


class TestLeaseStatus:
    """LeaseStatus 枚举测试。"""

    def test_status_values(self):
        """测试枚举值正确。"""
        assert LeaseStatus.ACTIVE == "active"
        assert LeaseStatus.EXPIRED == "expired"
        assert LeaseStatus.RELEASED == "released"

    def test_status_count(self):
        """测试枚举值数量。"""
        assert len(LeaseStatus) == 3