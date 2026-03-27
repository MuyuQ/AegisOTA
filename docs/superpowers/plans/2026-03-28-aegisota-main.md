# AegisOTA 完整实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个完整的安卓 OTA 升级异常注入与多机验证平台，包含设备管理、任务编排、异常注入、报告生成等完整功能。

**Architecture:** 采用"控制面 + 执行面"架构。控制面为 FastAPI 服务，负责设备清单、任务定义、调度、报告和 Web 展示。执行面为 Typer CLI 和后台 worker，负责调用 adb/fastboot 命令、采集日志、执行 monkey 测试。数据层使用 SQLite + SQLAlchemy。

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy, SQLite, Typer, Jinja2, HTMX

---

## 文件结构规划

```
app/
├── __init__.py
├── main.py                    # FastAPI 应用入口
├── config.py                  # 配置管理
├── database.py                # 数据库连接管理
├── api/
│   ├── __init__.py
│   ├── devices.py             # 设备 API
│   ├── runs.py                # 任务 API
│   └── reports.py             # 报告 API
├── models/
│   ├── __init__.py
│   ├── device.py              # Device, DeviceLease
│   ├── run.py                 # UpgradePlan, RunSession, RunStep
│   ├── fault.py               # FaultProfile
│   ├── artifact.py            # Artifact
│   └── report.py              # Report
├── services/
│   ├── __init__.py
│   ├── device_service.py      # 设备管理业务逻辑
│   ├── run_service.py         # 任务管理业务逻辑
│   ├── scheduler_service.py   # 调度逻辑
│   └── report_service.py      # 报告生成逻辑
├── executors/
│   ├── __init__.py
│   ├── command_runner.py      # 命令执行抽象
│   ├── adb_executor.py        # ADB 命令执行
│   ├── mock_executor.py       # Mock 执行器（测试用）
├── faults/
│   ├── __init__.py
│   ├── base.py                # FaultPlugin 基类
│   ├── storage_pressure.py    # 存储压力注入
│   ├── reboot_interrupted.py  # 重启中断注入
│   ├── monkey_after_upgrade.py # 升级后 monkey
│   └── download_interrupted.py # 下载中断注入
├── validators/
│   ├── __init__.py
│   ├── boot_check.py          # 开机检测
│   ├── version_check.py       # 版本确认
│   ├── monkey_runner.py       # Monkey 执行
│   └── perf_check.py          # 性能检查
├── reporting/
│   ├── __init__.py
│   ├── generator.py           # 报告生成
│   ├── failure_classifier.py  # 失败分类
│   └── templates/             # Jinja2 报告模板
├── templates/                 # Jinja2 Web 模板
│   ├── base.html
│   ├── dashboard.html
│   ├── devices.html
│   ├── runs.html
│   ├── run_detail.html
│   ├── report.html
├── static/                    # 静态文件
│   └── css/
│       └── style.css
├── cli/
│   ├── __init__.py
│   └── main.py                # Typer CLI 入口
│   ├── device.py              # 设备命令
│   ├── run.py                 # 任务命令
│   └ report.py                # 报告命令
tests/
├── __init__.py
├── conftest.py                # 测试配置和 fixtures
├── test_models/
├── test_services/
├── test_executors/
├── test_faults/
├── test_validators/
├── test_api/
artifacts/                     # 执行产物目录
```

---

## Phase 1: 基础骨架

### Task 1.1: 项目初始化与依赖管理

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "aegisota"
version = "0.1.0"
description = "Android OTA Upgrade Exception Injection and Multi-Device Verification Platform"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
    "sqlalchemy>=2.0.0",
    "typer>=0.9.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.6",
    "pydantic>=2.0.0",
    "httpx>=0.24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.0.280",
]

[project.scripts]
labctl = "app.cli.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: 创建 app/__init__.py**

```python
"""AegisOTA - Android OTA Upgrade Exception Injection and Multi-Device Verification Platform."""

__version__ = "0.1.0"
```

- [ ] **Step 3: 安装依赖**

Run: `pip install -e ".[dev]"`
Expected: Successfully installed aegisota and all dependencies

- [ ] **Step 4: 创建基础目录结构**

Run: `mkdir -p app/api app/models app/services app/executors app/faults app/validators app/reporting app/templates app/static/css app/cli tests/test_models tests/test_services tests/test_executors tests/test_faults tests/test_validators tests/test_api artifacts`

- [ ] **Step 5: 创建各模块 __init__.py 文件**

Run: `touch app/api/__init__.py app/models/__init__.py app/services/__init__.py app/executors/__init__.py app/faults/__init__.py app/validators/__init__.py app/reporting/__init__.py app/cli/__init__.py tests/__init__.py`

- [ ] **Step 6: 初始化 git 并提交**

```bash
git add pyproject.toml app/__init__.py
git commit -m "feat: initialize project structure with dependencies"
```

---

### Task 1.2: 配置系统

**Files:**
- Create: `app/config.py`
- Create: `tests/test_models/test_config.py`

- [ ] **Step 1: 写失败的配置测试**

