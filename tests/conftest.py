"""测试配置和 fixtures。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db


@pytest.fixture
def test_engine():
    """创建测试数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """创建测试数据库会话。"""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def override_get_db(test_session):
    """覆盖 get_db dependency。"""
    def _get_db():
        yield test_session
    return _get_db