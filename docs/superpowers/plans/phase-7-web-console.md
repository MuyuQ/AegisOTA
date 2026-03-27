# Phase 7: Web 控制台与文档

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-step.

**Goal:** 实现轻量级 Web 控制台界面，提供可视化入口，完成项目文档。

**Architecture:** 使用 Jinja2 模板 + HTMX 实现轻量级前端，无需构建工具。

**Tech Stack:** FastAPI, Jinja2, HTMX, CSS

---

## 文件结构

```
app/templates/
├── base.html                   # 基础布局模板
├── dashboard.html              # 仪表盘首页
├── devices.html                # 设备列表页
├── device_detail.html          # 设备详情页
├── runs.html                   # 任务列表页
├── run_detail.html             # 任务详情页
├── report.html                 # 报告查看页
├── create_run.html             # 创建任务页

app/static/css/
└── style.css                   # 样式表

app/api/
└── web.py                      # Web 页面路由
```

---

## Task 7.1: 基础布局模板

**Files:**
- Create: `app/templates/base.html`
- Create: `app/static/css/style.css`

- [ ] **Step 1: 创建样式表**

```css
/* app/static/css/style.css */

:root {
    --primary-color: #2563eb;
    --secondary-color: #64748b;
    --success-color: #22c55e;
    --warning-color: #f59e0b;
    --danger-color: #ef4444;
    --background-color: #f8fafc;
    --card-background: #ffffff;
    --border-color: #e2e8f0;
    --text-color: #1e293b;
    --text-muted: #64748b;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background-color: var(--background-color);
    color: var(--text-color);
    line-height: 1.6;
}

.container {
    max-width: 1280px;
    margin: 0 auto;
    padding: 0 1rem;
}

/* 导航栏 */
.navbar {
    background-color: var(--card-background);
    border-bottom: 1px solid var(--border-color);
    padding: 1rem 0;
    position: sticky;
    top: 0;
    z-index: 100;
}

.navbar .container {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.navbar-brand {
    font-size: 1.5rem;
    font-weight: bold;
    color: var(--primary-color);
    text-decoration: none;
}

.navbar-nav {
    display: flex;
    list-style: none;
    gap: 1.5rem;
}

.navbar-nav a {
    color: var(--text-muted);
    text-decoration: none;
    transition: color 0.2s;
}

.navbar-nav a:hover {
    color: var(--primary-color);
}

/* 主内容区 */
.main-content {
    padding: 2rem 0;
}

/* 卡片 */
.card {
    background-color: var(--card-background);
    border: 1px solid var(--border-color);
    border-radius: 0.5rem;
    padding: 1.5rem;
    margin-bottom: 1rem;
}

.card-header {
    font-size: 1.25rem;
    font-weight: 600;
    margin-bottom: 1rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border-color);
}

/* 状态标签 */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.875rem;
    font-weight: 500;
}

.status-idle { background-color: #e0f2fe; color: #0369a1; }
.status-busy { background-color: #fef3c7; color: #b45309; }
.status-offline { background-color: #f1f5f9; color: #475569; }
.status-quarantined { background-color: #fee2e2; color: #b91c1c; }

.status-queued { background-color: #e0f2fe; color: #0369a1; }
.status-running { background-color: #fef3c7; color: #b45309; }
.status-passed { background-color: #dcfce7; color: #15803d; }
.status-failed { background-color: #fee2e2; color: #b91c1c; }
.status-aborted { background-color: #f1f5f9; color: #475569; }

/* 表格 */
.table {
    width: 100%;
    border-collapse: collapse;
}

.table th,
.table td {
    padding: 0.75rem;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

.table th {
    background-color: var(--background-color);
    font-weight: 600;
}

.table tr:hover {
    background-color: var(--background-color);
}

/* 按钮 */
.btn {
    display: inline-block;
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    font-size: 0.875rem;
    font-weight: 500;
    text-decoration: none;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
}

.btn-primary {
    background-color: var(--primary-color);
    color: white;
}

.btn-primary:hover {
    background-color: #1d4ed8;
}

.btn-secondary {
    background-color: var(--secondary-color);
    color: white;
}

.btn-danger {
    background-color: var(--danger-color);
    color: white;
}

.btn-sm {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
}

/* 表单 */
.form-group {
    margin-bottom: 1rem;
}

.form-label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
}

.form-input,
.form-select {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid var(--border-color);
    border-radius: 0.375rem;
    font-size: 1rem;
}

.form-input:focus,
.form-select:focus {
    outline: none;
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

/* 网格布局 */
.grid {
    display: grid;
    gap: 1.5rem;
}

.grid-cols-2 { grid-template-columns: repeat(2, 1fr); }
.grid-cols-3 { grid-template-columns: repeat(3, 1fr); }
.grid-cols-4 { grid-template-columns: repeat(4, 1fr); }

@media (max-width: 768px) {
    .grid-cols-2,
    .grid-cols-3,
    .grid-cols-4 {
        grid-template-columns: 1fr;
    }
}

/* 统计卡片 */
.stat-card {
    text-align: center;
}

.stat-value {
    font-size: 2rem;
    font-weight: bold;
    color: var(--primary-color);
}

.stat-label {
    color: var(--text-muted);
    font-size: 0.875rem;
}

/* 时间线 */
.timeline {
    position: relative;
    padding-left: 2rem;
}

.timeline::before {
    content: '';
    position: absolute;
    left: 0.5rem;
    top: 0;
    bottom: 0;
    width: 2px;
    background-color: var(--border-color);
}

.timeline-item {
    position: relative;
    padding-bottom: 1rem;
}

.timeline-item::before {
    content: '';
    position: absolute;
    left: -1.625rem;
    top: 0.375rem;
    width: 0.75rem;
    height: 0.75rem;
    border-radius: 50%;
    background-color: var(--primary-color);
}

.timeline-item.success::before { background-color: var(--success-color); }
.timeline-item.failure::before { background-color: var(--danger-color); }
```