```python
# tests/test_models/test_config.py
"""配置系统测试。"""

import os
from pathlib import Path

import pytest

from app.config import Settings


def test_default_settings():
    """测试默认配置值。"""
    settings = Settings()

    assert settings.APP_NAME == "AegisOTA"
    assert settings.DEBUG is False
    assert settings.DATABASE_URL == "sqlite:///./aegisota.db"
    assert settings.ARTIFACTS_DIR == Path("artifacts")


def test_settings_from_env():
    """测试从环境变量读取配置。"""
    os.environ["AEGISOTA_DEBUG"] = "true"
    os.environ["AEGISOTA_DATABASE_URL"] = "sqlite:///./test.db"

    settings = Settings()

    assert settings.DEBUG is True
    assert settings.DATABASE_URL == "sqlite:///./test.db"

    # 清理环境变量
    del os.environ["AEGISOTA_DEBUG"]
    del os.environ["AEGISOTA_DATABASE_URL"]


def test_artifacts_dir_creation():
    """测试产物目录创建。"""
    settings = Settings(ARTIFACTS_DIR=Path("test_artifacts"))

    assert settings.ARTIFACTS_DIR.exists()

    # 清理测试目录
    import shutil
    shutil.rmtree("test_artifacts", ignore_errors=True)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_models/test_config.py -v`
Expected: FAIL - ModuleNotFoundError: No module named 'app.config'

- [ ] **Step 3: 实现配置类**

```python
# app/config.py
"""配置管理模块。"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置。"""

    APP_NAME: str = "AegisOTA"
    DEBUG: bool = False
    DATABASE_URL: str = "sqlite:///./aegisota.db"
    ARTIFACTS_DIR: Path = Path("artifacts")

    # 设备管理配置
    DEVICE_SYNC_INTERVAL: int = 60  # 设备同步间隔（秒）
    DEVICE_HEALTH_CHECK_INTERVAL: int = 30  # 健康检查间隔

    # 任务执行配置
    DEFAULT_TIMEOUT: int = 300  # 默认超时时间（秒）
    REBOOT_WAIT_TIMEOUT: int = 120  # 重启等待超时
    BOOT_COMPLETE_TIMEOUT: int = 90  # 开机完成超时

    # Monkey 配置
    MONKEY_DEFAULT_COUNT: int = 1000  # 默认 Monkey 事件数
    MONKEY_THROTTLE: int = 50  # Monkey 事件间隔（毫秒）

    # 调度配置
    MAX_CONCURRENT_RUNS: int = 5  # 最大并发任务数
    LEASE_DEFAULT_DURATION: int = 3600  # 默认租约时长（秒）

    class Config:
        env_prefix = "AEGISOTA_"
        env_file = ".env"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """获取配置实例（缓存）。"""
    return Settings()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_models/test_config.py -v`
Expected: PASS - 3 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/config.py tests/test_models/test_config.py
git commit -m "feat: add configuration system with Pydantic Settings"
```

---

### Task 1.3: 数据库连接管理

**Files:**
- Create: `app/database.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: 写数据库连接测试**

```python
# tests/conftest.py
"""测试配置和 fixtures。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db


@pytest.fixture
def test_engine():
    """创建测试数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """创建测试数据库会话。"""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def override_get_db(test_session):
    """覆盖 get_db dependency。"""
    def _get_db():
        yield test_session
    return _get_db
```

```python
# tests/test_models/test_database.py
"""数据库连接测试。"""

import pytest
from sqlalchemy import inspect

from app.database import Base, engine, get_db


def test_base_has_metadata():
    """测试 Base 有 metadata。"""
    assert Base.metadata is not None


def test_get_db_returns_session():
    """测试 get_db 返回会话。"""
    # 使用内存数据库测试
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_engine = create_engine("sqlite:///:memory:")
    TestSession = sessionmaker(bind=test_engine)

    def test_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    gen = test_get_db()
    session = next(gen)
    assert session is not None
    gen.close()


def test_tables_created_on_init():
    """测试表在初始化时创建。"""
    from app.database import init_db
    from sqlalchemy import create_engine

    test_engine = create_engine("sqlite:///:memory:")
    init_db(test_engine)

    inspector = inspect(test_engine)
    # 验证核心表存在
    table_names = inspector.get_table_names()
    # 由于模型还未定义，这里暂时跳过表验证
    assert isinstance(table_names, list)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_models/test_database.py -v`
Expected: FAIL - ModuleNotFoundError: No module named 'app.database'

- [ ] **Step 3: 实现数据库模块**

```python
# app/database.py
"""数据库连接管理模块。"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite 需要此参数
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """获取数据库会话（用于 FastAPI dependency）。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(db_engine=None):
    """初始化数据库，创建所有表。"""
    target_engine = db_engine or engine
    Base.metadata.create_all(bind=target_engine)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_models/test_database.py -v`
Expected: PASS - 3 tests passed

- [ ] **Step 5: 提交**

```bash
git add app/database.py tests/conftest.py tests/test_models/test_database.py
git commit -m "feat: add database connection management with SQLAlchemy"
```

---

### Task 1.4: 设备数据模型

**Files:**
- Create: `app/models/device.py`
- Create: `tests/test_models/test_device.py`

- [ ] **Step 1: 写设备模型测试**

