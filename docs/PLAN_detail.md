# AegisOTA 技术实施报告（详细版）

## 一、项目定义与落地目标
- 项目名称：`AegisOTA`
- 项目定位：面向安卓系统升级测试场景的“升级异常注入与多机验证平台”
- 项目目标：把原本分散在脚本、人工经验、机房操作中的升级测试流程，收敛为一套可配置、可执行、可追踪、可复盘的平台
- 项目面向对象：测试开发岗位面试官、具备 Android 测试背景的团队负责人、质量平台方向面试官
- 项目核心价值：
- 将 `OTA 全量升级`、`增量 patch`、`异常注入`、`升级后验证` 串成单一流水线
- 将机房设备从“人工点设备”升级为“可调度、可隔离、可回收”的资源池
- 将失败分析从“人工翻日志”升级为“结构化报告 + 自动归因”
- 项目不追求：
- 不做 Android 内核修改
- 不做真正的 OTA 底包生成系统
- 不做复杂前后端分离系统
- 不做分布式大规模调度
- 结果导向：
- 本地单机可运行
- 可管理一批安卓设备
- 可创建并执行升级验证任务
- 可产生有说服力的报告
- 可支撑完整面试讲解

## 二、整体架构与运行方式
### 2.1 架构分层
- 平台采用三层结构：`控制层`、`执行层`、`采集与分析层`
- 控制层负责接收任务、管理设备、维护状态机、生成报告、提供 Web 页面和 API
- 执行层负责真正调用 `adb`、`fastboot`、`cmd`、`monkey`、自定义 shell 脚本
- 采集与分析层负责日志、关键事件、性能数据、异常结论的统一汇总

### 2.2 部署方式
- 单机部署
- 一个 FastAPI 进程提供 API 与页面
- 一个 worker 进程轮询数据库执行任务
- 一个 CLI 工具供本地操作和调试
- 一个 SQLite 文件保存业务状态
- 日志和产物落地到本地目录，如 `artifacts/`

### 2.3 运行主流程
- 用户在 Web 或 CLI 中创建升级任务
- 调度器为任务分配符合条件的设备
- worker 锁定设备并执行任务状态机
- 每个状态阶段都允许插入 fault profile
- 执行过程中持续采集日志、命令输出、设备状态
- 执行结束后统一生成任务报告和失败归因
- 若设备异常，设备自动进入隔离状态，等待人工或自动恢复

## 三、模块设计、实现细节与实践步骤
## 3.1 设备管理模块
### 模块职责
- 维护设备清单
- 跟踪在线状态、占用状态、标签、健康度
- 提供设备隔离、回收、重试、同步能力

### 关键字段设计
- `Device`
- `id`
- `serial`
- `brand`
- `model`
- `android_version`
- `build_fingerprint`
- `status`
- `health_score`
- `battery_level`
- `tags`
- `last_seen_at`
- `quarantine_reason`
- `current_run_id`
- `DeviceLease`
- `id`
- `device_id`
- `run_id`
- `leased_at`
- `expired_at`
- `released_at`
- `lease_status`

### 状态定义
- 设备状态固定为：
- `idle`
- `busy`
- `offline`
- `quarantined`
- `recovering`

### 实现方式
- 通过 `adb devices` 获取在线设备
- 对每个设备执行 `adb -s <serial> shell getprop` 采集属性
- 周期性更新设备状态
- 在线但健康检查失败的设备标为 `quarantined`
- 离线设备自动标为 `offline`

### 实践步骤
- 第一步：实现 `device sync` 命令
- 第二步：实现设备数据库模型和增量更新逻辑
- 第三步：补充设备健康检查，包括 `battery`、`storage`、`boot_complete`、`adb shell 响应`
- 第四步：实现设备标签体系，如 `主力机型`、`Android14`、`高端机`、`实验机`
- 第五步：实现隔离与恢复接口

### 实践方式
- 命令执行统一封装到 `CommandRunner`
- 不在业务层直接拼接 shell 命令
- 每台设备的检查结果结构化保存，避免只保留原始文本
- 设备状态更新要做幂等处理，避免重复插入和误判

### 验收标准
- 可稳定发现在线设备
- 可识别离线设备和异常设备
- 同一设备不会被重复分配
- 设备支持按标签筛选和占用查询

