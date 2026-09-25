import os
import scrapy
from urllib.parse import urlparse, urljoin
from datetime import datetime
from numbo.items import ContactItem
from numbo.utils.phone import extract_phones
from numbo.utils.category import detect_city, detect_category, extract_emails
from numbo.utils.tech import detect_technologies
from numbo.config import load as load_config


class ContactSpider(scrapy.Spider):
    name = "contact"
    custom_settings = {
        "DEPTH_LIMIT": 3,
    }

    def __init__(self, seeds_file="seeds.txt", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seeds_file = seeds_file
        self.start_urls = []
        self.allowed_domains = []

        cfg = load_config()
        self.allowed_tlds = [t.lower().strip() for t in (cfg.get("allowed_tlds") or []) if str(t).strip()]

        if os.path.exists(seeds_file):
            with open(seeds_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if not line.startswith("http"):
                        line = "https://" + line

                    domain = urlparse(line).netloc.lower().replace("www.", "")
                    if not domain:
                        continue

                    if self.allowed_tlds and not any(domain.endswith(tld) for tld in self.allowed_tlds):
                        self.logger.debug("Skipping non-allowed TLD: %s", domain)
                        continue

                    self.start_urls.append(line)
                    if domain not in self.allowed_domains:
                        self.allowed_domains.append(domain)

        if not self.start_urls:
            self.logger.warning(
                "No valid seeds found in %s (after TLD filter).",
                seeds_file,
            )

    def is_allowed_domain(self, domain: str) -> bool:
        domain = domain.lower().replace("www.", "")
        if domain not in self.allowed_domains:
            return False
        if self.allowed_tlds and not any(domain.endswith(tld) for tld in self.allowed_tlds):
            return False
        return True

    def parse(self, response):
        text = " ".join(response.css("::text").getall())
        html = response.text or ""
        title = response.css("title::text").get(default="").strip()

        phones = extract_phones(text)
        emails = extract_emails(text)

        headers = {
            k.decode() if isinstance(k, bytes) else k:
            v[0].decode() if isinstance(v[0], bytes) else v[0]
            for k, v in response.headers.items()
        }
        technologies = detect_technologies(html=html, url=response.url, headers=headers)

        domain = urlparse(response.url).netloc.lower().replace("www.", "")
        city = detect_city(text)
        category = detect_category(text, domain)
        business = title.split("-")[0].split("|")[0].strip() if title else domain

        socials = {}
        for a in response.css("a::attr(href)").getall():
            a_lower = a.lower()
            if "instagram.com" in a_lower:
                socials["instagram"] = a
            elif "t.me" in a_lower or "telegram" in a_lower:
                socials["telegram"] = a
            elif "linkedin.com" in a_lower:
                socials["linkedin"] = a
            elif "twitter.com" in a_lower or "x.com" in a_lower:
                socials["twitter"] = a

        if phones or emails or technologies:
            item = ContactItem()
            item["source_url"] = response.url
            item["domain"] = domain
            item["title"] = title
            item["phones"] = phones
            item["emails"] = emails
            item["address"] = None
            item["business_name"] = business
            item["category"] = category
            item["city"] = city
            item["socials"] = socials
            item["technologies"] = technologies
            item["crawled_at"] = datetime.utcnow().isoformat()
            yield item

        for href in response.css("a::attr(href)").getall():
            full = urljoin(response.url, href)
            parsed = urlparse(full)
            if parsed.scheme not in ("http", "https"):
                continue
            domain = parsed.netloc.lower().replace("www.", "")
            if not self.is_allowed_domain(domain):
                continue
            path = parsed.path.lower()
            if any(k in path for k in ["contact", "about", "tamas"]):
                yield response.follow(full, callback=self.parse, priority=10)
            else:
                yield response.follow(full, callback=self.parse)
