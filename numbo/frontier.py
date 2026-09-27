import os
import sqlite3
import threading
import time
from datetime import datetime


class CrawlHistory:
    """Persistent URL history shared across crawler cycles."""

    def __init__(self, db_path="data/numbo.db"):
        self.db_path = os.fspath(db_path)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        self.write_lock = threading.RLock()
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
        # Optional per-seed BFS frontier. The normal crawler never consults
        # this table, so legacy/default crawl behavior remains unchanged.
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS layered_frontier (
                seed_url TEXT NOT NULL,
                url TEXT NOT NULL,
                depth INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                source_url TEXT,
                first_seen TEXT NOT NULL,
                crawled_at TEXT,
                PRIMARY KEY (seed_url, url)
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_layered_frontier_seed_depth ON layered_frontier(seed_url, depth, status)")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS discovered_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT NOT NULL,
                target_url TEXT NOT NULL,
                target_domain TEXT NOT NULL,
                external INTEGER NOT NULL DEFAULT 0,
                crawlable INTEGER NOT NULL DEFAULT 0,
                link_type TEXT NOT NULL DEFAULT 'anchor',
                first_seen TEXT NOT NULL,
                UNIQUE(source_url, target_url)
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_discovered_links_target_domain ON discovered_links(target_domain)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_discovered_links_external ON discovered_links(external)")
        # Backward-compatible migration for databases created before typed
        # discovery edges were introduced.
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(discovered_links)").fetchall()}
        if "link_type" not in columns:
            self.conn.execute("ALTER TABLE discovered_links ADD COLUMN link_type TEXT NOT NULL DEFAULT 'anchor'")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_discovered_links_type ON discovered_links(link_type)")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS site_technology_evidence (
                domain TEXT NOT NULL,
                technology TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0,
                evidence_count INTEGER NOT NULL DEFAULT 0,
                source_url TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                PRIMARY KEY (domain, technology)
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_site_technology_domain ON site_technology_evidence(domain)")
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

    def _write(self, operation):
        """Serialize crawler writes and retry transient SQLite locks."""
        with self.write_lock:
            for attempt in range(6):
                try:
                    result = operation()
                    self.conn.commit()
                    return result
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() or attempt == 5:
                        raise
                    self.conn.rollback()
                    time.sleep(0.10 * (2 ** attempt))

    def reserve(self, url, domain, source_url=None):
        """Reserve a URL; already crawled/queued URLs are never scheduled twice."""
        now = datetime.utcnow().isoformat()
        try:
            self._write(lambda: self.conn.execute(
                "INSERT INTO crawl_urls (url, domain, status, source_url, first_seen) "
                "VALUES (?, ?, 'queued', ?, ?)",
                (url, domain, source_url, now),
            ))
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
        self._write(lambda: self.conn.execute(
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
        ))
        return True

    def mark_crawled(self, url):
        self._write(lambda: self.conn.execute(
            "UPDATE crawl_urls SET status = 'crawled', crawled_at = ? WHERE url = ?",
            (datetime.utcnow().isoformat(), url),
        ))

    def mark_failed(self, url):
        self._write(lambda: self.conn.execute(
            "UPDATE crawl_urls SET status = 'failed' WHERE url = ?",
            (url,),
        ))

    def queue_layered_url(self, seed_url, url, depth, source_url=None):
        """Persist a URL in the optional per-seed BFS frontier."""
        seed_url = str(seed_url)
        url = str(url)
        depth = max(int(depth), 0)
        now = datetime.utcnow().isoformat()

        def write():
            global_crawled = self.conn.execute(
                "SELECT 1 FROM crawl_urls WHERE url=? AND status='crawled' LIMIT 1",
                (url,),
            ).fetchone()
            status = "crawled" if global_crawled else "pending"
            self.conn.execute(
                """INSERT INTO layered_frontier
                   (seed_url,url,depth,status,source_url,first_seen,crawled_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(seed_url,url) DO UPDATE SET
                     depth=MIN(layered_frontier.depth, excluded.depth),
                     source_url=COALESCE(layered_frontier.source_url, excluded.source_url)""",
                (seed_url, url, depth, status, source_url, now,
                 now if status == "crawled" else None),
            )
        self._write(write)

    def mark_layered_crawled(self, url):
        self._write(lambda: self.conn.execute(
            "UPDATE layered_frontier SET status='crawled', crawled_at=? "
            "WHERE url=? AND status IN ('pending','queued')",
            (datetime.utcnow().isoformat(), url),
        ))

    def mark_layered_failed(self, url):
        self._write(lambda: self.conn.execute(
            "UPDATE layered_frontier SET status='failed' WHERE url=? AND status='queued'",
            (url,),
        ))

    def mark_layered_queued(self, seed_url, url):
        self._write(lambda: self.conn.execute(
            "UPDATE layered_frontier SET status='queued' "
            "WHERE seed_url=? AND url=? AND status='pending'",
            (seed_url, url),
        ))

    def next_layered_batch(self, seed_url, limit=20):
        """Return only the lowest unfinished depth for one seed."""
        row = self.conn.execute(
            """SELECT MIN(depth) FROM layered_frontier
               WHERE seed_url=? AND status IN ('pending','queued')""",
            (seed_url,),
        ).fetchone()
        if not row or row[0] is None:
            return []
        depth = int(row[0])
        rows = self.conn.execute(
            """SELECT url, depth FROM layered_frontier
               WHERE seed_url=? AND depth=? AND status='pending'
               ORDER BY first_seen ASC LIMIT ?""",
            (seed_url, depth, max(int(limit), 1)),
        ).fetchall()
        return [(row[0], int(row[1])) for row in rows]

    def record_discovered_links(self, links):
        """Persist typed discovery edges in one transaction."""
        values = []
        now = datetime.utcnow().isoformat()
        for link in links:
            if len(link) == 5:
                source_url, target_url, target_domain, external, crawlable = link
                link_type = "anchor"
            else:
                source_url, target_url, target_domain, external, crawlable, link_type = link
            values.append((
                source_url, target_url, target_domain,
                int(external), int(crawlable), str(link_type or "anchor"), now,
            ))
        if not values:
            return

        def write():
            self.conn.executemany(
                """INSERT INTO discovered_links
                   (source_url, target_url, target_domain, external, crawlable, link_type, first_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(source_url, target_url) DO UPDATE SET
                     crawlable=MAX(discovered_links.crawlable, excluded.crawlable),
                     external=MAX(discovered_links.external, excluded.external),
                     link_type=CASE
                       WHEN discovered_links.link_type = excluded.link_type THEN discovered_links.link_type
                       WHEN instr(',' || discovered_links.link_type || ',', ',' || excluded.link_type || ',') > 0
                         THEN discovered_links.link_type
                       ELSE discovered_links.link_type || ',' || excluded.link_type
                     END""",
                values,
            )

        self._write(write)

    def record_technology_evidence(self, domain, source_url, technologies):
        """Persist technology evidence independently of lead qualification."""
        if not technologies or not domain:
            return
        now = datetime.utcnow().isoformat()
        values = []
        for tech in technologies:
            name = str(tech.get("name") or "").strip()
            if not name:
                continue
            confidence = float(tech.get("confidence") or 0)
            evidence_count = int(tech.get("evidence_count") or 0)
            values.append((domain, name, confidence, evidence_count, source_url, now, now))
        if not values:
            return
        def write():
            self.conn.executemany(
                """INSERT INTO site_technology_evidence
                   (domain,technology,confidence,evidence_count,source_url,first_seen,last_seen)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(domain,technology) DO UPDATE SET
                     confidence=MAX(site_technology_evidence.confidence, excluded.confidence),
                     evidence_count=site_technology_evidence.evidence_count + excluded.evidence_count,
                     last_seen=excluded.last_seen""",
                values,
            )
        self._write(write)

    def get_site_technologies(self, domain):
        return self.conn.execute(
            """SELECT technology, confidence, evidence_count, source_url
               FROM site_technology_evidence WHERE domain=?
               ORDER BY confidence DESC, technology ASC""",
            (domain,),
        ).fetchall()

    def record_discovered_link(self, source_url, target_url, target_domain, external, crawlable, link_type="anchor"):
        self.record_discovered_links([
            (source_url, target_url, target_domain, external, crawlable, link_type)
        ])

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
            f"""SELECT source_url, target_url, target_domain, crawlable, link_type, first_seen
                FROM discovered_links {where} ORDER BY first_seen DESC""",
            params,
        ).fetchall()
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["source_url", "target_url", "target_domain", "crawlable", "link_type", "first_seen"])
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
