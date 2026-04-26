"""FastAPI 应用入口测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """创建测试客户端。"""
    return TestClient(app)


class TestAppMetadata:
    """应用元数据测试。"""

    def test_app_title(self):
        """验证应用标题。"""
        assert app.title == "AegisOTA"

    def test_app_description(self):
        """验证应用描述。"""
        assert "OTA" in app.description

    def test_app_version(self):
        """验证应用版本。"""
        assert app.version == "0.1.0"


class TestRootEndpoint:
    """根端点测试。"""

    def test_root_returns_html(self, client):
        """验证根端点返回 HTML（仪表盘页面）。"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_root_contains_title(self, client):
        """验证根端点包含页面标题。"""
        response = client.get("/")
        assert "AegisOTA" in response.text


class TestHealthEndpoint:
    """健康检查端点测试。"""

    def test_health_endpoint_exists(self, client):
        """验证健康检查端点存在。"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy(self, client):
        """验证健康检查返回 healthy 状态。"""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"


class TestOpenAPI:
    """OpenAPI 文档测试。"""

    def test_docs_available(self, client):
        """验证 OpenAPI 文档可访问。"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_available(self, client):
        """验证 OpenAPI JSON 可访问。"""
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_openapi_schema_has_devices_path(self, client):
        """验证 OpenAPI schema 包含 devices 路径。"""
        response = client.get("/openapi.json")
        schema = response.json()
        assert "/api/v1/devices" in schema["paths"]

    def test_openapi_schema_has_runs_path(self, client):
        """验证 OpenAPI schema 包含 runs 路径。"""
        response = client.get("/openapi.json")
        schema = response.json()
        assert "/api/v1/runs" in schema["paths"]

    def test_openapi_schema_has_reports_path(self, client):
        """验证 OpenAPI schema 包含 reports 路径。"""
        response = client.get("/openapi.json")
        schema = response.json()
        assert "/api/v1/reports/{run_id}" in schema["paths"]


class TestDevicesEndpoint:
    """设备端点测试。"""

    def test_devices_endpoint_returns_list(self, client):
        """验证设备 API 端点返回列表。"""
        response = client.get("/api/v1/devices")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_devices_endpoint_empty_list_initially(self, client):
        """验证设备 API 端点返回列表格式。"""
        response = client.get("/api/v1/devices")
        data = response.json()
        assert isinstance(data, list)


class TestRunsEndpoint:
    """任务端点测试。"""

    def test_runs_endpoint_returns_list(self, client):
        """验证任务 API 端点返回列表。"""
        response = client.get("/api/v1/runs")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_runs_endpoint_empty_list_initially(self, client):
        """验证任务 API 端点初始返回空列表。"""
        response = client.get("/api/v1/runs")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestReportsEndpoint:
    """报告端点测试。"""

    def test_reports_endpoint_returns_404_for_nonexistent_run(self, client):
        """验证报告 API 端点对不存在的任务返回 404。"""
        response = client.get("/api/v1/reports/99999")
        assert response.status_code == 404

    def test_reports_endpoint_with_valid_run(self, client):
        """验证报告 API 端点对有效任务返回 JSON。"""
        # 首先创建一个计划
        plan_response = client.post(
            "/api/v1/runs/plans",
            json={
                "name": "测试计划",
                "upgrade_type": "full",
                "package_path": "/tmp/update.zip",
            },
        )
        assert plan_response.status_code == 200
        plan_id = plan_response.json()["plan_id"]

        # 创建任务
        run_response = client.post(
            "/api/v1/runs",
            json={
                "plan_id": plan_id,
            },
        )
        assert run_response.status_code == 200
        run_id = run_response.json()["run_id"]

        # 获取报告
        response = client.get(f"/api/v1/reports/{run_id}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        data = response.json()
        assert data["run_id"] == run_id
