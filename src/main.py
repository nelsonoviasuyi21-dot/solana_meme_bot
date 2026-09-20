import json
import time
import subprocess
from pathlib import Path
from config import *
from scanner import scan_once
from trader import monitor_take_profit

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "data/bot_state.json"
SETTINGS_FILE = ROOT / "data/bot_settings.json"

DEFAULT_STATE = {
    "status": "STARTING",
    "emergency_stop": False,
    "scan_requested": False,
    "positions": [],
    "latest_signal": None,
    "stats": {"entries": 0, "take_profits": 0, "rejected": 0},
    "health": "STARTING",
    "last_error": "",
    "updated_at": 0,
}

def load_json(path, default):
    try:
        if path.exists():
            value = json.loads(path.read_text())
            return value if isinstance(value, dict) else default.copy()
    except Exception:
        pass
    return default.copy()

def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)

def get_settings():
    value = {
        "trade_amount": DEFAULT_TRADE_AMOUNT_SOL,
        "unit": "SOL",
        "position_mode": POSITION_MODE,
        "max_active_projects": MAX_ACTIVE_PROJECTS,
    }
    value.update(load_json(SETTINGS_FILE, {}))
    try:
        value["trade_amount"] = max(float(value.get("trade_amount", DEFAULT_TRADE_AMOUNT_SOL)), 0.000001)
    except Exception:
        value["trade_amount"] = DEFAULT_TRADE_AMOUNT_SOL
    mode = str(value.get("position_mode", "SINGLE")).upper()
    value["position_mode"] = "MULTIPLE" if mode == "MULTIPLE" else "SINGLE"
    try:
        value["max_active_projects"] = max(1, min(int(value.get("max_active_projects", 1)), 10))
    except Exception:
        value["max_active_projects"] = 1
    if value["position_mode"] == "SINGLE":
        value["max_active_projects"] = 1
    save_json(SETTINGS_FILE, value)
    return value

def get_state():
    value = load_json(STATE_FILE, DEFAULT_STATE)
    merged = DEFAULT_STATE.copy()
    merged.update(value)
    merged["stats"] = {**DEFAULT_STATE["stats"], **(value.get("stats") or {})}
    merged["positions"] = value.get("positions") or []
    return merged

def set_state(state):
    state["updated_at"] = time.time()
    save_json(STATE_FILE, state)

def candidate_ok(candidate):
    try:
        return (
            bool(candidate.get("confirmed_entry"))
            and str(candidate.get("opportunity_level", "")).upper() == "ENTRY"
            and float(candidate.get("buy_ratio", 0) or 0) >= 65.0
            and float(candidate.get("price_usd", 0) or 0) > 0
        )
    except Exception:
        return False

def scan_candidates():
    result = scan_once()
    if isinstance(result, tuple) and len(result) >= 2:
        return list(result[0] or []), int(result[1] or 0)
    if isinstance(result, dict):
        return list(result.get("passed") or result.get("candidates") or []), int(result.get("rejected") or 0)
    return list(result or []), 0

def paper_entry(candidate, amount_sol):
    address = str(candidate.get("address", "")).strip()
    if not address:
        return False
    command = ["node", "wallet/swap_executor.js", address, f"{amount_sol:.9f}"]
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60)
    except Exception as exc:
        print("Paper executor error:", exc)
        return False
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    return result.returncode == 0 and "BROADCAST:           DISABLED" in result.stdout and "TRANSACTION SENT:    NO" in result.stdout

def run():
    settings = get_settings()
    state = get_state()
    state["status"] = "RUNNING"
    state["health"] = "ONLINE"
    state["last_error"] = ""
    set_state(state)
    print(f"{BOT_NAME} | PAPER ON | TP +{TAKE_PROFIT_PERCENT}% | SL OFF | {settings['position_mode']} | {settings['trade_amount']} SOL")
    while True:
        settings = get_settings()
        state = get_state()
        if state.get("emergency_stop"):
            state["status"] = "EMERGENCY STOP"
            state["health"] = "STOPPED"
            set_state(state)
            time.sleep(2)
            continue
        active = [p for p in state.get("positions", []) if p.get("status") == "ACTIVE"]
        state["positions"] = active
        capacity = 1 if settings["position_mode"] == "SINGLE" else settings["max_active_projects"]
        if len(active) >= capacity:
            for position in list(active):
                token = {"address": position["address"], "symbol": position.get("symbol"), "pair_address": position.get("pair_address")}
                result = monitor_take_profit(token, float(position["entry_price"]), position.get("entry_number", 1))
                position.update({"status": "CLOSED", "exit_price": result["exit_price"], "gain_percent": result["gain_percent"], "exit_time": time.time()})
                state["stats"]["take_profits"] += 1
                state.setdefault("events", []).append({"type":"TAKE_PROFIT","symbol":position.get("symbol","UNKNOWN"),"gain_percent":result.get("gain_percent"),"timestamp":time.time()})
                state["events"] = state["events"][-50:]
                state["positions"] = [p for p in state["positions"] if p.get("status") == "ACTIVE"]
                set_state(state)
            continue
        state["status"] = "SCANNING"
        state["health"] = "ONLINE"
        set_state(state)
        try:
            passed, rejected = scan_candidates()
            state["stats"]["rejected"] += rejected
            active_addresses = {p.get("address") for p in active}
            candidate = next((c for c in passed if candidate_ok(c) and c.get("address") not in active_addresses), None)
            state["scan_requested"] = False
        except Exception as exc:
            state["last_error"] = str(exc)
            state["health"] = "DEGRADED"
            set_state(state)
            time.sleep(5)
            continue
        if not candidate:
            set_state(state)
            time.sleep(3)
            continue
        state["latest_signal"] = {
            "symbol": candidate.get("symbol", "UNKNOWN"),
            "address": candidate.get("address"),
            "score": candidate.get("score"),
            "buy_ratio": candidate.get("buy_ratio"),
            "price_usd": candidate.get("price_usd"),
            "timestamp": time.time(),
        }
        set_state(state)
        if not paper_entry(candidate, settings["trade_amount"]):
            state = get_state()
            state["last_error"] = "Paper executor did not complete the unsigned transaction preparation."
            set_state(state)
            time.sleep(5)
            continue
        position = {
            "address": candidate["address"],
            "symbol": candidate.get("symbol", "UNKNOWN"),
            "pair_address": candidate.get("pair_address"),
            "entry_price": float(candidate["price_usd"]),
            "amount_sol": settings["trade_amount"],
            "entry_time": time.time(),
            "entry_number": int(state["stats"]["entries"]) + 1,
            "status": "ACTIVE",
        }
        state["positions"].append(position)
        state["stats"]["entries"] += 1
        state.setdefault("events", []).append({"type":"TRADE","symbol":position.get("symbol","UNKNOWN"),"amount_sol":settings["trade_amount"],"price":position["entry_price"],"timestamp":time.time()})
        state["events"] = state["events"][-50:]
        set_state(state)
        result = monitor_take_profit(candidate, position["entry_price"], position["entry_number"])
        position.update({"status": "CLOSED", "exit_price": result["exit_price"], "gain_percent": result["gain_percent"], "exit_time": time.time()})
        state = get_state()
        state["stats"]["take_profits"] += 1
        state.setdefault("events", []).append({"type":"TAKE_PROFIT","symbol":position.get("symbol","UNKNOWN"),"gain_percent":result.get("gain_percent"),"timestamp":time.time()})
        state["events"] = state["events"][-50:]
        state["positions"] = []
        set_state(state)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        state = get_state()
        state["status"] = "STOPPED"
        state["health"] = "OFFLINE"
        set_state(state)
