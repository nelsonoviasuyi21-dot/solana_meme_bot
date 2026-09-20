import json
import time
import subprocess
from pathlib import Path

from config import (
    TAKE_PROFIT_PERCENT,
    MIN_TOKEN_AGE_MINUTES,
    MAX_TOKEN_AGE_MINUTES,
)

from scanner import (
    scan_once,
    refresh_reentry_check,
)

from trader import (
    monitor_take_profit,
    get_current_price,
)


STATE_FILE = Path("data/project_states.json")



def prepare_wallet_entry(token):
    """
    Prepare the automatic wallet transaction for an entry.

    The wallet executor:
      - reads the protected private key locally
      - calculates 50% of current SOL balance
      - requests a Jupiter quote
      - builds an unsigned swap transaction

    LIVE_TRADING remains OFF in the executor, so this function
    does not sign or broadcast a transaction.
    """

    address = str(token.get("address", "")).strip()

    if not address:
        print("WALLET ENTRY: missing token address")
        return False

    print()
    print("=" * 64)
    print("PREPARING AUTOMATIC WALLET ENTRY")
    print("=" * 64)
    print(f"Token mint   : {address}")
    print("Allocation   : 50% of current wallet balance")
    print("Live trading : OFF")
    print("Signing      : OFF")
    print("Broadcast    : OFF")
    print("=" * 64)

    command = [
        "node",
        "wallet/swap_executor.js",
        address,
    ]

    try:
        result = subprocess.run(
            command,
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=45,
        )

    except subprocess.TimeoutExpired:
        print("WALLET ENTRY: executor timed out")
        print("Decision     : DO NOT ENTER")
        return False

    except Exception as exc:
        print(f"WALLET ENTRY ERROR: {exc}")
        print("Decision          : DO NOT ENTER")
        return False

    if result.stdout:
        print(result.stdout.rstrip())

    if result.stderr:
        print(result.stderr.rstrip())

    if result.returncode != 0:
        print("WALLET ENTRY: transaction preparation FAILED")
        print("Decision     : DO NOT ENTER")
        return False

    required_messages = [
        "QUOTE RECEIVED:      YES",
        "UNSIGNED TRANSACTION: RECEIVED",
        "BROADCAST:           DISABLED",
        "TRANSACTION SENT:    NO",
    ]

    for message in required_messages:
        if message not in result.stdout:
            print(
                "WALLET ENTRY: executor verification failed"
            )
            print(
                f"Missing confirmation: {message}"
            )
            print("Decision: DO NOT ENTER")
            return False

    print()
    print("=" * 64)
    print("WALLET ENTRY PREPARATION PASSED")
    print("=" * 64)
    print("Transaction      : BUILT")
    print("Signing          : OFF")
    print("Broadcast        : OFF")
    print("Funds moved      : NO")
    print("Decision         : CONTINUE ENTRY")
    print("=" * 64)

    return True


def load_project_state():
    if not STATE_FILE.exists():
        return None

    try:
        data = json.loads(
            STATE_FILE.read_text() or "{}"
        )

        if not isinstance(data, dict):
            return None

        return data if data else None

    except Exception as exc:
        print(f"State load error: {exc}")
        return None


def save_project_state(state):
    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if state is None:
        STATE_FILE.write_text("{}\n")
        return

    STATE_FILE.write_text(
        json.dumps(
            state,
            indent=2,
        ) + "\n"
    )


def reset_on_startup():
    STATE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    STATE_FILE.write_text("{}\n")

    print(
        "STARTUP RESET      : "
        "Old unfinished state cleared"
    )


def token_from_state(state):
    return {
        "address": state["address"],
        "name": state.get("name", "Unknown"),
        "symbol": state.get("symbol", "UNKNOWN"),
        "pair_address": state.get("pair_address"),
        "price_usd": state.get("watch_price", 0),
    }


