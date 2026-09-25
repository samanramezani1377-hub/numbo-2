import sqlite3
import os
import json
from datetime import datetime
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
from numbo.utils.tech import format_technologies


class ValidationPipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        phones = adapter.get("phones") or []
        emails = adapter.get("emails") or []
        # Allow items that only have technologies (useful for tech-only discovery)
        techs = adapter.get("technologies") or []
        if not phones and not emails and not techs:
            raise DropItem("No contact info or technologies found")
        return item


class DeduplicationPipeline:
    def __init__(self):
        self.seen_phones = set()
        self.seen_emails = set()
        self.seen_domains = set()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        phones = adapter.get("phones") or []
        emails = adapter.get("emails") or []
        domain = adapter.get("domain") or ""

        new_phones = [p for p in phones if p not in self.seen_phones]
        new_emails = [e for e in emails if e not in self.seen_emails]

        # If we already saw this domain and no new contacts, still allow tech update once
        if not new_phones and not new_emails:
            if domain in self.seen_domains:
                raise DropItem("Duplicate contact")
            self.seen_domains.add(domain)

        for p in new_phones:
            self.seen_phones.add(p)
        for e in new_emails:
            self.seen_emails.add(e)
        if domain:
            self.seen_domains.add(domain)

        adapter["phones"] = new_phones
        adapter["emails"] = new_emails
        return item


class SQLitePipeline:
    def __init__(self):
        self.db_path = os.path.join("data", "numbo.db")
        os.makedirs("data", exist_ok=True)
        self.conn = None

    def open_spider(self, spider):
        self.conn = sqlite3.connect(self.db_path)
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
                UNIQUE(source_url, phones)
            )
        """)
        # Migration for older DBs that don't have technologies column yet
        try:
            self.conn.execute("ALTER TABLE contacts ADD COLUMN technologies TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
        self.conn.commit()

    def close_spider(self, spider):
        if self.conn:
            self.conn.close()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        phones_str = ",".join(adapter.get("phones") or [])
        emails_str = ",".join(adapter.get("emails") or [])
        socials_str = str(adapter.get("socials") or {})
        techs = adapter.get("technologies") or []
        techs_str = format_technologies(techs)

        try:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO contacts
                (source_url, domain, title, phones, emails, address,
                 business_name, category, city, socials, technologies, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    adapter.get("source_url"),
                    adapter.get("domain"),
                    adapter.get("title"),
                    phones_str,
                    emails_str,
                    adapter.get("address"),
                    adapter.get("business_name"),
                    adapter.get("category"),
                    adapter.get("city"),
                    socials_str,
                    techs_str,
                    adapter.get("crawled_at") or datetime.utcnow().isoformat(),
                ),
            )
            self.conn.commit()
        except Exception as e:
            spider.logger.error(f"DB error: {e}")
        return item
