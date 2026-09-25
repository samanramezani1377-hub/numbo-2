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


def test_shorter_rows_get_empty_cells():
    df = pd.DataFrame([
        {"domain": "a.com", "phones": "09120000000"},
        {"domain": "b.com", "phones": "09121111111,09352222222"},
    ])

    result = prepare_export_dataframe(df)

    assert list(result["phone_1"]) == ["09120000000", "09121111111"]
    assert list(result["phone_2"]) == ["", "09352222222"]
