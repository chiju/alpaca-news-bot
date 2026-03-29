from dotenv import load_dotenv
import os, sys

# Load from ~/.alpaca/options-paper.env locally, or GitHub Secrets in CI
_env = os.path.expanduser("~/.alpaca/options-paper.env")
if os.path.exists(_env):
    load_dotenv(_env, override=True)
else:
    load_dotenv(override=True)  # fallback to .env if exists

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
IS_PAPER = os.getenv("IS_PAPER", "true").lower() == "true"
