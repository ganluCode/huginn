"""配置管理：基于 pydantic-settings 的环境变量配置"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置类，从环境变量读取配置"""

    database_url: str = "postgresql+asyncpg://huginn:huginn@localhost:5432/huginn"
    database_url_sync: str = "postgresql+psycopg2://huginn:huginn@localhost:5432/huginn"
    redis_url: str = "redis://localhost:6379/0"
    debug: bool = False

    # 调度器配置
    alert_webhook_url: str = ""
    scheduler_max_workers: int = 4
    spider_timeout: int = 600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# 全局单例
settings = Settings()
