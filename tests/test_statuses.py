from numbo.frontier import CrawlHistory


def test_failed_history_is_preserved_across_cycles(tmp_path):
    db = tmp_path / "numbo.db"
    history = CrawlHistory(db)
    history.record_discovered_link(
        "https://seed.ir", "https://seed.ir/broken", "seed.ir", False, True
    )
    history.reserve("https://seed.ir/broken", "seed.ir")
    history.mark_failed("https://seed.ir/broken", "robots.txt")

    assert history.get_url_status("https://seed.ir/broken") == "failed"
    assert history.next_crawl_batch("seed.ir", limit=20) == []

    history.reset_failed_for_new_cycle()
    assert history.get_url_status("https://seed.ir/broken") == "retry_pending"
    assert history.next_crawl_batch("seed.ir", limit=20) == ["https://seed.ir/broken"]
    history.close()


def test_discovery_export_contains_status_and_preserves_non_crawlable(tmp_path):
    db = tmp_path / "numbo.db"
    out = tmp_path / "discovered.csv"
    history = CrawlHistory(db)
    history.record_discovered_link(
        "https://seed.ir", "https://blocked.com/contact", "blocked.com", True, False, "anchor"
    )
    history.record_discovered_link(
        "https://seed.ir", "https://allowed.ir/contact", "allowed.ir", True, True, "anchor"
    )
    history.reserve("https://allowed.ir/contact", "allowed.ir")
    history.mark_failed("https://allowed.ir/contact", "TimeoutError")

    assert history.export_discovered_links(out) == 2
    text = out.read_text(encoding="utf-8-sig")
    assert "crawl_status" in text
    assert "NON_CRAWLABLE" in text
    assert "FAILED" in text
    assert "https://blocked.com/contact" in text
    history.close()


def test_crawl_stats_use_durable_frontier(tmp_path):
    db = tmp_path / "numbo.db"
    history = CrawlHistory(db)
    history.reserve("https://seed.ir/", "seed.ir")
    history.mark_crawled("https://seed.ir/")
    history.record_discovered_link(
        "https://seed.ir/", "https://allowed.ir/a", "allowed.ir", True, True, "anchor"
    )
    history.record_discovered_link(
        "https://seed.ir/", "https://blocked.com/a", "blocked.com", True, False, "script"
    )
    stats = history.crawl_stats()
    assert stats["pages_crawled"] == 1
    assert stats["sites_crawled"] == 1
    assert stats["urls_discovered"] == 2
    assert stats["external_domains"] == 2
    assert stats["crawlable_urls"] == 1
    history.close()
