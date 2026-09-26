import re
from urllib.parse import urlparse
from numbo.utils.phone import classify_phone, normalize_iranian

PLATFORM_HOSTS = {"google.com","googleusercontent.com","googleapis.com","business.google.com",
"developers.cafebazaar.ir","cafebazaar.ir","developer.myket.ir","myket.ir","ble.ir",
"t.me","telegram.me","telegram.dog","instagram.com","facebook.com","linkedin.com",
"twitter.com","x.com","youtube.com","youtu.be","wa.me","api.whatsapp.com"}
GENERIC_NAMES = {"","website","web site","home","homepage","صفحه اصلی","خانه","سایت",
"وب سایت","وب‌سایت","google","google business","developers","developer","cafe bazaar",
"bazaar","myket"}

def normalize_host(value):
    raw = str(value or "").strip().lower()
    if "://" in raw:
        raw = urlparse(raw).hostname or ""
    return raw.removeprefix("www.").rstrip(".")

def is_blocked_lead_domain(domain):
    host = normalize_host(domain)
    return not host or any(host == item or host.endswith("." + item) for item in PLATFORM_HOSTS)

def clean_business_name(value, domain=""):
    value = re.sub(r"\s+", " ", str(value or "")).strip(" \t\r\n|:-")
    host = normalize_host(domain)
    lowered = value.lower()
    if not value or len(value) < 2 or len(value) > 120:
        return ""
    if lowered in GENERIC_NAMES or lowered == host or lowered.removeprefix("www.") == host:
        return ""
    if "http://" in lowered or "https://" in lowered or "www." in lowered:
        return ""
    if len(value.split()) > 14 or value.count(",") > 4 or value.count("|") > 1:
        return ""
    if len(re.findall(r"[.!?]", value)) > 4:
        return ""
    return value

def normalize_record_phones(values):
    out = []
    for value in values or []:
        normalized = normalize_iranian(str(value))
        if classify_phone(normalized) and normalized not in out:
            out.append(normalized)
    return out

def normalize_record_emails(values):
    out = []
    for value in values or []:
        value = str(value or "").strip().lower()
        if re.fullmatch(r"[a-z0-9][a-z0-9._%+\-]{0,63}@[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?(?:\.[a-z]{2,63})+", value):
            if len(value) <= 254 and value not in out:
                out.append(value)
    return out

def is_qualified_lead(record):
    if is_blocked_lead_domain(record.get("domain")):
        return False
    if normalize_record_phones(record.get("phones")) or normalize_record_emails(record.get("emails")):
        return True
    name = clean_business_name(record.get("business_name"), record.get("domain"))
    address = str(record.get("address") or "").strip()
    category = str(record.get("category") or "").strip()
    return bool(name and (len(address) >= 8 or (category and category != "عمومی")))

def qualify_record(record):
    result = dict(record)
    result["phones"] = normalize_record_phones(result.get("phones"))
    result["emails"] = normalize_record_emails(result.get("emails"))
    result["business_name"] = clean_business_name(result.get("business_name"), result.get("domain"))
    result["address"] = str(result.get("address") or "").strip() or None
    return result if is_qualified_lead(result) else None
