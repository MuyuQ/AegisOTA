"""状态转换验证测试。"""

import pytest

from app.models.enums import DeviceStatus, RunStatus
from app.validators.state_machine import (
    StateMachine,
    StateTransitionError,
    device_state_machine,
    get_device_allowed_transitions,
    get_run_allowed_transitions,
    is_device_terminal_state,
    is_run_terminal_state,
    run_state_machine,
    validate_device_transition,
    validate_run_transition,
)


class TestStateMachine:
    """状态机基类测试。"""

    def test_can_transition_valid(self):
        """测试合法的状态转换。"""
        sm = StateMachine(
            {
                "state_a": {"state_b", "state_c"},
                "state_b": {"state_a"},
            }
        )

        assert sm.can_transition("state_a", "state_b") is True
        assert sm.can_transition("state_a", "state_c") is True
        assert sm.can_transition("state_b", "state_a") is True

    def test_can_transition_invalid(self):
        """测试非法的状态转换。"""
        sm = StateMachine(
            {
                "state_a": {"state_b"},
                "state_b": {"state_a"},
            }
        )

        assert sm.can_transition("state_a", "state_a") is False
        assert sm.can_transition("state_b", "state_b") is False

    def test_can_transition_unknown_state(self):
        """测试未知状态的转换。"""
        sm = StateMachine(
            {
                "state_a": {"state_b"},
            }
        )

        assert sm.can_transition("unknown", "state_b") is False
        assert sm.can_transition("state_a", "unknown") is False

    def test_get_allowed_transitions(self):
        """测试获取允许的转换。"""
        sm = StateMachine(
            {
                "state_a": {"state_b", "state_c"},
            }
        )

        allowed = sm.get_allowed_transitions("state_a")
        assert allowed == {"state_b", "state_c"}

    def test_is_terminal_state(self):
        """测试终态判断。"""
        sm = StateMachine(
            {
                "state_a": {"state_b"},
                "state_b": set(),  # 终态
            }
        )

        assert sm.is_terminal_state("state_a") is False
        assert sm.is_terminal_state("state_b") is True
        assert sm.is_terminal_state("unknown") is True


class TestDeviceStateMachine:
    """设备状态机测试。"""

    def test_idle_can_transition_to(self):
        """测试 IDLE 状态可以转换到的状态。"""
        allowed = device_state_machine.get_allowed_transitions(DeviceStatus.IDLE.value)
        assert DeviceStatus.RESERVED.value in allowed
        assert DeviceStatus.BUSY.value in allowed
        assert DeviceStatus.OFFLINE.value in allowed
        assert DeviceStatus.QUARANTINED.value in allowed

    def test_busy_can_transition_to(self):
        """测试 BUSY 状态可以转换到的状态。"""
        allowed = device_state_machine.get_allowed_transitions(DeviceStatus.BUSY.value)
        assert DeviceStatus.IDLE.value in allowed
        assert DeviceStatus.OFFLINE.value in allowed
        assert DeviceStatus.QUARANTINED.value in allowed

    def test_quarantined_can_transition_to(self):
        """测试 QUARANTINED 状态可以转换到的状态。"""
        allowed = device_state_machine.get_allowed_transitions(DeviceStatus.QUARANTINED.value)
        assert DeviceStatus.RECOVERING.value in allowed
        assert DeviceStatus.OFFLINE.value in allowed

    def test_invalid_device_transition(self):
        """测试非法的设备状态转换。"""
        # BUSY 不能直接转换到 RESERVED
        assert (
            device_state_machine.can_transition(
                DeviceStatus.BUSY.value, DeviceStatus.RESERVED.value
            )
            is False
        )

        # OFFLINE 不能直接转换到 BUSY
        assert (
            device_state_machine.can_transition(DeviceStatus.OFFLINE.value, DeviceStatus.BUSY.value)
            is False
        )


class TestRunStateMachine:
    """任务状态机测试。"""

    def test_queued_can_transition_to(self):
        """测试 QUEUED 状态可以转换到的状态。"""
        allowed = run_state_machine.get_allowed_transitions(RunStatus.QUEUED.value)
        assert RunStatus.ALLOCATING.value in allowed
        assert RunStatus.RESERVED.value in allowed
        assert RunStatus.ABORTED.value in allowed

    def test_running_can_transition_to(self):
        """测试 RUNNING 状态可以转换到的状态。"""
        allowed = run_state_machine.get_allowed_transitions(RunStatus.RUNNING.value)
        assert RunStatus.VALIDATING.value in allowed
        assert RunStatus.FAILED.value in allowed
        assert RunStatus.ABORTED.value in allowed
        assert RunStatus.PREEMPTED.value in allowed

    def test_terminal_states(self):
        """测试终态。"""
        assert run_state_machine.is_terminal_state(RunStatus.PASSED.value) is True
        assert run_state_machine.is_terminal_state(RunStatus.FAILED.value) is True
        assert run_state_machine.is_terminal_state(RunStatus.ABORTED.value) is True
        assert run_state_machine.is_terminal_state(RunStatus.PREEMPTED.value) is True

    def test_non_terminal_states(self):
        """测试非终态。"""
        assert run_state_machine.is_terminal_state(RunStatus.QUEUED.value) is False
        assert run_state_machine.is_terminal_state(RunStatus.RUNNING.value) is False

    def test_invalid_run_transition(self):
        """测试非法的任务状态转换。"""
        # PASSED 不能转换到任何状态
        assert (
            run_state_machine.can_transition(RunStatus.PASSED.value, RunStatus.QUEUED.value)
            is False
        )

        # QUEUED 不能直接转换到 PASSED
        assert (
            run_state_machine.can_transition(RunStatus.QUEUED.value, RunStatus.PASSED.value)
            is False
        )


