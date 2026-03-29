"""Tests for IndieHackersFlow."""

import logging
from unittest.mock import AsyncMock

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from huginn.core.constants import Category
from huginn.playwright.flows.community.indiehackers import IndieHackersFlow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_link_el(title: str | None, href: str | None) -> AsyncMock:
    """Build a mock 'a.content-title' element."""
    el = AsyncMock()
    el.inner_text = AsyncMock(return_value=title or "")
    el.get_attribute = AsyncMock(return_value=href)
    return el


def _make_text_el(text: str) -> AsyncMock:
    """Build a mock element that returns plain text."""
    el = AsyncMock()
    el.inner_text = AsyncMock(return_value=text)
    return el


def _make_feed_element(
    title: str | None = "Test Post Title",
    href: str | None = "/posts/test-post",
    author: str | None = "testuser",
    votes: str | None = "42",
    comments: str | None = "7",
    preview: str | None = "This is a preview.",
) -> AsyncMock:
    """Build a mock .feed-item ElementHandle.

    Args:
        title: text returned by a.content-title inner_text()
        href: href returned by a.content-title get_attribute('href')
        author/votes/comments/preview: optional field texts; None means the
            sub-element is absent (query_selector returns None).
    """
    link_el = _make_link_el(title, href)

    optional: dict[str, str | None] = {
        ".author": author,
        ".votes-count": votes,
        ".comments-count": comments,
        ".content-preview": preview,
    }

    async def _query_selector(selector: str):
        if selector == "a.content-title":
            return link_el
        value = optional.get(selector)
        if value is not None:
            return _make_text_el(value)
        return None

    element = AsyncMock()
    element.query_selector = AsyncMock(side_effect=_query_selector)
    return element


def _make_page(elements: list[AsyncMock]) -> AsyncMock:
    """Build a mock Playwright Page that returns *elements* for query_selector_all."""
    page = AsyncMock()
    page.goto = AsyncMock(return_value=None)
    page.wait_for_selector = AsyncMock(return_value=AsyncMock())
    page.query_selector_all = AsyncMock(return_value=elements)
    return page


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def flow() -> IndieHackersFlow:
    return IndieHackersFlow()


# ---------------------------------------------------------------------------
# F-001 / F-002: Class attributes
# ---------------------------------------------------------------------------

class TestIndieHackersFlowAttributes:
    def test_name(self, flow):
        assert flow.name == "indiehackers"

    def test_source_category(self, flow):
        assert flow.source_category == Category.COMMUNITY

    def test_run_is_async(self, flow):
        import inspect
        assert inspect.iscoroutinefunction(flow.run)


# ---------------------------------------------------------------------------
# F-005: Normal collection (3 posts, all fields present)
# ---------------------------------------------------------------------------

class TestNormalCollection:
    @pytest.mark.asyncio
    async def test_normal_collection(self, flow):
        """Three feed items with all fields → run() returns list of length 3."""
        elements = [
            _make_feed_element(
                title=f"Post {i}",
                href=f"/posts/post-{i}",
                author=f"author{i}",
                votes=str(i * 10),
                comments=str(i),
                preview=f"Preview for post {i}.",
            )
            for i in range(1, 4)
        ]
        page = _make_page(elements)

        items = await flow.run(page)

        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_normal_collection_required_keys(self, flow):
        """Each item must contain title, url, author, votes, comments, preview."""
        elements = [_make_feed_element()]
        page = _make_page(elements)

        items = await flow.run(page)

        assert len(items) == 1
        item = items[0]
        for key in ("title", "url", "author", "votes", "comments", "preview"):
            assert key in item, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_relative_href_becomes_full_url(self, flow):
        """Relative href is prefixed with https://www.indiehackers.com."""
        elements = [_make_feed_element(href="/posts/my-post")]
        page = _make_page(elements)

        items = await flow.run(page)

        assert items[0]["url"] == "https://www.indiehackers.com/posts/my-post"

    @pytest.mark.asyncio
    async def test_absolute_href_kept_as_is(self, flow):
        """Absolute href is stored without modification."""
        elements = [_make_feed_element(href="https://www.indiehackers.com/posts/abc")]
        page = _make_page(elements)

        items = await flow.run(page)

        assert items[0]["url"] == "https://www.indiehackers.com/posts/abc"

    @pytest.mark.asyncio
    async def test_goto_called_with_homepage(self, flow):
        """run() must call page.goto() with the IndieHackers homepage URL."""
        page = _make_page([])
        await flow.run(page)
        page.goto.assert_called_once_with("https://www.indiehackers.com/")

    @pytest.mark.asyncio
    async def test_wait_for_selector_called(self, flow):
        """run() must call page.wait_for_selector('.feed-item', timeout=15000)."""
        page = _make_page([])
        await flow.run(page)
        page.wait_for_selector.assert_called_once_with(".feed-item", timeout=15000)


