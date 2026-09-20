import time
from dataclasses import dataclass


@dataclass
class SecurityResult:
    passed: bool
    reasons: list[str]


def token_age_minutes(pair_created_at):
    if not pair_created_at:
        return None

    now_ms = int(time.time() * 1000)
    age_ms = now_ms - int(pair_created_at)

    if age_ms < 0:
        return 0

    return age_ms / 60000


def check_token_security(token: dict) -> SecurityResult:
    reasons = []

    # ---------------------------------------------------------
    # TOKEN AGE
    # Main scanner controls the final 6-15 minute window.
    # This check only rejects obviously old tokens.
    # ---------------------------------------------------------
    age = token_age_minutes(token.get("pair_created_at"))

    if age is not None and age > 15:
        reasons.append(
            f"Token/pair is too old: {age:.1f} minutes"
        )

    # ---------------------------------------------------------
    # LIQUIDITY
    # Faster discovery profile: $5,000 minimum.
    # ---------------------------------------------------------
    try:
        liquidity = float(token.get("liquidity_usd") or 0)
    except (TypeError, ValueError):
        liquidity = 0

    if liquidity < 5000:
        reasons.append(
            f"Liquidity too low: ${liquidity:,.0f}"
        )

    # ---------------------------------------------------------
    # 5-MINUTE VOLUME
    # Faster discovery profile: $500 minimum.
    # ---------------------------------------------------------
    try:
        volume = float(token.get("volume_5m_usd") or 0)
    except (TypeError, ValueError):
        volume = 0

    if volume < 500:
        reasons.append(
            f"5-minute volume too low: ${volume:,.0f}"
        )

    # ---------------------------------------------------------
    # IMPORTANT:
    # Do not reject simply because these fields are unavailable
    # here. The trusted RugCheck provider performs the important
    # authority/risk checks separately.
    # ---------------------------------------------------------

    return SecurityResult(
        passed=len(reasons) == 0,
        reasons=reasons,
    )
