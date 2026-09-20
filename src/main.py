import json
import time
import subprocess
from pathlib import Path
from config import *
from scanner import scan_once
from trader import get_current_price, calculate_target, position_snapshot

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "data/bot_state.json"
SETTINGS_FILE = ROOT / "data/bot_settings.json"
DEFAULT_STATE = {"status":"STARTING","emergency_stop":False,"scan_requested":False,"positions":[],"latest_signal":None,"stats":{"entries":0,"take_profits":0,"rejected":0},"health":"STARTING","last_error":"","updated_at":0,"events":[]}

def load_json(path, default):
    try:
        if path.exists():
            v=json.loads(path.read_text())
            return v if isinstance(v,dict) else default.copy()
    except Exception:
        pass
    return default.copy()

def save_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(value,indent=2)+'\n'); tmp.replace(path)

def get_settings():
    d={"trade_amount":DEFAULT_TRADE_AMOUNT_SOL,"unit":"SOL","position_mode":POSITION_MODE,"max_active_projects":MAX_ACTIVE_PROJECTS}; d.update(load_json(SETTINGS_FILE,{}))
    try:d["trade_amount"]=max(float(d.get("trade_amount",DEFAULT_TRADE_AMOUNT_SOL)),0.000001)
    except:d["trade_amount"]=DEFAULT_TRADE_AMOUNT_SOL
    d["position_mode"]="MULTIPLE" if str(d.get("position_mode","SINGLE")).upper()=="MULTIPLE" else "SINGLE"
    try:d["max_active_projects"]=max(1,min(int(d.get("max_active_projects",1)),10))
    except:d["max_active_projects"]=1
    if d["position_mode"]=="SINGLE": d["max_active_projects"]=1
    save_json(SETTINGS_FILE,d); return d

def get_state():
    v=load_json(STATE_FILE,DEFAULT_STATE); m={**DEFAULT_STATE,**v}; m["stats"]={**DEFAULT_STATE["stats"],**(v.get("stats") or {})}; m["positions"]=v.get("positions") or []; m["events"]=v.get("events") or []; return m

def set_state(s): s["updated_at"]=time.time(); save_json(STATE_FILE,s)

def event(state, kind, message, **extra):
    item={"type":kind,"message":message,"timestamp":time.time(),**extra}; state.setdefault("events",[]).append(item); state["events"]=state["events"][-100:]; print(f"[{kind}] {message}",flush=True)

def candidate_ok(c):
    try:return bool(c.get("confirmed_entry")) and str(c.get("opportunity_level","")).upper()=="ENTRY" and float(c.get("buy_ratio",0) or 0)>=65 and float(c.get("price_usd",0) or 0)>0
    except:return False

def scan_candidates():
    r=scan_once()
    if isinstance(r,tuple) and len(r)>=2:return list(r[0] or []),int(r[1] or 0)
    if isinstance(r,dict):return list(r.get("passed") or r.get("candidates") or []),int(r.get("rejected") or 0)
    return list(r or []),0

def paper_entry(c, amount):
    if not PAPER_TRADING:
        return False

    symbol = c.get("symbol", "UNKNOWN")
    address = c.get("address", "")

    print("========================================", flush=True)
    print(" PAPER ENTRY SIMULATION", flush=True)
    print("========================================", flush=True)
    print(f"TOKEN:               {symbol}", flush=True)
    print(f"ADDRESS:             {address}", flush=True)
    print(f"TRADE SIZE:          {amount:.6f} SOL", flush=True)
    print("WALLET:              NOT USED", flush=True)
    print("SIGNING:             DISABLED", flush=True)
    print("BROADCAST:           DISABLED", flush=True)
    print("FUNDS MOVED:         NO", flush=True)
    print("PAPER ENTRY:         ACCEPTED", flush=True)
    print("========================================", flush=True)

    return True

