import re
from typing import List, Set

# Iranian mobile: 09xxxxxxxxx or +989xxxxxxxxx or 989xxxxxxxxx
IR_MOBILE = re.compile(
    r"(?:\+98|98|0)?9(?:0[1-5]|1[0-9]|2[0-2]|3[0-9]|9[0-9])\d{7}"
)

# Iranian landline (common city codes) - simplified
IR_LANDLINE = re.compile(
    r"(?:\+98|98|0)?(?:21|26|25|31|41|51|61|71|81|11|13|17|34|35|38|44|45|54|56|58|61|71|74|76|77|81|83|84|86|87)\d{7,8}"
)

# General international phone (fallback)
GENERAL_PHONE = re.compile(
    r"(?:\+\d{1,3}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{3,4}(?:[\s\-]?\d{2,4})?"
)

def normalize_iranian(phone: str) -> str:
    """Normalize to 09xxxxxxxxx format when possible."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("98") and len(digits) >= 12:
        digits = "0" + digits[2:]
    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    if len(digits) == 11 and digits.startswith("09"):
        return digits
    return phone.strip()

def extract_phones(text: str) -> List[str]:
    found: Set[str] = set()
    for match in IR_MOBILE.finditer(text):
        norm = normalize_iranian(match.group(0))
        if len(re.sub(r"\D", "", norm)) >= 10:
            found.add(norm)
    for match in IR_LANDLINE.finditer(text):
        norm = normalize_iranian(match.group(0))
        found.add(norm)
    # fallback general (less priority)
    if not found:
        for match in GENERAL_PHONE.finditer(text):
            candidate = match.group(0).strip()
            if len(re.sub(r"\D", "", candidate)) >= 8:
                found.add(candidate)
    return sorted(found)