```python
# tests/test_models/test_device.py
"""设备模型测试。"""

import pytest
from datetime import datetime

from app.database import Base, SessionLocal
from app.models.device import Device, DeviceLease, DeviceStatus


def test_device_creation():
    """测试设备创建。"""
    device = Device(
        serial="ABC123",
        brand="Google",
        model="Pixel 6",
        android_version="14",
        status=DeviceStatus.IDLE,
        battery_level=85,
        tags=["主力机型", "Android14"]
    )

    assert device.serial == "ABC123"
    assert device.brand == "Google"
    assert device.status == DeviceStatus.IDLE
    assert device.tags == ["主力机型", "Android14"]


def test_device_status_values():
    """测试设备状态枚举值。"""
    assert DeviceStatus.IDLE.value == "idle"
    assert DeviceStatus.BUSY.value == "busy"
    assert DeviceStatus.OFFLINE.value == "offline"
    assert DeviceStatus.QUARANTINED.value == "quarantined"
    assert DeviceStatus.RECOVERING.value == "recovering"


def test_device_lease_creation():
    """测试设备租约创建。"""
    lease = DeviceLease(
        device_id=1,
        run_id=1,
        lease_status="active"
    )

    assert lease.device_id == 1
    assert lease.run_id == 1
    assert lease.lease_status == "active"


def test_device_database_operations(test_session):
    """测试设备数据库操作。"""
    from app.database import init_db
    from sqlalchemy import create_engine

    # 在内存数据库中测试
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)

    Session = sessionmaker(bind=test_engine)
    session = Session()

    device = Device(
        serial="TEST001",
        brand="Test",
        model="TestModel",
        status=DeviceStatus.IDLE
    )
    session.add(device)
    session.commit()

    retrieved = session.query(Device).filter_by(serial="TEST001").first()
    assert retrieved is not None
    assert retrieved.serial == "TEST001"

    session.close()


def test_device_is_available():
    """测试设备可用性判断方法。"""
    device = Device(
        serial="ABC123",
        status=DeviceStatus.IDLE,
        battery_level=80,
        health_score=90
    )

    assert device.is_available() is True

    device.status = DeviceStatus.BUSY
    assert device.is_available() is False

    device.status = DeviceStatus.IDLE
    device.battery_level = 10
    assert device.is_available() is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_models/test_device.py -v`
Expected: FAIL - ModuleNotFoundError: No module named 'app.models.device'

- [ ] **Step 3: 实现设备模型**

```python
# app/models/device.py
"""设备数据模型。"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.database import Base


class DeviceStatus(str, Enum):
    """设备状态枚举。"""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    QUARANTINED = "quarantined"
    RECOVERING = "recovering"


class Device(Base):
    """设备实体。"""

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial = Column(String(64), unique=True, nullable=False, index=True)
    brand = Column(String(64), nullable=True)
    model = Column(String(128), nullable=True)
    android_version = Column(String(32), nullable=True)
    build_fingerprint = Column(String(256), nullable=True)

    status = Column(
        SQLEnum(DeviceStatus),
        default=DeviceStatus.IDLE,
        nullable=False
    )
    health_score = Column(Float, default=100.0)
    battery_level = Column(Integer, nullable=True)
    tags = Column(Text, nullable=True)  # JSON 格式存储标签列表

    last_seen_at = Column(DateTime, default=datetime.utcnow)
    quarantine_reason = Column(Text, nullable=True)
    current_run_id = Column(Integer, ForeignKey("run_sessions.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    leases = relationship("DeviceLease", back_populates="device")
    run_sessions = relationship("RunSession", back_populates="device")

    def get_tags(self) -> List[str]:
        """获取标签列表。"""
        if not self.tags:
            return []
        import json
        return json.loads(self.tags)

    def set_tags(self, tags: List[str]):
        """设置标签列表。"""
        import json
        self.tags = json.dumps(tags)

    def is_available(self, min_battery: int = 20, min_health: float = 50.0) -> bool:
        """判断设备是否可用。"""
        if self.status != DeviceStatus.IDLE:
            return False
        if self.battery_level is not None and self.battery_level < min_battery:
            return False
        if self.health_score < min_health:
            return False
        return True

    def __repr__(self):
        return f"<Device(serial={self.serial}, status={self.status})>"


class DeviceLease(Base):
    """设备租约实体。"""

    __tablename__ = "device_leases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    run_id = Column(Integer, ForeignKey("run_sessions.id"), nullable=False)

    leased_at = Column(DateTime, default=datetime.utcnow)
    expired_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)
    lease_status = Column(String(32), default="active")  # active, expired, released

    # 关系
    device = relationship("Device", back_populates="leases")
    run_session = relationship("RunSession", back_populates="lease")

    def is_active(self) -> bool:
        """判断租约是否活跃。"""
        if self.lease_status != "active":
            return False
        if self.expired_at and datetime.utcnow() > self.expired_at:
            return False
        return True

    def __repr__(self):
        return f"<DeviceLease(device_id={self.device_id}, run_id={self.run_id}, status={self.lease_status})>"
```

- [ ] **Step 4: 更新 models/__init__.py 导出**

