import os
import sqlite3
from datetime import datetime


class CrawlHistory:
    """Persistent URL history shared across crawler cycles."""

    def __init__(self, db_path="data/numbo.db"):
        self.db_path = os.fspath(db_path)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS crawl_urls (
                url TEXT PRIMARY KEY,
                domain TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'crawled',
                source_url TEXT,
                first_seen TEXT NOT NULL,
                crawled_at TEXT
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_urls_domain ON crawl_urls(domain)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_crawl_urls_status ON crawl_urls(status)")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS discovered_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT NOT NULL,
                target_url TEXT NOT NULL,
                target_domain TEXT NOT NULL,
                external INTEGER NOT NULL DEFAULT 0,
                crawlable INTEGER NOT NULL DEFAULT 0,
                first_seen TEXT NOT NULL,
                UNIQUE(source_url, target_url)
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_discovered_links_target_domain ON discovered_links(target_domain)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_discovered_links_external ON discovered_links(external)")
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    def was_crawled(self, url):
        row = self.conn.execute(
            "SELECT 1 FROM crawl_urls WHERE url = ? AND status = 'crawled' LIMIT 1",
            (url,),
        ).fetchone()
        return row is not None

    def reserve(self, url, domain, source_url=None):
        """Reserve a URL; already crawled/queued URLs are never scheduled twice."""
        now = datetime.utcnow().isoformat()
        try:
            self.conn.execute(
                "INSERT INTO crawl_urls (url, domain, status, source_url, first_seen) "
                "VALUES (?, ?, 'queued', ?, ?)",
                (url, domain, source_url, now),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            row = self.conn.execute(
                "SELECT status FROM crawl_urls WHERE url = ?",
                (url,),
            ).fetchone()
            return bool(row and row[0] == "failed")

    def reserve_seed(self, url, domain, source_url=None):
        """Reserve an explicit seed for the current crawl cycle.

        Seeds are operator-selected entry points, so persistent history must
        not suppress them on later cycles. This does not change the normal
        deduplication rules for discovered/internal/external links.
        """
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """INSERT INTO crawl_urls
               (url, domain, status, source_url, first_seen, crawled_at)
               VALUES (?, ?, 'queued', ?, ?, NULL)
               ON CONFLICT(url) DO UPDATE SET
                   domain = excluded.domain,
                   status = 'queued',
                   source_url = excluded.source_url,
                   first_seen = excluded.first_seen,
                   crawled_at = NULL""",
            (url, domain, source_url, now),
        )
        self.conn.commit()
        return True

    def mark_crawled(self, url):
        self.conn.execute(
            "UPDATE crawl_urls SET status = 'crawled', crawled_at = ? WHERE url = ?",
            (datetime.utcnow().isoformat(), url),
        )
        self.conn.commit()

    def mark_failed(self, url):
        self.conn.execute(
            "UPDATE crawl_urls SET status = 'failed' WHERE url = ?",
            (url,),
        )
        self.conn.commit()

    def record_discovered_link(self, source_url, target_url, target_domain, external, crawlable):
        # Discovery happens frequently; keep a short retry loop because the
        # crawler and the UI may touch the same SQLite database concurrently.
        values = (
            source_url, target_url, target_domain, int(external), int(crawlable),
            datetime.utcnow().isoformat(),
        )
        for attempt in range(6):
            try:
                self.conn.execute(
                    """INSERT OR IGNORE INTO discovered_links
                       (source_url, target_url, target_domain, external, crawlable, first_seen)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    values,
                )
                self.conn.commit()
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == 5:
                    raise
                import time
                time.sleep(0.25 * (2 ** attempt))

    def list_discovered_links(self, query=None, page=1, per_page=50, crawlable=None):
        page = max(int(page), 1)
        per_page = max(int(per_page), 1)
        params = []
        conditions = ["external = 1"]
        if crawlable is not None:
            conditions.append("crawlable = ?")
            params.append(int(bool(crawlable)))
        if query:
            conditions.append("(source_url LIKE ? OR target_url LIKE ? OR target_domain LIKE ?)")
            value = f"%{query}%"
            params.extend([value, value, value])
        where = "WHERE " + " AND ".join(conditions)
        total = self.conn.execute(f"SELECT COUNT(*) FROM discovered_links {where}", params).fetchone()[0]
        rows = self.conn.execute(
            f"""SELECT source_url, target_url, target_domain, crawlable, first_seen
                FROM discovered_links {where} ORDER BY first_seen DESC LIMIT ? OFFSET ?""",
            params + [per_page, (page - 1) * per_page],
        ).fetchall()
        return rows, total

    def export_discovered_links(self, path, crawlable=None):
        import csv
        conditions = ["external = 1"]
        params = []
        if crawlable is not None:
            conditions.append("crawlable = ?")
            params.append(int(bool(crawlable)))
        where = "WHERE " + " AND ".join(conditions)
        rows = self.conn.execute(
            f"""SELECT source_url, target_url, target_domain, crawlable, first_seen
                FROM discovered_links {where} ORDER BY first_seen DESC""",
            params,
        ).fetchall()
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["source_url", "target_url", "target_domain", "crawlable", "first_seen"])
            writer.writerows(rows)
        return len(rows)


    def next_crawl_batch(self, domain, limit=20):
        """Return the next undiscovered/unqueued batch for a domain.

        Failed URLs are not retried inside the same crawl cycle. They remain
        recorded as failed and can be retried by a later crawl cycle.
        """
        rows = self.conn.execute(
            """SELECT d.target_url
               FROM discovered_links d
               LEFT JOIN crawl_urls c ON c.url = d.target_url
               WHERE d.target_domain = ?
                 AND d.crawlable = 1
                 AND c.url IS NULL
               ORDER BY d.first_seen ASC
               LIMIT ?""",
            (domain, max(int(limit), 1)),
        ).fetchall()
        return [row[0] for row in rows]
