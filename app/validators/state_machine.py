"""状态转换验证模块。

定义设备和任务的状态机，确保状态转换符合业务规则。
"""

from typing import Dict, Optional, Set

from app.models.enums import DeviceStatus, RunStatus


class StateMachine:
    """状态机基类。

    定义状态转换规则，验证状态变更是否合法。
    """

    def __init__(self, transitions: Dict[str, Set[str]]):
        """初始化状态机。

        Args:
            transitions: 状态转换映射，key 为当前状态，value 为允许的目标状态集合
        """
        self.transitions = transitions
        self._validate_transitions()

    def _validate_transitions(self) -> None:
        """验证转换定义的完整性。"""
        all_states = set(self.transitions.keys())
        for targets in self.transitions.values():
            for target in targets:
                if target not in all_states:
                    # 允许目标状态不在转换表中（如终态）
                    pass

    def can_transition(self, from_state: str, to_state: str) -> bool:
        """检查状态转换是否合法。

        Args:
            from_state: 当前状态
            to_state: 目标状态

        Returns:
            True 表示转换合法，False 表示非法
        """
        allowed = self.transitions.get(from_state, set())
        return to_state in allowed

    def get_allowed_transitions(self, from_state: str) -> Set[str]:
        """获取从指定状态可以转换到的所有状态。

        Args:
            from_state: 当前状态

        Returns:
            允许的目标状态集合
        """
        return self.transitions.get(from_state, set())

    def is_terminal_state(self, state: str) -> bool:
        """检查是否为终态。

        终态是没有允许转换的状态。

        Args:
            state: 要检查的状态

        Returns:
            True 表示是终态
        """
        return state not in self.transitions or not self.transitions[state]


# 设备状态转换定义
DEVICE_TRANSITIONS: Dict[str, Set[str]] = {
    DeviceStatus.IDLE.value: {
        DeviceStatus.RESERVED.value,  # 被任务占用
        DeviceStatus.BUSY.value,  # 直接开始执行
        DeviceStatus.OFFLINE.value,  # 设备离线
        DeviceStatus.QUARANTINED.value,  # 隔离
    },
    DeviceStatus.RESERVED.value: {
        DeviceStatus.BUSY.value,  # 任务开始执行
        DeviceStatus.IDLE.value,  # 任务取消/释放
        DeviceStatus.OFFLINE.value,  # 设备离线
    },
    DeviceStatus.BUSY.value: {
        DeviceStatus.IDLE.value,  # 任务完成
        DeviceStatus.OFFLINE.value,  # 设备离线
        DeviceStatus.QUARANTINED.value,  # 任务失败隔离
    },
    DeviceStatus.OFFLINE.value: {
        DeviceStatus.IDLE.value,  # 设备恢复在线
        DeviceStatus.QUARANTINED.value,  # 隔离
    },
    DeviceStatus.QUARANTINED.value: {
        DeviceStatus.RECOVERING.value,  # 开始恢复
        DeviceStatus.OFFLINE.value,  # 放弃恢复
    },
    DeviceStatus.RECOVERING.value: {
        DeviceStatus.IDLE.value,  # 恢复成功
        DeviceStatus.QUARANTINED.value,  # 恢复失败
    },
}

# 任务状态转换定义
RUN_TRANSITIONS: Dict[str, Set[str]] = {
    RunStatus.QUEUED.value: {
        RunStatus.ALLOCATING.value,  # 开始分配设备
        RunStatus.RESERVED.value,  # 直接分配设备
        RunStatus.ABORTED.value,  # 取消任务
    },
    RunStatus.ALLOCATING.value: {
        RunStatus.RESERVED.value,  # 设备分配成功
        RunStatus.QUEUED.value,  # 分配失败，重新排队
        RunStatus.ABORTED.value,  # 取消任务
    },
    RunStatus.RESERVED.value: {
        RunStatus.RUNNING.value,  # 开始执行
        RunStatus.QUEUED.value,  # 释放设备，重新排队
        RunStatus.ABORTED.value,  # 取消任务
        RunStatus.PREEMPTED.value,  # 被高优先级任务抢占
    },
    RunStatus.RUNNING.value: {
        RunStatus.VALIDATING.value,  # 执行完成，进入验证
        RunStatus.FAILED.value,  # 执行失败
        RunStatus.ABORTED.value,  # 用户终止
        RunStatus.PREEMPTED.value,  # 被高优先级任务抢占
    },
    RunStatus.VALIDATING.value: {
        RunStatus.PASSED.value,  # 验证通过
        RunStatus.FAILED.value,  # 验证失败
        RunStatus.ABORTED.value,  # 用户终止
    },
    RunStatus.PASSED.value: set(),  # 终态
    RunStatus.FAILED.value: set(),  # 终态
    RunStatus.ABORTED.value: set(),  # 终态
    RunStatus.PREEMPTED.value: set(),  # 终态
}

