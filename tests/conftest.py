"""Pytest 配置和共享 fixtures"""

import os
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from huginn.core.models import Base

# 从环境变量获取同步数据库 URL
DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://huginn:huginn@localhost:5432/huginn_test"
)


@pytest.fixture(scope="session")
def sync_engine():
    """创建同步 SQLAlchemy Engine（session 级别，整个测试会话共享）"""
    engine = create_engine(DATABASE_URL_SYNC, echo=False)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def create_tables(sync_engine):
    """在测试开始时创建所有表，结束时删除"""
    Base.metadata.create_all(sync_engine)
    yield
    Base.metadata.drop_all(sync_engine)


@pytest.fixture(scope="function")
def db_session(sync_engine, _create_tables) -> Generator[Session, None, None]:
    """为每个测试函数创建独立的数据库会话

    每个测试在事务中运行，测试后回滚，保证测试间隔离
    """
    connection = sync_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    # 清理：回滚事务，关闭会话和连接
    session.close()
    transaction.rollback()
    connection.close()
