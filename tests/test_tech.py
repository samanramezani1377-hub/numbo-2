from numbo.utils.tech import detect_technologies


def test_wordpress():
    html = '<html><head><meta name="generator" content="WordPress 6.4"></head>'
    html += '<link href="/wp-content/themes/x/style.css"><script src="/wp-includes/js/wp-emoji.js"></script>'
    names = [t["name"] for t in detect_technologies(html=html, url="https://shop.ir")]
    assert "WordPress" in names


def test_woocommerce():
    html = '<div class="woocommerce"><button class="wc-add-to-cart">buy</button></div>'
    html += '<script src="/wp-content/plugins/woocommerce/assets/js/woocommerce.js"></script>'
    names = [t["name"] for t in detect_technologies(html=html)]
    assert "WooCommerce" in names


def test_nextjs():
    html = '<script src="/_next/static/chunks/main.js"></script><script id="__NEXT_DATA__" type="application/json">{}</script>'
    names = [t["name"] for t in detect_technologies(html=html)]
    assert "Next.js" in names
