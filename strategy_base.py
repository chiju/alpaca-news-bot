"""
Base Strategy class - all strategies inherit from this.
Enforces position sizing, risk/reward, and trading rules.
"""
from dataclasses import dataclass
from abc import ABC, abstractmethod
from alpaca.trading.client import TradingClient


@dataclass
class TradeRules:
    max_position_pct: float = 0.20   # max 20% of account per trade
    max_positions:    int   = 5      # max open positions
    min_risk_reward:  float = 2.0    # min 1:2 R:R
    profit_target:    float = 0.50   # close at 50% profit
    stop_loss_mult:   float = 2.0    # close if loss > 2x premium
    close_dte:        int   = 7      # close 7 days before expiry
    max_daily_loss:   float = 0.02   # halt if account down 2% today


@dataclass
class Signal:
    symbol:     str
    action:     str        # OPEN / CLOSE / HOLD
    contract:   str = ""   # option contract symbol
    reason:     str = ""
    confidence: float = 0.0


class BaseStrategy(ABC):
    """All strategies must implement these methods."""

    def __init__(self, key: str, secret: str, rules: TradeRules = None):
        self.key    = key
        self.secret = secret
        self.rules  = rules or TradeRules()
        self.client = TradingClient(api_key=key, secret_key=secret, paper=True)

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def account_value(self) -> float:
        return float(self.client.get_account().portfolio_value)

    def cash(self) -> float:
        return float(self.client.get_account().cash)

    def max_capital_per_trade(self) -> float:
        return self.account_value() * self.rules.max_position_pct

    def open_positions(self) -> list:
        return self.client.get_all_positions()

    def is_market_open(self) -> bool:
        try:
            return self.client.get_clock().is_open
        except:
            return True

    def check_daily_loss_limit(self) -> bool:
        """Returns True if safe to trade, False if daily loss limit hit."""
        account = self.client.get_account()
        equity = float(account.equity)
        last_equity = float(account.last_equity)
        if last_equity > 0:
            daily_pnl_pct = (equity - last_equity) / last_equity
            if daily_pnl_pct <= -self.rules.max_daily_loss:
                return False
        return True

    @abstractmethod
    def find_trades(self, prices: dict) -> list[Signal]:
        """Find new trade opportunities. Returns list of Signals."""
        pass

    @abstractmethod
    def manage_positions(self) -> list[Signal]:
        """Check existing positions for exit signals."""
        pass

    @abstractmethod
    def execute(self, signal: Signal) -> str:
        """Execute a trade signal. Returns result message."""
        pass

    def run(self) -> str:
        """Main entry point - enforces all rules."""
        if not self.is_market_open():
            return f"{self.name}: Market closed"

        if not self.check_daily_loss_limit():
            return f"🛑 {self.name}: Daily loss limit hit - halting"

        results = []

        # Step 1: Manage existing positions
        for signal in self.manage_positions():
            result = self.execute(signal)
            results.append(result)

        # Step 2: Check position count
        positions = self.open_positions()
        if len(positions) >= self.rules.max_positions:
            results.append(f"⏸️ Max {self.rules.max_positions} positions reached")
            return "\n".join(results)

        # Step 3: Find new trades
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockLatestBarRequest
        stock_client = StockHistoricalDataClient(api_key=self.key, secret_key=self.secret)
        bars = stock_client.get_stock_latest_bar(
            StockLatestBarRequest(symbol_or_symbols=self.symbols)
        )
        prices = {sym: bar.close for sym, bar in bars.items()}

        for signal in self.find_trades(prices):
            if len(self.open_positions()) >= self.rules.max_positions:
                break
            result = self.execute(signal)
            results.append(result)

        return "\n".join(results) if results else "No trades placed."
