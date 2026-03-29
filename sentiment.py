"""FinBERT sentiment + Llama summary via HuggingFace."""
import os, requests

EMOJI = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}

def _hf():
    return os.environ.get("HF_TOKEN", "")


def get_sentiment(text: str) -> tuple[str, float]:
    """Returns (label, score) e.g. ('positive', 0.95)"""
    try:
        r = requests.post(
            "https://router.huggingface.co/hf-inference/models/ProsusAI/finbert",
            headers={"Authorization": f"Bearer {_hf()}"},
            json={"inputs": text[:200]},
            timeout=15,
        )
        result = r.json()
        if isinstance(result, list) and result:
            top = max(result[0], key=lambda x: x["score"])
            return top["label"], top["score"]
    except Exception:
        pass
    return "neutral", 0.0


def sentiment_emoji(label: str, score: float) -> str:
    return f"{EMOJI.get(label, '⚪')} {label} ({score:.0%})"


def generate_summary(mkt_mood: str, positive: list, negative: list) -> str:
    pos = ", ".join(set(s for x in positive for s in x["syms"])) or "none"
    neg = ", ".join(set(s for x in negative for s in x["syms"])) or "none"
    prompt = f"""Write exactly 4 short bullet points for a trader's morning briefing:
- Overall market is {mkt_mood}
- Stocks with positive news: {pos}
- Stocks with negative news: {neg}
Keep each line under 12 words. No headers, no labels, just 4 plain lines."""
    try:
        r = requests.post(
            "https://router.huggingface.co/novita/v3/openai/chat/completions",
            headers={"Authorization": f"Bearer {_hf()}"},
            json={"model": "meta-llama/llama-3.1-8b-instruct",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 120},
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return ""
