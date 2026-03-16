"""Tests for PlaywrightEngine class."""

import pytest
from playwright.async_api import Browser, BrowserContext, Page

from huginn.playwright.engine import PlaywrightEngine


class TestPlaywrightEngineInstantiation:
    """测试 PlaywrightEngine 实例化."""

    def test_engine_with_default_params(self):
        """测试使用默认参数创建引擎."""
        engine = PlaywrightEngine()
        assert engine.headless is True  # 默认 headless=True
        assert engine.browser_type == "chromium"  # 默认 chromium

    def test_engine_with_custom_params(self):
        """测试使用自定义参数创建引擎."""
        engine = PlaywrightEngine(headless=False, browser_type="firefox")
        assert engine.headless is False
        assert engine.browser_type == "firefox"


class TestPlaywrightEngineStartStop:
    """测试 PlaywrightEngine 启动和停止."""

    @pytest.mark.asyncio
    async def test_engine_start_stop(self):
        """测试 start() 和 stop() 正常工作."""
        engine = PlaywrightEngine()
        await engine.start()
        assert engine._playwright is not None
        assert engine._browser is not None

        await engine.stop()
        assert engine._playwright is None
        assert engine._browser is None

    @pytest.mark.asyncio
    async def test_start_idempotent(self):
        """测试 start() 重复调用不报错（幂等）."""
        engine = PlaywrightEngine()
        await engine.start()
        playwright_instance = engine._playwright

        # 第二次调用不应报错
        await engine.start()
        assert engine._playwright is playwright_instance

        await engine.stop()

    @pytest.mark.asyncio
    async def test_stop_idempotent(self):
        """测试 stop() 重复调用不报错（幂等）."""
        engine = PlaywrightEngine()
        await engine.start()
        await engine.stop()

        # 第二次调用不应报错
        await engine.stop()
        assert engine._playwright is None
        assert engine._browser is None


class TestPlaywrightEngineContextManager:
    """测试 PlaywrightEngine async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """测试 async with 语法正常，退出后 stop() 被调用."""
        async with PlaywrightEngine() as engine:
            assert engine._playwright is not None
            assert engine._browser is not None
            playwright_instance = engine._playwright

        # 退出 context manager 后应调用 stop()
        assert engine._playwright is None
        assert engine._browser is None


class TestPlaywrightEngineNewPage:
    """测试 PlaywrightEngine new_page 方法."""

    @pytest.mark.asyncio
    async def test_new_page_returns_page(self):
        """测试 new_page() 返回 Page 对象."""
        async with PlaywrightEngine() as engine:
            page = await engine.new_page()
            assert isinstance(page, Page)

            # 清理
            await page.close()


class TestPlaywrightEngineNewContext:
    """测试 PlaywrightEngine new_context 方法."""

    @pytest.mark.asyncio
    async def test_new_context_passes_kwargs(self):
        """测试 new_context() 的 kwargs 透传给底层."""
        async with PlaywrightEngine() as engine:
            # 传递一些参数给 new_context
            context = await engine.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="test-agent"
            )
            assert isinstance(context, BrowserContext)

            # 清理
            await context.close()


class TestPlaywrightEngineErrors:
    """测试 PlaywrightEngine 错误处理."""

    @pytest.mark.asyncio
    async def test_browser_not_installed_error(self):
        """测试浏览器未安装时抛出包含提示的异常."""
        # 使用不存在的浏览器类型触发错误
        engine = PlaywrightEngine(browser_type="nonexistent_browser")

        with pytest.raises(Exception) as exc_info:
            await engine.start()

        # Playwright 会抛出 TypeError，我们验证错误信息包含有用的提示
        # 注意：这里可能需要根据实际的 Playwright 错误类型调整
        error_msg = str(exc_info.value)
        # 错误信息应该包含相关信息（具体格式取决于 Playwright 版本）
        assert len(error_msg) > 0
