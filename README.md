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