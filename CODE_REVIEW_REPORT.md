# AegisOTA 项目代码审查报告

**审查日期：** 2026-04-26
**审查范围：** `app/cli/`、`app/models/`、`app/api/`、`app/utils/`、`app/main.py`、`app/config.py`、`app/database.py` 及相关配置文件
**前置参考：** 已有 CODE_REVIEW.md 报告，本次审查在此基础上补充发现
**审查工具：** OpenCode + superpowers/requesting-code-review Skill

---

## 一、审查范围

| 模块 | 文件数 | 说明 |
|------|--------|------|
| `app/cli/` | 7 | labctl CLI 全部命令（device, run, report, worker, pool, seed） |
| `app/models/` | 9 | 12 个 SQLAlchemy 模型 + 15+ 枚举定义 |
| `app/api/` | 8 | ~50 个 API/Web 路由 + schema 定义 |
| `app/utils/` | 3 | 日志工具（logging）、事务工具（transaction） |
| 配置与入口 | 3 | config.py, main.py, database.py |

---

## 二、发现的问题

### 高风险（P0）

**P0-1: CSRF 中间件对无 header 的写请求不拦截（已部分修复）**
- 位置：`app/main.py:58-66`
- 当前逻辑：`if not header_token or not cookie_token or cookie_token != header_token` → 403
- **状态：已修复。** 相比前版报告（指出"有 header 才校验"），当前代码在所有不带 header 的场景下都会返回 403，逻辑正确。
- **残余风险：** CSRF cookie 仍 `httponly=False` + 无 `secure=True`，XSS 可窃取 token 后伪造请求。

**P0-2: Worker CLI 缺少 `try/finally` DB 会话保护**
- 位置：`app/cli/worker.py:39-73`, `79-88`, `94-105`
- `db.close()` 仅在正常路径执行。若 `WorkerService` 抛出异常，会话泄漏。
- 对比 `device.py`、`pool.py`、`run.py` 全部使用 `try...finally: db.close()`，`worker.py` 是唯一遗漏的模块。

**P0-3: `worker.py` 类型注解错误**
- 位置：`app/cli/worker.py:13`
- `_worker: WorkerService = None` 应为 `Optional[WorkerService] = None`。在严格类型检查下会报错。

**P0-4: `pool.py` CLI 输出语言为英文，违反项目规范**
- 位置：`app/cli/pool.py` 整个文件
- AGENTS.md 明确规定："Prefer Chinese docstrings and user-facing text"。`pool.py` 是唯一使用英文输出的 CLI 模块（"Device Pools", "No pools found", "Invalid purpose" 等），与其他所有 CLI（中文）不一致。

**P0-5: 诊断报告中未转义的数据直接拼接 HTML/Markdown**
- 位置：`app/api/diagnosis.py:460-529` (`_generate_markdown_report`)
- `result.device_serial`, `result.root_cause`, `result.category` 等字段直接通过 f-string 插入 Markdown/HTML。`devices.py` 有 `_e()` 转义函数，但 `diagnosis.py` 和 `web.py` 中的 HTML 拼接没有使用。
- 尽管 `devices.py:3` 已导入 `html as html_module` 并定义了 `_e()`，该保护未扩展到诊断报告生成链路。

### 中风险（P1）

**P1-1: `FaultProfile.enabled` 映射为 `Integer` 而非 `Boolean`**
- 位置：`app/models/fault.py:59`
- 类型注解为 `bool`，实际列类型为 `Integer`。所有其他模型使用 `Boolean`，不一致。

**P1-2: 多处 `back_populates` 缺失导致关系孤立**
- 位置：`app/models/artifact.py:65`, `app/models/diagnostic.py:69, 129, 339`
- `Artifact.step`, `NormalizedEvent.run_session`, `DiagnosticResult.run_session`, `SimilarCaseIndex.run_session` 都定义了 `relationship()` 但未配对 `back_populates`。

**P1-3: `confidence` 和 `health_score` 无数据库级范围约束**
- 位置：`app/models/diagnostic.py:112`, `app/models/device.py:90`
- `confidence` (Float) 无 `[0.0, 1.0]` 约束；`health_score` (Integer) 无 `[0, 100]` 约束。

**P1-4: 路由层大量内联 import 语句**
- 位置：`app/api/devices.py:129`, `app/api/diagnosis.py:442`, `app/api/web.py:211-402`（9+ 处）
- `datetime`, `HTTPException`, `defaultdict` 等标准库/框架类在函数体内 import。虽然有避免循环引用的合理性，但多数应该提到模块级别。

**P1-5: `RunService.update_run_step` 使用字符串而非枚举**
- 位置：`app/services/run_service.py:298-301`
- `status == "running"` 和 `status in ("success", "failed")` 硬编码字符串。虽然与 `StepStatus` 枚举值一致，但类型安全性为零，容易引入拼写 bug。

**P1-6: `CommandRunner` 对字符串命令使用 `shell=True`**
- 位置：`app/executors/command_runner.py:103`
- 虽然 ADBExecutor 主要传 list，但该入口仍接受字符串命令。若未来扩展代码传入不受控字符串，将引入命令注入风险。

**P1-7: SQLite 下行级锁 (`with_for_update`) 语义不可靠**
- 位置：`app/services/scheduler_service.py:34-36`
- 代码注释声称使用 `SELECT FOR UPDATE` 防并发竞态，但 SQLite 对行级锁支持极为有限。多 worker 并发时仍可能重复分配设备。

### 低风险（P2）

**P2-1: `app/api/schemas.py` 中 `ErrorResponse` / `SuccessResponse` 从未使用**
- 位置：`app/api/schemas.py:102-124`
- 定义了通用响应模型，但所有路由手写 dict 或 Pydantic 模型。应统一或移除。

