# TraceLens 日志分析功能集成设计

## 概述

将 TraceLens 的日志分析能力完整集成到 AegisOTA，实现从"执行平台"到"执行+诊断平台"的升级。所有任务完成后自动从设备导出日志并触发分析。

## 集成目标

1. **自动日志导出**：任务完成后自动从设备拉取 recovery.log、update_engine.log、logcat 等日志
2. **多源日志解析**：支持 recovery、update_engine、logcat、monkey 等多种日志格式
3. **规则驱动诊断**：基于 YAML 定义的诊断规则进行故障分类和根因定位
4. **相似案例召回**：基于 RapidFuzz 搜索历史相似案例
5. **诊断报告生成**：生成包含证据链、置信度、建议操作的诊断报告
6. **独立诊断页面**：任务详情页简化展示，独立页面详细展示并支持 SN 搜索

---

## 模块架构

### 新增目录结构

```
app/
├── parsers/                    # 日志解析器模块
│   ├── __init__.py
│   ├── base.py                 # BaseParser 抽象基类
│   ├── recovery_parser.py      # recovery.log 和 last_install.txt 解析
│   ├── update_engine_parser.py # update_engine.log 解析
│   ├── logcat_parser.py        # Android logcat 解析
│   ├── monkey_parser.py        # Monkey 测试输出解析
│   └── normalizer.py           # 事件标准化器
│
├── diagnosis/                   # 诊断引擎模块
│   ├── __init__.py
│   ├── engine.py               # 规则匹配引擎
│   ├── loader.py               # YAML 规则加载器
│   ├── confidence.py           # 置信度计算器
│   └── similar.py              # 相似案例召回服务
│
├── services/
│   ├── log_export_service.py   # 设备日志导出服务
│   ├── diagnosis_service.py    # 诊断执行服务
│   └── ...existing services...
│
├── models/
│   ├── diagnostic.py           # 诊断相关数据模型
│   └── ...existing models...
│
├── api/
│   ├── diagnosis.py            # 诊断 API 路由
│   └── ...existing api...
│
├── rules/                      # 诊断规则定义
│   └── core_rules.yaml         # 核心诊断规则
│
└── templates/
    ├── diagnosis.html          # 诊断列表页
    ├── diagnosis_detail.html   # 诊断详情页
    └── ...existing templates...
```

---

## 数据模型设计

### NormalizedEvent（标准化事件）

解析后的日志事件，统一格式存储。

```python
class NormalizedEvent(Base):
    """标准化事件。"""
    __tablename__ = "normalized_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("run_sessions.id"), nullable=False, index=True)
    
    # 来源信息
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # recovery_log/update_engine/logcat/monkey
    
    # 事件属性
    stage: Mapped[str] = mapped_column(String(32), nullable=False)        # precheck/apply_update/reboot_wait/post_validate
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)   # error_signal/status_transition/progress_signal
    severity: Mapped[str] = mapped_column(String(16), nullable=False)     # info/warning/error/critical
    normalized_code: Mapped[str] = mapped_column(String(64), nullable=False)  # 标准化错误码，如 RECOVERY_LOW_BATTERY
    
    # 原始数据
    raw_line: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # 扩展数据
    kv_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 存储额外键值对
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

### DiagnosticResult（诊断结果）

诊断执行的最终结果。

```python
class DiagnosticResult(Base):
    """诊断结果。"""
    __tablename__ = "diagnostic_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("run_sessions.id"), nullable=False, unique=True, index=True)
    device_serial: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # 诊断结论
    stage: Mapped[str] = mapped_column(String(32), nullable=False)         # 失败阶段
    category: Mapped[str] = mapped_column(String(32), nullable=False)      # 故障分类
    root_cause: Mapped[str] = mapped_column(String(64), nullable=False)     # 根因标识
    confidence: Mapped[float] = mapped_column(Float, nullable=False)       # 置信度 0.0-1.0
    result_status: Mapped[str] = mapped_column(String(16), nullable=False) # passed/failed/transient_failure
    
    # 关键信息
    key_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 数组，关键日志行
    next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # 相似案例
    similar_cases: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 数组
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