```python
# app/models/__init__.py
"""数据模型模块。"""

from app.models.device import Device, DeviceLease, DeviceStatus

__all__ = [
    "Device",
    "DeviceLease",
    "DeviceStatus",
]
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_models/test_device.py -v`
Expected: PASS - 5 tests passed

- [ ] **Step 6: 提交**

```bash
git add app/models/device.py app/models/__init__.py tests/test_models/test_device.py
git commit -m "feat: add Device and DeviceLease models"
```

---

### Task 1.5: 任务数据模型

**Files:**
- Create: `app/models/run.py`
- Create: `tests/test_models/test_run.py`

- [ ] **Step 1: 写任务模型测试**

```python
# tests/test_models/test_run.py
"""任务模型测试。"""

import pytest
from datetime import datetime

from app.database import Base
from app.models.run import (
    UpgradePlan, RunSession, RunStep,
    RunStatus, UpgradeType, StepName
)
from app.models.device import Device, DeviceStatus


def test_run_status_values():
    """测试任务状态枚举值。"""
    assert RunStatus.QUEUED.value == "queued"
    assert RunStatus.RESERVED.value == "reserved"
    assert RunStatus.RUNNING.value == "running"
    assert RunStatus.VALIDATING.value == "validating"
    assert RunStatus.PASSED.value == "passed"
    assert RunStatus.FAILED.value == "failed"
    assert RunStatus.ABORTED.value == "aborted"
    assert RunStatus.QUARANTINED.value == "quarantined"


def test_upgrade_type_values():
    """测试升级类型枚举值。"""
    assert UpgradeType.FULL.value == "full"
    assert UpgradeType.INCREMENTAL.value == "incremental"
    assert UpgradeType.ROLLBACK.value == "rollback"


def test_upgrade_plan_creation():
    """测试升级计划创建。"""
    plan = UpgradePlan(
        name="Pixel 6 Android 14 升级计划",
        upgrade_type=UpgradeType.FULL,
        package_path="/tmp/update.zip",
        target_build="AP1A.240305.019",
        device_selector={"brand": "Google", "model": "Pixel 6"},
        parallelism=3
    )

    assert plan.name == "Pixel 6 Android 14 升级计划"
    assert plan.upgrade_type == UpgradeType.FULL
    assert plan.parallelism == 3


def test_run_session_creation():
    """测试任务会话创建。"""
    session = RunSession(
        plan_id=1,
        device_id=1,
        status=RunStatus.QUEUED
    )

    assert session.plan_id == 1
    assert session.status == RunStatus.QUEUED


def test_run_step_creation():
    """测试执行步骤创建。"""
    step = RunStep(
        run_id=1,
        step_name=StepName.PRECHECK,
        step_order=1,
        status="running"
    )

    assert step.run_id == 1
    assert step.step_name == StepName.PRECHECK
    assert step.step_order == 1


def test_run_session_failure_category():
    """测试任务失败分类。"""
    session = RunSession(
        status=RunStatus.FAILED,
        failure_category="device_env_issue"
    )

    assert session.failure_category == "device_env_issue"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_models/test_run.py -v`
Expected: FAIL - ModuleNotFoundError: No module named 'app.models.run'

- [ ] **Step 3: 实现任务模型**

