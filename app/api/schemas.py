"""API 响应模式定义。"""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationInfo(BaseModel):
    """分页信息。"""

    total: int
    limit: int
    offset: int
    has_more: bool

    @classmethod
    def create(cls, total: int, limit: int, offset: int) -> "PaginationInfo":
        """创建分页信息。

        Args:
            total: 总记录数
            limit: 每页数量
            offset: 偏移量

        Returns:
            分页信息对象
        """
        return cls(
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + limit < total,
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应模型。

    用于 API 列表接口返回分页数据。

    Attributes:
        data: 数据列表
        pagination: 分页信息
    """

    data: List[T]
    pagination: PaginationInfo

    @classmethod
    def create(
        cls,
        data: List[T],
        total: int,
        limit: int = 100,
        offset: int = 0,
    ) -> "PaginatedResponse[T]":
        """创建分页响应。

        Args:
            data: 数据列表
            total: 总记录数
            limit: 每页数量（默认 100）
            offset: 偏移量（默认 0）

        Returns:
            分页响应对象
        """
        return cls(
            data=data,
            pagination=PaginationInfo.create(total=total, limit=limit, offset=offset),
        )

    @classmethod
    def from_query(
        cls,
        query_result: List[T],
        total_count: int,
        limit: int = 100,
        offset: int = 0,
    ) -> "PaginatedResponse[T]":
        """从查询结果创建分页响应。

        Args:
            query_result: 查询结果列表
            total_count: 总记录数
            limit: 每页数量
            offset: 偏移量

        Returns:
            分页响应对象
        """
        return cls.create(
            data=query_result,
            total=total_count,
            limit=limit,
            offset=offset,
        )


class ErrorResponse(BaseModel):
    """错误响应模型。"""

    detail: str
    code: Optional[str] = None

    @classmethod
    def create(cls, detail: str, code: Optional[str] = None) -> "ErrorResponse":
        """创建错误响应。"""
        return cls(detail=detail, code=code)


class SuccessResponse(BaseModel):
    """成功响应模型。"""

    status: str = "success"
    message: Optional[str] = None
    data: Optional[dict] = None

    @classmethod
    def create(
        cls,
        message: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> "SuccessResponse":
        """创建成功响应。"""
        return cls(message=message, data=data)
