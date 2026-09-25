#!/usr/bin/env python3
"""
Export contacts from SQLite to CSV and Excel.

Multi-value contact fields are expanded into separate columns so that
multiple phones/emails never end up in a single spreadsheet cell.
"""
import json
import os
import sqlite3
from datetime import datetime

import pandas as pd

DB_PATH = os.path.join("data", "numbo.db")
OUT_DIR = "data"


def _split_values(value, separator=","):
    """Return clean, unique values from a stored multi-value field."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []

    values = value if isinstance(value, list) else str(value).split(separator)

    result = []
    for item in values:
        item = str(item).strip()
        if item and item not in result:
            result.append(item)
    return result


def _expand_column(df, source, prefix, separator=","):
    """Replace one multi-value column with numbered columns."""
    if source not in df.columns:
        return df

    values = df[source].apply(lambda value: _split_values(value, separator))
    width = int(values.map(len).max()) if len(values) else 0

    df = df.drop(columns=[source])
    for index in range(width):
        df[f"{prefix}_{index + 1}"] = values.map(
            lambda items, i=index: items[i] if i < len(items) else ""
        )
    return df


def _expand_socials(df):
    """Expand the stored social-links JSON object into one column per network."""
    if "socials" not in df.columns:
        return df

    parsed = []
    keys = []
    for value in df["socials"]:
        try:
            data = json.loads(value) if isinstance(value, str) and value else {}
        except (TypeError, json.JSONDecodeError):
            data = {}

        if not isinstance(data, dict):
            data = {}

        clean = {str(k).strip(): str(v).strip() for k, v in data.items() if str(v).strip()}
        parsed.append(clean)
        for key in clean:
            if key not in keys:
                keys.append(key)

    df = df.drop(columns=["socials"])
    for key in keys:
        safe_key = "".join(
            char if char.isalnum() or char == "_" else "_" for char in key.lower()
        ).strip("_") or "unknown"
        df[f"social_{safe_key}"] = [item.get(key, "") for item in parsed]
    return df


def prepare_export_dataframe(df):
    """Prepare contact data for spreadsheet export without multi-values in one cell."""
    df = df.copy()

    # One site remains one row; each phone/email gets its own cell/column.
    df = _expand_column(df, "phones", "phone")
    df = _expand_column(df, "emails", "email")

    # Technologies are stored as: Name(0.95); Name(0.80)
    df = _expand_column(df, "technologies", "technology", separator=";")

    # Social networks are stored as JSON and become social_<network> columns.
    df = _expand_socials(df)

    return df


def main():
    if not os.path.exists(DB_PATH):
        print("No database found. Run the crawler first.")
        return

    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM contacts ORDER BY crawled_at DESC", conn)
    conn.close()

    if df.empty:
        print("No contacts found yet.")
        return

    df = prepare_export_dataframe(df)

    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = os.path.join(OUT_DIR, f"contacts_{ts}.csv")
    xlsx_path = os.path.join(OUT_DIR, f"contacts_{ts}.xlsx")

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_excel(xlsx_path, index=False)

    print(f"Exported {len(df)} contacts")
    print(f"CSV  → {csv_path}")
    print(f"Excel → {xlsx_path}")


if __name__ == "__main__":
    main()
