"""Risk management - position sizing and daily loss checks."""
import re
from strategy_config.params import MAX_POSITION_PCT, MAX_DAILY_LOSS


def calculate_risk(positions) -> float:
    """Total capital at risk from open positions."""
    risk = 0.0
    for p in positions:
        sym = p.symbol
        if re.search(r'\d{6}P\d{8}', sym):  # short put
            try:
                strike = int(sym[-8:]) / 1000
                risk += strike * 100 * abs(int(float(p.qty)))
            except:
                pass
        elif not re.search(r'\d{6}[CP]\d{8}', sym):  # stock
            risk += float(p.avg_entry_price) * abs(int(float(p.qty)))
    return risk


def max_trade_capital(account_value: float) -> float:
    return account_value * MAX_POSITION_PCT


def daily_loss_ok(account) -> bool:
    equity      = float(account.equity)
    last_equity = float(account.last_equity)
    if last_equity > 0:
        return (equity - last_equity) / last_equity > -MAX_DAILY_LOSS
    return True
