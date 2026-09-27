import json
import os
import sqlite3
from datetime import datetime
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
from numbo.utils.tech import format_technologies
from numbo.qualification import qualify_record

class ValidationPipeline:
    def process_item(self, item):
        a = ItemAdapter(item)
        phones = a.get("phones") or []
        emails = a.get("emails") or []
        qualified = qualify_record({
            "domain": a.get("domain"), "phones": phones, "emails": emails,
            "address": a.get("address"), "business_name": a.get("business_name"),
            "category": a.get("category"),
        })
        if not qualified:
            raise DropItem("Not a qualified commercial lead")
        a["phones"] = qualified["phones"]
        a["emails"] = qualified["emails"]
        a["business_name"] = qualified["business_name"]
        a["address"] = qualified["address"]
        return item

class DeduplicationPipeline:
    def __init__(self):
        self.seen_phones, self.seen_emails, self.seen_domains = set(), set(), set()

    def process_item(self, item):
        a = ItemAdapter(item)
        phones = list(dict.fromkeys(a.get("phones") or []))
        emails = list(dict.fromkeys(e.lower() for e in (a.get("emails") or [])))
        domain = (a.get("domain") or "").lower()

        new_phones = [p for p in phones if p not in self.seen_phones]
        new_emails = [e for e in emails if e not in self.seen_emails]
        socials = a.get("socials") or {}
        techs = a.get("technologies") or []

        # Drop only pages that add no new contact/evidence. Preserve the complete
        # contact set on pages that do contribute new information.
        contributes = bool(new_phones or new_emails or socials or techs)
        if not contributes and domain in self.seen_domains:
            raise DropItem("Duplicate domain evidence")

        self.seen_phones.update(phones)
        self.seen_emails.update(emails)
        if domain:
            self.seen_domains.add(domain)
        a["phones"], a["emails"] = phones, emails
        return item

class SQLitePipeline:
    def __init__(self):
        self.db_path = os.path.join("data", "numbo.db")
        os.makedirs("data", exist_ok=True)
        self.conn = None
        self._owns_connection = False
        self.logger = None

    def open_spider(self, spider):
        # The spider's CrawlHistory already owns the SQLite connection used for
        # crawl frontier/discovery writes. Reuse that connection instead of
        # opening a second writer in the same process. Two concurrent SQLite
        # writers were the source of intermittent "database is locked" stalls.
        frontier = getattr(spider, "frontier", None)
        if frontier is not None and getattr(frontier, "conn", None) is not None:
            self.conn = frontier.conn
            self._owns_connection = False
        else:
            self.conn = sqlite3.connect(self.db_path, timeout=30)
            self._owns_connection = True
        self.logger = getattr(spider, "logger", None)
        self.write_lock = getattr(frontier, "write_lock", None) if frontier is not None else None
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT,
                domain TEXT,
                title TEXT,
                phones TEXT,
                emails TEXT,
                address TEXT,
                business_name TEXT,
                category TEXT,
                city TEXT,
                socials TEXT,
                technologies TEXT,
                crawled_at TEXT,
                quality_score REAL,
                evidence TEXT,
                UNIQUE(source_url, phones)
            )
        """)
        for name, typ in [("quality_score", "REAL"), ("evidence", "TEXT")]:
            try:
                self.conn.execute(f"ALTER TABLE contacts ADD COLUMN {name} {typ}")
            except sqlite3.OperationalError:
                pass
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_domain ON contacts(domain)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_crawled ON contacts(crawled_at)")
        self.conn.commit()

    def close_spider(self):
        if self.conn:
            self.conn.commit()
            if self._owns_connection:
                self.conn.close()
            self.conn = None

    def process_item(self, item):
        a = ItemAdapter(item)
        values = (
            a.get("source_url"), a.get("domain"), a.get("title"),
            ",".join(a.get("phones") or []), ",".join(a.get("emails") or []),
            a.get("address"), a.get("business_name"), a.get("category"),
            a.get("city"), json.dumps(a.get("socials") or {}, ensure_ascii=False),
            format_technologies(a.get("technologies") or []),
            a.get("crawled_at") or datetime.utcnow().isoformat(),
            float(a.get("quality_score") or 0),
            json.dumps(a.get("evidence") or {}, ensure_ascii=False),
        )
        statement = """
            INSERT OR IGNORE INTO contacts
            (source_url,domain,title,phones,emails,address,business_name,category,city,
             socials,technologies,crawled_at,quality_score,evidence)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        lock = self.write_lock
        if lock is None:
            import threading
            lock = threading.RLock()
        with lock:
            for attempt in range(6):
                try:
                    self.conn.execute(statement, values)
                    self.conn.commit()
                    return item
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() or attempt == 5:
                        (self.logger or __import__("logging").getLogger(__name__)).error(
                            "DB error after lock retries: %s", exc
                        )
                        raise
                    self.conn.rollback()
                    import time
                    time.sleep(0.10 * (2 ** attempt))
                except sqlite3.Error as exc:
                    self.conn.rollback()
                    (self.logger or __import__("logging").getLogger(__name__)).error(
                        "DB error: %s", exc
                    )
                    raise
        return item
