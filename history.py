"""Persist sentiment history to SQLite (local/repo) + Google Sheets (visualization)."""
import sqlite3, os, json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "sentiment_history.db")


def _conn():
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS history (
        symbol TEXT, label TEXT, score REAL, headline TEXT, ts TEXT
    )""")
    db.commit()
    return db


def save(symbol: str, label: str, score: float, headline: str = ""):
    """Save to SQLite and Google Sheets - skip if same headline already saved today."""
    ts = datetime.utcnow().isoformat()
    today = ts[:10]

    with _conn() as db:
        # Check if same symbol + headline already saved today
        exists = db.execute(
            "SELECT 1 FROM history WHERE symbol=? AND headline=? AND ts LIKE ?",
            (symbol, headline[:100], f"{today}%")
        ).fetchone()

        if exists:
            return  # Skip duplicate

        db.execute("INSERT INTO history VALUES (?,?,?,?,?)",
                   (symbol, label, score, headline[:100], ts))

    # Only append to Sheets if not a duplicate
    _append_to_sheets(symbol, label, score, headline, ts)


def get_trend(symbol: str, last_n: int = 3) -> str:
    emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}
    with _conn() as db:
        rows = db.execute(
            "SELECT label FROM history WHERE symbol=? ORDER BY ts DESC LIMIT ?",
            (symbol, last_n)
        ).fetchall()
    return "".join(emoji.get(r[0], "⚪") for r in reversed(rows))


def _append_to_sheets(symbol: str, label: str, score: float, headline: str, ts: str):
    """Append a row to Google Sheets."""
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        return

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        # Load from file (local) or env JSON (GitHub Actions)
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
        date, time = ts[:10], ts[11:16]

        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Sheet1!A:F",
            valueInputOption="USER_ENTERED",
            body={"values": [[date, time, symbol, emoji.get(label, "⚪") + " " + label,
                              round(score * 100), headline[:100]]]}
        ).execute()
    except Exception as e:
        print(f"Sheets warning: {e}")
