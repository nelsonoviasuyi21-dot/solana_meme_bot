import requests
from config import TAKE_PROFIT_PERCENT

DEX_API = "https://api.dexscreener.com"

def get_current_price(token):
    address = str(token.get("address", "")).strip()
    if not address:
        return None
    try:
        r = requests.get(f"{DEX_API}/tokens/v1/solana/{address}", timeout=12)
        r.raise_for_status()
        pairs = [p for p in r.json() if p.get("chainId") == "solana"]
        if not pairs:
            return None
        wanted = token.get("pair_address")
        if wanted:
            for p in pairs:
                if p.get("pairAddress") == wanted:
                    v = float(p.get("priceUsd") or 0)
                    if v > 0:
                        return v
        p = max(pairs, key=lambda x: float((x.get("liquidity") or {}).get("usd") or 0))
        v = float(p.get("priceUsd") or 0)
        return v if v > 0 else None
    except Exception as exc:
        print(f"PRICE ERROR | {exc}", flush=True)
        return None

def calculate_target(entry_price):
    return float(entry_price) * (1 + TAKE_PROFIT_PERCENT / 100.0)

def position_snapshot(token, entry_price, current_price, amount_sol):
    gain = ((current_price - entry_price) / entry_price) * 100.0 if entry_price else 0.0
    target = calculate_target(entry_price)
    progress = max(0.0, min(100.0, (gain / TAKE_PROFIT_PERCENT) * 100.0))
    pnl_sol = amount_sol * gain / 100.0
    return {
        "current_price": current_price, "gain_percent": gain, "pnl_sol": pnl_sol,
        "target_price": target, "target_percent": TAKE_PROFIT_PERCENT,
        "tp_progress": progress, "live": True
    }
