#!/usr/bin/env python3
"""
Export contacts from SQLite to CSV and Excel.

Every multi-value field is expanded into separate spreadsheet columns.
One crawled site remains one row.
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
    """Expand social links into one column per network."""
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

        clean = {
            str(k).strip(): str(v).strip()
            for k, v in data.items()
            if str(v).strip()
        }
        parsed.append(clean)
        for key in clean:
            if key not in keys:
                keys.append(key)

    df = df.drop(columns=["socials"])
    for key in keys:
        safe_key = "".join(
            char if char.isalnum() or char == "_" else "_"
            for char in key.lower()
        ).strip("_") or "unknown"
        df[f"social_{safe_key}"] = [item.get(key, "") for item in parsed]
    return df


def _expand_evidence(df):
    """Expand evidence JSON and its list values into independent columns."""
    if "evidence" not in df.columns:
        return df

    parsed = []
    for value in df["evidence"]:
        try:
            data = json.loads(value) if isinstance(value, str) and value else {}
        except (TypeError, json.JSONDecodeError):
            data = {}
        parsed.append(data if isinstance(data, dict) else {})

    df = df.drop(columns=["evidence"])

    # Scalar evidence stays one cell; list evidence gets numbered cells.
    for key in sorted({str(k) for item in parsed for k in item}):
        values = [item.get(key) for item in parsed]
        if any(isinstance(value, (list, tuple)) for value in values):
            lists = [_split_values(value) for value in values]
            width = max((len(items) for items in lists), default=0)
            for index in range(width):
                df[f"evidence_{key}_{index + 1}"] = [
                    items[index] if index < len(items) else ""
                    for items in lists
                ]
        else:
            df[f"evidence_{key}"] = [
                "" if value is None else str(value) for value in values
            ]

    return df


def prepare_export_dataframe(df):
    """Prepare a one-row-per-site export with no multi-value cells."""
    df = df.copy()

    # Contacts: each phone/email has its own cell.
    df = _expand_column(df, "phones", "phone")
    df = _expand_column(df, "emails", "email")

    # Site technology/structure: each detected technology has its own cell.
    df = _expand_column(df, "technologies", "technology", separator=";")

    # Social networks: one column per network.
    df = _expand_socials(df)

    # Crawl/evidence details: list-valued evidence is also separated.
    df = _expand_evidence(df)

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
