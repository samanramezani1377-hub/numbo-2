from numbo.utils.category import detect_city, detect_category, extract_emails

def test_city_uses_strongest_match():
    assert detect_city("دفتر تهران تهران") == "تهران"

def test_category():
    assert detect_category("فروشگاه اینترنتی خرید محصول") == "فروشگاه"

def test_email_normalized_and_validated():
    assert extract_emails("Email: TEST@example.com, bad@, foo..bar@example.com") == ["test@example.com"]


def test_extract_address_from_semantic_markup():
    from scrapy.http import HtmlResponse, Request
    from numbo.utils.category import extract_address

    response = HtmlResponse(
        url="https://example.ir/contact",
        request=Request("https://example.ir/contact"),
        body="""<html><body><address>تهران، خیابان ولیعصر، پلاک ۱۲۳</address></body></html>""",
        encoding="utf-8",
    )
    assert extract_address(response, "آدرس: تهران، خیابان ولیعصر، پلاک ۱۲۳") == "تهران، خیابان ولیعصر، پلاک ۱۲۳"


def test_extract_address_from_jsonld():
    from scrapy.http import HtmlResponse, Request
    from numbo.utils.category import extract_address

    response = HtmlResponse(
        url="https://example.ir/",
        request=Request("https://example.ir/"),
        body=b'''<script type="application/ld+json">{"@type":"LocalBusiness","address":{"@type":"PostalAddress","streetAddress":"Isfahan, Chaharbagh, 10"}}</script>''',
        encoding="utf-8",
    )
    assert extract_address(response, "") == "Isfahan, Chaharbagh, 10"