## 3.2 升级任务编排模块
### 模块职责
- 定义升级任务
- 执行升级状态机
- 维护每一步的事件、产物和结论

### 核心数据结构
- `UpgradePlan`
- `id`
- `name`
- `upgrade_type`
- `package_path`
- `target_build`
- `fault_profile_id`
- `validation_profile_id`
- `device_selector`
- `parallelism`
- `created_by`
- `RunSession`
- `id`
- `plan_id`
- `device_id`
- `status`
- `started_at`
- `ended_at`
- `result`
- `failure_category`
- `summary`
- `RunStep`
- `id`
- `run_id`
- `step_name`
- `step_order`
- `status`
- `started_at`
- `ended_at`
- `command`
- `stdout_path`
- `stderr_path`
- `step_result`

### 状态机定义
- 任务状态固定为：
- `queued`
- `reserved`
- `running`
- `validating`
- `passed`
- `failed`
- `aborted`
- `quarantined`
- 执行阶段固定为：
- `precheck`
- `package_prepare`
- `apply_update`
- `reboot_wait`
- `post_validate`
- `report_finalize`

### 实现方式
- 每个阶段是一个独立 handler
- 每个 handler 输入 `RunContext`
- 每个 handler 输出 `StepResult`
- 所有阶段执行记录写入 `RunStep`
- 任一阶段失败，状态机进入失败路径
- 若失败原因属于设备异常，任务状态改为 `quarantined`

### 实践步骤
- 第一步：定义统一 `RunContext`
- 第二步：实现状态机驱动器 `RunExecutor`
- 第三步：实现 `precheck` 阶段
- 第四步：实现 `apply_update` 和 `reboot_wait`
- 第五步：实现 `post_validate`
- 第六步：实现失败处理、超时处理、人工终止

### 实践方式
- 先用 mock executor 跑通流程
- 再接入真实 adb 实现
- 所有阶段都必须支持超时
- 所有阶段都必须有清晰的开始、结束、失败原因
- 阶段间传递的数据放入 `RunContext.artifacts`，不要散落在临时变量里

### 验收标准
- 可创建并执行任务
- 每一步都有执行记录
- 执行失败后能定位具体阶段
- 支持人工终止和超时中断

## 3.3 异常注入模块
### 模块职责
- 模拟升级过程中的典型风险场景
- 让任务能验证平台对异常的检测与处理能力
- 为面试官提供技术亮点

### 注入场景设计
- `download_interrupted`
- `package_corrupted`
- `low_battery`
- `storage_pressure`
- `reboot_interrupted`
- `post_boot_watchdog_like_failure`
- `monkey_after_upgrade`
- `performance_regression_check`

### 接口设计
- `FaultProfile`
- `id`
- `name`
- `fault_stage`
- `fault_type`
- `parameters`
- `enabled`
- 统一插件接口：
- `prepare(context)`
- `inject(context)`
- `cleanup(context)`
- 插件触发点固定为：
- `precheck`
- `apply_update`
- `post_validate`

### 实现方式
- 不追求内核级真实故障
- 采用“测试视角可解释的场景抽象”
- 例如：
- `storage_pressure` 通过向 `/data/local/tmp` 预填充大文件模拟可用空间不足
- `download_interrupted` 通过故意删除包、断开服务或模拟拉取失败
- `reboot_interrupted` 通过在重启等待期插入超时或连接断开
- `watchdog_like_failure` 通过检测开机长时间未完成、关键属性异常、关键进程拉起失败来归类

### 实践步骤
- 第一步：定义 fault profile 数据模型
- 第二步：抽象 fault plugin 基类
- 第三步：先落地 4 个基础场景：`存储压力`、`包损坏`、`重启异常`、`升级后 monkey`
- 第四步：将 fault hook 接入状态机
- 第五步：将故障结果接入报告系统

### 实践方式
- 每个 fault plugin 只负责一件事
- 插件实现必须可回收，避免污染设备环境
- 对无法自动清理的场景，执行结束后直接将设备打入 `quarantined`
- fault plugin 要输出结构化元数据，而不是仅输出命令日志

### 验收标准
- 可通过配置切换异常场景
- 异常场景会反映在任务时间线和结论里
- 插件执行后设备状态可被恢复或隔离
- 报告中能明确说明“异常注入点”和“实际观测结果”

## 3.4 升级后验证模块
### 模块职责
- 判断升级后系统是否可用、是否稳定、是否存在明显回归
- 将“升级成功”与“升级后可交付”区分开

