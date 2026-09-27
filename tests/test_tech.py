from numbo.utils.tech import detect_technologies, format_technologies


def test_woocommerce_strong_signature():
    result = detect_technologies("<script src='/wp-content/plugins/woocommerce/assets/js/wc-add-to-cart.js'></script>")
    names = {x["name"] for x in result}
    assert "WooCommerce" in names


def test_weak_word_not_enough():
    result = detect_technologies("<html><body>wordpress training course</body></html>")
    assert "WordPress" not in {x["name"] for x in result}


def test_nextjs_signature():
    result = detect_technologies("<script src='/_next/static/chunks/app.js'></script>")
    assert "Next.js" in {x["name"] for x in result}


def test_technology_format_is_clean_and_stable():
    result = detect_technologies(
        "<html><script src='/wp-content/plugins/woocommerce/assets/js/wc-add-to-cart.js'></script>"
        "<script src='/_next/static/chunks/app.js'></script></html>"
    )
    formatted = format_technologies(result)
    assert "(" not in formatted
    assert formatted.split("; ") == ["WordPress", "WooCommerce", "Next.js"]


def test_wordpress_generator_signature():
    result = detect_technologies(
        '<meta name="generator" content="WordPress 6.8.2">'
    )
    assert "WordPress" in {x["name"] for x in result}


def test_woocommerce_header_signature():
    result = detect_technologies(
        "<html><body>Store</body></html>",
        headers={"X-Powered-By": "WooCommerce"},
    )
    assert "WooCommerce" in {x["name"] for x in result}


def test_wordpress_api_link_signature():
    result = detect_technologies(
        '<link rel="https://api.w.org/" href="https://example.ir/wp-json/">'
    )
    assert "WordPress" in {x["name"] for x in result}
