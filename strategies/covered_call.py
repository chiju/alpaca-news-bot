"""Covered Call strategy - sell calls on owned 100+ share positions."""
import re
from datetime import datetime, timedelta
from strategies.base import BaseStrategy
from strategy_config.params import DELTA_MIN, DELTA_MAX, DTE_MIN, DTE_MAX


class CoveredCall(BaseStrategy):

    name    = "Covered Call"
    symbols = []  # dynamically set from owned positions

    def find_entries(self, prices: dict, max_capital: float) -> list:
        entries = []
        # Only sell calls on stocks we own 100+ shares
        positions = self.broker.positions()
        owned = {p.symbol: (float(p.current_price), int(float(p.qty)))
                 for p in positions
                 if not re.search(r'\d{6}[CP]\d{8}', p.symbol)
                 and int(float(p.qty)) >= 100}

        if not owned:
            return []  # No 100-share positions, nothing to do

        # Skip if already have a call on this stock
        open_calls = {re.match(r'([A-Z]+)', p.symbol).group(1)
                      for p in positions
                      if float(p.qty) < 0 and re.search(r'\d{6}C\d{8}', p.symbol)}

        for symbol, (price, qty) in owned.items():
            if symbol in open_calls:
                continue
            best = self._best_call(symbol, price)
            if best:
                entries.append((best["contract"],
                    f"${best['strike']:.0f}C {best['expiry']} ({best['dte']}d) | "
                    f"δ{best['delta']:.2f} | ${best['bid']*100:.0f} premium | "
                    f"Ann: {best['ann']:.0f}%"))
        return entries

    def _best_call(self, symbol, price):
        try:
            chain = self.broker.option_chain(symbol, DTE_MIN, DTE_MAX)
            candidates = []
            for sym, snap in chain.items():
                m = re.search(r'\d{6}([CP])\d{8}', sym)
                if not m or m.group(1) != "C":
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
                if strike <= price:  # only OTM calls
                    continue
                candidates.append({
                    "contract": sym, "bid": bid, "delta": delta,
                    "strike": strike, "expiry": expiry, "dte": dte,
                    "ann": (bid / price) * (365 / dte) * 100,
                })
            return max(candidates, key=lambda x: x["ann"]) if candidates else None
        except Exception as e:
            print(f"CC chain error {symbol}: {e}")
            return None
