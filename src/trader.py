import time
import requests
from config import TAKE_PROFIT_PERCENT, PRICE_CHECK_INTERVAL_SECONDS

DEX_API = "https://api.dexscreener.com"

def get_current_price(token):
    address = str(token.get("address", "")).strip()
    if not address:
        return None
    try:
        r = requests.get(f"{DEX_API}/tokens/v1/solana/{address}", timeout=15)
        r.raise_for_status()
        pairs = [p for p in r.json() if p.get("chainId") == "solana"]
        if not pairs:
            return None
        pair_address = token.get("pair_address")
        if pair_address:
            for p in pairs:
                if p.get("pairAddress") == pair_address:
                    value = float(p.get("priceUsd") or 0)
                    if value > 0:
                        return value
        p = max(pairs, key=lambda x: float((x.get("liquidity") or {}).get("usd") or 0))
        value = float(p.get("priceUsd") or 0)
        return value if value > 0 else None
    except Exception as exc:
        print("Price error:", exc)
        return None

def calculate_target(entry_price):
    return float(entry_price) * (1 + TAKE_PROFIT_PERCENT / 100.0)

def monitor_take_profit(token, entry_price, entry_number=1):
    target = calculate_target(entry_price)
    symbol = token.get("symbol", "UNKNOWN")
    print(f"ENTRY #{entry_number}: {symbol} @ ${entry_price:.10f} | TP ${target:.10f} (+{TAKE_PROFIT_PERCENT:.1f}%) | SL OFF | PAPER ON")
    while True:
        price = get_current_price(token)
        if price is None:
            time.sleep(PRICE_CHECK_INTERVAL_SECONDS)
            continue
        gain = ((price - entry_price) / entry_price) * 100.0
        print(f"{symbol} | ${price:.10f} | {gain:+.2f}%")
        if price >= target:
            return {"exit_price": price, "gain_percent": gain, "result": "TAKE_PROFIT"}
        time.sleep(PRICE_CHECK_INTERVAL_SECONDS)