# ---------------------------------------------------------------------------
# F-006: Edge cases
# ---------------------------------------------------------------------------

class TestMissingFields:
    @pytest.mark.asyncio
    async def test_missing_optional_fields_are_none(self, flow):
        """Optional fields (author/votes/comments/preview) absent → None in result."""
        elements = [
            _make_feed_element(author=None, votes=None, comments=None, preview=None)
        ]
        page = _make_page(elements)

        items = await flow.run(page)

        assert len(items) == 1
        item = items[0]
        assert item["author"] is None
        assert item["votes"] is None
        assert item["comments"] is None
        assert item["preview"] is None
        # title and url should still be present
        assert item["title"] == "Test Post Title"
        assert item["url"] == "https://www.indiehackers.com/posts/test-post"

    @pytest.mark.asyncio
    async def test_missing_title_skips_item(self, flow, caplog):
        """Item with empty title is skipped and a WARNING is logged."""
        elements = [
            _make_feed_element(title=""),       # empty title → skip
            _make_feed_element(title="Valid"),  # normal item
        ]
        page = _make_page(elements)

        with caplog.at_level(logging.WARNING, logger="huginn.playwright.flows.community.indiehackers"):
            items = await flow.run(page)

        assert len(items) == 1
        assert items[0]["title"] == "Valid"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)

    @pytest.mark.asyncio
    async def test_missing_url_skips_item(self, flow, caplog):
        """Item with None href is skipped and a WARNING is logged."""
        elements = [
            _make_feed_element(href=None),          # no href → skip
            _make_feed_element(title="Keep This"),  # normal item
        ]
        page = _make_page(elements)

        with caplog.at_level(logging.WARNING, logger="huginn.playwright.flows.community.indiehackers"):
            items = await flow.run(page)

        assert len(items) == 1
        assert items[0]["title"] == "Keep This"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)

    @pytest.mark.asyncio
    async def test_no_content_title_link_skips_item(self, flow, caplog):
        """Item where a.content-title is absent is skipped with WARNING."""
        element = AsyncMock()
        element.query_selector = AsyncMock(return_value=None)  # link_el is None
        page = _make_page([element, _make_feed_element(title="OK")])

        with caplog.at_level(logging.WARNING, logger="huginn.playwright.flows.community.indiehackers"):
            items = await flow.run(page)

        assert len(items) == 1
        assert items[0]["title"] == "OK"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)


class TestEmptyList:
    @pytest.mark.asyncio
    async def test_empty_feed_returns_empty_list(self, flow):
        """page.query_selector_all() returns [] → run() returns []."""
        page = _make_page([])

        items = await flow.run(page)

        assert items == []

    @pytest.mark.asyncio
    async def test_empty_feed_logs_warning(self, flow, caplog):
        """Empty feed logs a WARNING."""
        page = _make_page([])

        with caplog.at_level(logging.WARNING, logger="huginn.playwright.flows.community.indiehackers"):
            await flow.run(page)

        assert any(r.levelno >= logging.WARNING for r in caplog.records)


class TestTimeout:
    @pytest.mark.asyncio
    async def test_timeout_propagates(self, flow):
        """wait_for_selector TimeoutError propagates out of run()."""
        page = AsyncMock()
        page.goto = AsyncMock(return_value=None)
        page.wait_for_selector = AsyncMock(
            side_effect=PlaywrightTimeoutError("Timeout exceeded")
        )

        with pytest.raises(PlaywrightTimeoutError):
            await flow.run(page)

    @pytest.mark.asyncio
    async def test_timeout_not_caught_internally(self, flow):
        """run() does not swallow TimeoutError — query_selector_all is never reached."""
        page = AsyncMock()
        page.goto = AsyncMock(return_value=None)
        page.wait_for_selector = AsyncMock(
            side_effect=PlaywrightTimeoutError("Timeout exceeded")
        )

        try:
            await flow.run(page)
        except PlaywrightTimeoutError:
            pass

        page.query_selector_all.assert_not_called()
