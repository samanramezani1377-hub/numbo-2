from numbo.utils.category import detect_city, detect_category, extract_emails

def test_city_uses_strongest_match():
    assert detect_city("دفتر تهران تهران") == "تهران"

def test_category():
    assert detect_category("فروشگاه اینترنتی خرید محصول") == "فروشگاه"

def test_email_normalized_and_validated():
    assert extract_emails("Email: TEST@example.com, bad@, foo..bar@example.com") == ["test@example.com"]