```python
# app/models/run.py
"""任务数据模型。"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.database import Base


class RunStatus(str, Enum):
    """任务状态枚举。"""

    QUEUED = "queued"
    RESERVED = "reserved"
    RUNNING = "running"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"
    ABORTED = "aborted"
    QUARANTINED = "quarantined"


class UpgradeType(str, Enum):
    """升级类型枚举。"""

    FULL = "full"
    INCREMENTAL = "incremental"
    ROLLBACK = "rollback"


class StepName(str, Enum):
    """执行步骤名称枚举。"""

    PRECHECK = "precheck"
    PACKAGE_PREPARE = "package_prepare"
    APPLY_UPDATE = "apply_update"
    REBOOT_WAIT = "reboot_wait"
    POST_VALIDATE = "post_validate"
    REPORT_FINALIZE = "report_finalize"


class UpgradePlan(Base):
    """升级计划实体。"""

    __tablename__ = "upgrade_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    upgrade_type = Column(SQLEnum(UpgradeType), default=UpgradeType.FULL, nullable=False)
    package_path = Column(String(512), nullable=False)
    target_build = Column(String(256), nullable=True)

    fault_profile_id = Column(Integer, ForeignKey("fault_profiles.id"), nullable=True)
    validation_profile_id = Column(Integer, nullable=True)  # 暂不创建 ValidationProfile 表

    device_selector = Column(Text, nullable=True)  # JSON 格式设备选择条件
    parallelism = Column(Integer, default=1)
    created_by = Column(String(128), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    run_sessions = relationship("RunSession", back_populates="plan")

    def get_device_selector(self) -> Dict[str, Any]:
        """获取设备选择条件。"""
        if not self.device_selector:
            return {}
        import json
        return json.loads(self.device_selector)

    def set_device_selector(self, selector: Dict[str, Any]):
        """设置设备选择条件。"""
        import json
        self.device_selector = json.dumps(selector)

    def __repr__(self):
        return f"<UpgradePlan(name={self.name}, type={self.upgrade_type})>"


class RunSession(Base):
    """任务执行会话实体。"""

    __tablename__ = "run_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("upgrade_plans.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)

    status = Column(SQLEnum(RunStatus), default=RunStatus.QUEUED, nullable=False)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    result = Column(String(32), nullable=True)  # success, failure, aborted

    failure_category = Column(String(64), nullable=True)
    summary = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    plan = relationship("UpgradePlan", back_populates="run_sessions")
    device = relationship("Device", back_populates="run_sessions")
    steps = relationship("RunStep", back_populates="run_session", order_by="RunStep.step_order")
    lease = relationship("DeviceLease", back_populates="run_session", uselist=False)
    artifacts = relationship("Artifact", back_populates="run_session")

    def get_duration_seconds(self) -> Optional[int]:
        """获取执行时长（秒）。"""
        if self.started_at and self.ended_at:
            return int((self.ended_at - self.started_at).total_seconds())
        return None

    def __repr__(self):
        return f"<RunSession(id={self.id}, status={self.status})>"


class RunStep(Base):
    """执行步骤实体。"""

    __tablename__ = "run_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("run_sessions.id"), nullable=False)
    step_name = Column(SQLEnum(StepName), nullable=False)
    step_order = Column(Integer, nullable=False)

    status = Column(String(32), default="pending")  # pending, running, success, failure, skipped
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

    command = Column(Text, nullable=True)
    stdout_path = Column(String(512), nullable=True)
    stderr_path = Column(String(512), nullable=True)
    step_result = Column(Text, nullable=True)  # JSON 格式结果

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    run_session = relationship("RunSession", back_populates="steps")

    def get_result(self) -> Dict[str, Any]:
        """获取步骤结果。"""
        if not self.step_result:
            return {}
        import json
        return json.loads(self.step_result)

    def set_result(self, result: Dict[str, Any]):
        """设置步骤结果。"""
        import json
        self.step_result = json.dumps(result)

    def __repr__(self):
        return f"<RunStep(run_id={self.run_id}, step={self.step_name}, status={self.status})>"
```

- [ ] **Step 4: 更新 models/__init__.py**

```python
# app/models/__init__.py
"""数据模型模块。"""

from app.models.device import Device, DeviceLease, DeviceStatus
from app.models.run import (
    UpgradePlan, RunSession, RunStep,
    RunStatus, UpgradeType, StepName
)

__all__ = [
    "Device",
    "DeviceLease",
    "DeviceStatus",
    "UpgradePlan",
    "RunSession",
    "RunStep",
    "RunStatus",
    "UpgradeType",
    "StepName",
]
```

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_models/test_run.py -v`
Expected: PASS - 5 tests passed

- [ ] **Step 6: 提交**

```bash
git add app/models/run.py app/models/__init__.py tests/test_models/test_run.py
git commit -m "feat: add UpgradePlan, RunSession, and RunStep models"
```

---

### Task 1.6: 异常注入与产物数据模型

**Files:**
- Create: `app/models/fault.py`
- Create: `app/models/artifact.py`
- Create: `tests/test_models/test_fault.py`
- Create: `tests/test_models/test_artifact.py`

- [ ] **Step 1: 写 FaultProfile 测试**

```python
# tests/test_models/test_fault.py
"""异常注入模型测试。"""

import pytest

from app.models.fault import FaultProfile, FaultStage, FaultType


def test_fault_stage_values():
    """测试异常阶段枚举值。"""
    assert FaultStage.PRECHECK.value == "precheck"
    assert FaultStage.APPLY_UPDATE.value == "apply_update"
    assert FaultStage.POST_VALIDATE.value == "post_validate"


def test_fault_type_values():
    """测试异常类型枚举值。"""
    assert FaultType.STORAGE_PRESSURE.value == "storage_pressure"
    assert FaultType.DOWNLOAD_INTERRUPTED.value == "download_interrupted"
    assert FaultType.REBOOT_INTERRUPTED.value == "reboot_interrupted"
    assert FaultType.MONKEY_AFTER_UPGRADE.value == "monkey_after_upgrade"


def test_fault_profile_creation():
    """测试异常配置创建。"""
    profile = FaultProfile(
        name="存储压力测试",
        fault_stage=FaultStage.PRECHECK,
        fault_type=FaultType.STORAGE_PRESSURE,
        parameters={"fill_percent": 90, "target_path": "/data/local/tmp"},
        enabled=True
    )

    assert profile.name == "存储压力测试"
    assert profile.fault_stage == FaultStage.PRECHECK
    assert profile.enabled is True


def test_fault_profile_parameters():
    """测试异常参数存取。"""
    profile = FaultProfile(
        name="测试",
        fault_type=FaultType.STORAGE_PRESSURE,
        parameters={"key": "value"}
    )

    params = profile.get_parameters()
    assert params == {"key": "value"}

    profile.set_parameters({"new_key": "new_value"})
    assert profile.get_parameters() == {"new_key": "new_value"}
```

- [ ] **Step 2: 写 Artifact 测试**

```python
# tests/test_models/test_artifact.py
"""产物模型测试。"""

import pytest
from datetime import datetime

