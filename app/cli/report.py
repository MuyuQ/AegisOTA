"""报告管理 CLI 命令。

提供报告导出功能。
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from app.database import SessionLocal, init_db
from app.models import RunSession, Artifact

app = typer.Typer(help="报告管理命令")
console = Console()


@app.command("export")
def export_report(
    run_id: int = typer.Argument(..., help="任务 ID"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="输出文件路径"
    ),
    format: str = typer.Option(
        "markdown", "--format", "-f", help="报告格式 (markdown/html/json)"
    ),
):
    """导出任务报告。

    根据任务执行记录生成报告文件。
    """
    init_db()
    db = SessionLocal()

    try:
        run = db.query(RunSession).filter(RunSession.id == run_id).first()

        if not run:
            typer.echo(f"任务不存在: {run_id}", err=True)
            raise typer.Exit(1)

        # 显示任务基本信息
        typer.echo(f"\n任务报告 - ID: {run_id}")
        typer.echo("=" * 50)

        table = Table(show_header=False)
        table.add_column("属性", style="cyan")
        table.add_column("值", style="green")

        plan_name = run.plan.name if run.plan else "-"
        device_serial = run.device.serial if run.device else "-"
        duration = run.get_duration_seconds()
        duration_str = f"{duration:.1f}s" if duration else "-"

        table.add_row("升级计划", plan_name)
        table.add_row("设备序列号", device_serial)
        table.add_row("状态", run.status.value)
        table.add_row("失败分类", run.failure_category.value if run.failure_category else "-")
        table.add_row("持续时间", duration_str)
        table.add_row("创建时间", str(run.created_at))
        table.add_row("开始时间", str(run.started_at or "-"))
        table.add_row("结束时间", str(run.ended_at or "-"))

        console.print(table)

        # 显示执行步骤
        if run.steps:
            typer.echo("\n执行步骤:")
            steps_table = Table()
            steps_table.add_column("步骤", style="cyan")
            steps_table.add_column("状态", style="yellow")
            steps_table.add_column("开始时间", style="blue")
            steps_table.add_column("持续时间", style="white")

            for step in sorted(run.steps, key=lambda s: s.step_order):
                step_duration = step.get_duration_seconds()
                step_duration_str = f"{step_duration:.1f}s" if step_duration else "-"

                steps_table.add_row(
                    step.step_name.value,
                    step.status.value,
                    str(step.started_at or "-"),
                    step_duration_str,
                )

            console.print(steps_table)

        # 显示产物列表
        artifacts = db.query(Artifact).filter(Artifact.run_id == run_id).all()
        if artifacts:
            typer.echo("\n执行产物:")
            artifacts_table = Table()
            artifacts_table.add_column("类型", style="cyan")
            artifacts_table.add_column("文件路径", style="green")
            artifacts_table.add_column("大小", style="magenta")
            artifacts_table.add_column("描述", style="white")

            for artifact in artifacts:
                size_str = f"{artifact.file_size or 0} bytes"
                artifacts_table.add_row(
                    artifact.artifact_type,
                    artifact.file_path,
                    size_str,
                    artifact.description or "-",
                )

            console.print(artifacts_table)

        # 生成报告文件
        if output:
            report_content = _generate_report_content(run, artifacts, format)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(report_content, encoding="utf-8")
            typer.echo(f"\n报告已导出至: {output}")
        else:
            typer.echo("\n报告内容:")
            typer.echo(_generate_report_content(run, artifacts, "markdown"))

    finally:
        db.close()


def _generate_report_content(
    run: RunSession, artifacts: list[Artifact], format: str
) -> str:
    """生成报告内容。

    根据格式类型生成对应的报告文本。
    """
    plan_name = run.plan.name if run.plan else "-"
    device_serial = run.device.serial if run.device else "-"
    duration = run.get_duration_seconds()
    duration_str = f"{duration:.1f}s" if duration else "-"

    if format == "json":
        import json

        report_data = {
            "run_id": run.id,
            "plan_name": plan_name,
            "device_serial": device_serial,
            "status": run.status.value,
            "failure_category": run.failure_category.value if run.failure_category else None,
            "duration_seconds": duration,
            "created_at": str(run.created_at),
            "started_at": str(run.started_at) if run.started_at else None,
            "ended_at": str(run.ended_at) if run.ended_at else None,
            "summary": run.summary,
            "result": run.result,
            "steps": [
                {
                    "name": step.step_name.value,
                    "status": step.status.value,
                    "duration_seconds": step.get_duration_seconds(),
                }
                for step in sorted(run.steps, key=lambda s: s.step_order)
            ],
            "artifacts": [
                {
                    "type": artifact.artifact_type,
                    "path": artifact.file_path,
                    "size": artifact.file_size,
                }
                for artifact in artifacts
            ],
        }
        return json.dumps(report_data, indent=2, ensure_ascii=False)

    elif format == "html":
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"<title>任务报告 - {run.id}</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; }",
            "th { background-color: #f2f2f2; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>任务报告 - ID: {run.id}</h1>",
            "<h2>基本信息</h2>",
            "<table>",
            f"<tr><th>升级计划</th><td>{plan_name}</td></tr>",
            f"<tr><th>设备序列号</th><td>{device_serial}</td></tr>",
            f"<tr><th>状态</th><td>{run.status.value}</td></tr>",
            f"<tr><th>持续时间</th><td>{duration_str}</td></tr>",
            "</table>",
        ]

        if run.steps:
            html_parts.extend([
                "<h2>执行步骤</h2>",
                "<table>",
                "<tr><th>步骤</th><th>状态</th><th>持续时间</th></tr>",
            ])
            for step in sorted(run.steps, key=lambda s: s.step_order):
                step_duration = step.get_duration_seconds()
                step_duration_str = f"{step_duration:.1f}s" if step_duration else "-"
                html_parts.append(
                    f"<tr><td>{step.step_name.value}</td><td>{step.status.value}</td>"
                    f"<td>{step_duration_str}</td></tr>"
                )
            html_parts.append("</table>")

        html_parts.extend(["</body>", "</html>"])
        return "\n".join(html_parts)

    else:  # markdown
        md_parts = [
            f"# 任务报告 - ID: {run.id}",
            "",
            "## 基本信息",
            "",
            f"| 属性 | 值 |",
            f"| --- | --- |",
            f"| 升级计划 | {plan_name} |",
            f"| 设备序列号 | {device_serial} |",
            f"| 状态 | {run.status.value} |",
            f"| 失败分类 | {run.failure_category.value if run.failure_category else '-'} |",
            f"| 持续时间 | {duration_str} |",
            f"| 创建时间 | {run.created_at} |",
        ]

        if run.steps:
            md_parts.extend([
                "",
                "## 执行步骤",
                "",
                "| 步骤 | 状态 | 持续时间 |",
                "| --- | --- | --- |",
            ])
            for step in sorted(run.steps, key=lambda s: s.step_order):
                step_duration = step.get_duration_seconds()
                step_duration_str = f"{step_duration:.1f}s" if step_duration else "-"
                md_parts.append(
                    f"| {step.step_name.value} | {step.status.value} | {step_duration_str} |"
                )

        if artifacts:
            md_parts.extend([
                "",
                "## 执行产物",
                "",
                "| 类型 | 文件路径 | 大小 |",
                "| --- | --- | --- |",
            ])
            for artifact in artifacts:
                md_parts.append(
                    f"| {artifact.artifact_type} | {artifact.file_path} | "
                    f"{artifact.file_size or 0} bytes |"
                )

        if run.summary:
            md_parts.extend([
                "",
                "## 总结",
                "",
                run.summary,
            ])

        return "\n".join(md_parts)