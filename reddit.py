"""Reddit sentiment - scrapes WSB/stocks/investing for portfolio symbols."""
import requests
from collections import defaultdict

SUBREDDITS = ["wallstreetbets", "stocks", "investing"]
HEADERS = {"User-Agent": "PortfolioBot/1.0"}


def get_reddit_sentiment(symbols: list, limit: int = 25) -> dict:
    """
    Returns {symbol: {"mentions": int, "bullish": int, "bearish": int, "posts": list}}
    Uses Reddit JSON API - no API key needed.
    """
    results = defaultdict(lambda: {"mentions": 0, "bullish": 0, "bearish": 0, "posts": []})
    
    bull_words = {"buy", "calls", "moon", "bullish", "long", "upside", "breakout", "squeeze"}
    bear_words = {"sell", "puts", "short", "bearish", "crash", "dump", "overvalued", "downside"}

    for sub in SUBREDDITS:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}"
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            posts = r.json()["data"]["children"]
            for post in posts:
                data = post["data"]
                title = data.get("title", "").upper()
                text = (data.get("selftext", "") + " " + title).lower()
                
                for sym in symbols:
                    # Match $TSLA, TSLA, or tsla in title/text
                    if (f"${sym}" in title or 
                        f" {sym} " in f" {title} " or
                        f" {sym.lower()} " in f" {text} "):
                        results[sym]["mentions"] += 1
                        words = set(text.split())
                        if words & bull_words:
                            results[sym]["bullish"] += 1
                        elif words & bear_words:
                            results[sym]["bearish"] += 1
                        if len(results[sym]["posts"]) < 2:
                            results[sym]["posts"].append({
                                "title": data["title"][:80],
                                "score": data.get("score", 0),
                                "url": f"https://reddit.com{data.get('permalink', '')}"
                            })
        except Exception as e:
            print(f"Reddit {sub} error: {e}")
    
    return {k: v for k, v in results.items() if v["mentions"] > 0}


def format_reddit_section(reddit_data: dict) -> str:
    if not reddit_data:
        return ""
    
    lines = ["\n*🤖 Reddit Buzz*"]
    # Sort by mentions
    for sym, data in sorted(reddit_data.items(), key=lambda x: x[1]["mentions"], reverse=True)[:5]:
        bull = data["bullish"]
        bear = data["bearish"]
        mood = "🟢" if bull > bear else ("🔴" if bear > bull else "⚪")
        lines.append(f"• `{sym}` {mood} {data['mentions']} mentions ({bull}🟢 {bear}🔴)")
        for p in data["posts"][:1]:
            lines.append(f"  _{p['title']}_")
    
    return "\n".join(lines)
