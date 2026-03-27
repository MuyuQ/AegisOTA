"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api import devices, reports, runs
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。

    启动时初始化数据库，关闭时清理资源。
    """
    # 启动时初始化数据库
    init_db()
    yield
    # 关闭时的清理工作（如需要）


app = FastAPI(
    title="AegisOTA",
    description="Android OTA 升级异常注入与多设备验证平台",
    version="0.1.0",
    lifespan=lifespan,
)

# 静态文件挂载
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 模板配置
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# 注册路由
app.include_router(devices.router)
app.include_router(runs.router)
app.include_router(reports.router)


@app.get("/")
async def root():
    """根端点，返回 API 信息。"""
    return {
        "name": "AegisOTA",
        "description": "Android OTA 升级异常注入与多设备验证平台",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    """健康检查端点。"""
    return {"status": "healthy"}