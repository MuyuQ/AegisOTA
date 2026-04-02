"""设置 API 路由。"""

from pathlib import Path
from typing import List

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


@router.get("", response_class=HTMLResponse)
async def settings_page(request: Request):
    """设置页面。"""
    settings = get_settings()

    # 获取升级包目录下的文件列表
    full_packages = _list_packages(settings.get_full_package_path())
    incremental_packages = _list_packages(settings.get_incremental_package_path())

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "packages_dir": str(settings.OTA_PACKAGES_DIR),
            "full_dir": str(settings.get_full_package_path()),
            "incremental_dir": str(settings.get_incremental_package_path()),
            "full_packages": full_packages,
            "incremental_packages": incremental_packages,
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


def _list_packages(directory: Path) -> List[dict]:
    """列出目录下的升级包文件。"""
    if not directory.exists():
        return []

    packages = []
    for f in directory.iterdir():
        if f.is_file() and f.suffix in ['.zip', '.bin']:
            packages.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": f.stat().st_mtime,
            })

    # 按修改时间倒序
    packages.sort(key=lambda x: x["modified"], reverse=True)
    return packages