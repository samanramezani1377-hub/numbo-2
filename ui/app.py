#!/usr/bin/env python3
import os
import sys
import sqlite3
import subprocess
import signal
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from numbo.config import load as load_config, save as save_config  # noqa: E402

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "numbo.db"
SEEDS_PATH = BASE_DIR / "seeds.txt"
PID_FILE = DATA_DIR / "crawler.pid"
LOG_FILE = BASE_DIR / "numbo.log"

cfg0 = load_config()
SECRET = os.getenv("NUMBO_SECRET") or cfg0.get("secret") or "numbo-dev-secret"
PANEL_PASSWORD = os.getenv("NUMBO_PANEL_PASSWORD") or cfg0.get("panel_password") or ""

app = FastAPI(title="Numbo-2 Control Panel")
app.add_middleware(SessionMiddleware, secret_key=SECRET, same_site="lax")
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
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        PID_FILE.unlink(missing_ok=True)
        return False


def get_stats():
    empty = {"total": 0, "phones": 0, "emails": 0, "wordpress": 0, "woocommerce": 0, "cities": 0}
    conn = get_db()
    if not conn:
        return empty
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
    except Exception:
        return empty
    finally:
        conn.close()


def read_seeds() -> str:
    if SEEDS_PATH.exists():
        return SEEDS_PATH.read_text(encoding="utf-8")
    return ""


def logged_in(request: Request) -> bool:
    if not PANEL_PASSWORD:
        return True
    return bool(request.session.get("ok"))


@app.middleware("http")
async def auth_mw(request: Request, call_next):
    path = request.url.path
    if path in ("/login", "/health") or path.startswith("/static"):
        return await call_next(request)
    if logged_in(request):
        return await call_next(request)
    if path.startswith("/api"):
        return JSONResponse({"error": "auth"}, status_code=401)
    return RedirectResponse("/login", status_code=303)


@app.get("/health")
async def health():
    # Keep the legacy `ok` field for existing clients while exposing the
    # explicit health status expected by live E2E and monitoring.
    return {"status": "ok", "ok": True}


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    if logged_in(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": error})


@app.post("/login")
async def login_submit(request: Request, password: str = Form("")):
    if PANEL_PASSWORD and password == PANEL_PASSWORD:
        request.session["ok"] = True
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": "wrong"}, status_code=401)


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    cfg = load_config()
    tlds = ",".join(cfg.get("allowed_tlds") or [])
    return templates.TemplateResponse(request=request, name="index.html", context={
        "request": request,
        "stats": get_stats(),
        "running": is_crawler_running(),
        "seeds": read_seeds(),
        "tlds": tlds,
    })


@app.post("/start")
async def start_crawler():
    if is_crawler_running():
        return RedirectResponse("/", status_code=303)
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
    cfg = load_config()
    cleaned = []
    for t in tlds.split(","):
        t = t.strip().lower()
        if not t:
            continue
        if not t.startswith("."):
            t = "." + t
        cleaned.append(t)
    cfg["allowed_tlds"] = cleaned
    save_config(cfg)
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
        return templates.TemplateResponse(request=request, name="contacts.html", context={
            "request": request, "rows": [], "page": 1, "total_pages": 0,
            "q": q or "", "tech": tech or "", "city": city or "", "total": 0,
        })
    per_page = 50
    offset = (max(page, 1) - 1) * per_page
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
        "request": request, "rows": rows, "page": page, "total_pages": total_pages,
        "q": q or "", "tech": tech or "", "city": city or "", "total": total,
    })


@app.get("/export")
async def export_data():
    from export import main as do_export
    do_export()
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
        lines = LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
        content = "\n".join(lines[-150:])
    return templates.TemplateResponse(request=request, name="logs.html", context={"request": request, "logs": content})
