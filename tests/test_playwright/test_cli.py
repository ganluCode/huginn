"""Tests for CLI entry point in huginn.playwright.runner."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Page

from huginn.playwright.base_flow import BaseFlow


class TestCliHelp:
    """测试 CLI 帮助信息."""

    def test_cli_help_outputs_usage(self, capsys):
        """测试 python -m huginn.playwright.runner --help 输出用法说明."""
        # 模拟命令行参数
        with patch("sys.argv", ["huginn.playwright.runner", "--help"]):
            # 导入会触发 main()
            with pytest.raises(SystemExit) as exc_info:
                from huginn.playwright.runner import main

                main()

            # argparse --help 会触发 SystemExit(0)
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        output = captured.out + captured.err
        # 验证输出包含关键信息
        assert "usage" in output.lower() or "用法" in output
        assert "flow" in output.lower()


class TestCliUnknownFlow:
    """测试 CLI 未知 Flow 处理."""

    @patch("huginn.playwright.runner._discover_flows")
    def test_cli_unknown_name_exits_with_error(self, mock_discover, capsys):
        """测试 python -m huginn.playwright.runner <未知名称> 输出错误信息并以非零退出码退出."""
        # Mock 返回空的 flow 字典
        mock_discover.return_value = {}

        with patch("sys.argv", ["huginn.playwright.runner", "nonexistent_flow"]):
            with pytest.raises(SystemExit) as exc_info:
                from huginn.playwright.runner import main

                main()

            # 应该以非零退出码退出
            assert exc_info.value.code != 0

        captured = capsys.readouterr()
        output = captured.out + captured.err
        # 验证输出包含错误信息
        assert "not found" in output.lower() or "未找到" in output
        assert "nonexistent_flow" in output


class TestDiscoverFlows:
    """测试 Flow 发现功能."""

    def test_discover_flows_finds_baseflow_subclasses(self, tmp_path):
        """测试 flows/ 目录下的 BaseFlow 子类可被按 flow.name 索引发现."""
        # 创建一个临时的 flow 文件
        flows_dir = tmp_path / "flows"
        flows_dir.mkdir()
        (flows_dir / "__init__.py").write_text("")

        # 创建测试 Flow 类
        test_flow_code = '''
from huginn.playwright.base_flow import BaseFlow
from playwright.async_api import Page

class TestFlow1(BaseFlow):
    """测试 Flow 1."""
    name = "test_flow_1"
    source_category = "test"

    async def run(self, page: Page) -> list[dict]:
        return [{"data": "flow1"}]

class TestFlow2(BaseFlow):
    """测试 Flow 2."""
    name = "test_flow_2"
    source_category = "tech"

    async def run(self, page: Page) -> list[dict]:
        return [{"data": "flow2"}]
'''
        (flows_dir / "test_flows.py").write_text(test_flow_code)

        # 导入 _discover_flows 并测试
        import sys
        sys.path.insert(0, str(tmp_path))

        from huginn.playwright.runner import _discover_flows

        flows = _discover_flows(str(flows_dir))

        # 验证发现了两个 Flow
        assert len(flows) == 2
        assert "test_flow_1" in flows
        assert "test_flow_2" in flows

        # 验证 Flow 类可以被实例化
        flow1_class = flows["test_flow_1"]
        flow1 = flow1_class()
        assert flow1.name == "test_flow_1"
        assert flow1.source_category == "test"

    def test_discover_flows_handles_empty_directory(self, tmp_path):
        """测试 _discover_flows 处理空目录."""
        flows_dir = tmp_path / "flows"
        flows_dir.mkdir()
        (flows_dir / "__init__.py").write_text("")

        from huginn.playwright.runner import _discover_flows

        flows = _discover_flows(str(flows_dir))
        assert len(flows) == 0


class TestCliExecution:
    """测试 CLI 执行功能."""

    @patch("huginn.playwright.runner._discover_flows")
    @patch("huginn.playwright.runner.run_flow")
    @patch("huginn.playwright.runner.PlaywrightEngine")
    def test_cli_executes_flow_and_prints_collected_items(
        self, mock_engine_class, mock_run_flow, mock_discover, capsys
    ):
        """测试 CLI 执行成功后打印 'Collected N items' 格式输出."""
        # 创建测试 Flow 类
        class TestFlow(BaseFlow):
            name = "test_flow"
            source_category = "test"

            async def run(self, page: Page) -> list[dict]:
                return [{"data": "test"}]

        mock_discover.return_value = {"test_flow": TestFlow}
        mock_run_flow.return_value = 5  # 模拟返回 5 个项目

        with patch("sys.argv", ["huginn.playwright.runner", "test_flow"]):
            with pytest.raises(SystemExit) as exc_info:
                from huginn.playwright.runner import main

                main()

            # 应该以退出码 0 退出
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        output = captured.out + captured.err

        # 验证输出包含 "Collected N items" 格式
        assert "Collected 5 items" in output or "collected 5 items" in output.lower()

    @patch("huginn.playwright.runner._discover_flows")
    @patch("huginn.playwright.runner.run_flow")
    @patch("huginn.playwright.runner.PlaywrightEngine")
    def test_cli_lists_available_flows(
        self, mock_engine_class, mock_run_flow, mock_discover, capsys
    ):
        """测试 CLI --list 列出所有可用的 Flow."""
        # 创建测试 Flow 类
        class Flow1(BaseFlow):
            name = "flow1"
            source_category = "tech"

            async def run(self, page: Page) -> list[dict]:
                return []

        class Flow2(BaseFlow):
            name = "flow2"
            source_category = "finance"

            async def run(self, page: Page) -> list[dict]:
                return []

        mock_discover.return_value = {"flow1": Flow1, "flow2": Flow2}

        with patch("sys.argv", ["huginn.playwright.runner", "--list"]):
            with pytest.raises(SystemExit) as exc_info:
                from huginn.playwright.runner import main

                main()

            # --list 应该正常退出
            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        output = captured.out + captured.err

        # 验证输出包含 Flow 名称
        assert "flow1" in output
        assert "flow2" in output


class TestCliErrorHandling:
    """测试 CLI 错误处理."""

    @patch("huginn.playwright.runner._discover_flows")
    @patch("huginn.playwright.runner.run_flow")
    @patch("huginn.playwright.runner.PlaywrightEngine")
    def test_cli_handles_flow_execution_error(
        self, mock_engine_class, mock_run_flow, mock_discover, capsys
    ):
        """测试 CLI 处理 Flow 执行错误."""
        class TestFlow(BaseFlow):
            name = "test_flow"
            source_category = "test"

            async def run(self, page: Page) -> list[dict]:
                return []

        mock_discover.return_value = {"test_flow": TestFlow}
        mock_run_flow.side_effect = Exception("Flow execution failed")

        with patch("sys.argv", ["huginn.playwright.runner", "test_flow"]):
            with pytest.raises(SystemExit) as exc_info:
                from huginn.playwright.runner import main

                main()

            # 应该以非零退出码退出
            assert exc_info.value.code != 0

        captured = capsys.readouterr()
        output = captured.out + captured.err

        # 验证输出包含错误信息
        assert "error" in output.lower() or "错误" in output
