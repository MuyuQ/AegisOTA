"""异常注入基类测试。"""

from app.faults.base import FaultPlugin, FaultResult


def test_fault_result_creation():
    """测试异常注入结果创建。"""
    result = FaultResult(
        success=True,
        fault_type="storage_pressure",
        message="存储压力注入成功",
        data={"fill_percent": 90},
    )

    assert result.success is True
    assert result.fault_type == "storage_pressure"


def test_fault_result_failure():
    """测试异常注入失败结果。"""
    result = FaultResult(
        success=False,
        fault_type="test",
        message="注入失败",
        error="Device not ready",
    )

    assert result.success is False
    assert result.error == "Device not ready"


def test_fault_plugin_abstract():
    """测试 FaultPlugin 是抽象类。"""
    from abc import ABC

    assert FaultPlugin.__bases__[0] is ABC


def test_fault_plugin_interface():
    """测试 FaultPlugin 接口方法。"""
    # 检查抽象方法（使用 inspect.getattr_static 更合适）
    abstract_methods = [
        name
        for name in dir(FaultPlugin)
        if getattr(getattr(FaultPlugin, name, None), "__isabstractmethod__", False)
    ]
    assert "inject" in abstract_methods


def test_fault_plugin_lifecycle():
    """测试异常插件生命周期。"""
    # 检查生命周期方法存在
    assert hasattr(FaultPlugin, "prepare")
    assert hasattr(FaultPlugin, "inject")
    assert hasattr(FaultPlugin, "cleanup")


def test_fault_plugin_metadata():
    """测试异常插件元数据。"""

    class TestFault(FaultPlugin):
        fault_type = "test_fault"
        fault_stage = "precheck"
        description = "测试异常"

        def inject(self, context):
            return FaultResult(success=True, fault_type=self.fault_type, message="OK")

    plugin = TestFault()
    assert plugin.fault_type == "test_fault"
    assert plugin.fault_stage == "precheck"
