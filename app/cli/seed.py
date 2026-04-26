"""数据库种子命令 -- 写入示例设备和升级计划。"""

# fmt: off
# ruff: noqa: E501  -- 种子数据为单行 dict 记录，保持紧凑格式

import typer
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.device import Device, DeviceStatus
from app.models.run import UpgradePlan, UpgradeType

app = typer.Typer(help="数据库种子数据管理")


SAMPLE_DEVICES = [
    # 1楼106机房 第1列 - Magic 系列
    dict(serial="HNR000000001", brand="Honor", model="Magic6 Pro", system_version="MagicOS 8.0.0.115", status=DeviceStatus.IDLE, battery_level=95, health_score=98, location="1楼106机房第1列"),
    dict(serial="HNR000000002", brand="Honor", model="Magic6", system_version="MagicOS 8.0.0.115", status=DeviceStatus.IDLE, battery_level=88, health_score=95, location="1楼106机房第1列"),
    dict(serial="HNR000000003", brand="Honor", model="Magic5 Pro", system_version="MagicOS 8.0.0.112", status=DeviceStatus.IDLE, battery_level=82, health_score=92, location="1楼106机房第1列"),
    dict(serial="HNR000000004", brand="Honor", model="Magic5", system_version="MagicOS 8.0.0.112", status=DeviceStatus.BUSY, battery_level=65, health_score=88, location="1楼106机房第1列"),
    dict(serial="HNR000000005", brand="Honor", model="Magic4 Pro", system_version="MagicOS 7.2.0.135", status=DeviceStatus.IDLE, battery_level=78, health_score=85, location="1楼106机房第1列"),
    # 1楼106机房 第2列 - 数字系列
    dict(serial="HNR000000006", brand="Honor", model="100 Pro", system_version="MagicOS 8.0.0.108", status=DeviceStatus.IDLE, battery_level=92, health_score=96, location="1楼106机房第2列"),
    dict(serial="HNR000000007", brand="Honor", model="100", system_version="MagicOS 8.0.0.108", status=DeviceStatus.IDLE, battery_level=85, health_score=94, location="1楼106机房第2列"),
    dict(serial="HNR000000008", brand="Honor", model="90 Pro", system_version="MagicOS 7.2.0.132", status=DeviceStatus.OFFLINE, battery_level=25, health_score=72, location="1楼106机房第2列"),
    dict(serial="HNR000000009", brand="Honor", model="90", system_version="MagicOS 7.2.0.132", status=DeviceStatus.IDLE, battery_level=70, health_score=90, location="1楼106机房第2列"),
    dict(serial="HNR000000010", brand="Honor", model="80 Pro", system_version="MagicOS 7.1.0.168", status=DeviceStatus.IDLE, battery_level=75, health_score=87, location="1楼106机房第2列"),
    # 1楼106机房 第3列 - X系列和折叠屏
    dict(serial="HNR000000011", brand="Honor", model="Magic V2", system_version="MagicOS 8.0.0.120", status=DeviceStatus.IDLE, battery_level=88, health_score=95, location="1楼106机房第3列"),
    dict(serial="HNR000000012", brand="Honor", model="Magic V Flip", system_version="MagicOS 8.0.0.105", status=DeviceStatus.IDLE, battery_level=72, health_score=91, location="1楼106机房第3列"),
    dict(serial="HNR000000013", brand="Honor", model="X50 Pro", system_version="MagicOS 8.0.0.102", status=DeviceStatus.IDLE, battery_level=90, health_score=93, location="1楼106机房第3列"),
    dict(serial="HNR000000014", brand="Honor", model="X50", system_version="MagicOS 8.0.0.102", status=DeviceStatus.BUSY, battery_level=55, health_score=86, location="1楼106机房第3列"),
    dict(serial="HNR000000015", brand="Honor", model="X9b", system_version="MagicOS 7.2.0.128", status=DeviceStatus.IDLE, battery_level=80, health_score=89, location="1楼106机房第3列"),
    # 2楼205机房 第1列 - Magic 系列
    dict(serial="HNR000000016", brand="Honor", model="Magic6 Pro", system_version="MagicOS 8.0.0.115", status=DeviceStatus.IDLE, battery_level=92, health_score=97, location="2楼205机房第1列"),
    dict(serial="HNR000000017", brand="Honor", model="Magic6", system_version="MagicOS 8.0.0.115", status=DeviceStatus.IDLE, battery_level=88, health_score=95, location="2楼205机房第1列"),
    dict(serial="HNR000000018", brand="Honor", model="Magic5 Pro", system_version="MagicOS 8.0.0.112", status=DeviceStatus.QUARANTINED, battery_level=40, health_score=55, location="2楼205机房第1列"),
    dict(serial="HNR000000019", brand="Honor", model="Magic5", system_version="MagicOS 8.0.0.112", status=DeviceStatus.IDLE, battery_level=75, health_score=90, location="2楼205机房第1列"),
    dict(serial="HNR000000020", brand="Honor", model="Magic4", system_version="MagicOS 7.2.0.135", status=DeviceStatus.IDLE, battery_level=68, health_score=82, location="2楼205机房第1列"),
    # 2楼205机房 第2列 - Pad平板系列
    dict(serial="HNR000000021", brand="Honor", model="MagicPad 13", system_version="MagicOS 8.0.0.110", status=DeviceStatus.IDLE, battery_level=95, health_score=98, location="2楼205机房第2列"),
    dict(serial="HNR000000022", brand="Honor", model="Pad 9", system_version="MagicOS 8.0.0.100", status=DeviceStatus.IDLE, battery_level=88, health_score=94, location="2楼205机房第2列"),
    dict(serial="HNR000000023", brand="Honor", model="Pad 8 Pro", system_version="MagicOS 7.2.0.125", status=DeviceStatus.IDLE, battery_level=82, health_score=91, location="2楼205机房第2列"),
    dict(serial="HNR000000024", brand="Honor", model="Pad X9", system_version="MagicOS 7.2.0.118", status=DeviceStatus.IDLE, battery_level=78, health_score=88, location="2楼205机房第2列"),
    dict(serial="HNR000000025", brand="Honor", model="MagicPad 2", system_version="MagicOS 8.0.0.108", status=DeviceStatus.OFFLINE, battery_level=15, health_score=80, location="2楼205机房第2列"),
    # 2楼205机房 第3列 - 数字系列
    dict(serial="HNR000000026", brand="Honor", model="100 Pro", system_version="MagicOS 8.0.0.108", status=DeviceStatus.IDLE, battery_level=90, health_score=95, location="2楼205机房第3列"),
    dict(serial="HNR000000027", brand="Honor", model="90 Pro", system_version="MagicOS 7.2.0.132", status=DeviceStatus.IDLE, battery_level=85, health_score=92, location="2楼205机房第3列"),
    dict(serial="HNR000000028", brand="Honor", model="80", system_version="MagicOS 7.1.0.168", status=DeviceStatus.IDLE, battery_level=72, health_score=86, location="2楼205机房第3列"),
]

