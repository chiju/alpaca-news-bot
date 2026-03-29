"""Options flow - detect unusual activity using Alpaca options chain."""
import os
from datetime import datetime, timedelta
from alpaca.data.historical import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest

def _key():    return os.environ.get("ALPACA_API_KEY", "")
def _secret(): return os.environ.get("ALPACA_SECRET_KEY", "")

# Unusual = volume > open_interest * threshold
UNUSUAL_THRESHOLD = 2.0   # 2x open interest = unusual
MIN_PREMIUM       = 10000  # Min $10k notional to filter noise


def get_unusual_flow(symbols: list) -> list:
    """
    Returns list of unusual options activity:
    [{"symbol", "contract", "type", "strike", "expiry", "volume", "oi", "ratio", "premium", "side"}]
    """
    client = OptionHistoricalDataClient(api_key=_key(), secret_key=_secret())
    unusual = []

    for sym in symbols:
        try:
            req = OptionChainRequest(
                underlying_symbol=sym,
                expiration_date_gte=datetime.now().date(),
                expiration_date_lte=(datetime.now() + timedelta(days=60)).date(),
            )
            chain = client.get_option_chain(req)

            for contract_sym, snap in chain.items():
                if snap.latest_quote is None:
                    continue

                volume = getattr(snap, "volume", 0) or 0
                oi     = getattr(snap, "open_interest", 0) or 0
                bid    = snap.latest_quote.bid_price or 0

                if oi == 0 or volume == 0 or bid == 0:
                    continue

                ratio = volume / oi
                if ratio < UNUSUAL_THRESHOLD:
                    continue

                # Parse contract type and strike
                try:
                    offset = len(sym)
                    cp = contract_sym[offset + 6]  # C or P
                    strike = int(contract_sym[offset + 7:]) / 1000
                    expiry_str = contract_sym[offset:offset + 6]
                    expiry = datetime.strptime(expiry_str, "%y%m%d").strftime("%b %d")
                    dte = (datetime.strptime(expiry_str, "%y%m%d").date() - datetime.now().date()).days
                except Exception:
                    continue

                premium = bid * volume * 100
                if premium < MIN_PREMIUM:
                    continue

                unusual.append({
                    "symbol":   sym,
                    "contract": contract_sym,
                    "type":     "CALL" if cp == "C" else "PUT",
                    "strike":   strike,
                    "expiry":   expiry,
                    "dte":      dte,
                    "volume":   int(volume),
                    "oi":       int(oi),
                    "ratio":    round(ratio, 1),
                    "premium":  round(premium),
                    "side":     "🐂 Bullish" if cp == "C" else "🐻 Bearish",
                })

        except Exception as e:
            print(f"Options flow error {sym}: {e}")

    # Sort by premium (biggest money first)
    return sorted(unusual, key=lambda x: x["premium"], reverse=True)


def format_flow_section(flow: list) -> str:
    if not flow:
        return ""

    lines = ["\n*🐳 Unusual Options Flow*"]
    lines.append("_(Volume > 2× Open Interest)_\n")

    for f in flow[:5]:  # top 5
        lines.append(
            f"• `{f['symbol']}` {f['side']} | {f['type']} ${f['strike']:.0f} {f['expiry']} "
            f"| Vol: {f['volume']:,} / OI: {f['oi']:,} ({f['ratio']}×) "
            f"| 💰 ${f['premium']:,}"
        )

    return "\n".join(lines)
