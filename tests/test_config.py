"""单元测试：配置管理 (pydantic-settings)"""

import os
from unittest.mock import patch

import pytest

from huginn.core.config import Settings, settings


class TestSettingsDefaultValues:
    """测试 Settings 类的默认值"""

    def test_alert_webhook_url_default_is_empty_string(self):
        """alert_webhook_url 默认值为空字符串"""
        s = Settings()
        assert s.alert_webhook_url == ""

    def test_scheduler_max_workers_default_is_4(self):
        """scheduler_max_workers 默认值为 4"""
        s = Settings()
        assert s.scheduler_max_workers == 4

    def test_spider_timeout_default_is_600(self):
        """spider_timeout 默认值为 600"""
        s = Settings()
        assert s.spider_timeout == 600


class TestSettingsEnvironmentVariables:
    """测试从环境变量读取配置"""

    def test_alert_webhook_url_from_env(self):
        """从环境变量 ALERT_WEBHOOK_URL 读取配置"""
        with patch.dict(os.environ, {"ALERT_WEBHOOK_URL": "https://example.com/webhook"}):
            s = Settings(_env_file="")  # 禁用 .env 文件
            assert s.alert_webhook_url == "https://example.com/webhook"

    def test_scheduler_max_workers_from_env(self):
        """从环境变量 SCHEDULER_MAX_WORKERS 读取配置"""
        with patch.dict(os.environ, {"SCHEDULER_MAX_WORKERS": "8"}):
            s = Settings(_env_file="")
            assert s.scheduler_max_workers == 8

    def test_spider_timeout_from_env(self):
        """从环境变量 SPIDER_TIMEOUT 读取配置"""
        with patch.dict(os.environ, {"SPIDER_TIMEOUT": "1200"}):
            s = Settings(_env_file="")
            assert s.spider_timeout == 1200

    def test_scheduler_max_workers_invalid_value_raises_validation_error(self):
        """无效的 SCHEDULER_MAX_WORKERS 值抛出 ValidationError"""
        with patch.dict(os.environ, {"SCHEDULER_MAX_WORKERS": "invalid"}):
            with pytest.raises(Exception):  # pydantic.ValidationError
                Settings(_env_file="")

    def test_spider_timeout_invalid_value_raises_validation_error(self):
        """无效的 SPIDER_TIMEOUT 值抛出 ValidationError"""
        with patch.dict(os.environ, {"SPIDER_TIMEOUT": "not-a-number"}):
            with pytest.raises(Exception):  # pydantic.ValidationError
                Settings(_env_file="")


class TestSettingsSingleton:
    """测试全局 settings 单例"""

    def test_settings_singleton_has_spider_timeout(self):
        """全局 settings 单例包含 spider_timeout 字段且值为 600"""
        assert settings.spider_timeout == 600

    def test_settings_singleton_has_scheduler_max_workers(self):
        """全局 settings 单例包含 scheduler_max_workers 字段且值为 4"""
        assert settings.scheduler_max_workers == 4

    def test_settings_singleton_has_alert_webhook_url(self):
        """全局 settings 单例包含 alert_webhook_url 字段且为空字符串"""
        assert settings.alert_webhook_url == ""