### RuleHit（规则命中记录）

记录哪些规则被匹配，用于追溯诊断依据。

```python
class RuleHit(Base):
    """规则命中记录。"""
    __tablename__ = "rule_hits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("run_sessions.id"), nullable=False, index=True)
    result_id: Mapped[int] = mapped_column(Integer, ForeignKey("diagnostic_results.id"), nullable=False)
    
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(64), nullable=False)
    matched_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 数组
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    base_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

### DiagnosticRule（诊断规则）

可编辑的诊断规则定义。

```python
class DiagnosticRule(Base):
    """诊断规则。"""
    __tablename__ = "diagnostic_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 匹配条件
    match_all: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON 数组，全部匹配
    match_any: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # JSON 数组，任一匹配
    exclude_any: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON 数组，排除条件
    match_stage: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # JSON 数组，阶段匹配
    
    # 结论
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    root_cause: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    base_confidence: Mapped[float] = mapped_column(Float, default=0.8)
    next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

### SimilarCaseIndex（相似案例索引）

用于快速检索历史相似案例。

```python
class SimilarCaseIndex(Base):
    """相似案例索引。"""
    __tablename__ = "similar_case_index"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("run_sessions.id"), nullable=False, unique=True, index=True)
    device_serial: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    
    # 索引字段
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    root_cause: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    key_evidence_hash: Mapped[str] = mapped_column(String(64), nullable=True)  # MD5 哈希
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

---

## 核心流程

### 1. 任务完成自动触发流程

```
任务执行完成 (RunExecutor)
    │
    ├─ 状态变为 passed/failed/aborted
    │
    ├─ WorkerService._on_run_complete()
    │   │
    │   ├─ LogExportService.export_from_device(run_id, device_serial)
    │   │   │
    │   │   ├─ adb pull /cache/recovery/last_install
    │   │   ├─ adb pull /cache/recovery/log  
    │   │   ├─ adb logcat -d > logcat.txt
    │   │   ├─ adb pull /data/update_engine.log
    │   │   └─ adb shell getprop > device_info.txt
    │   │
    │   │   保存到 artifacts/{run_id}/logs/
    │   │
    │   └─ DiagnosisService.run_diagnosis(run_id)
    │       │
    │       ├─ 加载日志文件
    │       │
    │       ├─ 各解析器解析
    │       │   ├─ RecoveryParser.parse()
    │       │   ├─ UpdateEngineParser.parse()
    │       │   ├─ LogcatParser.parse()
    │       │   └─ MonkeyParser.parse()
    │       │
    │       ├─ Normalizer.normalize()
    │       │   └─ 生成 NormalizedEvent 记录
    │       │
    │       ├─ RuleEngine.match()
    │       │   ├─ 加载 DiagnosticRule
    │       │   ├─ 匹配规则
    │       │   ├─ 计算置信度
    │       │   └─ 生成 RuleHit 记录
    │       │
    │       ├─ SimilarCaseService.find_similar()
    │       │   └─ 检索相似历史案例
    │       │
    │       └─ 保存 DiagnosticResult
    │
    └─ 任务状态更新完成
```

### 2. 手动触发诊断流程

```
POST /api/diagnosis/{run_id}/run
    │
    ├─ 检查任务是否存在
    │
    ├─ 检查日志文件是否存在
    │   └─ 不存在则调用 LogExportService
    │
    ├─ 清理旧的诊断数据
    │   ├─ DELETE normalized_events WHERE run_id
    │   ├─ DELETE rule_hits WHERE run_id
    │   └─ DELETE diagnostic_results WHERE run_id
    │
    └─ 执行诊断流程（同上）
