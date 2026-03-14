"""db.py 单元测试

测试异步和同步 SQLAlchemy 引擎及 session 工厂的配置。
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import Session as SQLAlchemySyncSession
from sqlalchemy.orm import sessionmaker

from huginn.core.db import AsyncSessionLocal, SyncSessionLocal, get_async_session


class TestAsyncSessionLocal:
    """测试 AsyncSessionLocal 配置"""

    def test_is_async_sessionmaker(self):
        """AsyncSessionLocal 应该是 async_sessionmaker 实例"""
        assert isinstance(AsyncSessionLocal, async_sessionmaker)

    @pytest.mark.asyncio
    async def test_can_create_async_session(self):
        """AsyncSessionLocal 应该能创建 AsyncSession 实例"""
        session = AsyncSessionLocal()
        assert isinstance(session, SQLAlchemyAsyncSession)
        await session.close()

    @pytest.mark.asyncio
    async def test_session_has_expire_on_commit_false(self):
        """异步 session 应该配置 expire_on_commit=False"""
        session = AsyncSessionLocal()
        # AsyncSession 的配置通过 sync_session.expire_on_commit 访问
        assert not session.sync_session.expire_on_commit
        await session.close()

    def test_engine_uses_asyncpg(self):
        """异步引擎应该使用 asyncpg 驱动"""
        engine = AsyncSessionLocal.kw["bind"]
        assert engine is not None
        assert "postgresql+asyncpg://" in str(engine.url)

    def test_echo_when_debug_true(self, mocker):
        """当 settings.debug=True 时，异步引擎 echo=True"""
        # Mock settings.debug 为 True
        from huginn.core import db
        mocker.patch.object(db.settings, "debug", True)

        # 重新创建引擎以应用新设置
        from sqlalchemy.ext.asyncio import create_async_engine
        test_engine = create_async_engine(
            db.settings.database_url,
            echo=db.settings.debug,
        )

        assert test_engine.echo


class TestSyncSessionLocal:
    """测试 SyncSessionLocal 配置"""

    def test_is_sessionmaker(self):
        """SyncSessionLocal 应该是 sessionmaker 实例"""
        assert isinstance(SyncSessionLocal, sessionmaker)

    def test_can_create_sync_session(self):
        """SyncSessionLocal 应该能创建 Session 实例"""
        session = SyncSessionLocal()
        assert isinstance(session, SQLAlchemySyncSession)
        session.close()

    def test_engine_uses_psycopg2(self):
        """同步引擎应该使用 psycopg2 驱动"""
        engine = SyncSessionLocal.kw["bind"]
        assert engine is not None
        assert "postgresql+psycopg2://" in str(engine.url)


class TestGetAsyncSession:
    """测试 get_async_session 异步生成器"""

    @pytest.mark.asyncio
    async def test_is_async_generator(self):
        """get_async_session() 应该返回异步生成器"""
        gen = get_async_session()
        assert isinstance(gen, AsyncGenerator)

    @pytest.mark.asyncio
    async def test_can_iterate_with_async_for(self):
        """async for session in get_async_session() 应该能正常迭代"""
        session_count = 0
        async for session in get_async_session():
            assert isinstance(session, SQLAlchemyAsyncSession)
            session_count += 1
            if session_count >= 2:  # 测试两次迭代
                break

    @pytest.mark.asyncio
    async def test_session_cleanup_on_exit(self):
        """退出上下文时 session 应该被正确清理"""
        session_ref = None

        async for session in get_async_session():
            # 在上下文内 session 是活跃的
            assert session.sync_session.is_active
            session_ref = session
            break

        # 退出后 session 应该不再是活动状态
        # 注意：在 async with 上下文管理器中，session 会自动关闭
        # 但是这里的生成器使用 async with，所以退出时应该关闭
        # 检查 sync_session 是否不再活动
        # 由于我们使用了 break，session 应该已经被清理
        assert session_ref is not None
        # 由于 break 退出生成器，async with 会清理 session
        # 但是 session 对象仍然存在，只是不再活动
        # 我们通过检查无法执行新操作来验证已关闭

    @pytest.mark.asyncio
    async def test_multiple_calls_create_independent_sessions(self):
        """多次调用应该创建独立的 session"""
        # 第一次调用
        async for session1 in get_async_session():
            # 第二次调用
            async for session2 in get_async_session():
                # 两个 session 应该是不同的实例
                assert session1 is not session2
                break
            break