def create_watch_state(token):
    price = float(token.get("price_usd", 0))

    return {
        "status": "ENTERED",
        "address": token["address"],
        "name": token.get("name", "Unknown"),
        "symbol": token.get("symbol", "UNKNOWN"),
        "pair_address": token.get("pair_address"),
        "watch_price": price,
        "watch_started": time.time(),
        "rise_triggered": False,
        "entry_number": 0,
    }


def find_initial_candidate():
    passed, rejected = scan_once()

    print()
    print(
        f"Passed candidates : {len(passed)}"
    )
    print(
        f"Rejected           : {rejected}"
    )

    if not passed:
        return None

    for candidate in passed:

        if not candidate.get(
            "confirmed_entry",
            False,
        ):
            continue

        if candidate.get(
            "opportunity_level"
        ) != "ENTRY":
            continue

        if float(
            candidate.get("buy_ratio", 0)
        ) < 65.0:
            continue

        price = float(
            candidate.get("price_usd", 0)
        )

        if price <= 0:
            continue

        return candidate

    return None


    print()
    print("=" * 64)
    print("TOKEN WATCH STARTED")
    print("=" * 64)
    print(f"Name             : {token.get('name', 'Unknown')}")
    print(f"Symbol           : {token.get('symbol', 'UNKNOWN')}")
    print(f"Contract         : {token['address']}")
    print(f"Watch price      : ${watch_price:.10f}")
    print()
    print("RULE:")
    print("=" * 64)


def fresh_buyer_check(address):
    """
    Perform a fresh market/buyer-control check.
    """
    token, strong, reason = refresh_reentry_check(
        address
    )

    return token, strong, reason


def print_buyer_decision(
    token,
    current_price,
    watch_price,
    strong,
    reason,
):
    print()
    print("=" * 64)
    print("FRESH BUYER-CONTROL CHECK")
    print("=" * 64)
    print(
        f"Token          : "
        f"{token.get('symbol', 'UNKNOWN')}"
    )
    print(
        f"Current price  : "
        f"${current_price:.10f}"
    )
    print(
        f"Watch price    : "
        f"${watch_price:.10f}"
    )

    if token.get("buy_ratio") is not None:
        print(
            f"5m buyers      : "
            f"{float(token['buy_ratio']):.2f}%"
        )

    if token.get("buy_ratio_1m") is not None:
        print(
            f"1m buyers      : "
            f"{float(token['buy_ratio_1m']):.2f}%"
        )

    if token.get("score") is not None:
        print(
            f"Score          : "
            f"{float(token['score']):.2f}"
        )

    if strong:
        print("Buyer status   : STRONG")
        print("Decision       : ENTER")
    else:
        print("Buyer status   : NOT STRONG")
        print(f"Reason         : {reason}")
        print("Decision       : DO NOT ENTER")

    print("=" * 64)


def enter_position(
    state,
    token,
    entry_price,
):
    entry_number = int(
        state.get("entry_number", 0)
    ) + 1

    state["status"] = "ENTERED"
    state["entry_number"] = entry_number
    state["entry_price"] = float(entry_price)
    state["entry_started"] = time.time()
    state["rise_triggered"] = False

    if token.get("pair_address"):
        state["pair_address"] = token["pair_address"]

    save_project_state(state)

    print()
    print("=" * 64)
    print(f"ENTRY #{entry_number}")
    print("=" * 64)
    print(
        f"Token       : "
        f"{token.get('symbol', 'UNKNOWN')}"
    )
    print(
        f"Entry price : "
        f"${entry_price:.10f}"
    )
    print(
        f"Take profit : "
        f"+{TAKE_PROFIT_PERCENT:.1f}%"
    )
    print("Stop-loss   : OFF")
    print("=" * 64)


