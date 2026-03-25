"""Trade journal - auto-sync paper trades from Alpaca to Google Sheets."""
import os, json, re
from datetime import datetime


def _sheets_service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    key_file = os.path.expanduser("~/Desktop/down/yahoo-portfolio-data-44dbe4ae4313.json")
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if os.path.exists(key_file):
        creds = Credentials.from_service_account_file(
            key_file, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    else:
        creds = Credentials.from_service_account_info(
            json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _parse_option_symbol(symbol: str) -> dict:
    """Parse OCC symbol e.g. TSLA260430C00350000"""
    try:
        m = re.match(r"([A-Z]+)(\d{6})([CP])(\d{8})", symbol)
        if not m:
            return {}
        sym, date, cp, strike = m.groups()
        expiry = datetime.strptime(date, "%y%m%d").strftime("%Y-%m-%d")
        strike_price = int(strike) / 1000
        strategy = "Covered Call" if cp == "C" else "Cash-Secured Put"
        return {"symbol": sym, "expiry": expiry, "strike": strike_price, "strategy": strategy}
    except:
        return {}


def sync_trades():
    """Sync all filled options orders from Alpaca paper account to Google Sheets."""
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        return

    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus

    client = TradingClient(
        api_key=os.environ["ALPACA_API_KEY"],
        secret_key=os.environ["ALPACA_SECRET_KEY"],
        paper=True
    )

    # Get existing contracts in journal to avoid duplicates
    try:
        service = _sheets_service()
        existing = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range="Trade Journal!D:D"
        ).execute().get("values", [])
        existing_contracts = {r[0] for r in existing if r}
    except:
        existing_contracts = set()

    # Fetch filled orders
    orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=50))

    new_rows = []
    for o in orders:
        if not o.symbol or o.filled_avg_price is None:
            continue
        # Only options (contain digits in symbol)
        if not re.search(r'\d{6}[CP]', o.symbol):
            continue
        if o.symbol in existing_contracts:
            continue

        parsed = _parse_option_symbol(o.symbol)
        if not parsed:
            continue

        date = o.created_at.strftime("%Y-%m-%d")
        side = "SELL" if str(o.side) == "OrderSide.SELL" else "BUY"
        premium = float(o.filled_avg_price) * 100  # per contract
        status = "OPEN" if side == "SELL" else "CLOSED"

        new_rows.append([
            date, parsed["symbol"], parsed["strategy"], o.symbol,
            parsed["strike"], parsed["expiry"], "", f"${premium:.2f}",
            "", "", status, ""
        ])

    if new_rows:
        service = _sheets_service()
        # Insert after header (row 2) so newest trades appear at top
        sheet_meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheet_id_num = next(
            s["properties"]["sheetId"] for s in sheet_meta["sheets"]
            if s["properties"]["title"] == "Trade Journal"
        )
        # Insert blank rows after header
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"insertDimension": {
                "range": {"sheetId": sheet_id_num, "dimension": "ROWS",
                          "startIndex": 1, "endIndex": 1 + len(new_rows)},
                "inheritFromBefore": False
            }}]}
        ).execute()
        # Write to the newly inserted rows
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"Trade Journal!A2:L{1 + len(new_rows)}",
            valueInputOption="USER_ENTERED",
            body={"values": new_rows}
        ).execute()
        print(f"✅ Synced {len(new_rows)} trades to journal")
    else:
        print("No new trades to sync")
