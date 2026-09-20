import time
import requests

RUGCHECK_URL = "https://api.rugcheck.xyz/v1/tokens"
REQUEST_TIMEOUT = 5
MAX_RETRIES = 3


def get_security_report(mint):
    """
    Try several times to obtain a RugCheck report.

    A missing report is NOT treated as safe.
    """

    last_error = "Unknown error"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                f"{RUGCHECK_URL}/{mint}/report",
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code in (400, 404):
                try:
                    body = response.json()
                except ValueError:
                    body = {}

                if body.get("error") == "not found":
                    last_error = "REPORT_NOT_FOUND"
                else:
                    last_error = f"HTTP_{response.status_code}"

            else:
                response.raise_for_status()
                return response.json(), None

        except requests.RequestException as exc:
            last_error = str(exc)

        if attempt < MAX_RETRIES:
            time.sleep(1)

    return None, last_error


def security_passes(report):
    """
    Strict RugCheck security filter.

    A token only passes when the available report contains
    no known critical security problems.
    """

    if not report:
        return False, ["No valid RugCheck security report"]

    reasons = []

    # Rugged token
    if report.get("rugged") is True:
        reasons.append("Token is marked as rugged")

    # Mint authority
    if report.get("mintAuthority"):
        reasons.append("Mint authority is active")

    # Freeze authority
    if report.get("freezeAuthority"):
        reasons.append("Freeze authority is active")

    # RugCheck risk list
    risks = report.get("risks") or []

    for risk in risks:
        level = str(risk.get("level", "")).lower()
        name = str(risk.get("name", "")).lower()
        description = str(risk.get("description", "")).lower()

        if level in ("danger", "critical"):
            reasons.append(
                f"{level.upper()} risk: "
                f"{risk.get('name', 'unknown')}"
            )

        text = f"{name} {description}"

        if "honeypot" in text:
            reasons.append("Honeypot warning detected")

        if "cannot sell" in text:
            reasons.append("Token may not be sellable")

        if "sell blocked" in text:
            reasons.append("Selling may be blocked")

    # Liquidity check from RugCheck when available
    liquidity = report.get("totalMarketLiquidity")

    if liquidity is not None:
        try:
            liquidity_value = float(liquidity)

            if liquidity_value < 5000:
                reasons.append(
                    f"RugCheck liquidity too low: "
                    f"${liquidity_value:,.0f}"
                )

        except (TypeError, ValueError):
            pass

    return len(reasons) == 0, reasons


SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"


def onchain_security_check(mint):
    """
    Independent Solana RPC security check used when RugCheck
    has no report.

    Requires:
    - Mint account must exist
    - Mint authority must be disabled
    - Freeze authority must be disabled
    """

    try:
        response = requests.post(
            SOLANA_RPC_URL,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [
                    mint,
                    {
                        "encoding": "jsonParsed",
                        "commitment": "confirmed",
                    },
                ],
            },
            timeout=8,
        )

        response.raise_for_status()
        data = response.json()

        value = (
            data.get("result", {})
            .get("value")
        )

        if not value:
            return False, ["Mint account not found"]

        parsed = (
            value.get("data", {})
            .get("parsed", {})
            .get("info", {})
        )

        mint_authority = parsed.get("mintAuthority")
        freeze_authority = parsed.get("freezeAuthority")

        reasons = []

        if mint_authority:
            reasons.append("Mint authority is active")

        if freeze_authority:
            reasons.append("Freeze authority is active")

        if reasons:
            return False, reasons

        return True, [
            "On-chain mint authority disabled",
            "On-chain freeze authority disabled",
        ]

    except requests.RequestException as exc:
        return False, [
            f"Solana RPC unavailable: {exc}"
        ]

    except Exception as exc:
        return False, [
            f"On-chain security check failed: {exc}"
        ]
