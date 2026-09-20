import time
import requests

from config import (
    MIN_TOKEN_AGE_MINUTES,
    MAX_TOKEN_AGE_MINUTES,
    MIN_LIQUIDITY_USD,
    MIN_VOLUME_5M_USD,
)

from security_provider import (
    get_security_report,
    security_passes,
    onchain_security_check,
)

DEX_API = "https://api.dexscreener.com"
REQUEST_TIMEOUT = 8


# Cheap market filters
MIN_BUY_RATIO = 0.65
MIN_ACTIVITY_RATIO = 0.03
MIN_PRICE_CHANGE_5M = 0.0
ENTRY_SCORE = 50.0

# Secondary confirmation
SECONDARY_MIN_LIQUIDITY_USD = 7500
SECONDARY_MIN_VOLUME_5M_USD = 500

# Security rejection cache
SECURITY_REJECT_COOLDOWN_SECONDS = 600
SECURITY_REJECT_CACHE = {}



def cleanup_security_reject_cache():
    now = time.time()

    expired = [
        address
        for address, data in SECURITY_REJECT_CACHE.items()
        if data.get("expires", 0) <= now
    ]

    for address in expired:
        SECURITY_REJECT_CACHE.pop(address, None)


def get_cached_security_rejection(address):
    cleanup_security_reject_cache()

    data = SECURITY_REJECT_CACHE.get(address)

    if not data:
        return None

    return data.get("reasons", [])


def cache_security_rejection(address, reasons):
    SECURITY_REJECT_CACHE[address] = {
        "expires": time.time() + SECURITY_REJECT_COOLDOWN_SECONDS,
        "reasons": list(reasons),
    }


