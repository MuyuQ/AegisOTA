"""命令执行抽象模块。"""

import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass
class CommandResult:
    """命令执行结果。"""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int

    @property
    def success(self) -> bool:
        """判断命令是否成功。"""
        return self.exit_code == 0

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "success": self.success,
        }


class CommandRunner(ABC):
    """命令执行器抽象基类。"""

    @abstractmethod
    def run(
        self,
        command: Union[str, List[str]],
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> CommandResult:
        """执行命令并返回结果。

        Args:
            command: 要执行的命令（字符串或列表形式）
            timeout: 超时时间（秒）
            cwd: 工作目录
            env: 环境变量

        Returns:
            CommandResult: 命令执行结果
        """
        pass


class ShellCommandRunner(CommandRunner):
    """真实 shell 命令执行器。"""

    def run(
        self,
        command: Union[str, List[str]],
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> CommandResult:
        """执行 shell 命令。

        当 command 为列表时，直接传递给 subprocess（不使用 shell=True），
        避免命令注入风险。
        当 command 为字符串时，使用 shell=True 执行（保持向后兼容）。
        """
        start_time = time.time()

        # 判断是否使用 shell 模式
        use_shell = isinstance(command, str)
        command_display = command if isinstance(command, str) else " ".join(command)

        try:
            process = subprocess.run(
                command,
                shell=use_shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return CommandResult(
                command=command_display,
                exit_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_ms=duration_ms,
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return CommandResult(
                command=command_display,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return CommandResult(
                command=command_display,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
            )
