"""
Config loader - works locally and on GitHub Actions.
Local:   reads from ~/.alpaca/{account}.env
GitHub:  reads from environment variables (GitHub Secrets)
"""
import os


def load_env(env_file: str):
    """Load env file if it exists (local), otherwise use os.environ (GitHub Actions)."""
    path = os.path.expanduser(env_file)
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def get_account_config(account: str) -> dict:
    """
    Load credentials for a named account.
    
    account: "csp" | "covered_call" | "bull_put_spread" | "live"
    
    Local:   reads ~/.alpaca/{account}-paper.env
    GitHub:  reads ALPACA_{ACCOUNT}_API_KEY etc from env
    """
    # Try loading local env file first
    load_env(f"~/.alpaca/{account}-paper.env")
    load_env(f"~/.alpaca/options-paper.env")  # fallback for Telegram/Sheets creds

    # Map account name to env var prefix
    prefix = f"ALPACA_{account.upper()}_"

    # Try account-specific keys first, fall back to default ALPACA_API_KEY
    key    = os.environ.get(f"{prefix}API_KEY")    or os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get(f"{prefix}SECRET_KEY") or os.environ.get("ALPACA_SECRET_KEY")

    if not key or not secret:
        raise ValueError(f"No credentials found for account '{account}'. "
                         f"Set {prefix}API_KEY or ALPACA_API_KEY.")

    return {
        "key":           key,
        "secret":        secret,
        "telegram_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat":  os.environ.get("TELEGRAM_CHAT_ID", ""),
        "sheet_id":       os.environ.get("GOOGLE_SHEET_ID", ""),
        "hf_token":       os.environ.get("HF_TOKEN", ""),
    }
