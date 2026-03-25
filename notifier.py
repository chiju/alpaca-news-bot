"""Send messages to Telegram."""
import os, requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT_ID"]


def send(text: str):
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT, "text": chunk,
                  "parse_mode": "Markdown", "disable_web_page_preview": True},
            timeout=10,
        ).raise_for_status()
