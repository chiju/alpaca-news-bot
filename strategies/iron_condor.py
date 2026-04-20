"""Iron Condor strategy - sell OTM call + OTM put on same underlying."""
import re
from datetime import datetime, timedelta
from strategies.base import BaseStrategy
from strategy_config.params import DTE_MIN, DTE_MAX

# Iron Condor specific params
IC_DELTA      = 0.15   # sell 15-delta wings (further OTM than CSP)
IC_WIDTH      = 5      # $5 spread width each side
IC_MIN_CREDIT = 1.00   # min $1.00 total credit ($100 per condor)

class IronCondor(BaseStrategy):

    name    = "Iron Condor"
    symbols = ["SPY", "IWM", "PLTR", "SOFI", "IONQ"]  # affordable for $100K account

    def find_entries(self, prices: dict, max_capital: float) -> list:
        entries = []
        for symbol in self.symbols:
            price = prices.get(symbol)
            if not price:
                continue
            best = self._best_condor(symbol, price)
            if best:
                entries.append((best["sell_put"],  # use sell_put as primary key
                    f"${best['put_strike']:.0f}P/${best['call_strike']:.0f}C "
                    f"{best['expiry']} ({best['dte']}d) | "
                    f"Credit: ${best['credit']*100:.0f} | "
                    f"Range: ${best['put_strike']:.0f}-${best['call_strike']:.0f}"))
        return entries

    def _best_condor(self, symbol, price):
        try:
            chain = self.broker.option_chain(symbol, DTE_MIN, DTE_MAX)

            puts  = {}
            calls = {}
            for sym, snap in chain.items():
                m = re.search(r'\d{6}([CP])\d{8}', sym)
                if not m or not snap.greeks or not snap.latest_quote:
                    continue
                bid = snap.latest_quote.bid_price or 0
                ask = snap.latest_quote.ask_price or 0
                if bid <= 0:
                    continue
                try:
                    offset = len(symbol)
                    strike = int(sym[offset + 7:]) / 1000
                    expiry_str = sym[offset:offset + 6]
                    dte    = (datetime.strptime(expiry_str, "%y%m%d").date() - datetime.now().date()).days
                    expiry = datetime.strptime(expiry_str, "%y%m%d").strftime("%b %d")
                except:
                    continue

                entry = {"sym": sym, "bid": bid, "ask": ask,
                         "delta": abs(snap.greeks.delta), "dte": dte, "expiry": expiry}

                if m.group(1) == "P":
                    puts[strike] = entry
                else:
                    calls[strike] = entry

            # Find best put side (sell OTM put ~15 delta)
            put_candidates = [(s, d) for s, d in puts.items()
                              if 0.10 <= d["delta"] <= 0.20 and s < price]
            call_candidates = [(s, d) for s, d in calls.items()
                               if 0.10 <= d["delta"] <= 0.20 and s > price]

            if not put_candidates or not call_candidates:
                return None

            # Best put = highest premium with right delta
            best_put_strike, best_put = max(put_candidates, key=lambda x: x[1]["bid"])
            best_call_strike, best_call = max(call_candidates, key=lambda x: x[1]["bid"])

            # Buy wings (protection)
            buy_put_strike  = best_put_strike - IC_WIDTH
            buy_call_strike = best_call_strike + IC_WIDTH
            buy_put  = puts.get(buy_put_strike)
            buy_call = calls.get(buy_call_strike)

            if not buy_put or not buy_call:
                return None

            # Net credit = sell put + sell call - buy put - buy call
            net_credit = (best_put["bid"] + best_call["bid"] -
                          buy_put["ask"] - buy_call["ask"])

            if net_credit < IC_MIN_CREDIT:
                return None

            return {
                "sell_put":    best_put["sym"],
                "sell_call":   best_call["sym"],
                "buy_put":     buy_put["sym"],
                "buy_call":    buy_call["sym"],
                "put_strike":  best_put_strike,
                "call_strike": best_call_strike,
                "credit":      net_credit,
                "capital":     IC_WIDTH * 100,
                "dte":         best_put["dte"],
                "expiry":      best_put["expiry"],
            }

        except Exception as e:
            print(f"IC chain error {symbol}: {e}")
            return None

    def run(self) -> list[str]:
        """Override to handle 4-leg orders."""
        if not self.broker.is_open():
            return [f"{self.name}: Market closed"]

        from core.risk import daily_loss_ok
        account = self.broker.account()
        if not daily_loss_ok(account):
            return [f"🛑 {self.name}: Daily loss limit hit"]

        results = []

        # Close exits
        for sym, reason in self.find_exits():
            try:
                self.broker.close(sym)
                results.append(f"✅ Closed `{sym}` | {reason}")
            except Exception as e:
                results.append(f"⚠️ Close failed: {e}")

        from strategy_config.params import MAX_POSITIONS
        open_opts = [p for p in self.broker.positions()
                     if float(p.qty) < 0 and re.search(r'\d{6}[CP]\d{8}', p.symbol)]
        if len(open_opts) >= MAX_POSITIONS * 2:  # 2 short legs per condor
            results.append(f"⏸️ Max positions reached")
            return results

        from core.risk import max_trade_capital
        prices = self.broker.latest_prices(self.symbols)
        open_syms = {re.match(r'([A-Z]+)', p.symbol).group(1) for p in open_opts}

        for symbol in self.symbols:
            if symbol in open_syms:
                continue
            price = prices.get(symbol)
            if not price:
                continue

            best = self._best_condor(symbol, price)
            if not best:
                continue

            try:
                from alpaca.trading.requests import MarketOrderRequest
                from alpaca.trading.enums import OrderSide, TimeInForce
                for sym, side in [
                    (best["sell_put"],  OrderSide.SELL),
                    (best["sell_call"], OrderSide.SELL),
                    (best["buy_put"],   OrderSide.BUY),
                    (best["buy_call"],  OrderSide.BUY),
                ]:
                    self.broker.submit(MarketOrderRequest(
                        symbol=sym, qty=1,
                        side=side, time_in_force=TimeInForce.DAY
                    ))
                results.append(
                    f"✅ `{symbol}` Iron Condor\n"
                    f"   ${best['put_strike']:.0f}P / ${best['call_strike']:.0f}C "
                    f"{best['expiry']} | Credit: ${best['credit']*100:.0f}"
                )
                open_syms.add(symbol)
            except Exception as e:
                results.append(f"⚠️ `{symbol}` failed: {e}")

        return results or ["No trades placed."]
