import re
from typing import List, Set

_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

# High-confidence Iranian mobile and fixed-line patterns only.
# Local numbers must start with 0; international numbers must use +98/0098.
# This prevents prices, SKUs, dates and dimensions from being extracted.
IR_MOBILE = re.compile(
    r"(?<!\d)(?:0(?:9(?:0[1-5]|1[0-9]|2[0-2]|3[0-9]|9[0-9])\d{7})|"
    r"(?:\+?98|0098)9(?:0[1-5]|1[0-9]|2[0-2]|3[0-9]|9[0-9])\d{7})(?!\d)"
)
# Formatted numbers are deliberately strict: only spaces, hyphens and parentheses
# are accepted as separators. Dots are excluded because decimal prices, dimensions
# and coordinates frequently contain them.
FORMATTED_MOBILE = re.compile(
    r"(?<!\d)(?:(?:\+?98|0098)[\s()-]*|0[\s()-]*)9(?:[\s()-]*\d){9}(?!\d)"
)
FORMATTED_LANDLINE = re.compile(
    r"(?<!\d)(?:(?:\+?98|0098)[\s()-]*|0[\s()-]*)"
    r"(?:21|26|25|31|41|51|61|71|81|11|13|17|34|35|38|44|45|54|56|58|74|76|77|83|84|86|87)"
    r"(?:[\s()-]*\d){8}(?!\d)"
)

IR_LANDLINE = re.compile(
    r"(?<!\d)(?:0(?:21|26|25|31|41|51|61|71|81|11|13|17|34|35|38|44|45|54|56|58|74|76|77|83|84|86|87)\d{8}|"
    r"(?:\+?98|0098)(?:21|26|25|31|41|51|61|71|81|11|13|17|34|35|38|44|45|54|56|58|74|76|77|83|84|86|87)\d{8})(?!\d)"
)


def normalize_digits(value: str) -> str:
    return (value or "").translate(_DIGIT_MAP)


def _digits(value: str) -> str:
    return re.sub(r"\D", "", normalize_digits(value))


def normalize_iranian(phone: str) -> str:
    raw = normalize_digits(phone).strip()
    digits = _digits(raw)
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98"):
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return digits
    return raw


def _valid_mobile(value: str) -> bool:
    digits = _digits(value)
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98"):
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits
    return len(digits) == 11 and bool(re.fullmatch(
        r"09(?:0[1-5]|1[0-9]|2[0-2]|3[0-9]|9[0-9])\d{7}", digits
    ))


def _valid_landline(value: str) -> bool:
    digits = _digits(value)
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98"):
        digits = digits[2:]
    if len(digits) == 10:
        digits = "0" + digits
    return len(digits) == 11 and bool(re.fullmatch(
        r"0(?:21|26|25|31|41|51|61|71|81|11|13|17|34|35|38|44|45|54|56|58|74|76|77|83|84|86|87)\d{8}",
        digits,
    ))


def extract_phones(text: str) -> List[str]:
    normalized = normalize_digits(text or "")
    found: Set[str] = set()
    for match in IR_MOBILE.finditer(normalized):
        if _valid_mobile(match.group(0)):
            found.add(normalize_iranian(match.group(0)))
    for match in IR_LANDLINE.finditer(normalized):
        if _valid_landline(match.group(0)):
            found.add(normalize_iranian(match.group(0)))
    for pattern in (FORMATTED_MOBILE, FORMATTED_LANDLINE):
        for match in pattern.finditer(normalized):
            value = match.group(0)
            if _valid_mobile(value) or _valid_landline(value):
                found.add(normalize_iranian(value))
    return sorted(found)
