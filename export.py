#!/usr/bin/env python3
"""
Export contacts from SQLite to CSV and Excel.
"""
import os
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = os.path.join("data", "numbo.db")
OUT_DIR = "data"

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
