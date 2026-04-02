"""设备池管理服务测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device, DevicePool, DeviceStatus
from app.models.enums import PoolPurpose
from app.services.pool_service import PoolService


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
def pool_service(test_db):
    """创建池服务。"""
    return PoolService(test_db)


@pytest.fixture
def sample_device(test_db):
    """创建样本设备。"""
    device = Device(
        serial="TEST001",
        brand="Google",
        model="Pixel",
        system_version="14",
        status=DeviceStatus.IDLE,
    )
    test_db.add(device)
    test_db.commit()
    return device


class TestPoolServiceCreation:
    """测试池创建功能。"""

    def test_create_pool_minimal(self, pool_service, test_db):
        """测试创建最小化配置的池。"""
        pool = pool_service.create_pool(name="test_pool", purpose=PoolPurpose.STABLE)

        assert pool is not None
        assert pool.name == "test_pool"
        assert pool.purpose == PoolPurpose.STABLE
        assert pool.reserved_ratio == 0.2  # 默认值
        assert pool.max_parallel == 5  # 默认值
        assert pool.tag_selector is None
        assert pool.enabled is True

    def test_create_pool_full_config(self, pool_service, test_db):
        """测试创建完整配置的池。"""
        tag_selector = {"brand": "Google", "min_version": "14"}
        pool = pool_service.create_pool(
            name="full_config_pool",
            purpose=PoolPurpose.STRESS,
            reserved_ratio=0.3,
            max_parallel=10,
            tag_selector=tag_selector,
            enabled=False,
        )

        assert pool is not None
        assert pool.name == "full_config_pool"
        assert pool.purpose == PoolPurpose.STRESS
        assert pool.reserved_ratio == 0.3
        assert pool.max_parallel == 10
        assert pool.get_tag_selector() == tag_selector
        assert pool.enabled is False

    def test_create_pool_duplicate_name_raises_error(self, pool_service, test_db):
        """测试创建重复名称的池应抛出错误。"""
        pool_service.create_pool(name="duplicate_pool", purpose=PoolPurpose.STABLE)

        with pytest.raises(ValueError, match="Pool with name 'duplicate_pool' already exists"):
            pool_service.create_pool(name="duplicate_pool", purpose=PoolPurpose.STRESS)


class TestPoolServiceQuery:
    """测试池查询功能。"""

    @pytest.fixture
    def pools_with_data(self, pool_service, test_db):
        """创建多个池用于测试。"""
        pool1 = pool_service.create_pool(name="stable_pool", purpose=PoolPurpose.STABLE)
        pool2 = pool_service.create_pool(name="stress_pool", purpose=PoolPurpose.STRESS)
        pool3 = pool_service.create_pool(name="emergency_pool", purpose=PoolPurpose.EMERGENCY)
        pool4 = pool_service.create_pool(
            name="disabled_pool", purpose=PoolPurpose.STABLE, enabled=False
        )
        test_db.commit()
        return [pool1, pool2, pool3, pool4]

    def test_get_pool_by_id(self, pool_service, pools_with_data):
        """测试通过 ID 获取池。"""
        pool = pools_with_data[0]
        result = pool_service.get_pool_by_id(pool.id)

        assert result is not None
        assert result.id == pool.id
        assert result.name == "stable_pool"

    def test_get_pool_by_id_not_found(self, pool_service):
        """测试获取不存在的池返回 None。"""
        result = pool_service.get_pool_by_id(99999)
        assert result is None

    def test_get_pool_by_name(self, pool_service, pools_with_data):
        """测试通过名称获取池。"""
        result = pool_service.get_pool_by_name("stress_pool")

        assert result is not None
        assert result.name == "stress_pool"
        assert result.purpose == PoolPurpose.STRESS

    def test_get_pool_by_name_not_found(self, pool_service):
        """测试获取不存在的池名称返回 None。"""
        result = pool_service.get_pool_by_name("nonexistent_pool")
        assert result is None

    def test_list_pools_all(self, pool_service, pools_with_data):
        """测试列出所有池。"""
        pools = pool_service.list_pools()

        assert len(pools) == 4
        names = [p.name for p in pools]
        assert "stable_pool" in names
        assert "stress_pool" in names
        assert "emergency_pool" in names
        assert "disabled_pool" in names

    def test_list_pools_filter_by_purpose(self, pool_service, pools_with_data):
        """测试按用途筛选池。"""
        pools = pool_service.list_pools(purpose=PoolPurpose.STABLE)

        assert len(pools) == 2
        for pool in pools:
            assert pool.purpose == PoolPurpose.STABLE

    def test_list_pools_enabled_only(self, pool_service, pools_with_data):
        """测试只列出启用的池。"""
        pools = pool_service.list_pools(enabled_only=True)

        assert len(pools) == 3
        for pool in pools:
            assert pool.enabled is True


class TestPoolServiceUpdate:
    """测试池更新功能。"""

    def test_update_pool_config(self, pool_service, test_db):
        """测试更新池配置。"""
        pool = pool_service.create_pool(name="update_test_pool", purpose=PoolPurpose.STABLE)

        updated = pool_service.update_pool(
            pool.id, reserved_ratio=0.5, max_parallel=20
        )

        assert updated is not None
        assert updated.reserved_ratio == 0.5
        assert updated.max_parallel == 20

    def test_update_pool_tag_selector(self, pool_service, test_db):
        """测试更新标签选择器。"""
        pool = pool_service.create_pool(name="tag_update_pool", purpose=PoolPurpose.STRESS)

        new_selector = {"brand": "Samsung", "tags": ["5G", "flagship"]}
        updated = pool_service.update_pool(pool.id, tag_selector=new_selector)

        assert updated is not None
        assert updated.get_tag_selector() == new_selector

    def test_update_pool_enable_disable(self, pool_service, test_db):
        """测试启用/禁用池。"""
        pool = pool_service.create_pool(
            name="enable_test_pool", purpose=PoolPurpose.STABLE, enabled=True
        )

        # 禁用
        updated = pool_service.update_pool(pool.id, enabled=False)
        assert updated is not None
        assert updated.enabled is False

        # 重新启用
        updated = pool_service.update_pool(pool.id, enabled=True)
        assert updated is not None
        assert updated.enabled is True

    def test_update_pool_not_found(self, pool_service):
        """测试更新不存在的池返回 None。"""
        result = pool_service.update_pool(99999, reserved_ratio=0.5)
        assert result is None


class TestPoolServiceDeviceAssignment:
    """测试设备分配功能。"""

    def test_assign_device_to_pool(self, pool_service, sample_device, test_db):
        """测试将设备分配到池。"""
        pool = pool_service.create_pool(name="assignment_pool", purpose=PoolPurpose.STABLE)

        result = pool_service.assign_device_to_pool(sample_device.id, pool.id)

        assert result is not None
        assert result.pool_id == pool.id
        test_db.refresh(sample_device)
        assert sample_device.pool_id == pool.id

    def test_assign_device_to_pool_device_not_found(self, pool_service):
        """测试分配不存在的设备返回 None。"""
        pool = pool_service.create_pool(name="test_pool", purpose=PoolPurpose.STABLE)
        result = pool_service.assign_device_to_pool(99999, pool.id)
        assert result is None

    def test_assign_device_to_pool_pool_not_found(self, pool_service, sample_device):
        """测试分配到不存在的池返回 None。"""
        result = pool_service.assign_device_to_pool(sample_device.id, 99999)
        assert result is None

    def test_change_device_pool(self, pool_service, sample_device, test_db):
        """测试更换设备所属池。"""
        pool1 = pool_service.create_pool(name="pool1", purpose=PoolPurpose.STABLE)
        pool2 = pool_service.create_pool(name="pool2", purpose=PoolPurpose.STRESS)

        # 先分配到 pool1
        pool_service.assign_device_to_pool(sample_device.id, pool1.id)

        # 再分配到 pool2
        result = pool_service.assign_device_to_pool(sample_device.id, pool2.id)

        assert result is not None
        assert result.pool_id == pool2.id
        test_db.refresh(sample_device)
        assert sample_device.pool_id == pool2.id

    def test_remove_device_from_pool(self, pool_service, sample_device, test_db):
        """测试从池移除设备。"""
        pool = pool_service.create_pool(name="removal_pool", purpose=PoolPurpose.STABLE)
        pool_service.assign_device_to_pool(sample_device.id, pool.id)

        result = pool_service.remove_device_from_pool(sample_device.id)

        assert result is not None
        assert result.pool_id is None
        test_db.refresh(sample_device)
        assert sample_device.pool_id is None

    def test_remove_device_not_in_pool(self, pool_service, sample_device):
        """测试移除未分配的设备返回 None。"""
        result = pool_service.remove_device_from_pool(sample_device.id)
        assert result is None


class TestPoolServiceCapacity:
    """测试池容量计算功能。"""

    @pytest.fixture
    def pool_with_devices(self, pool_service, test_db):
        """创建带有多个设备的池。"""
        pool = pool_service.create_pool(
            name="capacity_pool",
            purpose=PoolPurpose.STABLE,
            reserved_ratio=0.2,
            max_parallel=3,
        )

        # 创建 5 个设备：3 个 idle, 1 个 busy, 1 个 offline
        for i in range(3):
            device = Device(
                serial=f"IDLE_{i}",
                brand="Google",
                status=DeviceStatus.IDLE,
                pool_id=pool.id,
            )
            test_db.add(device)

        busy_device = Device(
            serial="BUSY_001",
            brand="Google",
            status=DeviceStatus.BUSY,
            pool_id=pool.id,
        )
        test_db.add(busy_device)

        offline_device = Device(
            serial="OFFLINE_001",
            brand="Google",
            status=DeviceStatus.OFFLINE,
            pool_id=pool.id,
        )
        test_db.add(offline_device)

        test_db.commit()
        return pool

    def test_get_pool_capacity(self, pool_service, pool_with_devices):
        """测试获取池容量信息。"""
        capacity = pool_service.get_pool_capacity(pool_with_devices.id)

        assert capacity["total"] == 5
        assert capacity["available"] == 3  # IDLE 设备数
        assert capacity["busy"] == 1
        assert capacity["offline"] == 1
        assert capacity["max_parallel"] == 3
        assert capacity["reserved"] == 1  # 5 * 0.2 = 1
        assert capacity["usable"] == 2  # available - reserved = 3 - 1 = 2

    def test_get_pool_capacity_empty_pool(self, pool_service, test_db):
        """测试空池的容量计算。"""
        pool = pool_service.create_pool(
            name="empty_pool",
            purpose=PoolPurpose.STRESS,
            reserved_ratio=0.3,
            max_parallel=5,
        )
        test_db.commit()

        capacity = pool_service.get_pool_capacity(pool.id)

        assert capacity["total"] == 0
        assert capacity["available"] == 0
        assert capacity["busy"] == 0
        assert capacity["offline"] == 0
        assert capacity["max_parallel"] == 5
        assert capacity["reserved"] == 0
        assert capacity["usable"] == 0

    def test_get_pool_capacity_not_found(self, pool_service):
        """测试获取不存在的池容量返回 None。"""
        result = pool_service.get_pool_capacity(99999)
        assert result is None

    def test_get_pool_capacity_with_quarantined(self, pool_service, test_db):
        """测试隔离设备的容量计算。"""
        pool = pool_service.create_pool(name="quarantine_pool", purpose=PoolPurpose.STABLE)

        idle_device = Device(
            serial="IDLE_001",
            brand="Google",
            status=DeviceStatus.IDLE,
            pool_id=pool.id,
        )
        test_db.add(idle_device)

        quarantined_device = Device(
            serial="QUARANTINE_001",
            brand="Google",
            status=DeviceStatus.QUARANTINED,
            pool_id=pool.id,
        )
        test_db.add(quarantined_device)
        test_db.commit()

        capacity = pool_service.get_pool_capacity(pool.id)

        assert capacity["total"] == 2
        assert capacity["available"] == 1
        assert capacity["quarantined"] == 1


class TestPoolServiceTagMatching:
    """测试标签匹配功能。"""

    @pytest.fixture
    def pool_with_tagged_devices(self, pool_service, test_db):
        """创建带有标签设备的池。"""
        selector = {"brand": "Google", "min_version": "14"}
        pool = pool_service.create_pool(
            name="tag_match_pool",
            purpose=PoolPurpose.STABLE,
            tag_selector=selector,
        )

        # 创建匹配的设备
        match_device1 = Device(
            serial="MATCH_001",
            brand="Google",
            model="Pixel",
            system_version="14",
            status=DeviceStatus.IDLE,
            pool_id=pool.id,
        )
        match_device1.set_tags(["flagship", "5G"])
        test_db.add(match_device1)

        match_device2 = Device(
            serial="MATCH_002",
            brand="Google",
            model="Pixel 8",
            system_version="15",
            status=DeviceStatus.IDLE,
            pool_id=pool.id,
        )
        test_db.add(match_device2)

        # 创建不匹配的设备
        nomatch_device = Device(
            serial="NOMATCH_001",
            brand="Samsung",
            model="Galaxy",
            system_version="14",
            status=DeviceStatus.IDLE,
            pool_id=pool.id,
        )
        test_db.add(nomatch_device)

        test_db.commit()
        return pool

    def test_match_devices_for_pool(self, pool_service, pool_with_tagged_devices):
        """测试匹配池的设备。"""
        matched = pool_service.match_devices_for_pool(pool_with_tagged_devices.id)

        # 应该返回 2 个匹配品牌为 Google 的设备
        assert len(matched) == 2
        for device in matched:
            assert device.brand == "Google"

    def test_match_devices_empty_selector(self, pool_service, test_db):
        """测试空选择器匹配所有设备。"""
        pool = pool_service.create_pool(
            name="empty_selector_pool",
            purpose=PoolPurpose.STABLE,
            tag_selector=None,
        )

        device1 = Device(
            serial="DEV_001",
            brand="Google",
            status=DeviceStatus.IDLE,
            pool_id=pool.id,
        )
        test_db.add(device1)

        device2 = Device(
            serial="DEV_002",
            brand="Samsung",
            status=DeviceStatus.IDLE,
            pool_id=pool.id,
        )
        test_db.add(device2)
        test_db.commit()

        matched = pool_service.match_devices_for_pool(pool.id)

        assert len(matched) == 2

    def test_match_devices_not_found(self, pool_service):
        """测试不存在的池返回空列表。"""
        result = pool_service.match_devices_for_pool(99999)
        assert result == []


class TestPoolServiceDefaultPools:
    """测试默认池创建功能。"""

    def test_create_default_pools(self, pool_service, test_db):
        """测试创建默认池。"""
        pools = pool_service.create_default_pools()

        assert len(pools) == 3

        pool_names = {p.name: p for p in pools}

        # 检查 stable_pool
        assert "stable_pool" in pool_names
        stable = pool_names["stable_pool"]
        assert stable.purpose == PoolPurpose.STABLE
        assert stable.reserved_ratio == 0.1
        assert stable.max_parallel == 5
        assert stable.enabled is True

        # 检查 stress_pool
        assert "stress_pool" in pool_names
        stress = pool_names["stress_pool"]
        assert stress.purpose == PoolPurpose.STRESS
        assert stress.reserved_ratio == 0.2
        assert stress.max_parallel == 5
        assert stress.enabled is True

        # 检查 emergency_pool
        assert "emergency_pool" in pool_names
        emergency = pool_names["emergency_pool"]
        assert emergency.purpose == PoolPurpose.EMERGENCY
        assert emergency.reserved_ratio == 0.5
        assert emergency.max_parallel == 5
        assert emergency.enabled is True

    def test_create_default_pools_idempotent(self, pool_service, test_db):
        """测试创建默认池是幂等的。"""
        # 第一次创建
        pools1 = pool_service.create_default_pools()
        assert len(pools1) == 3

        # 第二次创建应该返回已存在的池，而不是创建新的
        pools2 = pool_service.create_default_pools()
        assert len(pools2) == 3

        # 两次返回的池应该是相同的（相同的 ID）
        ids1 = {p.id for p in pools1}
        ids2 = {p.id for p in pools2}
        assert ids1 == ids2

        # 数据库中应该只有 3 个池
        all_pools = test_db.query(DevicePool).all()
        assert len(all_pools) == 3

    def test_create_default_pools_with_existing_partial(self, pool_service, test_db):
        """测试部分默认池已存在时的创建。"""
        # 先创建一个默认池
        pool_service.create_pool(name="stable_pool", purpose=PoolPurpose.STABLE, reserved_ratio=0.1)

        # 创建默认池
        pools = pool_service.create_default_pools()

        assert len(pools) == 3

        # 应该包含已存在的 stable_pool
        stable_pool = pool_service.get_pool_by_name("stable_pool")
        assert stable_pool is not None
        assert stable_pool.reserved_ratio == 0.1
