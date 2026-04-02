"""FastAPI 应用入口。"""

import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import devices, reports, runs, web, settings, pools
from app.database import init_db


CSRF_TOKEN_COOKIE = "csrf_token"
CSRF_TOKEN_LENGTH = 32


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
app.include_router(settings.router)
app.include_router(pools.router)


@app.get("/health")
async def health_check():
    """健康检查端点。"""
    return {"status": "healthy"}