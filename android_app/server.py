#!/usr/bin/env python3
import json, os, subprocess, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SETTINGS = DATA / "bot_settings.json"
STATE = DATA / "bot_state.json"
PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
SVDIR = os.environ.get("SVDIR", f"{PREFIX}/var/service")

DEFAULT_SETTINGS = {"trade_amount": 0.001, "unit": "SOL", "position_mode": "SINGLE", "max_active_projects": 1}
DEFAULT_STATE = {"status": "STOPPED", "emergency_stop": False, "scan_requested": False, "positions": [], "latest_signal": None, "stats": {"entries": 0, "take_profits": 0, "rejected": 0}, "health": "OFFLINE", "last_error": "", "updated_at": 0}

def read_json(path, default):
    try:
        if path.exists(): return json.loads(path.read_text())
    except Exception: pass
    return default.copy()

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)

def run_sv(action):
    env = os.environ.copy(); env["SVDIR"] = SVDIR
    return subprocess.run(["sv", action, "solana-bot"], env=env, capture_output=True, text=True, timeout=10)

def state():
    value = read_json(STATE, DEFAULT_STATE); value["updated_at"] = value.get("updated_at", 0); return value

def response_json(handler, code, value):
    raw = json.dumps(value).encode()
    handler.send_response(code); handler.send_header("Content-Type", "application/json"); handler.send_header("Content-Length", str(len(raw))); handler.end_headers(); handler.wfile.write(raw)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): return
    def do_GET(self):
        if self.path in ("/", "/status"):
            response_json(self, 200, {"ok": True, "settings": read_json(SETTINGS, DEFAULT_SETTINGS), "state": state(), "server_time": time.time()}); return
        response_json(self, 404, {"ok": False, "error": "Not found"})
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0")); body = self.rfile.read(length) if length else b"{}"
        try: payload = json.loads(body.decode() or "{}")
        except Exception: payload = {}
        if self.path == "/start":
            r = run_sv("start"); response_json(self, 200, {"ok": r.returncode == 0, "message": "Bot start requested"}); return
        if self.path == "/stop":
            r = run_sv("stop"); response_json(self, 200, {"ok": r.returncode == 0, "message": "Bot stop requested"}); return
        if self.path == "/restart":
            r = run_sv("restart"); response_json(self, 200, {"ok": r.returncode == 0, "message": "Bot restart requested"}); return
        if self.path == "/emergency-stop":
            s = state(); s["emergency_stop"] = True; write_json(STATE, s); r = run_sv("stop"); response_json(self, 200, {"ok": True, "message": "Emergency stop active", "service": r.returncode}); return
        if self.path == "/resume":
            s = state(); s["emergency_stop"] = False; write_json(STATE, s); response_json(self, 200, {"ok": True, "message": "Emergency stop cleared"}); return
        if self.path == "/scan":
            s = state(); s["scan_requested"] = True; write_json(STATE, s); response_json(self, 200, {"ok": True, "message": "Fresh scan requested"}); return
        if self.path == "/settings":
            s = read_json(SETTINGS, DEFAULT_SETTINGS)
            try: s["trade_amount"] = max(float(payload.get("trade_amount", s["trade_amount"])), 0.000001)
            except Exception: pass
            mode = str(payload.get("position_mode", s.get("position_mode", "SINGLE"))).upper(); s["position_mode"] = "MULTIPLE" if mode == "MULTIPLE" else "SINGLE"
            try: s["max_active_projects"] = max(1, min(int(payload.get("max_active_projects", s.get("max_active_projects", 1))), 10))
            except Exception: pass
            if s["position_mode"] == "SINGLE": s["max_active_projects"] = 1
            s["unit"] = "SOL"; write_json(SETTINGS, s); response_json(self, 200, {"ok": True, "settings": s}); return
        response_json(self, 404, {"ok": False, "error": "Not found"})

if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    if not SETTINGS.exists(): write_json(SETTINGS, DEFAULT_SETTINGS)
    if not STATE.exists(): write_json(STATE, DEFAULT_STATE)
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
