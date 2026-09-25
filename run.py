#!/usr/bin/env python3
import os
import sys
import signal
import logging
from scrapy.crawler import CrawlerRunner
from scrapy.utils.project import get_project_settings
from twisted.internet import reactor, defer
from twisted.internet.task import deferLater
from numbo.config import load as load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("numbo.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("numbo-runner")

os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "numbo.settings")

cfg = load_config()
CYCLE_DELAY = int(cfg.get("cycle_delay") or 300)

running = True


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
        try:
            yield runner.crawl("contact", seeds_file="seeds.txt")
            logger.info("Cycle finished successfully")
        except Exception as e:
            logger.error("Cycle error: %s", e)

        if not running:
            break

        logger.info("Sleeping %d seconds before next cycle...", CYCLE_DELAY)
        yield deferLater(reactor, CYCLE_DELAY, lambda: None)

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
