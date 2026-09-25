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