### 验证内容
- 开机完成检测
- 系统版本确认
- 关键服务可用性
- monkey 稳定性测试
- 基础性能指标采集
- 异常重启与卡死检测

### 验证接口
- `ValidationProfile`
- `id`
- `name`
- `boot_timeout_sec`
- `monkey_enabled`
- `monkey_event_count`
- `perf_enabled`
- `perf_rules`
- `required_props`
- `ValidationResult`
- `check_name`
- `status`
- `score`
- `evidence`

### 实现方式
- `boot_complete` 用 `getprop sys.boot_completed`
- 版本确认用 `ro.build.fingerprint` 或版本号字段
- monkey 执行用标准命令，输出摘要保存为 artifact
- 性能回归先做轻量版，如启动耗时、CPU 峰值、内存占用快照，不做复杂基准框架
- 若发现重复重启、关键属性未达预期、monkey 发生严重崩溃，则标记失败

### 实践步骤
- 第一步：实现开机完成和版本确认
- 第二步：实现 monkey 执行与摘要解析
- 第三步：实现简单性能指标采集
- 第四步：定义验证失败分类规则
- 第五步：接入报告输出

### 实践方式
- 先做“是否可用”的 hard check
- 再做“是否稳定”的 soft check
- 性能部分只做“异常提示”，不做绝对质量结论
- monkey 场景要可配置，不默认对所有设备长时间执行

### 验收标准
- 升级后可自动判断系统是否起来
- 可确认版本是否更新正确
- 可运行 monkey 并收集摘要
- 验证结果可在报告中独立查看

## 3.5 调度与并发控制模块
### 模块职责
- 决定哪些设备执行哪些任务
- 控制并发
- 防止设备竞争和资源污染

### 调度规则
- 单设备同一时刻仅允许一个独占任务
- 任务创建时根据 `device_selector` 选设备
- 调度优先选择 `idle` 且健康度高的设备
- 有 fault profile 的任务默认不调度到生产稳定池设备
- 隔离设备不参与调度

### 实现方式
- 不引入消息队列
- 使用数据库行状态 + worker 轮询
- worker 从 `queued` 任务中取一条
- 尝试获取设备租约
- 获取成功则变为 `reserved`
- 进入执行后改为 `running`
- 结束后释放租约

### 实践步骤
- 第一步：实现设备选择器
- 第二步：实现租约表和获取逻辑
- 第三步：实现 worker 拉取任务和抢占逻辑
- 第四步：实现并发上限控制
- 第五步：实现失败设备自动隔离

### 实践方式
- 抢占逻辑必须原子化
- SQLite 下通过事务和状态判断实现简化互斥
- 不在内存中维护设备占用状态，统一以数据库为准
- worker 重启后可根据数据库恢复任务状态

### 验收标准
- 同一设备不会被重复使用
- 多个任务可并发跑在多个设备上
- 设备异常后会自动退出资源池
- worker 崩溃不会导致设备永久锁死

## 3.6 日志采集与产物管理模块
### 模块职责
- 收集运行时的证据
- 为归因和报告提供数据基础
- 保证任务可追溯

### 产物类型
- 原始命令输出
- `logcat` 日志
- monkey 结果
- 关键属性快照
- 性能采样结果
- 截图或文本结论
- 任务时间线 JSON
- HTML/Markdown 报告

### 数据模型
- `Artifact`
- `id`
- `run_id`
- `artifact_type`
- `path`
- `size`
- `metadata`
- `created_at`

### 实现方式
- 每个任务创建独立目录，如 `artifacts/{run_id}/`
- 每个步骤的 stdout、stderr 单独存文件
- logcat 只保留与当前运行有关的时间窗口
- 关键结论提取成结构化 JSON，原始日志作为补充

### 实践步骤
- 第一步：实现 artifact 存储目录规范
- 第二步：统一 stdout/stderr 写入方式
- 第三步：实现 logcat 抓取与截断
- 第四步：实现结构化时间线记录
- 第五步：将 artifact 与报告关联

### 实践方式
- 文件命名固定化，避免后期难以定位
- 所有 artifact 必须带 run_id 和 step_name
- 不依赖日志全文做业务判断，业务判断只读取结构化结论
- 原始日志仅用于复核

