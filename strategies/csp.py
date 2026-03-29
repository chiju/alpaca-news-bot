"""Cash-Secured Put strategy."""
import re
from datetime import datetime, timedelta
from strategies.base import BaseStrategy
from strategy_config.params import DELTA_MIN, DELTA_MAX, DTE_MIN, DTE_MAX, CSP_OTM_MIN, CSP_OTM_MAX


class CashSecuredPut(BaseStrategy):

    name    = "CSP"
    symbols = ["NVDA", "PLTR", "IONQ", "OKLO", "SOFI", "AMZN", "META", "TSLA"]

    def find_entries(self, prices: dict, max_capital: float) -> list:
        entries = []
        for symbol in self.symbols:
            price = prices.get(symbol)
            if not price:
                continue
            best = self._best_put(symbol, price, max_capital)
            if best:
                entries.append((best["contract"],
                    f"${best['strike']:.0f}P {best['expiry']} ({best['dte']}d) | "
                    f"δ{best['delta']:.2f} | {best['otm']:.0f}% OTM | "
                    f"${best['bid']*100:.0f} premium | Ann:{best['ann']:.0f}%"))
        return entries

    def _best_put(self, symbol, price, max_capital):
        try:
            chain = self.broker.option_chain(symbol, DTE_MIN, DTE_MAX)
            candidates = []
            for sym, snap in chain.items():
                m = re.search(r'\d{6}([CP])\d{8}', sym)
                if not m or m.group(1) != "P":
                    continue
                if not snap.greeks or not snap.latest_quote:
                    continue
                bid   = snap.latest_quote.bid_price or 0
                delta = abs(snap.greeks.delta)
                if not (DELTA_MIN <= delta <= DELTA_MAX) or bid <= 0:
                    continue
                try:
                    offset = len(symbol)
                    strike = int(sym[offset + 7:]) / 1000
                    expiry_str = sym[offset:offset + 6]
                    dte    = (datetime.strptime(expiry_str, "%y%m%d").date() - datetime.now().date()).days
                    expiry = datetime.strptime(expiry_str, "%y%m%d").strftime("%b %d")
                except:
                    continue
                otm = (price - strike) / price
                if not (CSP_OTM_MIN <= otm <= CSP_OTM_MAX):
                    continue
                if strike * 100 > max_capital:
                    continue
                candidates.append({
                    "contract": sym, "bid": bid, "delta": delta,
                    "strike": strike, "expiry": expiry, "dte": dte,
                    "otm": otm * 100,
                    "ann": (bid / strike) * (365 / dte) * 100,
                })
            return max(candidates, key=lambda x: x["ann"]) if candidates else None
        except Exception as e:
            print(f"CSP chain error {symbol}: {e}")
            return None
