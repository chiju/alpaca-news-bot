"""Base strategy - all strategies inherit from this."""
import re
from abc import ABC, abstractmethod
from datetime import datetime
from core.broker import Broker
from core.risk import max_trade_capital, daily_loss_ok
from strategy_config.params import MAX_POSITIONS, PROFIT_TARGET, STOP_LOSS_MULT, CLOSE_DTE


class BaseStrategy(ABC):

    def __init__(self, broker: Broker):
        self.broker = broker

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def symbols(self) -> list:
        pass

    @abstractmethod
    def find_entries(self, prices: dict, max_capital: float) -> list:
        """Return list of (contract_symbol, description) to open."""
        pass

    def find_exits(self) -> list:
        """Return list of (position_symbol, reason) to close."""
        exits = []
        for p in self.broker.positions():
            sym = p.symbol
            if float(p.qty) >= 0 or not re.search(r'\d{6}[CP]\d{8}', sym):
                continue

            entry   = abs(float(p.avg_entry_price))
            current = abs(float(p.current_price))
            profit  = (entry - current) / entry if entry > 0 else 0

            try:
                underlying = re.match(r'([A-Z]+)', sym).group(1)
                expiry_str = sym[len(underlying):len(underlying)+6]
                dte = (datetime.strptime(expiry_str, "%y%m%d").date() - datetime.now().date()).days
            except:
                dte = 99

            if profit >= PROFIT_TARGET:
                exits.append((sym, f"50% profit ({profit:.0%})"))
            elif profit <= -STOP_LOSS_MULT:
                exits.append((sym, f"Stop loss ({profit:.0%})"))
            elif dte <= CLOSE_DTE:
                exits.append((sym, f"Near expiry ({dte}d)"))

        return exits

    def run(self) -> list[str]:
        """Execute strategy - returns list of result messages."""
        if not self.broker.is_open():
            return [f"{self.name}: Market closed"]

        account = self.broker.account()
        if not daily_loss_ok(account):
            return [f"🛑 {self.name}: Daily loss limit hit"]

        results = []

        # Close exits first
        for sym, reason in self.find_exits():
            try:
                self.broker.close(sym)
                results.append(f"✅ Closed `{sym}` | {reason}")
            except Exception as e:
                results.append(f"⚠️ Close failed {sym}: {e}")

        # Check position count
        open_opts = [p for p in self.broker.positions()
                     if float(p.qty) < 0 and re.search(r'\d{6}[CP]\d{8}', p.symbol)]
        if len(open_opts) >= MAX_POSITIONS:
            results.append(f"⏸️ Max {MAX_POSITIONS} positions")
            return results

        # Open entries
        account_value = float(account.portfolio_value)
        prices = self.broker.latest_prices(self.symbols)
        open_syms = {p.symbol[:4] for p in open_opts}

        for contract, desc in self.find_entries(prices, max_trade_capital(account_value)):
            if len(open_opts) >= MAX_POSITIONS:
                break
            underlying = re.match(r'([A-Z]+)', contract).group(1)
            if underlying in open_syms:
                continue
            try:
                from alpaca.trading.requests import MarketOrderRequest
                from alpaca.trading.enums import OrderSide, TimeInForce
                self.broker.submit(MarketOrderRequest(
                    symbol=contract, qty=1,
                    side=OrderSide.SELL, time_in_force=TimeInForce.DAY
                ))
                results.append(f"✅ `{underlying}` | {desc}")
                open_syms.add(underlying)
            except Exception as e:
                results.append(f"⚠️ `{underlying}` failed: {e}")

        return results or ["No trades placed."]
