#!/usr/bin/env python3
import os
import sys
import signal
import logging
import time

os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "numbo.settings")

# Install Scrapy's configured reactor before importing any Twisted module.
# Importing twisted.internet.reactor first would install EPollReactor on Linux
# and make CrawlerRunner reject the configured AsyncioSelectorReactor.
from scrapy.utils.reactor import install_reactor

install_reactor("twisted.internet.asyncioreactor.AsyncioSelectorReactor")

from scrapy.crawler import CrawlerRunner
from scrapy.utils.project import get_project_settings
from twisted.internet import reactor, defer
from twisted.internet.threads import deferToThread
from twisted.internet.task import deferLater

from numbo.config import load as load_config

def _configure_logging():
    """Configure runner logging once without duplicating handlers."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    # Keep exactly one stdout and one file handler even if the runner module
    # is imported/reloaded by the hosting process.
    if not any(getattr(h, "_numbo_stdout", False) for h in root.handlers):
        stream = logging.StreamHandler(sys.stdout)
        stream._numbo_stdout = True
        stream.setFormatter(formatter)
        root.addHandler(stream)

    if not any(getattr(h, "_numbo_file", False) for h in root.handlers):
        file_handler = logging.FileHandler("numbo.log", encoding="utf-8")
        file_handler._numbo_file = True
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    logging.getLogger("numbo-runner").propagate = True


_configure_logging()
logger = logging.getLogger("numbo-runner")

cfg = load_config()
CYCLE_DELAY = int(cfg.get("cycle_delay") or 300)

running = True
_last_config_mtime = None


def _config_mtime():
    try:
        return os.path.getmtime(os.path.join(os.path.dirname(__file__), "config.json"))
    except OSError:
        return None


def _sleep_until_next_cycle(delay):
    global _last_config_mtime
    started = time.monotonic()
    _last_config_mtime = _config_mtime()
    while running:
        elapsed = time.monotonic() - started
        if elapsed >= delay:
            return False
        time.sleep(min(1.0, delay - elapsed))
        current = _config_mtime()
        if current != _last_config_mtime:
            logger.info("Configuration changed during cycle delay; starting next cycle now.")
            _last_config_mtime = current
            return True
    return False


def handle_signal(signum, frame):
    global running
    logger.info("Received signal %s — shutting down gracefully...", signum)
    running = False
    if reactor.running:
        reactor.stop()


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


@defer.inlineCallbacks
def crawl_cycle(runner):
    while running:
        logger.info("=== Starting new crawl cycle ===")
        cycle_cfg = load_config()
        layered = bool(cycle_cfg.get("layered_crawl", False))
        logger.info("Crawl mode: %s", "layered BFS" if layered else "normal")
        try:
            yield runner.crawl("contact", seeds_file="seeds.txt", layered_crawl=layered)
            logger.info("Cycle finished successfully")
        except Exception as e:
            logger.error("Cycle error: %s", e)

        if not running:
            break

        logger.info("Sleeping %d seconds before next cycle...", CYCLE_DELAY)
        yield deferLater(reactor, 0.1, lambda: None)
        changed = yield deferToThread(_sleep_until_next_cycle, CYCLE_DELAY)
        if changed:
            continue

    logger.info("Runner stopped.")


def main():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists("seeds.txt"):
        logger.error("seeds.txt not found.")
        sys.exit(1)

    with open("seeds.txt", "r", encoding="utf-8") as f:
        seeds = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if not seeds:
        logger.error("seeds.txt is empty.")
        sys.exit(1)

    logger.info("Numbo-2 continuous mode started with %d seeds", len(seeds))
    settings = get_project_settings()
    runner = CrawlerRunner(settings)
    crawl_cycle(runner)
    reactor.run()
    logger.info("Results are in data/numbo.db")


if __name__ == "__main__":
    main()
