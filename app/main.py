"""FastAPI 应用入口。"""

import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import devices, reports, runs, web, pools
from app.api.settings import router as settings_router
from app.config import get_settings
from app.database import init_db


CSRF_TOKEN_COOKIE = "csrf_token"
CSRF_TOKEN_LENGTH = 32

# 不需要 API Key 认证的路径
PUBLIC_PATHS = [
    "/",  # 首页（精确匹配）
    "/health",  # 健康检查（精确匹配）
]
# 不需要 API Key 认证的路径前缀
PUBLIC_PATH_PREFIXES = [
    "/static",  # 静态资源
    "/devices",  # 设备页面
    "/runs",  # 任务页面
    "/pools",  # 设备池页面
    "/reports",  # 报告页面
]
# 需要 API Key 认证的路径前缀
API_PATH_PREFIX = "/api"


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF 保护中间件。

    通过 cookie 存储 CSRF token，并在 POST 请求中验证表单提交的 token。
    """

    async def dispatch(self, request: Request, call_next):
        # 获取或生成 CSRF token
        csrf_token = request.cookies.get(CSRF_TOKEN_COOKIE)

        # 如果没有 token，先生成一个（在响应中设置）
        if not csrf_token:
            csrf_token = secrets.token_urlsafe(CSRF_TOKEN_LENGTH)

        # 对于 POST 请求，验证 CSRF token
        if request.method == "POST":
            # 尝试从表单数据获取 token
            form_token = None

            # 需要先读取 body，但要注意不能影响后续处理
            # 使用 request._body 缓存机制
            try:
                form_data = await request.form()
                form_token = form_data.get("csrf_token")
            except Exception:
                # 如果不是表单数据（如 JSON），跳过验证
                pass

            # 如果有表单 token，验证它
            if form_token is not None:
                cookie_token = request.cookies.get(CSRF_TOKEN_COOKIE)
                if not cookie_token or cookie_token != form_token:
                    return JSONResponse(
                        {"detail": "CSRF token missing or invalid"},
                        status_code=400
                    )

        # 调用下一个处理器
        response = await call_next(request)

        # 如果请求中没有 CSRF cookie，设置一个
        if not request.cookies.get(CSRF_TOKEN_COOKIE):
            response.set_cookie(
                key=CSRF_TOKEN_COOKIE,
                value=csrf_token,
                httponly=False,  # 需要 JavaScript 读取
                samesite="strict",
                max_age=86400 * 30,  # 30 天
            )

        return response


class APIKeyMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件。

    对 /api/* 路径的请求进行 API Key 验证，web 路径无需认证。
    """

    def __init__(self, app, api_keys: list[str], header_name: str = "X-API-Key"):
        super().__init__(app)
        self.api_keys = set(api_keys)  # 使用 set 加速查找
        self.header_name = header_name

    def _is_public_path(self, path: str) -> bool:
        """检查是否为公开路径。"""
        # 精确匹配
        if path in PUBLIC_PATHS:
            return True
        # 前缀匹配
        for prefix in PUBLIC_PATH_PREFIXES:
            if path.startswith(prefix):
                return True
        return False

    def _is_api_path(self, path: str) -> bool:
        """检查是否为 API 路径。"""
        return path.startswith(API_PATH_PREFIX)

    async def dispatch(self, request: Request, call_next):
        # 公开路径无需认证
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # API 路径需要认证
        if self._is_api_path(request.url.path):
            # 如果没有配置 API Keys，允许所有请求（开发模式）
            if not self.api_keys:
                return await call_next(request)

            # 获取 API Key
            api_key: Optional[str] = request.headers.get(self.header_name)

            if not api_key or api_key not in self.api_keys:
                return JSONResponse(
                    {"detail": "Invalid or missing API key"},
                    status_code=401,
                    headers={"WWW-Authenticate": f"ApiKey header={self.header_name}"}
                )

        return await call_next(request)


def get_csrf_token(request: Request) -> str:
    """获取 CSRF token（用于模板上下文）。"""
    token = request.cookies.get(CSRF_TOKEN_COOKIE)
    if not token:
        token = secrets.token_urlsafe(CSRF_TOKEN_LENGTH)
    return token


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

# 添加 CSRF 中间件（必须在其他中间件之前）
app.add_middleware(CSRFMiddleware)

# 添加 API Key 中间件（需要配置）
settings = get_settings()
if settings.API_KEY_ENABLED and settings.API_KEYS:
    app.add_middleware(
        APIKeyMiddleware,
        api_keys=settings.API_KEYS,
        header_name=settings.API_KEY_HEADER,
    )

# 静态文件挂载
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 模板配置
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# 注册路由
app.include_router(web.router, tags=["web"])
app.include_router(devices.router)
app.include_router(runs.router)
app.include_router(reports.router)
app.include_router(settings_router)
app.include_router(pools.router)


@app.get("/health")
async def health_check():
    """健康检查端点。"""
    return {"status": "healthy"}