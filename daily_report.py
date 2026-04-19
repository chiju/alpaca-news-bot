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
    from notifier import send as _send
    _send(msg)


def _save_performance_snapshot():
    """Append today's equity + win rate + risk metrics to PERFORMANCE_LOG sheet."""
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        return
    try:
        creds_json = os.environ.get("GOOGLE_CREDENTIALS")
        if not creds_json:
            return
        import json
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_service_account_info(
            json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"])
        svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

        meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
        tabs = {s["properties"]["title"] for s in meta["sheets"]}
        if "PERFORMANCE_LOG" not in tabs:
            svc.spreadsheets().batchUpdate(spreadsheetId=sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": "PERFORMANCE_LOG"}}}]}).execute()
            svc.spreadsheets().values().update(spreadsheetId=sheet_id, range="PERFORMANCE_LOG!A1",
                valueInputOption="RAW", body={"values": [[
                    "date",
                    "wheel_equity", "wheel_pnl",
                    "csp_equity", "csp_pnl",
                    "bull_put_equity", "bull_put_pnl",
                    "iron_condor_equity", "iron_condor_pnl",
                    "covered_call_equity", "covered_call_pnl",
                    "total_equity", "total_pnl",
                    "open_positions", "winning_positions", "win_rate_pct",
                    "max_position_pct", "position_sizing_ok",
                    "avg_unrealized_pnl_pct"
                ]]}).execute()

        today = datetime.now().strftime("%Y-%m-%d")
        row = [today]
        total_equity = total_baseline = 0
        all_positions = []

        for name, (acct, baseline) in ACCOUNTS.items():
            try:
                cfg = load_account(acct)
                broker = Broker(cfg["key"], cfg["secret"])
                acc = broker.account()
                equity = float(acc.equity)
                pnl = equity - baseline
                row += [round(equity, 2), round(pnl, 2)]
                total_equity += equity
                total_baseline += baseline
                # Collect option positions for risk metrics
                for p in broker.positions():
                    if re.search(r'\d{6}[CP]\d{8}', p.symbol):
                        all_positions.append({
                            "pnl": float(p.unrealized_pl),
                            "pnl_pct": float(p.unrealized_plpc) * 100,
                            "value": abs(float(p.market_value)),
                            "equity": equity,
                        })
            except Exception:
                row += ["", ""]

        row += [round(total_equity, 2), round(total_equity - total_baseline, 2)]

        # Risk metrics across all accounts
        if all_positions:
            winning = [p for p in all_positions if p["pnl"] > 0]
            win_rate = round(len(winning) / len(all_positions) * 100, 1)
            # Position sizing: each position should be < 20% of account
            oversized = [p for p in all_positions if p["equity"] > 0 and p["value"] / p["equity"] > 0.20]
            sizing_ok = "✅" if not oversized else f"❌ {len(oversized)} oversized"
            max_pos_pct = round(max(p["value"] / p["equity"] * 100 for p in all_positions if p["equity"] > 0), 1)
            avg_pnl_pct = round(sum(p["pnl_pct"] for p in all_positions) / len(all_positions), 1)
            row += [len(all_positions), len(winning), win_rate, max_pos_pct, sizing_ok, avg_pnl_pct]
        else:
            row += [0, 0, 0, 0, "N/A", 0]

        svc.spreadsheets().values().append(spreadsheetId=sheet_id, range="PERFORMANCE_LOG!A2",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": [row]}).execute()
        print(f"📊 Performance snapshot saved — {len(all_positions)} positions, win rate: {row[-4]}%")
    except Exception as e:
        print(f"Performance snapshot error: {e}")


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
        # Stock positions
        stocks = [p for p in positions if not re.search(r'\d{6}[CP]\d{8}', p.symbol)]
        if stocks:
            lines.append(f"Stocks ({len(stocks)}):")
            for p in stocks:
                pnl = float(p.unrealized_pl)
                lines.append(f"  {'🟢' if pnl >= 0 else '🔴'} `{p.symbol}` x{int(float(p.qty))}  {pnl:+.0f}")

        # Option positions
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
    _save_performance_snapshot()
