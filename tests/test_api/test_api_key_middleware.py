"""API Key 中间件测试。"""

import pytest
from fastapi.testclient import TestClient

from app.main import APIKeyMiddleware, app


class TestAPIKeyMiddleware:
    """API Key 中间件测试类。"""

    def test_health_check_no_auth_required(self):
        """测试健康检查端点无需认证。"""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_web_pages_no_auth_required(self):
        """测试 web 页面无需认证。"""
        client = TestClient(app)
        # 首页
        response = client.get("/")
        assert response.status_code == 200

    def test_static_files_no_auth_required(self):
        """测试静态资源无需认证。"""
        client = TestClient(app)
        # CSS 文件
        response = client.get("/static/css/style.css")
        # 即使文件不存在，也不应该返回 401
        assert response.status_code != 401

    def test_api_without_keys_configured(self):
        """测试未配置 API Keys 时允许所有请求（开发模式）。"""
        # 默认配置下 API_KEYS 为空列表，应允许请求
        client = TestClient(app)
        response = client.get("/api/v1/devices")
        # 如果未配置 API Keys，应返回 200 或其他非 401 状态
        assert response.status_code != 401


class TestAPIKeyMiddlewareWithKeys:
    """配置 API Keys 后的中间件测试。"""

    @pytest.fixture
    def app_with_keys(self):
        """创建带 API Key 配置的测试应用。"""
        from fastapi import FastAPI

        test_app = FastAPI()

        # 先添加 API Key 中间件，然后再定义路由
        test_app.add_middleware(
            APIKeyMiddleware,
            api_keys=["test-key-123", "admin-key-456"],
            header_name="X-API-Key",
        )

        # 添加简单测试路由
        @test_app.get("/api/v1/test")
        async def test_endpoint():
            return {"message": "success"}

        @test_app.get("/health")
        async def health():
            return {"status": "healthy"}

        return test_app

    def test_api_with_valid_key(self, app_with_keys):
        """测试有效 API Key 可访问 API。"""
        client = TestClient(app_with_keys)
        response = client.get("/api/v1/test", headers={"X-API-Key": "test-key-123"})
        assert response.status_code == 200
        assert response.json()["message"] == "success"

    def test_api_with_admin_key(self, app_with_keys):
        """测试管理员 API Key 可访问 API。"""
        client = TestClient(app_with_keys)
        response = client.get("/api/v1/test", headers={"X-API-Key": "admin-key-456"})
        assert response.status_code == 200

    def test_api_without_key(self, app_with_keys):
        """测试无 API Key 时返回 401。"""
        client = TestClient(app_with_keys)
        response = client.get("/api/v1/test")
        assert response.status_code == 401
        assert "Invalid or missing API key" in response.json()["detail"]

    def test_api_with_invalid_key(self, app_with_keys):
        """测试无效 API Key 时返回 401。"""
        client = TestClient(app_with_keys)
        response = client.get("/api/v1/test", headers={"X-API-Key": "invalid-key"})
        assert response.status_code == 401

    def test_health_check_still_public(self, app_with_keys):
        """测试健康检查端点仍无需认证。"""
        client = TestClient(app_with_keys)
        response = client.get("/health")
        assert response.status_code == 200

    def test_authenticate_header_in_response(self, app_with_keys):
        """测试 401 响应包含 WWW-Authenticate 头。"""
        client = TestClient(app_with_keys)
        response = client.get("/api/v1/test")
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers
        assert "ApiKey" in response.headers["WWW-Authenticate"]


class TestAPIKeyMiddlewareEdgeCases:
    """API Key 中间件边界情况测试。"""

    @pytest.fixture
    def app_custom_header(self):
        """创建使用自定义请求头的测试应用。"""
        from fastapi import FastAPI

        test_app = FastAPI()

        # 先添加中间件
        test_app.add_middleware(
            APIKeyMiddleware,
            api_keys=["secret-key"],
            header_name="X-Custom-Auth",
        )

        # 然后添加路由
        @test_app.get("/api/v1/test")
        async def test_endpoint():
            return {"message": "success"}

        return test_app

    def test_custom_header_name(self, app_custom_header):
        """测试自定义请求头名称。"""
        client = TestClient(app_custom_header)
        # 使用自定义请求头
        response = client.get("/api/v1/test", headers={"X-Custom-Auth": "secret-key"})
        assert response.status_code == 200

        # 使用默认请求头应失败
        response = client.get("/api/v1/test", headers={"X-API-Key": "secret-key"})
        assert response.status_code == 401

    @pytest.fixture
    def app_empty_keys(self):
        """创建空 API Keys 配置的测试应用。"""
        from fastapi import FastAPI

        test_app = FastAPI()

        # 先添加中间件（空 keys 配置）
        test_app.add_middleware(
            APIKeyMiddleware,
            api_keys=[],
            header_name="X-API-Key",
        )

        # 然后添加路由
        @test_app.get("/api/v1/test")
        async def test_endpoint():
            return {"message": "success"}

        return test_app

    def test_empty_keys_allows_all(self, app_empty_keys):
        """测试空 API Keys 允许所有请求。"""
        client = TestClient(app_empty_keys)
        response = client.get("/api/v1/test")
        assert response.status_code == 200

        response = client.get("/api/v1/test", headers={"X-API-Key": "any-key"})
        assert response.status_code == 200

    def test_case_sensitive_key(self):
        """测试 API Key 区分大小写。"""
        from fastapi import FastAPI

        test_app = FastAPI()

        # 先添加中间件
        test_app.add_middleware(
            APIKeyMiddleware,
            api_keys=["Secret-Key"],
            header_name="X-API-Key",
        )

        # 然后添加路由
        @test_app.get("/api/v1/test")
        async def test_endpoint():
            return {"message": "success"}

        client = TestClient(test_app)
        # 正确大小写
        response = client.get("/api/v1/test", headers={"X-API-Key": "Secret-Key"})
        assert response.status_code == 200

        # 错误大小写
        response = client.get("/api/v1/test", headers={"X-API-Key": "secret-key"})
        assert response.status_code == 401
