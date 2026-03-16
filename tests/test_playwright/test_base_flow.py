"""Tests for BaseFlow abstract base class."""

import pytest
from playwright.async_api import Page

from huginn.playwright.base_flow import BaseFlow


class TestBaseFlowAbstractConstraints:
    """测试 BaseFlow 抽象约束."""

    def test_cannot_instantiate_base_flow(self):
        """测试 BaseFlow 直接实例化抛出 TypeError."""
        with pytest.raises(TypeError) as exc_info:
            BaseFlow()  # type: ignore

        # Python 的 ABC 会提示无法实例化抽象类
        assert "abstract" in str(exc_info.value).lower()

    def test_must_implement_run(self):
        """测试未实现 run() 的子类实例化抛出 TypeError."""

        class IncompleteFlow(BaseFlow):
            """未实现 run() 的子类."""
            name = "test_flow"
            source_category = "test"

        with pytest.raises(TypeError) as exc_info:
            IncompleteFlow()

        assert "abstract" in str(exc_info.value).lower()


class TestBaseFlowConcreteImplementation:
    """测试 BaseFlow 具体实现."""

    def test_concrete_flow_works(self):
        """测试实现所有必需属性和方法的子类可正常实例化."""

        class ConcreteFlow(BaseFlow):
            """完整的 Flow 实现."""
            name = "test_flow"
            source_category = "test"

            async def run(self, page: Page) -> list[dict]:
                return []

        # 应该可以正常实例化
        flow = ConcreteFlow()
        assert flow.name == "test_flow"
        assert flow.source_category == "test"

    def test_concrete_flow_inheritance(self):
        """测试子类可以继承并覆盖属性."""

        class CustomFlow(BaseFlow):
            """自定义 Flow."""
            name = "custom_flow"
            source_category = "custom"

            async def run(self, page: Page) -> list[dict]:
                return [{"data": "test"}]

        flow = CustomFlow()
        assert isinstance(flow, BaseFlow)
        assert flow.name == "custom_flow"
        assert flow.source_category == "custom"


class TestBaseFlowDefaultMethods:
    """测试 BaseFlow 默认方法实现."""

    @pytest.mark.asyncio
    async def test_before_after_run_default(self):
        """测试 before_run() 和 after_run() 默认为空 async 方法，可 await."""

        class TestableFlow(BaseFlow):
            """可测试的 Flow."""
            name = "test_flow"
            source_category = "test"

            async def run(self, page: Page) -> list[dict]:
                return []

        flow = TestableFlow()

        # 默认实现应该可以 await 而不报错
        await flow.before_run()
        await flow.after_run([])

    @pytest.mark.asyncio
    async def test_run_returns_list(self):
        """测试 run() 返回 list[dict]."""

        class TestableFlow(BaseFlow):
            """返回数据的 Flow."""
            name = "test_flow"
            source_category = "test"

            async def run(self, page: Page) -> list[dict]:
                return [{"title": "test"}, {"url": "example.com"}]

        flow = TestableFlow()
        # 注意：这里不能直接调用 run，因为需要 Page 对象
        # 但我们可以检查方法的签名
        import inspect

        sig = inspect.signature(flow.run)
        assert sig.return_annotation == list[dict]


class TestBaseFlowLifecycleHooks:
    """测试 BaseFlow 生命周期钩子."""

    @pytest.mark.asyncio
    async def test_before_run_can_be_overridden(self):
        """测试子类可以覆盖 before_run()."""

        class CustomFlow(BaseFlow):
            """自定义 before_run 的 Flow."""
            name = "test_flow"
            source_category = "test"

            def __init__(self):
                super().__init__()
                self.before_run_called = False

            async def before_run(self) -> None:
                self.before_run_called = True

            async def run(self, page: Page) -> list[dict]:
                return []

        flow = CustomFlow()
        await flow.before_run()
        assert flow.before_run_called is True

    @pytest.mark.asyncio
    async def test_after_run_can_be_overridden(self):
        """测试子类可以覆盖 after_run()."""

        class CustomFlow(BaseFlow):
            """自定义 after_run 的 Flow."""
            name = "test_flow"
            source_category = "test"

            def __init__(self):
                super().__init__()
                self.items_passed_to_after_run = []

            async def run(self, page: Page) -> list[dict]:
                return [{"id": 1}, {"id": 2}]

            async def after_run(self, items: list[dict]) -> None:
                self.items_passed_to_after_run = items

        flow = CustomFlow()
        test_items = [{"id": 1}, {"id": 2}]
        await flow.after_run(test_items)
        assert flow.items_passed_to_after_run == test_items


class TestBaseFlowClassAttributes:
    """测试 BaseFlow 类属性."""

    def test_name_is_class_attribute(self):
        """测试 name 是类属性."""

        class FlowWithName(BaseFlow):
            name = "named_flow"
            source_category = "test"

            async def run(self, page: Page) -> list[dict]:
                return []

        flow = FlowWithName()
        assert FlowWithName.name == "named_flow"
        assert flow.name == "named_flow"

    def test_source_category_is_class_attribute(self):
        """测试 source_category 是类属性."""

        class FlowWithCategory(BaseFlow):
            name = "test_flow"
            source_category = "finance"

            async def run(self, page: Page) -> list[dict]:
                return []

        flow = FlowWithCategory()
        assert FlowWithCategory.source_category == "finance"
        assert flow.source_category == "finance"
