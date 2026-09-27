from numbo.frontier import CrawlHistory


def test_layered_frontier_only_returns_lowest_depth(tmp_path):
    history = CrawlHistory(str(tmp_path / "numbo.db"))
    seed = "https://seed.example/"
    history.queue_layered_url(seed, seed, 0)

    for url in ("https://a.example/", "https://b.example/", "https://c.example/"):
        history.queue_layered_url(seed, url, 1, source_url=seed)

    history.queue_layered_url(seed, "https://deep.example/", 2, source_url="https://a.example/")

    first = history.next_layered_batch(seed, limit=20)
    assert first == [(seed, 0)]
    history.mark_layered_queued(seed, seed)
    history.mark_layered_crawled(seed)

    second = history.next_layered_batch(seed, limit=20)
    assert second == [("https://a.example/", 1), ("https://b.example/", 1), ("https://c.example/", 1)]

    history.close()


def test_layered_frontier_preserves_deeper_links_until_shallower_layer_finishes(tmp_path):
    history = CrawlHistory(str(tmp_path / "numbo.db"))
    seed = "https://seed.example/"
    history.queue_layered_url(seed, seed, 0)
    history.queue_layered_url(seed, "https://direct.example/", 1, source_url=seed)
    history.queue_layered_url(seed, "https://deep.example/", 2, source_url="https://direct.example/")

    root = history.next_layered_batch(seed)
    assert root == [(seed, 0)]
    history.mark_layered_queued(seed, seed)
    history.mark_layered_crawled(seed)

    direct = history.next_layered_batch(seed)
    assert direct == [("https://direct.example/", 1)]

    # The depth-2 URL is persisted but is not schedulable while depth 1 is queued.
    history.mark_layered_queued(seed, "https://direct.example/")
    assert history.next_layered_batch(seed) == []

    history.mark_layered_crawled("https://direct.example/")
    assert history.next_layered_batch(seed) == [("https://deep.example/", 2)]

    history.close()