def main():
    reset_on_startup()

    print("=" * 64)
    print("SOLANA MEME BOT - WATCH / ENTRY / TP CYCLE")
    print("=" * 64)
    print("PAPER TRADING       : ON")
    print(f"TAKE PROFIT         : +{TAKE_PROFIT_PERCENT:.1f}%")
    print("STOP-LOSS           : OFF")
    print(
        f"TOKEN AGE           : "
        f"{MIN_TOKEN_AGE_MINUTES}-"
        f"{MAX_TOKEN_AGE_MINUTES} minutes"
    )
    print("BUYER CONTROL       : STRONG REQUIRED")
    print("POSITION            : ONE AT A TIME")
    print("=" * 64)

    project_state = load_project_state()

    while True:
        try:

            # =================================================
            # NO ACTIVE PROJECT -> FIND TOKEN TO WATCH
            # =================================================
            if not project_state:
                print()
                print("=" * 64)
                print("SEARCHING FOR ELIGIBLE TOKEN...")
                print("=" * 64)

                token = find_initial_candidate()

                if token is None:
                    print(
                        "No eligible strong-buyer "
                        "token found."
                    )
                    print(
                        "Scanning again in 2 seconds..."
                    )
                    time.sleep(2)
                    continue

                watch_price = float(
                    token["price_usd"]
                )

                if watch_price <= 0:
                    print("Invalid watch price.")
                    time.sleep(2)
                    continue

                # QUALIFIED TOKEN -> IMMEDIATE ENTRY
                if not prepare_wallet_entry(token):
                    print("ENTRY CANCELLED")
                    time.sleep(5)
                    continue
                project_state = create_watch_state(token)
                enter_position(project_state, token, watch_price)
                continue

            # =================================================
            # WATCHING FOR ENTRY
            # =================================================
            if project_state.get("status") == "WATCHING" and False:

                token, entry_price = watch_token(
                    project_state
                )

                if not prepare_wallet_entry(token):
                    print()
                    print("=" * 64)
                    print("ENTRY CANCELLED")
                    print("=" * 64)
                    print(
                        "Wallet transaction could not be "
                        "prepared."
                    )
                    print(
                        "Returning to token watch."
                    )
                    print("=" * 64)
                    time.sleep(5)
                    continue

                enter_position(
                    project_state,
                    token,
                    entry_price,
                )

                continue

            # =================================================
            # ACTIVE POSITION -> +25% TAKE PROFIT
            # =================================================
            if project_state.get(
                "status"
            ) == "ENTERED":

                token = token_from_state(
                    project_state
                )

                entry_number = int(
                    project_state.get(
                        "entry_number",
                        1,
                    )
                )

                entry_price = float(
                    project_state.get(
                        "entry_price",
                        0,
                    )
                )

                result = monitor_take_profit(
                    token,
                    entry_price,
                    entry_number,
                )

                if not result:
                    time.sleep(2)
                    continue

                exit_price = float(
                    result["exit_price"]
                )

                print()
                print("=" * 64)
                print("TAKE PROFIT COMPLETE")
                print("=" * 64)
                print(
                    f"Entry #{entry_number}"
                )
                print(
                    f"Entry price : "
                    f"${entry_price:.10f}"
                )
                print(
                    f"Exit price  : "
                    f"${exit_price:.10f}"
                )
                print(
                    f"Profit      : "
                    f"{float(result['gain_percent']):+.2f}%"
                )
                print()
                print(
                    "STARTING NEW WATCH CYCLE"
                )
                print("=" * 64)

                # The TP exit becomes the NEW watch price.
                project_state["status"] = "REENTRY_WATCHING"
                project_state["watch_price"] = exit_price
                project_state["watch_started"] = time.time()
                project_state["rise_triggered"] = False

                save_project_state(
                    project_state
                )

                continue

            # =================================================

            # UNKNOWN STATE
            # =================================================
            print(
                "Unknown state detected. Resetting."
            )

            save_project_state(project_state); raise RuntimeError("Unknown project state - trading cycle stopped")
            save_project_state(None)

        except KeyboardInterrupt:
            print()
            print("Bot stopped by user.")
            break

        except Exception as exc:
            print()
            print(f"MAIN LOOP ERROR: {exc}")
            print("Retrying in 10 seconds...")
            time.sleep(10)


if __name__ == "__main__":
    main()
