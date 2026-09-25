from numbo.utils.category import detect_city, detect_category, extract_emails


def test_city_tehran():
    assert detect_city("store in tehran") == "تهران"


def test_category_shop():
    assert detect_category("online shop store", "shop.ir") == "فروشگاه"


def test_email():
    emails = extract_emails("info@example.ir and sales@shop.com")
    assert "info@example.ir" in emails
    assert "sales@shop.com" in emails
