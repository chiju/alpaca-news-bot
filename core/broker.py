"""Single Alpaca broker facade - all API calls go through here."""
import os
from alpaca.trading.client import TradingClient
from alpaca.data.historical import OptionHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import OptionChainRequest, StockLatestBarRequest


class Broker:
    """Facade over all Alpaca clients."""

    def __init__(self, key: str, secret: str):
        self.key    = key
        self.secret = secret
        self._trade  = TradingClient(api_key=key, secret_key=secret, paper=True)
        self._stock  = StockHistoricalDataClient(api_key=key, secret_key=secret)
        self._option = OptionHistoricalDataClient(api_key=key, secret_key=secret)

    def account(self):
        return self._trade.get_account()

    def positions(self):
        return self._trade.get_all_positions()

    def is_open(self) -> bool:
        try:
            return self._trade.get_clock().is_open
        except:
            return True

    def latest_prices(self, symbols: list) -> dict:
        bars = self._stock.get_stock_latest_bar(
            StockLatestBarRequest(symbol_or_symbols=symbols)
        )
        return {sym: bar.close for sym, bar in bars.items()}

    def option_chain(self, symbol: str, dte_min: int, dte_max: int):
        from datetime import datetime, timedelta
        return self._option.get_option_chain(OptionChainRequest(
            underlying_symbol=symbol,
            expiration_date_gte=datetime.now().date() + timedelta(days=dte_min),
            expiration_date_lte=datetime.now().date() + timedelta(days=dte_max),
        ))

    def submit(self, order):
        return self._trade.submit_order(order)

    def close(self, symbol: str):
        return self._trade.close_position(symbol)