from app.models.artifact import Artifact, ArtifactType


def test_artifact_type_values():
    """测试产物类型枚举值。"""
    assert ArtifactType.LOGCAT.value == "logcat"
    assert ArtifactType.STDOUT.value == "stdout"
    assert ArtifactType.SCREENSHOT.value == "screenshot"
    assert ArtifactType.REPORT.value == "report"


def test_artifact_creation():
    """测试产物创建。"""
    artifact = Artifact(
        run_id=1,
        artifact_type=ArtifactType.LOGCAT,
        path="artifacts/1/logcat.txt",
        size=1024,
        metadata={"lines": 100}
    )

    assert artifact.run_id == 1
    assert artifact.artifact_type == ArtifactType.LOGCAT
    assert artifact.path == "artifacts/1/logcat.txt"


def test_artifact_metadata():
    """测试产物元数据存取。"""
    artifact = Artifact(
        run_id=1,
        artifact_type=ArtifactType.STDOUT,
        metadata={"command": "adb devices"}
    )

    meta = artifact.get_metadata()
    assert meta == {"command": "adb devices"}
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/test_models/test_fault.py tests/test_models/test_artifact.py -v`
Expected: FAIL - ModuleNotFoundError

- [ ] **Step 4: 实现异常注入模型**

```python
# app/models/fault.py
"""异常注入数据模型。"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.database import Base


class FaultStage(str, Enum):
    """异常注入阶段枚举。"""

    PRECHECK = "precheck"
    APPLY_UPDATE = "apply_update"
    POST_VALIDATE = "post_validate"


class FaultType(str, Enum):
    """异常类型枚举。"""

    STORAGE_PRESSURE = "storage_pressure"
    DOWNLOAD_INTERRUPTED = "download_interrupted"
    PACKAGE_CORRUPTED = "package_corrupted"
    LOW_BATTERY = "low_battery"
    REBOOT_INTERRUPTED = "reboot_interrupted"
    POST_BOOT_WATCHDOG_FAILURE = "post_boot_watchdog_failure"
    MONKEY_AFTER_UPGRADE = "monkey_after_upgrade"
    PERFORMANCE_REGRESSION = "performance_regression"


class FaultProfile(Base):
    """异常配置实体。"""

    __tablename__ = "fault_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(256), nullable=False)
    fault_stage = Column(SQLEnum(FaultStage), nullable=False)
    fault_type = Column(SQLEnum(FaultType), nullable=False)

    parameters = Column(Text, nullable=True)  # JSON 格式参数
    enabled = Column(Boolean, default=True)

    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    upgrade_plans = relationship("UpgradePlan", back_populates="fault_profile")

    def get_parameters(self) -> Dict[str, Any]:
        """获取参数。"""
        if not self.parameters:
            return {}
        import json
        return json.loads(self.parameters)

    def set_parameters(self, params: Dict[str, Any]):
        """设置参数。"""
        import json
        self.parameters = json.dumps(params)

    def __repr__(self):
        return f"<FaultProfile(name={self.name}, type={self.fault_type})>"
```

```python
# app/models/artifact.py
"""产物数据模型。"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.database import Base


class ArtifactType(str, Enum):
    """产物类型枚举。"""

    LOGCAT = "logcat"
    STDOUT = "stdout"
    STDERR = "stderr"
    SCREENSHOT = "screenshot"
    MONKEY_RESULT = "monkey_result"
    PERF_DATA = "perf_data"
    REPORT = "report"
    TIMELINE = "timeline"


class Artifact(Base):
    """产物实体。"""

    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("run_sessions.id"), nullable=False)
    artifact_type = Column(SQLEnum(ArtifactType), nullable=False)

    path = Column(String(512), nullable=False)
    size = Column(Integer, nullable=True)
    metadata = Column(Text, nullable=True)  # JSON 格式元数据

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    run_session = relationship("RunSession", back_populates="artifacts")

    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据。"""
        if not self.metadata:
            return {}
        import json
        return json.loads(self.metadata)

    def set_metadata(self, meta: Dict[str, Any]):
        """设置元数据。"""
        import json
        self.metadata = json.dumps(meta)

    def __repr__(self):
        return f"<Artifact(run_id={self.run_id}, type={self.artifact_type})>"
```

- [ ] **Step 5: 更新 models/__init__.py**

```python
# app/models/__init__.py
"""数据模型模块。"""

from app.models.device import Device, DeviceLease, DeviceStatus
from app.models.run import (
    UpgradePlan, RunSession, RunStep,
    RunStatus, UpgradeType, StepName
)
from app.models.fault import FaultProfile, FaultStage, FaultType
from app.models.artifact import Artifact, ArtifactType

__all__ = [
    "Device",
    "DeviceLease",
    "DeviceStatus",
    "UpgradePlan",
    "RunSession",
    "RunStep",
    "RunStatus",
    "UpgradeType",
    "StepName",
    "FaultProfile",
    "FaultStage",
    "FaultType",
    "Artifact",
    "ArtifactType",
]
```

- [ ] **Step 6: 运行测试**

Run: `pytest tests/test_models/ -v`
Expected: PASS - all tests passed

- [ ] **Step 7: 提交**

```bash
git add app/models/fault.py app/models/artifact.py app/models/__init__.py tests/test_models/test_fault.py tests/test_models/test_artifact.py
git commit -m "feat: add FaultProfile and Artifact models"
```

---

### Task 1.7: FastAPI 应用入口

**Files:**
- Create: `app/main.py`
- Create: `tests/test_api/test_main.py`

- [ ] **Step 1: 写 API 入口测试**

```python
# tests/test_api/test_main.py
"""FastAPI 应用入口测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """创建测试客户端。"""
    return TestClient(app)


