from numbo.utils.phone import extract_phones, normalize_iranian


def test_mobile_09():
    phones = extract_phones("contact 09121234567")
    assert "09121234567" in phones


def test_mobile_plus98():
    phones = extract_phones("call +989121234567 now")
    assert "09121234567" in phones


def test_normalize():
    assert normalize_iranian("+989351112233") == "09351112233"
    assert normalize_iranian("989121234567") == "09121234567"
