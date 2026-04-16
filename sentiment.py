"""FinBERT sentiment via HuggingFace Inference API."""
import os, requests

EMOJI = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}

def _hf(): return os.environ.get("HF_TOKEN", "")


def get_sentiment(text: str) -> tuple:
    """Returns (label, score) e.g. ('positive', 0.95). Falls back to keyword scoring."""
    hf = _hf()
    if hf:
        try:
            r = requests.post(
                "https://router.huggingface.co/hf-inference/models/ProsusAI/finbert",
                headers={"Authorization": f"Bearer {hf}"},
                json={"inputs": text[:200]}, timeout=10,
            )
            result = r.json()
            if isinstance(result, list) and result:
                top = max(result[0], key=lambda x: x["score"])
                return top["label"], top["score"]
        except Exception:
            pass
    # Keyword fallback
    t = text.lower()
    pos = sum(1 for w in ["surge","rally","beat","strong","gain","rise","bullish","upgrade","record"] if w in t)
    neg = sum(1 for w in ["drop","fall","miss","weak","loss","decline","bearish","downgrade","crash"] if w in t)
    if pos > neg: return "positive", 0.6
    if neg > pos: return "negative", 0.6
    return "neutral", 0.5


def sentiment_emoji(label: str, score: float) -> str:
    return f"{EMOJI.get(label, '⚪')} {label} ({score:.0%})"


def generate_summary(mkt_mood: str, positive: list, negative: list) -> str:
    """Generate 4-line summary via Groq (free) or return empty string."""
    pos = ", ".join(set(s for x in positive for s in x.get("syms", []))) or "none"
    neg = ", ".join(set(s for x in negative for s in x.get("syms", []))) or "none"
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        return ""
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.1-8b-instant",
                  "messages": [{"role": "user", "content":
                      f"Write 4 short bullet points for a trader briefing. Market: {mkt_mood}. "
                      f"Positive stocks: {pos}. Negative stocks: {neg}. Under 12 words each."}],
                  "max_tokens": 120}, timeout=15
        )
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""
