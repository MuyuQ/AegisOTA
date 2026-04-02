# 贡献指南

感谢您对 AegisOTA 项目的关注！本文档介绍如何为项目做出贡献。

## 开发环境设置

### 系统要求

- Python 3.11+
- SQLite 3
- ADB（Android Debug Bridge）

### 安装步骤

1. 克隆仓库

```bash
git clone https://github.com/your-org/AegisOTA.git
cd AegisOTA
```

2. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
```

3. 安装依赖

```bash
pip install -e ".[dev]"
```

或使用 uv：

```bash
uv pip install -e ".[dev]"
```

4. 初始化数据库

```bash
python -c "from app.database import init_db; init_db()"
```

5. 启动开发服务器

```bash
uvicorn app.main:app --reload
```

## 项目结构

```
AegisOTA/
├── app/
│   ├── api/           # FastAPI 路由
│   ├── cli/           # Typer CLI 命令
│   ├── executors/     # 命令执行抽象层
│   ├── faults/        # 故障注入插件
│   ├── models/        # SQLAlchemy 模型
│   ├── reporting/     # 报告生成
│   ├── services/      # 业务逻辑层
│   ├── static/        # 静态文件
│   ├── templates/     # Jinja2 模板
│   ├── utils/         # 工具函数
│   └── validators/    # 验证器
├── tests/             # 测试文件
├── docs/              # 文档
└── artifacts/         # 执行产物
```

## 编码规范

### Python 代码风格

- 遵循 PEP 8 规范
- 使用 Black 格式化代码
- 使用 isort 排序导入
- 类型注解推荐但非强制

### 命名约定

| 类型 | 约定 | 示例 |
|------|------|------|
| 模块 | snake_case | `device_service.py` |
| 类 | PascalCase | `DeviceService` |
| 函数/方法 | snake_case | `get_device_by_id` |
| 常量 | UPPER_SNAKE_CASE | `DEFAULT_TIMEOUT` |
| 私有方法 | _leading_underscore | `_validate_input` |

### 文档字符串

使用中文注释，遵循 Google 风格：

```python
def get_device(device_id: int) -> Device:
    """获取设备详情。

    Args:
        device_id: 设备 ID

    Returns:
        Device: 设备对象

    Raises:
        HTTPException: 设备不存在时抛出 404
    """
```

### Git 提交消息

使用 Conventional Commits 格式：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**类型：**

- `feat`: 新功能
- `fix`: 修复 Bug
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例：**

```
feat(api): add device pool management endpoints

- Add CRUD operations for device pools
- Add device assignment to pools
- Add pool capacity calculation

Closes #123
```

## 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_services/test_device_service.py

# 运行带覆盖率报告
pytest --cov=app --cov-report=html
```

### 测试命名约定

- 测试文件：`test_<module_name>.py`
- 测试类：`Test<FeatureName>`
- 测试方法：`test_<scenario>_<expected_result>`

```python
class TestDeviceService:
    def test_get_device_returns_device_when_exists(self):
        ...

    def test_get_device_raises_404_when_not_found(self):
        ...
```

## 添加新功能

### 1. 添加新的 API 端点

在 `app/api/` 目录下创建或修改路由文件：

```python
# app/api/custom.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/custom", tags=["custom"])

@router.get("/items")
def list_items():
    return {"items": []}
```

然后在 `app/main.py` 中注册：

```python
from app.api import custom
app.include_router(custom.router)
```

### 2. 添加新的故障类型

在 `app/faults/` 目录下创建新文件：

```python
# app/faults/my_fault.py
from app.faults.base import FaultPlugin, FaultResult
from app.executors.run_context import RunContext

class MyFault(FaultPlugin):
    fault_type = "my_fault"
    fault_stage = "precheck"

    def inject(self, context: RunContext) -> FaultResult:
        # 实现故障注入逻辑
        return FaultResult(success=True, ...)
```

在 `app/faults/__init__.py` 中导出：

```python
from app.faults.my_fault import MyFault
```

### 3. 添加新的服务方法

在 `app/services/` 目录下添加：

```python
# app/services/my_service.py
from app.database import SessionLocal

class MyService:
    def __init__(self, db: SessionLocal):
        self.db = db

    def do_something(self) -> dict:
        # 实现业务逻辑
        return {"result": "success"}
```

## 安全注意事项

- **不要**在代码中硬编码敏感信息
- **不要**使用 `shell=True` 执行命令
- **务必**验证所有用户输入
- **务必**使用参数化查询（SQLAlchemy 自动处理）
- **务必**为新 API 添加认证保护

## 发布流程

1. 更新 `pyproject.toml` 中的版本号
2. 更新 `CHANGELOG.md`
3. 创建 Git 标签：`git tag v0.x.x`
4. 推送标签：`git push origin v0.x.x`

## 获取帮助

- 提交 Issue：https://github.com/your-org/AegisOTA/issues
- 邮件列表：aegisota-dev@example.com
- 文档：https://aegisota.readthedocs.io

感谢您的贡献！