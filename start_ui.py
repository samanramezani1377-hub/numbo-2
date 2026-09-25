#!/usr/bin/env python3
import os
from pathlib import Path
from dotenv import load_dotenv
import uvicorn
from numbo.config import load as load_config

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
cfg = load_config()
PORT = int(os.getenv("NUMBO_PORT") or cfg.get("panel_port") or 8080)

if __name__ == "__main__":
    print(f"Numbo-2 panel: http://0.0.0.0:{PORT}")
    uvicorn.run("ui.app:app", host="0.0.0.0", port=PORT, reload=False)
