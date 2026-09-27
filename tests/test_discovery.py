import sqlite3

from scrapy.http import HtmlResponse, Request

from numbo.frontier import CrawlHistory
from numbo.spiders.contact import ContactSpider


def make_spider(tmp_path):
    seeds = tmp_path / "seeds.txt"
    seeds.write_text("https://example.com\n", encoding="utf-8")
    return ContactSpider(seeds_file=str(seeds), frontier_db=str(tmp_path / "numbo.db"))


def test_discovery_stores_link_types_and_merges_duplicate_edges(tmp_path):
    history = CrawlHistory(str(tmp_path / "numbo.db"))
    history.record_discovered_links([
        ("https://example.com/", "https://cdn.example.net/app.js", "cdn.example.net", True, False, "script"),
        ("https://example.com/", "https://cdn.example.net/app.js", "cdn.example.net", True, True, "anchor"),
    ])
    row = history.conn.execute(
        "SELECT external, crawlable, link_type FROM discovered_links"
    ).fetchone()
    history.close()

    assert row == (1, 1, "script,anchor")


def test_discovery_finds_resources_jsonld_meta_and_plain_urls(tmp_path):
    spider = make_spider(tmp_path)
    request = Request("https://example.com/")
    html = b"""
    <html><head>
      <link rel="canonical" href="https://canonical.example.net/page">
      <meta http-equiv="refresh" content="0; url=https://redirect.example.net/next">
      <script type="application/ld+json">
        {"@context":"https://schema.org","sameAs":["https://social.example.net/acme"],
         "url":"https://structured.example.net/"}
      </script>
      <script src="https://assets.example.net/app.js"></script>
    </head><body>
      <a href="https://external.example.net/contact">Contact</a>
      <iframe src="https://embed.example.net/widget"></iframe>
      <p>See https://text.example.net/about for details.</p>
    </body></html>
    """
    response = HtmlResponse(url=request.url, request=request, body=html, encoding="utf-8")

    discovered = list(spider._links(response))
    rows = spider.frontier.conn.execute(
        "SELECT target_url, link_type, crawlable FROM discovered_links ORDER BY target_url"
    ).fetchall()
    spider.frontier.close()

    by_url = {row[0]: row for row in rows}
    assert "https://external.example.net/contact" in by_url
    assert "https://social.example.net/acme" in by_url
    assert "https://assets.example.net/app.js" in by_url
    assert by_url["https://assets.example.net/app.js"][2] == 0
    assert "https://embed.example.net/widget" in by_url
    assert by_url["https://embed.example.net/widget"][1] == "iframe"
    assert "https://text.example.net/about" in by_url
    assert "https://redirect.example.net/next" in by_url
    assert "https://canonical.example.net/page" in by_url
    assert "https://external.example.net/contact" in discovered
    assert "https://canonical.example.net/page" in discovered
    assert "https://assets.example.net/app.js" not in discovered
    assert "https://embed.example.net/widget" not in discovered


def test_robots_sitemap_is_discovered_without_bypassing_tld_rules(tmp_path):
    spider = make_spider(tmp_path)
    request = Request("https://example.com/robots.txt")
    response = HtmlResponse(
        url=request.url,
        request=request,
        body=b"User-agent: *\nDisallow:\nSitemap: https://example.com/sitemap.xml\n",
        encoding="utf-8",
    )
    list(spider.parse_aux(response))
    row = spider.frontier.conn.execute(
        "SELECT target_url, link_type, crawlable FROM discovered_links"
    ).fetchone()
    spider.frontier.close()
    assert row == ("https://example.com/sitemap.xml", "robots_sitemap", 1)
