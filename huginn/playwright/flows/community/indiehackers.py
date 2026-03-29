"""IndieHackers 社区热帖采集 Flow.

使用 Playwright 渲染 IndieHackers 首页，提取社区热帖数据。

典型用法:
    flow = IndieHackersFlow()
    # 通过 huginn.playwright.runner 执行
"""

import logging

from playwright.async_api import Page

from huginn.core.constants import Category
from huginn.playwright.base_flow import BaseFlow

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.indiehackers.com"


class IndieHackersFlow(BaseFlow):
    """IndieHackers 社区热帖采集 Flow.

    采集 IndieHackers 首页 Feed 中的热帖，提取标题、链接、作者、
    投票数、评论数和内容预览。

    Attributes:
        name: Flow 唯一标识
        source_category: 数据源分类（社区）
    """

    name = "indiehackers"
    source_category = Category.COMMUNITY

    async def run(self, page: Page) -> list[dict]:
        """采集 IndieHackers 首页热帖.

        Args:
            page: Playwright Page 对象

        Returns:
            帖子数据列表，每项包含 title、url、author、votes、comments、preview。

        Raises:
            playwright.async_api.TimeoutError: 页面加载超时时向上传播。
        """
        await page.goto(_BASE_URL + "/")
        # 超时异常直接向上传播，不在此捕获
        await page.wait_for_selector(".feed-item", timeout=15000)

        elements = await page.query_selector_all(".feed-item")
        if not elements:
            logger.warning("IndieHackers: no .feed-item elements found on page")
            return []

        items: list[dict] = []
        for element in elements:
            try:
                item = await self._extract_item(element)
            except Exception as exc:
                logger.warning("IndieHackers: failed to process feed item: %s", exc)
                continue
            if item is not None:
                items.append(item)

        return items

    async def _extract_item(self, element) -> dict | None:
        """从单个 .feed-item 元素中提取帖子数据.

        Args:
            element: Playwright ElementHandle，对应一个 .feed-item 节点

        Returns:
            包含帖子字段的 dict；title 或 url 缺失时返回 None。
        """
        link_el = await element.query_selector("a.content-title")

        title: str | None = None
        url: str | None = None

        if link_el is not None:
            raw_title = await link_el.inner_text()
            title = raw_title.strip() if raw_title else None

            href = await link_el.get_attribute("href")
            if href:
                url = href if href.startswith("http") else f"{_BASE_URL}{href}"

        if not title or not url:
            logger.warning(
                "IndieHackers: skipping feed item with missing title or url "
                "(title=%r, url=%r)",
                title,
                url,
            )
            return None

        author = await self._get_text(element, ".author")
        votes = await self._get_text(element, ".votes-count")
        comments = await self._get_text(element, ".comments-count")
        preview = await self._get_text(element, ".content-preview")

        return {
            "title": title,
            "url": url,
            "author": author,
            "votes": votes,
            "comments": comments,
            "preview": preview,
        }

    async def _get_text(self, element, selector: str) -> str | None:
        """从子元素中提取文本内容，元素不存在时返回 None.

        Args:
            element: 父元素 ElementHandle
            selector: CSS 选择器

        Returns:
            去除首尾空白的文本，或 None。
        """
        el = await element.query_selector(selector)
        if el is None:
            return None
        text = await el.inner_text()
        return text.strip() if text else None
