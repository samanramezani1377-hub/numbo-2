import os
import re
import json
import scrapy
from scrapy import signals
from scrapy.exceptions import DontCloseSpider
from urllib.parse import urlparse, urljoin, urldefrag, urlunparse, parse_qsl, urlencode
from datetime import datetime
from numbo.items import ContactItem
from numbo.utils.phone import extract_phones
from numbo.utils.category import (
    detect_city, detect_category, extract_emails, extract_socials,
    extract_business_name, extract_address,
)
from numbo.utils.tech import detect_technologies
from numbo.config import load as load_config
from numbo.frontier import CrawlHistory
from numbo.qualification import qualify_record, is_blocked_lead_domain

class ContactSpider(scrapy.Spider):
    name = "contact"
    custom_settings = {"DEPTH_LIMIT": 0, "NUMBO_PAGE_BUDGET": 20}

    IMPORTANT_PATHS = ("contact", "contact-us", "about", "about-us", "support", "help", "service", "services", "product", "products", "shop", "store", "catalog", "category", "تماس", "درباره", "خدمات", "محصول", "فروشگاه", "tamas")
    SKIP_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".zip",
                       ".rar", ".mp4", ".mp3", ".css", ".js", ".woff", ".woff2")
    TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                       "gclid", "fbclid", "mc_cid", "mc_eid"}
    EXPLICIT_URL_RE = re.compile(r"https?://[^\s<>]+", re.I)
    RESOURCE_SELECTORS = (
        ("script[src]::attr(src)", "script"),
        ("img[src]::attr(src)", "image"),
        ("iframe[src]::attr(src)", "iframe"),
        ("frame[src]::attr(src)", "frame"),
        ("video[src]::attr(src)", "video"),
        ("audio[src]::attr(src)", "audio"),
        ("source[src]::attr(src)", "source"),
        ("object[data]::attr(data)", "object"),
        ("form[action]::attr(action)", "form"),
    )
    RESOURCE_LINK_TYPES = {"script", "image", "iframe", "frame", "video", "audio", "source", "object"}

    def __init__(self, seeds_file="seeds.txt", *args, **kwargs):
        page_budget_arg = kwargs.pop("page_budget", None)
        frontier_db = kwargs.pop("frontier_db", os.path.join("data", "numbo.db"))
        layered_arg = kwargs.pop("layered_crawl", False)
        super().__init__(*args, **kwargs)
        self.seeds_file = seeds_file
        default_budget = self.custom_settings.get("NUMBO_PAGE_BUDGET", 20)
        self.page_budget = max(1, int(page_budget_arg if page_budget_arg is not None else default_budget))
        self.layered_crawl = str(layered_arg).lower() in {"1", "true", "yes", "on"}
        self.start_urls, self.allowed_domains = [], []
        self.seed_domains = set()
        self.site_pages = {}
        self._batch_no = 1
        self.frontier = CrawlHistory(frontier_db)
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
                    if not domain:
                        continue
                    # An explicit seed is always honored, even when its TLD is
                    # outside the global filter. The exception is scoped to the
                    # exact seeded domain; it does not open crawling to other
                    # domains with that TLD.
                    self.seed_domains.add(domain)
                    line = self._canonical_url(line)
                    if line not in self.start_urls:
                        self.start_urls.append(line)
                    if domain not in self.allowed_domains:
                        self.allowed_domains.append(domain)
                    self.site_pages.setdefault(domain, {"scheduled": set(), "count": 0, "batch_count": 0})
        if not self.start_urls:
            self.logger.warning("No valid seeds found in %s (after TLD filter).", seeds_file)

    def start_requests(self):
        for seed in self.start_urls:
            if self.layered_crawl:
                self.frontier.queue_layered_url(seed, seed, 0, source_url=None)
            request = self._request_page(seed, priority=50, meta={"numbo_source": "seed", "numbo_seed": seed, "numbo_depth": 0}, seed=True, crawl_depth=0, crawl_seed=seed)
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
        hostname = (parsed.hostname or "").lower()
        # Preserve an explicit port for local/test runtimes such as 127.0.0.1:8765.
        netloc = hostname
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        return urlunparse((parsed.scheme.lower(), netloc,
                           path, "", urlencode(sorted(query)), ""))

    def is_allowed_domain(self, domain: str) -> bool:
        domain = (domain or "").lower().removeprefix("www.")
        if not domain:
            return False
        # Explicit seeds are always crawlable for their own domain, regardless
        # of the global TLD filter. This keeps a .com seed usable while the
        # global filter remains .ir, without allowing unrelated .com sites.
        if domain in self.seed_domains:
            return True
        return bool(not self.allowed_tlds or any(domain.endswith(tld) for tld in self.allowed_tlds))

    def _add_discovery(self, response, discovered, seen, href, link_type, crawl_hint=True):
        """Normalize and append one discovery edge without changing crawl semantics."""
        if not href:
            return
        href = str(href).strip()
        if not href or href.startswith(("#", "javascript:", "data:", "blob:", "mailto:", "tel:")):
            return
        href = href.strip(" \t\r\n.,;:!?)]}'\"")
        if not href:
            return
        full = self._canonical_url(urljoin(response.url, href))
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return
        if full in seen:
            return
        seen.add(full)
        source_domain = self._site_key(response.url)
        target_domain = self._site_key(full)
        allowed = self.is_allowed_domain(target_domain)
        crawlable = bool(
            crawl_hint and allowed
            and not parsed.path.lower().endswith(self.SKIP_EXTENSIONS)
            and not is_blocked_lead_domain(target_domain)
            and not self._is_non_content_external(full)
        )
        discovered.append((
            response.url, full, target_domain,
            target_domain != source_domain, crawlable, link_type,
        ))

    def _extract_explicit_urls(self, text):
        """Find explicit HTTP(S) URLs while filtering obvious schema/documentation noise."""
        if not text:
            return []
        blocked_hosts = {
            "schema.org", "www.w3.org", "w3.org", "json-schema.org",
            "purl.org", "xmlns.com", "ogp.me",
        }
        found = []
        seen = set()
        for match in self.EXPLICIT_URL_RE.findall(text):
            value = match.strip(" \t\r\n.,;:!?)]}'\"")
            try:
                parsed = urlparse(value)
            except ValueError:
                continue
            host = (parsed.hostname or "").lower().removeprefix("www.")
            if not host or host in blocked_hosts:
                continue
            full = self._canonical_url(value)
            if full not in seen:
                seen.add(full)
                found.append(full)
        return found

    def _links(self, response):
        seen = set()
        discovered = []

        for href in response.css("a::attr(href)").getall():
            self._add_discovery(response, discovered, seen, href, "anchor", True)
        for href in response.css('link[rel~="canonical"]::attr(href)').getall():
            self._add_discovery(response, discovered, seen, href, "canonical", True)
        for href in response.css('link[rel~="alternate"][hreflang]::attr(href)').getall():
            self._add_discovery(response, discovered, seen, href, "hreflang", True)

        for selector, link_type in self.RESOURCE_SELECTORS:
            for href in response.css(selector).getall():
                self._add_discovery(response, discovered, seen, href, link_type, False)

        for value in response.css("[srcset]::attr(srcset)").getall():
            for candidate in value.split(","):
                href = candidate.strip().split(" ", 1)[0]
                self._add_discovery(response, discovered, seen, href, "srcset", False)

        for value in response.css('meta[http-equiv]::attr(content)').getall():
            if re.match(r"^\s*\d+\s*;", value or ""):
                match = re.search(r";\s*url\s*=\s*(.+)$", value, flags=re.I)
                if match:
                    self._add_discovery(response, discovered, seen, match.group(1), "meta_refresh", True)

        for raw_json in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(raw_json)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            stack = [data]
            while stack:
                node = stack.pop()
                if isinstance(node, list):
                    stack.extend(node)
                    continue
                if isinstance(node, str):
                    for href in self._extract_explicit_urls(node):
                        self._add_discovery(response, discovered, seen, href, "jsonld", True)
                    continue
                if not isinstance(node, dict):
                    continue
                for key, value in node.items():
                    if isinstance(value, str) and (
                        key in {"url", "@id", "sameAs", "mainEntityOfPage", "image", "logo"}
                        or value.startswith(("http://", "https://"))
                    ):
                        for href in self._extract_explicit_urls(value):
                            self._add_discovery(response, discovered, seen, href, "jsonld", True)
                    if isinstance(value, (dict, list)):
                        stack.append(value)

        for href in self._extract_explicit_urls(response.text or ""):
            self._add_discovery(response, discovered, seen, href, "text_or_script", True)

        redirect_urls = list(response.request.meta.get("redirect_urls") or [])
        chain = [self._canonical_url(response.request.url)] + [
            self._canonical_url(value) for value in redirect_urls
        ] + [self._canonical_url(response.url)]
        for source, target in zip(chain, chain[1:]):
            if source != target:
                source_domain = self._site_key(source)
                target_domain = self._site_key(target)
                if target_domain:
                    allowed = self.is_allowed_domain(target_domain)
                    discovered.append((
                        source, target, target_domain,
                        target_domain != source_domain,
                        bool(allowed and not target.lower().endswith(self.SKIP_EXTENSIONS)),
                        "redirect",
                    ))

        self.frontier.record_discovered_links(discovered)
        # Preserve the crawler's existing contract: every navigational URL is
        # yielded to Scrapy even when its TLD is disallowed. parse() then keeps
        # it discovery-only. Resource URLs are recorded but never scheduled.
        for _, full, _, _, _, link_type in discovered:
            if link_type in self.RESOURCE_LINK_TYPES or link_type == "srcset":
                continue
            if urlparse(full).path.lower().endswith(self.SKIP_EXTENSIONS):
                continue
            yield full

    def _url_priority(self, url):
        """Prioritize useful content paths without excluding any discovered URL."""
        path = urlparse(url).path.lower().strip("/")
        if not path:
            return 5
        if any(token in path for token in ("contact", "contact-us", "تماس", "tamas")):
            return 30
        if any(token in path for token in ("about", "about-us", "درباره")):
            return 28
        if any(token in path for token in ("service", "services", "support", "help", "خدمات")):
            return 24
        if any(token in path for token in ("product", "products", "shop", "store", "catalog", "category", "محصول", "فروشگاه")):
            return 20
        return 5

    def _is_non_content_external(self, url):
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = parsed.path.lower()
        if host in {"linkedin.com", "facebook.com", "twitter.com", "x.com"} and (
            path.startswith("/share") or path.startswith("/sharer") or path.startswith("/intent")
        ):
            return True
        if host in {"t.me", "telegram.me", "telegram.dog"} and path.startswith("/share"):
            return True
        if host == "wa.me" or host == "api.whatsapp.com":
            return True
        # Some sites accidentally turn external share links into local paths,
        # e.g. /ble.ir/<channel>. Keep them in discovery history, but do not
        # spend crawl budget on them.
        known_external_path_prefixes = (
            "/ble.ir/", "/t.me/", "/telegram.me/", "/facebook.com/",
            "/instagram.com/", "/linkedin.com/", "/twitter.com/", "/x.com/",
        )
        if any(path.startswith(prefix) for prefix in known_external_path_prefixes):
            return True
        return False

    def _reserve_page(self, url, seed=False):
        domain = self._site_key(url)
        state = self.site_pages.setdefault(domain, {"scheduled": set(), "count": 0, "batch_count": 0})
        if url in state["scheduled"]:
            return False
        # batch_count already includes every URL reserved for this batch.
        # Adding len(scheduled) double-counts pending requests and cuts a
        # 20-page batch roughly in half.
        if state["batch_count"] >= self.page_budget:
            return False
        if seed:
            self.frontier.reserve_seed(url, domain)
        elif not self.frontier.reserve(url, domain):
            return False
        state["scheduled"].add(url)
        return True

    def _request_page(self, url, priority=0, meta=None, seed=False, crawl_depth=None, crawl_seed=None):
        target_domain = self._site_key(url)
        if self.is_allowed_domain(target_domain) and target_domain not in self.allowed_domains:
            # Keep Scrapy's OffsiteMiddleware in sync for configuration-allowed
            # domains discovered after the spider starts.
            self.allowed_domains.append(target_domain)
        if not self._reserve_page(url, seed=seed):
            if self.layered_crawl and crawl_seed and self.frontier.was_crawled(url):
                self.frontier.mark_layered_crawled(url)
            return None
        state = self.site_pages[self._site_key(url)]
        state["batch_count"] += 1
        request_meta = dict(meta or {})
        request_meta["numbo_site"] = self._site_key(url)
        if self.layered_crawl and crawl_seed:
            request_meta["numbo_seed"] = crawl_seed
            request_meta["numbo_depth"] = max(int(crawl_depth or 0), 0)
            self.frontier.mark_layered_queued(crawl_seed, url)
        return scrapy.Request(
            url,
            callback=self.parse,
            errback=self.request_failed,
            priority=priority,
            meta=request_meta,
        )

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_idle, signal=signals.spider_idle)
        return spider

    def spider_idle(self, spider):
        """Open the next batch; layered mode advances one BFS depth at a time."""
        scheduled = 0
        if self.layered_crawl:
            for seed in self.start_urls:
                pending = self.frontier.next_layered_batch(seed, limit=self.page_budget)
                if not pending:
                    continue
                domain = self._site_key(seed)
                state = self.site_pages.setdefault(domain, {"scheduled": set(), "count": 0, "batch_count": 0})
                state["batch_count"] = 0
                batch_scheduled = 0
                depth = pending[0][1]
                for url, url_depth in pending:
                    request = self._request_page(
                        url, priority=10,
                        meta={"numbo_source": "layered_batch"},
                        crawl_depth=url_depth, crawl_seed=seed,
                    )
                    if request:
                        batch_scheduled += 1
                        engine_crawl = getattr(self.crawler.engine, "crawl", None)
                        if engine_crawl:
                            engine_crawl(request)
                if batch_scheduled:
                    scheduled += batch_scheduled
                    self.logger.info(
                        "Layered crawl %s: depth=%d batch=%d",
                        seed, depth, batch_scheduled,
                    )
            if scheduled:
                raise DontCloseSpider()
            return

        for domain in sorted(self.site_pages):
            state = self.site_pages[domain]
            pending = self.frontier.next_crawl_batch(domain, limit=self.page_budget)
            if not pending:
                continue
            state["batch_count"] = 0
            batch_scheduled = 0
            for url in pending:
                request = self._request_page(url, priority=10, meta={"numbo_source": "next_batch"})
                if request:
                    batch_scheduled += 1
                    yield_request = getattr(self.crawler.engine, "crawl", None)
                    if yield_request:
                        yield_request(request)
            if batch_scheduled:
                scheduled += batch_scheduled
                self.logger.info(
                    "Starting next crawl batch for %s: %d pages (batch size=%d)",
                    domain, batch_scheduled, self.page_budget,
                )
        if scheduled:
            raise DontCloseSpider()

    def parse_aux(self, response):
        ctype = (response.headers.get("Content-Type") or b"").decode("latin1").lower()
        body = response.text or ""

        # robots.txt can advertise multiple sitemap sources.
        if response.url.lower().endswith("/robots.txt"):
            for raw_line in body.splitlines():
                match = re.match(r"^\s*sitemap\s*:\s*(\S+)\s*$", raw_line, flags=re.I)
                if not match:
                    continue
                loc = self._canonical_url(match.group(1))
                parsed = urlparse(loc)
                target_domain = self._site_key(loc)
                if parsed.scheme not in ("http", "https") or not target_domain:
                    continue
                allowed = self.is_allowed_domain(target_domain)
                self.frontier.record_discovered_link(
                    response.url, loc, target_domain,
                    target_domain != self._site_key(response.url),
                    allowed, link_type="robots_sitemap"
                )
                if allowed:
                    yield scrapy.Request(
                        loc, callback=self.parse_aux, priority=35,
                        meta={"numbo_site": self._site_key(loc), "numbo_aux": True}
                    )
            return

        if response.url.lower().endswith((".xml", "sitemap.xml", "sitemap_index.xml")) or "xml" in ctype:
            for raw_loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", body, flags=re.I | re.S):
                loc = self._canonical_url(re.sub(r"<[^>]+>", "", raw_loc).strip())
                parsed = urlparse(loc)
                target_domain = self._site_key(loc)
                if parsed.scheme not in ("http", "https") or not target_domain:
                    continue
                allowed = self.is_allowed_domain(target_domain)
                is_sitemap = loc.lower().endswith((".xml", ".xml.gz")) or "sitemap" in parsed.path.lower()
                self.frontier.record_discovered_link(
                    response.url, loc, target_domain,
                    target_domain != self._site_key(response.url),
                    allowed, link_type="sitemap"
                )
                if is_sitemap:
                    if allowed:
                        yield scrapy.Request(
                            loc, callback=self.parse_aux, priority=30,
                            meta={"numbo_site": self._site_key(loc), "numbo_aux": True}
                        )
                    continue
                if allowed:
                    request = self._request_page(
                        loc, priority=15, meta={"numbo_source": "sitemap"}
                    )
                    if request:
                        yield request

    def request_failed(self, failure):
        request = failure.request
        url = self._canonical_url(request.url)
        domain = self._site_key(url)
        state = self.site_pages.setdefault(domain, {"scheduled": set(), "count": 0, "batch_count": 0})
        state["scheduled"].discard(url)
        self.frontier.mark_failed(url)
        if self.layered_crawl:
            self.frontier.mark_layered_failed(url)
        self.logger.warning("Page request failed: %s (%s)", url, failure.value)

    def parse(self, response):
        domain = self._site_key(response.url)
        state = self.site_pages.setdefault(domain, {"scheduled": set(), "count": 0, "batch_count": 0})
        requested_url = self._canonical_url(response.request.url)
        state["scheduled"].discard(requested_url)
        state["scheduled"].discard(self._canonical_url(response.url))
        state["count"] += 1
        self.frontier.mark_crawled(requested_url)
        if self.layered_crawl:
            self.frontier.mark_layered_crawled(requested_url)
        final_url = self._canonical_url(response.url)
        if final_url != requested_url:
            self.frontier.mark_crawled(final_url)
            if self.layered_crawl:
                self.frontier.mark_layered_crawled(final_url)

        # Extract visible body text only. Script/style/noscript contents often contain
        # JSON configuration, prices, IDs and phone-like digit sequences that must
        # never become lead data.
        visible_chunks = [
            t.strip()
            for t in response.xpath(
                "//body//text()[not(ancestor::script) and not(ancestor::style) "
                "and not(ancestor::noscript) and not(ancestor::template)]"
            ).getall()
            if t.strip()
        ]
        # Keep a line-oriented version for address labels; collapsing everything
        # into one string lets a label accidentally capture the next 300 chars.
        visible_text = "\\n".join(visible_chunks)
        text = " ".join(visible_chunks)
        html = response.text or ""
        title = response.css("title::text").get(default="").strip()

        phones = extract_phones(text)
        tel_phones = []
        for href in response.css('a[href^="tel:"]::attr(href)').getall():
            tel_phones.extend(extract_phones(href[4:]))
        phones = sorted(set(phones + tel_phones))

        emails = extract_emails(text)
        mailto_hrefs = response.css('a[href^="mailto:"]::attr(href)').getall()
        for href in mailto_hrefs:
            emails.extend(extract_emails(href[7:].split("?")[0]))

        # JSON-LD commonly carries telephone/email without exposing it in visible text.
        # Parse only structured-data contact fields to avoid false positives from scripts.
        jsonld_contacts = []
        for raw_json in response.css('script[type="application/ld+json"]::text').getall():
            try:
                data = json.loads(raw_json)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            stack = data if isinstance(data, list) else [data]
            while stack:
                node = stack.pop()
                if isinstance(node, list):
                    stack.extend(node)
                    continue
                if not isinstance(node, dict):
                    continue
                for key in ("telephone", "phone", "email"):
                    value = node.get(key)
                    if isinstance(value, str):
                        jsonld_contacts.append((key, value))
                for value in node.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)

        for key, value in jsonld_contacts:
            if key in ("telephone", "phone"):
                phones.extend(extract_phones(value))
            else:
                emails.extend(extract_emails(value))
        phones = sorted(set(phones))
        emails = sorted(set(emails))

        headers = {k.decode() if isinstance(k, bytes) else k:
                   v[0].decode() if isinstance(v[0], bytes) else v[0]
                   for k, v in response.headers.items()}
        technologies = detect_technologies(html=html, url=response.url, headers=headers)
        self.frontier.record_technology_evidence(domain, response.url, technologies)
        city = detect_city(text)
        category = detect_category(text, domain)
        business = extract_business_name(response, domain)
        address = extract_address(response, visible_text)
        socials = extract_socials(response)

        evidence = {
            "page": response.url,
            "field_sources": {
                "phones": [response.url] if phones else [],
                "emails": [response.url] if emails else [],
                "address": [response.url] if address else [],
                "business_name": [response.url] if business else [],
                "city": [response.url] if city else [],
                "category": [response.url] if category else [],
                "socials": [response.url] if socials else [],
                "technologies": [response.url] if technologies else [],
            },
            "address_detected": bool(address),
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
        if address: quality += 0.10

        qualified = qualify_record({"domain": domain, "phones": phones, "emails": emails, "address": address, "business_name": business, "category": category})
        if qualified:
            phones = qualified["phones"]
            emails = qualified["emails"]
            business = qualified["business_name"]
            address = qualified["address"]
            yield ContactItem(
                source_url=response.url,
                domain=domain,
                title=title,
                phones=phones,
                emails=emails,
                address=address,
                business_name=business,
                category=category,
                city=city,
                socials=socials,
                technologies=technologies,
                crawled_at=datetime.utcnow().isoformat(),
                quality_score=round(min(quality, 1.0), 2),
                evidence=evidence,
            )

        parent_seed = response.request.meta.get("numbo_seed")
        parent_depth = int(response.request.meta.get("numbo_depth", 0) or 0)

        for full in self._links(response):
            path = urlparse(full).path.lower()
            priority = self._url_priority(full)
            target_domain = self._site_key(full)
            child_depth = parent_depth + 1
            if self.layered_crawl and parent_seed:
                self.frontier.queue_layered_url(
                    parent_seed, full, child_depth, source_url=response.url
                )
            # A discovered link becomes crawlable when its target TLD is
            # allowed by the current configuration, even when it belongs
            # to a different domain. Disallowed links remain discovery-only.
            if not self.is_allowed_domain(target_domain):
                continue
            # Keep known platform/utility destinations in discovery history,
            # but never spend crawl budget or retry time on them.
            if is_blocked_lead_domain(target_domain):
                continue
            # Keep social/share action URLs in discovery history, but do not
            # spend crawl budget on endpoints that are not content pages.
            if self._is_non_content_external(full):
                continue
            # Scrapy's OffsiteMiddleware also checks allowed_domains. Add
            # newly discovered, configuration-allowed domains dynamically so
            # an allowed external site can actually be fetched.
            if target_domain not in self.allowed_domains:
                self.allowed_domains.append(target_domain)
            # In layered mode, only depth-0 seed pages open their
            # direct children immediately. Every deeper page only records its
            # children; the idle scheduler opens that next layer later.
            if self.layered_crawl and parent_depth > 0:
                continue
            request = self._request_page(
                full,
                priority=priority,
                meta={"numbo_source": "external" if target_domain != domain else "internal"},
                crawl_depth=child_depth if self.layered_crawl else None,
                crawl_seed=parent_seed if self.layered_crawl else None,
            )
            if request:
                yield request

    def closed(self, reason):
        self.frontier.close()
