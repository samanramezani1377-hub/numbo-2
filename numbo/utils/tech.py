"""Technology detection for websites."""
import re
from typing import Dict, List, Tuple

# Keep patterns simple (no nested quotes) so they always compile.
RULES: Dict[str, List[Tuple[str, float, str]]] = {
    "WordPress": [
        (r"wp-content", 0.9, "html"),
        (r"wp-includes", 0.9, "html"),
        (r"/wp-json/", 0.8, "html"),
        (r"wordpress", 0.7, "html"),
        (r"wp-emoji", 0.7, "html"),
        (r"wp-block", 0.6, "html"),
    ],
    "WooCommerce": [
        (r"woocommerce", 0.95, "html"),
        (r"wc-block", 0.8, "html"),
        (r"wc-add-to-cart", 0.85, "html"),
        (r"woocommerce-product", 0.8, "html"),
        (r"/wc-api/", 0.7, "html"),
    ],
    "Joomla": [
        (r"/media/jui/", 0.8, "html"),
        (r"/components/com_", 0.7, "html"),
        (r"joomla", 0.6, "html"),
    ],
    "Drupal": [
        (r"drupal.settings", 0.9, "html"),
        (r"/sites/default/files", 0.7, "html"),
        (r"drupal", 0.5, "html"),
    ],
    "Shopify": [
        (r"cdn.shopify.com", 0.95, "html"),
        (r"shopify.theme", 0.9, "html"),
        (r"shopify", 0.6, "html"),
        (r"myshopify.com", 0.85, "url"),
    ],
    "Magento": [
        (r"mage.cookies", 0.9, "html"),
        (r"/static/version", 0.7, "html"),
        (r"magento", 0.5, "html"),
    ],
    "PrestaShop": [
        (r"prestashop", 0.9, "html"),
    ],
    "OpenCart": [
        (r"catalog/view/theme", 0.8, "html"),
        (r"opencart", 0.7, "html"),
    ],
    "Laravel": [
        (r"laravel_session", 0.85, "header"),
        (r"xsrf-token", 0.6, "header"),
        (r"laravel", 0.4, "html"),
    ],
    "Next.js": [
        (r"_next/static", 0.95, "html"),
        (r"__NEXT_DATA__", 0.95, "html"),
    ],
    "React": [
        (r"data-reactroot", 0.8, "html"),
        (r"__REACT", 0.6, "html"),
    ],
    "Vue.js": [
        (r"data-v-", 0.6, "html"),
    ],
    "Angular": [
        (r"ng-version", 0.9, "html"),
    ],
    "Bootstrap": [
        (r"bootstrap", 0.7, "html"),
        (r"bootstrap.min.css", 0.85, "link"),
    ],
    "jQuery": [
        (r"jquery.min.js", 0.8, "script"),
        (r"jquery", 0.5, "script"),
    ],
    "Cloudflare": [
        (r"cloudflare", 0.7, "html"),
        (r"cf-ray", 0.9, "header"),
    ],
    "Google Analytics": [
        (r"google-analytics.com", 0.85, "html"),
        (r"googletagmanager.com", 0.8, "html"),
        (r"gtag\(", 0.7, "html"),
    ],
    "Google Tag Manager": [
        (r"googletagmanager.com", 0.9, "html"),
        (r"GTM-[A-Z0-9]+", 0.85, "html"),
    ],
}


def detect_technologies(html: str = "", url: str = "", headers: dict = None) -> List[Dict[str, object]]:
    headers = headers or {}
    html_lower = (html or "").lower()
    url_lower = (url or "").lower()
    header_str = " ".join(f"{k}:{v}".lower() for k, v in headers.items())
    results = []

    for tech, rules in RULES.items():
        score = 0.0
        evidence = []
        max_possible = 0.0
        for pattern, weight, where in rules:
            max_possible += weight
            hay = html_lower
            if where == "header":
                hay = header_str
            elif where == "url":
                hay = url_lower
            if re.search(pattern, hay, re.I):
                score += weight
                evidence.append(pattern[:40])
        if score > 0:
            confidence = min(round(score / max(max_possible * 0.6, 0.01), 2), 1.0)
            if confidence >= 0.35:
                results.append({
                    "name": tech,
                    "confidence": confidence,
                    "evidence": evidence[:5],
                })
    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results


def format_technologies(techs: List[Dict]) -> str:
    if not techs:
        return ""
    return "; ".join(f"{t['name']}({t['confidence']})" for t in techs)