class TestValidateDeviceTransition:
    """设备状态转换验证函数测试。"""

    def test_validate_valid_transition(self):
        """测试验证合法转换不抛异常。"""
        # 不应抛出异常
        validate_device_transition(DeviceStatus.IDLE, DeviceStatus.BUSY)
        validate_device_transition(DeviceStatus.BUSY, DeviceStatus.IDLE)

    def test_validate_invalid_transition_raises(self):
        """测试验证非法转换抛出异常。"""
        with pytest.raises(StateTransitionError) as exc_info:
            validate_device_transition(
                DeviceStatus.BUSY,
                DeviceStatus.RESERVED,
                device_id=123,
            )

        assert "Device" in str(exc_info.value)
        assert "123" in str(exc_info.value)
        assert "busy" in str(exc_info.value)
        assert "reserved" in str(exc_info.value)

    def test_error_message_contains_allowed_states(self):
        """测试异常消息包含允许的状态列表。"""
        with pytest.raises(StateTransitionError) as exc_info:
            validate_device_transition(DeviceStatus.IDLE, DeviceStatus.RECOVERING)

        error_msg = str(exc_info.value)
        assert "idle" in error_msg
        assert "recovering" in error_msg


class TestValidateRunTransition:
    """任务状态转换验证函数测试。"""

    def test_validate_valid_transition(self):
        """测试验证合法转换不抛异常。"""
        validate_run_transition(RunStatus.QUEUED, RunStatus.RESERVED)
        validate_run_transition(RunStatus.RUNNING, RunStatus.VALIDATING)

    def test_validate_invalid_transition_raises(self):
        """测试验证非法转换抛出异常。"""
        with pytest.raises(StateTransitionError) as exc_info:
            validate_run_transition(
                RunStatus.QUEUED,
                RunStatus.PASSED,
                run_id=456,
            )

        assert "RunSession" in str(exc_info.value)
        assert "456" in str(exc_info.value)
        assert "queued" in str(exc_info.value)
        assert "passed" in str(exc_info.value)

    def test_validate_from_terminal_state_raises(self):
        """测试从终态转换抛出异常。"""
        with pytest.raises(StateTransitionError):
            validate_run_transition(RunStatus.PASSED, RunStatus.QUEUED)

        with pytest.raises(StateTransitionError):
            validate_run_transition(RunStatus.FAILED, RunStatus.RUNNING)


class TestHelperFunctions:
    """辅助函数测试。"""

    def test_is_run_terminal_state_true(self):
        """测试任务终态判断为真。"""
        assert is_run_terminal_state(RunStatus.PASSED) is True
        assert is_run_terminal_state(RunStatus.FAILED) is True
        assert is_run_terminal_state(RunStatus.ABORTED) is True
        assert is_run_terminal_state(RunStatus.PREEMPTED) is True

    def test_is_run_terminal_state_false(self):
        """测试任务终态判断为假。"""
        assert is_run_terminal_state(RunStatus.QUEUED) is False
        assert is_run_terminal_state(RunStatus.RUNNING) is False

    def test_get_run_allowed_transitions(self):
        """测试获取任务允许转换。"""
        allowed = get_run_allowed_transitions(RunStatus.RUNNING)
        assert RunStatus.VALIDATING in allowed
        assert RunStatus.FAILED in allowed
        assert RunStatus.ABORTED in allowed
        assert RunStatus.PREEMPTED in allowed

    def test_get_run_allowed_transitions_terminal(self):
        """测试终态没有允许转换。"""
        allowed = get_run_allowed_transitions(RunStatus.PASSED)
        assert len(allowed) == 0

    def test_get_device_allowed_transitions(self):
        """测试获取设备允许转换。"""
        allowed = get_device_allowed_transitions(DeviceStatus.IDLE)
        assert DeviceStatus.RESERVED in allowed
        assert DeviceStatus.BUSY in allowed
        assert DeviceStatus.OFFLINE in allowed
        assert DeviceStatus.QUARANTINED in allowed

    def test_is_device_terminal_state(self):
        """测试设备没有真正的终态。"""
        # 设备的所有状态都可以转换
        for status in DeviceStatus:
            # RECOVERING 不是终态
            if status == DeviceStatus.RECOVERING:
                assert is_device_terminal_state(status) is False
