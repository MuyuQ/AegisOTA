"""故障模型测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.device import Device
from app.models.fault import FaultProfile, FaultStage, FaultType
from app.models.run import RunSession, RunStatus, UpgradePlan, UpgradeType


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


class TestFaultStage:
    """FaultStage 枚举测试。"""

    def test_stage_values(self):
        """测试枚举值正确。"""
        assert FaultStage.PRECHECK == "precheck"
        assert FaultStage.APPLY_UPDATE == "apply_update"
        assert FaultStage.POST_VALIDATE == "post_validate"

    def test_stage_count(self):
        """测试枚举值数量。"""
        assert len(FaultStage) == 3

    def test_stage_is_string_enum(self):
        """测试枚举是字符串枚举。"""
        assert isinstance(FaultStage.PRECHECK.value, str)


class TestFaultType:
    """FaultType 枚举测试。"""

    def test_type_values(self):
        """测试枚举值正确。"""
        assert FaultType.STORAGE_PRESSURE == "storage_pressure"
        assert FaultType.DOWNLOAD_INTERRUPTED == "download_interrupted"
        assert FaultType.PACKAGE_CORRUPTED == "package_corrupted"
        assert FaultType.LOW_BATTERY == "low_battery"
        assert FaultType.REBOOT_INTERRUPTED == "reboot_interrupted"
        assert FaultType.POST_BOOT_WATCHDOG_FAILURE == "post_boot_watchdog_failure"
        assert FaultType.MONKEY_AFTER_UPGRADE == "monkey_after_upgrade"
        assert FaultType.PERFORMANCE_REGRESSION == "performance_regression"

    def test_type_count(self):
        """测试枚举值数量。"""
        assert len(FaultType) == 8

    def test_type_is_string_enum(self):
        """测试枚举是字符串枚举。"""
        assert isinstance(FaultType.STORAGE_PRESSURE.value, str)


class TestFaultProfileCreation:
    """FaultProfile 创建测试。"""

    def test_create_profile_minimal(self, db_session):
        """测试创建最小故障配置。"""
        profile = FaultProfile(
            name="存储压力测试",
            fault_stage=FaultStage.PRECHECK,
            fault_type=FaultType.STORAGE_PRESSURE,
        )
        db_session.add(profile)
        db_session.commit()

        assert profile.id is not None
        assert profile.name == "存储压力测试"
        assert profile.fault_stage == FaultStage.PRECHECK
        assert profile.fault_type == FaultType.STORAGE_PRESSURE
        assert profile.enabled == True
        assert profile.created_at is not None
        assert profile.updated_at is not None

    def test_create_profile_full(self, db_session):
        """测试创建完整故障配置。"""
        profile = FaultProfile(
            name="下载中断测试",
            fault_stage=FaultStage.APPLY_UPDATE,
            fault_type=FaultType.DOWNLOAD_INTERRUPTED,
            enabled=False,
            description="模拟下载过程中的网络中断",
        )
        profile.set_parameters({
            "interrupt_at": "50%",
            "timeout_seconds": 30,
            "retry_count": 3,
        })
        db_session.add(profile)
        db_session.commit()

        assert profile.id is not None
        assert profile.fault_stage == FaultStage.APPLY_UPDATE
        assert profile.fault_type == FaultType.DOWNLOAD_INTERRUPTED
        assert profile.enabled == False
        assert profile.description == "模拟下载过程中的网络中断"
        assert profile.get_parameters() == {
            "interrupt_at": "50%",
            "timeout_seconds": 30,
            "retry_count": 3,
        }

    def test_profile_parameters_methods(self, db_session):
        """测试参数方法。"""
        profile = FaultProfile(
            name="参数测试",
            fault_stage=FaultStage.POST_VALIDATE,
            fault_type=FaultType.MONKEY_AFTER_UPGRADE,
        )

        # 测试空参数
        assert profile.get_parameters() == {}

        # 测试设置参数
        params = {
            "seed": 12345,
            "throttle": 500,
            "event_count": 10000,
        }
        profile.set_parameters(params)
        db_session.add(profile)
        db_session.commit()

        assert profile.get_parameters() == params

    def test_profile_parameters_empty(self, db_session):
        """测试空参数。"""
        profile = FaultProfile(
            name="空参数",
            fault_stage=FaultStage.PRECHECK,
            fault_type=FaultType.LOW_BATTERY,
        )
        profile.set_parameters({})
        db_session.add(profile)
        db_session.commit()

        assert profile.parameters is None
        assert profile.get_parameters() == {}


class TestFaultProfileUpgradePlanRelationship:
    """FaultProfile 与 UpgradePlan 关联测试。"""

    def test_profile_plan_relationship(self, db_session):
        """测试故障配置与升级计划的关联。"""
        profile = FaultProfile(
            name="关联测试",
            fault_stage=FaultStage.PRECHECK,
            fault_type=FaultType.STORAGE_PRESSURE,
        )
        db_session.add(profile)
        db_session.commit()

        plan = UpgradePlan(
            name="使用故障的计划",
            upgrade_type=UpgradeType.FULL,
            fault_profile_id=profile.id,
        )
        db_session.add(plan)
        db_session.commit()

        # 验证关系
        db_session.refresh(plan)
        assert plan.fault_profile is not None
        assert plan.fault_profile.name == "关联测试"

        db_session.refresh(profile)
        assert len(profile.upgrade_plans) == 1
        assert profile.upgrade_plans[0].name == "使用故障的计划"

    def test_profile_multiple_plans(self, db_session):
        """测试一个故障配置关联多个升级计划。"""
        profile = FaultProfile(
            name="多计划配置",
            fault_stage=FaultStage.APPLY_UPDATE,
            fault_type=FaultType.REBOOT_INTERRUPTED,
        )
        db_session.add(profile)
        db_session.commit()

        plan1 = UpgradePlan(
            name="计划一",
            upgrade_type=UpgradeType.FULL,
            fault_profile_id=profile.id,
        )
        plan2 = UpgradePlan(
            name="计划二",
            upgrade_type=UpgradeType.INCREMENTAL,
            fault_profile_id=profile.id,
        )
        db_session.add_all([plan1, plan2])
        db_session.commit()

        db_session.refresh(profile)
        assert len(profile.upgrade_plans) == 2

    def test_profile_fk_on_delete_set_null(self, db_session):
        """测试删除故障配置时升级计划的 FK 设为 NULL。"""
        profile = FaultProfile(
            name="待删除配置",
            fault_stage=FaultStage.PRECHECK,
            fault_type=FaultType.LOW_BATTERY,
        )
        db_session.add(profile)
        db_session.commit()

        plan = UpgradePlan(
            name="关联计划",
            upgrade_type=UpgradeType.FULL,
            fault_profile_id=profile.id,
        )
        db_session.add(plan)
        db_session.commit()

        profile_id = profile.id
        plan_id = plan.id

        # 删除故障配置
        db_session.delete(profile)
        db_session.commit()

        # 验证升级计划的 fault_profile_id 设为 NULL
        db_session.refresh(plan)
        assert plan.fault_profile_id is None
        assert plan.fault_profile is None


class TestAllFaultTypes:
    """所有故障类型创建测试。"""

    def test_create_all_fault_types(self, db_session):
        """测试创建所有故障类型的配置。"""
        fault_configs = [
            (FaultType.STORAGE_PRESSURE, FaultStage.PRECHECK, {"fill_percent": 90}),
            (FaultType.DOWNLOAD_INTERRUPTED, FaultStage.APPLY_UPDATE, {"interrupt_time": 30}),
            (FaultType.PACKAGE_CORRUPTED, FaultStage.PRECHECK, {"corrupt_type": "header"}),
            (FaultType.LOW_BATTERY, FaultStage.PRECHECK, {"min_level": 15}),
            (FaultType.REBOOT_INTERRUPTED, FaultStage.APPLY_UPDATE, {"timeout": 60}),
            (FaultType.POST_BOOT_WATCHDOG_FAILURE, FaultStage.POST_VALIDATE, {"check_interval": 5}),
            (FaultType.MONKEY_AFTER_UPGRADE, FaultStage.POST_VALIDATE, {"event_count": 5000}),
            (FaultType.PERFORMANCE_REGRESSION, FaultStage.POST_VALIDATE, {"metrics": ["cpu", "mem"]}),
        ]

        profiles = []
        for fault_type, stage, params in fault_configs:
            profile = FaultProfile(
                name=f"{fault_type.value}_test",
                fault_stage=stage,
                fault_type=fault_type,
            )
            profile.set_parameters(params)
            profiles.append(profile)

        db_session.add_all(profiles)
        db_session.commit()

        assert len(profiles) == 8
        for profile in profiles:
            assert profile.id is not None
            assert profile.get_parameters() != {}