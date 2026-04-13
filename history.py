"""Persist sentiment history to SQLite (local/repo) + Google Sheets (visualization)."""
import sqlite3, os, json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "sentiment_history.db")


def _conn():
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS history (
        symbol TEXT, label TEXT, score REAL, headline TEXT, url TEXT, ts TEXT
    )""")
    # Auto-migrate: add new columns if they don't exist
    existing = {row[1] for row in db.execute("PRAGMA table_info(history)")}
    migrations = {
        "source": "TEXT DEFAULT 'benzinga'",
    }
    for col, definition in migrations.items():
        if col not in existing:
            db.execute(f"ALTER TABLE history ADD COLUMN {col} {definition}")
    db.commit()
    return db


def is_seen_today(url: str) -> bool:
    """Returns True if this URL was already sent today."""
    today = datetime.utcnow().isoformat()[:10]
    with _conn() as db:
        return bool(db.execute(
            "SELECT 1 FROM history WHERE url=? AND ts LIKE ?",
            (url, f"{today}%")
        ).fetchone())


def save(symbol: str, label: str, score: float, headline: str = "", url: str = "", dedup_key: str = ""):
    """Save to SQLite and Google Sheets."""
    ts = datetime.utcnow().isoformat()
    today = ts[:10]
    key = dedup_key or url

    with _conn() as db:
        if key:
            exists = db.execute(
                "SELECT 1 FROM history WHERE url=? AND ts LIKE ?",
                (key, f"{today}%")
            ).fetchone()
        else:
            exists = db.execute(
                "SELECT 1 FROM history WHERE symbol=? AND headline=? AND ts LIKE ?",
                (symbol, headline[:100], f"{today}%")
            ).fetchone()

        if exists:
            return

        db.execute("INSERT INTO history VALUES (?,?,?,?,?,?,?)",
                   (symbol, label, score, headline[:100], key, ts, "benzinga"))

    _append_to_sheets(symbol, label, score, headline, url, ts)  # real url for display


def get_trend(symbol: str, last_n: int = 3) -> str:
    emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}
    with _conn() as db:
        rows = db.execute(
            "SELECT label FROM history WHERE symbol=? ORDER BY ts DESC LIMIT ?",
            (symbol, last_n)
        ).fetchall()
    return "".join(emoji.get(r[0], "⚪") for r in reversed(rows))


def _get_or_create_sheet(service, sheet_id: str, symbol: str) -> int:
    """Get or create a sheet tab for the symbol. Returns sheet ID number."""
    meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    sheets = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

    if symbol not in sheets:
        # Create new sheet tab for this symbol
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": symbol}}}]}
        ).execute()
        # Add headers
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{symbol}!A1:G1",
            valueInputOption="USER_ENTERED",
            body={"values": [["Date", "Time", "Symbol", "Sentiment", "Score %", "Headline", "URL"]]}
        ).execute()
        # Re-fetch to get new sheet ID
        meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheets = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

    return sheets[symbol]


def _append_to_sheets(symbol: str, label: str, score: float, headline: str, url: str, ts: str):
    """Append a row to per-symbol Google Sheets tab."""
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        return

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        key_file = os.path.expanduser("~/Desktop/down/yahoo-portfolio-data-44dbe4ae4313.json")
        creds_json = os.environ.get("GOOGLE_CREDENTIALS")

        if os.path.exists(key_file):
            creds = Credentials.from_service_account_file(
                key_file, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        elif creds_json:
            creds = Credentials.from_service_account_info(
                json.loads(creds_json), scopes=["https://www.googleapis.com/auth/spreadsheets"])
        else:
            return

        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}
        from datetime import timedelta
        utc_dt = datetime.fromisoformat(ts)
        cet_dt = utc_dt + timedelta(hours=1)
        date, time = cet_dt.strftime("%Y-%m-%d"), cet_dt.strftime("%H:%M")

        # Get or create per-symbol sheet tab
        sheet_id_num = _get_or_create_sheet(service, sheet_id, symbol)

        # Insert at row 2 (newest first)
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"insertDimension": {
                "range": {"sheetId": sheet_id_num, "dimension": "ROWS",
                          "startIndex": 1, "endIndex": 2},
                "inheritFromBefore": False
            }}]}
        ).execute()

        # Write to row 2 of symbol's tab
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{symbol}!A2:G2",
            valueInputOption="USER_ENTERED",
            body={"values": [[date, time, symbol, emoji.get(label, "⚪") + " " + label,
                              round(score * 100), headline[:100], url]]}
        ).execute()
    except Exception as e:
        print(f"Sheets warning: {e}")
