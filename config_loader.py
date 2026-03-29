"""
Load account credentials.
Local:   reads ~/.alpaca/{strategy}-paper.env
GitHub:  reads ALPACA_{STRATEGY}_API_KEY from env
"""
import os


def load_account(strategy: str) -> dict:
    # Load local env file if exists
    for path in [f"~/.alpaca/{strategy}-paper.env", "~/.alpaca/options-paper.env"]:
        _path = os.path.expanduser(path)
        if os.path.exists(_path):
            for line in open(_path):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    prefix = f"ALPACA_{strategy.upper()}_"
    key    = os.environ.get(f"{prefix}API_KEY")    or os.environ["ALPACA_API_KEY"]
    secret = os.environ.get(f"{prefix}SECRET_KEY") or os.environ["ALPACA_SECRET_KEY"]

    return {
        "key":            key,
        "secret":         secret,
        "telegram_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat":  os.environ.get("TELEGRAM_CHAT_ID", ""),
        "sheet_id":       os.environ.get("GOOGLE_SHEET_ID", ""),
    }