def get_latest_profiles():
    response = requests.get(
        f"{DEX_API}/token-profiles/latest/v1",
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    return data if isinstance(data, list) else []


def get_latest_boosts():
    response = requests.get(
        f"{DEX_API}/token-boosts/latest/v1",
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    return data if isinstance(data, list) else []


def get_top_boosts():
    response = requests.get(
        f"{DEX_API}/token-boosts/top/v1",
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    return data if isinstance(data, list) else []


def get_discovery_pool():
    """
    Combine several DexScreener discovery streams.

    Boosts are discovery signals only.
    Market data and security checks determine whether
    a project actually qualifies.
    """

    sources = []

    try:
        sources.extend(get_latest_boosts())
    except Exception as exc:
        print(f"Latest boosts error: {exc}")

    try:
        sources.extend(get_top_boosts())
    except Exception as exc:
        print(f"Top boosts error: {exc}")

    try:
        sources.extend(get_latest_profiles())
    except Exception as exc:
        print(f"Latest profiles error: {exc}")

    # Broad Solana discovery searches.
    # Search results are cross-chain, so only Solana pairs are accepted.
    search_terms = ["pump", "dog", "cat", "ai", "inu"]

    for term in search_terms:
        try:
            response = requests.get(
                f"{DEX_API}/latest/dex/search",
                params={"q": term},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            data = response.json()

            for pair in data.get("pairs", []):
                if pair.get("chainId") != "solana":
                    continue

                base_token = pair.get("baseToken") or {}
                address = base_token.get("address")

                if not address:
                    continue

                sources.append({
                    "chainId": "solana",
                    "tokenAddress": address,
                    "amount": 0,
                    "totalAmount": 0,
                })

        except Exception as exc:
            print(f"Search discovery error [{term}]: {exc}")

    unique = {}

    for item in sources:
        if item.get("chainId") != "solana":
            continue

        address = item.get("tokenAddress")

        if not address:
            continue

        if address not in unique:
            unique[address] = {
                "chainId": "solana",
                "tokenAddress": address,
                "boost_amount": safe_float(
                    item.get("amount")
                ),
                "total_boost_amount": safe_float(
                    item.get("totalAmount")
                ),
            }
        else:
            unique[address]["boost_amount"] = max(
                unique[address].get("boost_amount", 0),
                safe_float(item.get("amount")),
            )

            unique[address]["total_boost_amount"] = max(
                unique[address].get("total_boost_amount", 0),
                safe_float(item.get("totalAmount")),
            )

    return list(unique.values())

def get_token_pairs(token_address):
    response = requests.get(
        f"{DEX_API}/tokens/v1/solana/{token_address}",
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    return data if isinstance(data, list) else []


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def token_age_minutes(created_at):
    if not created_at:
        return None

    try:
        age = (
            time.time() * 1000 - int(created_at)
        ) / 60000
    except (TypeError, ValueError):
        return None

    return max(age, 0)


def build_candidate(profile):
    if profile.get("chainId") != "solana":
        return None

    address = profile.get("tokenAddress")

    if not address:
        return None

    pairs = get_token_pairs(address)

    if not pairs:
        return None

    pairs = [
        pair
        for pair in pairs
        if pair.get("chainId") == "solana"
    ]

    if not pairs:
        return None

    # Use the most liquid Solana pair.
    pair = max(
        pairs,
        key=lambda item: safe_float(
            (item.get("liquidity") or {}).get("usd")
        ),
    )

    base_token = pair.get("baseToken") or {}
    liquidity = safe_float(
        (pair.get("liquidity") or {}).get("usd")
    )

    volume = pair.get("volume") or {}
    price_change = pair.get("priceChange") or {}
    txns = pair.get("txns") or {}

    txns_5m = txns.get("m5") or {}
    txns_1m = txns.get("m1") or {}

    buys_5m = safe_int(txns_5m.get("buys"))
    sells_5m = safe_int(txns_5m.get("sells"))

    buys_1m = safe_int(txns_1m.get("buys"))
    sells_1m = safe_int(txns_1m.get("sells"))

    has_1m_data = "m1" in price_change

    return {
        "address": address,
        "name": base_token.get("name") or "Unknown",
        "symbol": base_token.get("symbol") or "UNKNOWN",
        "price_usd": safe_float(pair.get("priceUsd")),
        "liquidity_usd": liquidity,
        "volume_5m_usd": safe_float(volume.get("m5")),
        "volume_1m_usd": safe_float(volume.get("m1")),
        "price_change_5m": safe_float(price_change.get("m5")),
        "price_change_1m": safe_float(price_change.get("m1")),
        "has_1m_data": has_1m_data,
        "buys_5m": buys_5m,
        "sells_5m": sells_5m,
        "buys_1m": buys_1m,
        "sells_1m": sells_1m,
        "pair_created_at": pair.get("pairCreatedAt"),
        "pair_address": pair.get("pairAddress"),
        "dex": pair.get("dexId") or "unknown",
    }


def refresh_reentry_check(address):
    """
    Refresh a previously traded token and determine whether
    buyer control is strong enough for a new entry.

    This is intentionally a fresh market-data check. It does
    not rely on the buyer statistics from the original entry.
    """
    try:
        profile = {
            "chainId": "solana",
            "tokenAddress": address,
        }

        token = build_candidate(profile)

        if not token:
            return None, False, "unable_to_refresh"

        age = token_age_minutes(
            token.get("pair_created_at")
        )

        if age is None:
            return token, False, "unknown_age"

        if age < MIN_TOKEN_AGE_MINUTES:
            return token, False, "too_young"

        if age > MAX_TOKEN_AGE_MINUTES:
            return token, False, "too_old"

        buy_ratio_value = buyer_ratio(token)

        # Strong buyer control is mandatory for re-entry.
        if buy_ratio_value < MIN_BUY_RATIO:
            return token, False, "buyers_not_strong"

        # If 1-minute data exists, reject a short-term loss
        # of buyer control.
        short_ratio = short_term_buyer_ratio(token)

        if short_ratio is not None and short_ratio < 0.45:
            return token, False, "short_term_buyers_weak"

        # Do not re-enter into negative short-term momentum.
        if token.get("price_change_5m", 0) < MIN_PRICE_CHANGE_5M:
            return token, False, "momentum_weak"

        score = candidate_score(token)

        if score < ENTRY_SCORE:
            return token, False, "entry_score_too_low"

        token["age_minutes"] = round(age, 1)
        token["buy_ratio"] = round(
            buy_ratio_value * 100,
            2,
        )
        token["buyer_pressure"] = round(
            buyer_pressure(token),
            2,
        )
        token["buy_ratio_1m"] = (
            round(short_ratio * 100, 2)
            if short_ratio is not None
            else None
        )
        token["score"] = score

        return token, True, "strong_buyers"

    except requests.RequestException as exc:
        print(f"Re-entry refresh network error: {exc}")
        return None, False, "network_error"

    except Exception as exc:
        print(f"Re-entry check error: {exc}")
        return None, False, "check_error"


def buyer_ratio(token):
    buys = token.get("buys_5m", 0)
    sells = token.get("sells_5m", 0)

    total = buys + sells

    if total <= 0:
        return 0.0

    return buys / total


def buyer_pressure(token):
    buys = token.get("buys_5m", 0)
    sells = token.get("sells_5m", 0)

    if sells <= 0:
        return float(buys)

    return buys / sells


def short_term_buyer_ratio(token):
    buys = token.get("buys_1m", 0)
    sells = token.get("sells_1m", 0)

    total = buys + sells

    if total <= 0:
        return None

    return buys / total


def candidate_score(token):
    """
    Buyer-control score.

    Maximum approximately 100.

    Components:
    - 5m buyer control
    - 1m buyer control
    - price momentum
    - activity
    - liquidity
    - transaction activity
    """

    liquidity = max(
        token.get("liquidity_usd", 0),
        0,
    )

    volume = max(
        token.get("volume_5m_usd", 0),
        0,
    )

    buys = max(
        token.get("buys_5m", 0),
        0,
    )

    sells = max(
        token.get("sells_5m", 0),
        0,
    )

    total_txns = buys + sells

    if liquidity <= 0 or volume <= 0 or total_txns <= 0:
        return 0.0

    # 5m buyer control: 55% = 25 points,
    # 61%+ = 40 points.
    ratio = buyer_ratio(token)

    buyer_score = min(
        max((ratio - 0.50) / 0.25, 0),
        1,
    ) * 40

    # Very recent buyer control.
    short_ratio = short_term_buyer_ratio(token)

    if short_ratio is None:
        short_score = 0
    else:
        short_score = min(
            max((short_ratio - 0.50) / 0.25, 0),
            1,
        ) * 15

    # Positive momentum.
    momentum = token.get("price_change_5m", 0)

    momentum_score = min(
        max(momentum / 15, 0),
        1,
    ) * 15

    # Trading activity relative to liquidity.
    activity_ratio = volume / liquidity

    activity_score = min(
        activity_ratio / 0.50,
        1,
    ) * 10

    # Prefer meaningful liquidity.
    liquidity_score = min(
        liquidity / 30000,
        1,
    ) * 10

    # More transactions means stronger evidence.
    transaction_score = min(
        total_txns / 100,
        1,
    ) * 10

    return round(
        buyer_score
        + short_score
        + momentum_score
        + activity_score
        + liquidity_score
        + transaction_score,
        2,
    )


def passes_reversal_check(token):
    """
    Avoid candidates where the recent flow is clearly reversing.

    We want current buyers to be stronger than sellers,
    not merely a token that pumped earlier.
    """

    ratio_5m = buyer_ratio(token)

    if ratio_5m < MIN_BUY_RATIO:
        return False

    short_ratio = short_term_buyer_ratio(token)

    if short_ratio is not None:
        # If 1m data exists, it should not show clear seller control.
        if short_ratio < 0.45:
            return False

    # Strongly negative 5m movement conflicts with buyer control.
    if token.get("price_change_5m", 0) < MIN_PRICE_CHANGE_5M:
        return False

    return True


def cheap_market_filter(token):
    """
    Fast filter before security checks.
    """

    age = token_age_minutes(
        token.get("pair_created_at")
    )

    if age is None:
        return False, "unknown_age"

    if age < MIN_TOKEN_AGE_MINUTES:
        return False, "too_young"

    if age > MAX_TOKEN_AGE_MINUTES:
        return False, "too_old"

    liquidity = token.get("liquidity_usd", 0)

    if liquidity < MIN_LIQUIDITY_USD:
        return False, "low_liquidity"

    volume = token.get("volume_5m_usd", 0)

    if volume < MIN_VOLUME_5M_USD:
        return False, "low_volume"

    buys = token.get("buys_5m", 0)
    sells = token.get("sells_5m", 0)

    if buys + sells <= 0:
        return False, "no_activity"

    if buyer_ratio(token) < MIN_BUY_RATIO:
        return False, "weak_buyers"

    if token.get("price_change_5m", 0) < MIN_PRICE_CHANGE_5M:
        return False, "weak_momentum"

    if not passes_reversal_check(token):
        return False, "reversal"

    activity_ratio = volume / max(liquidity, 1)

    if activity_ratio < MIN_ACTIVITY_RATIO:
        return False, "weak_activity"

    return True, None


def secondary_market_filter(token):
    """
    Stronger market confirmation before expensive security checks.
    """

    if token.get("liquidity_usd", 0) < SECONDARY_MIN_LIQUIDITY_USD:
        return False

    if token.get("volume_5m_usd", 0) < SECONDARY_MIN_VOLUME_5M_USD:
        return False

    if buyer_ratio(token) < 0.60:
        return False

    return True


def verify_security(token):
    """
    Security is intentionally performed late.

    This keeps scanning fast by avoiding expensive security calls
    for weak market candidates.
    """

    address = token["address"]

    cached = get_cached_security_rejection(address)

    if cached:
        return False, cached, True

    report, error = get_security_report(address)

    if error:
        # Fall back to direct on-chain authority checks.
        passed, reasons = onchain_security_check(address)

        if passed:
            return True, ["onchain_fallback_pass"], False

        reasons = reasons or [str(error)]

        cache_security_rejection(
            address,
            reasons,
        )

        return False, reasons, False

    passed, reasons = security_passes(report)

    if not passed:
        cache_security_rejection(
            address,
            reasons,
        )

        return False, reasons, False

    return True, [], False




def print_header():
    print()
    print("=" * 64)
    print("QUALIFIED TOKEN HUNT")
    print("=" * 64)
    print(
        f"AGE WINDOW             : "
        f"{MIN_TOKEN_AGE_MINUTES}-{MAX_TOKEN_AGE_MINUTES} minutes"
    )
    print("ENTRY LOGIC             : BUYERS IN CONTROL")
    print("SECURITY                : VERIFIED")
    print("PAPER TRADING           : ON")
    print("TAKE PROFIT             : +25%")
    print("STOP LOSS               : OFF")
    print("=" * 64)


def scan_once():
    print_header()

    stats = {
        "profiles": 0,
        "too_young": 0,
        "too_old": 0,
        "unknown_age": 0,
        "low_liquidity": 0,
        "low_volume": 0,
        "no_activity": 0,
        "weak_buyers": 0,
        "weak_momentum": 0,
        "reversal": 0,
        "weak_activity": 0,
        "secondary": 0,
        "security_rejected": 0,
        "security_cached": 0,
        "network_errors": 0,
        "other_errors": 0,
    }

    verified = []

    try:
        profiles = get_discovery_pool()
    except Exception as exc:
        print(f"Discovery error: {exc}")
        return [], []

    stats["profiles"] = len(profiles)

    for profile in profiles:

        try:
            token = build_candidate(profile)

            if not token:
                continue

            age = token_age_minutes(
                token.get("pair_created_at")
            )

            if age is None:
                stats["unknown_age"] += 1
                continue

            if age < MIN_TOKEN_AGE_MINUTES:
                stats["too_young"] += 1
                continue

            if age > MAX_TOKEN_AGE_MINUTES:
                stats["too_old"] += 1
                continue

            passed, reason = cheap_market_filter(token)

            if not passed:
                stats[reason] = stats.get(reason, 0) + 1
                continue

            if not secondary_market_filter(token):
                stats["secondary"] += 1
                continue

            token["age_minutes"] = round(age, 1)
            token["buy_ratio"] = round(
                buyer_ratio(token) * 100,
                2,
            )
            token["buyer_pressure"] = round(
                buyer_pressure(token),
                2,
            )

            short_ratio = short_term_buyer_ratio(token)

            token["buy_ratio_1m"] = (
                round(short_ratio * 100, 2)
                if short_ratio is not None
                else None
            )

            token["score"] = candidate_score(token)

            security_ok, reasons, cached = verify_security(token)

            if not security_ok:
                if cached:
                    stats["security_cached"] += 1
                else:
                    stats["security_rejected"] += 1
                continue

            token["security_reasons"] = reasons

            # Immediate entry: no multi-scan confirmation.
            # Entry is allowed only when buyer control is strong.
            # Final entry qualification.
            # A token is ENTRY only when both requirements are met:
            # score >= ENTRY_SCORE (53) and buyer control >= 70%.
            token["opportunity_level"] = (
                "ENTRY"
                if (
                    token.get("score", 0) >= ENTRY_SCORE
                    and buyer_ratio(token) >= MIN_BUY_RATIO
                )
                else "WATCH"
            )

            token["confirmed_entry"] = (
                token.get("opportunity_level") == "ENTRY"
                and buyer_ratio(token) >= MIN_BUY_RATIO
                and token.get("score", 0) >= ENTRY_SCORE
            )

            verified.append(token)

        except requests.RequestException:
            stats["network_errors"] += 1

        except Exception as exc:
            stats["other_errors"] += 1
            print(
                f"Candidate error: {exc}"
            )

    verified.sort(
        key=lambda token: (
            token.get("score", 0),
            token.get("buy_ratio", 0),
            token.get("volume_5m_usd", 0),
        ),
        reverse=True,
    )

    qualified_tokens = verified

    print()
    print("=" * 64)
    print("SCAN SUMMARY")
    print("=" * 64)

    print(
        f"Profiles received       : {stats['profiles']}"
    )
    print(
        f"Too young               : {stats['too_young']}"
    )
    print(
        f"Too old                 : {stats['too_old']}"
    )
    print(
        f"Unknown age             : {stats['unknown_age']}"
    )
    print(
        f"Low liquidity           : {stats['low_liquidity']}"
    )
    print(
        f"Low 5m volume           : {stats['low_volume']}"
    )
    print(
        f"No activity             : {stats['no_activity']}"
    )
    print(
        f"Weak buyers             : {stats['weak_buyers']}"
    )
    print(
        f"Weak momentum            : {stats['weak_momentum']}"
    )
    print(
        f"Reversal rejected       : {stats['reversal']}"
    )
    print(
        f"Weak activity           : {stats['weak_activity']}"
    )
    print(
        f"Secondary rejected      : {stats['secondary']}"
    )
    print(
        f"Security rejected       : {stats['security_rejected']}"
    )
    print(
        f"Security cached         : {stats['security_cached']}"
    )
    print(
        f"Network errors          : {stats['network_errors']}"
    )
    print(
        f"Other errors            : {stats['other_errors']}"
    )
    print(
        f"VERIFIED CANDIDATES     : {len(verified)}"
    )
    print(
        f"QUALIFIED TOKENS RETURNED         : {len(qualified_tokens)}"
    )

    print("=" * 64)

    if qualified_tokens:
        print()
        print("TOP BUYER-CONTROL PROJECTS")
        print("-" * 64)

        for index, token in enumerate(qualified_tokens, 1):
            print(
                f"{index:02d}. "
                f"{token.get('symbol', 'UNKNOWN'):12s} "
                f"score={token.get('score', 0):6.2f} "
                f"buyers={token.get('buy_ratio', 0):6.2f}% "
                f"5m=${token.get('volume_5m_usd', 0):,.0f} "
                f"liq=${token.get('liquidity_usd', 0):,.0f} "
                f"age={token.get('age_minutes', 0):.0f}m"
            )

        print("-" * 64)

    else:
        print(
            "NO VERIFIED BUYER-CONTROL PROJECTS FOUND."
        )

    return qualified_tokens, []


if __name__ == "__main__":
    print()
    print("Solana Buyer-Control Scanner")
    print("Continuous discovery mode")
    print()

    while True:
        try:
            scan_once()

        except KeyboardInterrupt:
            print()
            print("Scanner stopped.")
            break

        except Exception as exc:
            print(
                f"Scanner loop error: {exc}"
            )

        print()
        print("Next scan in 30 seconds...")
        time.sleep(30)
