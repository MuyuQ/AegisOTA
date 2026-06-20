"""使用 Playwright 测试 AegisOTA 界面。"""

import asyncio

from playwright.async_api import async_playwright


async def test_dashboard():
    """测试仪表盘页面。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        print("=" * 60)
        print("测试 1: 仪表盘页面")
        print("=" * 60)

        # 访问仪表盘
        await page.goto("http://localhost:8000")
        await page.wait_for_load_state("networkidle")

        # 截图
        await page.screenshot(path="test_results/dashboard.png", full_page=True)
        print("✓ 仪表盘截图已保存: test_results/dashboard.png")

        # 检查关键元素
        title = await page.title()
        print(f"✓ 页面标题: {title}")

        # 检查统计卡片
        stat_cards = await page.locator(".stat-card").count()
        print(f"✓ 统计卡片数量: {stat_cards}")

        # 检查侧边栏导航
        nav_items = await page.locator(".sidebar-menu-link").count()
        print(f"✓ 导航项数量: {nav_items}")

        await browser.close()
        print("✓ 仪表盘测试完成\n")


async def test_devices_page():
    """测试设备管理页面。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        print("=" * 60)
        print("测试 2: 设备管理页面")
        print("=" * 60)

        # 访问设备页面
        await page.goto("http://localhost:8000/devices")
        await page.wait_for_load_state("networkidle")

        # 截图
        await page.screenshot(path="test_results/devices.png", full_page=True)
        print("✓ 设备页面截图已保存: test_results/devices.png")

        # 检查设备表格
        device_rows = await page.locator(".data-table tbody tr").count()
        print(f"✓ 设备行数: {device_rows}")

        # 检查状态指示器
        status_indicators = await page.locator(".status-indicator").count()
        print(f"✓ 状态指示器数量: {status_indicators}")

        await browser.close()
        print("✓ 设备页面测试完成\n")


async def test_runs_page():
    """测试任务列表页面。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        print("=" * 60)
        print("测试 3: 任务列表页面")
        print("=" * 60)

        # 访问任务页面
        await page.goto("http://localhost:8000/runs")
        await page.wait_for_load_state("networkidle")

        # 截图
        await page.screenshot(path="test_results/runs.png", full_page=True)
        print("✓ 任务页面截图已保存: test_results/runs.png")

        # 检查创建任务按钮
        create_btn = await page.locator('a[href="/runs/create"]').count()
        print(f"✓ 创建任务按钮: {'存在' if create_btn > 0 else '不存在'}")

        await browser.close()
        print("✓ 任务页面测试完成\n")


async def test_create_run_page():
    """测试创建任务页面。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        print("=" * 60)
        print("测试 4: 创建任务页面")
        print("=" * 60)

        # 访问创建任务页面
        await page.goto("http://localhost:8000/runs/create")
        await page.wait_for_load_state("networkidle")

        # 截图
        await page.screenshot(path="test_results/create_run.png", full_page=True)
        print("✓ 创建任务页面截图已保存: test_results/create_run.png")

        # 检查表单元素
        plan_select = await page.locator('select[name="plan_id"]').count()
        print(f"✓ 升级计划选择框: {'存在' if plan_select > 0 else '不存在'}")

        device_checkboxes = await page.locator('input[name="device_serials"]').count()
        print(f"✓ 设备选择框数量: {device_checkboxes}")

        submit_btn = await page.locator('button[type="submit"]').count()
        print(f"✓ 提交按钮: {'存在' if submit_btn > 0 else '不存在'}")

        await browser.close()
        print("✓ 创建任务页面测试完成\n")


async def test_settings_page():
    """测试设置页面。"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        print("=" * 60)
        print("测试 5: 设置页面")
        print("=" * 60)

        # 访问设置页面
        await page.goto("http://localhost:8000/settings")
        await page.wait_for_load_state("networkidle")

        # 截图
        await page.screenshot(path="test_results/settings.png", full_page=True)
        print("✓ 设置页面截图已保存: test_results/settings.png")

        # 检查表单元素
        form_inputs = await page.locator(".form-input").count()
        print(f"✓ 表单输入框数量: {form_inputs}")

        await browser.close()
        print("✓ 设置页面测试完成\n")


async def main():
    """运行所有测试。"""
    import os

    os.makedirs("test_results", exist_ok=True)

    print("\n" + "=" * 60)
    print("AegisOTA 界面自动化测试")
    print("=" * 60 + "\n")

    try:
        await test_dashboard()
        await test_devices_page()
        await test_runs_page()
        await test_create_run_page()
        await test_settings_page()

        print("=" * 60)
        print("所有测试完成！")
        print("=" * 60)
        print("\n截图文件保存在: test_results/")

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
