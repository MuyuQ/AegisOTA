# 贡献指南

感谢对 AegisOTA 项目的关注！本文档介绍如何参与项目开发。

## 快速链接

- [项目仓库](https://github.com/MuyuQ/AegisOTA)
- [Issue 追踪](https://github.com/MuyuQ/AegisOTA/issues)
- [README](../README.md)
- [API 文档](API.md)
- [架构文档](architecture.md)

---

## 开发环境设置

### 系统要求

- Python 3.10+
- Git
- ADB (Android Debug Bridge) - 可选，用于集成测试

### 安装步骤

**1. 克隆仓库**

```bash
git clone https://github.com/MuyuQ/AegisOTA.git
cd AegisOTA
```

**2. 创建虚拟环境**

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

**3. 安装依赖**

```bash
# 使用 pip
pip install -e ".[dev]"

# 或使用 uv (推荐，更快)
uv pip install -e ".[dev]"
```

**4. 验证安装**

```bash
# CLI 应该可用
labctl --help

# 运行测试
pytest tests/ -v
```

**5. 启动开发服务**

```bash
# 数据库会自动创建
uvicorn app.main:app --reload
```

访问 http://localhost:8000/docs 查看 API 文档。

---

## 编码规范

### Python 风格

- 遵循 [PEP 8](https://pep8.org/)
- 使用类型注解
- 函数长度不超过 50 行
- 类长度不超过 300 行

### 命名约定

| 类型 | 约定 | 示例 |
|------|------|------|
| 模块 | `snake_case` | `device_service.py` |
| 类 | `PascalCase` | `DeviceService` |
| 函数/方法 | `snake_case` | `get_device_by_id` |
| 常量 | `UPPER_SNAKE_CASE` | `DEFAULT_TIMEOUT` |
| 私有方法 | `_leading_underscore` | `_validate_input` |

### 代码格式化

```bash
# 安装开发工具
pip install ruff

# 格式化代码
ruff format app/

# 检查代码
ruff check app/
```

### 文档字符串

使用中文，遵循 Google 风格：

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

---

## Git 工作流

### 分支管理

```
main          - 主分支，保护状态
├── feature/xxx  - 新功能
├── fix/xxx      - Bug 修复
└── docs/xxx     - 文档更新
```

### 提交消息格式

使用 Conventional Commits：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**类型说明：**

| Type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码格式 |
| `refactor` | 重构 |
| `test` | 测试相关 |
| `chore` | 构建/工具 |

**示例：**

```bash
feat(api): add device pool capacity endpoint

- Add GET /api/pools/{id}/capacity
- Return available/reserved/busy counts
- Add utilization percentage

Closes #42
```

### 提交前检查清单

```bash
# 1. 代码格式化
ruff format app/
ruff check app/

# 2. 运行测试
pytest tests/ -v

# 3. 运行覆盖率 (可选)
pytest --cov=app --cov-report=term-missing

# 4. 检查变更
git diff
```

---

## 开发功能

### 添加 API 端点

**1. 创建路由文件**

```python
# app/api/my_feature.py
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/my-feature", tags=["my-feature"])

@router.get("/")
def list_items():
    """列出项目。"""
    return {"items": []}

@router.post("/")
def create_item(name: str):
    """创建项目。"""
    return {"id": 1, "name": name}
```

**2. 注册路由**

```python
# app/main.py
from app.api import my_feature

app.include_router(my_feature.router)
```

**3. 编写测试**

```python
# tests/test_api/test_my_feature.py
def test_list_items(client):
    resp = client.get("/api/my-feature")
    assert resp.status_code == 200
    assert "items" in resp.json()
```

### 添加服务层

```python
# app/services/my_service.py
from sqlalchemy.orm import Session

class MyService:
    def __init__(self, db: Session):
        self.db = db

    def do_something(self, item_id: int) -> dict:
        """执行操作。"""
        # 业务逻辑
        return {"result": "success"}
```

### 添加异常注入插件

**1. 创建插件类**

```python
# app/faults/my_fault.py
from app.faults.base import FaultPlugin, FaultResult
from app.executors.run_context import RunContext

class MyFault(FaultPlugin):
    """我的故障注入。"""

    fault_type = "my_fault"
    fault_stage = "precheck"

    def prepare(self, context: RunContext) -> None:
        # 准备条件
        pass

    def inject(self, context: RunContext) -> FaultResult:
        # 注入故障
        return FaultResult(success=True)

    def cleanup(self, context: RunContext) -> None:
        # 清理恢复
        pass
```

**2. 注册插件**

```python
# app/faults/__init__.py
from app.faults.my_fault import MyFault

FAULT_PLUGINS = {
    "my_fault": MyFault,
    # ...
}
```

---

## 测试指南

### 运行测试

```bash
# 全部测试
pytest

# 特定模块
pytest tests/test_services/ -v

# 特定文件
pytest tests/test_api/test_devices.py::test_get_device -v

# 带覆盖率
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

### 编写测试

```python
# tests/test_services/test_device_service.py
import pytest
from app.services.device_service import DeviceService

class TestDeviceService:
    @pytest.fixture
    def db(self):
        # 测试数据库
        ...

    @pytest.fixture
    def service(self, db):
        return DeviceService(db)

    def test_sync_discovers_devices(self, service, mock_adb):
        """测试同步发现设备。"""
        mock_adb.list_devices.return_value = [("ABC123", "device")]
        
        result = service.sync_devices()
        
        assert result.discovered == 1
        assert result.registered == 0
```

### Mock 外部依赖

```python
from unittest.mock import patch, MagicMock

@patch("app.executors.adb_executor.subprocess")
def test_adb_command(mock_subprocess):
    mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="OK")
    
    # 测试代码
```

---

## 提交 Pull Request

### PR 模板

```markdown
## 变更说明
简要描述变更内容和原因。

## 相关 Issue
Closes #123

## 测试
- [ ] 已添加单元测试
- [ ] 已运行所有测试
- [ ] 覆盖率无下降

## 检查清单
- [ ] 代码已格式化 (ruff format)
- [ ] 通过代码检查 (ruff check)
- [ ] 已更新文档
```

### 审核流程

1. 创建 PR
2. CI 自动运行测试
3. 维护者审核
4. 根据反馈修改
5. 合并到 main

---

## 安全注意事项

- **禁止**硬编码敏感信息（使用环境变量或配置文件）
- **禁止**使用 `shell=True` 执行用户输入
- **务必**验证所有用户输入
- **务必**使用参数化查询
- **务必**为新 API 添加认证保护

---

## 获取帮助

- 提交 Issue：https://github.com/MuyuQ/AegisOTA/issues
- 查看现有讨论

感谢你的贡献！
