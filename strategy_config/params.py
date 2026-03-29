"""Strategy parameters - single source of truth for all strategies."""

# Position sizing
MAX_POSITION_PCT  = 0.20   # max 20% of account per trade
MAX_POSITIONS     = 5      # max open positions at once
MAX_DAILY_LOSS    = 0.02   # halt if account down 2% today

# Option selection
DELTA_MIN         = 0.20
DELTA_MAX         = 0.30
DTE_MIN           = 21
DTE_MAX           = 45
OI_MIN            = 50     # min open interest (liquidity)
SCORE_MIN         = 0.05   # min composite score

# CSP specific
CSP_OTM_MIN       = 0.10   # min 10% below price
CSP_OTM_MAX       = 0.15   # max 15% below price

# Bull Put Spread specific
SPREAD_WIDTH      = 5      # $5 between strikes

# Exit rules
PROFIT_TARGET     = 0.50   # close at 50% profit
STOP_LOSS_MULT    = 2.0    # close if loss > 2x premium
CLOSE_DTE         = 7      # close 7 days before expiry