### 验收标准
- 任意任务都能找到完整证据链
- 日志与步骤一一对应
- 报告能反查到原始产物
- 失败任务能快速定位到具体命令和日志片段

## 3.7 报告与归因模块
### 模块职责
- 输出技术上可信的执行结论
- 对失败做可解释归因
- 为简历和面试提供高价值展示材料

### 报告内容
- 任务基本信息
- 设备信息
- 升级类型
- fault profile
- 验证 profile
- 阶段时间线
- 关键日志片段
- 失败分类
- 风险结论
- 建议动作

### 失败分类体系
- `package_issue`
- `device_env_issue`
- `boot_failure`
- `validation_failure`
- `monkey_instability`
- `performance_suspect`
- `adb_transport_issue`
- `unknown`

### 实现方式
- 报告采用 `Jinja2` 模板生成 HTML 和 Markdown 两种格式
- 报告摘要由结构化数据拼接，不调用大模型
- 每个失败分类都定义判定规则
- 规则来源于步骤结果、关键命令返回值、关键属性、日志关键词

### 实践步骤
- 第一步：定义报告 JSON 结构
- 第二步：实现失败分类器
- 第三步：实现 HTML/Markdown 模板
- 第四步：接入任务详情页展示
- 第五步：补充导出命令

### 实践方式
- 分类逻辑写成独立模块，避免散落在执行代码里
- 报告内容优先结构化和摘要化
- 不用堆太多日志，关键片段即可
- 报告结尾加“建议动作”，例如重试、隔离、人工复核

### 验收标准
- 每次任务结束都有报告
- 报告能一眼看出在哪一步失败
- 失败结论具备基本可信度
- 报告可作为简历项目的附件展示逻辑

## 3.8 Web 控制台模块
### 模块职责
- 提供可视化入口
- 展示任务、设备、报告
- 辅助面试讲解平台全貌

### 页面范围
- 首页仪表盘
- 设备列表页
- 任务列表页
- 创建任务页
- 任务详情页
- 报告详情页

### 实现方式
- `FastAPI + Jinja2 + HTMX`
- 不做复杂前端状态管理
- 页面只做表单提交、列表刷新、详情查看

### 页面重点
- 仪表盘展示设备状态分布、最近任务结果、失败分类统计
- 设备页展示在线状态、版本、标签、健康度、是否隔离
- 任务页展示运行中、成功、失败、等待中任务
- 详情页展示时间线、每一步结果、关键日志链接、最终报告

### 实践步骤
- 第一步：完成基础布局和导航
- 第二步：完成设备和任务列表页
- 第三步：完成任务创建页
- 第四步：完成任务详情页
- 第五步：完成报告页和导出入口

### 实践方式
- 页面只消费内部 API
- 所有时间线、状态色、失败标签统一定义
- 页面上的字段必须与数据库和报告一致，避免多套命名

### 验收标准
- 能从页面创建任务
- 能看到设备当前状态
- 能查看运行过程和报告
- 页面足够清晰，适合讲项目

## 3.9 CLI 与执行器模块
### 模块职责
- 提供本地操作能力
- 供 worker 与调试流程复用
- 支撑无 Web 场景下的快速验证

### CLI 命令
- `labctl device sync`
- `labctl device list`
- `labctl run submit`
- `labctl run execute`
- `labctl run abort`
- `labctl report export`
- `labctl device recover`

### 实现方式
- 使用 `Typer`
- CLI 只做输入解析和结果展示
- 实际业务逻辑调用 service 层
- worker 调用与 CLI 共享同一套执行器

### 实践步骤
- 第一步：建 CLI 骨架
- 第二步：实现设备类命令
- 第三步：实现任务提交类命令
- 第四步：实现报告导出类命令
- 第五步：实现 worker 模式

### 实践方式
- CLI 输出要统一简洁
- 同一业务不要在 CLI 和 API 各写一套逻辑
- 命令失败要有明确返回码和错误信息

### 验收标准
- 不依赖 Web 也能提交和执行任务
- CLI 可用于开发调试
- CLI 与 API 行为一致