```

---

## API 端点设计

### 诊断相关 API

| 端点 | 方法 | 描述 | 请求/响应 |
|------|------|------|-----------|
| `/api/diagnosis` | GET | 诊断记录列表 | Query: `serial`, `category`, `page`; Response: 分页列表 |
| `/api/diagnosis/{run_id}` | GET | 获取诊断详情 | Response: DiagnosticResult + events |
| `/api/diagnosis/{run_id}/run` | POST | 手动触发诊断 | Response: `{"status": "started"}` |
| `/api/diagnosis/{run_id}/export` | GET | 导出诊断报告 | Query: `format=md/html`; Response: 文件下载 |
| `/api/diagnosis/export-logs/{run_id}` | POST | 从设备导出日志 | Response: 导出文件列表 |
| `/api/rules` | GET | 列出诊断规则 | Response: DiagnosticRule 列表 |
| `/api/rules` | POST | 创建规则 | Body: 规则定义; Response: 创建的规则 |
| `/api/rules/{rule_id}` | PUT | 更新规则 | Body: 更新字段; Response: 更新后的规则 |
| `/api/rules/import` | POST | 批量导入规则 | Body: YAML 文件; Response: 导入结果 |
| `/api/cases/search` | GET | 搜索相似案例 | Query: `category`, `root_cause`, `keywords` |

### 页面路由

| 路由 | 描述 |
|------|------|
| `/diagnosis` | 诊断列表页，支持 SN 搜索筛选 |
| `/diagnosis/{run_id}` | 诊断详情页 |

---

## 页面设计

### 任务详情页诊断展示

在现有 `run_detail.html` 中添加诊断摘要区块：

```html
<div class="card">
    <h2>诊断结果</h2>
    {% if diagnosis %}
    <div class="diagnosis-summary">
        <span class="status-badge">{{ diagnosis.category }}</span>
        <span>根因: {{ diagnosis.root_cause }}</span>
        <span>置信度: {{ (diagnosis.confidence * 100)|round }}%</span>
        <a href="/diagnosis/{{ run.id }}">查看详情</a>
    </div>
    {% else %}
    <p>暂无诊断结果</p>
    <button onclick="triggerDiagnosis({{ run.id }})">开始诊断</button>
    {% endif %}
</div>
```

### 独立诊断列表页 `/diagnosis`

**布局**：
- 顶部：搜索栏（设备 SN 输入框）、分类筛选下拉
- 中间：诊断记录表格
- 底部：分页控件

**表格列**：
| 列名 | 说明 |
|------|------|
| 任务ID | 可点击跳转到任务详情 |
| 设备SN | 显示设备序列号 |
| 故障分类 | 状态标签显示 |
| 根因 | 根因标识 |
| 置信度 | 百分比显示 |
| 诊断时间 | 时间戳 |
| 操作 | "查看详情"按钮 |

### 独立诊断详情页 `/diagnosis/{run_id}`

**布局**：

1. **诊断结果卡片**
   - 失败阶段
   - 故障分类
   - 根因
   - 置信度（进度条展示）
   - 建议下一步操作

2. **关键证据卡片**
   - 折叠式显示原始日志行
   - 高亮关键词
   - 支持展开/收起

3. **规则命中记录卡片**
   - 表格展示命中的规则
   - 显示规则名称、优先级、匹配的事件码

4. **相似案例卡片**
   - Top 3 历史相似案例
   - 显示相似度、分类、根因
   - 可点击跳转

5. **原始日志卡片**
   - Tab 切换不同日志源
   - 代码高亮显示
   - 支持下载

---

## 从 TraceLens 移植的代码

### 解析器模块

| TraceLens 源文件 | AegisOTA 目标文件 | 修改点 |
|------------------|-------------------|--------|
| `src/tracelens/parsers/base.py` | `app/parsers/base.py` | 无修改 |
| `src/tracelens/parsers/recovery.py` | `app/parsers/recovery_parser.py` | 模型引用改为 AegisOTA 模型 |
| `src/tracelens/parsers/update_engine.py` | `app/parsers/update_engine_parser.py` | 模型引用改为 AegisOTA 模型 |
| `src/tracelens/parsers/device.py` | `app/parsers/logcat_parser.py` + `monkey_parser.py` | 拆分为两个文件 |
| `src/tracelens/parsers/artifact.py` | `app/parsers/artifact_parser.py` | 可选，处理 JSON 产物 |

### 诊断引擎模块

| TraceLens 源文件 | AegisOTA 目标文件 | 修改点 |
|------------------|-------------------|--------|
| `src/tracelens/engine/rule.py` | 内联到 `app/diagnosis/engine.py` | 简化 |
| `src/tracelens/engine/loader.py` | `app/diagnosis/loader.py` | 适配 AegisOTA 数据库读取 |
| `src/tracelens/engine/engine.py` | `app/diagnosis/engine.py` | 模型引用改为 AegisOTA 模型 |

### 相似案例服务

| TraceLens 源文件 | AegisOTA 目标文件 | 修改点 |
|------------------|-------------------|--------|
| `src/tracelens/services/similar.py` | `app/diagnosis/similar.py` | 适配 AegisOTA 数据模型 |

### 规则定义

| TraceLens 源文件 | AegisOTA 目标文件 | 修改点 |
|------------------|-------------------|--------|
| `src/tracelens/rules/core_rules.yaml` | `app/rules/core_rules.yaml` | 无修改 |

### 数据模型适配

TraceLens 的 Pydantic 模型需要转换为 SQLAlchemy 模型，并与 AegisOTA 现有模型建立关联。

---

## 规则引擎设计

### YAML 规则格式

```yaml
- rule_id: R001
  name: low_battery_precheck_failure
  priority: 100
  enabled: true
  match_all:
    - RECOVERY_LOW_BATTERY
  match_stage:
    - precheck
  category: device_env_issue
  root_cause: low_battery
  base_confidence: 0.98
  next_action: 请将设备充电至阈值以上后重试

