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

from numbo.utils.tech import TECH_ORDER, sort_technologies
from numbo.qualification import qualify_record
from numbo.utils.phone import classify_phone, normalize_iranian

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


def _expand_technologies_fixed(df):
    """Expand technologies into stable columns shared by every exported row."""
    if "technologies" not in df.columns:
        return df

    parsed = []
    discovered = []
    for value in df["technologies"]:
        names = []
        for item in _split_values(value, separator=";"):
            # Stored data may come from older versions with confidence suffixes.
            name = item.split("(", 1)[0].strip()
            if name and name not in names:
                names.append(name)
            if name and name not in discovered:
                discovered.append(name)
        parsed.append(names)

    known = [name for name in TECH_ORDER if name in discovered]
    unknown = sorted(name for name in discovered if name not in set(TECH_ORDER))
    columns = known + unknown

    df = df.drop(columns=["technologies"])
    for index, name in enumerate(columns, start=1):
        df[f"technology_{index}"] = [
            name if name in names else "" for names in parsed
        ]
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


def _unique_values(values):
    result = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        value = str(value).strip()
        if value and value not in result:
            result.append(value)
    return result


def _merge_json_dicts(values):
    merged = {}
    for value in values:
        if isinstance(value, dict):
            data = value
        else:
            try:
                data = json.loads(value) if isinstance(value, str) and value else {}
            except (TypeError, json.JSONDecodeError):
                data = {}
        if not isinstance(data, dict):
            continue
        for key, item in data.items():
            if item not in (None, ""):
                merged.setdefault(str(key), item)
    return merged


def aggregate_contacts_dataframe(df):
    """Aggregate page-level crawl rows into one lead row per domain."""
    if df.empty or "domain" not in df.columns:
        return df.copy()

    rows = []
    for domain, group in df.groupby("domain", sort=False, dropna=False):
        row = {"domain": domain}
        for column in df.columns:
            if column == "domain":
                continue
            values = group[column].tolist()

            if column in {"phones", "emails"}:
                merged = []
                for value in values:
                    merged.extend(_split_values(value))
                row[column] = ",".join(_unique_values(merged))
            elif column == "technologies":
                merged = []
                for value in values:
                    merged.extend(_split_values(value, separator=";"))
                row[column] = "; ".join(_unique_values(merged))
            elif column == "socials":
                row[column] = json.dumps(_merge_json_dicts(values), ensure_ascii=False)
            elif column == "evidence":
                evidence = []
                for value in values:
                    try:
                        item = json.loads(value) if isinstance(value, str) and value else {}
                    except (TypeError, json.JSONDecodeError):
                        item = {}
                    if isinstance(item, dict):
                        evidence.append(item)
                merged = {}
                pages = _unique_values([item.get("page") for item in evidence])
                if pages:
                    merged["pages"] = pages
                field_sources = {}
                for item in evidence:
                    for field, sources in (item.get("field_sources") or {}).items():
                        field_sources.setdefault(field, [])
                        field_sources[field].extend(sources or [])
                for field, sources in field_sources.items():
                    clean = _unique_values(sources)
                    if clean:
                        field_sources[field] = clean
                if field_sources:
                    merged["field_sources"] = field_sources
                for key in ("tel_links", "mailto_links"):
                    total = sum(int(item.get(key) or 0) for item in evidence)
                    if total:
                        merged[key] = total
                row[column] = json.dumps(merged, ensure_ascii=False)
            elif column == "source_url":
                row[column] = ",".join(_unique_values(values))
            elif column in {"address", "business_name", "category", "city"}:
                candidates = _unique_values(values)
                # Prefer meaningful non-empty values; for address, longest is
                # generally the most complete semantic address.
                row[column] = max(candidates, key=len) if candidates else ""
            elif column == "quality_score":
                nums = [float(v) for v in values if v not in (None, "")]
                row[column] = round(max(nums), 2) if nums else 0
            elif column == "crawled_at":
                clean = _unique_values(values)
                row[column] = max(clean) if clean else ""
            elif column == "title":
                clean = _unique_values(values)
                row[column] = clean[0] if clean else ""
            else:
                clean = _unique_values(values)
                row[column] = clean[0] if clean else ""
        rows.append(row)

    return pd.DataFrame(rows, columns=df.columns)


def prepare_export_dataframe(df):
    """Prepare a one-row-per-site export with no multi-value cells."""
    df = df.copy()

    # Contacts: mobile numbers go to number_1, number_2, ... and fixed
    # lines go to tel_1, tel_2, ... . Never mix the two kinds.
    if "phones" in df.columns:
        parsed = df["phones"].apply(_split_values)
        mobiles = parsed.map(lambda items: [
            normalize_iranian(item) for item in items
            if classify_phone(item) == "mobile"
        ])
        landlines = parsed.map(lambda items: [
            normalize_iranian(item) for item in items
            if classify_phone(item) == "landline"
        ])
        df = df.drop(columns=["phones"])
        mobile_width = int(mobiles.map(len).max()) if len(mobiles) else 0
        landline_width = int(landlines.map(len).max()) if len(landlines) else 0
        for index in range(mobile_width):
            df[f"phone_{index + 1}"] = mobiles.map(
                lambda items, i=index: items[i] if i < len(items) else ""
            )
        for index in range(landline_width):
            df[f"tel_{index + 1}"] = landlines.map(
                lambda items, i=index: items[i] if i < len(items) else ""
            )

    df = _expand_column(df, "emails", "email")

    # Technologies use stable dataset-wide positions: a given technology
    # never moves between technology_1, technology_2, ... for different rows.
    df = _expand_technologies_fixed(df)

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
    raw = pd.read_sql_query("SELECT * FROM contacts ORDER BY crawled_at DESC", conn)
    conn.close()
    qualified_rows = []
    for record in raw.to_dict("records"):
        qualified = qualify_record(record)
        if qualified:
            record.update(qualified)
            qualified_rows.append(record)
    df = pd.DataFrame(qualified_rows, columns=raw.columns) if qualified_rows else raw.iloc[0:0].copy()
    df = aggregate_contacts_dataframe(df)

    if df.empty:
        print("No contacts found yet.")
        return

    df = prepare_export_dataframe(df)

    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = os.path.join(OUT_DIR, f"contacts_{ts}.csv")
    xlsx_path = os.path.join(OUT_DIR, f"contacts_{ts}.xlsx")

    for column in [c for c in df.columns if c.startswith("number_") or c.startswith("tel_") or c.startswith("email_")]:
        df[column] = df[column].fillna("").astype(str)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
        ws = writer.sheets["Sheet1"]
        for idx, column in enumerate(df.columns, start=1):
            if column.startswith("number_") or column.startswith("tel_") or column.startswith("email_"):
                for cells in ws.iter_cols(min_col=idx, max_col=idx, min_row=2):
                    for cell in cells:
                        cell.number_format = "@"
                        if cell.value is not None:
                            cell.value = str(cell.value)

    print(f"Exported {len(df)} sites/leads")
    print(f"CSV  → {csv_path}")
    print(f"Excel → {xlsx_path}")


if __name__ == "__main__":
    main()
