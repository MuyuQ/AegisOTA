# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

## [Unreleased]

### 新增

- API Key 认证中间件
- CSRF 保护中间件
- Report ORM 模型持久化
- 状态转换验证机制
- 数据库事务管理工具
- 分页响应封装（PaginatedResponse）
- 步骤执行幂等性支持
- 4 种新故障类型：
  - PackageCorruptedFault（包损坏）
  - LowBatteryFault（低电量）
  - PostBootWatchdogFailureFault（Watchdog 故障）
  - PerformanceRegressionFault（性能退化）
- 结构化日志系统
- Jinja2 报告模板
- 无障碍访问支持
- 响应式设计
- 暗黑模式支持

### 修复

- 修复设备租约竞态条件（使用 SELECT FOR UPDATE）
- 修复故障注入逻辑错误：
  - 下载中断：不同中断点执行不同操作
  - 重启中断：使用 adb disconnect 替代 shell exit
  - 存储压力：清理前保存路径到临时变量
- 修复 API 字段名不一致（android_version → system_version）
- 修复无效参数静默忽略问题

### 变更

- CLI 命令集成到服务层
- 迁移报告 HTML 生成到 Jinja2 模板
- 改进错误处理和验证

## [0.1.0] - 2026-03-15

### 新增

- 初始版本发布
- 设备管理功能
- 任务调度系统
- 故障注入框架
- 报告生成模块
- Web 管理界面
- CLI 工具

### 支持的故障类型

- StoragePressureFault（存储压力）
- DownloadInterruptedFault（下载中断）
- RebootInterruptedFault（重启中断）
- MonkeyAfterUpgradeFault（Monkey 稳定性测试）