- rule_id: R002
  name: update_engine_error
  priority: 90
  enabled: true
  match_any:
    - UPDATE_ENGINE_DOWNLOAD_ERROR
    - UPDATE_ENGINE_VERIFY_ERROR
    - UPDATE_ENGINE_APPLY_ERROR
  match_stage:
    - apply_update
  category: package_issue
  root_cause: update_engine_failure
  base_confidence: 0.85
  next_action: 检查升级包完整性，必要时重新下载
```

### 置信度计算

```python
def calculate_confidence(rule: DiagnosticRule, events: List[NormalizedEvent]) -> float:
    """计算诊断置信度。"""
    base = rule.base_confidence
    
    # 阶段跨度加成：事件跨越多个阶段
    stages = set(e.stage for e in events)
    stage_bonus = min(0.1 * (len(stages) - 1), 0.2)
    
    # 多源加成：事件来自多个日志源
    sources = set(e.source_type for e in events)
    source_bonus = min(0.05 * (len(sources) - 1), 0.1)
    
    # 证据数量加成
    evidence_bonus = min(0.02 * len(events), 0.1)
    
    return min(base + stage_bonus + source_bonus + evidence_bonus, 1.0)
```

### 冲突解决

当多个规则同时匹配时：
1. **优先级优先**：高 priority 的规则优先
2. **阶段优先**：后阶段（如 post_validate）优先于前阶段（如 precheck）
3. **证据完整度优先**：匹配事件数多的优先

---

## 相似案例召回

### 索引策略

使用 key_evidence_hash（关键证据的 MD5 哈希）+ category + root_cause 作为索引键。

### 相似度计算

```python
from rapidfuzz import fuzz

def calculate_similarity(case1: SimilarCaseIndex, case2: SimilarCaseIndex) -> float:
    """计算案例相似度。"""
    # 分类相同
    if case1.category != case2.category:
        return 0.0
    
    # 根因相同加分
    root_cause_score = 0.5 if case1.root_cause == case2.root_cause else 0.0
    
    # 证据哈希相似度
    if case1.key_evidence_hash and case2.key_evidence_hash:
        evidence_score = fuzz.ratio(case1.key_evidence_hash, case2.key_evidence_hash) / 100 * 0.5
    else:
        evidence_score = 0.0
    
    return root_cause_score + evidence_score
