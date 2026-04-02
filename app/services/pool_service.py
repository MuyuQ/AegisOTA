"""设备池管理业务逻辑。"""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.device import Device, DevicePool, DeviceStatus
from app.models.enums import PoolPurpose


class PoolService:
    """设备池管理服务。"""

    def __init__(self, db: Session):
        self.db = db

    def create_pool(
        self,
        name: str,
        purpose: PoolPurpose,
        reserved_ratio: float = 0.2,
        max_parallel: int = 5,
        tag_selector: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ) -> DevicePool:
        """创建设备池。

        Args:
            name: 池名称
            purpose: 池用途
            reserved_ratio: 预留比例 (0.0-1.0)
            max_parallel: 最大并行设备数
            tag_selector: 标签选择器配置
            enabled: 是否启用

        Returns:
            创建的 DevicePool 对象

        Raises:
            ValueError: 如果池名称已存在
        """
        # 检查名称是否重复
        existing = self.get_pool_by_name(name)
        if existing:
            raise ValueError(f"Pool with name '{name}' already exists")

        pool = DevicePool(
            name=name,
            purpose=purpose,
            reserved_ratio=reserved_ratio,
            max_parallel=max_parallel,
            enabled=enabled,
        )

        if tag_selector:
            pool.set_tag_selector(tag_selector)

        self.db.add(pool)
        self.db.commit()
        self.db.refresh(pool)

        return pool

    def get_pool_by_id(self, pool_id: int) -> Optional[DevicePool]:
        """通过 ID 获取设备池。

        Args:
            pool_id: 池 ID

        Returns:
            DevicePool 对象，如果不存在则返回 None
        """
        return self.db.query(DevicePool).filter_by(id=pool_id).first()

    def get_pool_by_name(self, name: str) -> Optional[DevicePool]:
        """通过名称获取设备池。

        Args:
            name: 池名称

        Returns:
            DevicePool 对象，如果不存在则返回 None
        """
        return self.db.query(DevicePool).filter_by(name=name).first()

    def list_pools(
        self,
        purpose: Optional[PoolPurpose] = None,
        enabled_only: bool = False,
    ) -> List[DevicePool]:
        """列出设备池。

        Args:
            purpose: 按用途筛选
            enabled_only: 是否只返回启用的池

        Returns:
            DevicePool 列表
        """
        query = self.db.query(DevicePool)

        if purpose:
            query = query.filter(DevicePool.purpose == purpose)

        if enabled_only:
            query = query.filter(DevicePool.enabled.is_(True))

        return query.all()

    def update_pool(
        self,
        pool_id: int,
        reserved_ratio: Optional[float] = None,
        max_parallel: Optional[int] = None,
        tag_selector: Optional[Dict[str, Any]] = None,
        enabled: Optional[bool] = None,
    ) -> Optional[DevicePool]:
        """更新设备池配置。

        Args:
            pool_id: 池 ID
            reserved_ratio: 预留比例
            max_parallel: 最大并行设备数
            tag_selector: 标签选择器配置
            enabled: 是否启用

        Returns:
            更新后的 DevicePool 对象，如果不存在则返回 None
        """
        pool = self.get_pool_by_id(pool_id)
        if not pool:
            return None

        if reserved_ratio is not None:
            pool.reserved_ratio = reserved_ratio

        if max_parallel is not None:
            pool.max_parallel = max_parallel

        if tag_selector is not None:
            pool.set_tag_selector(tag_selector)

        if enabled is not None:
            pool.enabled = enabled

        self.db.commit()
        self.db.refresh(pool)

        return pool

    def delete_pool(self, pool_id: int) -> bool:
        """删除设备池。

        Args:
            pool_id: 池 ID

        Returns:
            如果删除成功返回 True，如果池不存在返回 False
        """
        pool = self.get_pool_by_id(pool_id)
        if not pool:
            return False

        # 将池中设备的 pool_id 设置为 None
        for device in pool.devices:
            device.pool_id = None

        self.db.delete(pool)
        self.db.commit()

        return True

    def assign_device_to_pool(self, device_id: int, pool_id: int) -> Optional[Device]:
        """将设备分配到设备池。

        Args:
            device_id: 设备 ID
            pool_id: 池 ID

        Returns:
            更新后的 Device 对象，如果设备或池不存在则返回 None
        """
        device = self.db.query(Device).filter_by(id=device_id).first()
        if not device:
            return None

        pool = self.get_pool_by_id(pool_id)
        if not pool:
            return None

        device.pool_id = pool_id
        self.db.commit()
        self.db.refresh(device)

        return device

    def remove_device_from_pool(self, device_id: int) -> Optional[Device]:
        """从设备池移除设备。

        Args:
            device_id: 设备 ID

        Returns:
            更新后的 Device 对象，如果设备不在池中则返回 None
        """
        device = self.db.query(Device).filter_by(id=device_id).first()
        if not device or device.pool_id is None:
            return None

        device.pool_id = None
        self.db.commit()
        self.db.refresh(device)

        return device

    def get_pool_capacity(self, pool_id: int) -> Optional[Dict[str, int]]:
        """获取设备池容量信息。

        Args:
            pool_id: 池 ID

        Returns:
            容量信息字典，如果池不存在则返回 None
            包含：total, available, busy, offline, quarantined, max_parallel, reserved, usable
        """
        pool = self.get_pool_by_id(pool_id)
        if not pool:
            return None

        devices = pool.devices
        total = len(devices)

        # 统计各种状态的设备数
        available = 0
        busy = 0
        offline = 0
        quarantined = 0

        for device in devices:
            if device.status == DeviceStatus.IDLE:
                available += 1
            elif device.status == DeviceStatus.BUSY:
                busy += 1
            elif device.status == DeviceStatus.OFFLINE:
                offline += 1
            elif device.status == DeviceStatus.QUARANTINED:
                quarantined += 1

        # 计算预留设备数
        reserved = int(total * pool.reserved_ratio)

        # 可用设备数 = 空闲设备数 - 预留设备数
        usable = max(0, available - reserved)

        return {
            "total": total,
            "available": available,
            "busy": busy,
            "offline": offline,
            "quarantined": quarantined,
            "max_parallel": pool.max_parallel,
            "reserved": reserved,
            "usable": usable,
        }

    def match_devices_for_pool(self, pool_id: int) -> List[Device]:
        """获取符合池标签选择器的设备列表。

        Args:
            pool_id: 池 ID

        Returns:
            匹配的设备列表
        """
        pool = self.get_pool_by_id(pool_id)
        if not pool:
            return []

        selector = pool.get_tag_selector()
        devices = pool.devices

        # 如果没有选择器，返回所有设备
        if not selector:
            return devices

        matched = []
        for device in devices:
            if self._device_matches_selector(device, selector):
                matched.append(device)

        return matched

    def _device_matches_selector(
        self,
        device: Device,
        selector: Dict[str, Any],
    ) -> bool:
        """检查设备是否匹配选择器。

        Args:
            device: 设备对象
            selector: 选择器配置

        Returns:
            如果匹配返回 True
        """
        for key, value in selector.items():
            if key == "brand":
                if device.brand != value:
                    return False
            elif key == "model":
                if device.model != value:
                    return False
            elif key == "min_version":
                if not device.system_version:
                    return False
                try:
                    if float(device.system_version) < float(value):
                        return False
                except (ValueError, TypeError):
                    # 版本号无法比较时跳过
                    pass
            elif key == "tags":
                device_tags = device.get_tags()
                if not any(tag in device_tags for tag in value):
                    return False

        return True

    def create_default_pools(self) -> List[DevicePool]:
        """创建默认设备池。

        创建三个默认池：
        - stable_pool: 稳定测试池，预留比例 0.1
        - stress_pool: 压力测试池，预留比例 0.2
        - emergency_pool: 应急池，预留比例 0.5

        Returns:
            默认池列表（如果已存在则返回现有的）
        """
        default_pools = [
            {
                "name": "stable_pool",
                "purpose": PoolPurpose.STABLE,
                "reserved_ratio": 0.1,
            },
            {
                "name": "stress_pool",
                "purpose": PoolPurpose.STRESS,
                "reserved_ratio": 0.2,
            },
            {
                "name": "emergency_pool",
                "purpose": PoolPurpose.EMERGENCY,
                "reserved_ratio": 0.5,
            },
        ]

        pools = []
        for config in default_pools:
            # 检查是否已存在
            existing = self.get_pool_by_name(config["name"])
            if existing:
                pools.append(existing)
            else:
                pool = self.create_pool(
                    name=config["name"],
                    purpose=config["purpose"],
                    reserved_ratio=config["reserved_ratio"],
                    max_parallel=5,
                    enabled=True,
                )
                pools.append(pool)

        return pools
