#!/usr/bin/env python3
"""Daily P&L report - sends performance summary to Telegram."""
import os, re, requests
from datetime import datetime
from config_loader import load_account
from core.broker import Broker

# Load Telegram creds
_env = os.path.expanduser("~/.alpaca/options-paper.env")
if os.path.exists(_env):
    for line in open(_env):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")

ACCOUNTS = {
    "wheel":        ("options-paper", 980_000),
    "csp":          ("csp",           100_000),
    "bull-put":     ("bull_put",      100_000),
    "iron-condor":  ("iron_condor",   100_000),
    "covered-call": ("covered_call",  100_000),
}


def notify(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  json={"chat_id": CHAT, "text": msg, "parse_mode": "Markdown",
                        "disable_web_page_preview": True}, timeout=10)


def account_report(name: str, account_type: str, baseline: int) -> str:
    try:
        cfg = load_account(account_type)
        broker = Broker(cfg["key"], cfg["secret"])
        account = broker.account()
        positions = broker.positions()

        equity      = float(account.equity)
        last_equity = float(account.last_equity)
        day_pnl     = equity - last_equity
        day_pct     = (day_pnl / last_equity * 100) if last_equity > 0 else 0
        total_pnl   = equity - baseline

        lines = [
            f"*📊 {name.upper()}*",
            f"Equity: ${equity:,.0f}",
            f"{'🟢' if day_pnl >= 0 else '🔴'} Today: ${day_pnl:+,.0f} ({day_pct:+.1f}%)",
            f"{'🟢' if total_pnl >= 0 else '🔴'} Total: ${total_pnl:+,.0f}",
        ]

        # Open positions
        opts = [p for p in positions if re.search(r'\d{6}[CP]\d{8}', p.symbol)]
        if opts:
            lines.append(f"Options ({len(opts)} open):")
            for p in opts:
                pnl = float(p.unrealized_pl)
                pct = float(p.unrealized_plpc) * 100
                # Parse: MSFT260501C00420000 → MSFT $420 May01 CALL
                m = re.match(r'([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})', p.symbol)
                if m:
                    sym, yy, mm, dd, cp, strike_raw = m.groups()
                    strike = int(strike_raw) / 1000
                    months = ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
                    label = f"{sym} ${strike:.0f} {months[int(mm)]}{dd} {'CALL' if cp=='C' else 'PUT'}"
                else:
                    label = p.symbol
                lines.append(f"  {'🟢' if pnl >= 0 else '🔴'} `{label}` {pnl:+.0f} ({pct:+.1f}%)")

        return "\n".join(lines)
    except Exception as e:
        return f"*{name.upper()}*: Error - {e}"


if __name__ == "__main__":
    header = f"📈 *P&L Report* — {datetime.now().strftime('%b %d %H:%M')}\n"
    reports = [account_report(name, acct, baseline) for name, (acct, baseline) in ACCOUNTS.items()]
    msg = header + "\n\n".join(reports)
    notify(msg)
    print(msg)
