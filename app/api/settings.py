"""设置 API 路由。"""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings, clear_settings_cache
from app.database import get_db

router = APIRouter(prefix="/settings", tags=["settings"])

templates = Jinja2Templates(directory="app/templates")

# 配置文件路径
ENV_FILE = Path(".env")


def get_csrf_token(request: Request) -> str:
    """从请求中获取 CSRF token。"""
    import secrets
    token = request.cookies.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
    return token


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """设置页面。"""
    settings = get_settings()

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "request": request,
            "csrf_token": get_csrf_token(request),
            "max_concurrent_runs": settings.MAX_CONCURRENT_RUNS,
            "default_timeout": settings.DEFAULT_TIMEOUT,
            "reboot_wait_timeout": settings.REBOOT_WAIT_TIMEOUT,
            "monkey_default_count": settings.MONKEY_DEFAULT_COUNT,
            "monkey_throttle": settings.MONKEY_THROTTLE,
        }
    )


@router.post("/config", response_class=HTMLResponse)
async def save_config(
    request: Request,
    max_concurrent_runs: int = Form(...),
    default_timeout: int = Form(...),
    reboot_wait_timeout: int = Form(...),
    monkey_default_count: int = Form(...),
    monkey_throttle: int = Form(...),
):
    """保存配置。"""
    # 写入 .env 文件
    env_content = f"""AEGISOTA_MAX_CONCURRENT_RUNS={max_concurrent_runs}
AEGISOTA_DEFAULT_TIMEOUT={default_timeout}
AEGISOTA_REBOOT_WAIT_TIMEOUT={reboot_wait_timeout}
AEGISOTA_MONKEY_DEFAULT_COUNT={monkey_default_count}
AEGISOTA_MONKEY_THROTTLE={monkey_throttle}
"""
    ENV_FILE.write_text(env_content)

    # 清除配置缓存以重新加载
    clear_settings_cache()

    return HTMLResponse(content='''
    <div class="alert alert-success">
        配置已保存！部分配置可能需要重启服务生效。
    </div>
    ''')