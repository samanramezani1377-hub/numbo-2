from numbo.utils.tech import detect_technologies

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
