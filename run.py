#!/usr/bin/env python3
"""
Numbo-2 Continuous Runner
اجرای مداوم کراولر تا زمانی که با Ctrl+C یا SIGTERM متوقف شود.
"""
import os
import sys
import signal
import time
import logging
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("numbo.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("numbo-runner")

running = True

def handle_signal(signum, frame):
    global running
    logger.info("Received signal %s — shutting down gracefully...", signum)
    running = False

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

def main():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists("seeds.txt"):
        logger.error("seeds.txt not found. Create it and add domains.")
        sys.exit(1)

    with open("seeds.txt", "r", encoding="utf-8") as f:
        seeds = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if not seeds:
        logger.error("seeds.txt is empty. Add at least one domain or URL.")
        sys.exit(1)

    logger.info("Numbo-2 starting with %d seeds", len(seeds))
    logger.info("Press Ctrl+C to stop")

    settings = get_project_settings()
    process = CrawlerProcess(settings)

    # Run the spider once. For continuous mode we can loop later if needed.
    # Current design: one full crawl of the seeds + limited depth.
    # To keep process alive longer, user can re-run or extend seeds.
    process.crawl("contact", seeds_file="seeds.txt")
    process.start()  # blocks until finished

    logger.info("Crawl finished. Results saved in data/numbo.db")
    logger.info("Run `python export.py` to export CSV/Excel")

if __name__ == "__main__":
    main()
