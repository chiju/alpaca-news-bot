# The max dollar risk allowed by the strategy.  
MAX_RISK = 100_000

# The range of allowed Delta (absolute value) when choosing puts or calls to sell.  
DELTA_MIN = 0.20 
DELTA_MAX = 0.35

# The range of allowed yield when choosing puts or calls to sell.
YIELD_MIN = 0.01
YIELD_MAX = 1.00

# The range of allowed days till expiry when choosing puts or calls to sell.
EXPIRATION_MIN = 21
EXPIRATION_MAX = 45

# Only trade contracts with at least this much open interest.
OPEN_INTEREST_MIN = 100

# The minimum score passed to core.strategy.select_options().
SCORE_MIN = 0.05