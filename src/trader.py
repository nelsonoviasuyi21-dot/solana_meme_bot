import time
import requests

from config import (
    TAKE_PROFIT_PERCENT,
    PRICE_CHECK_INTERVAL_SECONDS,
)

DEX_API = "https://api.dexscreener.com"


def get_current_price(token):
    address = token["address"]
    pair_address = token.get("pair_address")

    try:
        response = requests.get(
            f"{DEX_API}/tokens/v1/solana/{address}",
            timeout=15,
        )
        response.raise_for_status()

        pairs = response.json()

        if not isinstance(pairs, list):
            return None

        pairs = [
            pair for pair in pairs
            if pair.get("chainId") == "solana"
        ]

        if not pairs:
            return None

        # Prefer the exact pair originally selected by the scanner.
        if pair_address:
            for pair in pairs:
                if pair.get("pairAddress") == pair_address:
                    price = float(pair.get("priceUsd") or 0)
                    if price > 0:
                        return price

        # Fallback to the highest-liquidity Solana pair.
        pair = max(
            pairs,
            key=lambda item: float(
                (item.get("liquidity") or {}).get("usd") or 0
            ),
        )

        return float(pair.get("priceUsd") or 0)

    except Exception as exc:
        print(f"Price error: {exc}")
        return None


def calculate_target(entry_price):
    return entry_price * (
        1 + TAKE_PROFIT_PERCENT / 100
    )


def calculate_drop_trigger(reference_price):
    # 15% drop means price reaches 85% of reference price.
    return reference_price * 0.85


def monitor_for_drop(token, reference_price, entry_number):
    """
    Watch a project until it drops 15% or more
    from the supplied reference price.

    The reference price is:
      Entry 1 -> initial claimed/watch price
      Entry 2 -> actual first TP exit price
    """

    symbol = token["symbol"]
    trigger_price = calculate_drop_trigger(reference_price)

    print()
    print("=" * 60)
    print(f"WATCHING FOR ENTRY #{entry_number}")
    print("=" * 60)
    print(f"Token          : {symbol}")
    print(f"Reference      : ${reference_price:.10f}")
    print("Required drop   : -15% or more")
    print(f"Entry trigger  : <= ${trigger_price:.10f}")
    print("Status         : WATCHING")
    print("=" * 60)

    while True:
        current_price = get_current_price(token)

        if current_price is None or current_price <= 0:
            print("Unable to read price. Retrying...")
            time.sleep(PRICE_CHECK_INTERVAL_SECONDS)
            continue

        drop_percent = (
            (current_price - reference_price)
            / reference_price
        ) * 100

        print(
            f"{symbol} | "
            f"Price: ${current_price:.10f} | "
            f"From reference: {drop_percent:+.2f}%"
        )

        if current_price <= trigger_price:
            print()
            print("=" * 60)
            print(f"15% DROP TRIGGERED - ENTRY #{entry_number}")
            print("=" * 60)
            print(f"Token       : {symbol}")
            print(f"Reference   : ${reference_price:.10f}")
            print(f"Entry price : ${current_price:.10f}")
            print(f"Drop        : {drop_percent:.2f}%")
            print("=" * 60)

            return current_price

        time.sleep(PRICE_CHECK_INTERVAL_SECONDS)


def monitor_take_profit(token, entry_price, entry_number):
    """
    Monitor an entered position until +25% TP is reached.
    No stop-loss is used.
    """

    symbol = token["symbol"]
    target_price = calculate_target(entry_price)

    print()
    print("=" * 60)
    print(f"ENTRY #{entry_number} ACTIVE")
    print("=" * 60)
    print(f"Token       : {symbol}")
    print(f"Entry       : ${entry_price:.10f}")
    print(
        f"Take Profit : ${target_price:.10f} "
        f"(+{TAKE_PROFIT_PERCENT:.1f}%)"
    )
    print("Stop-loss   : OFF")
    print("=" * 60)

    while True:
        current_price = get_current_price(token)

        if current_price is None or current_price <= 0:
            print("Unable to read price. Retrying...")
            time.sleep(PRICE_CHECK_INTERVAL_SECONDS)
            continue

        gain_percent = (
            (current_price - entry_price)
            / entry_price
        ) * 100

        print(
            f"{symbol} | "
            f"Price: ${current_price:.10f} | "
            f"From entry: {gain_percent:+.2f}%"
        )

        if current_price >= target_price:
            print()
            print("=" * 60)
            print(f"TAKE PROFIT HIT - ENTRY #{entry_number}")
            print("=" * 60)
            print(f"Token : {symbol}")
            print(f"Entry : ${entry_price:.10f}")
            print(f"Exit  : ${current_price:.10f}")
            print(f"Gain  : {gain_percent:+.2f}%")
            print("=" * 60)

            return {
                "result": "TAKE_PROFIT",
                "symbol": symbol,
                "entry_price": entry_price,
                "exit_price": current_price,
                "gain_percent": gain_percent,
            }
