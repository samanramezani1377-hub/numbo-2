BOT_NAME = "numbo"
SPIDER_MODULES = ["numbo.spiders"]
NEWSPIDER_MODULE = "numbo.spiders"

ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 3
NUMBO_PAGE_BUDGET = 20
DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = True
DOWNLOAD_TIMEOUT = 20
RETRY_TIMES = 3
RETRY_HTTP_CODES = [408, 425, 429, 500, 502, 503, 504]
REDIRECT_MAX_TIMES = 5

DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
}
USER_AGENT = "NumboContactBot/2.0 (+https://github.com/samanramezani1377-hub/numbo-2)"
COOKIES_ENABLED = False
TELNETCONSOLE_ENABLED = False

DOWNLOADER_MIDDLEWARES = {
    "numbo.middlewares.RotateUserAgentMiddleware": 400,
}
ITEM_PIPELINES = {
    "numbo.pipelines.ValidationPipeline": 100,
    "numbo.pipelines.DeduplicationPipeline": 200,
    "numbo.pipelines.SQLitePipeline": 300,
}
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
DEPTH_LIMIT = 4
DEPTH_PRIORITY = 1
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.5
CLOSESPIDER_TIMEOUT = 0

ALLOWED_TLDS = [".ir"]