SAMPLE_PLANS = [
    dict(name="MagicOS 9.0 全量升级", upgrade_type=UpgradeType.FULL, package_path="ota_packages/full/MagicOS_9.0.0.100_full.zip", target_build="HONOR.MGC.9.0.0.100"),
    dict(name="MagicOS 9.0 增量升级 (8.0→9.0)", upgrade_type=UpgradeType.INCREMENTAL, package_path="ota_packages/incremental/MagicOS_9.0.0.100_inc.zip", source_build="HONOR.MGC.8.0.0.115", target_build="HONOR.MGC.9.0.0.100"),
    dict(name="MagicOS 8.0 → 8.1 小版本升级", upgrade_type=UpgradeType.INCREMENTAL, package_path="ota_packages/incremental/MagicOS_8.1.0.120_inc.zip", source_build="HONOR.MGC.8.0.0.115", target_build="HONOR.MGC.8.1.0.120"),
    dict(name="MagicOS 9.0 版本回滚", upgrade_type=UpgradeType.ROLLBACK, package_path="ota_packages/full/MagicOS_8.0.0.115_rollback.zip", target_build="HONOR.MGC.8.0.0.115"),
    dict(name="MagicOS 9.0 折叠屏专属升级", upgrade_type=UpgradeType.FULL, package_path="ota_packages/full/MagicOS_9.0.0.100_fold.zip", target_build="HONOR.MGC.9.0.0.100"),
    dict(name="MagicOS 9.0 平板专属升级", upgrade_type=UpgradeType.FULL, package_path="ota_packages/full/MagicOS_9.0.0.100_pad.zip", target_build="HONOR.MGC.9.0.0.100"),
]


@app.command("seed")
def seed_db(
    devices: bool = typer.Option(True, "--devices", help="写入示例设备"),
    plans: bool = typer.Option(True, "--plans", help="写入示例升级计划"),
):
    """向数据库写入示例数据（仅开发环境使用）。

    默认同时写入示例设备和升级计划，可通过 --no-devices / --no-plans 关闭。
    """
    db: Session = SessionLocal()
    try:
        if devices and db.query(Device).count() == 0:
            for d in SAMPLE_DEVICES:
                db.add(Device(**d))
            db.commit()
            typer.echo(f"已写入 {len(SAMPLE_DEVICES)} 台示例设备")
        elif devices:
            typer.echo("设备数据已存在，跳过")

        if plans and db.query(UpgradePlan).count() == 0:
            for p in SAMPLE_PLANS:
                db.add(UpgradePlan(**p))
            db.commit()
            typer.echo(f"已写入 {len(SAMPLE_PLANS)} 个示例升级计划")
        elif plans:
            typer.echo("升级计划数据已存在，跳过")

    except Exception as e:
        db.rollback()
        typer.echo(f"种子数据写入失败: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()


@app.command("clear-seed")
def clear_seed(
    devices: bool = typer.Option(True, "--devices", help="清空示例设备"),
    plans: bool = typer.Option(True, "--plans", help="清空示例升级计划"),
):
    """清空种子数据。"""
    db: Session = SessionLocal()
    try:
        if devices:
            deleted = db.query(Device).delete()
            typer.echo(f"已删除 {deleted} 台设备")
        if plans:
            deleted = db.query(UpgradePlan).delete()
            typer.echo(f"已删除 {deleted} 个升级计划")
        db.commit()
    except Exception as e:
        db.rollback()
        typer.echo(f"清空失败: {e}", err=True)
        raise typer.Exit(1)
    finally:
        db.close()
