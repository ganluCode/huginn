"""Playwright 引擎封装，提供浏览器自动化能力.

这个模块提供了 PlaywrightEngine 类，封装了 Playwright 的异步 API，
提供了简洁的接口用于启动浏览器、创建上下文和页面。

典型用法:
    async with PlaywrightEngine() as engine:
        page = await engine.new_page()
        await page.goto("https://example.com")
"""

import logging
from typing import Literal

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    PlaywrightContextManager,
)

logger = logging.getLogger(__name__)


class PlaywrightEngine:
    """Playwright 引擎类，封装浏览器生命周期管理.

    这个类提供了对 Playwright 浏览器的封装，支持:
    - 启动和停止浏览器（幂等操作）
    - Async context manager 支持
    - 创建浏览器上下文和页面
    - 自定义 headless 模式和浏览器类型

    Attributes:
        headless: 是否使用无头模式（默认 True）
        browser_type: 浏览器类型（chromium/firefox/webkit，默认 chromium）

    Example:
        >>> # 使用 async context manager
        >>> async with PlaywrightEngine() as engine:
        ...     page = await engine.new_page()
        ...     await page.goto("https://example.com")

        >>> # 手动管理生命周期
        >>> engine = PlaywrightEngine(headless=False)
        >>> await engine.start()
        >>> page = await engine.new_page()
        >>> await engine.stop()
    """

    def __init__(
        self,
        headless: bool = True,
        browser_type: Literal["chromium", "firefox", "webkit"] = "chromium",
    ) -> None:
        """初始化 Playwright 引擎.

        Args:
            headless: 是否使用无头模式，默认为 True
            browser_type: 浏览器类型，支持 "chromium", "firefox", "webkit"，
                         默认为 "chromium"
        """
        self.headless = headless
        self.browser_type = browser_type

        # 内部状态
        self._playwright_context_manager: PlaywrightContextManager | None = None
        self._playwright: any | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        """启动 Playwright 浏览器.

        这个方法是幂等的，可以多次调用而不会报错。
        如果浏览器已经启动，后续调用会被忽略。

        Raises:
            Exception: 当浏览器未安装或启动失败时抛出异常。
                      异常消息包含 "playwright install" 提示。

        Example:
            >>> engine = PlaywrightEngine()
            >>> await engine.start()
            >>> # 浏览器已启动
            >>> await engine.start()  # 不会报错，幂等操作
        """
        # 如果已经启动，直接返回（幂等性）
        if self._browser is not None:
            logger.debug("Playwright browser already started, ignoring start() call")
            return

        try:
            # 创建 async_playwright context manager
            self._playwright_context_manager = async_playwright()
            self._playwright = await self._playwright_context_manager.__aenter__()

            # 根据类型获取对应的浏览器 launcher
            browser_launcher = getattr(self._playwright, self.browser_type)

            # 启动浏览器
            self._browser = await browser_launcher.launch(headless=self.headless)

            logger.info(
                "Playwright browser started: type=%s, headless=%s",
                self.browser_type,
                self.headless,
            )

        except Exception as e:
            # 清理可能已创建的资源
            if self._playwright_context_manager is not None:
                try:
                    await self._playwright_context_manager.__aexit__(None, None, None)
                except Exception:
                    pass
                self._playwright_context_manager = None
            self._playwright = None
            self._browser = None

            # 提供友好的错误提示
            error_msg = str(e).lower()
            if "executable" in error_msg or "browser" in error_msg or "chromium" in error_msg:
                install_hint = (
                    f"Browser not found or not installed. "
                    f"Run: playwright install {self.browser_type}"
                )
                raise Exception(f"{install_hint}\nOriginal error: {e}") from e
            raise

    async def stop(self) -> None:
        """停止 Playwright 浏览器.

        这个方法是幂等的，可以多次调用而不会报错。
        如果浏览器已经停止，后续调用会被忽略。

        Example:
            >>> engine = PlaywrightEngine()
            >>> await engine.start()
            >>> await engine.stop()
            >>> # 浏览器已停止
            >>> await engine.stop()  # 不会报错，幂等操作
        """
        # 如果已经停止，直接返回（幂等性）
        if self._browser is None:
            logger.debug("Playwright browser already stopped, ignoring stop() call")
            return

        try:
            # 关闭浏览器
            if self._browser is not None:
                await self._browser.close()
                self._browser = None

            # 关闭 playwright context manager
            if self._playwright_context_manager is not None:
                await self._playwright_context_manager.__aexit__(None, None, None)
                self._playwright_context_manager = None

            self._playwright = None

            logger.info("Playwright browser stopped")

        except Exception as e:
            logger.error("Error stopping Playwright browser: %s", e)
            # 即使出错，也要清空状态，保持幂等性
            self._browser = None
            self._playwright = None
            self._playwright_context_manager = None
            raise

    async def new_context(self, **kwargs) -> BrowserContext:
        """创建一个新的浏览器上下文.

        浏览器上下文类似于隐身模式，拥有独立的 cookies、cache、storage 等。
        kwargs 会透传给底层的 new_context 方法。

        Args:
            **kwargs: 传递给 browser.new_context() 的参数。
                     常用参数包括:
                     - viewport: 视口大小，如 {"width": 1280, "height": 720}
                     - user_agent: 用户代理字符串
                     - locale: 语言设置，如 "zh-CN"
                     - timezone_id: 时区，如 "Asia/Shanghai"

        Returns:
            BrowserContext: 新创建的浏览器上下文对象

        Raises:
            RuntimeError: 如果浏览器尚未启动

        Example:
            >>> engine = PlaywrightEngine()
            >>> await engine.start()
            >>> context = await engine.new_context(
            ...     viewport={"width": 1920, "height": 1080},
            ...     user_agent="Custom Bot 1.0"
            ... )
            >>> page = await context.new_page()
        """
        if self._browser is None:
            raise RuntimeError(
                "Browser not started. Call start() first or use async context manager."
            )

        context = await self._browser.new_context(**kwargs)
        logger.debug("Created new browser context with kwargs: %s", kwargs)
        return context

    async def new_page(self) -> Page:
        """创建一个新的浏览器页面.

        这是创建页面的便捷方法，等同于创建一个新的浏览器上下文并在其中创建页面。
        对于大多数简单场景，这个方法就足够了。
        如果需要多个页面共享上下文（如共享 cookies），请先使用 new_context()。

        Returns:
            Page: 新创建的页面对象

        Raises:
            RuntimeError: 如果浏览器尚未启动

        Example:
            >>> engine = PlaywrightEngine()
            >>> await engine.start()
            >>> page = await engine.new_page()
            >>> await page.goto("https://example.com")
            >>> title = await page.title()
        """
        if self._browser is None:
            raise RuntimeError(
                "Browser not started. Call start() first or use async context manager."
            )

        page = await self._browser.new_page()
        logger.debug("Created new page")
        return page

    async def __aenter__(self) -> "PlaywrightEngine":
        """Async context manager 入口.

        Returns:
            PlaywrightEngine: 返回自身，支持 async with 语法

        Example:
            >>> async with PlaywrightEngine() as engine:
            ...     # 此时浏览器已启动
            ...     page = await engine.new_page()
        """
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager 退出.

        确保浏览器被正确关闭，即使发生异常。

        Args:
            exc_type: 异常类型（如果有）
            exc_val: 异常值（如果有）
            exc_tb: 异常追踪信息（如果有）
        """
        await self.stop()
