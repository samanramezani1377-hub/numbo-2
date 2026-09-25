import re
from typing import Optional
from urllib.parse import urlparse

CITY_KEYWORDS = {
    "تهران": ["تهران", "tehran"],
    "اصفهان": ["اصفهان", "isfahan", "esfahan"],
    "مشهد": ["مشهد", "mashhad"],
    "شیراز": ["شیراز", "shiraz"],
    "تبریز": ["تبریز", "tabriz"],
    "کرج": ["کرج", "karaj"],
    "اهواز": ["اهواز", "ahvaz"],
    "قم": ["قم", "qom"],
    "کرمان": ["کرمان", "kerman"],
    "رشت": ["رشت", "rasht"],
    "همدان": ["همدان", "hamedan"],
    "یزد": ["یزد", "yazd"],
    "ارومیه": ["ارومیه", "urmia"],
    "کرمانشاه": ["کرمانشاه", "kermanshah"],
    "زاهدان": ["زاهدان", "zahedan"],
}

CATEGORY_KEYWORDS = {
    "فروشگاه": ["فروشگاه", "shop", "store", "خرید", "فروش"],
    "خدمات": ["خدمات", "service", "تعمیر", "مشاوره"],
    "رستوران": ["رستوران", "restaurant", "کافه", "cafe"],
    "پزشکی": ["پزشک", "کلینیک", "بیمارستان", "clinic", "doctor", "درمان"],
    "املاک": ["املاک", "ملک", "آپارتمان", "real estate", "مسکن"],
    "آموزش": ["آموزش", "آموزشگاه", "مدرسه", "university", "institute", "course"],
    "فناوری": ["نرم‌افزار", "نرم افزار", "برنامه", "سایت", "اپلیکیشن", "it", "software", "technology"],
    "حمل و نقل": ["باربری", "حمل", "ارسال", "پیک", "transport"],
}

def _norm(text: str) -> str:
    return (text or "").replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").lower()

def detect_city(text: str) -> Optional[str]:
    text_lower = _norm(text)
    hits = [(city, sum(1 for kw in kws if kw.lower() in text_lower))
            for city, kws in CITY_KEYWORDS.items()]
    hits = [(city, n) for city, n in hits if n]
    return max(hits, key=lambda x: x[1])[0] if hits else None

def detect_category(text: str, domain: str = "") -> str:
    combined = _norm(text + " " + domain)
    scores = []
    for cat, kws in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in kws if kw.lower() in combined)
        if score:
            scores.append((cat, score))
    return max(scores, key=lambda x: x[1])[0] if scores else "عمومی"

def extract_emails(text: str) -> list:
    if not text:
        return []
    text = text.replace("\u200b", "").replace("\u200c", "")
    pattern = re.compile(r"(?<![\w.+-])([a-zA-Z0-9][a-zA-Z0-9._%+\-]{0,63}@[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z]{2,63})+)(?![\w.-])")
    out = set()
    for value in pattern.findall(text):
        value = value.strip(".,;:()[]{}<>").lower()
        if ".." in value or value.startswith(".") or value.endswith("."):
            continue
        local, _, domain = value.rpartition("@")
        if local and domain and "." in domain and len(value) <= 254:
            out.add(value)
    return sorted(out)

def extract_socials(response):
    """Return normalized social profile URLs from anchors and social meta tags."""
    hosts = {
        "instagram": ("instagram.com",),
        "telegram": ("t.me", "telegram.me", "telegram.dog"),
        "linkedin": ("linkedin.com",),
        "twitter": ("twitter.com", "x.com"),
        "facebook": ("facebook.com", "fb.com"),
        "youtube": ("youtube.com", "youtu.be"),
    }
    found = {}
    hrefs = response.css("a::attr(href), link::attr(href)").getall()
    for raw in hrefs:
        raw = (raw or "").strip()
        if not raw:
            continue
        if raw.startswith("//"):
            raw = "https:" + raw
        elif raw.startswith("/"):
            raw = response.urljoin(raw)
        elif raw.startswith(("mailto:", "tel:", "javascript:")):
            continue
        elif not raw.startswith(("http://", "https://")):
            raw = response.urljoin(raw)
        try:
            parsed = urlparse(raw)
        except ValueError:
            continue
        host = (parsed.hostname or "").lower().removeprefix("www.")
        for platform, domains in hosts.items():
            if host == platform + ".com" or any(host == d or host.endswith("." + d) for d in domains):
                clean = f"https://{host}{parsed.path or ''}"
                if parsed.query:
                    clean += "?" + parsed.query
                found.setdefault(platform, clean)
                break
    return found

def extract_business_name(response, domain: str) -> str:
    """Prefer structured metadata and branding over arbitrary title splitting."""
    for selector in [
        'meta[property="og:site_name"]::attr(content)',
        'meta[name="application-name"]::attr(content)',
        'meta[itemprop="name"]::attr(content)',
    ]:
        value = response.css(selector).get(default="").strip()
        if value and len(value) <= 180:
            return value

    for script in response.css('script[type="application/ld+json"]::text').getall():
        if '"name"' not in script:
            continue
        names = re.findall(r'"name"\s*:\s*"([^"]{2,180})"', script)
        if names:
            return names[0].strip()

    title = response.css("title::text").get(default="").strip()
    if title:
        for sep in (" - ", " | ", " — ", " – "):
            if sep in title:
                candidate = title.split(sep)[0].strip()
                if 2 <= len(candidate) <= 180:
                    return candidate
        return title[:180]
    return domain
