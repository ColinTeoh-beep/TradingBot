"""
Configuration settings for the MT5 Auto-Trading Bot.
Adjust these parameters to match your trading style and risk tolerance.

MT5 credentials are loaded from environment variables by default:
    MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, MT5_PATH
You can also set them directly below for local development.
"""

# ─── MT5 Connection ────────────────────────────────────────────────
import os

MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))  # Your MT5 account number
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")  # Your MT5 account password
MT5_SERVER = os.getenv("MT5_SERVER", "")  # Your broker's MT5 server name
MT5_PATH = os.getenv("MT5_PATH", "")  # Path to terminal64.exe (optional)

# ─── Symbol & Timeframes ──────────────────────────────────────────
SYMBOL = "EURUSD"
HIGHER_TIMEFRAME = "H4"  # Higher timeframe for market structure / zone analysis
LOWER_TIMEFRAME = "M15"  # Lower timeframe for entry confluence

# ─── Market Analysis ──────────────────────────────────────────────
# Number of candles to fetch for analysis
HTF_CANDLE_COUNT = 500
LTF_CANDLE_COUNT = 500

# Supply/Demand zone detection
ZONE_LOOKBACK = 50  # Candles to look back for swing detection
ZONE_BODY_RATIO = 0.5  # Min body-to-range ratio for strong candles
ZONE_TOUCH_INVALIDATION = 3  # Zone invalidated after N re-touches

# FVG recency: only consider FVGs within the last N candles
FVG_RECENCY_CANDLES = 10

# ─── Confluence Requirements (Lower TF) ──────────────────────────
# Minimum number of confluences required on the lower timeframe to open a trade.
MIN_CONFLUENCES = 3

# Individual confluence toggles (enabled by default)
USE_STRUCTURE_CONFLUENCE = True  # Market structure (BOS / CHoCH)
USE_EMA_CONFLUENCE = True  # EMA alignment
USE_RSI_CONFLUENCE = True  # RSI overbought / oversold
USE_ENGULFING_CONFLUENCE = True  # Engulfing candlestick pattern
USE_FVG_CONFLUENCE = True  # Fair Value Gap

# EMA settings
EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 21

# RSI settings
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# How close (as a multiplier) price must be to a zone to trigger bias
# e.g. 1.002 means within 0.2% above a demand zone high
ZONE_PROXIMITY_TOLERANCE = 1.002

# ─── Trading Plan / Order ────────────────────────────────────────
# Risk-Reward Ratio (TP distance = SL distance * RR_RATIO)
RR_RATIO = 2.0

# SL buffer in points added beyond the zone boundary
SL_BUFFER_POINTS = 50  # 50 points ≈ 5 pips for 5-digit brokers

# Order filling type: "IOC", "FOK", or "RETURN"
# IOC = Immediate-Or-Cancel (default for most brokers)
ORDER_FILLING_TYPE = "IOC"

# ─── Risk Management ─────────────────────────────────────────────
RISK_PERCENT = 1.0  # % of balance risked per trade (applies to total across layers)
MAX_OPEN_TRADES = 5  # Max simultaneous open positions on the symbol

# ─── Break-Even ──────────────────────────────────────────────────
BREAKEVEN_ENABLED = True
# Move SL to break-even when price moves this multiple of SL distance in profit
BREAKEVEN_TRIGGER_RR = 1.0
# Offset from entry (in points) when moving to break-even (to cover spread/commission)
BREAKEVEN_OFFSET_POINTS = 10

# ─── Trailing Stop ───────────────────────────────────────────────
TRAILING_STOP_ENABLED = True
# Activate trailing after price reaches this RR multiple in profit
TRAILING_ACTIVATION_RR = 1.5
# Trail distance in points behind the current price
TRAILING_DISTANCE_POINTS = 100

# ─── Layering ────────────────────────────────────────────────────
LAYERING_ENABLED = True
MAX_LAYERS = 3  # Maximum number of layered entries
# Distance between layers in points
LAYER_DISTANCE_POINTS = 100
# All layers share the SL and TP of the first entry
# Risk is split equally across layers so total risk = RISK_PERCENT

# ─── Timing ──────────────────────────────────────────────────────
BOT_LOOP_INTERVAL_SECONDS = 10  # Main loop sleep between iterations
