import os
import re
import scrapy
from urllib.parse import urlparse, urljoin, urldefrag
from datetime import datetime
from numbo.items import ContactItem
from numbo.utils.phone import extract_phones
from numbo.utils.category import (
    detect_city, detect_category, extract_emails, extract_socials,
    extract_business_name,
)
from numbo.utils.tech import detect_technologies
from numbo.config import load as load_config

class ContactSpider(scrapy.Spider):
    name = "contact"
    custom_settings = {"DEPTH_LIMIT": 3}

    IMPORTANT_PATHS = ("contact", "contact-us", "about", "about-us", "تماس", "درباره", "tamas")
    SKIP_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".zip",
                       ".rar", ".mp4", ".mp3", ".css", ".js", ".woff", ".woff2")

    def __init__(self, seeds_file="seeds.txt", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seeds_file = seeds_file
        self.start_urls, self.allowed_domains = [], []
        self.allowed_tlds = [t.lower().strip() for t in
                             (load_config().get("allowed_tlds") or []) if str(t).strip()]
        if os.path.exists(seeds_file):
            with open(seeds_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if not line.startswith(("http://", "https://")):
                        line = "https://" + line
                    domain = (urlparse(line).hostname or "").lower().removeprefix("www.")
                    if not domain or (self.allowed_tlds and not any(domain.endswith(t) for t in self.allowed_tlds)):
                        continue
                    line, _ = urldefrag(line)
                    if line not in self.start_urls:
                        self.start_urls.append(line)
                    if domain not in self.allowed_domains:
                        self.allowed_domains.append(domain)
        if not self.start_urls:
            self.logger.warning("No valid seeds found in %s (after TLD filter).", seeds_file)

    def is_allowed_domain(self, domain: str) -> bool:
        domain = (domain or "").lower().removeprefix("www.")
        return bool(domain in self.allowed_domains and
                    (not self.allowed_tlds or any(domain.endswith(tld) for tld in self.allowed_tlds)))

    def _links(self, response):
        seen = set()
        for href in response.css("a::attr(href)").getall():
            full = urldefrag(urljoin(response.url, href))[0]
            parsed = urlparse(full)
            if parsed.scheme not in ("http", "https") or not self.is_allowed_domain(parsed.hostname or ""):
                continue
            if parsed.path.lower().endswith(self.SKIP_EXTENSIONS):
                continue
            if full not in seen:
                seen.add(full)
                yield full

    def parse(self, response):
        text = " ".join(t.strip() for t in response.css("body ::text, body::text").getall() if t.strip())
        html = response.text or ""
        title = response.css("title::text").get(default="").strip()

        phones = extract_phones(text)
        # Also inspect hrefs because tel: links are high-confidence evidence.
        tel_phones = []
        for href in response.css('a[href^="tel:"]::attr(href)').getall():
            tel_phones.extend(extract_phones(href[4:]))
        phones = sorted(set(phones + tel_phones))

        emails = extract_emails(text)
        for href in response.css('a[href^="mailto:"]::attr(href)').getall():
            emails.extend(extract_emails(href[7:].split("?")[0]))
        emails = sorted(set(emails))

        headers = {k.decode() if isinstance(k, bytes) else k:
                   v[0].decode() if isinstance(v[0], bytes) else v[0]
                   for k, v in response.headers.items()}
        technologies = detect_technologies(html=html, url=response.url, headers=headers)
        domain = (urlparse(response.url).hostname or "").lower().removeprefix("www.")
        city = detect_city(text)
        category = detect_category(text, domain)
        business = extract_business_name(response, domain)
        socials = extract_socials(response)

        evidence = {
            "page": response.url,
            "tel_links": len(tel_phones),
            "mailto_links": len(response.css('a[href^="mailto:"]::attr(href)').getall()),
            "socials": sorted(socials),
            "technologies": [t["name"] for t in technologies],
        }
        quality = 0.0
        if phones: quality += 0.35
        if emails: quality += 0.25
        if socials: quality += 0.10
        if technologies: quality += 0.10
        if business and business != domain: quality += 0.10
        if city: quality += 0.10

        if phones or emails or technologies or socials:
            item = ContactItem(
                source_url=response.url,
                domain=domain,
                title=title,
                phones=phones,
                emails=emails,
                address=None,
                business_name=business,
                category=category,
                city=city,
                socials=socials,
                technologies=technologies,
                crawled_at=datetime.utcnow().isoformat(),
                quality_score=round(min(quality, 1.0), 2),
                evidence=evidence,
            )
            yield item

        for full in self._links(response):
            path = urlparse(full).path.lower()
            priority = 20 if any(k in path for k in self.IMPORTANT_PATHS) else 0
            yield response.follow(full, callback=self.parse, priority=priority)