```

---

## 日志导出服务

### 从设备导出的日志

| 日志类型 | 设备路径 | 导出命令 |
|----------|----------|----------|
| recovery.log | `/cache/recovery/log` | `adb pull /cache/recovery/log` |
| last_install.txt | `/cache/recovery/last_install` | `adb pull /cache/recovery/last_install` |
| logcat | 内存缓冲 | `adb logcat -d` |
| update_engine.log | `/data/misc/update_engine_log/` | `adb pull /data/misc/update_engine_log/` |
| device_info | getprop | `adb shell getprop` |

### 导出服务实现

```python
class LogExportService:
    """设备日志导出服务。"""
    
    def __init__(self, db: Session, adb_executor: ADBExecutor):
        self.db = db
        self.adb = adb_executor
    
    def export_from_device(self, run_id: int, device_serial: str) -> List[str]:
        """从设备导出日志到任务产物目录。"""
        artifact_dir = Path(f"artifacts/{run_id}/logs")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        exported_files = []
        
        # 导出 recovery 日志
        for src, dst in [
            ("/cache/recovery/log", "recovery.log"),
            ("/cache/recovery/last_install", "last_install.txt"),
        ]:
            result = self.adb.pull(device_serial, src, str(artifact_dir / dst))
            if result.exit_code == 0:
                exported_files.append(dst)
        
        # 导出 logcat
        logcat_path = artifact_dir / "logcat.txt"
        result = self.adb.logcat(device_serial, output_path=str(logcat_path))
        if result.exit_code == 0:
            exported_files.append("logcat.txt")
        
        # 导出 update_engine 日志
        result = self.adb.pull(device_serial, "/data/misc/update_engine_log/", str(artifact_dir))
        if result.exit_code == 0:
            exported_files.append("update_engine.log")
        
        # 导出设备信息
        result = self.adb.get_device_snapshot(device_serial)
        if result:
            with open(artifact_dir / "device_info.json", "w") as f:
                json.dump(result, f, indent=2)
            exported_files.append("device_info.json")
        
        # 保存产物记录
        for filename in exported_files:
            artifact = Artifact(
                run_id=run_id,
                artifact_type="log",
                file_path=str(artifact_dir / filename),
            )
            self.db.add(artifact)
        self.db.commit()
        
        return exported_files
```

---

## 实施任务清单

### Phase 1: 基础设施（数据模型 + 解析器）

1. 创建数据库模型（NormalizedEvent, DiagnosticResult, RuleHit, DiagnosticRule, SimilarCaseIndex）
2. 移植 TraceLens 解析器代码
3. 移植事件标准化器
4. 编写解析器单元测试

### Phase 2: 诊断引擎

5. 移植规则加载器
6. 移植规则引擎
7. 移植置信度计算
8. 移植相似案例服务
9. 导入核心诊断规则
10. 编写诊断引擎测试

### Phase 3: 服务集成

11. 实现 LogExportService
12. 实现 DiagnosisService
13. 集成到 WorkerService 任务完成流程
14. 编写集成测试

### Phase 4: API 和页面

15. 实现诊断 API 路由
16. 修改任务详情页添加诊断摘要
17. 实现独立诊断列表页
18. 实现独立诊断详情页
19. 实现规则管理 API
20. 编写 API 测试

### Phase 5: 测试和文档

21. 编写端到端测试
22. 更新项目文档
23. 性能测试和优化

---

## 验收标准

1. **自动日志导出**：任务完成后自动从设备拉取日志，无需人工干预
2. **日志解析正确率**：核心日志类型解析正确率 > 95%
3. **诊断准确率**：对已知故障案例的诊断准确率 > 90%
4. **页面功能完整**：
   - 任务详情页显示诊断摘要
   - 诊断列表页支持 SN 搜索和分页
   - 诊断详情页显示完整诊断信息
5. **性能要求**：单次诊断（含日志导出）耗时 < 30 秒