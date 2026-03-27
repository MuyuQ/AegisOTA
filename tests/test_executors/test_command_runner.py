"""命令执行器测试。"""

import pytest
from dataclasses import dataclass

from app.executors.command_runner import CommandRunner, CommandResult


def test_command_result_creation():
    """测试命令结果创建。"""
    result = CommandResult(
        command="echo test",
        exit_code=0,
        stdout="test\n",
        stderr="",
        duration_ms=50
    )

    assert result.exit_code == 0
    assert result.stdout == "test\n"
    assert result.success is True


def test_command_result_failure():
    """测试命令失败结果。"""
    result = CommandResult(
        command="false",
        exit_code=1,
        stdout="",
        stderr="",
        duration_ms=10
    )

    assert result.exit_code == 1
    assert result.success is False


def test_command_runner_abstract():
    """测试 CommandRunner 是抽象类。"""
    # 不能直接实例化抽象类
    from abc import ABC
    assert CommandRunner.__bases__[0] is ABC


def test_command_runner_interface():
    """测试 CommandRunner 接口方法。"""
    # 检查抽象方法存在
    import inspect
    # 获取所有成员，包括函数
    members = inspect.getmembers(CommandRunner)
    abstract_methods = [
        name for name, obj in members
        if getattr(obj, '__isabstractmethod__', False)
    ]
    assert 'run' in abstract_methods or 'execute' in abstract_methods