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

    def test_root_returns_json(self, client):
        """验证根端点返回 JSON。"""
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_root_content(self, client):
        """验证根端点内容。"""
        response = client.get("/")
        data = response.json()
        assert data["name"] == "AegisOTA"
        assert "version" in data
        assert "docs" in data
        assert "health" in data


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
        assert "/devices" in schema["paths"]

    def test_openapi_schema_has_runs_path(self, client):
        """验证 OpenAPI schema 包含 runs 路径。"""
        response = client.get("/openapi.json")
        schema = response.json()
        assert "/runs" in schema["paths"]

    def test_openapi_schema_has_reports_path(self, client):
        """验证 OpenAPI schema 包含 reports 路径。"""
        response = client.get("/openapi.json")
        schema = response.json()
        assert "/reports/{run_id}" in schema["paths"]


class TestDevicesEndpoint:
    """设备端点测试。"""

    def test_devices_endpoint_returns_list(self, client):
        """验证设备端点返回列表。"""
        response = client.get("/devices")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_devices_endpoint_empty_list_initially(self, client):
        """验证设备端点初始返回空列表。"""
        response = client.get("/devices")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestRunsEndpoint:
    """任务端点测试。"""

    def test_runs_endpoint_returns_list(self, client):
        """验证任务端点返回列表。"""
        response = client.get("/runs")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_runs_endpoint_empty_list_initially(self, client):
        """验证任务端点初始返回空列表。"""
        response = client.get("/runs")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestReportsEndpoint:
    """报告端点测试。"""

    def test_reports_endpoint_returns_json(self, client):
        """验证报告端点返回 JSON。"""
        response = client.get("/reports/1")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_reports_endpoint_returns_run_id(self, client):
        """验证报告端点返回 run_id。"""
        response = client.get("/reports/123")
        data = response.json()
        assert data["run_id"] == 123