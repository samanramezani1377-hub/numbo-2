import os
import re
import scrapy
from urllib.parse import urlparse, urljoin, urldefrag, urlunparse, parse_qsl, urlencode
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
    custom_settings = {"DEPTH_LIMIT": 4, "NUMBO_PAGE_BUDGET": 20}

    IMPORTANT_PATHS = ("contact", "contact-us", "about", "about-us", "تماس", "درباره", "tamas")
    SKIP_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".zip",
                       ".rar", ".mp4", ".mp3", ".css", ".js", ".woff", ".woff2")
    TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                       "gclid", "fbclid", "mc_cid", "mc_eid"}

    def __init__(self, seeds_file="seeds.txt", *args, **kwargs):
        page_budget_arg = kwargs.pop("page_budget", None)
        super().__init__(*args, **kwargs)
        self.seeds_file = seeds_file
        default_budget = self.custom_settings.get("NUMBO_PAGE_BUDGET", 20)
        self.page_budget = max(1, int(page_budget_arg if page_budget_arg is not None else default_budget))
        self.start_urls, self.allowed_domains = [], []
        self.site_pages = {}
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
                    line = self._canonical_url(line)
                    if line not in self.start_urls:
                        self.start_urls.append(line)
                    if domain not in self.allowed_domains:
                        self.allowed_domains.append(domain)
                    self.site_pages.setdefault(domain, {"scheduled": set(), "count": 0})
        if not self.start_urls:
            self.logger.warning("No valid seeds found in %s (after TLD filter).", seeds_file)

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider.stats = crawler.stats
        return spider

    def start_requests(self):
        for seed in self.start_urls:
            request = self._request_page(seed, priority=50, meta={"numbo_source": "seed"})
            if request:
                yield request
            parsed = urlparse(seed)
            for path in ("/robots.txt", "/sitemap.xml", "/sitemap_index.xml"):
                yield scrapy.Request(
                    urlunparse((parsed.scheme, parsed.netloc, path, "", "", "")),
                    callback=self.parse_aux,
                    priority=40,
                    dont_filter=False,
                    meta={"numbo_site": self._site_key(seed), "numbo_aux": True},
                )

    def _site_key(self, url):
        return (urlparse(url).hostname or "").lower().removeprefix("www.")

    def _canonical_url(self, url):
        url, _ = urldefrag(url)
        parsed = urlparse(url)
        query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                 if k.lower() not in self.TRACKING_PARAMS]
        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/")
        return urlunparse((parsed.scheme.lower(), (parsed.hostname or "").lower(),
                           path, "", urlencode(sorted(query)), ""))

    def is_allowed_domain(self, domain: str) -> bool:
        domain = (domain or "").lower().removeprefix("www.")
        return bool(domain in self.allowed_domains and
                    (not self.allowed_tlds or any(domain.endswith(tld) for tld in self.allowed_tlds)))

    def _links(self, response):
        seen = set()
        for href in response.css("a::attr(href)").getall():
            full = self._canonical_url(urljoin(response.url, href))
            parsed = urlparse(full)
            if parsed.scheme not in ("http", "https") or not self.is_allowed_domain(parsed.hostname or ""):
                continue
            if parsed.path.lower().endswith(self.SKIP_EXTENSIONS):
                continue
            if full not in seen:
                seen.add(full)
                yield full

    def _reserve_page(self, url):
        domain = self._site_key(url)
        state = self.site_pages.setdefault(domain, {"scheduled": set(), "count": 0})
        if url in state["scheduled"]:
            return False
        if state["count"] + len(state["scheduled"]) >= self.page_budget:
            return False
        state["scheduled"].add(url)
        return True

    def _request_page(self, url, priority=0, meta=None):
        if not self._reserve_page(url):
            return None
        request_meta = dict(meta or {})
        request_meta["numbo_site"] = self._site_key(url)
        return scrapy.Request(url, callback=self.parse, priority=priority, meta=request_meta)

    def parse_aux(self, response):
        ctype = (response.headers.get("Content-Type") or b"").decode("latin1").lower()
        body = response.text or ""
        if response.url.lower().endswith((".xml", "sitemap.xml", "sitemap_index.xml")) or "xml" in ctype:
            for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", body, flags=re.I | re.S):
                loc = self._canonical_url(loc.strip())
                parsed = urlparse(loc)
                if self.is_allowed_domain(parsed.hostname or ""):
                    if loc.lower().endswith(".xml"):
                        yield scrapy.Request(
                            loc, callback=self.parse_aux, priority=30,
                            meta={"numbo_site": self._site_key(loc), "numbo_aux": True}
                        )
                    else:
                        request = self._request_page(
                            loc, priority=15, meta={"numbo_source": "sitemap"}
                        )
                        if request:
                            yield request

    def parse(self, response):
        domain = self._site_key(response.url)
        state = self.site_pages.setdefault(domain, {"scheduled": set(), "count": 0})
        state["scheduled"].discard(response.url)
        state["count"] += 1

        text = " ".join(t.strip() for t in response.css("body ::text, body::text").getall() if t.strip())
        html = response.text or ""
        title = response.css("title::text").get(default="").strip()

        phones = extract_phones(text)
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
            yield ContactItem(
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

        for full in self._links(response):
            path = urlparse(full).path.lower()
            priority = 20 if any(k in path for k in self.IMPORTANT_PATHS) else 0
            request = self._request_page(full, priority=priority)
            if request:
                yield request
