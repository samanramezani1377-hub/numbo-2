#!/usr/bin/env python3
"""
شروع رابط کاربری وب نومبو ۲
"""
import uvicorn

if __name__ == "__main__":
    print("Numbo-2 UI starting on http://0.0.0.0:8080")
    print("Open in browser: http://YOUR_SERVER_IP:8080")
    uvicorn.run("ui.app:app", host="0.0.0.0", port=8080, reload=False)
