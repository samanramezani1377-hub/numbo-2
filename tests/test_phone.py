from numbo.utils.phone import extract_phones, normalize_iranian


def test_mobile_09():
    phones = extract_phones("contact 09121234567")
    assert "09121234567" in phones


def test_mobile_plus98():
    phones = extract_phones("call +989121234567 now")
    assert "09121234567" in phones


def test_persian_mobile():
    phones = extract_phones("تماس: ۰۹۱۲۱۲۳۴۵۶۷")
    assert "09121234567" in phones


def test_landline():
    phones = extract_phones("دفتر: 02112345678")
    assert "02112345678" in phones


def test_normalize():
    assert normalize_iranian("+989351112233") == "09351112233"
    assert normalize_iranian("989121234567") == "09121234567"


def test_reject_fake_numbers():
    text = "SKU 1788017469 price 987654321 size 120x200 code +0152-0153"
    assert extract_phones(text) == []


def test_reject_partial_mobile():
    assert extract_phones("1234567890") == []


def test_spider_like_mailto_and_tel_inputs():
    from numbo.utils.phone import extract_phones
    from numbo.utils.category import extract_emails
    assert "09121234567" in extract_phones("+989121234567")
    assert extract_emails("Sales@Example.ir") == ["sales@example.ir"]


def test_formatted_iranian_phones():
    assert "09121234567" in extract_phones("موبایل: 0912-123-4567")
    assert "02112345678" in extract_phones("دفتر: 021 1234 5678")
    assert "09121234567" in extract_phones("موبایل: +98 912 123 4567")


def test_reject_decimal_and_measurement_noise():
    text = "قیمت 9813 69.4127 35 و امتیاز 9834 0.75 2.9834 و ابعاد 120.50x200.00"
    assert extract_phones(text) == []


def test_reject_arbitrary_spaced_digits():
    text = "مقادیر 1234 5678 9012 و 98348 91.4944 6"
    assert extract_phones(text) == []


def test_keep_strict_formatted_phones():
    text = "موبایل 0912-123-4567 و دفتر 021 1234 5678 و +98 912 123 4567"
    assert extract_phones(text) == ["02112345678", "09121234567"]
