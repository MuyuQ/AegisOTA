"""报告生成模块。"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.config import get_settings
from app.reporting.failure_classifier import FailureCategory


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
        """生成 HTML 格式报告。"""
        timeline = timeline or []
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'>",
            "<title>OTA升级报告 - Run #{}</title>".format(run_id),
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".header { background: #f0f0f0; padding: 15px; border-radius: 5px; }",
            ".status-passed { color: green; }",
            ".status-failed { color: red; }",
            ".timeline { margin-top: 20px; }",
            ".timeline-item { padding: 10px; border-bottom: 1px solid #ddd; }",
            "</style>",
            "</head>",
            "<body>",
            "<div class='header'>",
            "<h1>OTA升级报告</h1>",
            "<p><strong>Run ID:</strong> {}</p>".format(run_id),
            "<p><strong>计划:</strong> {}</p>".format(plan_name),
            "<p><strong>设备:</strong> {}</p>".format(device_serial),
            "<p><strong>状态:</strong> <span class='status-{}'>{}</span></p>".format(
                status.lower(), status
            ),
            "</div>",
            "<div class='timeline'>",
            "<h2>执行时间线</h2>",
        ]

        for event in timeline:
            html_parts.append(
                "<div class='timeline-item'>"
                "<span>{}</span> - {}"
                "</div>".format(
                    event.get("timestamp", ""),
                    event.get("message", "")
                )
            )

        html_parts.extend([
            "</div>",
            "</body>",
            "</html>",
        ])

        return "\n".join(html_parts)

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
        )
        html_path = output_dir / "report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return json_path