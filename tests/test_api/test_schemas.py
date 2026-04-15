"""API schemas 测试。"""

from app.api.schemas import (
    ErrorResponse,
    PaginatedResponse,
    PaginationInfo,
    SuccessResponse,
)


class TestPaginationInfo:
    """PaginationInfo 测试类。"""

    def test_create_basic(self):
        """测试基本创建。"""
        info = PaginationInfo.create(total=100, limit=10, offset=0)

        assert info.total == 100
        assert info.limit == 10
        assert info.offset == 0
        assert info.has_more is True

    def test_has_more_true(self):
        """测试 has_more 为 True 的情况。"""
        info = PaginationInfo.create(total=100, limit=10, offset=50)

        assert info.has_more is True  # 50 + 10 = 60 < 100

    def test_has_more_false(self):
        """测试 has_more 为 False 的情况。"""
        info = PaginationInfo.create(total=100, limit=10, offset=95)

        assert info.has_more is False  # 95 + 10 = 105 >= 100

    def test_has_more_exact_boundary(self):
        """测试边界情况。"""
        info = PaginationInfo.create(total=100, limit=10, offset=90)

        assert info.has_more is False  # 90 + 10 = 100, not < 100


class TestPaginatedResponse:
    """PaginatedResponse 测试类。"""

    def test_create_with_data(self):
        """测试创建带数据的响应。"""
        data = [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
        response = PaginatedResponse.create(data=data, total=10, limit=2, offset=0)

        assert len(response.data) == 2
        assert response.pagination.total == 10
        assert response.pagination.limit == 2
        assert response.pagination.offset == 0
        assert response.pagination.has_more is True

    def test_create_empty_data(self):
        """测试创建空数据响应。"""
        response = PaginatedResponse.create(data=[], total=0, limit=10, offset=0)

        assert len(response.data) == 0
        assert response.pagination.total == 0
        assert response.pagination.has_more is False

    def test_from_query(self):
        """测试从查询结果创建。"""
        items = ["item1", "item2", "item3"]
        response = PaginatedResponse.from_query(
            query_result=items,
            total_count=100,
            limit=3,
            offset=0,
        )

        assert response.data == items
        assert response.pagination.total == 100

    def test_default_pagination(self):
        """测试默认分页参数。"""
        response = PaginatedResponse.create(data=[1, 2, 3], total=3)

        assert response.pagination.limit == 100
        assert response.pagination.offset == 0


class TestErrorResponse:
    """ErrorResponse 测试类。"""

    def test_create_with_detail(self):
        """测试创建带详情的错误响应。"""
        error = ErrorResponse.create(detail="Something went wrong")

        assert error.detail == "Something went wrong"
        assert error.code is None

    def test_create_with_code(self):
        """测试创建带错误码的错误响应。"""
        error = ErrorResponse.create(detail="Not found", code="NOT_FOUND")

        assert error.detail == "Not found"
        assert error.code == "NOT_FOUND"


class TestSuccessResponse:
    """SuccessResponse 测试类。"""

    def test_create_basic(self):
        """测试基本创建。"""
        response = SuccessResponse.create()

        assert response.status == "success"
        assert response.message is None
        assert response.data is None

    def test_create_with_message(self):
        """测试创建带消息的响应。"""
        response = SuccessResponse.create(message="Operation completed")

        assert response.message == "Operation completed"

    def test_create_with_data(self):
        """测试创建带数据的响应。"""
        response = SuccessResponse.create(data={"count": 5})

        assert response.data == {"count": 5}

    def test_create_full(self):
        """测试创建完整响应。"""
        response = SuccessResponse.create(
            message="Created successfully",
            data={"id": 1},
        )

        assert response.status == "success"
        assert response.message == "Created successfully"
        assert response.data == {"id": 1}