**P2-2: `get_db()` 缺少返回类型注解**
- 位置：`app/database.py:20-26`
- 应为 `def get_db() -> Generator[Session, None, None]`。

**P2-3: `ResultStatus` 枚举未导出**
- 位置：`app/models/enums.py:97-103`
- 定义了 `ResultStatus` 枚举，但 `__init__.py` 中未导出，外部模块无法通过 `app.models.enums` 访问。

**P2-4: `ContextLogger._log` 丢失调用栈位置信息**
- 位置：`app/utils/logging.py:125-136`
- `makeRecord()` 使用 `fn=None, lno=0, func=None`，导致所有日志记录没有正确的文件名、行号、函数名。

**P2-5: 多个模块的 `__init__.py` 为空**
- 位置：`app/cli/__init__.py`, `app/api/__init__.py`
- 建议至少添加模块文档或 `__all__` 导出列表。

**P2-6: CSRF token 生成函数在 3 处重复定义**
- 位置：`app/main.py:178`, `app/api/web.py:29`, `app/api/settings.py:22`
- 3 个相同的 `get_csrf_token()` 函数。应提取到 `app/utils/csrf.py`。

**P2-7: `StructuredFormatter` 中每行都 `import json`**
- 位置：`app/utils/logging.py:51`
- `import json` 放在 `format()` 方法内部，每次日志调用都会执行。应提升到模块级别。

**P2-8: `build_fingerprint` 和 `source_build`/`target_build` 可能截断**
- 位置：`app/models/device.py:84`, `app/models/run.py:88-89`
- `String(256)` 对于 Android build fingerprint 可能不够（常见超过 256 字符）。

---

## 三、风险等级汇总

| 等级 | 数量 | 概要 |
|------|------|------|
| **P0 高** | 5 | Worker DB 泄漏、HTML XSS 未转义、类型错误、CLI 语言不一致 |
| **P1 中** | 7 | Boolean 映射错误、关系孤立、无范围约束、shell=True、SQLite 锁不可靠 |
| **P2 低** | 8 | 未用 schema、缺类型注解、重复代码、日志栈丢失、空 init 文件 |

---

## 四、修复建议

### P0 修复（立即处理）

1. **Worker CLI 补充 try/finally**：`app/cli/worker.py` 三个函数全部改为 `try: ... finally: db.close()` 模式，与 `device.py`/`pool.py` 保持一致。
2. **修复类型注解**：`worker.py:13` 改为 `_worker: Optional[WorkerService] = None` 并导入 `Optional`。
3. **扩展 HTML 转义到诊断报告**：在 `diagnosis.py` 中引入 `_e()` 函数（或直接 import `app.api.devices._e`），对 `_generate_markdown_report` 和 `_generate_html_report` 中所有用户数据调用转义。
4. **统一 pool CLI 为中文输出**：将 `pool.py` 中所有英文 UI 文本改为中文，匹配 AGENTS.md 规范。
5. **CSRF cookie 加 `secure` 标志**：`main.py:73-79` 增加 `secure=not settings.DEBUG`，在非 debug 环境强制 HTTPS 传输。

### P1 修复（短期）

6. **`FaultProfile.enabled` 改为 `Boolean`**：`fault.py:59` 将 `Integer` 换为 `Boolean`。
7. **补充 `back_populates` 或移除孤立关系**：为 `artifact.py`, `diagnostic.py` 中所有 relationship 补齐反向声明，或降级为单向查询。
8. **添加 CheckConstraint 约束**：`confidence` 加 `[0, 1]` 检查；`health_score` 加 `[0, 100]` 检查。
9. **将内联 import 提升到模块级**：`datetime`, `HTTPException`, `defaultdict` 等标准引用移到文件顶。
10. **`update_run_step` 使用 `StepStatus` 枚举**：将 `status == "running"` 改为 `status == StepStatus.RUNNING.value`。
11. **SQLite 锁文档说明**：在 `scheduler_service.py` 注释中标明 SQLite 行级锁的限制，建议生产环境迁移到 PostgreSQL。

### P2 修复（中期）

12. **统一响应 schema**：启用 `schemas.py` 中的 `ErrorResponse` / `SuccessResponse`，或移除未使用的定义。
13. **提取公共 CSRF 工具函数**：新建 `app/utils/csrf.py`，三处调用改为统一引用。
14. **修复 `ContextLogger` 栈信息**：使用 `stack_info=True` 或 `self._logger._log()` 替代手动 `makeRecord()`。
15. **`import json` 提升模块级**：`logging.py:51` 移到文件顶部。
16. **增加字符串长度**：`build_fingerprint` 从 256 提升到 512。

---

## 五、与前次 CODE_REVIEW.md 对比

前次报告（CODE_REVIEW.md）中标注的 8 项 P0 问题中，已修复 5 项：

| P0 # | 前次描述 | 状态 |
|------|---------|------|
| 1 | CSRF "有 header 才校验" | ✅ 已修复，无条件要求 header |
| 2 | `assigned_device_serial` 不存在 | ✅ 已修复，改用 `run_session.device.serial` |
| 3 | `func.case` 报错 | ✅ 已修复，改为 `case` (from sqlalchemy) |
| 4 | RunExecutor timeline 顺序 | ✅ 已修复，先记 `run_end` 再写文件 |
| 5 | Worker 跨线程复用 Session | ✅ 已修复，`_run_loop` 内创建独立 `SessionLocal()` |
| 6 | SQLite 行级锁不可靠 | ⚠️ 仍然存在，需文档标注或迁移 |
| 7 | ALLOCATING 路径不完整 | ⚠️ 仍然存在于 scheduler_service.py |
| 8 | 设备隔离保留 `current_run_id` | ⚠️ 仍需审查 device_service.py |
