"""Track sentiment history per symbol using SQLite."""
import sqlite3, os
from datetime import datetime

DB_PATH = os.path.expanduser("~/.alpaca/sentiment_history.db")


def _conn():
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS history (
        symbol TEXT, label TEXT, score REAL, ts TEXT
    )""")
    db.commit()
    return db


def save(symbol: str, label: str, score: float):
    with _conn() as db:
        db.execute("INSERT INTO history VALUES (?,?,?,?)",
                   (symbol, label, score, datetime.utcnow().isoformat()))


def get_trend(symbol: str, last_n: int = 5) -> str:
    """Returns emoji trend string e.g. '🟢🟢🔴⚪🟢'"""
    emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}
    with _conn() as db:
        rows = db.execute(
            "SELECT label FROM history WHERE symbol=? ORDER BY ts DESC LIMIT ?",
            (symbol, last_n)
        ).fetchall()
    return "".join(emoji.get(r[0], "⚪") for r in reversed(rows))