def run():
    settings=get_settings(); state=get_state(); state["status"]="RUNNING"; state["health"]="ONLINE"; state["last_error"]=""; set_state(state)
    event(state,"BOT_ONLINE",f"Bot online • scanning every cycle • TP +{TAKE_PROFIT_PERCENT:.1f}% • paper only"); set_state(state)
    while True:
        settings=get_settings(); state=get_state()
        if state.get("emergency_stop"):
            state["status"]="EMERGENCY STOP"; state["health"]="STOPPED"; set_state(state); time.sleep(2); continue
        active=[p for p in state.get("positions",[]) if p.get("status")=="ACTIVE"]
        state["positions"]=active
        # Live position engine: update price/P&L on every 5-second cycle without blocking the dashboard.
        if active:
            state["status"]="MONITORING"; state["health"]="ONLINE"
            for p in list(active):
                token={"address":p["address"],"symbol":p.get("symbol"),"pair_address":p.get("pair_address")}
                price=get_current_price(token)
                if price is None: continue
                snap=position_snapshot(token,float(p["entry_price"]),price,float(p.get("amount_sol",settings["trade_amount"])))
                p.update(snap); p["last_update"]=time.time()
                gain=snap["gain_percent"]
                if gain>=TAKE_PROFIT_PERCENT:
                    p.update({"status":"CLOSED","exit_price":price,"exit_time":time.time(),"live":False})
                    state["stats"]["take_profits"]+=1
                    event(state,"TAKE_PROFIT",f"{p.get('symbol','UNKNOWN')} reached +{gain:.2f}% TP",symbol=p.get("symbol"),gain_percent=gain)
                    state["positions"]=[x for x in state["positions"] if x.get("status")=="ACTIVE"]
                else:
                    print(f"LIVE | {p.get('symbol','UNKNOWN')} | entry ${float(p['entry_price']):.10f} | now ${price:.10f} | P/L {gain:+.2f}% | {snap['pnl_sol']:+.6f} SOL | TP +{TAKE_PROFIT_PERCENT:.1f}%",flush=True)
                    state["latest_signal"]={**(state.get("latest_signal") or {}),"live_price":price,"live_gain_percent":gain,"pnl_sol":snap["pnl_sol"],"tp_progress":snap["tp_progress"],"timestamp":time.time()}
            set_state(state)
            time.sleep(5); continue
        state["status"]="SCANNING"; state["health"]="ONLINE"
        requested=bool(state.get("scan_requested"))
        if requested: event(state,"SCAN_REQUEST","Fresh scan requested from dashboard")
        set_state(state)
        try:
            passed,rejected=scan_candidates(); state["stats"]["rejected"]+=rejected; state["scan_requested"]=False
            event(state,"SCAN",f"Scanner cycle • candidates {len(passed)} • rejected {rejected}")
            state["latest_signal"]={"scanner_candidates":len(passed),"rejected":rejected,"timestamp":time.time()}
            candidate=next((c for c in passed if candidate_ok(c)),None)
        except Exception as exc:
            state["last_error"]=str(exc); state["health"]="DEGRADED"; event(state,"ERROR",str(exc)); set_state(state); time.sleep(5); continue
        if not candidate:
            set_state(state); time.sleep(3); continue
        state["latest_signal"]={"symbol":candidate.get("symbol","UNKNOWN"),"address":candidate.get("address"),"score":candidate.get("score"),"buy_ratio":candidate.get("buy_ratio"),"price_usd":candidate.get("price_usd"),"timestamp":time.time()}
        set_state(state); event(state,"QUALIFIED",f"{candidate.get('symbol','UNKNOWN')} qualified • score {candidate.get('score','—')} • buy ratio {candidate.get('buy_ratio','—')}%")
        if not paper_entry(candidate,settings["trade_amount"]):
            state=get_state(); state["last_error"]="Paper executor did not complete unsigned transaction preparation."; event(state,"ENTRY_REJECTED",state["last_error"]); set_state(state); time.sleep(3); continue
        price=float(candidate.get("price_usd") or 0)
        pos={"status":"ACTIVE","symbol":candidate.get("symbol","UNKNOWN"),"address":candidate.get("address"),"pair_address":candidate.get("pair_address"),"entry_price":price,"current_price":price,"amount_sol":settings["trade_amount"],"target_price":calculate_target(price),"target_percent":TAKE_PROFIT_PERCENT,"gain_percent":0.0,"pnl_sol":0.0,"tp_progress":0.0,"entry_time":time.time(),"live":True,"entry_number":state["stats"]["entries"]+1}
        state=get_state(); state["positions"]=[p for p in state.get("positions",[]) if p.get("status")=="ACTIVE"]+[pos]; state["stats"]["entries"]+=1; event(state,"TRADE_ENTERED",f"{pos['symbol']} entered • {settings['trade_amount']:.6f} SOL • TP +{TAKE_PROFIT_PERCENT:.1f}%",symbol=pos["symbol"],entry_price=price); set_state(state)
        time.sleep(1)

if __name__=="__main__":
    try:run()
    except KeyboardInterrupt:pass
    except Exception as exc:
        state=get_state(); state["status"]="CRASHED"; state["health"]="OFFLINE"; state["last_error"]=str(exc); event(state,"CRASH",str(exc)); set_state(state); raise
