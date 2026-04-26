"""FastAPI 应用入口。"""

import logging
import secrets
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import devices, diagnosis, pools, reports, runs, web
from app.api.settings import router as settings_router
from app.config import get_settings
from app.database import init_db
from app.exceptions import AegisOTAError

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
API_PATH_PREFIX = "/api/v1"


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF 保护中间件。

    通过 cookie 存储 CSRF token，并验证请求头中的 token。
    """

    async def dispatch(self, request: Request, call_next):
        # 获取或生成 CSRF token
        csrf_token = request.cookies.get(CSRF_TOKEN_COOKIE)

        # 如果没有 token，先生成一个（在响应中设置）
        if not csrf_token:
            csrf_token = secrets.token_urlsafe(CSRF_TOKEN_LENGTH)

        # 对于 POST/PUT/PATCH/DELETE 请求，强制验证 CSRF token
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            # 从请求头获取 token（HTMX 使用 X-CSRF-Token）
            header_token = request.headers.get("X-CSRF-Token")
            cookie_token = request.cookies.get(CSRF_TOKEN_COOKIE)

            if not header_token or not cookie_token or cookie_token != header_token:
                return JSONResponse(
                    {"detail": "CSRF token missing or invalid"}, status_code=403
                )

        # 调用下一个处理器
        response = await call_next(request)

        # 如果请求中没有 CSRF cookie，设置一个
        if not request.cookies.get(CSRF_TOKEN_COOKIE):
            response.set_cookie(
                key=CSRF_TOKEN_COOKIE,
                value=csrf_token,
                httponly=False,  # JS 需读取 cookie 以设置 HTMX 请求头 X-CSRF-Token
                samesite="strict",
                max_age=86400 * 30,  # 30 天
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件。

    对 API 端点限制 100 请求/分钟，认证端点限制 10 请求/分钟。
    """

    def __init__(self, app):
        super().__init__(app)
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _is_auth_endpoint(self, path: str) -> bool:
        """检查是否为认证相关端点。"""
        return path.startswith("/api/v1/auth") or path.startswith("/api/v1/login")

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # 设置限制
        if self._is_auth_endpoint(path):
            max_requests = 10
            window_seconds = 60
        elif path.startswith("/api/v1"):
            max_requests = 100
            window_seconds = 60
        else:
            # 非 API 路径不限制
            return await call_next(request)

        # 检查速率限制
        now = time.time()
        cutoff = now - window_seconds
        self._requests[client_ip] = [ts for ts in self._requests[client_ip] if ts > cutoff]

        if len(self._requests[client_ip]) >= max_requests:
            return JSONResponse(
                {"detail": "Rate limit exceeded. Try again later."},
                status_code=429,
            )

        self._requests[client_ip].append(now)
        return await call_next(request)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件。

    对 /api/v1/* 路径的请求进行 API Key 验证，web 路径无需认证。
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
                    headers={"WWW-Authenticate": f"ApiKey header={self.header_name}"},
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
    # 初始化日志系统
    from app.utils.logging import setup_logging

    setup_logging()
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

# 添加速率限制中间件
app.add_middleware(RateLimitMiddleware)

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
app.include_router(diagnosis.router)


@app.get("/health")
async def health_check():
    """健康检查端点。"""
    return {"status": "healthy"}


@app.exception_handler(AegisOTAError)
async def aegis_ota_error_handler(request: Request, exc: AegisOTAError):
    """全局异常处理器：捕获 AegisOTAError 及其子类。"""
    logger = logging.getLogger(__name__)
    logger.error(
        "AegisOTAError: %s (status=%d, path=%s)",
        exc.message,
        exc.status_code,
        request.url.path,
    )
    return JSONResponse(
        {"detail": exc.message, "error_type": type(exc).__name__},
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """全局异常处理器：捕获所有未处理的异常。"""
    logger = logging.getLogger(__name__)
    logger.exception(
        "Unhandled exception: %s (path=%s)",
        str(exc),
        request.url.path,
    )
    return JSONResponse(
        {"detail": "Internal server error", "error_type": "InternalError"},
        status_code=500,
    )
