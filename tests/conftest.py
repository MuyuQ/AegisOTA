"""全局测试配置和 fixtures。"""

import gc

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import close_all_sessions, sessionmaker

from app.database import Base, SessionLocal, engine, get_db


@pytest.fixture(autouse=True)
def cleanup_db():
    """每个测试后清理数据库连接。"""
    yield
    # 关闭所有活动会话
    close_all_sessions()
    # 释放引擎连接池
    engine.dispose()
    # 强制垃圾回收以关闭未引用的 sqlite3 连接
    gc.collect()


@pytest.fixture
def test_engine():
    """创建测试数据库引擎。"""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture
def test_session(test_engine):
    """创建测试数据库会话。"""
    session_factory = sessionmaker(bind=test_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def db_session():
    """提供独立的数据库会话用于测试。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def override_get_db(test_session):
    """覆盖 FastAPI 的 get_db dependency。"""

    def _get_db():
        yield test_session

    return _get_db


@pytest.fixture
def app_with_db_override(override_get_db):
    """提供已覆盖数据库依赖的 FastAPI 应用。"""
    app = FastAPI()
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()
