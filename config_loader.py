"""
Load account credentials.
Local:   reads ~/.alpaca/{strategy}-paper.env
GitHub:  reads ALPACA_{STRATEGY}_API_KEY from env
"""
import os


def load_account(strategy: str) -> dict:
    """Load credentials for a named account."""
    # Load strategy-specific env file first (takes priority)
    _specific = os.path.expanduser(f"~/.alpaca/{strategy}-paper.env")
    _default  = os.path.expanduser("~/.alpaca/options-paper.env")

    env_vars = {}

    # Load default first (for Telegram/Sheets creds)
    if os.path.exists(_default):
        for line in open(_default):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    # Override with strategy-specific creds if file exists
    if os.path.exists(_specific):
        for line in open(_specific):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()

    # Apply to os.environ
    for k, v in env_vars.items():
        os.environ[k] = v

    # Also check GitHub Secrets prefix
    prefix = f"ALPACA_{strategy.upper()}_"
    key    = os.environ.get(f"{prefix}API_KEY")    or env_vars.get("ALPACA_API_KEY")
    secret = os.environ.get(f"{prefix}SECRET_KEY") or env_vars.get("ALPACA_SECRET_KEY")

    return {
        "key":            key,
        "secret":         secret,
        "telegram_token": env_vars.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat":  env_vars.get("TELEGRAM_CHAT_ID", ""),
        "sheet_id":       env_vars.get("GOOGLE_SHEET_ID", ""),
    }
