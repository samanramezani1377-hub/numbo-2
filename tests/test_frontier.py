from scrapy.http import HtmlResponse, Request

from numbo.frontier import CrawlHistory
from numbo.spiders.contact import ContactSpider


def test_crawl_history_persists_and_deduplicates(tmp_path):
    db = tmp_path / "numbo.db"
    first = CrawlHistory(db)
    assert first.reserve("https://one.ir/page", "one.ir")
    assert not first.reserve("https://one.ir/page", "one.ir")
    first.mark_crawled("https://one.ir/page")
    first.close()

    second = CrawlHistory(db)
    assert second.was_crawled("https://one.ir/page")
    assert not second.reserve("https://one.ir/page", "one.ir")
    second.close()


def test_failed_url_can_be_retried(tmp_path):
    db = tmp_path / "numbo.db"
    history = CrawlHistory(db)
    assert history.reserve("https://one.ir/page", "one.ir")
    history.mark_failed("https://one.ir/page")
    assert history.reserve("https://one.ir/page", "one.ir")
    history.close()


def test_external_allowed_tld_links_are_discovered(tmp_path):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("https://seed.ir\n", encoding="utf-8")
    db = tmp_path / "numbo.db"
    spider = ContactSpider(seeds_file=str(seeds), frontier_db=str(db))

    response = HtmlResponse(
        url="https://seed.ir/",
        request=Request("https://seed.ir/"),
        body=b"""
            <a href="https://external.ir/contact">contact</a>
            <a href="https://external.com/contact">blocked</a>
            <a href="https://seed.ir/about">internal</a>
        """,
        encoding="utf-8",
    )

    links = list(spider._links(response))
    assert "https://external.ir/contact" in links
    assert "https://external.com/contact" in links

    rows, total = spider.frontier.list_discovered_links()
    assert total == 2
    targets = {row[1] for row in rows}
    assert "https://external.com/contact" in targets
    assert "https://external.ir/contact" in targets
    crawlable = {row[1]: row[3] for row in rows}
    assert crawlable["https://external.com/contact"] == 0
    assert crawlable["https://external.ir/contact"] == 1
    assert "https://seed.ir/about" in links
    spider.frontier.close()


def test_already_crawled_link_is_not_scheduled(tmp_path):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("https://seed.ir\n", encoding="utf-8")
    db = tmp_path / "numbo.db"

    history = CrawlHistory(db)
    history.reserve("https://external.ir/contact", "external.ir")
    history.mark_crawled("https://external.ir/contact")
    history.close()

    spider = ContactSpider(seeds_file=str(seeds), frontier_db=str(db))
    assert spider._request_page("https://external.ir/contact") is None
    spider.frontier.close()
