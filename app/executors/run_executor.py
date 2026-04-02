"""任务执行状态机驱动器。"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.config import get_settings
from app.executors.command_runner import CommandRunner
from app.executors.adb_executor import ADBExecutor
from app.executors.mock_executor import MockADBExecutor
from app.executors.run_context import RunContext
from app.executors.step_handlers import (
    StepHandler, StepHandlerResult,
    PrecheckHandler, PushPackageHandler,
    ApplyUpdateHandler, RebootWaitHandler,
    PostValidateHandler,
)
from app.models.run import StepName


@dataclass
class RunExecutionResult:
    """任务执行结果。"""

    success: bool
    run_id: int
    started_at: datetime
    ended_at: datetime
    step_results: Dict[str, StepHandlerResult] = field(default_factory=dict)
    failed_step: Optional[StepName] = None
    error: Optional[str] = None
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    def get_duration_seconds(self) -> int:
        """获取总执行时长。"""
        return int((self.ended_at - self.started_at).total_seconds())

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "success": self.success,
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "duration_seconds": self.get_duration_seconds(),
            "failed_step": self.failed_step.value if self.failed_step else None,
            "error": self.error,
            "steps": {
                name: result.to_dict()
                for name, result in self.step_results.items()
            },
        }


# 保持向后兼容
ExecutionResult = RunExecutionResult


class RunExecutor:
    """任务执行状态机。"""

    # 默认执行步骤顺序
    DEFAULT_STEPS = [
        StepName.PRECHECK,
        StepName.PACKAGE_PREPARE,
        StepName.APPLY_UPDATE,
        StepName.REBOOT_WAIT,
        StepName.POST_VALIDATE,
    ]

    def __init__(
        self,
        runner: Optional[CommandRunner] = None,
        custom_handlers: Optional[Dict[StepName, StepHandler]] = None,
    ):
        self.settings = get_settings()
        self.runner = runner

        # 初始化 handler
        self.handlers: Dict[StepName, StepHandler] = custom_handlers or self._create_default_handlers()

    def _create_default_handlers(self) -> Dict[StepName, StepHandler]:
        """创建默认 handler 集合。"""
        executor = ADBExecutor(runner=self.runner) if self.runner else ADBExecutor()

        return {
            StepName.PRECHECK: PrecheckHandler(executor=executor),
            StepName.PACKAGE_PREPARE: PushPackageHandler(executor=executor),
            StepName.APPLY_UPDATE: ApplyUpdateHandler(executor=executor),
            StepName.REBOOT_WAIT: RebootWaitHandler(executor=executor),
            StepName.POST_VALIDATE: PostValidateHandler(executor=executor),
        }

    def get_step_names(self) -> List[StepName]:
        """获取执行步骤名称列表。"""
        return self.DEFAULT_STEPS

    def execute(self, context: RunContext) -> RunExecutionResult:
        """执行完整任务流程。"""
        started_at = datetime.now(timezone.utc)
        context.started_at = started_at

        context.record_event("run_start", f"Starting run {context.run_id}")

        step_results: Dict[str, StepHandlerResult] = {}
        failed_step: Optional[StepName] = None
        error: Optional[str] = None

        # 按顺序执行各阶段
        for step_name in self.DEFAULT_STEPS:
            handler = self.handlers.get(step_name)
            if not handler:
                continue

            # 执行阶段
            result = handler.execute(context)
            step_results[step_name.value] = result

            # 记录结果到上下文
            context.set_step_result(step_name.value, result.to_dict())

            # 检查是否失败
            if not result.success:
                failed_step = step_name
                error = result.error
                context.record_event(
                    "step_failure",
                    f"Step {step_name.value} failed: {result.message}",
                    {"error": result.error}
                )
                break

            context.record_event(
                "step_success",
                f"Step {step_name.value} completed",
            )

        ended_at = datetime.now(timezone.utc)

        # 保存时间线
        if context.artifact_dir:
            timeline_file = context.artifact_dir / "timeline.json"
            timeline_file.parent.mkdir(parents=True, exist_ok=True)
            with open(timeline_file, "w") as f:
                json.dump(context.timeline, f, indent=2)

        context.record_event("run_end", f"Run {context.run_id} ended")

        return RunExecutionResult(
            success=(failed_step is None),
            run_id=context.run_id,
            started_at=started_at,
            ended_at=ended_at,
            step_results=step_results,
            failed_step=failed_step,
            error=error,
            timeline=context.timeline,
        )

    def execute_step(
        self,
        step_name: StepName,
        context: RunContext,
    ) -> StepHandlerResult:
        """执行单个阶段。"""
        handler = self.handlers.get(step_name)
        if not handler:
            return StepHandlerResult(
                success=False,
                step_name=step_name,
                message="Handler not found",
                data={},
                duration_ms=0,
                error=f"No handler for step {step_name}",
            )

        return handler.execute(context)


class MockRunExecutor(RunExecutor):
    """Mock 状态机执行器（用于测试）。"""

    def __init__(self, mock_executor: Optional[MockADBExecutor] = None):
        executor = mock_executor or MockADBExecutor.upgrade_success_responses()

        handlers = {
            StepName.PRECHECK: PrecheckHandler(executor=executor),
            StepName.PACKAGE_PREPARE: PushPackageHandler(executor=executor),
            StepName.APPLY_UPDATE: ApplyUpdateHandler(executor=executor),
            StepName.REBOOT_WAIT: RebootWaitHandler(executor=executor),
            StepName.POST_VALIDATE: PostValidateHandler(executor=executor),
        }

        super().__init__(custom_handlers=handlers)