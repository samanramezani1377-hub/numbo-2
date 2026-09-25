import os
import scrapy
from urllib.parse import urlparse, urljoin
from datetime import datetime
from numbo.items import ContactItem
from numbo.utils.phone import extract_phones
from numbo.utils.category import detect_city, detect_category, extract_emails


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

        if os.path.exists(seeds_file):
            with open(seeds_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if not line.startswith("http"):
                        line = "https://" + line
                    self.start_urls.append(line)
                    domain = urlparse(line).netloc.lower().replace("www.", "")
                    if domain and domain not in self.allowed_domains:
                        self.allowed_domains.append(domain)

        if not self.start_urls:
            self.logger.warning("No seeds found in %s. Add domains to seeds.txt", seeds_file)

    def parse(self, response):
        text = " ".join(response.css("::text").getall())
        title = response.css("title::text").get(default="").strip()

        phones = extract_phones(text)
        emails = extract_emails(text)

        if phones or emails:
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
            item["crawled_at"] = datetime.utcnow().isoformat()
            yield item

        for href in response.css("a::attr(href)").getall():
            full = urljoin(response.url, href)
            parsed = urlparse(full)
            if parsed.scheme not in ("http", "https"):
                continue
            domain = parsed.netloc.lower().replace("www.", "")
            if domain in self.allowed_domains:
                path = parsed.path.lower()
                if any(k in path for k in ["contact", "about", "تماس", "درباره", "ارتباط"]):
                    yield response.follow(full, callback=self.parse, priority=10)
                else:
                    yield response.follow(full, callback=self.parse)
