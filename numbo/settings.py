BOT_NAME = "numbo"

SPIDER_MODULES = ["numbo.spiders"]
NEWSPIDER_MODULE = "numbo.spiders"

ROBOTSTXT_OBEY = True

CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 1.5
RANDOMIZE_DOWNLOAD_DELAY = True

DOWNLOAD_TIMEOUT = 20
RETRY_TIMES = 2
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
}

USER_AGENT = "NumboContactBot/1.0 (+https://github.com/samanramezani1377-hub/numbo-2)"

COOKIES_ENABLED = False
TELNETCONSOLE_ENABLED = False

ITEM_PIPELINES = {
    "numbo.pipelines.ValidationPipeline": 100,
    "numbo.pipelines.DeduplicationPipeline": 200,
    "numbo.pipelines.SQLitePipeline": 300,
}

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"

# Depth limit to avoid endless crawling of a single large site
DEPTH_LIMIT = 3

# AutoThrottle for better politeness
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# Close spider after idle (helps continuous runner)
CLOSESPIDER_TIMEOUT = 0  # disabled, controlled by runner
