"""Scrapy settings for huginn project.

For more information see the Scrapy documentation:
https://docs.scrapy.org/en/latest/topics/settings.html
"""

from pathlib import Path  # noqa: I001


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Scrapy core settings
BOT_NAME = "huginn"

SPIDER_MODULES = ["huginn.scrapy.spiders"]
NEWSPIDER_MODULE = "huginn.scrapy.spiders"


# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = f"{BOT_NAME}/ (+http://www.yourdomain.com)"


# Obey robots.txt rules
ROBOTSTXT_OBEY = True


# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 8

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
DOWNLOAD_DELAY = 0.5
# The download delay setting will honor only one of:
CONCURRENT_REQUESTS_PER_DOMAIN = 4
CONCURRENT_REQUESTS_PER_IP = 0


# Disable cookies (enabled by default)
COOKIES_ENABLED = False


# Disable Telnet Console (enabled by default)
TELNETCONSOLE_ENABLED = False


# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en",
}


# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#
# Custom middlewares for user-agent randomization and proxy rotation.
# Uncomment to enable:
# - RandomUserAgentMiddleware: rotates User-Agent headers (requires RANDOM_UA_ENABLED=True)
# - ProxyMiddleware: rotates proxy servers (requires PROXY_ENABLED=True)
#
# DOWNLOADER_MIDDLEWARES = {
#     # Disable Scrapy's built-in UserAgentMiddleware to use our custom one
#     "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
#     # Custom middlewares (higher priority = executed earlier)
#     "huginn.scrapy.middlewares.proxy.ProxyMiddleware": 350,
#     "huginn.scrapy.middlewares.useragent.RandomUserAgentMiddleware": 400,
# }
DOWNLOADER_MIDDLEWARES = {}


# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
EXTENSIONS = {
    "scrapy.extensions.telnet.TelnetConsole": None,
}


# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
# Note: Using string references to avoid circular imports
ITEM_PIPELINES = {
    "huginn.scrapy.pipelines.CleanScrapyPipeline": 100,
    "huginn.scrapy.pipelines.DedupScrapyPipeline": 200,
    "huginn.scrapy.pipelines.StorageScrapyPipeline": 300,
}


# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
AUTOTHROTTLE_ENABLED = False


# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
HTTPCACHE_ENABLED = False


# Retry settings
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]
RETRY_PRIORITY_ADJUST = 0


# Download timeout
DOWNLOAD_TIMEOUT = 30


# Randomize download delay to avoid being detected
RANDOMIZE_DOWNLOAD_DELAY = True


# Log settings
LOG_LEVEL = "INFO"

# Feed exports (disabled by default)
FEEDS = {}


# Request depth limits
DEPTH_LIMIT = 0
DEPTH_STATS = True
DEPTH_PRIORITY = 0


# URL length limit
URLLENGTH_LIMIT = 2083


# Referer settings
REFERER_ENABLED = True
REFERRER_POLICY = "scrapy.spidermiddlewares.referer.DefaultReferrerPolicy"


# Redirect settings
REDIRECT_ENABLED = True
REDIRECT_MAX_TIMES = 20


# Cookies settings
COOKIES_DEBUG = False


# Stats collection
STATS_CLASS = "scrapy.statscollectors.StatsCollector"


# Telnet Console
TELNETCONSOLE_HOST = "127.0.0.1"
TELNETCONSOLE_PORT = [6023, 6073]


# Scheduling settings
SCHEDULER_PRIORITY_QUEUE = "scrapy.pqueues.ScrapyPriorityQueue"
SCHEDULER_DISK_QUEUE = "scrapy.squeues.PickleLifoDiskQueue"
SCHEDULER_MEMORY_QUEUE = "scrapy.squeues.LifoMemoryQueue"


# DNS settings
DNS_RESOLVER = "scrapy.resolver.CachingThreadedResolver"
DNS_TIMEOUT = 60


# Logging
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# Reddit spider configuration
REDDIT_SUBREDDITS = ["SideProject", "entrepreneur", "startups"]
REDDIT_LIMIT = 25


# Redis URL (read from huginn config, which loads .env)
from huginn.core.config import settings as _huginn_settings  # noqa: E402
REDIS_URL = _huginn_settings.redis_url


# scrapy-playwright configuration
# See https://github.com/scrapy-plugins/scrapy-playwright
DOWNLOAD_HANDLERS = {
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "http": "scrapy.core.downloader.handlers.http11.HTTP11DownloadHandler",
}

# Use asyncio reactor for scrapy-playwright compatibility
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Playwright browser type (chromium, firefox, webkit)
PLAYWRIGHT_BROWSER_TYPE = "chromium"

# Playwright browser launch options
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
}

# Default navigation timeout in milliseconds
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000