- [ ] **Step 2: 创建基础布局模板**

```html
<!-- app/templates/base.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}AegisOTA{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/style.css">
    <script src="https://unpkg.com/htmx.org@1.9.6"></script>
</head>
<body>
    <nav class="navbar">
        <div class="container">
            <a href="/" class="navbar-brand">AegisOTA</a>
            <ul class="navbar-nav">
                <li><a href="/">仪表盘</a></li>
                <li><a href="/devices">设备管理</a></li>
                <li><a href="/runs">任务列表</a></li>
                <li><a href="/runs/create">创建任务</a></li>
            </ul>
        </div>
    </nav>

    <main class="main-content">
        <div class="container">
            {% block content %}{% endblock %}
        </div>
    </main>

    <footer style="text-align: center; padding: 2rem; color: var(--text-muted);">
        <p>AegisOTA - Android OTA Upgrade Exception Injection Platform</p>
    </footer>

    {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3: 提交**

```bash
git add app/templates/base.html app/static/css/style.css
git commit -m "feat: add base layout template and CSS styles"
```

---

## Task 7.2: 仪表盘页面

**Files:**
- Create: `app/templates/dashboard.html`
- Create: `app/api/web.py`

- [ ] **Step 1: 创建仪表盘模板**

```html
<!-- app/templates/dashboard.html -->
{% extends "base.html" %}

{% block title %}仪表盘 - AegisOTA{% endblock %}

{% block content %}
<h1 style="margin-bottom: 2rem;">仪表盘</h1>

<div class="grid grid-cols-4">
    <div class="card stat-card">
        <div class="stat-value">{{ stats.total_devices }}</div>
        <div class="stat-label">设备总数</div>
    </div>
    <div class="card stat-card">
        <div class="stat-value">{{ stats.idle_devices }}</div>
        <div class="stat-label">空闲设备</div>
    </div>
    <div class="card stat-card">
        <div class="stat-value">{{ stats.running_tasks }}</div>
        <div class="stat-label">运行中任务</div>
    </div>
    <div class="card stat-card">
        <div class="stat-value">{{ stats.today_tasks }}</div>
        <div class="stat-label">今日任务</div>
    </div>
