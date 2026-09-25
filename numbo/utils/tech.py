"""Technology detection for websites."""
import re
from typing import Dict, List, Tuple


RULES: Dict[str, List[Tuple[str, float, str]]] = {
    "WordPress": [
        (r"wp-content", 0.9, "html"),
        (r"wp-includes", 0.9, "html"),
        (r"/wp-json/", 0.8, "html"),
        (r"wordpress", 0.6, "html"),
        (r"name=[\"']generator[\"'][^>]*content=[\"']WordPress", 0.95, "meta"),
        (r"wp-emoji", 0.7, "html"),
        (r"wp-block", 0.6, "html"),
    ],
    "WooCommerce": [
        (r"woocommerce", 0.95, "html"),
        (r"wc-block", 0.8, "html"),
        (r"wc-add-to-cart", 0.85, "html"),
        (r"woocommerce-product", 0.8, "html"),
        (r"/wc-api/", 0.7, "html"),
        (r"woocommerce-js", 0.75, "script"),
    ],
    "Joomla": [
        (r"/media/jui/", 0.8, "html"),
        (r"/components/com_", 0.7, "html"),
        (r"name=[\"']generator[\"'][^>]*content=[\"']Joomla", 0.95, "meta"),
        (r"joomla", 0.5, "html"),
    ],
    "Drupal": [
        (r"Drupal\\.settings", 0.9, "html"),
        (r"/sites/default/files", 0.7, "html"),
        (r"name=[\"']generator[\"'][^>]*content=[\"']Drupal", 0.95, "meta"),
        (r"drupal", 0.5, "html"),
    ],
    "Shopify": [
        (r"cdn\\.shopify\\.com", 0.95, "html"),
        (r"Shopify\\.theme", 0.9, "html"),
        (r"shopify", 0.6, "html"),
        (r"myshopify\\.com", 0.85, "url"),
    ],
    "Magento": [
        (r"Mage\\.Cookies", 0.9, "html"),
        (r"/static/version", 0.7, "html"),
        (r"magento", 0.5, "html"),
    ],
    "PrestaShop": [
        (r"prestashop", 0.9, "html"),
        (r"/modules/", 0.4, "html"),
    ],
    "OpenCart": [
        (r"catalog/view/theme", 0.8, "html"),
        (r"opencart", 0.7, "html"),
    ],
    "Laravel": [
        (r"laravel_session", 0.85, "header"),
        (r"XSRF-TOKEN", 0.6, "header"),
        (r"laravel", 0.4, "html"),
    ],
    "Next.js": [
        (r"_next/static", 0.95, "html"),
        (r"__NEXT_DATA__", 0.95, "html"),
        (r"next/dist", 0.7, "html"),
    ],
    "React": [
        (r"react", 0.5, "script"),
        (r"data-reactroot", 0.8, "html"),
        (r"__REACT", 0.6, "html"),
    ],
    "Vue.js": [
        (r"vue", 0.5, "script"),
        (r"data-v-", 0.6, "html"),
    ],
    "Angular": [
        (r"ng-version", 0.9, "html"),
        (r"angular", 0.5, "script"),
    ],
    "Bootstrap": [
        (r"bootstrap", 0.7, "html"),
        (r"bootstrap\\.min\\.(css|js)", 0.85, "link"),
    ],
    "jQuery": [
        (r"jquery", 0.6, "script"),
        (r"jquery\\.min\\.js", 0.8, "script"),
    ],
    "Cloudflare": [
        (r"cloudflare", 0.7, "html"),
        (r"cf-ray", 0.9, "header"),
        (r"__cfduid", 0.6, "header"),
    ],
    "Google Analytics": [
        (r"google-analytics\\.com|googletagmanager\\.com|gtag\\(", 0.85, "html"),
        (r"UA-\\d+-\\d+|G-[A-Z0-9]+", 0.7, "html"),
    ],
    "Google Tag Manager": [
        (r"googletagmanager\\.com", 0.9, "html"),
        (r"GTM-[A-Z0-9]+", 0.85, "html"),
    ],
}


def detect_technologies(html: str = "", url: str = "", headers: dict = None) -> List[Dict[str, object]]:
    headers = headers or {}
    html_lower = (html or "").lower()
    url_lower = (url or "").lower()

    meta_content = " ".join(
        re.findall(r"<meta[^>]+content=[\"']([^\"']+)[\"']", html or "", re.I)
    ).lower()
    script_srcs = " ".join(
        re.findall(r"<script[^>]+src=[\"']([^\"']+)[\"']", html or "", re.I)
    ).lower()
    link_hrefs = " ".join(
        re.findall(r"<link[^>]+href=[\"']([^\"']+)[\"']", html or "", re.I)
    ).lower()

    header_str = " ".join(f"{k}:{v}".lower() for k, v in headers.items())
    results = []

    for tech, rules in RULES.items():
        score = 0.0
        evidence = []
        max_possible = 0.0
        for pattern, weight, where in rules:
            max_possible += weight
            matched = False
            if where == "html" and re.search(pattern, html_lower, re.I):
                matched = True
            elif where == "meta" and re.search(pattern, meta_content, re.I):
                matched = True
            elif where == "script" and re.search(pattern, script_srcs + html_lower, re.I):
                matched = True
            elif where == "link" and re.search(pattern, link_hrefs, re.I):
                matched = True
            elif where == "header" and re.search(pattern, header_str, re.I):
                matched = True
            elif where == "url" and re.search(pattern, url_lower, re.I):
                matched = True
            if matched:
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