# 创建状态机实例
device_state_machine = StateMachine(DEVICE_TRANSITIONS)
run_state_machine = StateMachine(RUN_TRANSITIONS)


class StateTransitionError(Exception):
    """状态转换异常。

    当状态转换不合法时抛出。
    """

    def __init__(
        self,
        entity_type: str,
        entity_id: Optional[int],
        from_state: str,
        to_state: str,
        allowed_states: Set[str],
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.from_state = from_state
        self.to_state = to_state
        self.allowed_states = allowed_states

        message = (
            f"Invalid state transition for {entity_type}"
            f"{f' (id={entity_id})' if entity_id else ''}: "
            f"cannot transition from '{from_state}' to '{to_state}'. "
            f"Allowed states: "
            f"{sorted(allowed_states) if allowed_states else 'none (terminal state)'}"
        )
        super().__init__(message)


def validate_device_transition(
    from_status: DeviceStatus,
    to_status: DeviceStatus,
    device_id: Optional[int] = None,
) -> None:
    """验证设备状态转换。

    Args:
        from_status: 当前设备状态
        to_status: 目标设备状态
        device_id: 设备 ID（用于错误消息）

    Raises:
        StateTransitionError: 状态转换非法
    """
    if not device_state_machine.can_transition(from_status.value, to_status.value):
        allowed = device_state_machine.get_allowed_transitions(from_status.value)
        raise StateTransitionError(
            entity_type="Device",
            entity_id=device_id,
            from_state=from_status.value,
            to_state=to_status.value,
            allowed_states=allowed,
        )


def validate_run_transition(
    from_status: RunStatus,
    to_status: RunStatus,
    run_id: Optional[int] = None,
) -> None:
    """验证任务状态转换。

    Args:
        from_status: 当前任务状态
        to_status: 目标任务状态
        run_id: 任务 ID（用于错误消息）

    Raises:
        StateTransitionError: 状态转换非法
    """
    if not run_state_machine.can_transition(from_status.value, to_status.value):
        allowed = run_state_machine.get_allowed_transitions(from_status.value)
        raise StateTransitionError(
            entity_type="RunSession",
            entity_id=run_id,
            from_state=from_status.value,
            to_state=to_status.value,
            allowed_states=allowed,
        )


def is_run_terminal_state(status: RunStatus) -> bool:
    """检查任务是否处于终态。

    Args:
        status: 任务状态

    Returns:
        True 表示是终态
    """
    return run_state_machine.is_terminal_state(status.value)


def is_device_terminal_state(status: DeviceStatus) -> bool:
    """检查设备是否处于终态。

    Args:
        status: 设备状态

    Returns:
        True 表示是终态（设备没有真正的终态）
    """
    return device_state_machine.is_terminal_state(status.value)


def get_run_allowed_transitions(status: RunStatus) -> Set[RunStatus]:
    """获取任务允许的状态转换。

    Args:
        status: 当前任务状态

    Returns:
        允许转换到的状态集合
    """
    allowed_values = run_state_machine.get_allowed_transitions(status.value)
    return {RunStatus(v) for v in allowed_values}


def get_device_allowed_transitions(status: DeviceStatus) -> Set[DeviceStatus]:
    """获取设备允许的状态转换。

    Args:
        status: 当前设备状态

    Returns:
        允许转换到的状态集合
    """
    allowed_values = device_state_machine.get_allowed_transitions(status.value)
    return {DeviceStatus(v) for v in allowed_values}
