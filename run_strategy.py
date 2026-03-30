#!/usr/bin/env python3
"""
Strategy runner - loads account config and runs specified strategy.
Usage: python run_strategy.py --strategy csp|wheel|covered_call|bull_put
"""
import os, argparse, requests, sys, sqlite3
from datetime import datetime, timedelta
from config_loader import load_account
from core.broker import Broker


def notify(token, chat, msg):
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": msg, "parse_mode": "Markdown",
                            "disable_web_page_preview": True}, timeout=10)
    except:
        pass


def get_blocked_symbols(db_path: str) -> set:
    """Return symbols with strongly negative sentiment in last 24hrs."""
    if not os.path.exists(db_path):
        return set()
    db = sqlite3.connect(db_path)
    cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    rows = db.execute(
        "SELECT symbol FROM history WHERE ts > ? AND label='negative' "
        "GROUP BY symbol HAVING AVG(score) > 0.85",
        (cutoff,)
    ).fetchall()
    db.close()
    return {r[0] for r in rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True,
                        choices=["csp", "wheel", "covered_call", "bull_put", "iron_condor"])
    args = parser.parse_args()

    cfg = load_account(args.strategy)
    broker = Broker(cfg["key"], cfg["secret"])
    account = broker.account()
    header = (f"*{args.strategy.upper()}* — {datetime.now().strftime('%b %d %H:%M')}\n"
              f"Account: ${float(account.portfolio_value):,.0f} | "
              f"Cash: ${float(account.cash):,.0f}\n")

    if args.strategy == "csp":
        from strategies.csp import CashSecuredPut
        results = CashSecuredPut(broker).run()

    elif args.strategy == "wheel":
        db_path = os.path.join(os.path.dirname(__file__), "sentiment_history.db")
        blocked = get_blocked_symbols(db_path)
        symbol_file = os.path.join(os.path.dirname(__file__), "wheel/config/symbol_list.txt")

        with open(symbol_file) as f:
            original = f.read()

        filtered = [s for s in original.strip().splitlines() if s not in blocked]
        with open(symbol_file, "w") as f:
            f.write("\n".join(filtered))

        results = []
        if blocked:
            results.append(f"⚠️ Skipping {', '.join(blocked)} (negative sentiment)")

        try:
            import subprocess
            wheel_dir = os.path.join(os.path.dirname(__file__), "wheel")
            env = os.environ.copy()
            result = subprocess.run(
                [sys.executable, "scripts/run_strategy.py"],
                cwd=wheel_dir, env=env, capture_output=True, text=True, timeout=120
            )
            if result.stdout:
                print(result.stdout)
            if result.returncode == 0:
                results.append("✅ Wheel executed")
            else:
                results.append(f"⚠️ Wheel error: {result.stderr[-200:]}")
        finally:
            with open(symbol_file, "w") as f:
                f.write(original)

    elif args.strategy == "covered_call":
        from strategies.covered_call import CoveredCall
        results = CoveredCall(broker).run()

    elif args.strategy == "bull_put":
        from strategies.bull_put import BullPutSpread
        results = BullPutSpread(broker).run()

    elif args.strategy == "iron_condor":
        from strategies.iron_condor import IronCondor
        results = IronCondor(broker).run()

    msg = header + "\n".join(results)
    notify(cfg["telegram_token"], cfg["telegram_chat"], msg)
    print(msg)


if __name__ == "__main__":
    main()
