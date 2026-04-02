"""报告生成模块。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.reporting.failure_classifier import FailureCategory


# 初始化 Jinja2 环境
_templates_dir = Path(__file__).parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(_templates_dir),
    autoescape=select_autoescape(["html", "xml"]),
)


@dataclass
class ReportData:
    """报告数据结构。"""

    run_id: int
    plan_name: str
    device_serial: str
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    failed_step: Optional[str] = None
    failure_category: Optional[FailureCategory] = None
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    step_results: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    summary: Optional[str] = None


class ReportGenerator:
    """报告生成器。"""

    def generate(
        self,
        run_id: int,
        plan_name: str,
        device_serial: str,
        status: str,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
        failed_step: Optional[str] = None,
        failure_category: Optional[FailureCategory] = None,
        timeline: Optional[List[Dict[str, Any]]] = None,
        step_results: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """生成报告数据。"""
        timeline = timeline or []
        step_results = step_results or {}
        report = {
            "run_id": run_id,
            "plan_name": plan_name,
            "device_serial": device_serial,
            "status": status,
            "started_at": started_at.isoformat() if started_at else None,
            "ended_at": ended_at.isoformat() if ended_at else None,
            "duration_seconds": self._calculate_duration(started_at, ended_at),
            "failed_step": failed_step,
            "failure_category": failure_category.value if failure_category else None,
            "timeline": timeline,
            "step_results": step_results,
            "summary": self._generate_summary(status, failed_step, failure_category),
        }

        return report

    def _calculate_duration(
        self,
        started_at: Optional[datetime],
        ended_at: Optional[datetime],
    ) -> Optional[float]:
        """计算执行时长。"""
        if started_at and ended_at:
            delta = ended_at - started_at
            return delta.total_seconds()
        return None

    def _generate_summary(
        self,
        status: str,
        failed_step: Optional[str],
        failure_category: Optional[FailureCategory],
    ) -> str:
        """生成报告摘要。"""
        if status in ["passed", "success"]:
            return "升级任务成功完成"
        elif status in ["failed", "failure"]:
            parts = ["升级任务失败"]
            if failed_step:
                parts.append(f"，失败步骤: {failed_step}")
            if failure_category:
                parts.append(f"，原因分类: {failure_category.value}")
            return "".join(parts)
        elif status == "aborted":
            return "升级任务被终止"
        else:
            return f"升级任务状态: {status}"

    def generate_html(
        self,
        run_id: int,
        plan_name: str,
        device_serial: str,
        status: str,
        timeline: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> str:
        """生成 HTML 格式报告（使用 Jinja2 模板）。"""
        timeline = timeline or []
        template = _jinja_env.get_template("report.html")

        # 状态显示映射
        status_display_map = {
            "passed": "成功",
            "success": "成功",
            "failed": "失败",
            "failure": "失败",
            "aborted": "已终止",
            "running": "运行中",
            "queued": "排队中",
        }

        # 计算执行时长
        started_at = kwargs.get("started_at")
        ended_at = kwargs.get("ended_at")
        duration_seconds = None
        if started_at and ended_at:
            if isinstance(started_at, str):
                started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            if isinstance(ended_at, str):
                ended_at = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
            duration_seconds = (ended_at - started_at).total_seconds()

        # 格式化时长显示
        duration_display = None
        if duration_seconds:
            minutes, seconds = divmod(int(duration_seconds), 60)
            if minutes > 0:
                duration_display = f"{minutes}分{seconds}秒"
            else:
                duration_display = f"{seconds}秒"

        # 格式化时间显示
        started_at_display = None
        ended_at_display = None
        if started_at:
            if isinstance(started_at, str):
                started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            started_at_display = started_at.strftime("%Y-%m-%d %H:%M:%S")
        if ended_at:
            if isinstance(ended_at, str):
                ended_at = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
            ended_at_display = ended_at.strftime("%Y-%m-%d %H:%M:%S")

        # 渲染模板
        return template.render(
            run_id=run_id,
            plan_name=plan_name,
            device_serial=device_serial,
            status=status,
            status_display=status_display_map.get(status.lower(), status),
            timeline=timeline,
            step_results=kwargs.get("step_results", {}),
            summary=kwargs.get("summary"),
            failure_category=kwargs.get("failure_category"),
            failed_step=kwargs.get("failed_step"),
            started_at=started_at,
            ended_at=ended_at,
            started_at_display=started_at_display,
            ended_at_display=ended_at_display,
            duration_seconds=duration_seconds,
            duration_display=duration_display,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

    def generate_markdown(
        self,
        run_id: int,
        plan_name: str,
        device_serial: str,
        status: str,
        timeline: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> str:
        """生成 Markdown 格式报告。"""
        timeline = timeline or []
        md_parts = [
            "# OTA升级报告",
            "",
            "## 基本信息",
            "",
            "- **Run ID**: {}".format(run_id),
            "- **计划**: {}".format(plan_name),
            "- **设备**: {}".format(device_serial),
            "- **状态**: {}".format(status),
            "",
            "## 执行时间线",
            "",
        ]

        for event in timeline:
            md_parts.append("- **{}**: {}".format(
                event.get("timestamp", ""),
                event.get("message", "")
            ))

        return "\n".join(md_parts)

    def save_report(
        self,
        report_data: Dict[str, Any],
        output_dir: Path,
    ) -> Path:
        """保存报告到文件。"""
        settings = get_settings()
        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存 JSON 报告
        import json
        json_path = output_dir / "report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        # 保存 Markdown 报告
        md_content = self.generate_markdown(
            run_id=report_data["run_id"],
            plan_name=report_data["plan_name"],
            device_serial=report_data["device_serial"],
            status=report_data["status"],
            timeline=report_data.get("timeline", []),
        )
        md_path = output_dir / "report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        # 保存 HTML 报告
        html_content = self.generate_html(
            run_id=report_data["run_id"],
            plan_name=report_data["plan_name"],
            device_serial=report_data["device_serial"],
            status=report_data["status"],
            timeline=report_data.get("timeline", []),
            step_results=report_data.get("step_results", {}),
            summary=report_data.get("summary"),
            failure_category=report_data.get("failure_category"),
            failed_step=report_data.get("failed_step"),
            started_at=report_data.get("started_at"),
            ended_at=report_data.get("ended_at"),
        )
        html_path = output_dir / "report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return json_path