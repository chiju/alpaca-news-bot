"""
Sentiment history persistence — Google Sheets only (no SQLite).
Filesystem = Google Sheets. Works in GitHub Actions and locally.
"""
import os, json
from datetime import datetime, timedelta


SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "")
SCOPES   = ["https://www.googleapis.com/auth/spreadsheets"]


def _svc():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS", "")
    key_file   = os.path.expanduser("~/Desktop/down/yahoo-portfolio-data-44dbe4ae4313.json")
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    if os.path.exists(key_file):
        creds = Credentials.from_service_account_file(key_file, scopes=SCOPES)
    elif creds_json:
        creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=SCOPES)
    else:
        raise RuntimeError("No Google credentials found")
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _ensure_tab(svc, tab: str, headers: list):
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    tabs = [s["properties"]["title"] for s in meta["sheets"]]
    if tab not in tabs:
        svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={
            "requests": [{"addSheet": {"properties": {"title": tab}}}]
        }).execute()
        svc.spreadsheets().values().update(
            spreadsheetId=SHEET_ID, range=f"{tab}!A1",
            valueInputOption="RAW", body={"values": [headers]}).execute()


def is_seen_today(url: str) -> bool:
    """Returns True if this URL was already sent today."""
    if not SHEET_ID: return False
    today = datetime.utcnow().isoformat()[:10]
    try:
        svc = _svc()
        r = svc.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range="NEWS_SEEN!A:B").execute()
        return any(row and row[0] == url and len(row) > 1 and row[1][:10] == today
                   for row in r.get("values", [])[1:])
    except Exception:
        return False


def save(symbol: str, label: str, score: float, headline: str = "",
         url: str = "", dedup_key: str = ""):
    """Save sentiment entry and mark URL as seen. Deduplicates by URL per day."""
    if not SHEET_ID: return
    today = datetime.utcnow().isoformat()[:10]
    key = dedup_key or url
    if key and is_seen_today(key):
        return
    ts = datetime.utcnow().isoformat()
    try:
        svc = _svc()
        # 1. Mark as seen (dedup)
        _ensure_tab(svc, "NEWS_SEEN", ["url", "ts"])
        svc.spreadsheets().values().append(
            spreadsheetId=SHEET_ID, range="NEWS_SEEN!A:B",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": [[key, ts]]}).execute()

        # 2. Write to per-symbol tab
        emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}
        cet = datetime.utcnow() + timedelta(hours=2)
        _ensure_tab(svc, symbol, ["Date", "Time", "Symbol", "Sentiment", "Score%", "Headline", "URL"])
        # Insert at row 2 (newest first)
        meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
        sheet_id_num = next(
            s["properties"]["sheetId"] for s in meta["sheets"]
            if s["properties"]["title"] == symbol)
        svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={
            "requests": [{"insertDimension": {
                "range": {"sheetId": sheet_id_num, "dimension": "ROWS",
                          "startIndex": 1, "endIndex": 2},
                "inheritFromBefore": False}}]}).execute()
        svc.spreadsheets().values().update(
            spreadsheetId=SHEET_ID, range=f"{symbol}!A2:G2",
            valueInputOption="USER_ENTERED",
            body={"values": [[cet.strftime("%Y-%m-%d"), cet.strftime("%H:%M"),
                              symbol, emoji.get(label, "⚪") + " " + label,
                              round(score * 100), headline[:100], url]]}).execute()
    except Exception as e:
        print(f"  history.save warning: {e}")


def get_trend(symbol: str, last_n: int = 3) -> str:
    """Get last N sentiment labels as emoji string."""
    if not SHEET_ID: return ""
    emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}
    try:
        svc = _svc()
        r = svc.spreadsheets().values().get(
            spreadsheetId=SHEET_ID, range=f"{symbol}!D2:D{last_n+1}").execute()
        rows = r.get("values", [])
        labels = []
        for row in rows:
            if row:
                for k, v in emoji.items():
                    if k in row[0].lower():
                        labels.append(v)
                        break
        return "".join(reversed(labels))
    except Exception:
        return ""