## 四、接口与目录建议
## 4.1 API 设计
- `POST /api/runs`
- 输入：升级类型、包路径、设备选择器、fault profile、validation profile
- 输出：run_id、状态、已匹配设备数
- `GET /api/runs/{id}`
- 输出：任务摘要、阶段状态、artifact 链接、失败分类、报告摘要
- `POST /api/runs/{id}/abort`
- 输出：中止结果
- `GET /api/devices`
- 输出：设备列表、状态、版本、标签、健康度
- `POST /api/devices/{id}/quarantine`
- 输出：隔离结果
- `POST /api/devices/{id}/recover`
- 输出：恢复结果
- `GET /api/reports/{id}`
- 输出：结构化报告内容

## 4.2 建议目录结构
- `app/api/`
- `app/models/`
- `app/services/`
- `app/executors/`
- `app/faults/`
- `app/validators/`
- `app/reporting/`
- `app/templates/`
- `app/static/`
- `app/cli/`
- `tests/`
- `artifacts/`

## 4.3 公共类型与接口
- `RunContext`
- `StepResult`
- `DeviceSnapshot`
- `FaultPlugin`
- `ValidationCheck`
- `ReportPayload`

## 五、实际开发步骤与顺序
### 第一阶段：打基础骨架
- 初始化 FastAPI、Typer、SQLAlchemy 项目
- 建数据库模型
- 建配置系统和日志系统
- 做设备同步命令
- 做最小设备列表页面

### 第二阶段：打通最短主链路
- 先不做异常注入
- 只做正常升级流程
- 从任务创建到执行到报告输出跑通一条链
- 这一步的目标是平台真正能跑，不是功能多

### 第三阶段：补状态机和执行细节
- 加入分阶段执行
- 加入超时、重试、人工终止
- 加入每一步 artifact 落盘
- 加入任务时间线

### 第四阶段：补异常注入
- 先做 4 个最能讲的 fault profile
- 接入状态机钩子
- 报告中展示注入点和结果差异
- 这一步是项目差异化核心

### 第五阶段：补升级后验证
- 接 monkey
- 接版本核验
- 接 boot check
- 接轻量性能检查
- 定义失败分类规则

### 第六阶段：补多机调度和隔离
- 加设备租约
- 加多任务 worker
- 加隔离与恢复
- 加标签池与调度规则
- 这一步让项目从“脚本”变成“平台”

### 第七阶段：补展示和文档
- 补完整 Web 页面
- 补 README
- 补架构图
- 补时序图
- 补面试讲稿
- 补示例报告

## 六、测试方案与验证方式
### 单元测试
- 状态机转换正确
- fault plugin 参数校验正确
- 失败分类逻辑正确
- 设备租约竞争控制正确
- 任务中止逻辑正确

### 集成测试
- mock adb 执行器跑通正常升级链路
- mock reboot 超时跑通失败链路
- mock monkey 异常跑通报告归因
- mock 设备离线跑通 quarantine 逻辑

### 人工验证
- 准备 2 到 3 台设备做最小实测
- 验证正常任务
- 验证异常任务
- 验证设备隔离和恢复
- 验证 HTML 报告是否可读

### 面试验收点
- 能说清平台解决什么问题
- 能说明为什么状态机是核心
- 能说明 fault plugin 为什么是差异化设计
- 能说明调度和隔离怎么避免设备池混乱
- 能说明为什么选 SQLite、HTMX、纯 Python

## 七、关键技术取舍
- 选择纯 Python，是为了保证项目叙事统一、实现效率高、与你的背景完全一致
- 选择 SQLite，是因为项目重点是平台设计和流程编排，不是数据库高并发
- 选择 Jinja2/HTMX，是因为 Web 只是展示层，不值得引入前后端分离复杂度
- 不上 Celery/Redis，是因为单机 worker 足以证明调度设计
- 不做复杂性能基准，是因为面试场景更看重“平台思维 + 问题建模 + 工程设计”
- 不承诺真实 COW 底层实现，而是将其映射为升级阶段和故障模型，这是技术上更可信的表达

## 八、默认实现结论
- 这份项目应优先做成“真实设备可接入，但 mock 路径完整”的平台
- 第一版最重要的是“正常升级 + 4 个 fault profile + monkey 验证 + 报告系统 + 多机调度”
- 如果时间不够，优先保留：
- 升级状态机
- 异常注入
- 报告归因
- 设备租约
- 如果时间紧张，后置：
- 复杂性能分析
- 权限系统
- 富前端
- Postgres 切换
- 这份项目最终对外叙事应是：
- 你不是做了一个脚本集合
- 你是把安卓升级测试和机房群控经验抽象成了一套质量工程平台

