"""Worker 服务模块。"""

import time
import threading
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.executors.command_runner import CommandRunner
from app.executors.run_executor import RunExecutor, MockRunExecutor, ExecutionResult
from app.executors.run_context import RunContext
from app.executors.mock_executor import MockExecutor
from app.models.device import Device, DeviceStatus
from app.models.run import RunSession, RunStatus, StepName
from app.models.artifact import Artifact, ArtifactType
from app.services.scheduler_service import SchedulerService
from app.services.run_service import RunService
from app.reporting.generator import ReportGenerator
from app.reporting.failure_classifier import FailureCategory, FailureClassifier


class WorkerService:
    """后台任务执行 Worker。"""

    def __init__(
        self,
        db: Session,
        runner: Optional[CommandRunner] = None,
        poll_interval: int = 5,
        max_concurrent: int = 5,
        max_iterations: int = -1,  # -1 表示无限循环
    ):
        self.db = db
        self.settings = get_settings()
        self.poll_interval = poll_interval
        self.max_concurrent = max_concurrent
        self.max_iterations = max_iterations
        self.running = False
        self._thread: Optional[threading.Thread] = None

        # 执行器
        self.executor = RunExecutor(runner=runner) if runner else RunExecutor()

        # 服务
        self.scheduler = SchedulerService(db)
        self.run_service = RunService(db)
        self.report_generator = ReportGenerator()
        self.failure_classifier = FailureClassifier()

    def start(self):
        """启动 Worker。"""
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止 Worker。"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=10)
            self._thread = None

    def _run_loop(self):
        """主循环。"""
        iterations = 0

        while self.running:
            if self.max_iterations > 0 and iterations >= self.max_iterations:
                break

            try:
                self.process_one_iteration()
            except Exception as e:
                print(f"Worker iteration error: {e}")

            iterations += 1

            if self.running:
                time.sleep(self.poll_interval)

    def process_one_iteration(self) -> Optional[RunSession]:
        """处理一个任务。"""
        # 检查并发限制
        if not self.scheduler.can_start_new_run():
            return None

        # 获取下一个待执行任务
        next_run = self.scheduler.get_next_run_to_execute()

        if not next_run:
            return None

        # 执行任务
        return self.execute_run(next_run.id)

    def execute_run(self, run_id: int) -> Optional[RunSession]:
        """执行指定任务。"""
        run = self.run_service.get_run_session(run_id)
        if not run:
            return None

        # 获取设备和计划信息
        device = self.db.query(Device).filter_by(id=run.device_id).first()
        plan = run.plan

        if not device or not plan:
            return None

        # 更新状态为运行中
        self.run_service.update_run_status(run_id, RunStatus.RUNNING)

        # 读取任务选项
        run_options = run.get_run_options()
        total_iterations = run.total_iterations or 1

        # 创建执行上下文
        upgrade_type = plan.upgrade_type
        if hasattr(upgrade_type, 'value'):
            upgrade_type = upgrade_type.value

        context = RunContext(
            run_id=run_id,
            device_serial=device.serial,
            plan_id=plan.id,
            upgrade_type=upgrade_type,
            package_path=plan.package_path,
            target_build=plan.target_build,
            run_options=run_options,
            total_iterations=total_iterations,
        )

        # 执行任务
        execution_result = self.executor.execute(context)

        # 保存产物记录
        self._save_artifacts(run_id, context)

        # 更新任务状态
        if execution_result.success:
            self.run_service.complete_run_session(
                run_id,
                result="success",
                status=RunStatus.PASSED,
                summary=f"升级成功完成，耗时 {execution_result.get_duration_seconds()} 秒",
            )
        else:
            # 分类失败原因
            failure_category = self._classify_failure(
                execution_result.failed_step,
                execution_result.error,
            )

            self.run_service.complete_run_session(
                run_id,
                result="failure",
                status=RunStatus.FAILED,
                summary=f"升级失败：{execution_result.error}",
                failure_category=failure_category.value if failure_category else None,
            )

            # 设备隔离检查
            if failure_category in [
                FailureCategory.BOOT_FAILURE,
                FailureCategory.DEVICE_ENV_ISSUE,
            ]:
                self.scheduler.device_service.quarantine_device(
                    device.serial,
                    reason=f"Task {run_id} failed: {failure_category.value}",
                    run_id=run_id,
                )

        # 释放设备租约
        self.scheduler.release_device_lease(device.id, run_id)

        # 生成报告
        self._generate_report(run, execution_result, context.timeline)

        self.db.refresh(run)
        return run

    def get_running_count(self) -> int:
        """获取正在运行的任务数。"""
        return self.scheduler.get_concurrent_run_count()

    def _classify_failure(
        self,
        failed_step: Optional[StepName],
        error: Optional[str],
    ) -> Optional[FailureCategory]:
        """分类失败原因。"""
        if not failed_step:
            return FailureCategory.UNKNOWN

        return self.failure_classifier.classify(
            failed_step.value,
            error or "",
            {},
        )

    def _save_artifacts(self, run_id: int, context: RunContext):
        """保存产物记录到数据库。"""
        artifact_dir = context.artifact_dir

        if not artifact_dir or not artifact_dir.exists():
            return

        for file_path in artifact_dir.iterdir():
            if file_path.is_file():
                artifact_type = self._determine_artifact_type(file_path.name)

                artifact = Artifact(
                    run_id=run_id,
                    artifact_type=artifact_type,
                    file_path=str(file_path),
                    file_size=file_path.stat().st_size,
                )
                self.db.add(artifact)

        self.db.commit()

    def _determine_artifact_type(self, filename: str) -> str:
        """判断产物类型。"""
        if "logcat" in filename.lower():
            return ArtifactType.LOGCAT.value
        elif "stdout" in filename.lower():
            return ArtifactType.STDOUT.value
        elif "stderr" in filename.lower():
            return ArtifactType.STDERR.value
        elif "monkey" in filename.lower():
            return ArtifactType.MONKEY_RESULT.value
        elif "timeline" in filename.lower():
            return ArtifactType.TIMELINE.value
        elif "report" in filename.lower():
            return ArtifactType.REPORT.value
        else:
            return ArtifactType.STDOUT.value

    def _generate_report(
        self,
        run: RunSession,
        execution_result: ExecutionResult,
        timeline: list,
    ):
        """生成任务报告。"""
        # 转换 step_results 为可序列化格式
        step_results = {}
        if hasattr(execution_result, 'step_results'):
            for name, result in execution_result.step_results.items():
                if hasattr(result, 'to_dict'):
                    step_results[name] = result.to_dict()
                elif isinstance(result, dict):
                    step_results[name] = result
                else:
                    step_results[name] = str(result)

        report_data = self.report_generator.generate(
            run_id=run.id,
            plan_name=run.plan.name if run.plan else "Unknown",
            device_serial=run.device.serial if run.device else "Unknown",
            status=run.status.value if hasattr(run.status, 'value') else str(run.status),
            started_at=run.started_at,
            ended_at=run.ended_at,
            failed_step=execution_result.failed_step.value if execution_result.failed_step else None,
            failure_category=FailureCategory(run.failure_category) if run.failure_category else None,
            timeline=timeline,
            step_results=step_results,
        )

        # 保存报告
        settings = get_settings()
        output_dir = settings.ARTIFACTS_DIR / str(run.id)
        self.report_generator.save_report(report_data, output_dir)