def test_app_metadata():
    """测试应用元数据。"""
    assert app.title == "AegisOTA"
    assert app.description is not None


def test_root_endpoint(client):
    """测试根路径。"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


def test_health_endpoint(client):
    """测试健康检查端点。"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_openapi_available(client):
    """测试 OpenAPI 文档可用。"""
    response = client.get("/docs")
    assert response.status_code == 200


def test_devices_endpoint_empty(client):
    """测试设备列表端点（空数据）。"""
    response = client.get("/api/devices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_api/test_main.py -v`
Expected: FAIL - ModuleNotFoundError: No module named 'app.main'

- [ ] **Step 3: 实现 FastAPI 应用入口**

```python
# app/main.py
"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # 启动时初始化数据库
    init_db()
    yield
    # 关闭时清理资源（如有需要）


app = FastAPI(
    title="AegisOTA",
    description="Android OTA Upgrade Exception Injection and Multi-Device Verification Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 模板引擎
templates = Jinja2Templates(directory="app/templates")


# 根路径
@app.get("/")
async def root():
    """根路径响应。"""
    return {"message": "AegisOTA API", "version": "0.1.0"}


# 健康检查
@app.get("/health")
async def health():
    """健康检查端点。"""
    return {"status": "healthy", "app_name": settings.APP_NAME}


# 导入路由模块
from app.api.devices import router as devices_router
from app.api.runs import router as runs_router
from app.api.reports import router as reports_router

app.include_router(devices_router, prefix="/api", tags=["devices"])
app.include_router(runs_router, prefix="/api", tags=["runs"])
app.include_router(reports_router, prefix="/api", tags=["reports"])
```

- [ ] **Step 4: 创建空的 API 路由文件**

```python
# app/api/__init__.py
"""API 路由模块。"""
```

```python
# app/api/devices.py
"""设备 API 路由。"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter()


@router.get("/devices")
async def list_devices(db: Session = Depends(get_db)):
    """获取设备列表。"""
    # 暂时返回空列表
    return []
```

```python
# app/api/runs.py
"""任务 API 路由。"""

from fastapi import APIRouter, Depends

from app.database import get_db

router = APIRouter()


@router.get("/runs")
async def list_runs(db: Session = Depends(get_db)):
    """获取任务列表。"""
    return []
```

```python
# app/api/reports.py
"""报告 API 路由。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/reports/{run_id}")
async def get_report(run_id: int):
    """获取报告。"""
    return {"run_id": run_id, "message": "Not implemented yet"}
```

- [ ] **Step 5: 创建静态文件目录和模板目录**

Run: `mkdir -p app/static/css app/templates`

- [ ] **Step 6: 运行测试**

Run: `pytest tests/test_api/test_main.py -v`
Expected: PASS - 5 tests passed

- [ ] **Step 7: 提交**

```bash
git add app/main.py app/api/__init__.py app/api/devices.py app/api/runs.py app/api/reports.py tests/test_api/test_main.py
git commit -m "feat: add FastAPI application entry with basic API routes"
```

---

### Task 1.8: Typer CLI 入口

**Files:**
- Create: `app/cli/main.py`
- Create: `app/cli/device.py`
- Create: `tests/test_cli/test_main.py`

- [ ] **Step 1: 写 CLI 测试**

```python
# tests/test_cli/test_main.py
"""CLI 测试。"""

import pytest
from typer.testing import CliRunner

from app.cli.main import app

runner = CliRunner()


def test_cli_help():
    """测试 CLI 帮助信息。"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "AegisOTA" in result.stdout or "labctl" in result.stdout


def test_device_help():
    """测试设备命令帮助。"""
    result = runner.invoke(app, ["device", "--help"])
    assert result.exit_code == 0
    assert "sync" in result.stdout or "list" in result.stdout


def test_device_list():
    """测试设备列表命令。"""
    result = runner.invoke(app, ["device", "list"])
    assert result.exit_code == 0


def test_run_help():
    """测试任务命令帮助。"""
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_cli/test_main.py -v`
Expected: FAIL - ModuleNotFoundError: No module named 'app.cli.main'

- [ ] **Step 3: 实现 CLI 入口**

```python
# app/cli/main.py
"""CLI 主入口。"""

import typer

app = typer.Typer(
    name="labctl",
    help="AegisOTA Lab Control CLI - Android OTA Upgrade Lab Manager",
    add_completion=False,
)

# 导入子命令
from app.cli.device import device_app
from app.cli.run import run_app
from app.cli.report import report_app

app.add_typer(device_app, name="device", help="设备管理命令")
app.add_typer(run_app, name="run", help="任务管理命令")
app.add_typer(report_app, name="report", help="报告管理命令")


@app.command()
def version():
    """显示版本信息。"""
    from app import __version__
    typer.echo(f"AegisOTA version: {__version__}")


if __name__ == "__main__":
    app()
```

```python
# app/cli/device.py
"""设备管理 CLI 命令。"""

import typer

device_app = typer.Typer(help="设备管理")


@device_app.command("sync")
def device_sync():
    """扫描并同步在线设备。"""
    typer.echo("扫描设备...")
    # TODO: 实现设备同步逻辑
    typer.echo("设备同步完成")


@device_app.command("list")
def device_list():
    """列出所有设备。"""
    typer.echo("设备列表:")
    # TODO: 实现设备列表逻辑
    typer.echo("(暂无设备)")


@device_app.command("quarantine")
def device_quarantine(
    serial: str = typer.Argument(..., help="设备序列号"),
    reason: str = typer.Option(None, "--reason", "-r", help="隔离原因"),
):
    """隔离异常设备。"""
    typer.echo(f"隔离设备: {serial}")
    if reason:
        typer.echo(f"原因: {reason}")


@device_app.command("recover")
def device_recover(
    serial: str = typer.Argument(..., help="设备序列号"),
):
    """恢复隔离设备。"""
    typer.echo(f"恢复设备: {serial}")
```

```python
# app/cli/run.py
"""任务管理 CLI 命令。"""

import typer

run_app = typer.Typer(help="任务管理")


@run_app.command("submit")
def run_submit(
    plan_id: int = typer.Argument(..., help="升级计划 ID"),
    device: str = typer.Option(None, "--device", "-d", help="指定设备序列号"),
):
    """提交升级任务。"""
    typer.echo(f"提交任务，计划 ID: {plan_id}")
    if device:
        typer.echo(f"指定设备: {device}")


@run_app.command("list")
def run_list():
    """列出所有任务。"""
    typer.echo("任务列表:")
    # TODO: 实现任务列表逻辑
    typer.echo("(暂无任务)")


@run_app.command("abort")
def run_abort(
    run_id: int = typer.Argument(..., help="任务 ID"),
):
    """终止任务。"""
    typer.echo(f"终止任务: {run_id}")


@run_app.command("execute")
def run_execute(
    run_id: int = typer.Argument(..., help="任务 ID"),
):
    """执行任务（Worker 模式）。"""
    typer.echo(f"执行任务: {run_id}")
```

```python
# app/cli/report.py
"""报告管理 CLI 命令。"""

import typer

report_app = typer.Typer(help="报告管理")


@report_app.command("export")
def report_export(
    run_id: int = typer.Argument(..., help="任务 ID"),
    format: str = typer.Option("markdown", "--format", "-f", help="输出格式 (markdown/html)"),
    output: str = typer.Option(None, "--output", "-o", help="输出文件路径"),
):
    """导出报告。"""
    typer.echo(f"导出报告，任务 ID: {run_id}")
    typer.echo(f"格式: {format}")
    if output:
        typer.echo(f"输出到: {output}")
```

- [ ] **Step 4: 创建测试目录**

Run: `mkdir -p tests/test_cli`

- [ ] **Step 5: 运行测试**

Run: `pytest tests/test_cli/test_main.py -v`
Expected: PASS - 4 tests passed

- [ ] **Step 6: 提交**

```bash
git add app/cli/main.py app/cli/device.py app/cli/run.py app/cli/report.py tests/test_cli/test_main.py
git commit -m "feat: add Typer CLI entry with device, run, and report commands"
```

---

## Phase 1 完成检查

至此，Phase 1 基础骨架已完成。验证：

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass

Run: `labctl --help`
Expected: CLI help displayed

Run: `uvicorn app.main:app --reload`
Expected: FastAPI server starts successfully

---

## Phase 2-7 详细计划

各阶段详细计划已保存在单独文件中：

| Phase | 文件 | 内容 | 任务数 |
|-------|------|------|--------|
| Phase 2 | [phase-2-executor-service.md](phase-2-executor-service.md) | 命令执行器、ADB 执行器、Mock 执行器、服务层 | 6 tasks |
| Phase 3 | [phase-3-state-machine.md](phase-3-state-machine.md) | 阶段 Handler、状态机驱动器、验证器 | 3 tasks |
| Phase 4 | [phase-4-fault-injection.md](phase-4-fault-injection.md) | 异常注入基类、存储压力、重启中断、Monkey、下载中断 | 5 tasks |
| Phase 5 | [phase-5-validation-report.md](phase-5-validation-report.md) | Monkey 执行器、性能检查、失败分类、报告生成 | 4 tasks |
| Phase 6 | [phase-6-scheduling-worker.md](phase-6-scheduling-worker.md) | Worker 服务、Worker CLI、完善 API 端点 | 3 tasks |
| Phase 7 | [phase-7-web-console.md](phase-7-web-console.md) | Web 模板、仪表盘、设备/任务页面、文档 | 4 tasks |

**执行顺序**：Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7

**注意**：Phase 4 和 Phase 5 可以并行执行，Phase 6 需要等待 Phase 3 完成。