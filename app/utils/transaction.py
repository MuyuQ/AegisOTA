"""数据库事务管理工具。

提供事务上下文管理器和装饰器，确保操作失败时自动回滚。
"""

import logging
from contextlib import contextmanager
from functools import wraps
from typing import Callable, Generator, Optional, TypeVar

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

T = TypeVar("T")


@contextmanager
def transaction(db: Session, auto_commit: bool = True) -> Generator[Session, None, None]:
    """事务上下文管理器。

    在上下文块结束时自动提交或回滚事务。

    Args:
        db: SQLAlchemy 会话
        auto_commit: 是否在成功时自动提交（默认 True）

    Usage:
        with transaction(db):
            db.add(obj)
            # 成功时自动提交，异常时自动回滚
    """
    try:
        yield db
        if auto_commit:
            db.commit()
    except Exception as e:
        logger.error(f"Transaction failed, rolling back: {e}")
        db.rollback()
        raise


def with_transaction(auto_commit: bool = True) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """事务装饰器。

    为服务方法添加事务处理，失败时自动回滚。

    Args:
        auto_commit: 是否在成功时自动提交（默认 True）

    Usage:
        @with_transaction()
        def create_user(self, db, name):
            user = User(name=name)
            db.add(user)
            return user

    Note:
        被装饰的方法必须接收一个名为 'db' 的 Session 参数。
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # 查找 db 参数
            db: Optional[Session] = None

            # 从 kwargs 中获取
            if "db" in kwargs:
                db = kwargs["db"]

            # 从 args 中获取（假设 self 是第一个参数，db 是属性）
            if db is None and args:
                # 检查 args 中是否有 Session 类型
                for arg in args:
                    if isinstance(arg, Session):
                        db = arg
                        break

            # 如果 db 是 self 的属性
            if db is None and args and hasattr(args[0], "db"):
                db = args[0].db

            if db is None:
                raise ValueError("with_transaction decorator requires a 'db' Session parameter")

            try:
                result = func(*args, **kwargs)
                if auto_commit:
                    db.commit()
                return result
            except Exception as e:
                logger.error(f"Transaction in {func.__name__} failed, rolling back: {e}")
                db.rollback()
                raise

        return wrapper
    return decorator


class TransactionalMixin:
    """事务支持混入类。

    为服务类提供事务处理方法。
    """

    def _execute_in_transaction(
        self,
        db: Session,
        operation: Callable[..., T],
        *args,
        auto_commit: bool = True,
        **kwargs
    ) -> T:
        """在事务中执行操作。

        Args:
            db: SQLAlchemy 会话
            operation: 要执行的操作函数
            auto_commit: 是否在成功时自动提交

        Returns:
            操作的结果

        Raises:
            操作失败时抛出原始异常，事务已回滚
        """
        try:
            result = operation(*args, **kwargs)
            if auto_commit:
                db.commit()
            return result
        except Exception as e:
            logger.error(f"Transaction failed, rolling back: {e}")
            db.rollback()
            raise


def safe_commit(db: Session) -> bool:
    """安全提交事务。

    尝试提交事务，失败时回滚并返回 False。

    Args:
        db: SQLAlchemy 会话

    Returns:
        True 表示提交成功，False 表示失败
    """
    try:
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Commit failed, rolling back: {e}")
        db.rollback()
        return False


def safe_rollback(db: Session) -> bool:
    """安全回滚事务。

    尝试回滚事务，失败时仅记录日志。

    Args:
        db: SQLAlchemy 会话

    Returns:
        True 表示回滚成功，False 表示失败
    """
    try:
        db.rollback()
        return True
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return False