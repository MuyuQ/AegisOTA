"""报告生成服务。

整合报告生成器、失败分类器和数据库持久化。
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.report import Report, ReportFormat, ReportStatus
from app.models.run import RunSession, RunStep, RunStatus, StepStatus
from app.reporting.generator import ReportGenerator
from app.reporting.failure_classifier import FailureClassifier, FailureCategory


class ReportService:
    """报告生成服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.generator = ReportGenerator()
        self.classifier = FailureClassifier()

    def generate_report(
        self,
        run_session: RunSession,
        save_files: bool = True,
    ) -> Report:
        """为任务会话生成报告。

        Args:
            run_session: 任务会话对象
            save_files: 是否保存报告文件到磁盘

        Returns:
            生成的报告对象
        """
        # 获取任务步骤
        steps = self._get_run_steps(run_session)

        # 分类失败原因
        failure_category = None
        failure_summary = None
        root_cause = None
        recommendation = None

        if (run_session.status.value if hasattr(run_session.status, 'value') else str(run_session.status)) == RunStatus.FAILED.value:
            failed_step, error_message = self._find_failed_step(steps)
            if failed_step:
                failure_category = self._classify_failure(
                    failed_step, error_message, steps
                )
                failure_summary = f"步骤 {failed_step} 失败"
                root_cause = error_message
                recommendation = self.classifier.get_recommendation(failure_category)

        # 统计步骤
        total_steps = len(steps)
        passed_steps = sum(1 for s in steps if (s.status.value if hasattr(s.status, 'value') else str(s.status)) == StepStatus.SUCCESS.value)
        failed_steps = sum(1 for s in steps if (s.status.value if hasattr(s.status, 'value') else str(s.status)) == StepStatus.FAILED.value)
        skipped_steps = sum(1 for s in steps if (s.status.value if hasattr(s.status, 'value') else str(s.status)) == StepStatus.SKIPPED.value)

        # 创建报告记录
        report = Report(
            run_id=run_session.id,
            title=self._generate_title(run_session),
            format=ReportFormat.JSON,
            status=ReportStatus.GENERATING,
            failure_category=failure_category.value if failure_category else None,
            failure_summary=failure_summary,
            root_cause=root_cause,
            recommendation=recommendation,
            total_steps=total_steps,
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            skipped_steps=skipped_steps,
            duration_seconds=run_session.get_duration_seconds(),
        )

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        # 生成报告数据
        report_data = self._build_report_data(run_session, steps, failure_category)

        # 保存报告文件
        if save_files:
            try:
                content_path = self._save_report_files(report, report_data)
                report.content_path = str(content_path)
            except Exception as e:
                report.status = ReportStatus.FAILED
                self.db.commit()
                raise

        report.status = ReportStatus.COMPLETED
        self.db.commit()

        return report

    def get_report(self, report_id: int) -> Optional[Report]:
        """获取报告。

        Args:
            report_id: 报告 ID

        Returns:
            报告对象，不存在则返回 None
        """
        return self.db.query(Report).filter_by(id=report_id).first()

    def get_report_by_run_id(self, run_id: int) -> Optional[Report]:
        """根据任务 ID 获取报告。

        Args:
            run_id: 任务 ID

        Returns:
            报告对象，不存在则返回 None
        """
        return self.db.query(Report).filter_by(run_id=run_id).first()

    def load_report_content(self, report: Report) -> Optional[Dict[str, Any]]:
        """加载报告内容。

        Args:
            report: 报告对象

        Returns:
            报告数据字典，加载失败返回 None
        """
        if not report.content_path:
            return None

        try:
            path = Path(report.content_path)
            if path.suffix == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            elif path.suffix in (".md", ".markdown"):
                with open(path, "r", encoding="utf-8") as f:
                    return {"markdown": f.read()}
            elif path.suffix in (".html", ".htm"):
                with open(path, "r", encoding="utf-8") as f:
                    return {"html": f.read()}
        except Exception:
            return None

        return None

    def regenerate_report(
        self,
        run_session: RunSession,
        format: ReportFormat = ReportFormat.JSON,
    ) -> Report:
        """重新生成报告。

        Args:
            run_session: 任务会话对象
            format: 报告格式

        Returns:
            新生成的报告对象
        """
        # 删除旧报告
        old_reports = self.db.query(Report).filter_by(run_id=run_session.id).all()
        for old in old_reports:
            if old.content_path:
                self._delete_report_files(old)
            self.db.delete(old)
        self.db.commit()

        # 生成新报告
        return self.generate_report(run_session)

    def _get_run_steps(self, run_session: RunSession) -> List[RunStep]:
        """获取任务的所有步骤。"""
        return self.db.query(RunStep).filter_by(
            run_id=run_session.id
        ).order_by(RunStep.step_order).all()

    def _find_failed_step(
        self,
        steps: List[RunStep],
    ) -> tuple[Optional[str], Optional[str]]:
        """查找失败的步骤。"""
        failed_status = StepStatus.FAILED.value
        for step in steps:
            step_status = step.status.value if hasattr(step.status, 'value') else str(step.status)
            if step_status == failed_status:
                error_msg = None
                if step.step_result:
                    try:
                        result = step.get_result()
                        error_msg = result.get("error") or result.get("message")
                    except Exception:
                        pass
                # step_name 可能是枚举或字符串
                step_name = step.step_name
                if step_name:
                    return step_name.value if hasattr(step_name, 'value') else str(step_name), error_msg
                return None, error_msg
        return None, None

    def _classify_failure(
        self,
        failed_step: str,
        error_message: Optional[str],
        steps: List[RunStep],
    ) -> FailureCategory:
        """分类失败原因。"""
        step_results = {}
        for step in steps:
            if step.step_name:
                try:
                    step_name_value = step.step_name.value if hasattr(step.step_name, 'value') else str(step.step_name)
                    step_results[step_name_value] = step.get_result()
                except Exception:
                    pass

        return self.classifier.classify(failed_step, error_message or "", step_results)

    def _generate_title(self, run_session: RunSession) -> str:
        """生成报告标题。"""
        plan_name = run_session.plan.name if run_session.plan else "未知计划"
        device_serial = run_session.device.serial if run_session.device else "未知设备"
        status_value = run_session.status.value if hasattr(run_session.status, 'value') else str(run_session.status)
        status_text = "成功" if status_value == RunStatus.PASSED.value else "失败"
        return f"{plan_name} - {device_serial} - {status_text}"

    def _build_report_data(
        self,
        run_session: RunSession,
        steps: List[RunStep],
        failure_category: Optional[FailureCategory],
    ) -> Dict[str, Any]:
        """构建报告数据。"""
        # 构建时间线
        timeline = []
        for step in steps:
            # step_name 可能是枚举或字符串
            step_name = step.step_name
            step_name_value = step_name.value if step_name and hasattr(step_name, 'value') else str(step_name) if step_name else None

            event = {
                "step_name": step_name_value,
                "step_order": step.step_order,
                "status": step.status.value if hasattr(step.status, 'value') else str(step.status),
                "started_at": step.started_at.isoformat() if step.started_at else None,
                "ended_at": step.ended_at.isoformat() if step.ended_at else None,
                "duration_seconds": step.get_duration_seconds(),
            }
            timeline.append(event)

        # 构建步骤结果
        step_results = {}
        for step in steps:
            if step.step_name:
                step_name_value = step.step_name.value if hasattr(step.step_name, 'value') else str(step.step_name)
                try:
                    step_results[step_name_value] = step.get_result()
                except Exception:
                    step_results[step_name_value] = {}

        # 生成报告数据
        status_value = run_session.status.value if hasattr(run_session.status, 'value') else str(run_session.status)
        return self.generator.generate(
            run_id=run_session.id,
            plan_name=run_session.plan.name if run_session.plan else "未知计划",
            device_serial=run_session.device.serial if run_session.device else "未知设备",
            status=status_value,
            started_at=run_session.started_at,
            ended_at=run_session.ended_at,
            failed_step=timeline[0]["step_name"] if timeline and status_value == "failed" else None,
            failure_category=failure_category,
            timeline=timeline,
            step_results=step_results,
        )

    def _save_report_files(
        self,
        report: Report,
        report_data: Dict[str, Any],
    ) -> Path:
        """保存报告文件。

        Args:
            report: 报告对象
            report_data: 报告数据

        Returns:
            主报告文件路径
        """
        # 创建报告目录
        report_dir = self.settings.ARTIFACTS_DIR / "reports" / f"run_{report.run_id}"
        report_dir.mkdir(parents=True, exist_ok=True)

        # 保存 JSON 报告
        json_path = report_dir / "report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        # 保存 Markdown 报告
        md_content = self.generator.generate_markdown(
            run_id=report_data["run_id"],
            plan_name=report_data["plan_name"],
            device_serial=report_data["device_serial"],
            status=report_data["status"],
            timeline=report_data.get("timeline", []),
        )
        md_path = report_dir / "report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # 保存 HTML 报告
        html_content = self.generator.generate_html(
            run_id=report_data["run_id"],
            plan_name=report_data["plan_name"],
            device_serial=report_data["device_serial"],
            status=report_data["status"],
            timeline=report_data.get("timeline", []),
        )
        html_path = report_dir / "report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return json_path

    def _delete_report_files(self, report: Report) -> None:
        """删除报告文件。"""
        if not report.content_path:
            return

        try:
            import shutil
            report_dir = Path(report.content_path).parent
            if report_dir.exists():
                shutil.rmtree(report_dir)
        except Exception:
            pass

    def list_reports(
        self,
        status: Optional[ReportStatus] = None,
        limit: int = 100,
    ) -> List[Report]:
        """列出报告。

        Args:
            status: 按状态过滤
            limit: 返回数量限制

        Returns:
            报告列表
        """
        query = self.db.query(Report)

        if status:
            query = query.filter(Report.status == status)

        return query.order_by(
            Report.generated_at.desc()
        ).limit(limit).all()