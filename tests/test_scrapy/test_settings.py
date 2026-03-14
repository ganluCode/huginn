"""Test Scrapy settings configuration (F-002)."""

from huginn.scrapy import settings


class TestScrapySettings:
    """Verify Scrapy settings are properly configured."""

    def test_module_importable(self):
        """Settings module should be importable."""
        assert settings is not None

    def test_bot_name(self):
        """BOT_NAME should be 'huginn'."""
        assert settings.BOT_NAME == "huginn"

    def test_spider_modules(self):
        """SPIDER_MODULES should point to huginn.scrapy.spiders."""
        assert settings.SPIDER_MODULES == ["huginn.scrapy.spiders"]

    def test_new_spider_module(self):
        """NEWSPIDER_MODULE should point to huginn.scrapy.spiders."""
        assert settings.NEWSPIDER_MODULE == "huginn.scrapy.spiders"

    def test_concurrent_requests(self):
        """CONCURRENT_REQUESTS should be 8."""
        assert settings.CONCURRENT_REQUESTS == 8

    def test_concurrent_requests_per_domain(self):
        """CONCURRENT_REQUESTS_PER_DOMAIN should be 4."""
        assert settings.CONCURRENT_REQUESTS_PER_DOMAIN == 4

    def test_download_delay(self):
        """DOWNLOAD_DELAY should be 0.5."""
        assert settings.DOWNLOAD_DELAY == 0.5

    def test_randomize_download_delay(self):
        """RANDOMIZE_DOWNLOAD_DELAY should be True."""
        assert settings.RANDOMIZE_DOWNLOAD_DELAY is True

    def test_download_timeout(self):
        """DOWNLOAD_TIMEOUT should be 30."""
        assert settings.DOWNLOAD_TIMEOUT == 30

    def test_robotstxt_obey(self):
        """ROBOTSTXT_OBEY should be True."""
        assert settings.ROBOTSTXT_OBEY is True

    def test_retry_times(self):
        """RETRY_TIMES should be 3."""
        assert settings.RETRY_TIMES == 3

    def test_retry_http_codes(self):
        """RETRY_HTTP_CODES should include standard error codes."""
        required_codes = {500, 502, 503, 504, 408, 429}
        assert required_codes.issubset(settings.RETRY_HTTP_CODES)

    def test_item_pipelines(self):
        """ITEM_PIPELINES should have three entries with priorities 100, 200, 300."""
        pipelines = settings.ITEM_PIPELINES
        assert len(pipelines) == 3

        # Check priorities are exactly 100, 200, 300
        priorities = set(pipelines.values())
        assert priorities == {100, 200, 300}

        # Check pipeline class names (using string references since classes don't exist yet)
        pipeline_names = list(pipelines.keys())
        assert any("CleanScrapyPipeline" in str(name) for name in pipeline_names)
        assert any("DedupScrapyPipeline" in str(name) for name in pipeline_names)
        assert any("StorageScrapyPipeline" in str(name) for name in pipeline_names)

    def test_default_request_headers(self):
        """DEFAULT_REQUEST_HEADERS should include Accept and Accept-Language."""
        headers = settings.DEFAULT_REQUEST_HEADERS
        assert "Accept" in headers
        assert "Accept-Language" in headers
