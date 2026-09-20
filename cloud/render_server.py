#!/usr/bin/env python3
import json, os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("PORT", "10000"))

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import the existing paper-only bot engine. It remains the single source of truth.
from src import main as bot_main

BOT_THREAD = None
BOT_LOCK = threading.Lock()


def start_bot_thread():
    global BOT_THREAD
    with BOT_LOCK:
        if BOT_THREAD and BOT_THREAD.is_alive():
            return
        BOT_THREAD = threading.Thread(target=bot_main.run, name="ovi-paper-bot", daemon=True)
        BOT_THREAD.start()


def read_json(path, default):
    try:
        if path.exists():
            value = json.loads(path.read_text())
            return value if isinstance(value, dict) else default
    except Exception:
        pass
    return default


def json_response(handler, code, payload):
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path in ("/", "/health"):
            json_response(self, 200, {"ok": True, "service": "ovi-plus", "paper_trading": True, "signing": False, "broadcast": False, "server_time": time.time()})
            return
        if self.path == "/status":
            settings = read_json(bot_main.SETTINGS_FILE, {})
            state = bot_main.get_state()
            json_response(self, 200, {"ok": True, "settings": settings, "state": state, "server_time": time.time()})
            return
        if self.path == "/events":
            state = bot_main.get_state()
            json_response(self, 200, {"ok": True, "events": state.get("events", [])[-50:], "server_time": time.time()})
            return
        if self.path == "/logs":
            log = ROOT / "logs" / "bot_console.log"
            try:
                lines = log.read_text(errors="replace").splitlines()[-100:]
            except Exception:
                lines = []
            json_response(self, 200, {"ok": True, "lines": lines, "server_time": time.time()})
            return
        json_response(self, 404, {"ok": False, "error": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            payload = {}

        if self.path == "/control/start":
            start_bot_thread()
            json_response(self, 200, {"ok": True, "message": "Paper bot started"})
            return

        if self.path == "/control/stop":
            state = bot_main.get_state()
            state["emergency_stop"] = True
            state["status"] = "STOPPED"
            bot_main.set_state(state)
            json_response(self, 200, {"ok": True, "message": "Paper bot stop requested"})
            return

        if self.path == "/control/emergency-stop":
            state = bot_main.get_state()
            state["emergency_stop"] = True
            state["status"] = "EMERGENCY STOP"
            bot_main.set_state(state)
            json_response(self, 200, {"ok": True, "message": "Emergency stop active"})
            return

        if self.path == "/control/resume":
            state = bot_main.get_state()
            state["emergency_stop"] = False
            bot_main.set_state(state)
            start_bot_thread()
            json_response(self, 200, {"ok": True, "message": "Paper bot resumed"})
            return

        if self.path == "/control/scan":
            state = bot_main.get_state()
            state["scan_requested"] = True
            bot_main.set_state(state)
            json_response(self, 200, {"ok": True, "message": "Fresh scan requested"})
            return

        if self.path == "/settings":
            settings = bot_main.get_settings()
            try:
                settings["trade_amount"] = max(float(payload.get("trade_amount", settings["trade_amount"])), 0.000001)
            except Exception:
                pass
            mode = str(payload.get("position_mode", settings.get("position_mode", "SINGLE"))).upper()
            settings["position_mode"] = "MULTIPLE" if mode == "MULTIPLE" else "SINGLE"
            try:
                settings["max_active_projects"] = max(1, min(int(payload.get("max_active_projects", settings.get("max_active_projects", 1))), 10))
            except Exception:
                pass
            if settings["position_mode"] == "SINGLE":
                settings["max_active_projects"] = 1
            bot_main.save_json(bot_main.SETTINGS_FILE, settings)
            json_response(self, 200, {"ok": True, "settings": settings})
            return

        json_response(self, 404, {"ok": False, "error": "Not found"})


def main():
    start_bot_thread()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"OVI PLUS CLOUD API listening on 0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
