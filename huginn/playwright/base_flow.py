"""Playwright Flow 抽象基类.

这个模块提供了 BaseFlow 抽象基类，用于定义 Playwright 采集流程的接口。
所有 Playwright 采集 Flow 都应该继承自 BaseFlow 并实现必需的方法。

典型用法:
    class MyFlow(BaseFlow):
        name = "my_flow"
        source_category = "tech"

        async def run(self, page: Page) -> list[dict]:
            await page.goto("https://example.com")
            return [{"title": await page.title()}]
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class BaseFlow(ABC):
    """Playwright 采集流程抽象基类.

    这个类定义了所有 Playwright 采集流程必须实现的接口。
    子类必须提供 name 和 source_category 类属性，并实现 run() 方法。

    Attributes:
        name: Flow 的唯一标识名称（类属性）
        source_category: 数据源分类，如 "tech", "finance", "social"（类属性）

    Example:
        >>> class GitHubTrendingFlow(BaseFlow):
        ...     name = "github_trending"
        ...     source_category = "tech"
        ...
        ...     async def run(self, page: Page) -> list[dict]:
        ...         await page.goto("https://github.com/trending")
        ...         return [{"data": "extracted"}]

    生命周期方法:
        - before_run(): 执行前钩子（可选覆盖）
        - run(): 必须实现，执行采集逻辑
        - after_run(items): 执行后钩子（可选覆盖）
    """

    # 类属性，子类必须定义
    name: str
    source_category: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """验证子类是否定义了必需的类属性.

        当创建 BaseFlow 的子类时，这个方法会被自动调用，
        用于检查子类是否定义了 name 和 source_category 类属性。

        Args:
            **kwargs: 传递给父类的额外关键字参数

        Raises:
            TypeError: 如果子类未定义 name 或 source_category 类属性
        """
        super().__init_subclass__(**kwargs)

        # 检查是否定义了 name 类属性
        if "name" not in cls.__dict__:
            raise TypeError(
                f"Class '{cls.__name__}' must define a 'name' class attribute"
            )

        # 检查是否定义了 source_category 类属性
        if "source_category" not in cls.__dict__:
            raise TypeError(
                f"Class '{cls.__name__}' must define a 'source_category' class attribute"
            )

    @abstractmethod
    async def run(self, page: Page) -> list[dict]:
        """执行采集流程的核心逻辑.

        这个方法必须由子类实现，包含实际的采集逻辑。

        Args:
            page: Playwright Page 对象，用于浏览器交互

        Returns:
            list[dict]: 采集到的数据列表，每个元素是一个字典

        Example:
            >>> async def run(self, page: Page) -> list[dict]:
            ...     await page.goto("https://example.com")
            ...     title = await page.title()
            ...     return [{"title": title}]
        """
        pass

    async def before_run(self) -> None:
        """执行采集前的钩子方法.

        这个方法在 run() 之前被调用，可以用于执行初始化操作，
        如设置页面 viewport、注入 JavaScript、登录等。

        默认实现为空，子类可以选择覆盖。

        Example:
            >>> async def before_run(self) -> None:
            ...     # 设置视口大小
            ...     await self.page.set_viewport_size({"width": 1920, "height": 1080})
        """
        pass

    async def after_run(self, items: list[dict]) -> None:
        """执行采集后的钩子方法.

        这个方法在 run() 之后被调用，接收采集到的数据列表，
        可以用于执行清理操作或后处理。

        默认实现为空，子类可以选择覆盖。

        Args:
            items: run() 方法返回的数据列表

        Example:
            >>> async def after_run(self, items: list[dict]) -> None:
            ...     # 记录采集结果
            ...     logger.info("Collected %d items", len(items))
        """
        pass
