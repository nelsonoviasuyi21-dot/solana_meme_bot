def watch_token(state):
    token = token_from_state(state)
    watch_price = float(state["watch_price"])
    symbol = token.get("symbol", "UNKNOWN")
    confirm_seconds = 15.0
    sample_interval = 3.0
    drop_trigger = watch_price * 0.85
    started = time.time()

    print()
    print("=" * 64)
    print("15-SECOND UPWARD CONFIRMATION")
    print("=" * 64)
    print(f"Token       : {symbol}")
    print(f"Watch price : ${watch_price:.10f}")
    print("Buyer rule  : 65%+")
    print("Momentum    : 1m and 5m positive")
    print("=" * 64)

    while time.time() - started < confirm_seconds:
        current_price = get_current_price(token)

        if current_price is None or current_price <= 0:
            print("Unable to read price. Retrying...")
            time.sleep(sample_interval)
            continue

        distance = ((current_price - watch_price) / watch_price) * 100
        fresh_token, strong, reason = fresh_buyer_check(state["address"])

        ratio_5m = None
        ratio_1m = None
        change_5m = None
        change_1m = None

        if fresh_token is not None:
            try:
                ratio_5m = float(fresh_token.get("buy_ratio", 0))
            except (TypeError, ValueError):
                pass
            try:
                value = fresh_token.get("buy_ratio_1m")
                ratio_1m = float(value) if value is not None else None
            except (TypeError, ValueError):
                pass
            try:
                change_5m = float(fresh_token.get("price_change_5m", 0))
            except (TypeError, ValueError):
                pass
            try:
                change_1m = float(fresh_token.get("price_change_1m", 0))
            except (TypeError, ValueError):
                pass

        buyer_ok = ratio_5m is not None and ratio_5m >= 65.0
        buyer_1m_ok = ratio_1m is None or ratio_1m >= 65.0
        momentum_ok = (
            change_5m is not None
            and change_5m > 0
            and change_1m is not None
            and change_1m > 0
        )
        price_rising = current_price > watch_price

        print(
            f"{symbol} | Price: ${current_price:.10f} | "
            f"From watch: {distance:+.2f}% | "
            f"1m: {change_1m if change_1m is not None else N/A}% | "
            f"5m: {change_5m if change_5m is not None else N/A}%"
        )

        if buyer_ok and buyer_1m_ok and momentum_ok and price_rising:
            entry_token = fresh_token if fresh_token is not None else token
            entry_price = float(entry_token.get("price_usd", current_price))
            if entry_price <= 0:
                entry_price = current_price

            print()
            print("=" * 64)
            print("UPWARD CONFIRMATION PASSED")
            print("=" * 64)
            print(f"Entry price : ${entry_price:.10f}")
            print(f"Buyer 5m    : {ratio_5m:.2f}%")
            print(f"Buyer 1m    : {ratio_1m:.2f}%" if ratio_1m is not None else "Buyer 1m    : N/A")
            print(f"Momentum 1m : {change_1m:+.2f}%" if change_1m is not None else "Momentum 1m : N/A")
            print(f"Momentum 5m : {change_5m:+.2f}%" if change_5m is not None else "Momentum 5m : N/A")
            print("ACTION      : ENTER")
            print("=" * 64)
            return entry_token, entry_price

        time.sleep(sample_interval)

    print()
    print("=" * 64)
    print("15-SECOND CONFIRMATION FAILED")
    print("=" * 64)
    print(f"Fallback trigger: ${drop_trigger:.10f}")
    print("Continuing to watch for a 15% drop.")
    print("=" * 64)

    while True:
        current_price = get_current_price(token)

        if current_price is None or current_price <= 0:
            print("Unable to read price. Retrying...")
            time.sleep(5)
            continue

        distance = ((current_price - watch_price) / watch_price) * 100
        print(
            f"{symbol} | Price: ${current_price:.10f} | "
            f"From watch: {distance:+.2f}%"
        )

        if current_price <= drop_trigger:
            print()
            print("=" * 64)
            print("WATCH PRICE -15% REACHED")
            print("=" * 64)
            print("Next step: FRESH BUYER CHECK")
            print("=" * 64)

            fresh_token, strong, reason = fresh_buyer_check(state["address"])

            if fresh_token is None:
                print("Fresh buyer check unavailable.")
                time.sleep(5)
                continue

            print_buyer_decision(
                fresh_token,
                current_price,
                watch_price,
                strong,
                reason,
            )

            if strong:
                entry_price = float(
                    fresh_token.get("price_usd", current_price)
                )
                if entry_price <= 0:
                    entry_price = current_price

                print("FRESH BUYER CHECK PASSED - ENTER")
                return fresh_token, entry_price

            print("Buyer control is not strong enough.")
            print("No entry. Continuing to watch.")

        time.sleep(5)
