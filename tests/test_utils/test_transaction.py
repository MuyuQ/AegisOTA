"""事务管理工具测试。"""

import pytest
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import Session, declarative_base

from app.utils.transaction import (
    transaction,
    with_transaction,
    TransactionalMixin,
    safe_commit,
    safe_rollback,
)

Base = declarative_base()


class TestModel(Base):
    """测试用模型。"""
    __tablename__ = "test_models"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))


@pytest.fixture
def test_db():
    """创建测试数据库。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    yield session
    session.close()


class TestTransactionContext:
    """事务上下文管理器测试。"""

    def test_transaction_commit_on_success(self, test_db):
        """测试成功时提交事务。"""
        with transaction(test_db):
            obj = TestModel(name="test")
            test_db.add(obj)

        # 事务已提交，可以查询到
        result = test_db.query(TestModel).filter_by(name="test").first()
        assert result is not None
        assert result.name == "test"

    def test_transaction_rollback_on_exception(self, test_db):
        """测试异常时回滚事务。"""
        try:
            with transaction(test_db):
                obj = TestModel(name="test")
                test_db.add(obj)
                raise ValueError("Simulated error")
        except ValueError:
            pass

        # 事务已回滚，查询不到数据
        result = test_db.query(TestModel).filter_by(name="test").first()
        assert result is None

    def test_transaction_no_auto_commit(self, test_db):
        """测试禁用自动提交。"""
        from sqlalchemy.orm import Session

        with transaction(test_db, auto_commit=False):
            obj = TestModel(name="test")
            test_db.add(obj)

        # 创建新会话验证数据未提交到数据库
        engine = test_db.get_bind()
        new_session = Session(bind=engine)
        try:
            result = new_session.query(TestModel).filter_by(name="test").first()
            assert result is None
        finally:
            new_session.close()


class TestTransactionDecorator:
    """事务装饰器测试。"""

    def test_decorator_with_db_kwarg(self, test_db):
        """测试装饰器处理 db 关键字参数。"""
        @with_transaction()
        def create_obj(db, name):
            obj = TestModel(name=name)
            db.add(obj)
            return obj

        result = create_obj(db=test_db, name="test")
        assert result.name == "test"

        # 验证已提交
        found = test_db.query(TestModel).filter_by(name="test").first()
        assert found is not None

    def test_decorator_with_db_in_args(self, test_db):
        """测试装饰器处理 db 位置参数。"""
        @with_transaction()
        def create_obj(db, name):
            obj = TestModel(name=name)
            db.add(obj)
            return obj

        result = create_obj(test_db, "test")
        assert result.name == "test"

        found = test_db.query(TestModel).filter_by(name="test").first()
        assert found is not None

    def test_decorator_rollback_on_exception(self, test_db):
        """测试装饰器异常时回滚。"""
        @with_transaction()
        def create_obj(db, name, fail=False):
            obj = TestModel(name=name)
            db.add(obj)
            if fail:
                raise RuntimeError("Simulated error")
            return obj

        with pytest.raises(RuntimeError):
            create_obj(db=test_db, name="test", fail=True)

        # 验证已回滚
        found = test_db.query(TestModel).filter_by(name="test").first()
        assert found is None

    def test_decorator_no_auto_commit(self, test_db):
        """测试装饰器禁用自动提交。"""
        from sqlalchemy.orm import Session

        @with_transaction(auto_commit=False)
        def create_obj(db, name):
            obj = TestModel(name=name)
            db.add(obj)
            return obj

        create_obj(db=test_db, name="test")

        # 创建新会话验证数据未提交到数据库
        engine = test_db.get_bind()
        new_session = Session(bind=engine)
        try:
            found = new_session.query(TestModel).filter_by(name="test").first()
            assert found is None
        finally:
            new_session.close()

    def test_decorator_requires_db_parameter(self, test_db):
        """测试装饰器要求 db 参数。"""
        @with_transaction()
        def no_db_param():
            return "ok"

        with pytest.raises(ValueError, match="requires a 'db' Session parameter"):
            no_db_param()


class TestTransactionalMixin:
    """事务混入类测试。"""

    class TestService(TransactionalMixin):
        """测试服务类。"""

        def __init__(self, db):
            self.db = db

        def create_obj(self, name):
            def operation():
                obj = TestModel(name=name)
                self.db.add(obj)
                return obj

            return self._execute_in_transaction(self.db, operation)

    def test_mixin_execute_success(self, test_db):
        """测试混入类执行成功。"""
        service = self.TestService(test_db)
        result = service.create_obj("test")

        assert result.name == "test"

        found = test_db.query(TestModel).filter_by(name="test").first()
        assert found is not None

    def test_mixin_execute_rollback(self, test_db):
        """测试混入类执行失败回滚。"""
        service = self.TestService(test_db)

        def failing_operation():
            obj = TestModel(name="test")
            test_db.add(obj)
            raise ValueError("Simulated error")

        with pytest.raises(ValueError):
            service._execute_in_transaction(test_db, failing_operation)

        found = test_db.query(TestModel).filter_by(name="test").first()
        assert found is None


class TestSafeFunctions:
    """安全函数测试。"""

    def test_safe_commit_success(self, test_db):
        """测试安全提交成功。"""
        obj = TestModel(name="test")
        test_db.add(obj)

        result = safe_commit(test_db)

        assert result is True
        found = test_db.query(TestModel).filter_by(name="test").first()
        assert found is not None

    def test_safe_rollback_success(self, test_db):
        """测试安全回滚成功。"""
        obj = TestModel(name="test")
        test_db.add(obj)

        result = safe_rollback(test_db)

        assert result is True
        # 回滚后数据不在数据库中
        test_db.commit()  # 需要提交来验证
        found = test_db.query(TestModel).filter_by(name="test").first()
        assert found is None

    def test_safe_commit_with_exception(self, test_db):
        """测试安全提交异常处理。"""
        # 创建一个无效状态来触发异常
        obj1 = TestModel(id=1, name="test1")
        obj2 = TestModel(id=1, name="test2")  # 重复 ID
        test_db.add(obj1)
        test_db.commit()

        test_db.add(obj2)
        result = safe_commit(test_db)

        assert result is False