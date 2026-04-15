"""设置 API 路由。"""

from pathlib import Path

from dotenv import set_key
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import clear_settings_cache, get_settings
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
        },
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
    # 逐个更新 key，保留 .env 中其他配置（如 API Keys）
    set_key(str(ENV_FILE), "AEGISOTA_MAX_CONCURRENT_RUNS", str(max_concurrent_runs))
    set_key(str(ENV_FILE), "AEGISOTA_DEFAULT_TIMEOUT", str(default_timeout))
    set_key(str(ENV_FILE), "AEGISOTA_REBOOT_WAIT_TIMEOUT", str(reboot_wait_timeout))
    set_key(str(ENV_FILE), "AEGISOTA_MONKEY_DEFAULT_COUNT", str(monkey_default_count))
    set_key(str(ENV_FILE), "AEGISOTA_MONKEY_THROTTLE", str(monkey_throttle))

    # 清除配置缓存以重新加载
    clear_settings_cache()

    return HTMLResponse(
        content="""
    <div class="alert alert-success">
        配置已保存！部分配置可能需要重启服务生效。
    </div>
    """
    )
