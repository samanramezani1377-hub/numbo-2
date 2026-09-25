import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

DEFAULTS = {
    "panel_port": 8080,
    "panel_password": "",
    "secret": "",
    "allowed_tlds": [".ir"],
    "cycle_delay": 300,
}


def load():
    data = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except Exception:
            pass
    return data


def save(data):
    CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return data
