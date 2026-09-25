#!/usr/bin/env python3
"""
Numbo-2 Web UI
رابط کاربری مدیریت کراولر
"""
import os
import sys
import sqlite3
import subprocess
import signal
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn

# مسیر ریشه پروژه
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "numbo.db"
SEEDS_PATH = BASE_DIR / "seeds.txt"
SETTINGS_PATH = BASE_DIR / "numbo" / "settings.py"
PID_FILE = DATA_DIR / "crawler.pid"
LOG_FILE = BASE_DIR / "numbo.log"

app = FastAPI(title="Numbo-2 Control Panel")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

os.makedirs(DATA_DIR, exist_ok=True)


def get_db():
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def is_crawler_running() -> bool:
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # check if process exists
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)
        return False


def get_stats():
    conn = get_db()
    if not conn:
        return {"total": 0, "phones": 0, "emails": 0, "wordpress": 0, "woocommerce": 0, "cities": 0}
    try:
        total = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        phones = conn.execute("SELECT COUNT(*) FROM contacts WHERE phones IS NOT NULL AND phones != ''").fetchone()[0]
        emails = conn.execute("SELECT COUNT(*) FROM contacts WHERE emails IS NOT NULL AND emails != ''").fetchone()[0]
        wordpress = conn.execute("SELECT COUNT(*) FROM contacts WHERE technologies LIKE '%WordPress%'").fetchone()[0]
        woocommerce = conn.execute("SELECT COUNT(*) FROM contacts WHERE technologies LIKE '%WooCommerce%'").fetchone()[0]
        cities = conn.execute("SELECT COUNT(DISTINCT city) FROM contacts WHERE city IS NOT NULL AND city != ''").fetchone()[0]
        return {
            "total": total,
            "phones": phones,
            "emails": emails,
            "wordpress": wordpress,
            "woocommerce": woocommerce,
            "cities": cities,
        }
    finally:
        conn.close()


def read_seeds() -> str:
    if SEEDS_PATH.exists():
        return SEEDS_PATH.read_text(encoding="utf-8")
    return ""


def read_allowed_tlds() -> str:
    if not SETTINGS_PATH.exists():
        return ".ir"
    content = SETTINGS_PATH.read_text(encoding="utf-8")
    for line in content.splitlines():
        if line.strip().startswith("ALLOWED_TLDS"):
            # ساده استخراج
            if "[]" in line:
                return ""
            import re
            matches = re.findall(r'["'](\.[^"']+)["']', line)
            return ",".join(matches) if matches else ".ir"
    return ".ir"


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    stats = get_stats()
    running = is_crawler_running()
    seeds = read_seeds()
    tlds = read_allowed_tlds()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "stats": stats,
        "running": running,
        "seeds": seeds,
        "tlds": tlds,
    })


@app.post("/start")
async def start_crawler():
    if is_crawler_running():
        return RedirectResponse("/", status_code=303)
    # start in background
    proc = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "run.py")],
        cwd=str(BASE_DIR),
        stdout=open(LOG_FILE, "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid))
    return RedirectResponse("/", status_code=303)


@app.post("/stop")
async def stop_crawler():
    if not is_crawler_running():
        return RedirectResponse("/", status_code=303)
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    except Exception:
        pass
    PID_FILE.unlink(missing_ok=True)
    return RedirectResponse("/", status_code=303)


@app.post("/seeds")
async def save_seeds(seeds: str = Form(...)):
    SEEDS_PATH.write_text(seeds.strip() + "\n", encoding="utf-8")
    return RedirectResponse("/", status_code=303)


@app.post("/tlds")
async def save_tlds(tlds: str = Form(...)):
    tlds_clean = [t.strip() for t in tlds.split(",") if t.strip()]
    if not tlds_clean:
        tlds_list = "[]"
    else:
        tlds_list = "[" + ", ".join(f'"{t}"' for t in tlds_clean) + "]"

    content = SETTINGS_PATH.read_text(encoding="utf-8")
    import re
    new_content = re.sub(
        r"ALLOWED_TLDS\s*=\s*\[.*?\]",
        f"ALLOWED_TLDS = {tlds_list}",
        content,
        flags=re.DOTALL,
    )
    SETTINGS_PATH.write_text(new_content, encoding="utf-8")
    return RedirectResponse("/", status_code=303)


@app.get("/contacts")
async def list_contacts(
    request: Request,
    q: Optional[str] = None,
    tech: Optional[str] = None,
    city: Optional[str] = None,
    page: int = 1,
):
    conn = get_db()
    if not conn:
        return templates.TemplateResponse("contacts.html", {
            "request": request,
            "rows": [],
            "page": 1,
            "total_pages": 0,
            "q": q or "",
            "tech": tech or "",
            "city": city or "",
        })

    per_page = 50
    offset = (page - 1) * per_page
    where = []
    params = []

    if q:
        where.append("(domain LIKE ? OR phones LIKE ? OR emails LIKE ? OR business_name LIKE ?)")
        params.extend([f"%{q}%"] * 4)
    if tech:
        where.append("technologies LIKE ?")
        params.append(f"%{tech}%")
    if city:
        where.append("city = ?")
        params.append(city)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = conn.execute(f"SELECT COUNT(*) FROM contacts {where_sql}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM contacts {where_sql} ORDER BY crawled_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()
    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)

    return templates.TemplateResponse("contacts.html", {
        "request": request,
        "rows": rows,
        "page": page,
        "total_pages": total_pages,
        "q": q or "",
        "tech": tech or "",
        "city": city or "",
        "total": total,
    })


@app.get("/export")
async def export_data():
    from export import main as do_export
    do_export()
    # آخرین فایل excel را پیدا کن
    files = sorted(DATA_DIR.glob("contacts_*.xlsx"), key=os.path.getmtime, reverse=True)
    if files:
        return FileResponse(files[0], filename=files[0].name)
    return JSONResponse({"error": "No data to export"})


@app.get("/api/stats")
async def api_stats():
    return get_stats() | {"running": is_crawler_running()}


@app.get("/logs")
async def view_logs(request: Request):
    content = ""
    if LOG_FILE.exists():
        # آخرین ۱۰۰ خط
        lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
        content = "\n".join(lines[-100:])
    return templates.TemplateResponse("logs.html", {"request": request, "logs": content})


if __name__ == "__main__":
    uvicorn.run("ui.app:app", host="0.0.0.0", port=8080, reload=False)
