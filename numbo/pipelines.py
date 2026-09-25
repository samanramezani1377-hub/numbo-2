import json
import os
import sqlite3
from datetime import datetime
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
from numbo.utils.tech import format_technologies

class ValidationPipeline:
    def process_item(self, item, spider):
        a = ItemAdapter(item)
        phones = a.get("phones") or []
        emails = a.get("emails") or []
        techs = a.get("technologies") or []
        socials = a.get("socials") or {}
        if not phones and not emails and not techs and not socials:
            raise DropItem("No useful contact, technology or social data")
        if any(len(p) < 8 for p in phones):
            raise DropItem("Invalid normalized phone")
        return item

class DeduplicationPipeline:
    def __init__(self):
        self.seen_phones, self.seen_emails, self.seen_domains = set(), set(), set()

    def process_item(self, item, spider):
        a = ItemAdapter(item)
        phones = list(dict.fromkeys(a.get("phones") or []))
        emails = list(dict.fromkeys(e.lower() for e in (a.get("emails") or [])))
        domain = (a.get("domain") or "").lower()
        new_phones = [p for p in phones if p not in self.seen_phones]
        new_emails = [e for e in emails if e not in self.seen_emails]

        # Keep a page if it contributes new evidence. Otherwise only one technology/social snapshot per domain.
        has_new_social = bool(a.get("socials"))
        if not new_phones and not new_emails and not has_new_social and domain in self.seen_domains:
            raise DropItem("Duplicate domain evidence")

        self.seen_phones.update(new_phones)
        self.seen_emails.update(new_emails)
        if domain:
            self.seen_domains.add(domain)

        a["phones"], a["emails"] = new_phones, new_emails
        return item

class SQLitePipeline:
    def __init__(self):
        self.db_path = os.path.join("data", "numbo.db")
        os.makedirs("data", exist_ok=True)
        self.conn = None

    def open_spider(self, spider):
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
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
        migrations = [
            ("quality_score", "REAL"),
            ("evidence", "TEXT"),
        ]
        for name, typ in migrations:
            try:
                self.conn.execute(f"ALTER TABLE contacts ADD COLUMN {name} {typ}")
            except sqlite3.OperationalError:
                pass
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_domain ON contacts(domain)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_contacts_crawled ON contacts(crawled_at)")
        self.conn.commit()

    def close_spider(self, spider):
        if self.conn:
            self.conn.commit()
            self.conn.close()

    def process_item(self, item, spider):
        a = ItemAdapter(item)
        values = (
            a.get("source_url"), a.get("domain"), a.get("title"),
            ",".join(a.get("phones") or []), ",".join(a.get("emails") or []),
            a.get("address"), a.get("business_name"), a.get("category"),
            a.get("city"), json.dumps(a.get("socials") or {}, ensure_ascii=False),
            format_technologies(a.get("technologies") or []),
            a.get("crawled_at") or datetime.utcnow().isoformat(),
            float(a.get("quality_score") or 0), json.dumps(a.get("evidence") or {}, ensure_ascii=False),
        )
        try:
            self.conn.execute("""
                INSERT OR IGNORE INTO contacts
                (source_url,domain,title,phones,emails,address,business_name,category,city,
                 socials,technologies,crawled_at,quality_score,evidence)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, values)
            self.conn.commit()
        except sqlite3.Error as exc:
            spider.logger.error("DB error: %s", exc)
            raise
        return item
