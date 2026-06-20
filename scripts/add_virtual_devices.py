"""添加虚拟设备到数据库用于测试。"""

import sys

sys.path.insert(0, "e:\\Git_Repositories\\AegisOTA")

from datetime import datetime, timezone

from app.database import SessionLocal, init_db
from app.models.device import Device, DevicePool
from app.models.enums import DeviceStatus, PoolPurpose

# 初始化数据库
init_db()

db = SessionLocal()

try:
    # 先创建默认设备池
    pools_data = [
        {"name": "stable", "purpose": PoolPurpose.STABLE, "reserved_ratio": 0.2},
        {"name": "stress", "purpose": PoolPurpose.STRESS, "reserved_ratio": 0.1},
        {"name": "emergency", "purpose": PoolPurpose.EMERGENCY, "reserved_ratio": 0.3},
    ]

    pools = {}
    for pool_data in pools_data:
        pool = db.query(DevicePool).filter(DevicePool.name == pool_data["name"]).first()
        if not pool:
            pool = DevicePool(**pool_data)
            db.add(pool)
            db.flush()
            print(f"✓ 创建设备池: {pool.name}")
        pools[pool_data["name"]] = pool

    db.commit()

    # 虚拟设备数据
    virtual_devices = [
        {
            "serial": "TEST001",
            "brand": "Xiaomi",
            "model": "Mi 14",
            "system_version": "Android 14",
            "build_fingerprint": (
                "Xiaomi/mi14/mi14:14/UKQ1.231003.002/V816.0.5.0.UNCCNXM:user/release-keys"
            ),
            "status": DeviceStatus.IDLE,
            "health_score": 95,
            "battery_level": 85,
            "pool_id": pools["stable"].id,
            "location": "Lab-A1",
            "tags": '["wifi", "5g"]',
            "last_seen_at": datetime.now(timezone.utc),
        },
        {
            "serial": "TEST002",
            "brand": "Xiaomi",
            "model": "Mi 14 Pro",
            "system_version": "Android 14",
            "build_fingerprint": (
                "Xiaomi/mi14pro/mi14pro:14/UKQ1.231003.002/V816.0.5.0.UNCCNXM:user/release-keys"
            ),
            "status": DeviceStatus.IDLE,
            "health_score": 92,
            "battery_level": 78,
            "pool_id": pools["stable"].id,
            "location": "Lab-A2",
            "tags": '["wifi", "5g"]',
            "last_seen_at": datetime.now(timezone.utc),
        },
        {
            "serial": "TEST003",
            "brand": "Huawei",
            "model": "Mate 60",
            "system_version": "HarmonyOS 4.0",
            "build_fingerprint": (
                "HUAWEI/ALN-AL00/HWALN:4.0.0/HUAWEIALN-AL00/102.0.0.168:user/release-keys"
            ),
            "status": DeviceStatus.BUSY,
            "health_score": 88,
            "battery_level": 65,
            "pool_id": pools["stress"].id,
            "location": "Lab-B1",
            "tags": '["wifi", "stress-test"]',
            "last_seen_at": datetime.now(timezone.utc),
        },
        {
            "serial": "TEST004",
            "brand": "Huawei",
            "model": "Mate 60 Pro",
            "system_version": "HarmonyOS 4.0",
            "build_fingerprint": (
                "HUAWEI/ALN-AL10/HWALN:4.0.0/HUAWEIALN-AL10/102.0.0.168:user/release-keys"
            ),
            "status": DeviceStatus.IDLE,
            "health_score": 90,
            "battery_level": 92,
            "pool_id": pools["stress"].id,
            "location": "Lab-B2",
            "tags": '["wifi", "stress-test"]',
            "last_seen_at": datetime.now(timezone.utc),
        },
        {
            "serial": "TEST005",
            "brand": "OPPO",
            "model": "Find X7",
            "system_version": "Android 14",
            "build_fingerprint": (
                "OPPO/PHEM00/OP4E6F:14/UKQ1.231003.002/V14.0.0.168:user/release-keys"
            ),
            "status": DeviceStatus.QUARANTINED,
            "health_score": 45,
            "battery_level": 30,
            "pool_id": None,
            "location": "Lab-C1",
            "tags": '["wifi", "quarantined"]',
            "last_seen_at": datetime.now(timezone.utc),
            "quarantine_reason": "Boot failure detected",
        },
        {
            "serial": "TEST006",
            "brand": "vivo",
            "model": "X100",
            "system_version": "Android 14",
            "build_fingerprint": (
                "vivo/PD2317/PD2317:14/UP1A.231005.007/V14.0.16.0.W10:user/release-keys"
            ),
            "status": DeviceStatus.IDLE,
            "health_score": 98,
            "battery_level": 100,
            "pool_id": pools["emergency"].id,
            "location": "Lab-D1",
            "tags": '["wifi", "emergency"]',
            "last_seen_at": datetime.now(timezone.utc),
        },
        {
            "serial": "TEST007",
            "brand": "Samsung",
            "model": "Galaxy S24",
            "system_version": "Android 14",
            "build_fingerprint": (
                "samsung/e1qzhx/e1q:14/UP1A.231005.007/S9210ZHU1AWM3:user/release-keys"
            ),
            "status": DeviceStatus.OFFLINE,
            "health_score": 100,
            "battery_level": None,
            "pool_id": pools["stable"].id,
            "location": "Lab-A3",
            "tags": '["wifi"]',
            "last_seen_at": None,
        },
        {
            "serial": "TEST008",
            "brand": "OnePlus",
            "model": "12",
            "system_version": "Android 14",
            "build_fingerprint": (
                "OnePlus/PJD110/OP5D35L1:14/UKQ1.231003.002/V14.0.0.168:user/release-keys"
            ),
            "status": DeviceStatus.IDLE,
            "health_score": 94,
            "battery_level": 88,
            "pool_id": pools["stable"].id,
            "location": "Lab-A4",
            "tags": '["wifi", "5g"]',
            "last_seen_at": datetime.now(timezone.utc),
        },
    ]

    # 添加设备
    for device_data in virtual_devices:
        existing = db.query(Device).filter(Device.serial == device_data["serial"]).first()
        if existing:
            print(f"✗ 设备已存在: {device_data['serial']}")
            continue

        device = Device(**device_data)
        db.add(device)
        print(
            f"✓ 添加设备: {device.serial} ({device.brand} {device.model}) - {device.status.value}"
        )

    db.commit()
    print("\n✓ 虚拟设备添加完成！")

    # 统计
    total = db.query(Device).count()
    idle = db.query(Device).filter(Device.status == DeviceStatus.IDLE).count()
    busy = db.query(Device).filter(Device.status == DeviceStatus.BUSY).count()
    offline = db.query(Device).filter(Device.status == DeviceStatus.OFFLINE).count()
    quarantined = db.query(Device).filter(Device.status == DeviceStatus.QUARANTINED).count()

    print("\n设备统计:")
    print(f"  总计: {total}")
    print(f"  空闲: {idle}")
    print(f"  忙碌: {busy}")
    print(f"  离线: {offline}")
    print(f"  隔离: {quarantined}")

except Exception as e:
    db.rollback()
    print(f"✗ 错误: {e}")
    import traceback

    traceback.print_exc()
finally:
    db.close()
