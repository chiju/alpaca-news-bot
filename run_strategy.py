#!/usr/bin/env python3
"""
Strategy runner - loads account config and runs specified strategy.
Usage: python run_strategy.py --strategy csp
"""
import os, argparse, requests
from datetime import datetime
from config_loader import load_account
from core.broker import Broker


def notify(token, chat, msg):
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": msg, "parse_mode": "Markdown",
                            "disable_web_page_preview": True}, timeout=10)
    except:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True,
                        choices=["csp", "covered_call", "bull_put"],
                        help="Strategy to run")
    args = parser.parse_args()

    # Load credentials
    cfg = load_account(args.strategy)
    broker = Broker(cfg["key"], cfg["secret"])

    # Load strategy
    if args.strategy == "csp":
        from strategies.csp import CashSecuredPut
        strategy = CashSecuredPut(broker)
    elif args.strategy == "covered_call":
        from strategies.covered_call import CoveredCall
        strategy = CoveredCall(broker)
    elif args.strategy == "bull_put":
        from strategies.bull_put import BullPutSpread
        strategy = BullPutSpread(broker)

    # Run
    account = broker.account()
    header = (f"*{strategy.name}* — {datetime.now().strftime('%b %d %H:%M')}\n"
              f"Account: ${float(account.portfolio_value):,.0f} | "
              f"Cash: ${float(account.cash):,.0f}\n")

    results = strategy.run()
    msg = header + "\n".join(results)

    notify(cfg["telegram_token"], cfg["telegram_chat"], msg)
    print(msg)


if __name__ == "__main__":
    main()