</div>

<div class="grid grid-cols-2" style="margin-top: 2rem;">
    <div class="card">
        <div class="card-header">设备状态分布</div>
        <table class="table">
            <thead>
                <tr>
                    <th>状态</th>
                    <th>数量</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><span class="status-badge status-idle">空闲</span></td>
                    <td>{{ stats.idle_devices }}</td>
                </tr>
                <tr>
                    <td><span class="status-badge status-busy">忙碌</span></td>
                    <td>{{ stats.busy_devices }}</td>
                </tr>
                <tr>
                    <td><span class="status-badge status-offline">离线</span></td>
                    <td>{{ stats.offline_devices }}</td>
                </tr>
                <tr>
                    <td><span class="status-badge status-quarantined">隔离</span></td>
                    <td>{{ stats.quarantined_devices }}</td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="card">
        <div class="card-header">最近任务</div>
        <table class="table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>设备</th>
                    <th>状态</th>
                    <th>结果</th>
                </tr>
            </thead>
            <tbody>
                {% for run in recent_runs %}
                <tr>
                    <td><a href="/runs/{{ run.id }}">#{{ run.id }}</a></td>
                    <td>{{ run.device_serial }}</td>
                    <td><span class="status-badge status-{{ run.status }}">{{ run.status }}</span></td>
                    <td>{{ run.result or '-' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 2: 创建 Web 路由**

```python
# app/api/web.py
"""Web 页面路由。"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.models.device import Device, DeviceStatus
from app.models.run import RunSession, RunStatus

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """仪表盘首页。"""
    # 统计数据
    total_devices = db.query(Device).count()
    idle_devices = db.query(Device).filter(Device.status == DeviceStatus.IDLE).count()
    busy_devices = db.query(Device).filter(Device.status == DeviceStatus.BUSY).count()
    offline_devices = db.query(Device).filter(Device.status == DeviceStatus.OFFLINE).count()
    quarantined_devices = db.query(Device).filter(Device.status == DeviceStatus.QUARANTINED).count()

    running_tasks = db.query(RunSession).filter(
        RunSession.status.in_([RunStatus.RUNNING, RunStatus.VALIDATING])
    ).count()

    # 今日任务
    today = datetime.utcnow().date()
    today_tasks = db.query(RunSession).filter(
        func.date(RunSession.created_at) == today
    ).count()

    # 最近任务
    recent_runs = db.query(RunSession).order_by(
        RunSession.created_at.desc()
    ).limit(5).all()

    stats = {
        "total_devices": total_devices,
        "idle_devices": idle_devices,
        "busy_devices": busy_devices,
        "offline_devices": offline_devices,
        "quarantined_devices": quarantined_devices,
        "running_tasks": running_tasks,
        "today_tasks": today_tasks,
    }

    # 格式化最近任务
    runs_data = [
        {
            "id": r.id,
            "device_serial": r.device.serial if r.device else "-",
            "status": r.status.value,
            "result": r.result,
        }
        for r in recent_runs
    ]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "recent_runs": runs_data,
        }
    )


@router.get("/devices", response_class=HTMLResponse)
async def devices_page(request: Request, db: Session = Depends(get_db)):
    """设备列表页面。"""
    devices = db.query(Device).order_by(Device.last_seen_at.desc()).all()

    devices_data = [
        {
            "id": d.id,
            "serial": d.serial,
            "brand": d.brand or "-",
            "model": d.model or "-",
            "android_version": d.android_version or "-",
            "status": d.status.value,
            "battery_level": d.battery_level,
            "health_score": d.health_score,
            "tags": d.get_tags(),
            "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else "-",
        }
        for d in devices
    ]

    return templates.TemplateResponse(
        "devices.html",
        {"request": request, "devices": devices_data}
    )


@router.get("/runs", response_class=HTMLResponse)
async def runs_page(request: Request, db: Session = Depends(get_db)):
    """任务列表页面。"""
    runs = db.query(RunSession).order_by(RunSession.created_at.desc()).limit(50).all()

    runs_data = [
        {
            "id": r.id,
            "plan_name": r.plan.name if r.plan else "-",
            "device_serial": r.device.serial if r.device else "-",
            "status": r.status.value,
            "result": r.result or "-",
            "started_at": r.started_at.isoformat() if r.started_at else "-",
            "ended_at": r.ended_at.isoformat() if r.ended_at else "-",
            "duration": r.get_duration_seconds() or "-",
            "failure_category": r.failure_category or "-",
        }
        for r in runs
    ]

    return templates.TemplateResponse(
        "runs.html",
        {"request": request, "runs": runs_data}
    )


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail_page(
    request: Request,
    run_id: int,
    db: Session = Depends(get_db),
):
    """任务详情页面。"""
    run = db.query(RunSession).filter_by(id=run_id).first()

    if not run:
        return templates.TemplateResponse(
            "base.html",
            {"request": request},
            status_code=404
        )

    # 获取执行步骤
    steps = db.query(RunSession).filter_by(run_id=run_id).all() if hasattr(run, 'steps') else []

    run_data = {
        "id": run.id,
        "plan_name": run.plan.name if run.plan else "-",
        "device_serial": run.device.serial if run.device else "-",
        "status": run.status.value,
        "result": run.result or "-",
        "started_at": run.started_at.isoformat() if run.started_at else "-",
        "ended_at": run.ended_at.isoformat() if run.ended_at else "-",
        "duration": run.get_duration_seconds() or "-",
        "failure_category": run.failure_category or "-",
        "summary": run.summary or "-",
    }

    return templates.TemplateResponse(
        "run_detail.html",
        {"request": request, "run": run_data, "steps": steps}
    )


@router.get("/runs/create", response_class=HTMLResponse)
async def create_run_page(request: Request, db: Session = Depends(get_db)):
    """创建任务页面。"""
    from app.models.run import UpgradePlan

    plans = db.query(UpgradePlan).all()
    devices = db.query(Device).filter(Device.status == DeviceStatus.IDLE).all()

    return templates.TemplateResponse(
        "create_run.html",
        {
            "request": request,
            "plans": plans,
            "devices": devices,
        }
    )
```

- [ ] **Step 3: 更新 main.py 添加 Web 路由**

```python
# 在 app/main.py 中添加

from app.api.web import router as web_router

app.include_router(web_router, tags=["web"])
```

- [ ] **Step 4: 提交**

```bash
git add app/templates/dashboard.html app/api/web.py app/main.py
git commit -m "feat: add dashboard page and web routes"
```

---

## Task 7.3: 设备和任务页面

**Files:**
- Create: `app/templates/devices.html`
- Create: `app/templates/runs.html`
- Create: `app/templates/run_detail.html`
- Create: `app/templates/create_run.html`

- [ ] **Step 1: 创建设备列表模板**

```html
<!-- app/templates/devices.html -->
{% extends "base.html" %}

{% block title %}设备管理 - AegisOTA{% endblock %}

{% block content %}
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
    <h1>设备管理</h1>
    <button class="btn btn-primary" hx-post="/api/devices/sync" hx-swap="innerHTML" hx-target="#device-list">
        同步设备
    </button>
</div>

<div id="device-list" class="card">
    <table class="table">
        <thead>
            <tr>
                <th>序列号</th>
                <th>品牌/型号</th>
                <th>Android 版本</th>
                <th>状态</th>
                <th>电量</th>
                <th>健康度</th>
                <th>最后在线</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
            {% for device in devices %}
            <tr>
                <td><strong>{{ device.serial }}</strong></td>
                <td>{{ device.brand }} {{ device.model }}</td>
                <td>{{ device.android_version }}</td>
                <td>
                    <span class="status-badge status-{{ device.status }}">{{ device.status }}</span>
                </td>
                <td>{{ device.battery_level }}%</td>
                <td>{{ device.health_score }}%</td>
                <td>{{ device.last_seen_at }}</td>
                <td>
                    {% if device.status == 'quarantined' %}
                    <button class="btn btn-sm btn-primary" hx-post="/api/devices/{{ device.serial }}/recover" hx-swap="outerHTML" hx-target="closest tr">
                        恢复
                    </button>
                    {% elif device.status == 'idle' %}
                    <button class="btn btn-sm btn-danger" hx-post="/api/devices/{{ device.serial }}/quarantine" hx-vals='{"reason": "手动隔离"}' hx-swap="outerHTML" hx-target="closest tr">
                        隔离
                    </button>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 2: 创建任务列表模板**

```html
<!-- app/templates/runs.html -->
{% extends "base.html" %}

{% block title %}任务列表 - AegisOTA{% endblock %}

{% block content %}
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
    <h1>任务列表</h1>
    <a href="/runs/create" class="btn btn-primary">创建任务</a>
</div>

<div class="card">
    <table class="table">
        <thead>
            <tr>
                <th>ID</th>
                <th>升级计划</th>
                <th>设备</th>
                <th>状态</th>
                <th>结果</th>
                <th>耗时</th>
                <th>创建时间</th>
                <th>操作</th>
            </tr>
        </thead>
        <tbody>
            {% for run in runs %}
            <tr>
                <td><a href="/runs/{{ run.id }}"><strong>#{{ run.id }}</strong></a></td>
                <td>{{ run.plan_name }}</td>
                <td>{{ run.device_serial }}</td>
                <td>
                    <span class="status-badge status-{{ run.status }}">{{ run.status }}</span>
                </td>
                <td>{{ run.result }}</td>
                <td>{{ run.duration }}s</td>
                <td>{{ run.started_at }}</td>
                <td>
                    <a href="/runs/{{ run.id }}" class="btn btn-sm btn-secondary">详情</a>
                    {% if run.status in ['queued', 'reserved', 'running'] %}
                    <button class="btn btn-sm btn-danger" hx-post="/api/runs/{{ run.id }}/abort" hx-swap="outerHTML" hx-target="closest tr">
                        终止
                    </button>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 3: 创建任务详情模板**

```html
<!-- app/templates/run_detail.html -->
{% extends "base.html" %}

{% block title %}任务 #{{ run.id }} - AegisOTA{% endblock %}

{% block content %}
<h1>任务 #{{ run.id }}</h1>

<div class="grid grid-cols-2" style="margin-top: 2rem;">
    <div class="card">
        <div class="card-header">基本信息</div>
        <table class="table">
            <tr>
                <th>升级计划</th>
                <td>{{ run.plan_name }}</td>
            </tr>
            <tr>
                <th>设备</th>
                <td>{{ run.device_serial }}</td>
            </tr>
            <tr>
                <th>状态</th>
                <td><span class="status-badge status-{{ run.status }}">{{ run.status }}</span></td>
            </tr>
            <tr>
                <th>结果</th>
                <td>{{ run.result }}</td>
            </tr>
            <tr>
                <th>开始时间</th>
                <td>{{ run.started_at }}</td>
            </tr>
            <tr>
                <th>结束时间</th>
                <td>{{ run.ended_at }}</td>
            </tr>
            <tr>
                <th>执行时长</th>
                <td>{{ run.duration }} 秒</td>
            </tr>
            {% if run.failure_category != '-' %}
            <tr>
                <th>失败分类</th>
                <td>{{ run.failure_category }}</td>
            </tr>
            {% endif %}
        </table>
    </div>

    <div class="card">
        <div class="card-header">操作</div>
        <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
            <a href="/api/reports/{{ run.id }}/html" class="btn btn-primary" target="_blank">
                查看 HTML 报告
            </a>
            <a href="/api/reports/{{ run.id }}/markdown" class="btn btn-secondary" target="_blank">
                下载 Markdown
            </a>
            <a href="/api/reports/{{ run.id }}/artifacts" class="btn btn-secondary" target="_blank">
                查看产物
            </a>
        </div>

        {% if run.summary != '-' %}
        <div style="margin-top: 1.5rem;">
            <h3>摘要</h3>
            <p>{{ run.summary }}</p>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

- [ ] **Step 4: 创建创建任务模板**

```html
<!-- app/templates/create_run.html -->
{% extends "base.html" %}

{% block title %}创建任务 - AegisOTA{% endblock %}

{% block content %}
<h1>创建升级任务</h1>

<div class="card" style="max-width: 600px; margin-top: 2rem;">
    <form hx-post="/api/runs" hx-swap="innerHTML" hx-target="#result">
        <div class="form-group">
            <label class="form-label">升级计划</label>
            <select name="plan_id" class="form-select" required>
                <option value="">请选择升级计划</option>
                {% for plan in plans %}
                <option value="{{ plan.id }}">{{ plan.name }} ({{ plan.upgrade_type.value }})</option>
                {% endfor %}
            </select>
        </div>

        <div class="form-group">
            <label class="form-label">设备（可选，留空自动分配）</label>
            <select name="device_serial" class="form-select">
                <option value="">自动分配</option>
                {% for device in devices %}
                <option value="{{ device.serial }}">{{ device.serial }} ({{ device.brand }} {{ device.model }})</option>
                {% endfor %}
            </select>
        </div>

        <button type="submit" class="btn btn-primary" style="margin-top: 1rem;">
            创建任务
        </button>
    </form>

    <div id="result" style="margin-top: 1rem;"></div>
</div>
{% endblock %}
```

- [ ] **Step 5: 提交**

```bash
git add app/templates/devices.html app/templates/runs.html app/templates/run_detail.html app/templates/create_run.html
git commit -m "feat: add devices, runs, and create run page templates"
```

---

## Task 7.4: 项目文档

**Files:**
- Create: `README.md`
- Create: `docs/architecture.md`

- [ ] **Step 1: 创建 README**

```markdown
# AegisOTA

安卓 OTA 升级异常注入与多机验证平台

## 项目简介

AegisOTA 是一个面向测试开发场景的安卓系统升级异常注入与多机验证平台。它将原本分散在脚本、人工经验、机房操作中的升级测试流程，收敛为一套可配置、可执行、可追踪、可复盘的平台。

### 核心功能

- **升级流程编排**: 支持全量升级、增量 patch、失败回滚、升级后验证四类任务模板
- **异常注入**: 支持电量不足、存储压力、下载中断、校验失败、重启打断、升级后 Monkey 压测等场景
- **多机管理**: 设备注册、标签分组、占用租约、健康检查、故障隔离
- **结果归因**: 任务时间线、失败分类、设备统计、报告导出

## 技术栈

- **语言**: Python 3.10+
- **Web 框架**: FastAPI
- **数据库**: SQLite + SQLAlchemy
- **CLI**: Typer
- **前端**: Jinja2 + HTMX

## 快速开始

### 安装

```bash
pip install -e ".[dev]"
```

### 启动服务

```bash
# 启动 Web 服务
uvicorn app.main:app --reload

# 启动 Worker
labctl worker start
```

### 使用 CLI

```bash
# 同步设备
labctl device sync

# 列出设备
labctl device list

# 创建升级计划
labctl run create-plan --name "测试升级" --type full --package /tmp/update.zip

# 提交任务
labctl run submit <plan_id>

# 查看任务状态
labctl run list

# 导出报告
labctl report export <run_id> --format html
```

## 项目结构

```
app/
├── api/           # FastAPI 端点
├── models/        # SQLAlchemy 数据模型
├── services/      # 业务逻辑层
├── executors/     # 命令执行器
├── faults/        # 异常注入插件
├── validators/    # 升级后验证器
├── reporting/     # 报告生成
├── templates/     # Jinja2 模板
├── static/        # 静态文件
├── cli/           # Typer CLI 命令
tests/             # 测试用例
artifacts/         # 执行产物
```

## 核心设计

### 状态机

任务状态转换:
```
queued -> reserved -> running -> validating -> passed/failed/aborted/quarantined
```

执行阶段:
```
precheck -> push_package -> apply_update -> reboot_wait -> post_validate
```

### 异常注入

异常注入采用插件模式，每个插件实现 prepare/inject/cleanup 三阶段:

```python
class FaultPlugin:
    def prepare(self, context): ...
    def inject(self, context): ...
    def cleanup(self, context): ...
```

支持的异常类型:
- `storage_pressure`: 存储压力
- `download_interrupted`: 下载中断
- `reboot_interrupted`: 重启中断
- `monkey_after_upgrade`: 升级后 Monkey 测试

### 设备调度

- 单设备同一时刻只允许一个独占任务
- 设备租约机制防止并发冲突
- 异常设备自动进入隔离状态

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行覆盖率测试
pytest tests/ --cov=app --cov-report=html
```

## 许可证

MIT License
```

- [ ] **Step 2: 创建架构文档**

```markdown
# AegisOTA 系统架构

## 概述

AegisOTA 采用"控制面 + 执行面"架构:

- **控制面**: FastAPI 服务，负责设备管理、任务调度、报告生成、Web 展示
- **执行面**: Worker 进程 + Typer CLI，负责调用 ADB/Fastboot、执行升级、采集日志

## 核心模块

### 1. 设备管理模块

负责设备生命周期管理:

- 设备发现与注册
- 状态跟踪 (idle/busy/offline/quarantined)
- 健康检查 (电量、存储、启动状态)
- 标签管理
- 租约机制

### 2. 任务编排模块

负责任务状态机驱动:

- 任务创建与排队
- 设备分配与预留
- 阶段执行 (precheck -> apply -> reboot -> validate)
- 超时处理与人工终止

### 3. 异常注入模块

负责模拟故障场景:

- 插件模式设计
- 三阶段生命周期 (prepare/inject/cleanup)
- 支持多触发点 (precheck/apply_update/post_validate)

### 4. 报告模块

负责任务归因:

- 失败分类 (package_issue/device_env_issue/boot_failure 等)
- 时间线生成
- HTML/Markdown 报告输出

## 数据模型

```
Device (设备)
├── id, serial, brand, model
├── status, health_score, battery_level
└── tags, last_seen_at

DeviceLease (设备租约)
├── device_id, run_id
└── leased_at, expired_at, lease_status

UpgradePlan (升级计划)
├── name, upgrade_type, package_path
├── fault_profile_id
└── device_selector, parallelism

RunSession (任务会话)
├── plan_id, device_id, status
├── started_at, ended_at
└── result, failure_category

RunStep (执行步骤)
├── run_id, step_name, step_order
├── status, command
└── stdout_path, stderr_path

Artifact (产物)
├── run_id, artifact_type
└── path, size, metadata
```

## 接口设计

### REST API

- `POST /api/runs` - 创建任务
- `GET /api/runs/{id}` - 查询任务
- `POST /api/runs/{id}/abort` - 终止任务
- `GET /api/devices` - 列出设备
- `POST /api/devices/{id}/quarantine` - 隔离设备
- `GET /api/reports/{id}` - 获取报告

### CLI 命令

- `labctl device sync/list/quarantine/recover`
- `labctl run submit/list/abort`
- `labctl report export`
- `labctl worker start/status`

## 设计决策

1. **SQLite 而非 PostgreSQL**: 项目重点是平台设计和流程编排，不是数据库高并发
2. **Jinja2 + HTMX 而非 SPA**: Web 只是展示层，不引入前后端分离复杂度
3. **单机 Worker 而非 Celery**: 单机调度足以证明设计，不需要分布式复杂度
4. **插件模式异常注入**: 灵活扩展，每个异常独立封装
```

- [ ] **Step 3: 提交**

```bash
git add README.md docs/architecture.md
git commit -m "docs: add README and architecture documentation"
```

---

## Phase 7 完成检查

启动服务验证:

Run: `uvicorn app.main:app --reload`
Expected: Web 服务正常启动，访问 http://localhost:8000 可看到仪表盘

Run: `labctl --help`
Expected: CLI 帮助信息正常显示

---

## 全项目验收

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass

Run: `labctl device sync`
Expected: 设备同步命令执行成功

Run: `labctl run list`
Expected: 任务列表显示正常

---

完成！AegisOTA 项目已完整实现。