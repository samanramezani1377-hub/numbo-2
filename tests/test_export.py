import json

import pandas as pd

from export import prepare_export_dataframe


def test_multi_value_fields_are_exported_to_separate_columns():
    df = pd.DataFrame([
        {
            "domain": "example.com",
            "phones": "09120000000, 09350000000, 02112345678",
            "emails": "one@example.com,two@example.com",
            "technologies": "WordPress(0.95); WooCommerce(1.0)",
            "socials": json.dumps({
                "telegram": "https://t.me/example",
                "instagram": "https://instagram.com/example",
            }),
            "evidence": json.dumps({
                "page": "https://example.com/contact",
                "tel_links": 3,
                "socials": ["telegram", "instagram"],
                "technologies": ["WordPress", "WooCommerce"],
            }),
        }
    ])

    result = prepare_export_dataframe(df)

    assert "phones" not in result.columns
    assert result.loc[0, "phone_1"] == "09120000000"
    assert result.loc[0, "phone_2"] == "09350000000"
    assert result.loc[0, "phone_3"] == "02112345678"

    assert "emails" not in result.columns
    assert result.loc[0, "email_1"] == "one@example.com"
    assert result.loc[0, "email_2"] == "two@example.com"

    assert result.loc[0, "technology_1"] == "WordPress(0.95)"
    assert result.loc[0, "technology_2"] == "WooCommerce(1.0)"

    assert result.loc[0, "social_telegram"] == "https://t.me/example"
    assert result.loc[0, "social_instagram"] == "https://instagram.com/example"

    assert result.loc[0, "evidence_page"] == "https://example.com/contact"
    assert result.loc[0, "evidence_tel_links"] == "3"
    assert result.loc[0, "evidence_socials_1"] == "telegram"
    assert result.loc[0, "evidence_socials_2"] == "instagram"
    assert result.loc[0, "evidence_technologies_1"] == "WordPress"
    assert result.loc[0, "evidence_technologies_2"] == "WooCommerce"
    assert "evidence" not in result.columns


def test_shorter_rows_get_empty_cells():
    df = pd.DataFrame([
        {"domain": "a.com", "phones": "09120000000"},
        {"domain": "b.com", "phones": "09121111111,09352222222"},
    ])

    result = prepare_export_dataframe(df)

    assert list(result["phone_1"]) == ["09120000000", "09121111111"]
    assert list(result["phone_2"]) == ["", "09352222222"]


def test_aggregate_contacts_merges_pages_into_one_site():
    from export import aggregate_contacts_dataframe

    df = pd.DataFrame([
        {
            "source_url": "https://example.ir/",
            "domain": "example.ir",
            "phones": "09120000000",
            "emails": "one@example.ir",
            "address": "",
            "business_name": "Example",
            "category": "فروشگاه",
            "city": "تهران",
            "socials": json.dumps({"instagram": "https://instagram.com/example"}),
            "technologies": "WordPress(0.9)",
            "crawled_at": "2026-09-25T10:00:00",
            "quality_score": 0.6,
            "evidence": json.dumps({"page": "https://example.ir/"}),
        },
        {
            "source_url": "https://example.ir/contact",
            "domain": "example.ir",
            "phones": "09350000000",
            "emails": "two@example.ir",
            "address": "تهران، خیابان نمونه، پلاک ۱۰",
            "business_name": "Example",
            "category": "فروشگاه",
            "city": "تهران",
            "socials": json.dumps({"telegram": "https://t.me/example"}),
            "technologies": "WooCommerce(1.0)",
            "crawled_at": "2026-09-25T10:01:00",
            "quality_score": 0.8,
            "evidence": json.dumps({
                "page": "https://example.ir/contact",
                "field_sources": {"address": ["https://example.ir/contact"]},
            }),
        },
    ])

    result = aggregate_contacts_dataframe(df)
    assert len(result) == 1
    row = result.iloc[0]
    assert "09120000000" in row["phones"]
    assert "09350000000" in row["phones"]
    assert "one@example.ir" in row["emails"]
    assert "two@example.ir" in row["emails"]
    assert row["address"] == "تهران، خیابان نمونه، پلاک ۱۰"
    assert "WordPress(0.9)" in row["technologies"]
    assert "WooCommerce(1.0)" in row["technologies"]
    assert "telegram" in row["socials"]
    assert "contact" in row["source_url"]
