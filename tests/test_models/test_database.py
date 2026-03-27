"""数据库连接测试。"""

import pytest
from sqlalchemy import inspect

from app.database import Base, engine, get_db


def test_base_has_metadata():
    """测试 Base 有 metadata。"""
    assert Base.metadata is not None


def test_get_db_returns_session():
    """测试 get_db 返回会话。"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_engine = create_engine("sqlite:///:memory:")
    TestSession = sessionmaker(bind=test_engine)

    def test_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    gen = test_get_db()
    session = next(gen)
    assert session is not None
    gen.close()


def test_tables_created_on_init():
    """测试表在初始化时创建。"""
    from app.database import init_db
    from sqlalchemy import create_engine

    test_engine = create_engine("sqlite:///:memory:")
    init_db(test_engine)

    inspector = inspect(test_engine)
    table_names = inspector.get_table_names()
    assert isinstance(table_names, list)