import re
from typing import Optional, Tuple

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
    "فروشگاه": ["فروشگاه", "shop", "store", "خرید"],
    "خدمات": ["خدمات", "service", "تعمیر"],
    "رستوران": ["رستوران", "restaurant", "کافه", "cafe"],
    "پزشکی": ["پزشک", "کلینیک", "بیمارستان", "clinic", "doctor"],
    "املاک": ["املاک", "ملک", "آپارتمان", "real estate"],
    "آموزش": ["آموزش", "آموزشگاه", "مدرسه", "university", "institute"],
    "فناوری": ["نرم‌افزار", "برنامه", "سایت", "اپلیکیشن", "it", "software"],
    "حمل و نقل": ["باربری", "حمل", "ارسال", "پیک"],
}

def detect_city(text: str) -> Optional[str]:
    text_lower = text.lower()
    for city, kws in CITY_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in text_lower:
                return city
    return None

def detect_category(text: str, domain: str = "") -> str:
    combined = (text + " " + domain).lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in combined:
                return cat
    return "عمومی"

def extract_emails(text: str) -> list:
    pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    return sorted(set(pattern.findall(text)))
