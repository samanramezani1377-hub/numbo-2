"""Technology detection with evidence-weighted confidence."""
import re
from typing import Dict, List, Tuple

RULES: Dict[str, List[Tuple[str, float, str]]] = {
    "WordPress": [(r"wp-content", .95, "html"), (r"wp-includes", .95, "html"),
                  (r"/wp-json/", .9, "html"), (r"wordpress", .75, "html"),
                  (r"wp-emoji", .7, "html"), (r"wp-block", .65, "html")],
    "WooCommerce": [(r"woocommerce", 1.0, "html"), (r"wc-block", .9, "html"),
                    (r"wc-add-to-cart", .95, "html"), (r"woocommerce-product", .9, "html"),
                    (r"/wc-api/", .8, "html")],
    "Joomla": [(r"/media/jui/", .9, "html"), (r"/components/com_", .9, "html"), (r"joomla", .75, "html")],
    "Drupal": [(r"drupal.settings", .95, "html"), (r"/sites/default/files", .85, "html"), (r"drupal", .7, "html")],
    "Shopify": [(r"cdn.shopify.com", .98, "html"), (r"shopify.theme", .95, "html"),
                (r"shopify", .75, "html"), (r"myshopify.com", .9, "url")],
    "Magento": [(r"mage.cookies", .95, "html"), (r"/static/version", .85, "html"), (r"magento", .7, "html")],
    "PrestaShop": [(r"prestashop", .9, "html")],
    "OpenCart": [(r"catalog/view/theme", .9, "html"), (r"opencart", .8, "html")],
    "Laravel": [(r"laravel_session", .95, "header"), (r"xsrf-token", .7, "header"), (r"laravel", .55, "html")],
    "Next.js": [(r"_next/static", .98, "html"), (r"__NEXT_DATA__", .98, "html")],
    "React": [(r"data-reactroot", .85, "html"), (r"__REACT", .65, "html")],
    "Vue.js": [(r"data-v-[a-z0-9]", .75, "html")],
    "Angular": [(r"ng-version", .95, "html")],
    "Bootstrap": [(r"bootstrap", .65, "html"), (r"bootstrap.min.css", .9, "link")],
    "jQuery": [(r"jquery.min.js", .9, "script"), (r"jquery", .55, "script")],
    "Cloudflare": [(r"cloudflare", .75, "html"), (r"cf-ray", .98, "header")],
    "Google Analytics": [(r"google-analytics.com", .9, "html"), (r"googletagmanager.com", .7, "html"), (r"gtag\(", .75, "html")],
    "Google Tag Manager": [(r"googletagmanager.com", .95, "html"), (r"GTM-[A-Z0-9]+", .9, "html")],
}

def detect_technologies(html: str = "", url: str = "", headers: dict = None) -> List[Dict[str, object]]:
    headers = headers or {}
    html_lower = html or ""
    url_lower = url or ""
    header_str = " ".join(f"{k}:{v}" for k, v in headers.items()).lower()
    results = []

    for tech, rules in RULES.items():
        hits = []
        for pattern, weight, where in rules:
            hay = html_lower if where == "html" else header_str if where == "header" else url_lower
            if re.search(pattern, hay, re.I):
                hits.append((pattern, weight, where))

        if not hits:
            continue

        total = sum(w for _, w, _ in rules)
        score = sum(w for _, w, _ in hits)
        strong = sum(1 for _, w, _ in hits if w >= 0.85)
        sources = {where for _, _, where in hits}
        confidence = min(1.0, score / max(total * 0.55, 0.01))

        # One strong, technology-specific signature is enough; weak generic
        # keywords need corroboration to avoid false positives.
        specific_single = strong >= 1 and max(w for _, w, _ in hits) >= 0.9
        corroborated = len(hits) >= 2 or len(sources) >= 2
        if (specific_single or corroborated) and confidence >= 0.35:
            results.append({
                "name": tech,
                "confidence": round(confidence, 2),
                "evidence": [p[:60] for p, _, _ in hits[:6]],
                "evidence_count": len(hits),
            })

    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results

def format_technologies(techs: List[Dict]) -> str:
    return "; ".join(f"{t['name']}({t['confidence']})" for t in (techs or []))
