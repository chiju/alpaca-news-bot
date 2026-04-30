"""Bull Put Spread strategy - capital efficient options income."""
import re
from datetime import datetime, timedelta
from strategies.base import BaseStrategy
from strategy_config.params import DELTA_MIN, DELTA_MAX, DTE_MIN, DTE_MAX

SPREAD_WIDTH = 5  # $5 between strikes = $500 capital per spread
MIN_CREDIT   = 0.80  # min $0.80 net credit ($80 per spread)
MIN_ROC      = 0.15  # min 15% return on capital


class BullPutSpread(BaseStrategy):

    name    = "Bull Put Spread"
    symbols = ["NVDA", "PLTR", "AMZN", "META", "TSLA", "QQQ", "IONQ", "OKLO"]

    def find_entries(self, prices: dict, max_capital: float) -> list:
        entries = []
        for symbol in self.symbols:
            price = prices.get(symbol)
            if not price:
                continue
            best = self._best_spread(symbol, price)
            if best:
                entries.append((best["sell_sym"],
                    f"${best['sell_strike']:.0f}P/${best['buy_strike']:.0f}P "
                    f"{best['expiry']} ({best['dte']}d) | "
                    f"Credit: ${best['credit']*100:.0f} | "
                    f"Capital: ${best['capital']:.0f} | "
                    f"ROC: {best['roc']:.0f}%"))
        return entries

    def _best_spread(self, symbol, price):
        try:
            chain = self.broker.option_chain(symbol, DTE_MIN, DTE_MAX)

            # Collect all puts with valid data
            puts = {}
            for sym, snap in chain.items():
                m = re.search(r'\d{6}([CP])\d{8}', sym)
                if not m or m.group(1) != "P":
                    continue
                if not snap.greeks or not snap.latest_quote:
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
                puts[strike] = {"sym": sym, "bid": bid, "ask": ask,
                                "delta": abs(snap.greeks.delta),
                                "dte": dte, "expiry": expiry}

            # Find sell leg: delta 0.20-0.30
            candidates = []
            for strike, data in puts.items():
                if not (DELTA_MIN <= data["delta"] <= DELTA_MAX):
                    continue

                # Find buy leg: SPREAD_WIDTH below
                buy_strike = strike - SPREAD_WIDTH
                buy_data = puts.get(buy_strike)
                if not buy_data:
                    # Find nearest available
                    available = [s for s in puts if s < strike and s >= strike - SPREAD_WIDTH - 2]
                    if not available:
                        continue
                    buy_strike = max(available)
                    buy_data = puts[buy_strike]

                net_credit = data["bid"] - buy_data["ask"]
                if net_credit < MIN_CREDIT:
                    continue

                spread_width = strike - buy_strike
                capital = spread_width * 100
                roc = (net_credit * 100) / capital * 100

                if roc < MIN_ROC * 100:
                    continue

                candidates.append({
                    "sell_sym": data["sym"],
                    "buy_sym":  buy_data["sym"],
                    "sell_strike": strike,
                    "buy_strike":  buy_strike,
                    "credit":  net_credit,
                    "capital": capital,
                    "roc":     roc,
                    "delta":   data["delta"],
                    "dte":     data["dte"],
                    "expiry":  data["expiry"],
                })

            return max(candidates, key=lambda x: x["roc"]) if candidates else None

        except Exception as e:
            print(f"BPS chain error {symbol}: {e}")
            return None

    def run(self) -> list[str]:
        """Override to handle two-leg orders."""
        if not self.broker.is_open():
            return [f"{self.name}: Market closed"]

        from core.risk import daily_loss_ok
        account = self.broker.account()
        if not daily_loss_ok(account):
            return [f"🛑 {self.name}: Daily loss limit hit"]

        results = []

        # Close profitable spreads (check short leg)
        for sym, reason in self.find_exits():
            try:
                self.broker.close(sym)
                results.append(f"✅ Closed `{sym}` | {reason}")
            except Exception as e:
                results.append(f"⚠️ Close failed: {e}")

        # Count open spreads (short puts = number of spreads)
        from strategy_config.params import MAX_POSITIONS
        all_positions = self.broker.positions()
        open_short_puts = [p for p in all_positions
                           if float(p.qty) < 0 and re.search(r'\d{6}P\d{8}', p.symbol)]
        open_syms = {re.match(r'([A-Z]+)', p.symbol).group(1) for p in open_short_puts}

        if len(open_short_puts) >= MAX_POSITIONS:
            results.append(f"⏸️ Max {MAX_POSITIONS} spreads open")
            return results

        from core.risk import max_trade_capital
        account_value = float(account.portfolio_value)
        prices = self.broker.latest_prices(self.symbols)

        for symbol in self.symbols:
            if len(open_short_puts) >= MAX_POSITIONS:
                break
            if symbol in open_syms:
                continue
            price = prices.get(symbol)
            if not price:
                continue

            best = self._best_spread(symbol, price)
            if not best:
                continue

            try:
                from alpaca.trading.requests import MarketOrderRequest
                from alpaca.trading.enums import OrderSide, TimeInForce
                # Buy lower strike FIRST (so sell is covered, not naked)
                self.broker.submit(MarketOrderRequest(
                    symbol=best["buy_sym"], qty=1,
                    side=OrderSide.BUY, time_in_force=TimeInForce.DAY
                ))
                # Then sell higher strike (now it's a spread, not naked)
                self.broker.submit(MarketOrderRequest(
                    symbol=best["sell_sym"], qty=1,
                    side=OrderSide.SELL, time_in_force=TimeInForce.DAY
                ))
                results.append(
                    f"✅ `{symbol}` Bull Put Spread\n"
                    f"   ${best['sell_strike']:.0f}P/${best['buy_strike']:.0f}P "
                    f"{best['expiry']} | Credit: ${best['credit']*100:.0f} | "
                    f"ROC: {best['roc']:.0f}%"
                )
                open_syms.add(symbol)
                open_short_puts.append(None)  # increment count
            except Exception as e:
                results.append(f"⚠️ `{symbol}` failed: {e}")

        return results or ["No trades placed."]
